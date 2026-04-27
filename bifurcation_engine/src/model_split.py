"""Split-decay 3-species ODE for the Hopf-hunt experiment.

This is a quarantined experimental model. The production 2-D and 3-species
ODEs in :mod:`bifurcation_engine.src.model` are **not** modified or imported
in any code path triggered by this module — the file lives alongside them
purely to keep the directory layout coherent.

The model is::

    S_dot = L  - kappa_S*S - rho_S*S       - beta_SD*S*D - beta_SR*S*R
    R_dot =       rho_S*S  - delta_R*R     - beta_RD*R*D - beta_SR*S*R
    D_dot = eta_SD*beta_SD*S*D + eta_SR*beta_SR*S*R + eta_RD*beta_RD*R*D
            + gamma*D**2 - delta_D*D

with state vector ``y = [S, R, D]``. The Jacobian for this system is in
:mod:`bifurcation_engine.src.eigenvalues_split`; the closed-form derivation
is in the project plan (split-decay Hopf-hunt).

Two modelling choices to flag explicitly:

* The two ``S_dot`` outflow terms ``-kappa_S*S - rho_S*S`` together equal
  the original shell's ``-delta_S*S``. The split is therefore comparable to
  the existing 3-species model term-by-term whenever
  ``kappa_S + rho_S == delta_S``; this conservation is enforced in
  :class:`SplitDecayConfig.__post_init__`.

* ``R_dot`` includes ``-beta_SR*S*R`` (the derelict body is removed in an
  active-derelict collision). This is the physically realistic version of
  the channel and a deliberate departure from the existing 3-species
  model's documented asymmetry. The Jacobian and trace inequality reflect
  this exactly — see the plan.

Both functions are autonomous (``t`` is unused) and interoperate with
:func:`scipy.integrate.solve_ivp`.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .split_decay_config import SplitDecayConfig

__all__ = [
    "s_dot_split",
    "r_dot_split",
    "d_dot_split",
    "ode_system_split",
]


def s_dot_split(S: float, R: float, D: float, params: SplitDecayConfig) -> float:
    """Active-satellite rate of change in the split-decay model.

    ``S_dot = L - kappa_S*S - rho_S*S - beta_SD*S*D - beta_SR*S*R``

    Reduces to the existing 3-species ``s_dot_3species`` exactly when
    ``rho_S = delta_S`` and ``kappa_S = 0`` (the boundary that
    :class:`SplitDecayConfig` rejects, but mathematically continuous).
    """
    return (
        params.L
        - params.kappa_S * S
        - params.rho_S * S
        - params.beta_SD * S * D
        - params.beta_SR * S * R
    )


def r_dot_split(S: float, R: float, D: float, params: SplitDecayConfig) -> float:
    """Derelict population rate of change in the split-decay model.

    ``R_dot = rho_S*S - delta_R*R - beta_RD*R*D - beta_SR*S*R``

    Sources: failed active satellites (``rho_S*S``).
    Sinks: atmospheric drag (``delta_R*R``), debris collisions
    (``beta_RD*R*D``), and the deliberate ``-beta_SR*S*R`` derelict-removal
    correction that distinguishes this model from the existing
    asymmetric 3-species ``r_dot_3species``.
    """
    return (
        params.rho_S * S
        - params.delta_R * R
        - params.beta_RD * R * D
        - params.beta_SR * S * R
    )


def d_dot_split(S: float, R: float, D: float, params: SplitDecayConfig) -> float:
    """Debris rate of change in the split-decay model.

    ``D_dot = eta_SD*beta_SD*S*D + eta_SR*beta_SR*S*R + eta_RD*beta_RD*R*D
             + gamma*D**2 - delta_D*D``

    Each collision channel that produces fragments is multiplied by its own
    ``eta`` (yield multiplier). With ``eta_SD = eta_SR = eta_RD = 1`` this
    reduces to the existing 3-species ``d_dot_3species`` source structure
    exactly (modulo the rename ``beta_SD = beta``).
    """
    return (
        params.eta_SD * params.beta_SD * S * D
        + params.eta_SR * params.beta_SR * S * R
        + params.eta_RD * params.beta_RD * R * D
        + params.gamma * D * D
        - params.delta_D * D
    )


def ode_system_split(
    t: float,
    y: Sequence[float] | np.ndarray,
    params: SplitDecayConfig,
) -> np.ndarray:
    """Right-hand side of the split-decay ODE for :func:`scipy.integrate.solve_ivp`.

    Parameters
    ----------
    t:
        Current time (unused — the system is autonomous).
    y:
        State vector ``[S, R, D]``.
    params:
        Split-decay shell parameters.

    Returns
    -------
    numpy.ndarray
        Length-3 array ``[s_dot_split, r_dot_split, d_dot_split]``.
    """
    S = float(y[0])
    R = float(y[1])
    D = float(y[2])
    return np.array(
        [
            s_dot_split(S, R, D, params),
            r_dot_split(S, R, D, params),
            d_dot_split(S, R, D, params),
        ],
        dtype=float,
    )
