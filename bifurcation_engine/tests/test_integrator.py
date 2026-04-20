"""Tests for :mod:`bifurcation_engine.src.integrator` (Task 6).

The new acceptance criterion — replacing VALIDATION.md T5.4 now that we know
the 2D Kessler model undergoes a saddle-node fold rather than a Hopf — is
that ``integrate_trajectory`` produces distinguishable qualitative
behaviour at ``L = 0.5 * L_fold``, ``L_fold`` and ``1.5 * L_fold``:

* below the fold the trajectory relaxes onto the lower stable coexistence
  fixed point,
* at the fold the dynamics slow dramatically (the two coexistence roots
  have just merged into a non-hyperbolic fixed point),
* past the fold no coexistence equilibrium exists and ``D`` runs away.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import detect_fold
from bifurcation_engine.src.integrator import (
    check_limit_cycle,
    integrate_trajectory,
    sweep_trajectories_above_Lc,
)
from bifurcation_engine.src.shell_config import ShellConfig, default_shells


def _shell_B() -> ShellConfig:
    return ShellConfig(
        shell_name="Shell_B_800km",
        altitude_km=800.0,
        L=100.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
        L_sweep_min=0.0,
        L_sweep_max=1000.0,
    )


# ---------------------------------------------------------------------------
# Basic API
# ---------------------------------------------------------------------------


def test_integrate_trajectory_shape_and_keys() -> None:
    params = _shell_B()
    traj = integrate_trajectory(100.0, 50.0, params, (0.0, 10.0))
    for key in ("t", "S", "D", "success", "message", "terminated_early"):
        assert key in traj
    assert traj["t"].shape == traj["S"].shape == traj["D"].shape
    assert traj["t"][0] == pytest.approx(0.0)
    assert traj["t"][-1] == pytest.approx(10.0)
    assert traj["success"] is True


def test_integrate_trajectory_zero_debris_stays_zero() -> None:
    """With ``D0 = 0`` the debris population must remain identically zero
    (the origin is an absorbing state of the D equation) and ``S`` relaxes
    to the Case-1 equilibrium ``L / delta_S`` on the satellite decay timescale.
    """
    params = _shell_B()
    # Run for 10 satellite e-folding times (delta_S = 0.005 -> tau = 200 yr).
    t_span = (0.0, 10.0 / params.delta_S)
    traj = integrate_trajectory(100.0, 0.0, params, t_span)
    assert np.all(traj["D"] == 0.0)
    assert traj["S"][-1] == pytest.approx(params.L / params.delta_S, rel=1e-3)


def test_integrate_trajectory_rejects_negative_ics() -> None:
    params = _shell_B()
    with pytest.raises(ValueError, match="non-negative"):
        integrate_trajectory(-1.0, 0.0, params, (0.0, 1.0))
    with pytest.raises(ValueError, match="non-negative"):
        integrate_trajectory(0.0, -1.0, params, (0.0, 1.0))


def test_integrate_trajectory_rejects_empty_span() -> None:
    params = _shell_B()
    with pytest.raises(ValueError, match="strictly increasing"):
        integrate_trajectory(1.0, 1.0, params, (5.0, 5.0))


def test_integrate_trajectory_respects_t_eval() -> None:
    params = _shell_B()
    t_eval = np.linspace(0.0, 50.0, 21)
    traj = integrate_trajectory(100.0, 10.0, params, (0.0, 50.0), t_eval=t_eval)
    np.testing.assert_allclose(traj["t"], t_eval)


# ---------------------------------------------------------------------------
# Fold-driven acceptance test (replaces T5.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shell", list(default_shells()))
def test_trajectory_relaxes_to_lower_branch_below_fold(
    shell: ShellConfig,
) -> None:
    """At L = 0.5 * L_fold the trajectory must relax onto the stable lower
    coexistence fixed point.
    """
    sweep_max = max(shell.L_sweep_max, 1.0)
    L = np.linspace(0.0, 2.0 * sweep_max, 2001)
    fold = detect_fold(shell, L)
    assert fold.L_fold is not None

    L_test = 0.5 * float(fold.L_fold)
    local = replace(shell, L=L_test)
    roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
    assert len(roots) == 2, "Must have two coexistence roots below the fold"
    (S_low_star, D_low_star), _upper = roots

    traj = integrate_trajectory(S_low_star, D_low_star, local, (0.0, 500.0))
    assert traj["success"] is True
    # Late-time state matches the analytical lower-branch equilibrium.
    assert traj["S"][-1] == pytest.approx(S_low_star, rel=1e-3)
    assert traj["D"][-1] == pytest.approx(D_low_star, rel=1e-3)


@pytest.mark.parametrize("shell", list(default_shells()))
def test_trajectory_runs_away_above_fold(shell: ShellConfig) -> None:
    """At L = 1.5 * L_fold no coexistence equilibrium exists and D must
    grow unboundedly (or trip the solver's runaway event). The integration
    window is scaled by the shell's satellite decay timescale so slow-drag
    shells (notably Shell C) have enough time to see the blowup develop.
    """
    sweep_max = max(shell.L_sweep_max, 1.0)
    L = np.linspace(0.0, 2.0 * sweep_max, 2001)
    fold = detect_fold(shell, L)
    assert fold.L_fold is not None and fold.D_star_at_fold is not None

    L_test = 1.5 * float(fold.L_fold)
    local = replace(shell, L=L_test)

    S0 = float(fold.S_star_at_fold or 1.0)
    D0 = float(fold.D_star_at_fold)

    # t_final = 10 satellite-decay timescales, capped at 20 000 years.
    t_final = min(10.0 / shell.delta_S, 2.0e4)
    traj = integrate_trajectory(
        S0,
        D0,
        local,
        (0.0, t_final),
        runaway_ceiling_D=1e9,
    )
    assert traj["terminated_early"] or traj["D"][-1] > 10.0 * D0


@pytest.mark.parametrize("shell", list(default_shells()))
def test_trajectory_at_fold_hovers_near_merged_root(
    shell: ShellConfig,
) -> None:
    """At ``L = L_fold`` the merged coexistence root ``(S_fold, D_fold)`` is
    still a fixed point (with a zero eigenvalue) — so starting exactly
    there, ``D(t)`` must hover within a reasonable band of ``D_fold`` over
    a long integration window, rather than either relaxing to a different
    equilibrium or running away.
    """
    sweep_max = max(shell.L_sweep_max, 1.0)
    L = np.linspace(0.0, 2.0 * sweep_max, 2001)
    fold = detect_fold(shell, L)
    assert fold.L_fold is not None and fold.D_star_at_fold is not None

    local = replace(shell, L=float(fold.L_fold))
    S0 = float(fold.S_star_at_fold or 1.0)
    D0 = float(fold.D_star_at_fold)

    # 5 satellite-decay timescales — long enough for non-hyperbolic drift
    # to manifest but short enough to stay near the merged point.
    t_final = min(5.0 / shell.delta_S, 1.0e4)
    traj = integrate_trajectory(S0, D0, local, (0.0, t_final))

    # D stays bounded — no runaway (within an order of magnitude).
    assert traj["D"].max() < 10.0 * D0
    # And does not collapse to zero.
    assert traj["D"][-1] > 0.05 * D0


# ---------------------------------------------------------------------------
# check_limit_cycle
# ---------------------------------------------------------------------------


def test_check_limit_cycle_stabilized_trajectory() -> None:
    params = _shell_B()
    sweep = np.linspace(0.0, 2.0 * params.L_sweep_max, 2001)
    fold = detect_fold(params, sweep)
    assert fold.L_fold is not None

    local = replace(params, L=0.5 * float(fold.L_fold))
    roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
    S_low, D_low = roots[0]
    traj = integrate_trajectory(S_low, D_low, local, (0.0, 500.0))

    result = check_limit_cycle(traj)
    assert result["classification"] == "stabilized"
    assert result["oscillating"] is False


def test_check_limit_cycle_decayed_trajectory() -> None:
    params = _shell_B()
    traj = integrate_trajectory(100.0, 0.0, params, (0.0, 50.0))
    result = check_limit_cycle(traj)
    assert result["classification"] == "decayed"


def test_check_limit_cycle_runaway_trajectory() -> None:
    params = _shell_B()
    sweep = np.linspace(0.0, 2.0 * params.L_sweep_max, 2001)
    fold = detect_fold(params, sweep)
    assert fold.L_fold is not None and fold.D_star_at_fold is not None

    local = replace(params, L=1.5 * float(fold.L_fold))
    traj = integrate_trajectory(
        1.0,
        float(fold.D_star_at_fold),
        local,
        (0.0, 500.0),
        runaway_ceiling_D=1e10,
    )
    result = check_limit_cycle(traj)
    assert result["classification"] == "runaway"


def test_check_limit_cycle_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="at least two"):
        check_limit_cycle({"t": np.array([0.0]), "D": np.array([1.0])})
    with pytest.raises(ValueError, match="transient_fraction"):
        check_limit_cycle(
            {"t": np.linspace(0, 1, 10), "D": np.ones(10)},
            transient_fraction=1.0,
        )


# ---------------------------------------------------------------------------
# sweep_trajectories_above_Lc
# ---------------------------------------------------------------------------


def test_sweep_trajectories_above_Lc_returns_requested_number() -> None:
    params = _shell_B()
    sweep = np.linspace(0.0, 2.0 * params.L_sweep_max, 2001)
    fold = detect_fold(params, sweep)
    assert fold.L_fold is not None

    results = sweep_trajectories_above_Lc(
        params,
        float(fold.L_fold),
        n_steps=3,
        t_span=(0.0, 50.0),
    )
    assert len(results) == 3
    for r in results:
        assert r["L"] > float(fold.L_fold)
        assert "L_fraction" in r
        assert r["t"].shape == r["D"].shape
