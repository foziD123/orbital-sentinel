"""Tests for :class:`SplitDecayConfig` (Hopf-hunt experiment, additive).

These tests are completely additive: they only construct
:class:`SplitDecayConfig` instances and call :meth:`from_shell`. The 2-D
:class:`ShellConfig` and the existing 3-species pipeline are not modified
or imported in any code path that this test file triggers.
"""

from __future__ import annotations

import pytest

from bifurcation_engine.src.shell_config import ShellConfig
from bifurcation_engine.src.split_decay_config import (
    OUTFLOW_ABS_TOL,
    OUTFLOW_REL_TOL,
    SplitDecayConfig,
)


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
# Construction and basic invariants
# ---------------------------------------------------------------------------


def test_minimal_construction_succeeds() -> None:
    cfg = SplitDecayConfig(
        shell_name="Shell_B_800km",
        altitude_km=800.0,
        L=100.0,
        kappa_S=0.0025,
        rho_S=0.0025,
        delta_R=0.0125,
        delta_D=0.02,
        beta_SD=1.5e-5,
        beta_SR=3.0e-5,
        beta_RD=4.5e-5,
        gamma=1.5e-7,
    )
    assert cfg.delta_S == pytest.approx(0.005, rel=1e-12)
    assert cfg.eta_SD == 1.0
    assert cfg.eta_SR == 1.0
    assert cfg.eta_RD == 1.0


def test_effective_L_sweep_max_default() -> None:
    cfg = SplitDecayConfig(
        shell_name="Shell_B_800km",
        altitude_km=800.0,
        L=100.0,
        kappa_S=0.0025,
        rho_S=0.0025,
        delta_R=0.0125,
        delta_D=0.02,
        beta_SD=1.5e-5,
        beta_SR=3.0e-5,
        beta_RD=4.5e-5,
        gamma=1.5e-7,
    )
    assert cfg.effective_L_sweep_max == pytest.approx(1000.0, rel=1e-12)


def test_effective_L_sweep_max_falls_back_to_10_times_L() -> None:
    cfg = SplitDecayConfig(
        shell_name="X",
        altitude_km=800.0,
        L=42.0,
        kappa_S=0.001,
        rho_S=0.004,
        delta_R=0.012,
        delta_D=0.02,
        beta_SD=1e-5,
        beta_SR=2e-5,
        beta_RD=3e-5,
        gamma=1e-7,
    )
    assert cfg.effective_L_sweep_max == pytest.approx(420.0, rel=1e-12)


# ---------------------------------------------------------------------------
# Validation: positivity / ordering / yields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kappa", [0.0, -1e-5])
def test_kappa_S_must_be_strictly_positive(kappa: float) -> None:
    with pytest.raises(ValueError, match="kappa_S"):
        SplitDecayConfig(
            shell_name="X",
            altitude_km=800.0,
            L=100.0,
            kappa_S=kappa,
            rho_S=0.005,
            delta_R=0.012,
            delta_D=0.02,
            beta_SD=1e-5,
            beta_SR=2e-5,
            beta_RD=3e-5,
            gamma=1e-7,
        )


@pytest.mark.parametrize("rho", [0.0, -1e-5])
def test_rho_S_must_be_strictly_positive(rho: float) -> None:
    with pytest.raises(ValueError, match="rho_S"):
        SplitDecayConfig(
            shell_name="X",
            altitude_km=800.0,
            L=100.0,
            kappa_S=0.005,
            rho_S=rho,
            delta_R=0.012,
            delta_D=0.02,
            beta_SD=1e-5,
            beta_SR=2e-5,
            beta_RD=3e-5,
            gamma=1e-7,
        )


def test_delta_R_must_exceed_delta_S() -> None:
    with pytest.raises(ValueError, match="delta_R"):
        SplitDecayConfig(
            shell_name="X",
            altitude_km=800.0,
            L=100.0,
            kappa_S=0.005,
            rho_S=0.005,   # delta_S = 0.010
            delta_R=0.005, # too small
            delta_D=0.02,
            beta_SD=1e-5,
            beta_SR=2e-5,
            beta_RD=3e-5,
            gamma=1e-7,
        )


def test_delta_D_must_exceed_delta_R() -> None:
    with pytest.raises(ValueError, match="delta_D"):
        SplitDecayConfig(
            shell_name="X",
            altitude_km=800.0,
            L=100.0,
            kappa_S=0.0025,
            rho_S=0.0025,
            delta_R=0.02,  # equal to delta_D below
            delta_D=0.02,
            beta_SD=1e-5,
            beta_SR=2e-5,
            beta_RD=3e-5,
            gamma=1e-7,
        )


