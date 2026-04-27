"""Fixed-point solver for the split-decay 3-species ODE.

This module mirrors the structure of the existing 3-species solver in
:mod:`bifurcation_engine.src.fixed_points` (``find_fixed_points_3species`` /
``continuation_sweep_3species``) but reads :class:`SplitDecayConfig` instead
of :class:`ShellConfig`. The 2-D and 3-species production solvers are not
imported or modified here.

Public surface:

* :func:`find_fixed_points_split` — grid-seeded :func:`scipy.optimize.fsolve`
  scan with deduplication and physicality (non-negative populations) filter.
* :func:`continuation_sweep_split` — warm-started, all-branch continuation
  over a sweep in ``L`` with a grid rescan to spawn newly-born branches.

The split-decay system has no closed-form fixed-point equation (the three
nonlinear stationarity equations are coupled and degree-2 in ``D``), so the
grid-seeded approach is the only practical option at the experiment scale.
The grid scaling and tolerances are chosen to match the existing 3-species
solver as closely as possible so the experiment outcomes are directly
comparable.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

import numpy as np
from scipy.optimize import fsolve

from .model_split import (
    d_dot_split,
    r_dot_split,
    s_dot_split,
)
from .split_decay_config import SplitDecayConfig

__all__ = [
    "find_fixed_points_split",
    "continuation_sweep_split",
]


# Tolerances, mirroring the 3-species solver in ``fixed_points.py``.
_EPS = 1e-12
_GRID_STEPS_3D = 5
_DEDUP_REL_TOL_3D = 1e-6
_BRANCH_MATCH_REL = 0.05


def _residual_split(state: np.ndarray, params: SplitDecayConfig) -> np.ndarray:
    """Stationary-state residual ``[S_dot, R_dot, D_dot]`` at ``state``."""
    S = float(state[0])
    R = float(state[1])
    D = float(state[2])
    return np.array(
        [
            s_dot_split(S, R, D, params),
            r_dot_split(S, R, D, params),
            d_dot_split(S, R, D, params),
        ],
        dtype=float,
    )


def _refine(
    params: SplitDecayConfig,
    guess: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    """Polish a candidate ``(S, R, D)`` with :func:`fsolve`.

    Returns ``None`` if the solver fails, the residual stays large, or any
    coordinate is meaningfully negative. Tiny negatives (``-_EPS``) are
    snapped to zero to keep boundary equilibria like the clean orbit
    representable.
    """
    try:
        sol, _info, ier, _msg = fsolve(
            _residual_split,
            np.asarray(guess, dtype=float),
            args=(params,),
            full_output=True,
            xtol=1e-12,
        )
    except Exception:
        return None

    if ier != 1:
        return None

    S, R, D = float(sol[0]), float(sol[1]), float(sol[2])
    if S < -_EPS or R < -_EPS or D < -_EPS:
        return None

    res = _residual_split(np.asarray(sol, dtype=float), params)
    scale = 1.0 + abs(S) + abs(R) + abs(D)
    if float(np.linalg.norm(res)) > 1e-6 * scale:
        return None

    return (max(S, 0.0), max(R, 0.0), max(D, 0.0))


def _grid_seeds(params: SplitDecayConfig) -> list[tuple[float, float, float]]:
    """Coarse grid of ``(S, R, D)`` seeds spanning the natural species scales.

    Same scaling rationale as :func:`_grid_seeds_3species` in
    ``fixed_points.py``: each axis runs from 0 to twice the value the species
    would take in the relevant decoupled limit, so the seeds bracket both
    the clean-orbit and the high-debris regimes without per-shell tuning.

    * ``S`` from 0 to ``2 * L / delta_S`` (twice the clean-orbit value).
    * ``R`` from 0 to ``2 * L / delta_R``.
    * ``D`` from 0 to ``2 * delta_D / max(gamma, 1e-12)``.
    """
    delta_S = max(params.delta_S, 1e-12)
    delta_R = max(params.delta_R, delta_S * 1.5)
    gamma = max(params.gamma, 1e-12)

    S_max = max(2.0 * params.L / delta_S, 1.0)
    R_max = max(2.0 * params.L / delta_R, 1.0)
    D_max = max(2.0 * params.delta_D / gamma, 1.0)

    s_axis = np.linspace(0.0, S_max, _GRID_STEPS_3D)
    r_axis = np.linspace(0.0, R_max, _GRID_STEPS_3D)
    d_axis = np.linspace(0.0, D_max, _GRID_STEPS_3D)

    seeds: list[tuple[float, float, float]] = []
    for s in s_axis:
        for r in r_axis:
            for d in d_axis:
                seeds.append((float(s), float(r), float(d)))
    return seeds


def _is_duplicate(
    candidate: tuple[float, float, float],
    existing: list[tuple[float, float, float]],
    rel_tol: float = _DEDUP_REL_TOL_3D,
) -> bool:
    cx = np.asarray(candidate, dtype=float)
    for r in existing:
        rx = np.asarray(r, dtype=float)
        scale = max(float(np.linalg.norm(cx)), float(np.linalg.norm(rx)), 1.0)
        if float(np.linalg.norm(cx - rx)) <= rel_tol * scale:
            return True
    return False


def _with_launch_rate(params: SplitDecayConfig, L: float) -> SplitDecayConfig:
    """Return a copy of ``params`` with ``L`` overridden for one sweep step.

    The dataclass is frozen and validates on construction; we drop the sweep
    bounds so the new ``L`` is never rejected for falling outside the
    original window.
    """
    if L < 0.0:
        raise ValueError(f"Continuation L must be non-negative (got {L!r})")
    return replace(params, L=L, L_sweep_min=0.0, L_sweep_max=None)


def find_fixed_points_split(
    params: SplitDecayConfig,
    L: float | None = None,
) -> list[tuple[float, float, float]]:
    """Return every physically valid 3-species fixed point ``(S*, R*, D*)``.

    Parameters
    ----------
    params:
        Split-decay shell parameters. Reads ``L`` from ``params`` unless
        overridden by the ``L`` argument below.
    L:
        Optional override for the launch rate, useful for probing the same
        shell at any launch rate without rebuilding the dataclass.

    Returns
    -------
    list[tuple[float, float, float]]
        Distinct equilibria, deduplicated by relative Euclidean distance.
        Empty list if no physical solution is found.
    """
    local = params if L is None else _with_launch_rate(params, float(L))
    results: list[tuple[float, float, float]] = []
    for seed in _grid_seeds(local):
        refined = _refine(local, seed)
        if refined is None:
            continue
        if _is_duplicate(refined, results):
            continue
        results.append(refined)
    return results


def _match_branch(
    candidate: tuple[float, float, float],
    branches_last: list[tuple[float, float, float]],
    rel_tol: float = _BRANCH_MATCH_REL,
) -> int | None:
    if not branches_last:
        return None
    cx = np.asarray(candidate, dtype=float)
    best_idx: int | None = None
    best_dist = float("inf")
    for i, b in enumerate(branches_last):
        bx = np.asarray(b, dtype=float)
        scale = max(float(np.linalg.norm(bx)), float(np.linalg.norm(cx)), 1.0)
        d = float(np.linalg.norm(cx - bx)) / scale
        if d < best_dist:
            best_dist = d
            best_idx = i
    if best_idx is not None and best_dist <= rel_tol:
        return best_idx
    return None


def continuation_sweep_split(
    params: SplitDecayConfig,
    L_values: Sequence[float] | np.ndarray,
) -> list[dict[str, np.ndarray]]:
    """Track every coexistence branch across a sweep over ``L``.

    Strategy at each L step:

    1. **Warm-start** every active branch's last point through fsolve at the
       new L. Surviving warm starts continue their branch.
    2. **Grid scan** at the new L to catch new branches (e.g. born from a
       fold). Solutions matching an active branch's warm-started point are
       merged; orphans start a new branch.

    A branch is *terminated* at the L step where its warm start fails — that
    is the operational signature of the saddle-node fold in the split-decay
    model (the closed-form discriminant trick used for the 2-D model does
    not apply once R and three collision channels are coupled).

    Returns
    -------
    list[dict[str, np.ndarray]]
        One dict per branch with keys ``L``, ``S_star``, ``R_star``,
        ``D_star`` (all 1-D float arrays of equal length, monotone in ``L``).
        Branches are returned in birth order. Empty list when no physical
        fixed point exists at any sampled ``L``.
    """
    L_arr = np.asarray(L_values, dtype=float)
    if L_arr.ndim != 1:
        raise ValueError("L_values must be one-dimensional")

    branches: list[dict[str, list[float]]] = []
    last_point: list[tuple[float, float, float]] = []
    active: list[bool] = []

    for L_i in L_arr:
        local = _with_launch_rate(params, float(L_i))

        # Step 1: warm-start every active branch.
        warm_results: list[tuple[float, float, float] | None] = []
        for i, is_active in enumerate(active):
            if not is_active:
                warm_results.append(None)
                continue
            warm_results.append(_refine(local, last_point[i]))

        for i, w in enumerate(warm_results):
            if not active[i]:
                continue
            if w is None:
                active[i] = False
                continue
            branches[i]["L"].append(float(L_i))
            branches[i]["S_star"].append(w[0])
            branches[i]["R_star"].append(w[1])
            branches[i]["D_star"].append(w[2])
            last_point[i] = w

        # Step 2: grid scan to discover new branches at this L.
        scan = find_fixed_points_split(local)

        live_endpoints: list[tuple[float, float, float]] = []
        for i, is_active in enumerate(active):
            if is_active and warm_results[i] is not None:
                live_endpoints.append(last_point[i])

        for cand in scan:
            match = _match_branch(cand, live_endpoints)
            if match is not None:
                continue
            new_branch: dict[str, list[float]] = {
                "L": [float(L_i)],
                "S_star": [cand[0]],
                "R_star": [cand[1]],
                "D_star": [cand[2]],
            }
            branches.append(new_branch)
            last_point.append(cand)
            active.append(True)
            live_endpoints.append(cand)

    return [
        {
            "L": np.asarray(b["L"], dtype=float),
            "S_star": np.asarray(b["S_star"], dtype=float),
            "R_star": np.asarray(b["R_star"], dtype=float),
            "D_star": np.asarray(b["D_star"], dtype=float),
        }
        for b in branches
        if len(b["L"]) > 0
    ]
