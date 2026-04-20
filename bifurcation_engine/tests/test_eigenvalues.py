"""Tests for :mod:`bifurcation_engine.src.eigenvalues` (Task 4).

Covers the Jacobian form from the PDF, the ``(alpha, omega)`` convention,
``track_eigenvalues`` over a continuation sweep, and VALIDATION.md T5.1
(analytical eigenvalues at the clean-orbit fixed point to 1e-10).
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.eigenvalues import (
    eigenvalue_pair,
    jacobian,
    track_eigenvalues,
)
from bifurcation_engine.src.fixed_points import (
    clean_orbit_fixed_point,
    continuation_sweep,
)
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


# ---------------------------------------------------------------------------
# Jacobian — matches the PDF form element-by-element
# ---------------------------------------------------------------------------


def test_jacobian_shape_and_dtype() -> None:
    J = jacobian(100.0, 50.0, _shell_B())
    assert J.shape == (2, 2)
    assert J.dtype == np.float64


def test_jacobian_matches_pdf_element_by_element() -> None:
    params = _shell_B()
    S, D = 1234.5, 678.9
    J = jacobian(S, D, params)
    assert J[0, 0] == pytest.approx(-params.delta_S - params.beta * D)
    assert J[0, 1] == pytest.approx(-params.beta * S)
    assert J[1, 0] == pytest.approx(params.beta * D)
    assert J[1, 1] == pytest.approx(
        params.beta * S + 2.0 * params.gamma * D - params.delta_D
    )


def test_jacobian_at_clean_orbit_is_triangular() -> None:
    """At D*=0 the lower-left entry must be exactly zero, matching T5.1."""
    params = _shell_B()
    S_star, _ = clean_orbit_fixed_point(params)
    J = jacobian(S_star, 0.0, params)
    assert J[1, 0] == 0.0
    assert J[0, 0] == pytest.approx(-params.delta_S)
    assert J[1, 1] == pytest.approx(params.beta * S_star - params.delta_D)


# ---------------------------------------------------------------------------
# T5.1 — analytical eigenvalues at clean-orbit fixed point to 1e-10
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        _shell_B(L=0.0),
        _shell_B(L=10.0),
        _shell_B(L=100.0),
        _shell_B(L=500.0),
        _shell_B(L=2000.0),
        ShellConfig(
            shell_name="Shell_A_600km",
            altitude_km=600.0,
            L=200.0,
            delta_S=0.02,
            delta_D=0.10,
            beta=1.0e-5,
            gamma=1.0e-7,
        ),
    ],
)
def test_T5_1_clean_orbit_eigenvalues_match_analytical_form(
    params: ShellConfig,
) -> None:
    """eigenvalues at (L/delta_S, 0) are exactly -delta_S and beta*S* - delta_D."""
    S_star, D_star = clean_orbit_fixed_point(params)
    J = jacobian(S_star, D_star, params)
    computed = np.sort(np.linalg.eigvals(J).real)

    expected = np.sort(
        np.array(
            [-params.delta_S, params.beta * S_star - params.delta_D],
            dtype=float,
        )
    )
    np.testing.assert_allclose(computed, expected, atol=1e-10)

    # Both eigenvalues are real: omega from our helper must be zero.
    alpha, omega = eigenvalue_pair(S_star, D_star, params)
    assert omega == 0.0
    assert alpha == pytest.approx(float(max(expected)), abs=1e-10)


# ---------------------------------------------------------------------------
# eigenvalue_pair — complex vs real branching
# ---------------------------------------------------------------------------


def test_eigenvalue_pair_real_stable_case() -> None:
    """Pure stable node from the lower Case-2 branch of Shell_B at L=300."""
    params = _shell_B(L=300.0)
    # Lower branch D* ~ 16.8k, S* ~ 1165 (computed in Task 3 notes).
    S_star, D_star = 1164.68, 16885.03
    alpha, omega = eigenvalue_pair(S_star, D_star, params)
    # Both eigenvalues negative → stable node, omega is 0.
    assert omega == 0.0
    assert alpha < 0.0


def test_eigenvalue_pair_complex_pair_has_shared_real_part() -> None:
    """Construct a Jacobian with known complex eigenvalues and check both parts.

    Chosen so ``4*det - trace**2`` is comfortably positive (around 0.3) —
    well away from the discriminant=0 boundary where floating-point noise
    would dominate.
    """
    params = ShellConfig(
        shell_name="Synthetic_complex",
        altitude_km=600.0,
        L=1.0,
        delta_S=0.1,
        delta_D=0.2,
        beta=1.0,
        gamma=0.01,
    )
    S_star, D_star = 1.0, 1.0
    J = jacobian(S_star, D_star, params)
    tau = float(np.trace(J))
    det = float(np.linalg.det(J))
    disc = tau * tau - 4.0 * det
    assert disc < -0.25, (
        f"Test precondition: eigenvalues must be comfortably complex "
        f"(disc = {disc:.4f})"
    )

    alpha, omega = eigenvalue_pair(S_star, D_star, params)
    assert alpha == pytest.approx(0.5 * tau)
    expected_omega = 0.5 * (-disc) ** 0.5
    assert omega == pytest.approx(expected_omega)


# ---------------------------------------------------------------------------
# track_eigenvalues — array wiring
# ---------------------------------------------------------------------------


def test_track_eigenvalues_structure() -> None:
    params = _shell_B()
    sweep = continuation_sweep(params, np.linspace(0.0, 500.0, 51))
    tracked = track_eigenvalues(sweep, params)

    assert set(tracked.keys()) >= {"L", "alpha", "omega", "is_complex"}
    assert tracked["L"].shape == sweep["L"].shape
    assert tracked["alpha"].shape == sweep["L"].shape
    assert tracked["omega"].shape == sweep["L"].shape
    assert tracked["is_complex"].dtype == bool
    np.testing.assert_array_equal(tracked["is_complex"], tracked["omega"] > 0.0)


def test_track_eigenvalues_clean_orbit_is_real_throughout() -> None:
    """Case-1 entries in the sweep must never produce a complex pair (T5.1)."""
    params = _shell_B()
    sweep = continuation_sweep(params, np.linspace(0.0, 1000.0, 51))
    tracked = track_eigenvalues(sweep, params)

    case1_mask = tracked["branch"] == 1
    assert case1_mask.sum() > 0
    assert not np.any(tracked["is_complex"][case1_mask])
    assert np.all(tracked["omega"][case1_mask] == 0.0)
