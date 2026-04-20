"""Full nonlinear trajectory integration (Task 6).

Wraps :func:`scipy.integrate.solve_ivp` around :func:`model.ode_system` to
produce time-series trajectories ``(S(t), D(t))`` from an initial condition.
In the 2D Kessler model this is what we use to observe the qualitative
consequence of crossing the saddle-node fold: below the fold trajectories
relax onto the stable lower coexistence branch; past it they run away
because no coexistence equilibrium is left to hold the debris population
back.

Non-negativity is enforced by a post-integration clip (our solve_ivp
tolerances are tight enough that negative excursions, when they occur, are
of order the absolute tolerance — they come from the solver's internal
predictor dipping below zero, not from the physics). A light safety net
also terminates the integration early if either state diverges past a
configurable ceiling so "runaway" trajectories finish in finite time.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

import numpy as np
from scipy.integrate import solve_ivp

from .model import ode_system
from .shell_config import ShellConfig

__all__ = [
    "integrate_trajectory",
    "check_limit_cycle",
    "sweep_trajectories_above_Lc",
]


# When a trajectory exceeds this multiple of (L / delta_S) for S, or a hard
# ceiling for D, we abort integration. Prevents solvers from chasing a pure
# exponential blowup for longer than needed.
_S_RUNAWAY_MULTIPLIER = 1e4
_D_RUNAWAY_CEILING = 1e12


def integrate_trajectory(
    S0: float,
    D0: float,
    params: ShellConfig,
    t_span: tuple[float, float],
    t_eval: Sequence[float] | np.ndarray | None = None,
    rtol: float = 1e-6,
    atol: float = 1e-9,
    method: str = "RK45",
    enforce_nonnegativity: bool = True,
    runaway_ceiling_D: float = _D_RUNAWAY_CEILING,
) -> dict:
    """Integrate ``[S(t), D(t)]`` forward from ``(S0, D0)`` over ``t_span``.

    Parameters
    ----------
    S0, D0:
        Initial satellite and debris populations. Must be non-negative.
    params:
        Shell parameters (including ``params.L``, which is used *as-is* by
        :func:`model.ode_system` — callers wanting to integrate at a
        different launch rate must produce a ``replace``-d copy first).
    t_span:
        ``(t0, t_final)`` in years.
    t_eval:
        Optional explicit output grid. If ``None`` a dense linearly spaced
        1001-point grid across ``t_span`` is produced for the caller.
    rtol, atol:
        Relative and absolute tolerances forwarded to
        :func:`scipy.integrate.solve_ivp`.
    method:
        Any valid ``solve_ivp`` integrator. Defaults to ``"RK45"``.
    enforce_nonnegativity:
        When ``True`` (the default), any sample where ``S`` or ``D`` dips
        below zero is clipped to zero on the returned arrays. Small negative
        excursions are a known consequence of explicit integrators near the
        boundary ``D = 0`` (which is an absorbing state); clipping makes the
        output physically meaningful without slowing down the solver.
    runaway_ceiling_D:
        The solver is stopped early via a terminal event once ``D`` reaches
        this ceiling, so runaway trajectories complete quickly. Set to a
        very large number if you want to let the solver run to ``t_final``.

    Returns
    -------
    dict
        Keys: ``t``, ``S``, ``D`` (1-D arrays), ``success`` (bool),
        ``message`` (solver message), ``terminated_early`` (True when the
        runaway-event cut the run short), ``params_L`` (copy of the launch
        rate used, for reproducibility).

    Raises
    ------
    ValueError
        If ``S0 < 0`` or ``D0 < 0``, or ``t_span`` is empty.
    """
    if S0 < 0.0 or D0 < 0.0:
        raise ValueError(
            f"Initial conditions must be non-negative; got S0={S0}, D0={D0}"
        )
    t0, t_final = float(t_span[0]), float(t_span[1])
    if t_final <= t0:
        raise ValueError(f"t_span must be strictly increasing; got {t_span}")

    if t_eval is None:
        t_eval_arr = np.linspace(t0, t_final, 1001)
    else:
        t_eval_arr = np.asarray(t_eval, dtype=float)
        if t_eval_arr.ndim != 1 or t_eval_arr.size < 2:
            raise ValueError("t_eval must be a 1-D array of length >= 2")
        if t_eval_arr[0] < t0 or t_eval_arr[-1] > t_final:
            raise ValueError("t_eval must lie within t_span")

    def _runaway_event(t: float, y: np.ndarray) -> float:
        return float(runaway_ceiling_D - y[1])

    _runaway_event.terminal = True
    _runaway_event.direction = -1.0

    sol = solve_ivp(
        fun=lambda t, y: ode_system(t, y, params),
        t_span=(t0, t_final),
        y0=np.array([S0, D0], dtype=float),
        t_eval=t_eval_arr,
        method=method,
        rtol=rtol,
        atol=atol,
        events=_runaway_event,
    )

    t_out = np.asarray(sol.t, dtype=float)
    S_out = np.asarray(sol.y[0], dtype=float)
    D_out = np.asarray(sol.y[1], dtype=float)
    terminated_early = bool(sol.status == 1)

    if enforce_nonnegativity:
        S_out = np.maximum(S_out, 0.0)
        D_out = np.maximum(D_out, 0.0)

    return {
        "t": t_out,
        "S": S_out,
        "D": D_out,
        "success": bool(sol.success),
        "message": str(sol.message),
        "terminated_early": terminated_early,
        "params_L": float(params.L),
    }


def check_limit_cycle(
    trajectory: dict,
    transient_fraction: float = 0.5,
    cv_threshold: float = 0.05,
) -> dict:
    """Classify the late-time behaviour of a ``D(t)`` trajectory.

    After discarding the initial ``transient_fraction`` of the time series
    we look at the coefficient of variation ``std(D) / mean(D)``. When
    ``mean(D) == 0`` (or effectively so) we report a ``decayed`` outcome.

    Parameters
    ----------
    trajectory:
        Dict with keys ``t`` and ``D`` as returned by
        :func:`integrate_trajectory`.
    transient_fraction:
        Fraction of samples to discard from the start.
    cv_threshold:
        Coefficient-of-variation threshold above which the trajectory is
        classified as ``oscillating``.

    Returns
    -------
    dict
        Keys: ``oscillating`` (bool), ``amplitude`` (float,
        ``(max-min)/2``), ``period_estimate`` (float in years, ``NaN`` if
        non-oscillatory), ``mean`` (float), ``coefficient_of_variation``
        (float), ``classification`` (one of ``decayed``, ``stabilized``,
        ``oscillating``, ``runaway``, ``unknown``).
    """
    t = np.asarray(trajectory["t"], dtype=float)
    D = np.asarray(trajectory["D"], dtype=float)
    if t.size < 2 or D.size < 2:
        raise ValueError("trajectory must have at least two samples")
    if not 0.0 <= transient_fraction < 1.0:
        raise ValueError("transient_fraction must be in [0, 1)")

    start = int(transient_fraction * t.size)
    t_tail = t[start:]
    D_tail = D[start:]
    mean = float(np.mean(D_tail))
    amplitude = 0.5 * float(np.max(D_tail) - np.min(D_tail))

    if mean < 1e-6:
        return {
            "oscillating": False,
            "amplitude": amplitude,
            "period_estimate": float("nan"),
            "mean": mean,
            "coefficient_of_variation": 0.0,
            "classification": "decayed",
        }

    cv = float(np.std(D_tail) / mean)

    # Runaway: final value is enormously larger than the tail average → the
    # mean and std reflect growth, not oscillation.
    if trajectory.get("terminated_early", False) or D[-1] > 100.0 * mean:
        return {
            "oscillating": False,
            "amplitude": amplitude,
            "period_estimate": float("nan"),
            "mean": mean,
            "coefficient_of_variation": cv,
            "classification": "runaway",
        }

    if cv < cv_threshold:
        return {
            "oscillating": False,
            "amplitude": amplitude,
            "period_estimate": float("nan"),
            "mean": mean,
            "coefficient_of_variation": cv,
            "classification": "stabilized",
        }

    # Oscillatory: estimate the period from zero-crossings of D - mean.
    centered = D_tail - mean
    sign = np.sign(centered)
    # Zero-crossings are indices where sign changes (ignore zero samples).
    idx = np.where(np.diff(np.sign(np.where(sign == 0, 1, sign))))[0]
    if idx.size >= 2:
        crossing_times = t_tail[idx]
        diffs = np.diff(crossing_times)
        # A full period spans two zero-crossings.
        period = float(2.0 * np.mean(diffs))
    else:
        period = float("nan")

    return {
        "oscillating": True,
        "amplitude": amplitude,
        "period_estimate": period,
        "mean": mean,
        "coefficient_of_variation": cv,
        "classification": "oscillating",
    }


def sweep_trajectories_above_Lc(
    params: ShellConfig,
    L_c: float,
    n_steps: int = 5,
    S0: float | None = None,
    D0: float | None = None,
    t_span: tuple[float, float] = (0.0, 200.0),
) -> list[dict]:
    """Integrate trajectories at a ladder of launch rates above ``L_c``.

    Defaults to the fractions ``[1.01, 1.05, 1.10, 1.20, 1.50]`` (trimmed
    to the first ``n_steps`` entries). Each trajectory is returned with its
    corresponding ``L`` under the key ``"L"`` alongside the usual
    :func:`integrate_trajectory` payload.

    Parameters
    ----------
    params:
        Shell parameters. ``params.L`` is overridden per step.
    L_c:
        Reference launch rate (Hopf critical value or saddle-node fold).
    n_steps:
        How many of the canonical fractions to use (1..5). Values outside
        that range are clamped.
    S0, D0:
        Initial condition. Defaults to the clean-orbit fixed point at
        ``L = L_c`` with a small 10-object debris seed to break degeneracy.
    t_span:
        Integration window in years.
    """
    fractions = [1.01, 1.05, 1.10, 1.20, 1.50]
    n = max(1, min(n_steps, len(fractions)))
    fractions = fractions[:n]

    if S0 is None:
        S0 = L_c / params.delta_S
    if D0 is None:
        D0 = 10.0

    out: list[dict] = []
    for frac in fractions:
        L_step = float(L_c * frac)
        local = replace(params, L=L_step)
        traj = integrate_trajectory(S0, D0, local, t_span)
        traj = {**traj, "L": L_step, "L_fraction": frac}
        out.append(traj)
    return out
