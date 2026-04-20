"""ODE system for a single orbital shell (Task 2).

Implements the Kessler-syndrome model exactly as stated in
``Space_Debris_Preliminary_Model.pdf`` and reiterated in ``CLAUDE.md``::

    S_dot = L - delta_S * S - beta * S * D
    D_dot = beta * S * D + gamma * D**2 - delta_D * D

The quadratic ``gamma * D**2`` term is the mathematical signature of Kessler
syndrome: once debris density is high enough it dominates the linear drag term
``delta_D * D`` and the debris population runs away.

State variable ordering follows ``y = [S, D]`` throughout, which is the order
consumed by :func:`ode_system` and returned by the fixed-point solvers in
:mod:`bifurcation_engine.src.fixed_points`.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .shell_config import ShellConfig

__all__ = ["s_dot", "d_dot", "ode_system"]


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
