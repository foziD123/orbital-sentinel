"""Export pre-computed bifurcation data for the Module 2 frontend.

Runs the bifurcation engine on all three default shells and writes three
static JSON files consumed by the frontend on page load:

  frontend/data/base_curves.json        -- lower/upper branch D* vs L per shell
  frontend/data/shell_current_state.json -- copy of real-world state JSON
  frontend/data/indicator_curves.json   -- recovery time, variance, AC curves

These files make the frontend fully functional even when the FastAPI server
is not running (Step 1 of MODULE2_PLAN.md: static-first architecture).

Usage:
    python scripts/export_frontend_data.py

No arguments. Run from the repo root.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np

from bifurcation_engine.src.early_warning import (
    autocorrelation_indicator,
    critical_slowing_down,
    variance_indicator,
)
from bifurcation_engine.src.eigenvalues import eigenvalue_pair
from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import detect_fold
from bifurcation_engine.src.integrator import integrate_trajectory
from bifurcation_engine.src.shell_config import load_shell_by_name

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DATA = REPO_ROOT / "frontend" / "data"
REAL_WORLD_JSON = REPO_ROOT / "data" / "real_world" / "shell_current_state.json"

SHELL_NAMES = ["Shell_A_600km", "Shell_B_800km", "Shell_C_1000km"]

# Number of L points for branch curves — 400 gives smooth curves at ~25 KB per shell.
N_BRANCH_POINTS = 400
# Number of L points for recovery-time sweep (lower branch only, up to 0.98 * L_fold).
N_INDICATOR_L_POINTS = 200


# ---------------------------------------------------------------------------
# Branch curve computation
# ---------------------------------------------------------------------------

def _case2_branches(
    shell, L_values: np.ndarray
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Return lower and upper Case-2 D* branch arrays across L_values.

    Mirrors _case2_branches from scripts/plot_shell_B_bifurcation.py but
    returns Python lists (not numpy arrays) for direct JSON serialisation.
    """
    L_low, D_low, L_up, D_up = [], [], [], []
    for L in L_values:
        local = replace(shell, L=float(L))
        roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
        if roots:
            L_low.append(float(L))
            D_low.append(float(roots[0][1]))
        if len(roots) == 2:
            L_up.append(float(L))
            D_up.append(float(roots[1][1]))
    return L_low, D_low, L_up, D_up


def _export_base_curves() -> dict:
    """Compute lower/upper branches + fold coordinates for all shells."""
    output: dict = {}
    for name in SHELL_NAMES:
        print(f"  {name}: computing branches...", end=" ", flush=True)
        shell = load_shell_by_name(name)

        # Detect fold on a fine grid to get accurate L_fold, S_fold, D_fold.
        L_fine = np.linspace(0.0, 1.2 * shell.L_sweep_max, 4001)
        fold = detect_fold(shell, L_fine)
        if fold.L_fold is None:
            raise RuntimeError(f"detect_fold returned no fold for {name}")
        L_fold = float(fold.L_fold)
        D_fold = float(fold.D_star_at_fold)
        S_fold = float(fold.S_star_at_fold)

        # Coarser grid for compact JSON: from near-zero to just past L_fold.
        L_branch = np.linspace(1.0, 1.05 * L_fold, N_BRANCH_POINTS)
        L_low, D_low, L_up, D_up = _case2_branches(shell, L_branch)

        output[name] = {
            "altitude_km": shell.altitude_km,
            "L_fold": L_fold,
            "D_fold": D_fold,
            "S_fold": S_fold,
            "L_sweep_max": float(shell.L_sweep_max),
            "params": {
                "delta_S": float(shell.delta_S),
                "delta_D": float(shell.delta_D),
                "beta": float(shell.beta),
                "gamma": float(shell.gamma),
                "L_default": float(shell.L),
            },
            "lower_branch": {"L": L_low, "D_star": D_low},
            "upper_branch": {"L": L_up, "D_star": D_up},
        }
        print(
            f"lower={len(L_low)} pts, upper={len(L_up)} pts, "
            f"L_fold={L_fold:.1f}"
        )
    return output


# ---------------------------------------------------------------------------
# Indicator curve computation
# ---------------------------------------------------------------------------

def _recovery_time_curve(shell, L_fold: float) -> dict:
    """1/|alpha| on the lower coexistence branch from L≈0 up to 0.98*L_fold."""
    L_vals = np.linspace(1.0, 0.98 * L_fold, N_INDICATOR_L_POINTS)
    L_valid: list[float] = []
    alpha_valid: list[float] = []

    for L in L_vals:
        local = replace(shell, L=float(L))
        roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
        if not roots:
            continue
        S_star, D_star = roots[0]
        alpha, _ = eigenvalue_pair(float(S_star), float(D_star), local)
        if np.isfinite(alpha):
            L_valid.append(float(L))
            alpha_valid.append(float(alpha))

    if not L_valid:
        return {"L": [], "recovery_time": []}

    result = critical_slowing_down(np.array(L_valid), np.array(alpha_valid))
    return {
        "L": [float(v) for v in result["L"]],
        "recovery_time": [float(v) for v in result["recovery_time"]],
    }


