"""Tests for the split-decay 3-species ODE in :mod:`model_split`.

Headline assertions:

* term-by-term value of each ``*_dot_split`` at a non-trivial state,
* equivalence with the existing 3-species ODE in the boundary limit
  ``kappa_S -> 0``, ``rho_S -> delta_S``, ``eta_SD = eta_SR = eta_RD = 1``
  (this is the rigorous reduction to the asymmetric 3-species model
  ``r_dot_3species`` *modulo* the corrected ``-beta_SR*S*R`` sink — i.e.
  equivalence holds for ``S_dot`` and ``D_dot`` term-by-term, and ``R_dot``
  differs by exactly ``-beta_SR*S*R``),
* :func:`ode_system_split` returns the right shape and dtype.
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.model import (
    d_dot_3species,
    r_dot_3species,
    s_dot_3species,
)
from bifurcation_engine.src.model_split import (
    d_dot_split,
    ode_system_split,
    r_dot_split,
    s_dot_split,
)
from bifurcation_engine.src.shell_config import ShellConfig
from bifurcation_engine.src.split_decay_config import SplitDecayConfig


def _shell_3species() -> ShellConfig:
    """A shell that is valid for both the 3-species ODE and from_shell()."""
    return ShellConfig(
        shell_name="Shell_B_test",
        altitude_km=800.0,
        L=100.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
        delta_R=0.0125,
        beta_SR=3.0e-5,
        beta_RD=4.5e-5,
        use_3species=True,
    )


def _split_balanced() -> SplitDecayConfig:
    """50/50 split with baseline (eta=1) yields, used for term-by-term checks."""
    return SplitDecayConfig.from_shell(_shell_3species(), rho_fraction=0.5)


# ---------------------------------------------------------------------------
# Term-by-term values
# ---------------------------------------------------------------------------


def test_s_dot_split_matches_closed_form() -> None:
    p = _split_balanced()
    S, R, D = 1000.0, 200.0, 50.0
    expected = (
        p.L
        - p.kappa_S * S
        - p.rho_S * S
        - p.beta_SD * S * D
        - p.beta_SR * S * R
    )
    assert s_dot_split(S, R, D, p) == pytest.approx(expected, rel=1e-12)


def test_r_dot_split_matches_closed_form_includes_beta_SR_sink() -> None:
    p = _split_balanced()
    S, R, D = 1000.0, 200.0, 50.0
    expected = (
        p.rho_S * S
        - p.delta_R * R
        - p.beta_RD * R * D
        - p.beta_SR * S * R
    )
    assert r_dot_split(S, R, D, p) == pytest.approx(expected, rel=1e-12)


def test_d_dot_split_matches_closed_form_with_baseline_eta() -> None:
    p = _split_balanced()
    S, R, D = 1000.0, 200.0, 50.0
    expected = (
        p.eta_SD * p.beta_SD * S * D
        + p.eta_SR * p.beta_SR * S * R
        + p.eta_RD * p.beta_RD * R * D
        + p.gamma * D * D
        - p.delta_D * D
    )
    assert d_dot_split(S, R, D, p) == pytest.approx(expected, rel=1e-12)


def test_d_dot_split_eta_multipliers_scale_only_collision_terms() -> None:
    base = _shell_3species()
    p = SplitDecayConfig.from_shell(
        base, rho_fraction=0.5, eta_SD=1.0, eta_SR=2.0, eta_RD=5.0
    )
    S, R, D = 1000.0, 200.0, 50.0
    val = d_dot_split(S, R, D, p)
    expected = (
        1.0 * p.beta_SD * S * D
        + 2.0 * p.beta_SR * S * R
        + 5.0 * p.beta_RD * R * D
        + p.gamma * D * D
        - p.delta_D * D
    )
    assert val == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# Equivalence in the boundary limit
# ---------------------------------------------------------------------------


def test_split_reduces_to_3species_in_no_deorbit_limit() -> None:
    """In the limit ``kappa_S -> 0``, ``rho_S -> delta_S``, ``eta = 1``:

    * ``s_dot_split == s_dot_3species`` exactly.
    * ``d_dot_split == d_dot_3species`` exactly (the eta=1 baseline reduces
      the channel-by-channel debris source to the existing one).
    * ``r_dot_split == r_dot_3species - beta_SR*S*R`` — i.e. the split model
      differs from the existing 3-species model by exactly the
      ``-beta_SR*S*R`` correction documented in CLAUDE.md as the
      'deliberate asymmetry'. This is the experiment's intended
      modelling change.
    """
    base = _shell_3species()
    # Approach the boundary; use a very small kappa to stay inside validation.
    rho_fraction = 1.0 - 1e-9
    p_split = SplitDecayConfig.from_shell(
        base,
        rho_fraction=rho_fraction,
        eta_SD=1.0,
        eta_SR=1.0,
        eta_RD=1.0,
    )

    S, R, D = 1234.0, 321.0, 99.0

    s_3 = s_dot_3species(S, R, D, base)
    d_3 = d_dot_3species(S, R, D, base)
    r_3 = r_dot_3species(S, R, D, base)

    assert s_dot_split(S, R, D, p_split) == pytest.approx(s_3, rel=1e-7)
    assert d_dot_split(S, R, D, p_split) == pytest.approx(d_3, rel=1e-12)

    expected_r = r_3 - base.beta_SR * S * R
    assert r_dot_split(S, R, D, p_split) == pytest.approx(expected_r, rel=1e-7)


# ---------------------------------------------------------------------------
# ode_system_split contract
# ---------------------------------------------------------------------------


def test_ode_system_split_shape_and_dtype() -> None:
    p = _split_balanced()
    out = ode_system_split(0.0, np.array([1000.0, 100.0, 50.0]), p)
    assert out.shape == (3,)
    assert out.dtype == np.float64


def test_ode_system_split_matches_individual_derivatives() -> None:
    p = _split_balanced()
    S, R, D = 1500.0, 250.0, 75.0
    out = ode_system_split(0.0, [S, R, D], p)
    assert out[0] == pytest.approx(s_dot_split(S, R, D, p), rel=1e-12)
    assert out[1] == pytest.approx(r_dot_split(S, R, D, p), rel=1e-12)
    assert out[2] == pytest.approx(d_dot_split(S, R, D, p), rel=1e-12)


def test_ode_system_split_is_autonomous_in_t() -> None:
    p = _split_balanced()
    state = np.array([1000.0, 200.0, 50.0])
    a = ode_system_split(0.0, state, p)
    b = ode_system_split(1.234e7, state, p)
    np.testing.assert_array_equal(a, b)
