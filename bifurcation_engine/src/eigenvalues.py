"""Jacobian and eigenvalue tracking for the Kessler ODE (Task 4).

The Jacobian at a fixed point ``(S*, D*)`` is taken verbatim from the PDF /
CLAUDE.md::

    J = [[-delta_S - beta * D*,   -beta * S*                   ],
         [ beta * D*,              beta * S* + 2 * gamma * D* - delta_D]]

Eigenvalues are computed with :func:`numpy.linalg.eigvals`.

``eigenvalue_pair`` returns a ``(alpha, omega)`` tuple:

* When the eigenvalues are a complex conjugate pair, ``alpha`` is their shared
  real part and ``omega`` is the absolute value of their imaginary part.
* When the eigenvalues are real (no rotation — and therefore no Hopf
  possible), ``alpha`` is the larger of the two real parts (the component
  that governs stability) and ``omega`` is zero.

Both modules downstream (``hopf_detector``, ``early_warning``) treat
``omega > 0`` as the signal that the fixed point is a spiral and therefore a
candidate site for a Hopf bifurcation.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .shell_config import ShellConfig

__all__ = [
    "jacobian",
    "eigenvalue_pair",
    "track_eigenvalues",
    "jacobian_3species",
    "eigenvalue_analysis_3species",
    "track_eigenvalues_3species",
]


# A generous floor for treating a numpy-computed imaginary part as
# numerically zero. We scale it by the magnitude of the eigenvalues so that
# large-trace Jacobians (like the ones produced at high D*) do not get their
# complex pairs misclassified as real.
_OMEGA_REL_TOL = 1e-10
_OMEGA_ABS_TOL = 1e-12


def jacobian(S_star: float, D_star: float, params: ShellConfig) -> np.ndarray:
    """Return the 2x2 Jacobian of the ODE at the fixed point ``(S*, D*)``.

    The Jacobian is derived analytically from the ODE in
    :mod:`bifurcation_engine.src.model`; see module docstring for the exact
    form. Only ``params.delta_S``, ``params.delta_D``, ``params.beta`` and
    ``params.gamma`` are read; ``params.L`` is not used (it enters the
    dynamics only through the fixed-point location, not through the
    Jacobian).
    """
    j00 = -params.delta_S - params.beta * D_star
    j01 = -params.beta * S_star
    j10 = params.beta * D_star
    j11 = params.beta * S_star + 2.0 * params.gamma * D_star - params.delta_D
    return np.array([[j00, j01], [j10, j11]], dtype=float)


def eigenvalue_pair(
    S_star: float,
    D_star: float,
    params: ShellConfig,
) -> tuple[float, float]:
    """Return ``(alpha, omega)`` for the eigenvalues of the Jacobian at
    ``(S*, D*)``.

    See module docstring for the convention used when the eigenvalues are
    real.
    """
    J = jacobian(S_star, D_star, params)
    eigs = np.linalg.eigvals(J)

    # For a real 2x2 matrix eigvals always returns a complex-conjugate pair
    # (possibly with zero imaginary parts when both roots are real).
    im_magnitude = float(max(abs(eigs[0].imag), abs(eigs[1].imag)))
    re_magnitude = float(max(abs(eigs[0].real), abs(eigs[1].real)))
    threshold = max(_OMEGA_ABS_TOL, _OMEGA_REL_TOL * re_magnitude)

    if im_magnitude > threshold:
        # Complex conjugate pair: both eigenvalues share a real part.
        alpha = 0.5 * (float(eigs[0].real) + float(eigs[1].real))
        omega = im_magnitude
        return alpha, omega

    # Real eigenvalues: stability is governed by the larger real part, and
    # there is no rotation so omega is exactly zero.
    alpha = float(max(eigs[0].real, eigs[1].real))
    return alpha, 0.0


def track_eigenvalues(
    continuation_result: Mapping[str, np.ndarray],
    params: ShellConfig,
) -> dict[str, np.ndarray]:
    """Evaluate ``(alpha, omega)`` at every fixed point in a sweep.

    Parameters
    ----------
    continuation_result:
        A dict with the shape produced by
        :func:`bifurcation_engine.src.fixed_points.continuation_sweep`;
        specifically, keys ``L``, ``S_star``, ``D_star`` (all 1-D arrays of
        equal length, optionally also ``branch``).
    params:
        Shell parameters. Only the non-``L`` fields are read — the Jacobian
        does not depend on the launch rate directly.

    Returns
    -------
    dict
        A dict with keys ``L``, ``alpha``, ``omega``, ``is_complex`` (bool
        array flagging entries where ``omega > 0``). When the input contains
        a ``branch`` column, it is copied through unchanged so callers can
        filter by branch before feeding the result into the Hopf detector.
    """
    L = np.asarray(continuation_result["L"], dtype=float)
    S = np.asarray(continuation_result["S_star"], dtype=float)
    D = np.asarray(continuation_result["D_star"], dtype=float)
    if not (L.shape == S.shape == D.shape):
        raise ValueError(
            "continuation_result arrays must all have the same shape"
        )

    n = L.size
    alpha = np.zeros(n, dtype=float)
    omega = np.zeros(n, dtype=float)

    for i in range(n):
        alpha[i], omega[i] = eigenvalue_pair(float(S[i]), float(D[i]), params)

    is_complex = omega > 0.0

    out: dict[str, np.ndarray] = {
        "L": L,
        "alpha": alpha,
        "omega": omega,
        "is_complex": is_complex,
    }
    if "branch" in continuation_result:
        out["branch"] = np.asarray(continuation_result["branch"])
    return out


# ---------------------------------------------------------------------------
# 3-species (S, R, D) extension
# ---------------------------------------------------------------------------


def jacobian_3species(
    S_star: float,
    R_star: float,
    D_star: float,
    params: ShellConfig,
) -> np.ndarray:
    """Return the 3x3 Jacobian of the 3-species ODE at ``(S*, R*, D*)``.

    Derived analytically from :func:`s_dot_3species`,
    :func:`r_dot_3species`, :func:`d_dot_3species`. With::

        S_dot = L - delta_S*S - beta*S*D - beta_SR*S*R
        R_dot = delta_S*S - delta_R*R - beta_RD*R*D
        D_dot = beta*S*D + beta_SR*S*R + beta_RD*R*D + gamma*D**2 - delta_D*D

    the Jacobian rows are::

        d(S_dot)/d(S, R, D) = [-delta_S - beta*D - beta_SR*R,
                                -beta_SR * S,
                                -beta * S]
        d(R_dot)/d(S, R, D) = [ delta_S,
                                -delta_R - beta_RD * D,
                                -beta_RD * R]
        d(D_dot)/d(S, R, D) = [ beta*D + beta_SR*R,
                                 beta_SR*S + beta_RD*D,
                                 beta*S + beta_RD*R + 2*gamma*D - delta_D]

    Only the non-``L`` parameter fields are read; ``L`` enters only through
    the location of the fixed point (already baked into the arguments).
    """
    delta_S = params.delta_S
    delta_R = params.delta_R
    delta_D = params.delta_D
    beta = params.beta
    beta_SR = params.beta_SR
    beta_RD = params.beta_RD
    gamma = params.gamma

    j00 = -delta_S - beta * D_star - beta_SR * R_star
    j01 = -beta_SR * S_star
    j02 = -beta * S_star

    j10 = delta_S
    j11 = -delta_R - beta_RD * D_star
    j12 = -beta_RD * R_star

    j20 = beta * D_star + beta_SR * R_star
    j21 = beta_SR * S_star + beta_RD * D_star
    j22 = beta * S_star + beta_RD * R_star + 2.0 * gamma * D_star - delta_D

    return np.array(
        [
            [j00, j01, j02],
            [j10, j11, j12],
            [j20, j21, j22],
        ],
        dtype=float,
    )


def eigenvalue_analysis_3species(
    S_star: float,
    R_star: float,
    D_star: float,
    params: ShellConfig,
) -> dict[str, object]:
    """Classify the three eigenvalues of the 3-species Jacobian at one point.

    Returns a dict with:

    * ``eigs`` (ndarray, shape (3,), complex): the three eigenvalues.
    * ``real_parts`` (ndarray, shape (3,), float): real parts sorted ascending.
    * ``has_complex_pair`` (bool): True iff at least one pair has a non-zero
      imaginary part above the relative tolerance.
    * ``alpha_complex`` (float): shared real part of the dominant complex pair
      (the one with the largest real part); ``nan`` if no complex pair.
    * ``omega_complex`` (float): absolute imaginary part of the same pair;
      ``nan`` if no complex pair.
    * ``leading_alpha`` (float): the largest real part among all three
      eigenvalues — governs linear stability whether or not a complex pair
      exists. A Hopf candidate is signalled when ``has_complex_pair`` is True
      *and* the dominant ``alpha_complex`` crosses zero across an L sweep.
    """
    J = jacobian_3species(S_star, R_star, D_star, params)
    eigs = np.linalg.eigvals(J)

    re = np.real(eigs)
    im = np.imag(eigs)

    re_scale = float(np.max(np.abs(re))) if re.size else 0.0
    threshold = max(_OMEGA_ABS_TOL, _OMEGA_REL_TOL * re_scale)
    complex_mask = np.abs(im) > threshold

    leading_alpha = float(np.max(re))

    if not complex_mask.any():
        return {
            "eigs": eigs,
            "real_parts": np.sort(re),
            "has_complex_pair": False,
            "alpha_complex": float("nan"),
            "omega_complex": float("nan"),
            "leading_alpha": leading_alpha,
        }

    # Pick the dominant complex pair: the conjugate pair whose shared real
    # part is largest. NumPy returns conjugate pairs as adjacent entries
    # for real matrices, but we don't rely on order — we group entries with
    # near-equal real parts.
    complex_indices = np.where(complex_mask)[0]
    best_alpha = -np.inf
    best_omega = float("nan")
    for idx in complex_indices:
        alpha_i = float(re[idx])
        omega_i = float(abs(im[idx]))
        if alpha_i > best_alpha:
            best_alpha = alpha_i
            best_omega = omega_i

    return {
        "eigs": eigs,
        "real_parts": np.sort(re),
        "has_complex_pair": True,
        "alpha_complex": float(best_alpha),
        "omega_complex": float(best_omega),
        "leading_alpha": leading_alpha,
    }


def track_eigenvalues_3species(
    branch: Mapping[str, np.ndarray],
    params: ShellConfig,
) -> dict[str, np.ndarray]:
    """Evaluate the 3-species eigenvalue analysis along one continuation branch.

    Parameters
    ----------
    branch:
        A dict shaped like one element of
        :func:`continuation_sweep_3species`'s output: ``L``, ``S_star``,
        ``R_star``, ``D_star`` arrays of equal length.
    params:
        Shell parameters; only the non-``L`` fields are read.

    Returns
    -------
    dict
        Keys: ``L`` (copy of input), ``alpha_complex`` (shared real part of
        the dominant complex pair, or ``nan`` where there is no complex
        pair), ``omega_complex`` (absolute imag part, or ``nan``),
        ``leading_alpha`` (largest real part, always finite),
        ``has_complex_pair`` (bool array). The dict is in the shape
        :func:`bifurcation_engine.src.hopf_detector.detect_hopf` expects via
        the ``alpha`` / ``omega`` keys, mapped through aliases below for
        convenience: ``alpha`` aliases ``alpha_complex`` and ``omega``
        aliases ``omega_complex`` so the existing detector can be reused
        directly on a per-branch basis.
    """
    L = np.asarray(branch["L"], dtype=float)
    S = np.asarray(branch["S_star"], dtype=float)
    R = np.asarray(branch["R_star"], dtype=float)
    D = np.asarray(branch["D_star"], dtype=float)
    if not (L.shape == S.shape == R.shape == D.shape):
        raise ValueError("branch arrays must all have the same shape")

    n = L.size
    alpha_complex = np.full(n, np.nan, dtype=float)
    omega_complex = np.full(n, np.nan, dtype=float)
    leading_alpha = np.zeros(n, dtype=float)
    has_complex = np.zeros(n, dtype=bool)

    for i in range(n):
        analysis = eigenvalue_analysis_3species(
            float(S[i]), float(R[i]), float(D[i]), params
        )
        leading_alpha[i] = float(analysis["leading_alpha"])  # type: ignore[arg-type]
        if bool(analysis["has_complex_pair"]):
            alpha_complex[i] = float(analysis["alpha_complex"])  # type: ignore[arg-type]
            omega_complex[i] = float(analysis["omega_complex"])  # type: ignore[arg-type]
            has_complex[i] = True

    return {
        "L": L,
        "alpha_complex": alpha_complex,
        "omega_complex": omega_complex,
        "leading_alpha": leading_alpha,
        "has_complex_pair": has_complex,
        # Aliases so detect_hopf can consume this dict directly.
        "alpha": alpha_complex,
        "omega": omega_complex,
        "is_complex": has_complex,
    }
