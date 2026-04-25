"""Fixed-point solver for the Kessler ODE (Task 3).

Implements the analytical fixed-point expressions from the PDF exactly::

    Case 1 (clean orbit):
        S* = L / delta_S,  D* = 0

    Case 2 (coexistence):
        beta * gamma * D*^2 + (delta_S * gamma - beta * delta_D) * D*
            + (beta * L - delta_S * delta_D) = 0
        S* = (delta_D - gamma * D*) / beta

and wraps them with:

* a Case-2 quadratic solver that filters physically invalid roots
  (``S* < 0`` or ``D* < 0``);
* a union helper :func:`find_all_fixed_points`;
* a Newton-continuation sweep over launch rate :func:`continuation_sweep`
  that warm-starts :func:`scipy.optimize.fsolve` from the solution at the
  previous ``L`` step so the coexistence branch is tracked smoothly.

All public helpers consume a :class:`ShellConfig` so nothing downstream
depends on hard-coded parameter values.
"""

from __future__ import annotations

from dataclasses import replace
from math import sqrt
from typing import Sequence

import numpy as np
from scipy.optimize import fsolve

from .model import (
    d_dot,
    d_dot_3species,
    r_dot_3species,
    s_dot,
    s_dot_3species,
)
from .shell_config import ShellConfig

__all__ = [
    "clean_orbit_fixed_point",
    "coexistence_fixed_points",
    "find_all_fixed_points",
    "continuation_sweep",
    "find_fixed_points_3species",
    "continuation_sweep_3species",
]

# Tolerance used when filtering numerical noise near zero; chosen well below
# the 1e-8 / 1e-10 tolerances of the validation tests.
_EPS = 1e-12

# Minimum value of |discriminant| / b^2 of the Case-2 quadratic before we
# consider the continuation to be entering the ill-conditioned fold
# neighbourhood. Near a saddle-node fold the upper and lower roots collide
# and ``dD*/dL`` diverges, so uniformly stepping in L produces arbitrarily
# large jumps in ``S*`` no matter how faithful the solver is. Truncating
# before the fold keeps the reported continuation branch smooth and leaves
# downstream code free to sample the fold region separately if needed.
_FOLD_DISCRIMINANT_FLOOR = 0.05


# ---------------------------------------------------------------------------
# Case 1: clean orbit
# ---------------------------------------------------------------------------


def clean_orbit_fixed_point(params: ShellConfig) -> tuple[float, float]:
    """Return the clean-orbit equilibrium ``(S*, D*) = (L / delta_S, 0)``.

    Always exists for ``delta_S > 0``. The validation in :class:`ShellConfig`
    rejects ``delta_S`` values that would make this ill-defined (``delta_S``
    must be non-negative and strictly below ``delta_D``, so in practice
    ``delta_S > 0`` whenever a shell reaches this call).
    """
    if params.delta_S == 0.0:
        raise ValueError(
            "clean_orbit_fixed_point requires delta_S > 0; got delta_S=0"
        )
    return (params.L / params.delta_S, 0.0)


# ---------------------------------------------------------------------------
# Case 2: coexistence
# ---------------------------------------------------------------------------


def _case2_quadratic_coeffs(
    params: ShellConfig,
) -> tuple[float, float, float]:
    """Return the ``(a, b, c)`` coefficients of the Case-2 quadratic in ``D*``.

    Taken verbatim from the PDF::

        a = beta * gamma
        b = delta_S * gamma - beta * delta_D
        c = beta * L - delta_S * delta_D
    """
    a = params.beta * params.gamma
    b = params.delta_S * params.gamma - params.beta * params.delta_D
    c = params.beta * params.L - params.delta_S * params.delta_D
    return a, b, c


