"""Saddle-node fold detection for the split-decay 3-species model.

The closed-form fold detector in :mod:`bifurcation_engine.src.hopf_detector`
(``detect_fold``) relies on the Case-2 quadratic discriminant of the 2-D
``(S, D)`` model, which has no analogue once the split-decay model couples
``R`` with three collision channels (``beta_SD``, ``beta_SR``, ``beta_RD``)
and three yield multipliers (``eta_SD``, ``eta_SR``, ``eta_RD``). The
operational fold signature in this regime is the L value at which a
warm-started continuation step on the lower coexistence branch fails — i.e.
where ``dD*/dL`` diverges.

This module exposes:

* :func:`detect_fold_numerical` — given a branch dict produced by
  :func:`bifurcation_engine.src.fixed_points_split.continuation_sweep_split`,
  return a :class:`FoldNumericalResult` describing whether the branch ended
  inside the sampled L window and where.

The Hopf detector itself does **not** need a split-decay variant: the
existing :func:`bifurcation_engine.src.hopf_detector.detect_hopf` consumes
``(L, alpha, omega)`` arrays and is reused unchanged via the aliases
exposed by :func:`track_eigenvalues_split`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

__all__ = [
    "FoldNumericalResult",
    "detect_fold_numerical",
]


@dataclass(frozen=True)
class FoldNumericalResult:
    """Outcome of a numerical fold-detection pass on one branch.

    Attributes
    ----------
    found:
        ``True`` if the branch terminates strictly inside the sampled L
        window — i.e. the warm-start fails before reaching ``L_sweep_max``.
        ``False`` if the branch reaches the upper end of the sweep, in
        which case the fold (if any) is above the sweep.
    L_fold:
        Estimated launch rate at the fold. When ``found`` is True this is
        the midpoint between the last L on the branch and a one-step
        extrapolation past it; if branch tracking sampled L values uniformly
        the result is accurate to half the sampling resolution. ``None``
        when ``found`` is False.
    L_last_on_branch:
        The largest L at which the branch still has a fixed point. ``None``
        if the branch is empty.
    last_state:
        ``(S, R, D)`` at ``L_last_on_branch``, useful for evaluating the
        trace inequality at the lower-branch terminus.
    description:
        Plain-English summary suitable for reports and logs.
    """

    found: bool
    description: str
    L_fold: float | None = None
    L_last_on_branch: float | None = None
    last_state: tuple[float, float, float] | None = None


def detect_fold_numerical(
    branch: Mapping[str, np.ndarray],
    L_sweep_max: float,
    fold_resolution_floor: float = 1e-12,
) -> FoldNumericalResult:
    """Detect a saddle-node fold by branch-termination on a continuation pass.

    Parameters
    ----------
    branch:
        A dict shaped like one element of
        :func:`continuation_sweep_split`'s output (keys ``L``, ``S_star``,
        ``R_star``, ``D_star`` of equal length, monotone in ``L``).
    L_sweep_max:
        The upper end of the L grid that produced ``branch``. Used to
        decide whether the branch ended *inside* the sweep (a real fold)
        or *at* the sweep upper bound (the fold, if any, is past the
        sampled window).
    fold_resolution_floor:
        Numerical floor for ``(L_sweep_max - L_last) > fold_resolution_floor``
        when deciding whether the branch ended inside the window. Defaults
        to ``1e-12``; only relevant when the user asked the sweep to stop
        exactly at a fold.

    Returns
    -------
    FoldNumericalResult
        See the dataclass for the field semantics.
    """
    L = np.asarray(branch["L"], dtype=float)

    if L.size == 0:
        return FoldNumericalResult(
            found=False,
            description="Empty branch; no fold detection possible.",
        )

    L_last = float(L[-1])
    S_last = float(np.asarray(branch["S_star"], dtype=float)[-1])
    R_last = float(np.asarray(branch["R_star"], dtype=float)[-1])
    D_last = float(np.asarray(branch["D_star"], dtype=float)[-1])
    last_state = (S_last, R_last, D_last)

    # If the branch covers the whole sampling window, the fold (if any) is
    # above L_sweep_max. We cannot place it without extrapolation; report
    # not-found and let the caller decide.
    if L_sweep_max - L_last <= fold_resolution_floor:
        return FoldNumericalResult(
            found=False,
            description=(
                f"Branch reaches L_sweep_max = {L_sweep_max:.4g} without "
                "warm-start failure; the fold (if any) lies above the "
                "sampled window."
            ),
            L_last_on_branch=L_last,
            last_state=last_state,
        )

    # Branch terminated inside the sweep. The fold sits between L_last and
    # the next sample point that would have been visited. Without that
    # next sample we report L_last as the conservative lower bound and a
    # midpoint estimate using the average step size as the working value.
    if L.size >= 2:
        step_estimate = float(L[-1] - L[-2])
    else:
        step_estimate = max(L_last, 1.0) * 1e-3

    L_fold_estimate = L_last + 0.5 * step_estimate

    return FoldNumericalResult(
        found=True,
        description=(
            f"Branch terminates at L = {L_last:.4g} with warm-start failure "
            f"(estimated fold at L_fold ~= {L_fold_estimate:.4g}, "
            f"step resolution {step_estimate:.4g}). The lower coexistence "
            "fixed point ceases to exist past this L."
        ),
        L_fold=L_fold_estimate,
        L_last_on_branch=L_last,
        last_state=last_state,
    )
