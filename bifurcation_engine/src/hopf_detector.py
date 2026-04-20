"""Hopf and saddle-node fold bifurcation detection (Task 5 + fold add-on).

This module hosts two detectors that act on the Case-2 coexistence branch of
the Kessler model:

``detect_hopf``
    Given arrays of ``(L, alpha, omega)`` produced by
    :func:`bifurcation_engine.src.eigenvalues.track_eigenvalues`, decide
    whether the three Hopf conditions are satisfied at some critical launch
    rate ``L_c``.

``detect_fold``
    Locate the saddle-node fold where the Case-2 quadratic discriminant
    ``b^2 - 4ac`` crosses zero. Beyond this launch rate the two coexistence
    fixed points annihilate each other and the system loses its stable
    equilibrium — this is the real Kessler tipping point in the 2D model,
    since our pipeline has confirmed that the lower branch does not cross
    alpha = 0 while still complex (see ``reports/task4_5_summary.md``).

The three Hopf conditions (PDF, section "What is a Hopf Bifurcation?") are:

1. ``alpha(L_c) = 0``                 — real part vanishes,
2. ``omega(L_c) != 0``                — rotation is present,
3. ``d alpha / dL (L_c) != 0``        — the crossing is genuine, not grazing.

A Hopf bifurcation is NOT guaranteed to exist for a given shell; the detector
must report the outcome honestly. Five outcomes are distinguished:

* ``no_complex_eigenvalues`` — ``omega == 0`` everywhere along the supplied
  sweep. The fixed point is (locally) a node, and only saddle-node /
  pitchfork bifurcations are possible; no limit cycle is born.
* ``complex_no_crossing`` — the eigenvalues are complex over some region but
  ``alpha`` stays strictly negative there (stable spiral throughout, system
  safe).
* ``unstable_throughout`` — ``alpha`` is positive wherever the eigenvalues
  are complex (unstable spiral for every sampled L).
* ``hopf_detected`` — a sign change in ``alpha`` is observed in the
  complex-eigenvalue region with a non-vanishing derivative. Supercritical
  vs subcritical classification requires a nonlinear trajectory integration
  (Task 6) and is therefore left blank by this detector; callers should
  refine the outcome to ``hopf_supercritical`` / ``hopf_subcritical`` once
  that data is available.
* ``grazing`` — ``alpha`` touches zero but ``d alpha / dL`` is within the
  grazing tolerance. Reported as ``found=False`` with a warning-style
  description, since condition (3) of the Hopf theorem is not met.

None of these outcomes are treated as errors. A non-Hopf result is a
legitimate scientific conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .shell_config import ShellConfig

__all__ = [
    "HopfResult",
    "HopfOutcome",
    "detect_hopf",
    "FoldResult",
    "detect_fold",
]


HopfOutcome = Literal[
    "no_complex_eigenvalues",
    "complex_no_crossing",
    "unstable_throughout",
    "hopf_detected",
    "hopf_supercritical",
    "hopf_subcritical",
    "grazing",
]


@dataclass(frozen=True)
class HopfResult:
    """Outcome of a Hopf detection pass.

    Attributes
    ----------
    found:
        ``True`` if all three Hopf conditions are satisfied (up to tolerance),
        ``False`` otherwise.
    L_c:
        Interpolated critical launch rate when ``found`` is True, else None.
    outcome:
        One of :data:`HopfOutcome`. The three non-Hopf values are scientifically
        valid results, not errors.
    description:
        Human-readable explanation suitable for logs and dashboards.
    alpha_at_Lc, omega_at_Lc, dalpha_dL_at_Lc:
        Linearly interpolated values of ``alpha``, ``omega`` and the finite-
        difference derivative ``d alpha / dL`` at ``L_c``. ``alpha_at_Lc``
        should be within :attr:`alpha_zero_tol` of zero.
    alpha_zero_tol:
        The absolute tolerance used when testing ``|alpha| < eps`` at the
        interpolated crossing. Exposed so callers can reproduce the decision.
    """

    found: bool
    outcome: HopfOutcome
    description: str
    L_c: float | None = None
    alpha_at_Lc: float | None = None
    omega_at_Lc: float | None = None
    dalpha_dL_at_Lc: float | None = None
    alpha_zero_tol: float = 1e-12


# --- tolerances -------------------------------------------------------------

# Below this threshold, ``omega`` is treated as numerical zero (i.e. the
# eigenvalue pair is real for detection purposes).
_OMEGA_COMPLEX_TOL = 1e-12

# A crossing whose finite-difference ``d alpha / dL`` is below this fraction
# of the global ``max|alpha|`` is classified as a grazing contact rather than
# a genuine Hopf event.
_GRAZING_SLOPE_FRACTION = 1e-6


def _interpolate_zero_crossing(
    L: np.ndarray,
    alpha: np.ndarray,
    i: int,
) -> float:
    """Return the linearly-interpolated ``L`` where ``alpha`` crosses zero
    between ``L[i]`` and ``L[i + 1]``.
    """
    a0, a1 = float(alpha[i]), float(alpha[i + 1])
    L0, L1 = float(L[i]), float(L[i + 1])
    if a1 == a0:
        return 0.5 * (L0 + L1)
    # Linear interpolation: alpha = a0 + (a1 - a0) * (L - L0) / (L1 - L0) = 0
    t = -a0 / (a1 - a0)
    return L0 + t * (L1 - L0)


def _linear_interp(
    x0: float, x1: float, y0: float, y1: float, x: float
) -> float:
    if x1 == x0:
        return 0.5 * (y0 + y1)
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def detect_hopf(
    L_array: np.ndarray,
    alpha_array: np.ndarray,
    omega_array: np.ndarray,
) -> HopfResult:
    """Classify the Hopf outcome for a single continuation branch.

    Parameters
    ----------
    L_array, alpha_array, omega_array:
        One-dimensional arrays, all of identical shape, such that
        ``(alpha_array[i], omega_array[i])`` are the real and absolute-
        imaginary parts of the Jacobian eigenvalues at the fixed point
        corresponding to launch rate ``L_array[i]``. ``L_array`` must be
        monotonically non-decreasing.

    Returns
    -------
    HopfResult
        A fully populated result. See :class:`HopfResult` and the module
        docstring for the definitions of the five possible outcomes.

    Notes
    -----
    Classification of a detected Hopf as supercritical or subcritical
    requires integrating the full nonlinear ODE (Task 6); this function
    stops at ``outcome='hopf_detected'``.
    """
    L = np.asarray(L_array, dtype=float).ravel()
    alpha = np.asarray(alpha_array, dtype=float).ravel()
    omega = np.asarray(omega_array, dtype=float).ravel()

    if not (L.shape == alpha.shape == omega.shape):
        raise ValueError("L, alpha and omega arrays must have the same shape")
    if L.size < 2:
        raise ValueError("Need at least two sweep points to detect a crossing")
    if np.any(np.diff(L) < 0.0):
        raise ValueError("L_array must be monotonically non-decreasing")

    complex_mask = omega > _OMEGA_COMPLEX_TOL

    # --- Outcome 1: no complex eigenvalues anywhere -----------------------
    if not np.any(complex_mask):
        return HopfResult(
            found=False,
            outcome="no_complex_eigenvalues",
            description=(
                "omega is (numerically) zero throughout the sweep. "
                "The fixed point is a real node at every L; no Hopf "
                "bifurcation is possible on this branch."
            ),
        )

    # --- Search for a sign change in alpha within the complex-eigenvalue region --
    # A valid Hopf crossing requires BOTH sides of the step to have omega > 0.
    crossings: list[int] = []
    for i in range(L.size - 1):
        if not (complex_mask[i] and complex_mask[i + 1]):
            continue
        a0, a1 = alpha[i], alpha[i + 1]
        if a0 == 0.0 and a1 == 0.0:
            continue  # identically zero is not a crossing
        if a0 * a1 < 0.0 or (a0 == 0.0) ^ (a1 == 0.0):
            crossings.append(i)

    # --- Outcome 2: complex eigenvalues but no zero crossing of alpha -----
    if not crossings:
        alpha_in_complex = alpha[complex_mask]
        if np.all(alpha_in_complex < 0.0):
            return HopfResult(
                found=False,
                outcome="complex_no_crossing",
                description=(
                    "Eigenvalues are complex over part of the sweep but "
                    "alpha stays strictly negative there: the fixed point "
                    "is a stable spiral throughout. No Hopf bifurcation."
                ),
            )
        if np.all(alpha_in_complex > 0.0):
            return HopfResult(
                found=False,
                outcome="unstable_throughout",
                description=(
                    "Eigenvalues are complex over part of the sweep but "
                    "alpha is positive everywhere they exist: the fixed "
                    "point is an unstable spiral for all sampled L."
                ),
            )
        # Mixed signs possible only if a crossing straddled a gap in the
        # complex region (omega went to zero in between). Treat as no Hopf.
        return HopfResult(
            found=False,
            outcome="complex_no_crossing",
            description=(
                "alpha changes sign only across a gap where the eigenvalues "
                "became real; the Hopf condition omega != 0 is not satisfied "
                "at the crossing."
            ),
        )

    # --- Outcome 3: at least one valid Hopf crossing ----------------------
    # Pick the first crossing. Refine L_c and read alpha/omega there.
    i = crossings[0]
    L_c = _interpolate_zero_crossing(L, alpha, i)
    omega_at_Lc = _linear_interp(
        float(L[i]), float(L[i + 1]), float(omega[i]), float(omega[i + 1]), L_c
    )
    alpha_at_Lc = _linear_interp(
        float(L[i]), float(L[i + 1]), float(alpha[i]), float(alpha[i + 1]), L_c
    )

    # Finite-difference derivative across the crossing interval.
    dL = float(L[i + 1] - L[i])
    dalpha_dL = (float(alpha[i + 1]) - float(alpha[i])) / dL if dL > 0 else 0.0

    # Grazing check: genuine sign change needs |d alpha / dL| non-trivial.
    alpha_scale = float(max(np.max(np.abs(alpha)), 1.0))
    L_scale = float(max(L[-1] - L[0], 1.0))
    grazing_threshold = _GRAZING_SLOPE_FRACTION * alpha_scale / L_scale
    if abs(dalpha_dL) < grazing_threshold:
        return HopfResult(
            found=False,
            outcome="grazing",
            description=(
                f"alpha touches zero at L ~= {L_c:.4g} but d alpha / dL is "
                f"below the grazing tolerance ({abs(dalpha_dL):.3g} < "
                f"{grazing_threshold:.3g}); Hopf condition (3) is not met."
            ),
            L_c=L_c,
            alpha_at_Lc=alpha_at_Lc,
            omega_at_Lc=omega_at_Lc,
            dalpha_dL_at_Lc=dalpha_dL,
        )

    direction = "ascending" if dalpha_dL > 0 else "descending"
    return HopfResult(
        found=True,
        outcome="hopf_detected",
        description=(
            f"Hopf crossing at L_c ~= {L_c:.4g}: alpha changes sign "
            f"({direction}) with omega = {omega_at_Lc:.4g} and "
            f"d alpha / dL = {dalpha_dL:.4g}. Supercritical vs subcritical "
            "classification requires a nonlinear trajectory integration "
            "(Task 6)."
        ),
        L_c=L_c,
        alpha_at_Lc=alpha_at_Lc,
        omega_at_Lc=omega_at_Lc,
        dalpha_dL_at_Lc=dalpha_dL,
    )


# ===========================================================================
# Saddle-node fold detection
# ===========================================================================


@dataclass(frozen=True)
class FoldResult:
    """Outcome of a saddle-node fold detection pass.

    The Case-2 coexistence quadratic is

        a * D^2 + b * D + c(L) = 0,
        a    = beta * gamma,
        b    = delta_S * gamma - beta * delta_D,
        c(L) = beta * L - delta_S * delta_D.

    Its discriminant ``disc(L) = b^2 - 4 * a * c(L)`` is linear in ``L`` and
    strictly decreasing when ``beta, gamma > 0``. When ``disc`` crosses zero
    the two coexistence fixed points merge into a single degenerate point
    and then vanish — the saddle-node fold. In the 2D Kessler model this
    fold is the actual Kessler tipping point (see report in ``reports/``).

    Attributes
    ----------
    found:
        ``True`` when a physical fold is located *inside* the supplied sweep
        range (positive ``S_fold`` and ``D_fold``, crossing in range).
    L_fold:
        Sweep-interpolated launch rate at the fold, ``None`` if ``found`` is
        False and no sensible prediction is available.
    S_star_at_fold, D_star_at_fold:
        Fixed-point coordinates at the merged root, computed from
        ``D_fold = -b / (2 a)`` and ``S_fold = (delta_D - gamma * D_fold) / beta``.
        ``None`` when ``found`` is False and the closed form is unphysical.
    description:
        Plain-English summary suitable for reports and dashboards.
    """

    found: bool
    description: str
    L_fold: float | None = None
    S_star_at_fold: float | None = None
    D_star_at_fold: float | None = None


def _fold_closed_form(params: ShellConfig) -> tuple[float, float, float] | None:
    """Return ``(L_fold, S_fold, D_fold)`` from the closed-form solution of
    ``disc(L) = 0`` — or ``None`` when the quadratic is degenerate (gamma=0).
    """
    if params.gamma <= 0.0 or params.beta <= 0.0:
        return None

    # D_fold = -b / (2a)
    a = params.beta * params.gamma
    b = params.delta_S * params.gamma - params.beta * params.delta_D
    D_fold = -b / (2.0 * a)

    # S_fold from the Case-2 identity S* = (delta_D - gamma * D*) / beta.
    S_fold = (params.delta_D - params.gamma * D_fold) / params.beta

    # L_fold from disc(L) = 0: closed form
    # L_fold = (delta_S * gamma + beta * delta_D)**2 / (4 * beta**2 * gamma)
    num = (params.delta_S * params.gamma + params.beta * params.delta_D) ** 2
    den = 4.0 * params.beta ** 2 * params.gamma
    L_fold = num / den

    return L_fold, S_fold, D_fold


def detect_fold(
    params: ShellConfig,
    L_values: np.ndarray,
) -> FoldResult:
    """Detect a saddle-node fold along a continuation sweep in ``L``.

    Parameters
    ----------
    params:
        Shell parameters defining the Case-2 quadratic.
    L_values:
        Monotonically non-decreasing 1-D array of launch rates along which
        the discriminant is evaluated (typically the same grid used for
        :func:`bifurcation_engine.src.fixed_points.continuation_sweep`).

    Returns
    -------
    FoldResult
        ``found=True`` only if the discriminant changes sign strictly inside
        ``[L_values[0], L_values[-1]]`` and the merged root ``(S_fold,
        D_fold)`` is physical (both non-negative). Otherwise ``found=False``
        with a description explaining which condition failed — never
        an error, since a shell with ``gamma = 0`` or with the fold outside
        the requested sweep is a scientifically valid outcome.

    Notes
    -----
    * The sweep-based crossing detection is what the pipeline contract
      requires. The closed-form result (derived from ``disc(L) = 0``) is
      used as a refinement: since ``disc`` is *linear* in ``L`` a single
      linear interpolation between the bracket points is already exact to
      floating-point precision, so the two values agree to machine epsilon.
    * When ``gamma = 0`` the quadratic degenerates to a linear equation and
      no fold exists; ``found`` is False in that case.
    """
    L = np.asarray(L_values, dtype=float).ravel()
    if L.size < 2:
        raise ValueError("Need at least two sweep points to detect a fold")
    if np.any(np.diff(L) < 0.0):
        raise ValueError("L_values must be monotonically non-decreasing")

    closed = _fold_closed_form(params)
    if closed is None:
        return FoldResult(
            found=False,
            description=(
                "gamma = 0 or beta = 0 makes the Case-2 equation degenerate "
                "(no quadratic term); no saddle-node fold exists."
            ),
        )
    L_fold_cf, S_fold, D_fold = closed

    # Discriminant along the supplied sweep.
    a = params.beta * params.gamma
    b = params.delta_S * params.gamma - params.beta * params.delta_D
    c_L = params.beta * L - params.delta_S * params.delta_D
    disc = b * b - 4.0 * a * c_L

    # Physical realisability of the merged root.
    if D_fold < 0.0 or S_fold < 0.0:
        return FoldResult(
            found=False,
            description=(
                f"Closed-form fold predicts D_fold = {D_fold:.4g}, "
                f"S_fold = {S_fold:.4g} at L = {L_fold_cf:.4g}, but the "
                "merged root is not physical (negative coordinate). No "
                "saddle-node fold in the physically admissible region."
            ),
            L_fold=L_fold_cf,
            S_star_at_fold=S_fold,
            D_star_at_fold=D_fold,
        )

    # Sweep-based sign-change search.
    sign_change_idx = -1
    for i in range(L.size - 1):
        if disc[i] >= 0.0 > disc[i + 1]:
            sign_change_idx = i
            break

    if sign_change_idx == -1:
        # Fold is outside the sweep range — report predictively.
        if np.all(disc > 0.0):
            side = f"above the sweep (L_sweep_max = {L[-1]:.4g})"
        elif np.all(disc < 0.0):
            side = f"below the sweep (L_sweep_min = {L[0]:.4g})"
        else:  # pragma: no cover - disc is linear, cannot straddle twice
            side = "outside the sweep"
        return FoldResult(
            found=False,
            description=(
                f"Discriminant does not change sign in the sweep: the fold "
                f"lies {side}. Closed-form prediction: L_fold = "
                f"{L_fold_cf:.4g}, (S_fold, D_fold) = ({S_fold:.4g}, "
                f"{D_fold:.4g})."
            ),
            L_fold=L_fold_cf,
            S_star_at_fold=S_fold,
            D_star_at_fold=D_fold,
        )

    # Linear interpolation of the crossing (exact since disc is linear in L).
    d0 = float(disc[sign_change_idx])
    d1 = float(disc[sign_change_idx + 1])
    L0 = float(L[sign_change_idx])
    L1 = float(L[sign_change_idx + 1])
    if d0 == d1:  # pragma: no cover — only if the sweep is degenerate
        L_fold = 0.5 * (L0 + L1)
    else:
        L_fold = L0 + (L1 - L0) * d0 / (d0 - d1)

    return FoldResult(
        found=True,
        description=(
            f"Saddle-node fold at L_fold ~= {L_fold:.4g}. At this launch rate "
            f"the two Case-2 coexistence fixed points merge at "
            f"(S*, D*) = ({S_fold:.4g}, {D_fold:.4g}) and vanish for L > "
            "L_fold, leaving only the (generally unstable) clean-orbit fixed "
            "point. In the 2D Kessler model this is the real tipping point: "
            "crossing it means there is no coexistence equilibrium left to "
            "stabilise the debris population."
        ),
        L_fold=L_fold,
        S_star_at_fold=S_fold,
        D_star_at_fold=D_fold,
    )
