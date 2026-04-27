"""Early-warning indicators for the Kessler tipping point (Task 7).

This module operationalises the three classical critical-slowing-down
signals — recovery-time divergence, variance inflation, and lag-1
autocorrelation approaching unity — for the saddle-node fold that the
project has identified as the Kessler tipping point.

Why fold-only. The 2-D source-sink model admits no Hopf bifurcation, the
3-species extension found none either, and the additive split-decay
Hopf-hunt sweep (April 2026, 2,400 cells) confirmed the same outcome on
Shells B and C. The trace inequality in ``CLAUDE.md`` shows this is a
structural property of the model class, not an accident of any one
parameter set. The four functions below are therefore keyed to the fold
detected by :func:`bifurcation_engine.src.hopf_detector.detect_fold`,
with the Hopf channel kept in :func:`early_warning_summary` purely for
forward compatibility with future model extensions (inter-shell
coupling, NASA Standard Breakup Model integration via pySSEM, etc.).

Public API:

* :func:`critical_slowing_down` — converts an ``alpha`` array along the
  stable lower branch into a recovery-time array ``1 / |alpha|``.
* :func:`variance_indicator` — rolling variance of ``D(t)``.
* :func:`autocorrelation_indicator` — lag-1 autocorrelation of ``D(t)``
  in sliding windows.
* :func:`early_warning_summary` — combines a :class:`FoldResult` with
  the current launch rate to emit a green/amber/red traffic light, and
  reports ``not_applicable`` on the Hopf channel until a future model
  extension surfaces a genuine Hopf locus.

The module is dependency-light: only ``numpy``, the existing
``ShellConfig`` parameter object, and the ``FoldResult`` /
``HopfResult`` dataclasses from
:mod:`bifurcation_engine.src.hopf_detector`. No solver state is held;
every function is pure.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from .hopf_detector import FoldResult, HopfResult
from .shell_config import ShellConfig

__all__ = [
    "critical_slowing_down",
    "variance_indicator",
    "autocorrelation_indicator",
    "early_warning_summary",
    "DEFAULT_RECOVERY_TIME_MAX",
    "GREEN_AMBER_THRESHOLD",
    "AMBER_RED_THRESHOLD",
]


# Display cap for ``1 / |alpha|`` so plots and dashboards remain readable
# even when ``alpha`` numerically touches zero at the fold itself.
DEFAULT_RECOVERY_TIME_MAX = 1.0e4

# Traffic-light thresholds (fractions of L_fold). Spec is in
# ``TASKS.md`` Task 7 and ``VALIDATION.md`` T4.2-T4.4.
GREEN_AMBER_THRESHOLD = 0.80
AMBER_RED_THRESHOLD = 0.95


# ---------------------------------------------------------------------------
# Critical slowing down: recovery time along the stable branch
# ---------------------------------------------------------------------------


def critical_slowing_down(
    L_array: np.ndarray,
    alpha_array: np.ndarray,
    *,
    max_recovery_time: float = DEFAULT_RECOVERY_TIME_MAX,
) -> dict[str, np.ndarray]:
    """Return the per-step recovery time ``tau(L) = 1 / |alpha(L)|``.

    Parameters
    ----------
    L_array, alpha_array:
        One-dimensional arrays of identical shape. ``alpha_array[i]`` is
        the leading eigenvalue real part of the Jacobian at the lower-
        branch fixed point at launch rate ``L_array[i]``. On a stable
        branch ``alpha`` should be negative; close to the saddle-node
        fold ``alpha`` approaches zero from below and the recovery time
        diverges.
    max_recovery_time:
        Display cap. Any ``1 / |alpha|`` exceeding this value (including
        the numerically-zero case ``alpha == 0``) is clipped here so
        plots remain readable. Default is ``1e4`` years, well above any
        physically meaningful relaxation timescale.

    Returns
    -------
    dict
        Two arrays, both the same shape as the inputs:

        * ``L`` — copy of ``L_array``,
        * ``recovery_time`` — ``min(1 / |alpha|, max_recovery_time)``,
          clipped to ``max_recovery_time`` where ``alpha`` is exactly
          zero.

    Raises
    ------
    ValueError
        On shape mismatch or ``max_recovery_time <= 0``.
    """
    L = np.asarray(L_array, dtype=float)
    alpha = np.asarray(alpha_array, dtype=float)

    if L.shape != alpha.shape:
        raise ValueError(
            "L_array and alpha_array must have the same shape "
            f"(got {L.shape} vs {alpha.shape})"
        )
    if max_recovery_time <= 0.0:
        raise ValueError(
            f"max_recovery_time must be positive (got {max_recovery_time!r})"
        )

    abs_alpha = np.abs(alpha)
    # Where alpha is exactly zero, 1/|alpha| is +inf; we replace it by the cap.
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = np.where(abs_alpha > 0.0, 1.0 / abs_alpha, np.inf)
    rec = np.minimum(raw, max_recovery_time)
    # Replace any residual NaN (alpha = NaN inputs) by the cap as well so
    # the caller never has to special-case missing values.
    rec = np.where(np.isnan(rec), max_recovery_time, rec)
    return {"L": L.copy(), "recovery_time": rec}


# ---------------------------------------------------------------------------
# Variance and autocorrelation: time-series indicators
# ---------------------------------------------------------------------------


def _trajectory_arrays(trajectory: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Pull ``t`` and ``D`` out of a trajectory dict and validate."""
    if "t" not in trajectory or "D" not in trajectory:
        raise ValueError(
            "trajectory dict must contain keys 't' and 'D' (the integrator "
            "output produced by integrate_trajectory satisfies this)"
        )
    t = np.asarray(trajectory["t"], dtype=float).ravel()
    D = np.asarray(trajectory["D"], dtype=float).ravel()
    if t.shape != D.shape:
        raise ValueError(
            "trajectory['t'] and trajectory['D'] must have the same shape "
            f"(got {t.shape} vs {D.shape})"
        )
    return t, D