@pytest.mark.parametrize(
    "field,value",
    [("beta_SD", 0.0), ("beta_SR", 0.0), ("beta_RD", 0.0)],
)
def test_collision_rates_must_be_strictly_positive(field: str, value: float) -> None:
    base = dict(
        shell_name="X",
        altitude_km=800.0,
        L=100.0,
        kappa_S=0.0025,
        rho_S=0.0025,
        delta_R=0.0125,
        delta_D=0.02,
        beta_SD=1e-5,
        beta_SR=2e-5,
        beta_RD=3e-5,
        gamma=1e-7,
    )
    base[field] = value
    with pytest.raises(ValueError, match=field):
        SplitDecayConfig(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("eta_field", ["eta_SD", "eta_SR", "eta_RD"])
def test_eta_below_one_is_rejected(eta_field: str) -> None:
    base = dict(
        shell_name="X",
        altitude_km=800.0,
        L=100.0,
        kappa_S=0.0025,
        rho_S=0.0025,
        delta_R=0.0125,
        delta_D=0.02,
        beta_SD=1e-5,
        beta_SR=2e-5,
        beta_RD=3e-5,
        gamma=1e-7,
    )
    base[eta_field] = 0.99
    with pytest.raises(ValueError, match=eta_field):
        SplitDecayConfig(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# from_shell helper
# ---------------------------------------------------------------------------


def test_from_shell_default_recipe_preserves_outflow_and_inherits_fields() -> None:
    shell = _shell_B()
    cfg = SplitDecayConfig.from_shell(shell, rho_fraction=0.5)

    assert cfg.shell_name == shell.shell_name
    assert cfg.altitude_km == pytest.approx(shell.altitude_km, rel=1e-12)
    assert cfg.L == pytest.approx(shell.L, rel=1e-12)
    assert cfg.beta_SD == pytest.approx(shell.beta, rel=1e-12)
    assert cfg.gamma == pytest.approx(shell.gamma, rel=1e-12)
    assert cfg.L_sweep_max == pytest.approx(shell.L_sweep_max, rel=1e-12)

    # Conservation: kappa_S + rho_S = delta_S to within tolerance.
    residual = cfg.conservation_residual(shell.delta_S)
    tol = max(OUTFLOW_ABS_TOL, OUTFLOW_REL_TOL * shell.delta_S)
    assert residual <= tol

    # Recipe matches the existing 3-species pipeline.
    assert cfg.delta_R == pytest.approx(0.5 * (shell.delta_S + shell.delta_D), rel=1e-12)
    assert cfg.beta_SR == pytest.approx(2.0 * shell.beta, rel=1e-12)
    assert cfg.beta_RD == pytest.approx(3.0 * shell.beta, rel=1e-12)


def test_from_shell_rho_fraction_outside_open_unit_interval_rejected() -> None:
    shell = _shell_B()
    with pytest.raises(ValueError, match="rho_fraction"):
        SplitDecayConfig.from_shell(shell, rho_fraction=0.0)
    with pytest.raises(ValueError, match="rho_fraction"):
        SplitDecayConfig.from_shell(shell, rho_fraction=1.0)
    with pytest.raises(ValueError, match="rho_fraction"):
        SplitDecayConfig.from_shell(shell, rho_fraction=-0.1)
    with pytest.raises(ValueError, match="rho_fraction"):
        SplitDecayConfig.from_shell(shell, rho_fraction=1.1)


def test_from_shell_gamma_multiplier_scales_gamma() -> None:
    shell = _shell_B()
    cfg = SplitDecayConfig.from_shell(shell, rho_fraction=0.3, gamma_multiplier=10.0)
    assert cfg.gamma == pytest.approx(10.0 * shell.gamma, rel=1e-12)


def test_from_shell_eta_overrides_propagate() -> None:
    shell = _shell_B()
    cfg = SplitDecayConfig.from_shell(
        shell, rho_fraction=0.5, eta_SD=1.0, eta_SR=2.0, eta_RD=5.0
    )
    assert cfg.eta_SD == 1.0
    assert cfg.eta_SR == 2.0
    assert cfg.eta_RD == 5.0


def test_from_shell_split_is_genuinely_two_sided() -> None:
    """Both sides of the split are strictly positive for any 0 < rho_fraction < 1."""
    shell = _shell_B()
    for rho in [1e-3, 0.1, 0.5, 0.9, 1 - 1e-3]:
        cfg = SplitDecayConfig.from_shell(shell, rho_fraction=rho)
        assert cfg.kappa_S > 0.0
        assert cfg.rho_S > 0.0
        assert cfg.delta_S == pytest.approx(shell.delta_S, rel=1e-12)
