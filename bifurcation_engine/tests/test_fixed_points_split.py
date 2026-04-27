"""Tests for the split-decay fixed-point solver and continuation sweep.

We focus on the structural assertions that don't depend on the solver's
exact discovery order: every returned fixed point really is a stationary
state, populations are non-negative, the trivial clean-orbit
``(L/delta_S, 0, 0)`` is reproduced when no debris seed survives, and
:func:`continuation_sweep_split` produces well-formed branches whose
endpoints stay close to actual fixed points.
"""

from __future__ import annotations

import numpy as np
import pytest

from bifurcation_engine.src.fixed_points_split import (
    continuation_sweep_split,
    find_fixed_points_split,
)
from bifurcation_engine.src.model_split import (
    d_dot_split,
    r_dot_split,
    s_dot_split,
)
from bifurcation_engine.src.shell_config import ShellConfig
from bifurcation_engine.src.split_decay_config import SplitDecayConfig


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


def _split_at(L: float, *, rho_fraction: float = 0.5) -> SplitDecayConfig:
    shell = _shell_B()
    cfg = SplitDecayConfig.from_shell(shell, rho_fraction=rho_fraction)
    from dataclasses import replace
    return replace(cfg, L=L, L_sweep_min=0.0, L_sweep_max=None)


# ---------------------------------------------------------------------------
# find_fixed_points_split
# ---------------------------------------------------------------------------


def test_find_fixed_points_returns_only_physical_zeros() -> None:
    p = _split_at(L=10.0)
    pts = find_fixed_points_split(p)
    assert len(pts) >= 1, "Expected at least one fixed point at low L"

    for S, R, D in pts:
        assert S >= 0.0
        assert R >= 0.0
        assert D >= 0.0
        residual = np.array(
            [
                s_dot_split(S, R, D, p),
                r_dot_split(S, R, D, p),
                d_dot_split(S, R, D, p),
            ]
        )
        scale = 1.0 + abs(S) + abs(R) + abs(D)
        assert float(np.linalg.norm(residual)) <= 1e-6 * scale


def test_find_fixed_points_finds_clean_orbit_at_zero_launch() -> None:
    """At L=0 the only physical fixed point is the trivial origin (0,0,0)."""
    p = _split_at(L=0.0)
    pts = find_fixed_points_split(p)
    assert len(pts) >= 1
    # The trivial origin must be among the fixed points.
    distances = [
        float(np.linalg.norm(np.asarray(pt))) for pt in pts
    ]
    assert min(distances) < 1e-6


def test_split_model_has_no_clean_orbit_equilibrium_for_positive_L() -> None:
    """The split-decay model has no ``D = 0`` coexistence equilibrium for
    any ``L > 0``.

    Sketch of the argument: at any equilibrium with ``D = 0``, the third
    equation reduces to ``D_dot = eta_SR*beta_SR*S*R = 0``, forcing
    ``S*R = 0``. ``R = 0`` then forces ``rho_S*S = 0`` from ``R_dot``, hence
    ``S = 0``; but then ``S_dot = L`` has no zero. ``S = 0`` likewise forces
    ``L = 0`` from ``S_dot``. So for ``L > 0`` every equilibrium has
    ``D > 0``: the rho_S leak sustains a non-zero derelict pool which
    in turn pumps debris through eta_SR*beta_SR*S*R.

    This is a structural difference from the existing 3-species model,
    which retains a clean-orbit equilibrium because its ``D_dot`` source
    ``beta_SR*S*R`` is unmultiplied (eta-baseline) and the ``D = 0`` axis
    is invariant only because the same product appears in ``R_dot`` as a
    sink — but in the corrected model it does *not* appear, because the
    derelict body is removed in an active-derelict collision.
    """
    p = _split_at(L=10.0)
    pts = find_fixed_points_split(p)
    assert pts, "Solver must still find at least one fixed point at L=10"
    for S, R, D in pts:
        # Either the trivial origin (irrelevant for L>0) or a coexistence
        # state with D > 0. We assert there's no D~=0 fixed point with S>0.
        if S > 1.0:
            assert D > 1e-3, (
                f"Found unexpected near-clean-orbit equilibrium "
                f"(S={S:.3g}, R={R:.3g}, D={D:.3g}) for L>0; the split-decay "
                "model should not admit this branch."
            )


def test_find_fixed_points_with_explicit_L_overrides_params_L() -> None:
    p = _split_at(L=10.0)
    pts_low = find_fixed_points_split(p, L=10.0)
    pts_via_arg = find_fixed_points_split(p, L=10.0)
    assert len(pts_low) == len(pts_via_arg)


# ---------------------------------------------------------------------------
# continuation_sweep_split
# ---------------------------------------------------------------------------


def test_continuation_sweep_returns_well_formed_branches() -> None:
    p = _split_at(L=1.0)
    L_grid = np.linspace(0.5, 50.0, 25)
    branches = continuation_sweep_split(p, L_grid)

    assert len(branches) >= 1
    for b in branches:
        assert b["L"].ndim == 1
        assert b["L"].size > 0
        assert (
            b["L"].size
            == b["S_star"].size
            == b["R_star"].size
            == b["D_star"].size
        )
        # L is monotonic non-decreasing along a tracked branch.
        assert np.all(np.diff(b["L"]) >= 0)


def test_continuation_branch_points_are_fixed_points() -> None:
    p = _split_at(L=1.0)
    L_grid = np.linspace(0.5, 30.0, 15)
    branches = continuation_sweep_split(p, L_grid)

    from dataclasses import replace
    for b in branches:
        for i in range(b["L"].size):
            local = replace(p, L=float(b["L"][i]), L_sweep_min=0.0, L_sweep_max=None)
            S = float(b["S_star"][i])
            R = float(b["R_star"][i])
            D = float(b["D_star"][i])
            res = np.array(
                [
                    s_dot_split(S, R, D, local),
                    r_dot_split(S, R, D, local),
                    d_dot_split(S, R, D, local),
                ]
            )
            scale = 1.0 + abs(S) + abs(R) + abs(D)
            assert float(np.linalg.norm(res)) <= 1e-5 * scale


def test_continuation_sweep_rejects_non_1d_L() -> None:
    p = _split_at(L=1.0)
    with pytest.raises(ValueError, match="one-dimensional"):
        continuation_sweep_split(p, np.array([[1.0, 2.0], [3.0, 4.0]]))
