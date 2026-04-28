"""Thin wrapper around the bifurcation engine for the FastAPI layer.

Only imports from bifurcation_engine.src — never modifies it.

compute_whatif() applies three what-if parameters to each default shell,
re-runs the bifurcation analysis, and returns the new lower-branch curve,
fold location, and traffic-light status. All three shells are computed
in a single call (MODULE2_PLAN.md constraint).

Debris removal is modelled as an additional linear decay on D:
    delta_D_eff = delta_D + debris_removal_rate / D_fold_base
This is dimensionally consistent: removing R objects/yr from a population
at the fold (D_fold) is equivalent to increasing the effective decay rate
by R / D_fold (1/yr units).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from bifurcation_engine.src.early_warning import (
    AMBER_RED_THRESHOLD,
    GREEN_AMBER_THRESHOLD,
)
from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import detect_fold
from bifurcation_engine.src.shell_config import load_shell_by_name

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_WORLD_JSON = REPO_ROOT / "data" / "real_world" / "shell_current_state.json"

SHELL_NAMES = ["Shell_A_600km", "Shell_B_800km", "Shell_C_1000km"]
SHELL_KEYS  = ["A", "B", "C"]

# Curve resolution for API responses — fewer points than static files
# for faster response times (~200 ms per shell).
N_CURVE_POINTS = 200


def _load_current_state() -> dict:
    with REAL_WORLD_JSON.open(encoding="utf-8") as fh:
        return json.load(fh)


def _classify(L_fraction: float) -> str:
    if L_fraction < GREEN_AMBER_THRESHOLD:
        return "green"
    if L_fraction < AMBER_RED_THRESHOLD:
        return "amber"
    return "red"


def _lower_branch_curve(shell, L_fold: float) -> list[dict]:
    """Return the lower Case-2 branch as [{L, D_star}] up to 1.05 × L_fold."""
    L_vals = np.linspace(1.0, 1.05 * L_fold, N_CURVE_POINTS)
    curve: list[dict] = []
    for L in L_vals:
        local = replace(shell, L=float(L))
        roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
        if roots:
            curve.append({"L": float(L), "D_star": float(roots[0][1])})
    return curve


def compute_whatif(
    L_multiplier: float,
    debris_removal_rate: float,
    gamma_multiplier: float,
) -> dict:
    """Compute modified bifurcation results for all three shells in one call.

    Parameters
    ----------
    L_multiplier:
        Scales the real-world L_current for each shell.
        1.0 = no change; 2.0 = launch cadence doubles.
    debris_removal_rate:
        Active removal in objects/yr. Added to the effective debris decay
        rate as delta_D_eff = delta_D + removal_rate / D_fold_base.
    gamma_multiplier:
        Scales the cascade coefficient gamma.
        1.0 = no change; 1.5 = 50% more energetic debris-on-debris cascade.

    Returns
    -------
    dict
        Keys are "A", "B", "C". Each value contains:
        - L_fold_new     : new saddle-node fold launch rate (float or None)
        - L_current_new  : new launch rate = L_current_base * L_multiplier
        - traffic_light  : "green" | "amber" | "red"
        - curve          : list of {L, D_star} dicts (lower branch only)
    """
    state = _load_current_state()
    result: dict = {}

    for name, key in zip(SHELL_NAMES, SHELL_KEYS):
        shell = load_shell_by_name(name)
        shell_state = state["shells"][name]
        L_current_base = float(shell_state["L_current"])

        # Detect base fold to get D_fold for normalising debris removal.
        L_fine = np.linspace(0.0, 1.2 * shell.L_sweep_max, 4001)
        base_fold = detect_fold(shell, L_fine)
        D_fold_base = float(base_fold.D_star_at_fold) if base_fold.D_star_at_fold else 1.0

        # Apply what-if modifications.
        L_new        = L_current_base * L_multiplier
        gamma_new    = shell.gamma * gamma_multiplier
        delta_D_new  = shell.delta_D + (debris_removal_rate / D_fold_base)

        modified = replace(shell, L=L_new, gamma=gamma_new, delta_D=delta_D_new)

        # Sweep wide enough to capture the fold even when L_new is large.
        L_max_sweep = max(1.2 * shell.L_sweep_max, 1.5 * L_new, 1.2 * D_fold_base)
        L_sweep_new = np.linspace(0.0, L_max_sweep, 4001)
        fold_new = detect_fold(modified, L_sweep_new)

        if fold_new.L_fold is None:
            result[key] = {
                "L_fold_new": None,
                "L_current_new": float(L_new),
                "traffic_light": "green",
                "curve": [],
            }
        else:
            L_fold_new = float(fold_new.L_fold)
            L_fraction = L_new / L_fold_new
            result[key] = {
                "L_fold_new": L_fold_new,
                "L_current_new": float(L_new),
                "traffic_light": _classify(L_fraction),
                "curve": _lower_branch_curve(modified, L_fold_new),
            }

    return result