def _trajectory_indicators(shell, L_fold: float) -> dict:
    """Variance and lag-1 AC of D(t) from a trajectory at L = 0.9 * L_fold.

    Starting from the lower-branch equilibrium perturbed by +5% on D,
    integrating for min(500, 20/delta_S) years — long enough to show the
    slow return near the fold.
    """
    L_near = 0.9 * L_fold
    local = replace(shell, L=L_near)
    roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
    if not roots:
        empty: dict = {"t": [], "values": []}
        return {"variance": empty, "ac1": empty}

    S0, D0 = roots[0]
    t_final = min(500.0, 20.0 / shell.delta_S)
    traj = integrate_trajectory(
        float(S0), float(D0) * 1.05, local,
        t_span=(0.0, t_final),
        runaway_ceiling_D=1e10,
    )

    window = 50
    var_result = variance_indicator(traj, window=window)
    ac_result = autocorrelation_indicator(traj, lag=1, window=window)

    def _clean(arr: np.ndarray) -> list[float]:
        """Convert to list, replacing non-finite with None for JSON."""
        return [float(v) if np.isfinite(v) else None for v in arr]

    return {
        "variance": {
            "t": _clean(var_result["t"]),
            "values": _clean(var_result["variance_D"]),
        },
        "ac1": {
            "t": _clean(ac_result["t"]),
            "values": _clean(ac_result["ac1_D"]),
        },
    }


def _export_indicator_curves() -> dict:
    """Compute early-warning indicators for all shells."""
    output: dict = {}
    for name in SHELL_NAMES:
        print(f"  {name}: computing indicators...", end=" ", flush=True)
        shell = load_shell_by_name(name)

        L_fine = np.linspace(0.0, 1.2 * shell.L_sweep_max, 4001)
        fold = detect_fold(shell, L_fine)
        L_fold = float(fold.L_fold)

        rec = _recovery_time_curve(shell, L_fold)
        traj_ind = _trajectory_indicators(shell, L_fold)

        output[name] = {
            "altitude_km": shell.altitude_km,
            "L_fold": L_fold,
            "trajectory_L": 0.9 * L_fold,  # L used for variance/AC trajectory
            "recovery_time": rec,
            "variance": traj_ind["variance"],
            "ac1": traj_ind["ac1"],
        }
        print(
            f"recovery={len(rec['L'])} pts, "
            f"variance={len(traj_ind['variance']['t'])} pts, "
            f"ac1={len(traj_ind['ac1']['t'])} pts"
        )
    return output


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)

    # --- base_curves.json -----------------------------------------------
    print("\nStep 1a — base_curves.json")
    base = _export_base_curves()
    base_path = FRONTEND_DATA / "base_curves.json"
    with base_path.open("w", encoding="utf-8") as fh:
        json.dump(base, fh, separators=(",", ":"))
    print(f"  → {base_path.relative_to(REPO_ROOT)}  ({base_path.stat().st_size / 1024:.1f} KB)")

    # --- shell_current_state.json (copy) ---------------------------------
    print("\nStep 1b — shell_current_state.json (copy from data/real_world/)")
    if not REAL_WORLD_JSON.exists():
        raise FileNotFoundError(
            f"Missing {REAL_WORLD_JSON}\n"
            "Run scripts/fetch_realworld_data.py first to generate it."
        )
    dest = FRONTEND_DATA / "shell_current_state.json"
    shutil.copy2(REAL_WORLD_JSON, dest)
    print(f"  → {dest.relative_to(REPO_ROOT)}  (copied, {dest.stat().st_size} bytes)")

    # --- indicator_curves.json ------------------------------------------
    print("\nStep 1c — indicator_curves.json")
    indicators = _export_indicator_curves()
    ind_path = FRONTEND_DATA / "indicator_curves.json"
    with ind_path.open("w", encoding="utf-8") as fh:
        json.dump(indicators, fh, separators=(",", ":"))
    print(f"  → {ind_path.relative_to(REPO_ROOT)}  ({ind_path.stat().st_size / 1024:.1f} KB)")

    # --- Summary ---------------------------------------------------------
    print("\n" + "=" * 60)
    print("JSON structure summary")
    print("=" * 60)

    print("\nbase_curves.json  (top-level keys: shell names)")
    for name in SHELL_NAMES:
        bc = base[name]
        print(f"  {name}:")
        print(f"    altitude_km: {bc['altitude_km']}")
        print(f"    L_fold:      {bc['L_fold']:.1f}")
        print(f"    D_fold:      {bc['D_fold']:.1f}")
        print(f"    S_fold:      {bc['S_fold']:.1f}")
        print(f"    params:      {list(bc['params'].keys())}")
        print(f"    lower_branch: L[{len(bc['lower_branch']['L'])} pts], D_star[{len(bc['lower_branch']['D_star'])} pts]")
        print(f"    upper_branch: L[{len(bc['upper_branch']['L'])} pts], D_star[{len(bc['upper_branch']['D_star'])} pts]")

    print("\nshell_current_state.json  (unchanged copy — see data/real_world/)")
    print("  keys: epoch, data_source, methodology, shells{A,B,C}")
    print("  per shell: S_current, D_current, L_current, L_fold, L_fraction, traffic_light, ...")

    print("\nindicator_curves.json  (top-level keys: shell names)")
    for name in SHELL_NAMES:
        ic = indicators[name]
        print(f"  {name}:")
        print(f"    L_fold:          {ic['L_fold']:.1f}")
        print(f"    trajectory_L:    {ic['trajectory_L']:.1f}  (0.9 * L_fold)")
        print(f"    recovery_time:   L[{len(ic['recovery_time']['L'])} pts], recovery_time[{len(ic['recovery_time']['recovery_time'])} pts]")
        print(f"    variance:        t[{len(ic['variance']['t'])} pts], values[{len(ic['variance']['values'])} pts]")
        print(f"    ac1:             t[{len(ic['ac1']['t'])} pts], values[{len(ic['ac1']['values'])} pts]")

    print("\nAll three files written. Frontend can now load static data.")
    print("Run the FastAPI server (Step 2) to enable what-if scenarios.\n")


if __name__ == "__main__":
    main()