def variance_indicator(
    trajectory: Mapping[str, Any],
    window: int = 50,
) -> dict[str, np.ndarray]:
    """Rolling sample variance of ``D(t)`` in a right-aligned window.

    Parameters
    ----------
    trajectory:
        A dict produced by
        :func:`bifurcation_engine.src.integrator.integrate_trajectory`,
        with at least keys ``t`` and ``D`` of equal shape.
    window:
        Window length (number of samples). Must be ``>= 2`` because the
        sample variance with ``ddof=1`` is undefined for ``window=1``.

    Returns
    -------
    dict
        ``t`` — right-aligned end-of-window times,
        length ``len(D) - window + 1``;
        ``variance_D`` — sample variance (``ddof=1``) of ``D`` in each
        window, same length.

        Both arrays are empty when the trajectory is shorter than
        ``window``; this is a no-op output rather than an error.

    Raises
    ------
    ValueError
        If ``window < 2``, the trajectory dict is missing ``t`` / ``D``,
        or those two arrays have mismatched shapes.
    """
    if window < 2:
        raise ValueError(f"window must be >= 2 (got {window!r})")

    t, D = _trajectory_arrays(trajectory)
    if D.size < window:
        return {"t": np.empty(0, dtype=float), "variance_D": np.empty(0, dtype=float)}

    n = D.size - window + 1
    var_D = np.empty(n, dtype=float)
    for i in range(n):
        var_D[i] = float(np.var(D[i : i + window], ddof=1))
    return {"t": t[window - 1 :].copy(), "variance_D": var_D}


def autocorrelation_indicator(
    trajectory: Mapping[str, Any],
    lag: int = 1,
    window: int = 50,
) -> dict[str, np.ndarray]:
    """Lag-`lag` autocorrelation of ``D(t)`` in right-aligned sliding windows.

    For each window of length ``window`` over ``D(t)``, computes::

        ac[i] = sum_k (x_k - mean(x)) * (x_{k + lag} - mean(x))
              / sum_k (x_k - mean(x))**2

    where ``x = D[i : i + window]``. As the system approaches the
    saddle-node fold ``alpha -> 0``, recovery from perturbations slows
    down and consecutive samples become near-identical, so ``ac1``
    approaches one. This is the canonical critical-slowing-down
    autocorrelation signature; it precedes saddle-node folds as well as
    Hopf bifurcations.

    Parameters
    ----------
    trajectory:
        Integrator output; must contain ``t`` and ``D``.
    lag:
        Time lag in samples. Must be ``>= 1``.
    window:
        Window length. Must satisfy ``window >= lag + 2`` so the centred
        sums have at least two terms.

    Returns
    -------
    dict
        ``t`` — right-aligned end-of-window times;
        ``ac1_D`` — autocorrelation in each window. NaN where the
        within-window sum of squared deviations is below numerical
        floor (constant trajectory in that window).

    Raises
    ------
    ValueError
        On bad ``lag`` / ``window`` arguments or a malformed trajectory.
    """
    if lag < 1:
        raise ValueError(f"lag must be >= 1 (got {lag!r})")
    if window < lag + 2:
        raise ValueError(
            f"window must be >= lag + 2 (got window={window!r}, lag={lag!r})"
        )

    t, D = _trajectory_arrays(trajectory)
    if D.size < window:
        return {"t": np.empty(0, dtype=float), "ac1_D": np.empty(0, dtype=float)}

    n = D.size - window + 1
    ac = np.empty(n, dtype=float)
    denom_floor = 1.0e-30
    for i in range(n):
        x = D[i : i + window]
        m = float(np.mean(x))
        centred = x - m
        denom = float(np.sum(centred * centred))
        if denom <= denom_floor:
            ac[i] = float("nan")
            continue
        num = float(np.sum(centred[:-lag] * centred[lag:]))
        ac[i] = num / denom

    return {"t": t[window - 1 :].copy(), "ac1_D": ac}