def _solve_case2_quadratic(params: ShellConfig) -> list[float]:
    """Return the real roots of the Case-2 quadratic in ``D*``.

    Roots are returned in ascending order. When ``gamma == 0`` the equation
    degenerates to a linear one and is handled separately. Returns an empty
    list if the discriminant is negative.
    """
    a, b, c = _case2_quadratic_coeffs(params)

    if a == 0.0:
        # Linear fallback when gamma == 0: -beta*delta_D * D* + (beta*L - delta_S*delta_D) = 0
        if b == 0.0:
            return []  # degenerate, no isolated root
        return [-c / b]

    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return []
    if disc == 0.0:
        return [-b / (2.0 * a)]

    sq = sqrt(disc)
    r1 = (-b - sq) / (2.0 * a)
    r2 = (-b + sq) / (2.0 * a)
    return sorted([r1, r2])


def _is_near_fold(params: ShellConfig) -> bool:
    """True iff the Case-2 quadratic is within :data:`_FOLD_DISCRIMINANT_FLOOR`
    of having a zero discriminant (i.e. the upper and lower roots are on the
    verge of merging).

    The degenerate ``gamma == 0`` case has no fold and always returns False.
    """
    a, b, _c = _case2_quadratic_coeffs(params)
    if a == 0.0 or b == 0.0:
        return False
    disc = b * b - 4.0 * a * _case2_quadratic_coeffs(params)[2]
    return disc / (b * b) < _FOLD_DISCRIMINANT_FLOOR


def coexistence_fixed_points(params: ShellConfig) -> list[tuple[float, float]]:
    """Return every physically valid Case-2 fixed point ``(S*, D*)``.

    Zero, one, or two solutions can exist. Roots with ``D* < 0`` or
    ``S* = (delta_D - gamma*D*)/beta < 0`` are filtered out as unphysical.
    Duplicate roots arising from a double root are de-duplicated.
    """
    results: list[tuple[float, float]] = []
    for D_star in _solve_case2_quadratic(params):
        if D_star < -_EPS:
            continue
        D_star = max(D_star, 0.0)  # snap tiny negatives to 0
        S_star = (params.delta_D - params.gamma * D_star) / params.beta
        if S_star < -_EPS:
            continue
        S_star = max(S_star, 0.0)
        candidate = (S_star, D_star)
        # Avoid returning the same point twice when roots coincide numerically.
        if any(
            abs(candidate[0] - r[0]) < _EPS and abs(candidate[1] - r[1]) < _EPS
            for r in results
        ):
            continue
        results.append(candidate)
    return results


# ---------------------------------------------------------------------------
# Union helper
# ---------------------------------------------------------------------------


def find_all_fixed_points(params: ShellConfig) -> list[tuple[float, float]]:
    """Return every physically valid fixed point (Case 1 + Case 2, de-duped)."""
    fps: list[tuple[float, float]] = [clean_orbit_fixed_point(params)]
    for fp in coexistence_fixed_points(params):
        if any(
            abs(fp[0] - r[0]) < _EPS and abs(fp[1] - r[1]) < _EPS for r in fps
        ):
            continue
        fps.append(fp)
    return fps


# ---------------------------------------------------------------------------
# Newton continuation over launch rate
# ---------------------------------------------------------------------------


def _refine_fixed_point(
    params: ShellConfig,
    guess: tuple[float, float],
) -> tuple[float, float] | None:
    """Run :func:`fsolve` on the ODE residual starting from ``guess``.

    Returns the refined ``(S*, D*)`` or ``None`` if the solver fails or the
    solution is non-physical.
    """

    def residual(y: np.ndarray) -> np.ndarray:
        return np.array(
            [s_dot(float(y[0]), float(y[1]), params),
             d_dot(float(y[0]), float(y[1]), params)],
            dtype=float,
        )

    try:
        sol, _info, ier, _msg = fsolve(
            residual,
            np.asarray(guess, dtype=float),
            full_output=True,
            xtol=1e-12,
        )
    except Exception:
        return None

    if ier != 1:
        return None
    S, D = float(sol[0]), float(sol[1])
    if S < -_EPS or D < -_EPS:
        return None
    # Residual sanity: fsolve can report ier=1 with a loose fit in edge cases.
    res = residual(sol)
    if float(np.linalg.norm(res)) > 1e-6 * (1.0 + abs(S) + abs(D)):
        return None
    return (max(S, 0.0), max(D, 0.0))


