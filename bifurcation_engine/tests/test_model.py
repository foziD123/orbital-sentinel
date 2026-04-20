"""Tests for :mod:`bifurcation_engine.src.model` (Task 2).

Covers VALIDATION.md T1.1, T1.2, T1.3 (see note below), T1.4, T1.5.
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.integrator import integrate_trajectory
from bifurcation_engine.src.model import d_dot, ode_system, s_dot
from bifurcation_engine.src.shell_config import ShellConfig


def _shell_B() -> ShellConfig:
    """Literature-calibrated Shell_B_800km parameters."""
    return ShellConfig(
        shell_name="Shell_B_800km",
        altitude_km=800.0,
        L=100.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
    )


# ---------------------------------------------------------------------------
# T1.1 — clean orbit is stationary in D
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("S0", [0.0, 1.0, 100.0, 1.0e6])
def test_T1_1_clean_orbit_is_stationary(S0: float) -> None:
    params = _shell_B()
    assert d_dot(S0, 0.0, params) == 0.0


# ---------------------------------------------------------------------------
# T1.2 — satellite decay only depends on L and delta_S when D=0
# ---------------------------------------------------------------------------


def test_T1_2_satellite_rate_without_debris() -> None:
    params = _shell_B()
    expected = params.L - params.delta_S * 100.0
    assert s_dot(100.0, 0.0, params) == pytest.approx(expected, rel=0, abs=1e-12)


# ---------------------------------------------------------------------------
# T1.3 — Kessler term dominates at sufficiently high debris
#
# NOTE ON VALIDATION.md T1.3: the spec lists gamma=1e-7, delta_D=0.005, D=10000
# and asserts `gamma * D**2 > delta_D * D`. These numbers are internally
# inconsistent: the Kessler/drag crossover sits at D = delta_D/gamma = 50_000,
# so at D=10_000 we have gamma*D**2 = 10 < 50 = delta_D*D and d_dot < 0. The
# stated intent of the test ("Kessler term dominates at high debris") is still
# the right physics check, so we exercise the ODE below and above the
# crossover to pin down both regimes. Flag for VALIDATION.md update.
# ---------------------------------------------------------------------------


def _kessler_test_shell() -> ShellConfig:
    """Minimal shell exposing only the terms T1.3 cares about."""
    return ShellConfig(
        shell_name="Shell_T13",
        altitude_km=800.0,
        L=0.0,
        delta_S=0.001,  # not exercised by T1.3 (S=0)
        delta_D=0.005,
        beta=1e-5,  # not exercised by T1.3 (S=0)
        gamma=1e-7,
    )


def test_T1_3_kessler_term_dominates_above_crossover() -> None:
    params = _kessler_test_shell()
    crossover_D = params.delta_D / params.gamma  # 50_000
    below = crossover_D / 5.0
    above = crossover_D * 2.0

    assert d_dot(0.0, below, params) < 0.0, (
        "below the crossover, linear drag must still dominate"
    )
    assert d_dot(0.0, above, params) > 0.0, (
        "above the crossover, the quadratic Kessler term must drive D upward"
    )

    expected_above = params.gamma * above**2 - params.delta_D * above
    assert d_dot(0.0, above, params) == pytest.approx(expected_above)


# ---------------------------------------------------------------------------
# T1.4 — non-negativity under integration
# ---------------------------------------------------------------------------


def test_T1_4_non_negativity_under_integration() -> None:
    """A long integration at large L must keep both states non-negative."""
    params = _shell_B()
    high_L = ShellConfig(
        shell_name=params.shell_name,
        altitude_km=params.altitude_km,
        L=1e4,
        delta_S=params.delta_S,
        delta_D=params.delta_D,
        beta=params.beta,
        gamma=params.gamma,
    )
    traj = integrate_trajectory(
        S0=10.0,
        D0=0.0,
        params=high_L,
        t_span=(0.0, 200.0),
    )
    assert traj["success"] is True or traj["terminated_early"]
    assert traj["S"].min() >= 0.0
    assert traj["D"].min() >= 0.0


# ---------------------------------------------------------------------------
# T1.5 — ode_system signature matches scipy convention
# ---------------------------------------------------------------------------


def test_T1_5_ode_system_signature() -> None:
    params = _shell_B()
    y = [100.0, 50.0]
    result = ode_system(0.0, y, params)

    assert isinstance(result, np.ndarray)
    assert result.shape == (2,)
    assert result[0] == pytest.approx(s_dot(100.0, 50.0, params))
    assert result[1] == pytest.approx(d_dot(100.0, 50.0, params))


def test_T1_5_ode_system_accepts_numpy_array() -> None:
    params = _shell_B()
    y = np.array([123.4, 56.7])
    result = ode_system(7.0, y, params)  # time argument is ignored (autonomous)
    assert result[0] == pytest.approx(s_dot(123.4, 56.7, params))
    assert result[1] == pytest.approx(d_dot(123.4, 56.7, params))


# ---------------------------------------------------------------------------
# Additional sanity checks (not in VALIDATION.md but cheap to add)
# ---------------------------------------------------------------------------


def test_origin_is_a_fixed_point_for_L_zero() -> None:
    """With L=0, (S=0, D=0) is a stationary state of the full system."""
    params = ShellConfig(
        shell_name="Shell_L0",
        altitude_km=800.0,
        L=0.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
    )
    assert s_dot(0.0, 0.0, params) == 0.0
    assert d_dot(0.0, 0.0, params) == 0.0


def test_equations_match_pdf_exactly() -> None:
    """Compare to the raw arithmetic form from the PDF at an off-axis point."""
    params = _shell_B()
    S, D = 500.0, 2_000.0

    expected_s = params.L - params.delta_S * S - params.beta * S * D
    expected_d = (
        params.beta * S * D + params.gamma * D * D - params.delta_D * D
    )

    assert s_dot(S, D, params) == pytest.approx(expected_s)
    assert d_dot(S, D, params) == pytest.approx(expected_d)
