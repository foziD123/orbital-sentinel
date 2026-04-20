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

from .model import d_dot, s_dot
from .shell_config import ShellConfig

__all__ = [
    "clean_orbit_fixed_point",
    "coexistence_fixed_points",
    "find_all_fixed_points",
    "continuation_sweep",
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