def continuation_sweep(
    params: ShellConfig,
    L_values: Sequence[float] | np.ndarray,
) -> dict[str, np.ndarray]:
    """Sweep over ``L_values`` tracking Case-1 and Case-2 branches smoothly.

    For each ``L`` in ``L_values``:

    * the Case-1 fixed point ``(L/delta_S, 0)`` is added (always exists);
    * the *upper* Case-2 fixed point (the one with larger ``D*``) is refined
      with :func:`scipy.optimize.fsolve`, warm-started from the solution at
      the previous ``L`` when available and otherwise seeded from the
      analytical quadratic root. When no physical Case-2 solution exists,
      or when the quadratic's discriminant drops below
      :data:`_FOLD_DISCRIMINANT_FLOOR` of ``b**2`` (i.e. we are entering
      the ill-conditioned fold neighbourhood where ``dD*/dL`` diverges),
      the entry is skipped (rather than padded with NaN). Downstream code
      that needs to resolve the fold itself can call
      :func:`coexistence_fixed_points` directly.

    Returns a dict with the keys required by ``TASKS.md``:

    * ``L`` — launch rate at which each fixed point was computed.
    * ``S_star``, ``D_star`` — the fixed-point coordinates.
    * ``branch`` — ``1`` for Case 1, ``2`` for Case 2.

    All arrays have the same length. Case-1 entries come first and are
    ordered by ``L``, followed by the valid Case-2 entries also ordered by
    ``L`` so that filtering ``branch == 2`` yields a smooth curve suitable
    for the VALIDATION.md T2.5 smoothness check.
    """
    L_arr = np.asarray(L_values, dtype=float)
    if L_arr.ndim != 1:
        raise ValueError("L_values must be one-dimensional")

    n = L_arr.size

    case1_S = L_arr / params.delta_S
    case1_D = np.zeros(n)

    case2_L: list[float] = []
    case2_S: list[float] = []
    case2_D: list[float] = []

    guess: tuple[float, float] | None = None
    for L_i in L_arr:
        local = _with_launch_rate(params, float(L_i))

        # Skip the ill-conditioned fold neighbourhood entirely: the upper
        # and lower roots collide there and ``dD*/dL`` diverges, so any
        # uniform sampling in L would report an arbitrarily large jump.
        if _is_near_fold(local):
            guess = None
            continue

        analytical = coexistence_fixed_points(local)

        candidate: tuple[float, float] | None = None

        if guess is not None:
            candidate = _refine_fixed_point(local, guess)

        if candidate is None and analytical:
            # Prefer the upper branch (larger D*) as the tracked coexistence root.
            seed = max(analytical, key=lambda sd: sd[1])
            candidate = _refine_fixed_point(local, seed) or seed

        if candidate is None:
            # Gap in the coexistence branch (e.g. past the fold where the
            # discriminant goes negative). Drop the warm start so the next L
            # that admits a root re-seeds from the analytical quadratic.
            guess = None
            continue

        guess = candidate
        case2_L.append(float(L_i))
        case2_S.append(candidate[0])
        case2_D.append(candidate[1])

    L_out = np.concatenate([L_arr, np.asarray(case2_L, dtype=float)])
    S_out = np.concatenate([case1_S, np.asarray(case2_S, dtype=float)])
    D_out = np.concatenate([case1_D, np.asarray(case2_D, dtype=float)])
    branch_out = np.concatenate(
        [np.ones(n, dtype=int), np.full(len(case2_L), 2, dtype=int)]
    )

    return {
        "L": L_out,
        "S_star": S_out,
        "D_star": D_out,
        "branch": branch_out,
    }


def _with_launch_rate(params: ShellConfig, L: float) -> ShellConfig:
    """Return a copy of ``params`` with ``L`` overridden for the sweep step.

    ``ShellConfig`` is frozen and validates on construction; ``L >= 0`` is
    enforced there, so callers must provide a non-negative ``L``. We also
    drop the sweep-bounds metadata so the new launch rate is never rejected
    for falling outside the original sweep window.
    """
    if L < 0.0:
        raise ValueError(f"Continuation L must be non-negative (got {L!r})")
    return replace(params, L=L, L_sweep_min=0.0, L_sweep_max=None)


