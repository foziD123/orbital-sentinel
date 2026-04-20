"""Tests for :mod:`bifurcation_engine.src.fixed_points` (Task 3).

Covers VALIDATION.md T2.1, T2.2, T2.3, T2.4, T2.5. T2.6 (``delta_D > delta_S``
validation on :class:`ShellConfig` construction) is already covered in
``test_shell_config.py``; a single regression test here asserts that the
check is reachable from this module's entry point too.
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.fixed_points import (
    clean_orbit_fixed_point,
    coexistence_fixed_points,
    continuation_sweep,
    find_all_fixed_points,
)
from bifurcation_engine.src.model import d_dot, s_dot
from bifurcation_engine.src.shell_config import ShellConfig


def _shell_B(**overrides: float) -> ShellConfig:
    base = dict(
        shell_name="Shell_B_800km",
        altitude_km=800.0,
        L=100.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
    )
    base.update(overrides)
    return ShellConfig(**base)  # type: ignore[arg-type]


def _shell_T2_1() -> ShellConfig:
    """Exact parameters called out by VALIDATION.md T2.1."""
    return ShellConfig(
        shell_name="Shell_T2_1",
        altitude_km=800.0,
        L=100.0,
        delta_S=0.01,
        delta_D=0.05,
        beta=1e-5,
        gamma=1e-7,
    )


# ---------------------------------------------------------------------------
# T2.1 — Case 1 analytical fixed point is correct to 1e-10
# ---------------------------------------------------------------------------


def test_T2_1_clean_orbit_fixed_point_exact() -> None:
    params = _shell_T2_1()
    S_star, D_star = clean_orbit_fixed_point(params)

    # VALIDATION.md T2.1 requires tolerance 1e-10 on the analytical identity
    # S* == L / delta_S. With L=100, delta_S=0.01 the expected value is 10000.
    assert S_star == pytest.approx(10000.0, abs=1e-10)
    assert D_star == 0.0


# ---------------------------------------------------------------------------
# T2.2 — Case 1 fixed point satisfies the ODE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        _shell_B(),
        _shell_B(L=0.0),
        _shell_B(L=500.0),
        _shell_T2_1(),
    ],
)
def test_T2_2_clean_orbit_satisfies_ode(params: ShellConfig) -> None:
    S_star, D_star = clean_orbit_fixed_point(params)
    assert abs(s_dot(S_star, D_star, params)) < 1e-10
    assert abs(d_dot(S_star, D_star, params)) < 1e-10


# ---------------------------------------------------------------------------
# T2.3 — Case 2 fixed points satisfy the ODE when they exist
# ---------------------------------------------------------------------------


def test_T2_3_case2_fixed_points_satisfy_ode() -> None:
    # L=300 sits comfortably below the Shell_B fold (discriminant > 0) so
    # both Case-2 roots are real and physical.
    params = _shell_B(L=300.0)
    coexistence = coexistence_fixed_points(params)
    assert len(coexistence) >= 1, "Shell_B at L=300 should admit Case-2 solutions"
    for S_star, D_star in coexistence:
        assert abs(s_dot(S_star, D_star, params)) < 1e-8
        assert abs(d_dot(S_star, D_star, params)) < 1e-8


def test_coexistence_returns_empty_above_fold() -> None:
    # With Shell_B the discriminant of the Case-2 quadratic goes negative
    # at L of order 670; at L=1000 no real roots should be reported.
    params = _shell_B(L=1000.0)
    assert coexistence_fixed_points(params) == []


def test_coexistence_linear_branch_when_gamma_is_zero() -> None:
    """With gamma=0 the quadratic degenerates to a linear equation."""
    params = _shell_B(gamma=0.0, L=300.0)
    coexistence = coexistence_fixed_points(params)
    # Linear case: single root at D* = (beta*L - delta_S*delta_D) / (beta*delta_D)
    expected_D = (params.beta * params.L - params.delta_S * params.delta_D) / (
        params.beta * params.delta_D
    )
    assert len(coexistence) == 1
    S_star, D_star = coexistence[0]
    assert D_star == pytest.approx(expected_D)
    assert abs(s_dot(S_star, D_star, params)) < 1e-8
    assert abs(d_dot(S_star, D_star, params)) < 1e-8


# ---------------------------------------------------------------------------
# T2.4 — physical validity: no negative populations anywhere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "L",
    [0.0, 50.0, 100.0, 300.0, 500.0, 1000.0, 2000.0],
)
def test_T2_4_no_negative_populations(L: float) -> None:
    params = _shell_B(L=L)
    for S_star, D_star in find_all_fixed_points(params):
        assert S_star >= 0.0, f"S* = {S_star} is negative at L={L}"
        assert D_star >= 0.0, f"D* = {D_star} is negative at L={L}"


# ---------------------------------------------------------------------------
# T2.5 — continuation produces a smooth Case-2 branch
# ---------------------------------------------------------------------------


def test_T2_5_continuation_smoothness() -> None:
    params = _shell_B()
    L_values = np.linspace(0.0, 1000.0, 101)

    result = continuation_sweep(params, L_values)

    # Basic structure.
    n = len(L_values)
    assert result["L"].shape == result["S_star"].shape == result["D_star"].shape
    assert result["L"].shape == result["branch"].shape
    assert result["branch"].shape[0] >= n
    assert np.all(result["branch"][:n] == 1)

    # Case-1 segment: S* = L/delta_S, D* = 0 exactly.
    np.testing.assert_allclose(
        result["S_star"][:n], L_values / params.delta_S, atol=1e-10
    )
    np.testing.assert_allclose(result["D_star"][:n], 0.0, atol=1e-12)

    # Case-2 segment: ordered by L, smooth within the valid window.
    case2_mask = result["branch"] == 2
    case2_L = result["L"][case2_mask]
    case2_S = result["S_star"][case2_mask]
    case2_D = result["D_star"][case2_mask]

    assert case2_L.size > 10, (
        "Expected a non-trivial Case-2 branch in the Shell_B sweep below the fold"
    )
    # L must be monotonically non-decreasing along the Case-2 branch output.
    assert np.all(np.diff(case2_L) >= 0.0)

    # VALIDATION.md T2.5 smoothness criterion.
    mean_S = float(np.mean(case2_S))
    max_jump = float(np.max(np.abs(np.diff(case2_S))))
    assert max_jump / mean_S < 0.1, (
        f"Case-2 branch has a non-smooth jump: max step = {max_jump:.3g}, "
        f"mean |S*| = {mean_S:.3g}"
    )

    # Sanity: every returned Case-2 entry must actually sit at a fixed point.
    for L_i, S_star, D_star in zip(case2_L, case2_S, case2_D):
        local = ShellConfig(
            shell_name=params.shell_name,
            altitude_km=params.altitude_km,
            L=float(L_i),
            delta_S=params.delta_S,
            delta_D=params.delta_D,
            beta=params.beta,
            gamma=params.gamma,
        )
        assert abs(s_dot(S_star, D_star, local)) < 1e-6
        assert abs(d_dot(S_star, D_star, local)) < 1e-6


# ---------------------------------------------------------------------------
# T2.6 regression — lives in test_shell_config.py, re-checked from this suite
# ---------------------------------------------------------------------------


def test_T2_6_regression_via_shell_config() -> None:
    """Sanity check: constructing an invalid shell still raises from this module."""
    with pytest.raises(ValueError, match="delta_D.*delta_S"):
        _shell_B(delta_S=0.05, delta_D=0.01)
