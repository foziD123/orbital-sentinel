"""Tests for the 3-species Jacobian, eigenvalue analysis and branch tracker.

Covers Step 4 of the 3-species engine extension. The headline assertions:

* shape and dtype of :func:`jacobian_3species`,
* at least four entries verified analytically against an independent
  expression with deliberately non-trivial parameter values,
* when ``R* = 0``, ``beta_SR = 0``, ``beta_RD = 0`` the (S, D) sub-block of
  the 3x3 Jacobian equals the 2-D Jacobian and the R-row leaves the
  (S, D) block decoupled,
* :func:`eigenvalue_analysis_3species` correctly classifies a synthetic
  matrix with a known complex pair and a known real eigenvalue,
* :func:`track_eigenvalues_3species` agrees with per-point analysis along a
  small synthetic branch.
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.eigenvalues import (
    eigenvalue_analysis_3species,
    jacobian,
    jacobian_3species,
    track_eigenvalues_3species,
)
from bifurcation_engine.src.shell_config import ShellConfig


def _shell_3D(**overrides: object) -> ShellConfig:
    base: dict[str, object] = {
        "shell_name": "Shell_test_3D",
        "altitude_km": 800.0,
        "L": 100.0,
        "delta_S": 0.005,
        "delta_D": 0.02,
        "beta": 1.5e-5,
        "gamma": 1.5e-7,
        "delta_R": 0.0125,
        "beta_SR": 3.0e-5,
        "beta_RD": 4.5e-5,
        "use_3species": True,
    }
    base.update(overrides)
    return ShellConfig(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and dtype
# ---------------------------------------------------------------------------


def test_jacobian_3species_shape_and_dtype() -> None:
    p = _shell_3D()
    J = jacobian_3species(1234.0, 567.0, 89.0, p)
    assert J.shape == (3, 3)
    assert J.dtype == np.float64


# ---------------------------------------------------------------------------
# Analytical verification of at least four Jacobian entries
# ---------------------------------------------------------------------------


def test_jacobian_3species_entry_J00_matches_analytical() -> None:
    p = _shell_3D()
    S, R, D = 1000.0, 200.0, 50.0
    J = jacobian_3species(S, R, D, p)
    expected = -p.delta_S - p.beta * D - p.beta_SR * R
    assert J[0, 0] == pytest.approx(expected, rel=1e-12)


def test_jacobian_3species_entry_J10_is_delta_S() -> None:
    """Independent of (S, R, D): R_dot has only the linear delta_S*S source."""
    p = _shell_3D()
    for S, R, D in [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1e6, 1e3, 1e4)]:
        J = jacobian_3species(S, R, D, p)
        assert J[1, 0] == pytest.approx(p.delta_S, rel=1e-12)


def test_jacobian_3species_entry_J21_matches_analytical() -> None:
    p = _shell_3D()
    S, R, D = 1000.0, 200.0, 50.0
    J = jacobian_3species(S, R, D, p)
    expected = p.beta_SR * S + p.beta_RD * D
    assert J[2, 1] == pytest.approx(expected, rel=1e-12)


def test_jacobian_3species_entry_J22_matches_analytical() -> None:
    p = _shell_3D()
    S, R, D = 1000.0, 200.0, 50.0
    J = jacobian_3species(S, R, D, p)
    expected = p.beta * S + p.beta_RD * R + 2.0 * p.gamma * D - p.delta_D
    assert J[2, 2] == pytest.approx(expected, rel=1e-12)


def test_jacobian_3species_entry_J11_matches_analytical() -> None:
    p = _shell_3D()
    S, R, D = 1000.0, 200.0, 50.0
    J = jacobian_3species(S, R, D, p)
    expected = -p.delta_R - p.beta_RD * D
    assert J[1, 1] == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------------------
# Reduces to the 2-D Jacobian
# ---------------------------------------------------------------------------


def test_jacobian_3species_reduces_to_2D_when_couplings_off() -> None:
    """With R* = 0, beta_SR = 0 and beta_RD = 0 the 3-species Jacobian's
    (S, D) sub-block must equal the 2-D Jacobian, AND the R-row must
    decouple the R degree of freedom from (S, D)."""
    p = ShellConfig(
        shell_name="reduced",
        altitude_km=800.0,
        L=100.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
        delta_R=0.012,   # any positive value; R-row uses it
        beta_SR=0.0,
        beta_RD=0.0,
        use_3species=False,  # avoid 3-species validation; logic is independent
    )
    S, D = 1500.0, 75.0
    J3 = jacobian_3species(S, R_star=0.0, D_star=D, params=p)
    J2 = jacobian(S, D, p)

    # (S, D) sub-block: rows 0 and 2, columns 0 and 2 of J3.
    sub = J3[np.ix_([0, 2], [0, 2])]
    np.testing.assert_allclose(sub, J2, rtol=1e-12, atol=1e-15)

    # R-row should decouple: J3[1,0] = delta_S (the inflow), J3[1,2] = 0
    # (no debris coupling), so the (S, R, D) system splits into
    # {S, D} <-> {R} along the R-axis.
    assert J3[0, 1] == pytest.approx(0.0, abs=1e-15)  # no S<-R coupling
    assert J3[2, 1] == pytest.approx(0.0, abs=1e-15)  # no D<-R coupling
    assert J3[1, 2] == pytest.approx(0.0, abs=1e-15)  # no R<-D coupling
    assert J3[1, 1] == pytest.approx(-p.delta_R, rel=1e-12)


# ---------------------------------------------------------------------------
# eigenvalue_analysis_3species classification on synthetic matrices
# ---------------------------------------------------------------------------


def test_eigenvalue_analysis_classifies_complex_pair_and_real_root() -> None:
    """Construct a Jacobian with a known complex pair and a known real
    eigenvalue by patching a ShellConfig such that the analytical structure
    yields a block-diagonal matrix:

        [[-a,  -b,   0],
         [ b,  -a,   0],
         [ 0,   0,  -c]]

    has eigenvalues {-a +- i*b, -c}. We achieve this with R*=0,
    beta_SR=0, and choosing parameters so that the (S, D) 2-D Jacobian
    has a complex pair while the R sub-block is the scalar -delta_R.
    """
    # Pick parameters where the 2-D (S, D) Jacobian at the chosen point has
    # discriminant < 0. Pick the generic case J=[[-a,-b],[b,-a]] manually.
    # Use the ShellConfig wiring for the rest.
    p = ShellConfig(
        shell_name="synthetic",
        altitude_km=800.0,
        L=1.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
        delta_R=0.013,
        beta_SR=0.0,
        beta_RD=0.0,
        use_3species=False,
    )
    # Choose (S, D) that puts the 2-D Jacobian close to the real-pair regime
    # but still in the complex-eigenvalue region. We brute-force a search
    # rather than solving inequalities by hand.
    found = False
    for D_try in np.linspace(100.0, 5000.0, 50):
        for S_try in np.linspace(100.0, 1500.0, 30):
            J3 = jacobian_3species(S_try, R_star=0.0, D_star=D_try, params=p)
            eigs = np.linalg.eigvals(J3)
            if np.max(np.abs(eigs.imag)) > 1e-8:
                S_star, D_star = S_try, D_try
                found = True
                break
        if found:
            break
    assert found, "Could not find a (S, D) with complex eigenvalues for the test"

    analysis = eigenvalue_analysis_3species(S_star, R_star=0.0, D_star=D_star, params=p)

    assert analysis["has_complex_pair"] is True
    assert isinstance(analysis["alpha_complex"], float)
    assert isinstance(analysis["omega_complex"], float)
    assert not np.isnan(analysis["alpha_complex"])
    assert analysis["omega_complex"] > 0.0
    # leading_alpha should be the max real part across all three eigenvalues.
    eigs = analysis["eigs"]
    expected_leading = float(np.max(np.real(eigs)))
    assert analysis["leading_alpha"] == pytest.approx(expected_leading, rel=1e-12)


def test_eigenvalue_analysis_returns_no_pair_for_pure_real_spectrum() -> None:
    """At ``R* = 0``, ``D* = 0`` and beta_SR = beta_RD = 0 the Jacobian is
    block-diagonal with three real eigenvalues -delta_S, -delta_R,
    -delta_D + beta*S, all real."""
    p = ShellConfig(
        shell_name="real_spec",
        altitude_km=800.0,
        L=1.0,
        delta_S=0.005,
        delta_D=0.02,
        beta=1.5e-5,
        gamma=1.5e-7,
        delta_R=0.012,
        beta_SR=0.0,
        beta_RD=0.0,
        use_3species=False,
    )
    analysis = eigenvalue_analysis_3species(
        S_star=200.0, R_star=0.0, D_star=0.0, params=p
    )
    assert analysis["has_complex_pair"] is False
    assert np.isnan(analysis["alpha_complex"])
    assert np.isnan(analysis["omega_complex"])
    assert np.isfinite(analysis["leading_alpha"])


# ---------------------------------------------------------------------------
# track_eigenvalues_3species
# ---------------------------------------------------------------------------


def test_track_eigenvalues_3species_matches_per_point_analysis() -> None:
    p = _shell_3D()

    L_arr = np.array([10.0, 20.0, 30.0, 40.0], dtype=float)
    S_arr = np.array([1000.0, 1100.0, 1200.0, 1300.0], dtype=float)
    R_arr = np.array([200.0, 220.0, 240.0, 260.0], dtype=float)
    D_arr = np.array([50.0, 75.0, 100.0, 125.0], dtype=float)

    branch = {"L": L_arr, "S_star": S_arr, "R_star": R_arr, "D_star": D_arr}
    track = track_eigenvalues_3species(branch, p)

    assert track["L"].shape == L_arr.shape
    for i in range(L_arr.size):
        a = eigenvalue_analysis_3species(
            float(S_arr[i]), float(R_arr[i]), float(D_arr[i]), p
        )
        assert track["leading_alpha"][i] == pytest.approx(
            a["leading_alpha"], rel=1e-12
        )
        assert track["has_complex_pair"][i] == bool(a["has_complex_pair"])
        if bool(a["has_complex_pair"]):
            assert track["alpha_complex"][i] == pytest.approx(
                a["alpha_complex"], rel=1e-12
            )
            assert track["omega_complex"][i] == pytest.approx(
                a["omega_complex"], rel=1e-12
            )

    # Aliases for direct consumption by detect_hopf.
    np.testing.assert_array_equal(track["alpha"], track["alpha_complex"])
    np.testing.assert_array_equal(track["omega"], track["omega_complex"])
    np.testing.assert_array_equal(track["is_complex"], track["has_complex_pair"])


def test_track_eigenvalues_3species_rejects_mismatched_shapes() -> None:
    p = _shell_3D()
    bad = {
        "L": np.array([1.0, 2.0]),
        "S_star": np.array([1.0, 2.0, 3.0]),
        "R_star": np.array([1.0, 2.0]),
        "D_star": np.array([1.0, 2.0]),
    }
    with pytest.raises(ValueError, match="same shape"):
        track_eigenvalues_3species(bad, p)