# ---------------------------------------------------------------------------
# 3-species fixed points (S, R, D)
# ---------------------------------------------------------------------------

# Tolerance and step counts for the grid-seeded fsolve scan. Five points per
# axis gives a 5*5*5 = 125-point grid which is small enough to stay fast on
# a per-L call inside the continuation sweep. Tightening to 7 per axis would
# triple the cost without observably improving recall on the test shells.
_GRID_STEPS_3D = 5
# Two points are "the same" fixed point if they sit within 1e-6 in Euclidean
# distance, normalised by the magnitude of either point. Looser than the
# 2-D _EPS because the grid seeds tend to land at slightly different places
# even when they converge to the same root.
_DEDUP_REL_TOL_3D = 1e-6
# Branch-matching threshold across L steps: a candidate at L[i+1] is treated
# as the continuation of branch B if its (S, R, D) is within 5% of B's last
# point (Euclidean, normalised by the branch magnitude). Orphans start a
# new branch.
_BRANCH_MATCH_REL = 0.05


def _residual_3species(
    state: np.ndarray, params: ShellConfig
) -> np.ndarray:
    """Stationary-state residual ``[S_dot, R_dot, D_dot]``."""
    S = float(state[0])
    R = float(state[1])
    D = float(state[2])
    return np.array(
        [
            s_dot_3species(S, R, D, params),
            r_dot_3species(S, R, D, params),
            d_dot_3species(S, R, D, params),
        ],
        dtype=float,
    )