# ---------------------------------------------------------------------------
# Traffic light: combine all channels into a dashboard-ready summary
# ---------------------------------------------------------------------------


def _classify_traffic_light(L_fraction: float) -> str:
    """Map ``L / L_threshold`` to ``green | amber | red``."""
    if L_fraction < GREEN_AMBER_THRESHOLD:
        return "green"
    if L_fraction < AMBER_RED_THRESHOLD:
        return "amber"
    return "red"


def early_warning_summary(
    params: ShellConfig,
    L_values: np.ndarray,
    fold_result: FoldResult,
    hopf_result: HopfResult | None = None,
) -> dict[str, Any]:
    """Combine fold, Hopf and current launch rate into a dashboard summary.

    Parameters
    ----------
    params:
        Shell configuration whose ``params.L`` is the *current* launch
        rate to be classified against the fold (and, optionally, Hopf)
        thresholds.
    L_values:
        The L grid that was used to produce ``fold_result`` and (when
        provided) the eigenvalue track behind ``hopf_result``. Carried
        through unchanged on the returned ``L_values`` key for
        dashboards that want to overlay the indicators on the same
        sweep window.
    fold_result:
        Output of :func:`bifurcation_engine.src.hopf_detector.detect_fold`
        (or any other detector that exposes the same dataclass fields).
        When ``found is False`` or ``L_fold is None`` the primary status
        is ``unknown``.
    hopf_result:
        Optional Hopf detector output. The Hopf channel always reports
        ``not_applicable`` when ``hopf_result is None`` or
        ``hopf_result.found is False`` — the API hook is kept for
        forward compatibility with future model extensions.

    Returns
    -------
    dict
        Top-level keys:

        * ``status`` — the primary (fold) traffic-light value;
          ``green``, ``amber``, ``red``, or ``unknown`` when the fold
          channel cannot evaluate.
        * ``L_fraction`` — ``params.L / fold_result.L_fold`` when
          available, else ``None``.
        * ``L_fold`` — the fold's launch rate, or ``None``.
        * ``L_current`` — copy of ``params.L``.
        * ``primary_channel`` — full fold-channel dict (always present).
        * ``secondary_channel`` — full Hopf-channel dict (always
          present, with ``status='not_applicable'`` when no Hopf).
        * ``L_values`` — passthrough for dashboards.
    """
    L_current = float(params.L)
    L_arr = np.asarray(L_values, dtype=float)

    # --- Primary channel: fold ------------------------------------------------
    if not fold_result.found or fold_result.L_fold is None or fold_result.L_fold <= 0.0:
        primary: dict[str, Any] = {
            "channel": "fold",
            "available": False,
            "status": "unknown",
            "L_fraction": None,
            "L_current": L_current,
            "L_fold": None,
            "description": (
                "No saddle-node fold located inside the supplied L window; "
                "primary traffic light is unknown."
            ),
        }
    else:
        L_fold = float(fold_result.L_fold)
        L_fraction = L_current / L_fold
        status = _classify_traffic_light(L_fraction)
        primary = {
            "channel": "fold",
            "available": True,
            "status": status,
            "L_fraction": L_fraction,
            "L_current": L_current,
            "L_fold": L_fold,
            "description": (
                f"L = {L_current:.4g} obj/yr is "
                f"{100.0 * L_fraction:.1f}% of L_fold = {L_fold:.4g} obj/yr; "
                f"traffic light: {status}."
            ),
        }

    # --- Secondary channel: Hopf (placeholder under current model class) -----
    if (
        hopf_result is None
        or not hopf_result.found
        or hopf_result.L_c is None
        or hopf_result.L_c <= 0.0
    ):
        secondary: dict[str, Any] = {
            "channel": "hopf",
            "available": False,
            "status": "not_applicable",
            "L_fraction": None,
            "L_current": L_current,
            "L_c": None,
            "description": (
                "Hopf channel is reserved for future model extensions; "
                "the 2-D, 3-species, and split-decay model classes admit "
                "no Hopf bifurcation, so this channel is not applicable "
                "for the current shell."
            ),
        }
    else:
        L_c = float(hopf_result.L_c)
        L_fraction_hopf = L_current / L_c
        hopf_status = _classify_traffic_light(L_fraction_hopf)
        secondary = {
            "channel": "hopf",
            "available": True,
            "status": hopf_status,
            "L_fraction": L_fraction_hopf,
            "L_current": L_current,
            "L_c": L_c,
            "description": (
                f"Hopf channel: L = {L_current:.4g} obj/yr is "
                f"{100.0 * L_fraction_hopf:.1f}% of L_c = {L_c:.4g}; "
                f"traffic light: {hopf_status}."
            ),
        }

    return {
        "status": primary["status"],
        "L_fraction": primary["L_fraction"],
        "L_fold": primary["L_fold"],
        "L_current": L_current,
        "primary_channel": primary,
        "secondary_channel": secondary,
        "L_values": L_arr,
    }
