"""Tests for :mod:`bifurcation_engine.src.early_warning` (Task 7).

Acceptance gate: T4.1-T4.5 from VALIDATION.md, all keyed to the
saddle-node fold (the project's operational Kessler tipping point — see
``CLAUDE.md`` for the trace inequality argument and the post-3-species
and post-split-decay sweep summaries that close the Hopf hunt).

The tests are organised in two groups:

* unit tests — shape / edge-case behaviour of each individual function;
* T4.1-T4.5 — the acceptance scenarios written verbatim against the
  spec, using the packaged Shell B parameters and the real
  ``detect_fold`` / ``integrate_trajectory`` machinery so the tests
  exercise the same wiring the Module 3 dashboard will rely on.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from bifurcation_engine.src.early_warning import (
    AMBER_RED_THRESHOLD,
    DEFAULT_RECOVERY_TIME_MAX,
    GREEN_AMBER_THRESHOLD,
    autocorrelation_indicator,
    critical_slowing_down,
    early_warning_summary,
    variance_indicator,
)
from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import (
    FoldResult,
    HopfResult,
    detect_fold,
)
from bifurcation_engine.src.integrator import integrate_trajectory
from bifurcation_engine.src.shell_config import ShellConfig, load_shell_by_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def shell_b() -> ShellConfig:
    """Packaged Shell B parameters (~800 km, the historically congested band)."""
    return load_shell_by_name("Shell_B_800km")


@pytest.fixture(scope="module")
def shell_b_fold(shell_b: ShellConfig) -> FoldResult:
    """Real fold result on Shell B; ``L_fold ~ 670 obj/yr`` per CLAUDE.md."""
    L_grid = np.linspace(0.0, max(shell_b.L_sweep_max or 2000.0, 2000.0), 401)
    fold = detect_fold(shell_b, L_grid)
    assert fold.found, "Shell B must have a fold inside the default sweep window"
    assert fold.L_fold is not None and fold.L_fold > 0.0
    return fold


# ---------------------------------------------------------------------------
# critical_slowing_down — unit tests
# ---------------------------------------------------------------------------


def test_recovery_time_is_one_over_abs_alpha() -> None:
    L = np.linspace(0.0, 1.0, 5)
    alpha = np.array([-2.0, -1.0, -0.5, -0.25, -0.1])

    out = critical_slowing_down(L, alpha)

    assert np.allclose(out["L"], L)
    assert np.allclose(out["recovery_time"], 1.0 / np.abs(alpha))


def test_recovery_time_clipped_at_max_when_alpha_is_zero() -> None:
    L = np.array([0.0, 0.5, 1.0])
    alpha = np.array([-1.0, 0.0, -1.0e-12])

    out = critical_slowing_down(L, alpha, max_recovery_time=1.0e4)

    assert out["recovery_time"][0] == pytest.approx(1.0)
    # alpha = 0  -> recovery time at the cap.
    assert out["recovery_time"][1] == pytest.approx(1.0e4)
    # alpha = 1e-12 -> 1/|alpha| = 1e12, also clipped to the cap.
    assert out["recovery_time"][2] == pytest.approx(1.0e4)


def test_critical_slowing_down_default_cap() -> None:
    out = critical_slowing_down(np.array([0.0]), np.array([1.0e-30]))
    assert out["recovery_time"][0] == pytest.approx(DEFAULT_RECOVERY_TIME_MAX)


def test_critical_slowing_down_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        critical_slowing_down(np.zeros(3), np.zeros(4))


def test_critical_slowing_down_invalid_cap_raises() -> None:
    with pytest.raises(ValueError):
        critical_slowing_down(np.zeros(2), np.zeros(2), max_recovery_time=-1.0)


# ---------------------------------------------------------------------------
# variance_indicator — unit tests
# ---------------------------------------------------------------------------


def _flat_trajectory(t_final: float = 100.0, n: int = 200, value: float = 5.0) -> dict:
    t = np.linspace(0.0, t_final, n)
    return {"t": t, "D": np.full_like(t, value)}


def test_variance_of_constant_signal_is_zero() -> None:
    traj = _flat_trajectory()
    out = variance_indicator(traj, window=20)

    assert out["t"].shape == out["variance_D"].shape
    assert out["t"].size == traj["t"].size - 20 + 1
    assert np.allclose(out["variance_D"], 0.0)


def test_variance_window_must_be_at_least_two() -> None:
    traj = _flat_trajectory()
    with pytest.raises(ValueError):
        variance_indicator(traj, window=1)


def test_variance_returns_empty_when_trajectory_shorter_than_window() -> None:
    traj = {"t": np.array([0.0, 1.0]), "D": np.array([1.0, 1.0])}
    out = variance_indicator(traj, window=10)

    assert out["t"].size == 0
    assert out["variance_D"].size == 0


def test_variance_inflates_with_amplitude() -> None:
    n = 400
    t = np.linspace(0.0, 100.0, n)
    rng = np.random.default_rng(42)
    quiet = 1.0 + 0.01 * rng.standard_normal(n)
    loud = 1.0 + 0.10 * rng.standard_normal(n)

    out_quiet = variance_indicator({"t": t, "D": quiet}, window=50)
    out_loud = variance_indicator({"t": t, "D": loud}, window=50)

    # Variance should be O(100x) higher with 10x amplitude noise.
    assert out_loud["variance_D"].mean() > 10.0 * out_quiet["variance_D"].mean()


# ---------------------------------------------------------------------------
# autocorrelation_indicator — unit tests
# ---------------------------------------------------------------------------


def test_autocorrelation_window_lag_validation() -> None:
    traj = _flat_trajectory()
    with pytest.raises(ValueError):
        autocorrelation_indicator(traj, lag=0)
    with pytest.raises(ValueError):
        autocorrelation_indicator(traj, lag=1, window=2)


def test_autocorrelation_of_constant_signal_is_nan() -> None:
    """Constant signal -> sum of squared deviations is zero -> AC1 undefined."""
    out = autocorrelation_indicator(_flat_trajectory(value=7.0), window=30)
    assert out["ac1_D"].size > 0
    assert np.all(np.isnan(out["ac1_D"]))


def test_autocorrelation_of_white_noise_is_near_zero() -> None:
    rng = np.random.default_rng(0)
    n = 1000
    t = np.linspace(0.0, 100.0, n)
    D = rng.standard_normal(n)

    out = autocorrelation_indicator({"t": t, "D": D}, window=200)

    assert np.nanmean(out["ac1_D"]) == pytest.approx(0.0, abs=0.1)


def test_autocorrelation_of_smooth_signal_is_near_one() -> None:
    n = 500
    t = np.linspace(0.0, 100.0, n)
    D = np.exp(-t / 200.0)  # tau=200 >> dt -> AC1 -> 1

    out = autocorrelation_indicator({"t": t, "D": D}, window=50)

    valid = out["ac1_D"][~np.isnan(out["ac1_D"])]
    assert valid.size > 0
    # An exponential decay sampled in a finite window has AC1 ~= 0.94 here
    # (centred-window estimator with W=50 over a smooth tail). The point of
    # the test is that it sits well above the white-noise level (~0).
    assert valid.mean() > 0.9


# ---------------------------------------------------------------------------
# early_warning_summary — unit tests
# ---------------------------------------------------------------------------


def test_summary_status_unknown_when_fold_not_found(shell_b: ShellConfig) -> None:
    no_fold = FoldResult(found=False, description="not found in window")
    summary = early_warning_summary(
        shell_b, np.linspace(0.0, 1.0, 5), fold_result=no_fold
    )

    assert summary["status"] == "unknown"
    assert summary["primary_channel"]["available"] is False
    assert summary["secondary_channel"]["status"] == "not_applicable"


def test_summary_secondary_not_applicable_when_hopf_none(
    shell_b: ShellConfig, shell_b_fold: FoldResult
) -> None:
    summary = early_warning_summary(
        shell_b,
        np.linspace(0.0, 1.0, 5),
        fold_result=shell_b_fold,
        hopf_result=None,
    )
    assert summary["secondary_channel"]["status"] == "not_applicable"
    assert summary["secondary_channel"]["available"] is False


def test_summary_secondary_not_applicable_when_hopf_not_found(
    shell_b: ShellConfig, shell_b_fold: FoldResult
) -> None:
    null_hopf = HopfResult(found=False, outcome="no_complex_eigenvalues", description="x")
    summary = early_warning_summary(
        shell_b,
        np.linspace(0.0, 1.0, 5),
        fold_result=shell_b_fold,
        hopf_result=null_hopf,
    )
    assert summary["secondary_channel"]["status"] == "not_applicable"


# ---------------------------------------------------------------------------
# T4.1 — Recovery time diverges as alpha -> 0
# ---------------------------------------------------------------------------


def test_T4_1_recovery_time_diverges_as_alpha_goes_to_zero() -> None:
    alpha_array = np.array([-1.0, -0.5, -0.1, -0.01, -0.001])
    L_array = np.linspace(100.0, 600.0, alpha_array.size)

    out = critical_slowing_down(L_array, alpha_array)

    rec = out["recovery_time"]
    assert np.all(np.diff(rec) > 0.0), "recovery_time must be monotonically increasing"
    assert rec[-1] > 100.0 * rec[0]


# ---------------------------------------------------------------------------
# T4.2 — Traffic light: green far from L_fold
# ---------------------------------------------------------------------------


def test_T4_2_traffic_light_green_far_from_fold(
    shell_b: ShellConfig, shell_b_fold: FoldResult
) -> None:
    assert shell_b_fold.L_fold is not None
    L_current = 0.5 * shell_b_fold.L_fold  # 50% of L_fold
    params = replace(shell_b, L=L_current)

    summary = early_warning_summary(
        params,
        np.linspace(0.0, shell_b_fold.L_fold * 1.1, 50),
        fold_result=shell_b_fold,
    )

    assert summary["status"] == "green"
    assert summary["L_fraction"] == pytest.approx(0.5, rel=1e-9)
    assert 0.5 < GREEN_AMBER_THRESHOLD


# ---------------------------------------------------------------------------
# T4.3 — Traffic light: amber near L_fold
# ---------------------------------------------------------------------------


def test_T4_3_traffic_light_amber_near_fold(
    shell_b: ShellConfig, shell_b_fold: FoldResult
) -> None:
    assert shell_b_fold.L_fold is not None
    L_current = 0.88 * shell_b_fold.L_fold
    params = replace(shell_b, L=L_current)

    summary = early_warning_summary(
        params,
        np.linspace(0.0, shell_b_fold.L_fold * 1.1, 50),
        fold_result=shell_b_fold,
    )

    assert summary["status"] == "amber"
    assert GREEN_AMBER_THRESHOLD <= summary["L_fraction"] < AMBER_RED_THRESHOLD


# ---------------------------------------------------------------------------
# T4.4 — Traffic light: red at or past L_fold
# ---------------------------------------------------------------------------


def test_T4_4_traffic_light_red_at_or_past_fold(
    shell_b: ShellConfig, shell_b_fold: FoldResult
) -> None:
    assert shell_b_fold.L_fold is not None
    L_current = 1.00 * shell_b_fold.L_fold
    params = replace(shell_b, L=L_current)

    summary = early_warning_summary(
        params,
        np.linspace(0.0, shell_b_fold.L_fold * 1.2, 50),
        fold_result=shell_b_fold,
    )

    assert summary["status"] == "red"
    assert summary["L_fraction"] >= AMBER_RED_THRESHOLD


# ---------------------------------------------------------------------------
# T4.5 — Autocorrelation approaches 1 near the bifurcation
# ---------------------------------------------------------------------------


def test_T4_5_autocorrelation_approaches_one_near_fold(
    shell_b: ShellConfig, shell_b_fold: FoldResult
) -> None:
    """Integrate at L = 0.99 * L_fold with +5% IC perturbation; the lag-1
    autocorrelation in the late-time window should be > 0.8 because the
    relaxation time toward the lower fixed point diverges at the fold
    (critical slowing down)."""
    assert shell_b_fold.L_fold is not None
    L_current = 0.99 * shell_b_fold.L_fold
    params = replace(shell_b, L=L_current)

    # ``coexistence_fixed_points`` returns both Case-2 roots; the stable
    # lower branch is the one with the smaller D*. (The 2-D
    # ``continuation_sweep`` deliberately tracks only the upper branch.)
    coexistence = coexistence_fixed_points(params)
    assert len(coexistence) == 2, (
        f"expected two coexistence fixed points at L = 0.99 * L_fold, "
        f"got {len(coexistence)}"
    )
    S_star, D_star = min(coexistence, key=lambda sd: sd[1])
    assert D_star > 0.0, "lower-branch coexistence fixed point must have D* > 0"

    # Perturb D(0) by +5% so the trajectory has structure to autocorrelate.
    D0 = 1.05 * D_star
    S0 = S_star

    # Integrate over a horizon long enough to see relaxation but short
    # enough that the perturbation is still measurable above FP noise.
    t_final = 500.0
    n_eval = 1001
    t_eval = np.linspace(0.0, t_final, n_eval)
    traj = integrate_trajectory(S0, D0, params, t_span=(0.0, t_final), t_eval=t_eval)
    assert traj["success"], f"integration should succeed: {traj['message']}"

    out = autocorrelation_indicator(traj, lag=1, window=50)
    ac1 = out["ac1_D"]
    valid = ac1[~np.isnan(ac1)]
    assert valid.size > 0, "autocorrelation must produce at least one valid window"

    # "Mean of the last quarter" per VALIDATION.md T4.5.
    last_quarter = valid[-max(1, valid.size // 4) :]
    assert last_quarter.mean() > 0.8, (
        f"lag-1 autocorrelation in the late-time window should approach 1 "
        f"near the fold (got mean={last_quarter.mean():.3f})"
    )
