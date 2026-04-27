"""Jacobian and eigenvalue tracker for the split-decay 3-species model.

The 3x3 Jacobian implemented here was derived from first principles in the
project plan (split-decay Hopf-hunt, section 4) and verified against the
ODE in :mod:`bifurcation_engine.src.model_split`. Every entry was confirmed
by direct partial differentiation; the closed form at a fixed point
``(S*, R*, D*)`` is::

    J[0,0] = -kappa_S - rho_S - beta_SD*D - beta_SR*R   = -delta_S - beta_SD*D - beta_SR*R
    J[0,1] = -beta_SR*S
    J[0,2] = -beta_SD*S

    J[1,0] =  rho_S - beta_SR*R
    J[1,1] = -delta_R - beta_RD*D - beta_SR*S
    J[1,2] = -beta_RD*R

    J[2,0] =  eta_SD*beta_SD*D + eta_SR*beta_SR*R
    J[2,1] =  eta_SR*beta_SR*S + eta_RD*beta_RD*D
    J[2,2] =  eta_SD*beta_SD*S + eta_RD*beta_RD*R + 2*gamma*D - delta_D

The trace simplifies to::

    tr(J_split) = -(delta_S + delta_R + delta_D)
                  + beta_SD * (eta_SD*S - D)
                  + beta_RD * (eta_RD*R - D)
                  - beta_SR * (R + S)
                  + 2 * gamma * D

which is the structural lever the experiment is testing — see the plan
for the comparison to the 3-species trace and the resulting Hopf-window
hypothesis.

The ``track_eigenvalues_split`` helper exposes the same ``alpha`` /
``omega`` / ``is_complex`` aliases that the existing 3-species tracker does,
so the existing :func:`bifurcation_engine.src.hopf_detector.detect_hopf`
can be reused unchanged on a per-branch basis.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .split_decay_config import SplitDecayConfig

__all__ = [
    "jacobian_split",
    "eigenvalue_analysis_split",
    "track_eigenvalues_split",
]


# Same tolerance constants as the existing 3-species analyser, so the two
# pipelines flag complex pairs identically.
_OMEGA_REL_TOL = 1e-10
_OMEGA_ABS_TOL = 1e-12


def jacobian_split(
    S_star: float,
    R_star: float,
    D_star: float,
    params: SplitDecayConfig,
) -> np.ndarray:
    """Return the 3x3 Jacobian of the split-decay ODE at ``(S*, R*, D*)``.

    Each entry follows the closed form derived in the project plan;
    ``test_eigenvalues_split.py`` asserts every entry individually against
    a hand-evaluated reference (V1-style verification).
    """
    kappa_S = params.kappa_S
    rho_S = params.rho_S
    delta_R = params.delta_R
    delta_D = params.delta_D
    beta_SD = params.beta_SD
    beta_SR = params.beta_SR
    beta_RD = params.beta_RD
    eta_SD = params.eta_SD
    eta_SR = params.eta_SR
    eta_RD = params.eta_RD
    gamma = params.gamma

    j00 = -(kappa_S + rho_S) - beta_SD * D_star - beta_SR * R_star
    j01 = -beta_SR * S_star
    j02 = -beta_SD * S_star

    j10 = rho_S - beta_SR * R_star
    j11 = -delta_R - beta_RD * D_star - beta_SR * S_star
    j12 = -beta_RD * R_star

    j20 = eta_SD * beta_SD * D_star + eta_SR * beta_SR * R_star
    j21 = eta_SR * beta_SR * S_star + eta_RD * beta_RD * D_star
    j22 = (
        eta_SD * beta_SD * S_star
        + eta_RD * beta_RD * R_star
        + 2.0 * gamma * D_star
        - delta_D
    )

    return np.array(
        [
            [j00, j01, j02],
            [j10, j11, j12],
            [j20, j21, j22],
        ],
        dtype=float,
    )


def eigenvalue_analysis_split(
    S_star: float,
    R_star: float,
    D_star: float,
    params: SplitDecayConfig,
) -> dict[str, object]:
    """Classify the three eigenvalues of :func:`jacobian_split` at one point.

    Returns a dict with:

    * ``eigs`` (ndarray, shape (3,), complex): the three eigenvalues.
    * ``real_parts`` (ndarray, shape (3,), float): real parts sorted ascending.
    * ``has_complex_pair`` (bool): True iff at least one eigenvalue has a
      non-zero imaginary part above the relative tolerance.
    * ``alpha_complex`` (float): shared real part of the dominant complex
      pair (largest real part among complex eigenvalues); ``nan`` if none.
    * ``omega_complex`` (float): absolute imaginary part of the same pair;
      ``nan`` if none.
    * ``leading_alpha`` (float): the largest real part among all three
      eigenvalues — governs linear stability whether or not a complex pair
      exists.
    * ``trace`` (float): explicit ``tr(J_split)`` for diagnostic logging
      (the sweep records this at the lower-branch terminus to corroborate
      the trace inequality).
    """
    J = jacobian_split(S_star, R_star, D_star, params)
    eigs = np.linalg.eigvals(J)

    re = np.real(eigs)
    im = np.imag(eigs)

    re_scale = float(np.max(np.abs(re))) if re.size else 0.0
    threshold = max(_OMEGA_ABS_TOL, _OMEGA_REL_TOL * re_scale)
    complex_mask = np.abs(im) > threshold

    leading_alpha = float(np.max(re))
    trace = float(np.trace(J))

    if not complex_mask.any():
        return {
            "eigs": eigs,
            "real_parts": np.sort(re),
            "has_complex_pair": False,
            "alpha_complex": float("nan"),
            "omega_complex": float("nan"),
            "leading_alpha": leading_alpha,
            "trace": trace,
        }

    # Pick the dominant complex pair: the conjugate pair whose shared real
    # part is largest. We don't rely on numpy returning conjugate pairs in
    # adjacent slots — we scan all complex entries for the one with the
    # largest real part.
    best_alpha = -np.inf
    best_omega = float("nan")
    for idx in np.where(complex_mask)[0]:
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
        "trace": trace,
    }


def track_eigenvalues_split(
    branch: Mapping[str, np.ndarray],
    params: SplitDecayConfig,
) -> dict[str, np.ndarray]:
    """Evaluate the split-decay eigenvalue analysis along one branch.

    Parameters
    ----------
    branch:
        A dict shaped like one element of
        :func:`continuation_sweep_split`'s output, with keys ``L``,
        ``S_star``, ``R_star``, ``D_star`` (1-D arrays of equal length).
    params:
        Split-decay shell parameters; ``L`` is read from the branch arrays,
        not from ``params`` (the Jacobian does not depend on ``L`` directly).

    Returns
    -------
    dict
        Keys: ``L`` (copy of input), ``alpha_complex`` / ``omega_complex``
        (NaN where there's no complex pair), ``leading_alpha`` (always
        finite), ``has_complex_pair`` (bool array), ``trace`` (per-step
        ``tr(J_split)`` for diagnostics). The aliases ``alpha``, ``omega``,
        ``is_complex`` mirror the keys
        :func:`bifurcation_engine.src.hopf_detector.detect_hopf` consumes,
        so the existing detector runs unchanged on a per-branch basis.
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
    trace = np.zeros(n, dtype=float)

    for i in range(n):
        analysis = eigenvalue_analysis_split(
            float(S[i]), float(R[i]), float(D[i]), params
        )
        leading_alpha[i] = float(analysis["leading_alpha"])  # type: ignore[arg-type]
        trace[i] = float(analysis["trace"])  # type: ignore[arg-type]
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
        "trace": trace,
        # detect_hopf-compatible aliases.
        "alpha": alpha_complex,
        "omega": omega_complex,
        "is_complex": has_complex,
    }
