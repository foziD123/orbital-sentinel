"""Tests for the 3-species (S, R, D) extension of the ODE model.

Covers Step 2 of the 3-species engine extension. The acceptance criterion
that matters most: when ``beta_SR = 0`` and ``beta_RD = 0`` the (S, D)
projection of :func:`ode_system_3species` matches :func:`ode_system` exactly,
so all existing 2-D tests continue to describe the same dynamics in the
3-species code path.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from bifurcation_engine.src.model import (
    d_dot,
    d_dot_3species,
    ode_system,
    ode_system_3species,
    r_dot_3species,
    s_dot,
    s_dot_3species,
)
from bifurcation_engine.src.shell_config import ShellConfig


def _shell_2D(**overrides: object) -> ShellConfig:
    """Shell_B-like 2-D config for sanity tests."""
    base: dict[str, object] = {
        "shell_name": "Shell_B_test",
        "altitude_km": 800.0,
        "L": 100.0,
        "delta_S": 0.005,
        "delta_D": 0.02,
        "beta": 1.5e-5,
        "gamma": 1.5e-7,
    }
    base.update(overrides)
    return ShellConfig(**base)  # type: ignore[arg-type]


def _shell_3D(**overrides: object) -> ShellConfig:
    """Shell_B-like config with the parameter recipe from Step 5 baked in."""
    base: dict[str, object] = {
        "shell_name": "Shell_B_test_3D",
        "altitude_km": 800.0,
        "L": 100.0,
        "delta_S": 0.005,
        "delta_D": 0.02,
        "beta": 1.5e-5,
        "gamma": 1.5e-7,
        "delta_R": 0.5 * (0.005 + 0.02),
        "beta_SR": 2.0 * 1.5e-5,
        "beta_RD": 3.0 * 1.5e-5,
        "use_3species": True,
    }
    base.update(overrides)
    return ShellConfig(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Per-component sanity
# ---------------------------------------------------------------------------


def test_r_dot_zero_satellite_collapses_to_decay() -> None:
    """When S = 0, r_dot reduces to -(delta_R + beta_RD * D) * R."""
    p = _shell_3D()
    R, D = 250.0, 1000.0
    expected = -(p.delta_R + p.beta_RD * D) * R
    assert r_dot_3species(0.0, R, D, p) == pytest.approx(expected, rel=1e-12)


def test_r_dot_no_debris_is_pure_inflow_minus_drag() -> None:
    """With D = 0, r_dot = delta_S * S - delta_R * R."""
    p = _shell_3D()
    S, R = 5000.0, 200.0
    expected = p.delta_S * S - p.delta_R * R
    assert r_dot_3species(S, R, 0.0, p) == pytest.approx(expected, rel=1e-12)


def test_s_dot_3species_with_zero_R_matches_2D() -> None:
    """When R = 0, the new beta_SR*S*R term vanishes and s_dot_3species
    reproduces the 2-D s_dot pointwise."""
    p = _shell_3D()
    p_2D = _shell_2D(
        L=p.L,
        delta_S=p.delta_S,
        delta_D=p.delta_D,
        beta=p.beta,
        gamma=p.gamma,
    )
    for S, D in [(100.0, 50.0), (5000.0, 0.0), (0.0, 0.0)]:
        assert s_dot_3species(S, 0.0, D, p) == pytest.approx(
            s_dot(S, D, p_2D), rel=1e-12, abs=1e-15
        )


def test_d_dot_3species_with_zero_R_and_zero_couplings_matches_2D() -> None:
    """When beta_SR = beta_RD = 0, d_dot_3species reduces to d_dot regardless
    of R."""
    p_3D = _shell_3D(beta_SR=0.0, beta_RD=0.0, use_3species=False)
    # use_3species=False is necessary because beta_SR=0 violates the 3-species
    # validation; we still want the *function* to behave correctly for any R.
    p_2D = _shell_2D(
        L=p_3D.L,
        delta_S=p_3D.delta_S,
        delta_D=p_3D.delta_D,
        beta=p_3D.beta,
        gamma=p_3D.gamma,
    )
    for S, R, D in [(100.0, 0.0, 50.0), (5000.0, 200.0, 1.0), (0.0, 50.0, 0.0)]:
        assert d_dot_3species(S, R, D, p_3D) == pytest.approx(
            d_dot(S, D, p_2D), rel=1e-12, abs=1e-15
        )


# ---------------------------------------------------------------------------
# ode_system_3species signature
# ---------------------------------------------------------------------------


def test_ode_system_3species_returns_length_3_array() -> None:
    p = _shell_3D()
    out = ode_system_3species(0.0, [10.0, 5.0, 2.0], p)
    assert isinstance(out, np.ndarray)
    assert out.shape == (3,)
    assert out.dtype == np.float64


def test_ode_system_3species_components_match_per_component_helpers() -> None:
    p = _shell_3D()
    state = (123.0, 17.0, 45.0)
    out = ode_system_3species(0.0, list(state), p)

    S, R, D = state
    assert out[0] == pytest.approx(s_dot_3species(S, R, D, p), rel=1e-12)
    assert out[1] == pytest.approx(r_dot_3species(S, R, D, p), rel=1e-12)
    assert out[2] == pytest.approx(d_dot_3species(S, R, D, p), rel=1e-12)


def test_ode_system_3species_is_autonomous_in_t() -> None:
    """Right-hand side must not depend on the time argument."""
    p = _shell_3D()
    state = [1000.0, 100.0, 50.0]
    a = ode_system_3species(0.0, state, p)
    b = ode_system_3species(123.456, state, p)
    np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# Reduces-to-2D projection (the headline equivalence test)
# ---------------------------------------------------------------------------


def test_3species_reduces_to_2D_in_S_D_projection() -> None:
    """With beta_SR = beta_RD = 0 the (S, D) sub-system of the 3-species
    model is decoupled from R and equals the 2-D system. We integrate both
    side-by-side and compare ``S(t)`` and ``D(t)`` pointwise. R is allowed
    to drift; we don't constrain it.
    """
    # Build a 2-D shell and a 3-D shell sharing every shared parameter,
    # with the new collision channels switched off. We deliberately give
    # delta_R a non-trivial value (the midpoint) to show that the (S, D)
    # equivalence does NOT depend on what R is doing.
    p_2D = _shell_2D()
    p_3D = ShellConfig(
        shell_name=p_2D.shell_name + "_3D",
        altitude_km=p_2D.altitude_km,
        L=p_2D.L,
        delta_S=p_2D.delta_S,
        delta_D=p_2D.delta_D,
        beta=p_2D.beta,
        gamma=p_2D.gamma,
        delta_R=0.5 * (p_2D.delta_S + p_2D.delta_D),
        beta_SR=0.0,
        beta_RD=0.0,
        use_3species=False,  # avoid 3-species validation; logic is what matters
    )

    S0, R0, D0 = 5000.0, 250.0, 50.0
    t_eval = np.linspace(0.0, 200.0, 401)

    sol_2D = solve_ivp(
        fun=lambda t, y: ode_system(t, y, p_2D),
        t_span=(t_eval[0], t_eval[-1]),
        y0=[S0, D0],
        t_eval=t_eval,
        rtol=1e-9,
        atol=1e-12,
        method="RK45",
    )
    sol_3D = solve_ivp(
        fun=lambda t, y: ode_system_3species(t, y, p_3D),
        t_span=(t_eval[0], t_eval[-1]),
        y0=[S0, R0, D0],
        t_eval=t_eval,
        rtol=1e-9,
        atol=1e-12,
        method="RK45",
    )

    assert sol_2D.success
    assert sol_3D.success

    # The (S, D) dynamics are mathematically identical, so the only source of
    # divergence here is that the 2-D and 3-D RK45 runs take *different*
    # adaptive step sequences (because the 3-D state vector is one component
    # longer, the per-step error estimate differs). We therefore compare in
    # relative terms against RK45's rtol=1e-9: a 1e-7 relative ceiling leaves
    # two orders of magnitude of headroom for accumulated step error over the
    # 200-year integration.
    S_ref = np.max(np.abs(sol_2D.y[0]))
    D_ref = np.max(np.abs(sol_2D.y[1]))
    S_rel = float(np.max(np.abs(sol_3D.y[0] - sol_2D.y[0])) / max(S_ref, 1.0))
    D_rel = float(np.max(np.abs(sol_3D.y[2] - sol_2D.y[1])) / max(D_ref, 1.0))
    assert S_rel < 1e-7, f"S(t) projection drift {S_rel!r} exceeds RK45 budget"
    assert D_rel < 1e-7, f"D(t) projection drift {D_rel!r} exceeds RK45 budget"