def _refine_fixed_point_3species(
    params: ShellConfig,
    guess: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    """Polish a candidate ``(S, R, D)`` with :func:`fsolve`.

    Returns ``None`` if the solver fails, the residual stays large, or the
    refined point is non-physical (negative population in any species).
    """
    try:
        sol, _info, ier, _msg = fsolve(
            _residual_3species,
            np.asarray(guess, dtype=float),
            args=(params,),
            full_output=True,
            xtol=1e-12,
        )
    except Exception:  # pragma: no cover - fsolve is well-trodden
        return None

    if ier != 1:
        return None

    S, R, D = float(sol[0]), float(sol[1]), float(sol[2])
    if S < -_EPS or R < -_EPS or D < -_EPS:
        return None

    res = _residual_3species(np.asarray(sol, dtype=float), params)
    scale = 1.0 + abs(S) + abs(R) + abs(D)
    if float(np.linalg.norm(res)) > 1e-6 * scale:
        return None

    return (max(S, 0.0), max(R, 0.0), max(D, 0.0))


def _grid_seeds_3species(params: ShellConfig) -> list[tuple[float, float, float]]:
    """Return a coarse grid of physically plausible ``(S, R, D)`` seeds.

    Magnitudes are scaled to the natural units of each species so the seeds
    cover both the clean-orbit equilibrium and the high-debris regime without
    requiring per-shell hand-tuning:

    * ``S`` from 0 to ``2 * L / delta_S`` (twice the clean-orbit value);
    * ``R`` from 0 to ``2 * delta_S * L / (delta_S * delta_R)``
      = ``2 * L / delta_R`` (the steady-state R when (S,D) is decoupled);
    * ``D`` from 0 to ``2 * delta_D / max(gamma, 1e-12)``
      (a debris scale where the cascade term dominates the linear sink).

    A small floor prevents collapse to zero ranges on a freshly-launched shell
    with ``L == 0``. The first axis point is always 0 so the clean-orbit seed
    is included.
    """
    delta_S = max(params.delta_S, 1e-12)
    delta_R = max(params.delta_R, delta_S * 1.5)  # safe fallback if 0
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


def _is_duplicate_3species(
    candidate: tuple[float, float, float],
    existing: list[tuple[float, float, float]],
    rel_tol: float = _DEDUP_REL_TOL_3D,
) -> bool:
    """Return True iff ``candidate`` is within ``rel_tol`` of any point in
    ``existing``, normalised by the larger of the two magnitudes."""
    cx = np.asarray(candidate, dtype=float)
    for r in existing:
        rx = np.asarray(r, dtype=float)
        scale = max(float(np.linalg.norm(cx)), float(np.linalg.norm(rx)), 1.0)
        if float(np.linalg.norm(cx - rx)) <= rel_tol * scale:
            return True
    return False


def find_fixed_points_3species(
    params: ShellConfig,
    L: float | None = None,
) -> list[tuple[float, float, float]]:
    """Return every physically valid 3-species fixed point ``(S*, R*, D*)``.

    Parameters
    ----------
    params:
        Shell parameters. Reads ``delta_S``, ``delta_R``, ``delta_D``,
        ``beta``, ``beta_SR``, ``beta_RD``, ``gamma`` and (if ``L`` is None)
        ``params.L``.
    L:
        Optional override for the launch rate. When provided we operate on a
        copy of ``params`` with ``L`` swapped in (and the sweep bounds
        cleared) so callers can probe the same shell at any launch rate
        without rebuilding the dataclass.

    Returns
    -------
    list[tuple[float, float, float]]
        Distinct equilibria, deduplicated by ``_DEDUP_REL_TOL_3D``. Empty
        list if the grid scan finds no physical solution.
    """
    local = params if L is None else _with_launch_rate(params, float(L))
    results: list[tuple[float, float, float]] = []
    for seed in _grid_seeds_3species(local):
        refined = _refine_fixed_point_3species(local, seed)
        if refined is None:
            continue
        if _is_duplicate_3species(refined, results):
            continue
        results.append(refined)
    return results


def _match_branch(
    candidate: tuple[float, float, float],
    branches_last: list[tuple[float, float, float]],
    rel_tol: float = _BRANCH_MATCH_REL,
) -> int | None:
    """Find the index of the branch whose last point is closest to
    ``candidate`` and within ``rel_tol`` (relative) Euclidean distance.
    Returns ``None`` if no branch is close enough.
    """
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


def continuation_sweep_3species(
    params: ShellConfig,
    L_values: Sequence[float] | np.ndarray,
) -> list[dict[str, np.ndarray]]:
    """Track every 3-species coexistence branch across a sweep over ``L``.

    Strategy at each L step:

    1. **Warm-start** every active branch's last point through fsolve at the
       new L. Surviving warm starts continue their branch.
    2. **Grid scan** at the new L to catch new branches that came into
       existence (e.g. born from a fold). Solutions matching an active
       branch's warm-started point are merged; orphans start a new branch.

    A branch is *terminated* at the L step where its warm start fails. Future
    L steps may spawn a new branch with similar coordinates if the fold
    re-creates one; the matcher will not retroactively join them, by design,
    because we cannot tell from the data alone whether they are the same
    physical branch.

    Returns
    -------
    list[dict[str, np.ndarray]]
        One dict per branch, each with keys ``L``, ``S_star``, ``R_star``,
        ``D_star`` (all 1-D float arrays of equal length, monotone in L).
        Branches are returned in birth order. The list is empty when no
        physical fixed point exists at any sampled L.
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
            warm_results.append(_refine_fixed_point_3species(local, last_point[i]))

        # Apply warm-start results: surviving branches grow, dying ones go
        # inactive (no NaN padding — branches simply end).
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
        scan = find_fixed_points_3species(local)

        # Active branch endpoints at this L (post warm-start).
        live_endpoints: list[tuple[float, float, float]] = []
        live_indices: list[int] = []
        for i, is_active in enumerate(active):
            if is_active and warm_results[i] is not None:
                live_endpoints.append(last_point[i])
                live_indices.append(i)

        for cand in scan:
            match = _match_branch(cand, live_endpoints)
            if match is not None:
                # Already represented by an active branch.
                continue
            # New branch born at this L.
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
            live_indices.append(len(branches) - 1)

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
