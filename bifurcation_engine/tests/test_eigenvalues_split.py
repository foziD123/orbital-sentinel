"""Tests for the split-decay Jacobian and eigenvalue tracker.

Headline assertions (every Jacobian entry independently verified):

* shape and dtype of :func:`jacobian_split`,
* each of the 9 entries verified analytically against an independent
  expression with deliberately non-trivial parameter values (the
  pre-implementation gate: the Jacobian closed form was approved before
  any code was written, so each entry gets its own assertion),
* :func:`eigenvalue_analysis_split` correctly reports leading_alpha and
  trace,
* :func:`track_eigenvalues_split` agrees with per-point analysis along a
  small synthetic branch and exposes ``alpha`` / ``omega`` / ``is_complex``
  aliases,
* :func:`detect_hopf` from the existing module accepts the alias dict
  unchanged (this is the cross-pipeline reuse claim).
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.eigenvalues_split import (
    eigenvalue_analysis_split,
    jacobian_split,
    track_eigenvalues_split,
)
from bifurcation_engine.src.hopf_detector import detect_hopf
from bifurcation_engine.src.shell_config import ShellConfig
from bifurcation_engine.src.split_decay_config import SplitDecayConfig


def _split_p() -> SplitDecayConfig:
    base = ShellConfig(
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
    return SplitDecayConfig.from_shell(
        base, rho_fraction=0.4, eta_SD=1.0, eta_SR=2.0, eta_RD=5.0
    )


# ---------------------------------------------------------------------------
# Shape and dtype
# ---------------------------------------------------------------------------


def test_jacobian_split_shape_and_dtype() -> None:
    p = _split_p()
    J = jacobian_split(1234.0, 567.0, 89.0, p)
    assert J.shape == (3, 3)
    assert J.dtype == np.float64


# ---------------------------------------------------------------------------
# Entry-by-entry verification of every Jacobian element
# ---------------------------------------------------------------------------


def _state() -> tuple[float, float, float]:
    return 1000.0, 200.0, 50.0


def test_jacobian_split_J00() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    expected = -p.kappa_S - p.rho_S - p.beta_SD * D - p.beta_SR * R
    assert J[0, 0] == pytest.approx(expected, rel=1e-12)
    # Equivalent simplification using delta_S = kappa_S + rho_S.
    assert J[0, 0] == pytest.approx(
        -p.delta_S - p.beta_SD * D - p.beta_SR * R, rel=1e-12
    )


def test_jacobian_split_J01() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    assert J[0, 1] == pytest.approx(-p.beta_SR * S, rel=1e-12)


def test_jacobian_split_J02() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    assert J[0, 2] == pytest.approx(-p.beta_SD * S, rel=1e-12)


def test_jacobian_split_J10() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    assert J[1, 0] == pytest.approx(p.rho_S - p.beta_SR * R, rel=1e-12)


def test_jacobian_split_J11() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    expected = -p.delta_R - p.beta_RD * D - p.beta_SR * S
    assert J[1, 1] == pytest.approx(expected, rel=1e-12)


def test_jacobian_split_J12() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    assert J[1, 2] == pytest.approx(-p.beta_RD * R, rel=1e-12)


def test_jacobian_split_J20() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    expected = p.eta_SD * p.beta_SD * D + p.eta_SR * p.beta_SR * R
    assert J[2, 0] == pytest.approx(expected, rel=1e-12)


def test_jacobian_split_J21() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    expected = p.eta_SR * p.beta_SR * S + p.eta_RD * p.beta_RD * D
    assert J[2, 1] == pytest.approx(expected, rel=1e-12)


def test_jacobian_split_J22() -> None:
    p = _split_p()
    S, R, D = _state()
    J = jacobian_split(S, R, D, p)
    expected = (
        p.eta_SD * p.beta_SD * S
        + p.eta_RD * p.beta_RD * R
        + 2.0 * p.gamma * D
        - p.delta_D
    )
    assert J[2, 2] == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# Trace identity
# ---------------------------------------------------------------------------


def test_jacobian_split_trace_matches_inequality_form() -> None:
    """The trace simplifies to:

        tr = -(delta_S + delta_R + delta_D)
             + beta_SD * (eta_SD * S - D)
             + beta_RD * (eta_RD * R - D)
             - beta_SR * (R + S)
             + 2 * gamma * D
    """
    p = _split_p()
    S, R, D = 1500.0, 300.0, 75.0
    J = jacobian_split(S, R, D, p)
    raw_trace = float(np.trace(J))
    closed = (
        -(p.delta_S + p.delta_R + p.delta_D)
        + p.beta_SD * (p.eta_SD * S - D)
        + p.beta_RD * (p.eta_RD * R - D)
        - p.beta_SR * (R + S)
        + 2.0 * p.gamma * D
    )
    assert raw_trace == pytest.approx(closed, rel=1e-12)


# ---------------------------------------------------------------------------
# eigenvalue_analysis_split
# ---------------------------------------------------------------------------


def test_eigenvalue_analysis_returns_pure_real_spectrum_when_decoupled() -> None:
    """At ``S=R=D=0`` and a fully-decoupled-style state the Jacobian is
    block-triangular with three real eigenvalues, so the analyser must
    flag no complex pair."""
    p = _split_p()
    a = eigenvalue_analysis_split(0.0, 0.0, 0.0, p)
    assert a["has_complex_pair"] is False
    assert np.isnan(a["alpha_complex"])
    assert np.isnan(a["omega_complex"])
    assert np.isfinite(a["leading_alpha"])
    assert np.isfinite(a["trace"])
    # Expected diagonal eigenvalues at the origin: -delta_S, -delta_R, -delta_D.
    expected_eigs = sorted([-p.delta_S, -p.delta_R, -p.delta_D])
    assert a["real_parts"][0] == pytest.approx(expected_eigs[0], rel=1e-12)
    assert a["real_parts"][1] == pytest.approx(expected_eigs[1], rel=1e-12)
    assert a["real_parts"][2] == pytest.approx(expected_eigs[2], rel=1e-12)


def test_eigenvalue_analysis_finds_complex_pair_when_present() -> None:
    """Sweep (S, D) until a complex pair appears, then assert the analyser
    flags it correctly."""
    p = _split_p()
    found = False
    S_star = D_star = 0.0
    for D_try in np.linspace(50.0, 5000.0, 30):
        for S_try in np.linspace(50.0, 2000.0, 30):
            J = jacobian_split(S_try, 0.0, D_try, p)
            eigs = np.linalg.eigvals(J)
            if float(np.max(np.abs(eigs.imag))) > 1e-6:
                S_star, D_star = S_try, D_try
                found = True
                break
        if found:
            break
    assert found, "Could not find a (S, D) with complex eigenvalues for the test"

    a = eigenvalue_analysis_split(S_star, 0.0, D_star, p)
    assert a["has_complex_pair"] is True
    assert isinstance(a["alpha_complex"], float)
    assert a["omega_complex"] > 0.0


# ---------------------------------------------------------------------------
# track_eigenvalues_split
# ---------------------------------------------------------------------------


def test_track_eigenvalues_split_matches_per_point_analysis() -> None:
    p = _split_p()
    L = np.array([10.0, 20.0, 30.0, 40.0])
    S = np.array([1000.0, 1100.0, 1200.0, 1300.0])
    R = np.array([200.0, 220.0, 240.0, 260.0])
    D = np.array([50.0, 75.0, 100.0, 125.0])

    branch = {"L": L, "S_star": S, "R_star": R, "D_star": D}
    track = track_eigenvalues_split(branch, p)

    for i in range(L.size):
        a = eigenvalue_analysis_split(float(S[i]), float(R[i]), float(D[i]), p)
        assert track["leading_alpha"][i] == pytest.approx(
            a["leading_alpha"], rel=1e-12
        )
        assert track["trace"][i] == pytest.approx(a["trace"], rel=1e-12)
        assert track["has_complex_pair"][i] == bool(a["has_complex_pair"])

    np.testing.assert_array_equal(track["alpha"], track["alpha_complex"])
    np.testing.assert_array_equal(track["omega"], track["omega_complex"])
    np.testing.assert_array_equal(track["is_complex"], track["has_complex_pair"])


def test_track_eigenvalues_split_rejects_mismatched_shapes() -> None:
    p = _split_p()
    bad = {
        "L": np.array([1.0, 2.0]),
        "S_star": np.array([1.0, 2.0, 3.0]),
        "R_star": np.array([1.0, 2.0]),
        "D_star": np.array([1.0, 2.0]),
    }
    with pytest.raises(ValueError, match="same shape"):
        track_eigenvalues_split(bad, p)


# ---------------------------------------------------------------------------
# Cross-pipeline reuse: detect_hopf consumes the alias dict
# ---------------------------------------------------------------------------


def test_detect_hopf_runs_unchanged_on_split_track_dict() -> None:
    """Smoke test that the alias keys make the existing detector usable
    without modification — the experiment doesn't need a Hopf detector
    variant."""
    p = _split_p()
    L = np.linspace(1.0, 200.0, 20)
    S = np.linspace(500.0, 1500.0, 20)
    R = np.linspace(100.0, 300.0, 20)
    D = np.linspace(10.0, 100.0, 20)
    branch = {"L": L, "S_star": S, "R_star": R, "D_star": D}
    track = track_eigenvalues_split(branch, p)

    # detect_hopf should run and return a HopfResult-like dataclass
    # regardless of whether a Hopf is actually present.
    result = detect_hopf(track["L"], track["alpha"], track["omega"])
    assert hasattr(result, "found")
    assert isinstance(result.found, bool)
