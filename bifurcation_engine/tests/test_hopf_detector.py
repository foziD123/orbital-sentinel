"""Tests for :mod:`bifurcation_engine.src.hopf_detector` (Task 5).

Covers VALIDATION.md T3.1-T3.5 plus a few additional sanity checks for the
grazing-contact and mixed-sign edge cases that the detector needs to handle
honestly (the three non-Hopf outcomes are all valid scientific results).
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import (
    FoldResult,
    HopfResult,
    detect_fold,
    detect_hopf,
)
from bifurcation_engine.src.shell_config import ShellConfig, default_shells


# ---------------------------------------------------------------------------
# T3.1 — no complex eigenvalues anywhere
# ---------------------------------------------------------------------------


def test_T3_1_no_complex_eigenvalues() -> None:
    L = np.linspace(0.0, 100.0, 50)
    alpha = -np.linspace(0.5, 0.1, 50)  # real, negative
    omega = np.zeros_like(L)

    result = detect_hopf(L, alpha, omega)

    assert isinstance(result, HopfResult)
    assert result.found is False
    assert result.outcome == "no_complex_eigenvalues"
    assert result.L_c is None
    assert result.alpha_at_Lc is None
    assert result.omega_at_Lc is None


# ---------------------------------------------------------------------------
# T3.2 — complex eigenvalues but alpha never crosses zero
# ---------------------------------------------------------------------------


def test_T3_2_complex_but_no_crossing_stable_spiral() -> None:
    L = np.linspace(0.0, 100.0, 50)
    alpha = -np.linspace(0.5, 0.1, 50)  # always negative
    omega = np.ones_like(L) * 0.3

    result = detect_hopf(L, alpha, omega)

    assert result.found is False
    assert result.outcome == "complex_no_crossing"
    assert result.L_c is None


def test_complex_but_no_crossing_unstable_throughout() -> None:
    L = np.linspace(0.0, 100.0, 50)
    alpha = np.linspace(0.1, 0.5, 50)  # always positive
    omega = np.ones_like(L) * 0.3

    result = detect_hopf(L, alpha, omega)

    assert result.found is False
    assert result.outcome == "unstable_throughout"
    assert result.L_c is None


# ---------------------------------------------------------------------------
# T3.3 — genuine Hopf: alpha crosses zero with omega nonzero
# ---------------------------------------------------------------------------


def test_T3_3_genuine_hopf_crossing() -> None:
    L = np.linspace(0.0, 100.0, 200)
    alpha = np.linspace(-0.5, 0.5, 200)
    omega = np.ones_like(L)

    result = detect_hopf(L, alpha, omega)

    assert result.found is True
    assert result.outcome == "hopf_detected"
    assert result.L_c is not None
    assert abs(result.L_c - 50.0) < 1.0
    assert result.dalpha_dL_at_Lc is not None
    assert result.dalpha_dL_at_Lc > 0.0
    assert result.omega_at_Lc is not None
    assert result.omega_at_Lc == pytest.approx(1.0, rel=1e-3)


def test_genuine_hopf_descending() -> None:
    """alpha going positive -> negative is still a valid Hopf (negative slope)."""
    L = np.linspace(0.0, 100.0, 200)
    alpha = np.linspace(0.5, -0.5, 200)
    omega = np.ones_like(L)

    result = detect_hopf(L, alpha, omega)

    assert result.found is True
    assert result.outcome == "hopf_detected"
    assert result.dalpha_dL_at_Lc is not None
    assert result.dalpha_dL_at_Lc < 0.0


# ---------------------------------------------------------------------------
# T3.4 — L_c interpolation accuracy
# ---------------------------------------------------------------------------


def test_T3_4_interpolation_accuracy_at_37_5() -> None:
    """alpha crosses zero at exactly L=37.5 by construction."""
    L = np.linspace(0.0, 100.0, 200)
    alpha = 0.1 * (L - 37.5)
    omega = np.ones_like(L) * 0.7

    result = detect_hopf(L, alpha, omega)

    assert result.found is True
    assert result.L_c is not None
    assert abs(result.L_c - 37.5) < 0.5


@pytest.mark.parametrize("true_Lc", [5.0, 12.3, 37.5, 83.7, 99.0])
def test_interpolation_accuracy_sweep(true_Lc: float) -> None:
    L = np.linspace(0.0, 100.0, 300)
    alpha = 0.05 * (L - true_Lc)
    omega = np.ones_like(L) * 0.5

    result = detect_hopf(L, alpha, omega)

    assert result.found is True
    assert result.L_c is not None
    assert abs(result.L_c - true_Lc) < 0.5


# ---------------------------------------------------------------------------
# T3.5 — HopfResult is complete when found=True
# ---------------------------------------------------------------------------


def test_T3_5_hopf_result_is_complete_when_found() -> None:
    L = np.linspace(0.0, 100.0, 200)
    alpha = np.linspace(-0.5, 0.5, 200)
    omega = np.ones_like(L) * 0.8

    result = detect_hopf(L, alpha, omega)

    assert result.found is True
    assert result.L_c is not None
    assert result.omega_at_Lc is not None
    assert result.dalpha_dL_at_Lc is not None
    assert result.alpha_at_Lc is not None
    assert result.description is not None and len(result.description) > 0
    assert result.outcome is not None and len(result.outcome) > 0


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


def test_crossing_inside_real_region_is_not_hopf() -> None:
    """alpha changes sign, but omega == 0 at both sides of the step."""
    L = np.linspace(0.0, 100.0, 50)
    alpha = np.linspace(-0.5, 0.5, 50)
    omega = np.zeros_like(L)

    result = detect_hopf(L, alpha, omega)

    assert result.found is False
    assert result.outcome == "no_complex_eigenvalues"


def test_mixed_complex_region_with_alpha_sign_change_across_gap() -> None:
    """alpha changes sign only across a segment where omega returned to 0."""
    n = 50
    L = np.linspace(0.0, 100.0, n)
    alpha = np.linspace(-0.5, 0.5, n)
    omega = np.ones_like(L) * 0.3
    # Punch a hole in the complex region around the zero crossing.
    zero_idx = int(np.argmin(np.abs(alpha)))
    omega[zero_idx - 1 : zero_idx + 2] = 0.0

    result = detect_hopf(L, alpha, omega)

    assert result.found is False
    assert result.outcome == "complex_no_crossing"


def test_input_validation_raises_on_mismatched_shapes() -> None:
    L = np.linspace(0.0, 100.0, 10)
    alpha = np.zeros(9)
    omega = np.zeros(10)
    with pytest.raises(ValueError, match="same shape"):
        detect_hopf(L, alpha, omega)


def test_input_validation_raises_on_non_monotone_L() -> None:
    L = np.array([0.0, 10.0, 5.0, 20.0])
    alpha = np.zeros_like(L)
    omega = np.zeros_like(L)
    with pytest.raises(ValueError, match="monotonically"):
        detect_hopf(L, alpha, omega)


# ===========================================================================
# detect_fold
# ===========================================================================


def _shell_B(**overrides: float) -> ShellConfig:
    base = dict(
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
    base.update(overrides)
    return ShellConfig(**base)  # type: ignore[arg-type]


def _expected_fold(params: ShellConfig) -> tuple[float, float, float]:
    """Return closed-form (L_fold, S_fold, D_fold) for cross-checking."""
    a = params.beta * params.gamma
    b = params.delta_S * params.gamma - params.beta * params.delta_D
    D_fold = -b / (2.0 * a)
    S_fold = (params.delta_D - params.gamma * D_fold) / params.beta
    num = (params.delta_S * params.gamma + params.beta * params.delta_D) ** 2
    den = 4.0 * params.beta ** 2 * params.gamma
    L_fold = num / den
    return L_fold, S_fold, D_fold


def test_detect_fold_returns_fold_result() -> None:
    shell = _shell_B()
    L = np.linspace(0.0, shell.L_sweep_max, 201)
    result = detect_fold(shell, L)
    assert isinstance(result, FoldResult)


def test_detect_fold_matches_closed_form_shell_B() -> None:
    shell = _shell_B()
    L_fold_cf, S_fold_cf, D_fold_cf = _expected_fold(shell)
    # Make sure the closed-form fold actually sits inside the sweep.
    assert shell.L_sweep_min < L_fold_cf < shell.L_sweep_max

    L = np.linspace(shell.L_sweep_min, shell.L_sweep_max, 2001)
    result = detect_fold(shell, L)
    assert result.found is True
    assert result.L_fold == pytest.approx(L_fold_cf, rel=1e-8, abs=1e-8)
    assert result.S_star_at_fold == pytest.approx(S_fold_cf, rel=1e-10)
    assert result.D_star_at_fold == pytest.approx(D_fold_cf, rel=1e-10)
    assert "saddle-node fold" in result.description.lower()


def test_detect_fold_merged_root_is_degenerate_coexistence_equilibrium() -> None:
    """By Vieta's formulas the two Case-2 roots sum to ``-b/a = 2*D_fold``
    for every L where both roots exist. Their midpoint must therefore
    coincide with ``D_star_at_fold`` at any L below the fold, and the root
    spread must shrink to zero as L → L_fold from below.
    """
    shell = _shell_B()
    L = np.linspace(shell.L_sweep_min, shell.L_sweep_max, 401)
    result = detect_fold(shell, L)
    assert result.found
    assert result.L_fold is not None and result.D_star_at_fold is not None

    from dataclasses import replace

    D_fold = float(result.D_star_at_fold)
    prev_spread = float("inf")
    for eps in (1e-2, 1e-4, 1e-6):
        L_test = float(result.L_fold) * (1.0 - eps)
        at_L = replace(shell, L=L_test)
        roots = coexistence_fixed_points(at_L)
        assert len(roots) == 2, f"expected two roots at eps={eps}"
        D_lo, D_hi = sorted(D for _, D in roots)
        midpoint = 0.5 * (D_lo + D_hi)
        # Midpoint is D_fold identically (Vieta), up to floating-point noise.
        assert midpoint == pytest.approx(D_fold, rel=1e-8, abs=1e-6)
        spread = D_hi - D_lo
        assert spread < prev_spread
        prev_spread = spread


@pytest.mark.parametrize("shell", list(default_shells()))
def test_detect_fold_all_default_shells_have_physical_fold(
    shell: ShellConfig,
) -> None:
    """For the three catalogued shells the fold must be real, physical and
    within (or at worst just outside) the sweep range."""
    L_fold_cf, S_fold_cf, D_fold_cf = _expected_fold(shell)
    assert L_fold_cf > 0.0
    assert S_fold_cf > 0.0
    assert D_fold_cf > 0.0

    # Build a generous sweep that definitely brackets the fold.
    L_max = max(shell.L_sweep_max, 2.0 * L_fold_cf)
    L = np.linspace(0.0, L_max, 4001)
    result = detect_fold(shell, L)
    assert result.found is True
    assert result.L_fold == pytest.approx(L_fold_cf, rel=1e-6, abs=1e-6)


def test_detect_fold_sweep_entirely_below_fold_returns_prediction() -> None:
    shell = _shell_B()
    L_fold_cf, _, _ = _expected_fold(shell)
    # Sweep ends well before the fold.
    L = np.linspace(0.0, 0.25 * L_fold_cf, 51)
    result = detect_fold(shell, L)
    assert result.found is False
    assert result.L_fold is not None
    assert result.L_fold == pytest.approx(L_fold_cf, rel=1e-6)
    assert "above the sweep" in result.description


def test_detect_fold_sweep_entirely_above_fold_returns_prediction() -> None:
    shell = _shell_B()
    L_fold_cf, _, _ = _expected_fold(shell)
    L = np.linspace(2.0 * L_fold_cf, 5.0 * L_fold_cf, 51)
    result = detect_fold(shell, L)
    assert result.found is False
    assert result.L_fold is not None
    assert result.L_fold == pytest.approx(L_fold_cf, rel=1e-6)
    assert "below the sweep" in result.description


def test_detect_fold_gamma_zero_returns_no_fold() -> None:
    shell = _shell_B(gamma=0.0)
    L = np.linspace(0.0, 1000.0, 101)
    result = detect_fold(shell, L)
    assert result.found is False
    assert result.L_fold is None
    assert result.S_star_at_fold is None
    assert result.D_star_at_fold is None
    assert "degenerate" in result.description.lower()


def test_detect_fold_unphysical_merged_root_rejected() -> None:
    """When delta_S * gamma > beta * delta_D the closed-form D_fold is
    negative and therefore unphysical; the detector must flag ``found=False``
    and explain why.
    """
    # Pick parameters that flip the sign of ``b`` above.
    shell = _shell_B(delta_S=0.01, delta_D=0.02, beta=1e-6, gamma=1e-4)
    L = np.linspace(0.0, 1e6, 201)
    result = detect_fold(shell, L)
    assert result.found is False
    assert "not physical" in result.description


def test_detect_fold_input_validation() -> None:
    shell = _shell_B()
    with pytest.raises(ValueError, match="at least two"):
        detect_fold(shell, np.array([100.0]))
    with pytest.raises(ValueError, match="monotonically"):
        detect_fold(shell, np.array([0.0, 100.0, 50.0]))
