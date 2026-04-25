"""ODE system for a single orbital shell (Task 2 + 3-species extension).

The 2-D model (default) is taken verbatim from
``Space_Debris_Preliminary_Model.pdf`` and reiterated in ``CLAUDE.md``::

    S_dot = L - delta_S * S - beta * S * D
    D_dot = beta * S * D + gamma * D**2 - delta_D * D

The quadratic ``gamma * D**2`` term is the mathematical signature of Kessler
syndrome: once debris density is high enough it dominates the linear drag term
``delta_D * D`` and the debris population runs away.

The 3-species opt-in (``use_3species=True`` on :class:`ShellConfig`) adds a
derelict population ``R`` between active satellites and debris::

    S_dot = L - delta_S * S - beta * S * D - beta_SR * S * R
    R_dot = delta_S * S - delta_R * R - beta_RD * R * D
    D_dot = beta * S * D + beta_SR * S * R + beta_RD * R * D
            + gamma * D**2 - delta_D * D

Note on the ``R_dot`` form: the active-derelict collision term
``-beta_SR * S * R`` appears in ``S_dot`` (the active satellite is fragmented)
and as a positive source in ``D_dot`` (those fragments enter the debris
population), but is intentionally absent from ``R_dot`` — the derelict body is
treated as not removed by the encounter. This is the spec set in TODO.md /
TASKS.md and is preserved exactly here so future readers do not assume mass
conservation across the S-R channel.

State variable ordering for the 2-D system is ``y = [S, D]``; for the 3-D
extension it is ``y = [S, R, D]``. Both functions are autonomous (``t`` is
unused) and both interoperate with :mod:`scipy.integrate.solve_ivp`.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .shell_config import ShellConfig

__all__ = [
    "s_dot",
    "d_dot",
    "ode_system",
    "s_dot_3species",
    "r_dot_3species",
    "d_dot_3species",
    "ode_system_3species",
]


def s_dot(S: float, D: float, params: ShellConfig) -> float:
    """Satellite population rate of change.

    ``S_dot = L - delta_S * S - beta * S * D``
    """
    return params.L - params.delta_S * S - params.beta * S * D


def d_dot(S: float, D: float, params: ShellConfig) -> float:
    """Debris population rate of change.

    ``D_dot = beta * S * D + gamma * D**2 - delta_D * D``

    When ``D == 0`` every term vanishes, so a clean orbit is an absorbing
    boundary for the debris population (no cascade source).
    """
    return params.beta * S * D + params.gamma * D * D - params.delta_D * D


def ode_system(
    t: float,
    y: Sequence[float] | np.ndarray,
    params: ShellConfig,
) -> np.ndarray:
    """Right-hand side suitable for :func:`scipy.integrate.solve_ivp`.

    Parameters
    ----------
    t:
        Current time (unused — the system is autonomous).
    y:
        State vector ``[S, D]``.
    params:
        Shell parameters.

    Returns
    -------
    numpy.ndarray
        Length-2 array ``[s_dot, d_dot]``.
    """
    S = float(y[0])
    D = float(y[1])
    return np.array(
        [s_dot(S, D, params), d_dot(S, D, params)],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# 3-species (S, R, D) extension
# ---------------------------------------------------------------------------


def s_dot_3species(S: float, R: float, D: float, params: ShellConfig) -> float:
    """Active-satellite rate of change in the 3-species model.

    ``S_dot = L - delta_S*S - beta*S*D - beta_SR*S*R``

    Reduces exactly to :func:`s_dot` when ``R == 0`` or ``beta_SR == 0``
    (the latter being how the 3-species model degenerates to the 2-D one).
    """
    return (
        params.L
        - params.delta_S * S
        - params.beta * S * D
        - params.beta_SR * S * R
    )


def r_dot_3species(S: float, R: float, D: float, params: ShellConfig) -> float:
    """Derelict population rate of change.

    ``R_dot = delta_S*S - delta_R*R - beta_RD*R*D``

    Sources: post-mission active satellites lose station-keeping at rate
    ``delta_S`` and become derelicts. Sinks: atmospheric drag (``delta_R``)
    and collisions with debris (``beta_RD * R * D``). The active-derelict
    collision term ``beta_SR * S * R`` is *not* a sink for ``R``; see the
    module docstring for the modelling rationale.
    """
    return params.delta_S * S - params.delta_R * R - params.beta_RD * R * D


def d_dot_3species(S: float, R: float, D: float, params: ShellConfig) -> float:
    """Debris rate of change in the 3-species model.

    ``D_dot = beta*S*D + beta_SR*S*R + beta_RD*R*D + gamma*D**2 - delta_D*D``

    Three collision sources feed debris: active-on-debris, active-on-derelict,
    and derelict-on-debris. The Kessler ``gamma*D**2`` self-cascade and the
    linear atmospheric sink ``delta_D*D`` are unchanged from the 2-D model.
    Reduces exactly to :func:`d_dot` when ``beta_SR == 0`` and
    ``beta_RD == 0`` (or equivalently when ``R == 0``).
    """
    return (
        params.beta * S * D
        + params.beta_SR * S * R
        + params.beta_RD * R * D
        + params.gamma * D * D
        - params.delta_D * D
    )


def ode_system_3species(
    t: float,
    y: Sequence[float] | np.ndarray,
    params: ShellConfig,
) -> np.ndarray:
    """Right-hand side of the 3-species ODE for :func:`scipy.integrate.solve_ivp`.

    Parameters
    ----------
    t:
        Current time (unused — the system is autonomous).
    y:
        State vector ``[S, R, D]``.
    params:
        Shell parameters. The 3-species fields ``delta_R``, ``beta_SR``,
        ``beta_RD`` are read; ``params.use_3species`` is *not* asserted by
        this function so that the 2-D-equivalence test (``beta_SR=0``,
        ``beta_RD=0``) can run with ``use_3species=True`` without tripping
        validation.

    Returns
    -------
    numpy.ndarray
        Length-3 array ``[s_dot_3species, r_dot_3species, d_dot_3species]``.
    """
    S = float(y[0])
    R = float(y[1])
    D = float(y[2])
    return np.array(
        [
            s_dot_3species(S, R, D, params),
            r_dot_3species(S, R, D, params),
            d_dot_3species(S, R, D, params),
        ],
        dtype=float,
    )
