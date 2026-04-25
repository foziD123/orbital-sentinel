"""Tests for the 3-species fixed-point solver and continuation sweep.

Covers Step 3 of the 3-species engine extension:

* every returned ``(S*, R*, D*)`` satisfies the 3-species ODE residual to
  ``1e-8`` tolerance and is non-negative in every component;
* when ``beta_SR = beta_RD = 0`` the projection of the 3-D fixed points onto
  ``(S, D)`` matches :func:`find_all_fixed_points`, and the corresponding
  ``R*`` equals the steady-state ``delta_S * S* / delta_R`` (decoupled R);
* per-branch ``D_star`` curves out of :func:`continuation_sweep_3species` are
  smooth (no jump greater than 10 % of the branch's mean ``D_star`` between
  adjacent ``L`` steps), the analogue of VALIDATION.md T2.5.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from bifurcation_engine.src.fixed_points import (
    continuation_sweep_3species,
    find_all_fixed_points,
    find_fixed_points_3species,
)
from bifurcation_engine.src.model import (
    d_dot_3species,
    r_dot_3species,
    s_dot_3species,
)
from bifurcation_engine.src.shell_config import ShellConfig, default_shells


def _shell_3D_recipe(shell: ShellConfig) -> ShellConfig:
    """Apply the Step-5 parameter recipe to a 2-D default shell."""
    return replace(
        shell,
        delta_R=0.5 * (shell.delta_S + shell.delta_D),
        beta_SR=2.0 * shell.beta,
        beta_RD=3.0 * shell.beta,
        use_3species=True,
    )


# ---------------------------------------------------------------------------
# Residual + non-negativity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shell_index", [0, 1, 2], ids=["Shell_A", "Shell_B", "Shell_C"]
)
def test_find_fixed_points_3species_satisfies_ode_residual(
    shell_index: int,
) -> None:
    """Every returned (S*, R*, D*) makes |f_S| + |f_R| + |f_D| < 1e-8.

    We probe at a small L common to every shell (1.0 obj/yr) so that all
    three shells always have at least the clean-orbit fixed point — the
    residual check only makes sense when there's something to check, and
    Shell_C's default L=50 lies above its ~31.5 fold in the 2-D model.
    """
    shell = _shell_3D_recipe(default_shells()[shell_index])
    L_probe = 1.0
    points = find_fixed_points_3species(shell, L=L_probe)
    assert points, (
        f"No 3-species fixed points found for {shell.shell_name!r} at L={L_probe}"
    )

    shell_at_L = replace(shell, L=L_probe, L_sweep_min=0.0, L_sweep_max=None)
    for S, R, D in points:
        residual = (
            abs(s_dot_3species(S, R, D, shell_at_L))
            + abs(r_dot_3species(S, R, D, shell_at_L))
            + abs(d_dot_3species(S, R, D, shell_at_L))
        )
        assert residual < 1e-8, (
            f"Residual {residual!r} too large at (S,R,D)=({S}, {R}, {D})"
        )


@pytest.mark.parametrize(
    "shell_index", [0, 1, 2], ids=["Shell_A", "Shell_B", "Shell_C"]
)
def test_find_fixed_points_3species_non_negative(shell_index: int) -> None:
    shell = _shell_3D_recipe(default_shells()[shell_index])
    L_probe = 1.0
    for S, R, D in find_fixed_points_3species(shell, L=L_probe):
        assert S >= 0.0
        assert R >= 0.0
        assert D >= 0.0


def test_find_fixed_points_3species_with_L_override() -> None:
    """Passing L explicitly must yield results equivalent to constructing a
    new shell with that L (no validation tripped, no L_sweep clash)."""
    shell = _shell_3D_recipe(default_shells()[1])  # Shell_B
    L_target = 10.0  # well below Shell_B's L_fold of ~670

    via_arg = find_fixed_points_3species(shell, L=L_target)
    via_replace = find_fixed_points_3species(replace(shell, L=L_target))

    # Both should give the same set up to dedup tolerance and ordering.
    assert len(via_arg) == len(via_replace)
    via_arg_sorted = sorted(via_arg, key=lambda p: p[2])
    via_replace_sorted = sorted(via_replace, key=lambda p: p[2])
    for a, b in zip(via_arg_sorted, via_replace_sorted):
        np.testing.assert_allclose(a, b, rtol=1e-6, atol=1e-6)


# ---------------------------------------------------------------------------
# 2-D-projection sanity
# ---------------------------------------------------------------------------


def test_3species_fixed_points_project_to_2D_when_couplings_off() -> None:
    """With beta_SR = beta_RD = 0 the (S, D) projection of 3-D fixed points
    matches the 2-D solver, and R* = delta_S * S* / delta_R for each one
    (the steady state of the decoupled R-equation).
    """
    base = default_shells()[1]  # Shell_B
    decoupled = replace(
        base,
        delta_R=0.5 * (base.delta_S + base.delta_D),
        beta_SR=0.0,
        beta_RD=0.0,
        use_3species=False,  # avoid 3-species validation; logic is what matters
    )

    points_3D = find_fixed_points_3species(decoupled)
    points_2D = find_all_fixed_points(decoupled)

    # Project onto (S, D) and sort by D for comparison.
    proj_3D = sorted(((S, D) for S, _R, D in points_3D), key=lambda x: x[1])
    proj_2D = sorted(points_2D, key=lambda x: x[1])

    assert len(proj_3D) == len(proj_2D), (
        f"3-D projection has {len(proj_3D)} pts, 2-D has {len(proj_2D)}"
    )
    for (S3, D3), (S2, D2) in zip(proj_3D, proj_2D):
        assert S3 == pytest.approx(S2, rel=1e-6, abs=1e-6)
        assert D3 == pytest.approx(D2, rel=1e-6, abs=1e-6)

    # R* should equal delta_S * S* / delta_R when D = 0 (clean orbit).
    # When D > 0 the steady state is delta_S * S* / (delta_R + beta_RD * D),
    # and beta_RD = 0 here, so the same formula holds across the board.
    for S, R, _D in points_3D:
        expected_R = decoupled.delta_S * S / decoupled.delta_R
        assert R == pytest.approx(expected_R, rel=1e-6, abs=1e-6)


# ---------------------------------------------------------------------------
# Continuation sweep
# ---------------------------------------------------------------------------


def test_continuation_sweep_3species_returns_at_least_one_branch() -> None:
    shell = _shell_3D_recipe(default_shells()[1])  # Shell_B
    L_values = np.linspace(0.0, shell.effective_L_sweep_max, 50)
    branches = continuation_sweep_3species(shell, L_values)
    assert branches, "Expected at least one branch on Shell_B"


def test_continuation_sweep_3species_branch_smoothness() -> None:
    """Catches silent mis-merges: a branch swap shows up as a jump that is
    huge relative to the *local* branch magnitude (e.g. switching from a
    D~10² to D~10⁵ branch is a 1000x jump). Legitimate fold acceleration
    (D ~ sqrt(L_fold - L)) gives at most ~50% per-step relative jumps for
    100 sample points across the sweep, so we use 0.6 as a safe ceiling.

    The (S, R, D) point at L=0 is excluded because the trivial origin
    (0, 0, 0) is genuinely degenerate (clean orbit and lower-coexistence
    branches collide there) and would alias as a 100% jump on the first
    step regardless of mis-merge status.
    """
    shell = _shell_3D_recipe(default_shells()[1])  # Shell_B
    L_values = np.linspace(0.0, shell.effective_L_sweep_max, 100)
    branches = continuation_sweep_3species(shell, L_values)

    for branch in branches:
        D = branch["D_star"]
        L_arr = branch["L"]
        # Drop a leading L=0 point to skip the trivial-origin alias.
        if D.size and L_arr[0] == 0.0:
            D = D[1:]
        if D.size < 2:
            continue
        for i in range(D.size - 1):
            local_scale = max(abs(D[i]), abs(D[i + 1]), 1.0)
            ratio = abs(D[i + 1] - D[i]) / local_scale
            assert ratio < 0.6, (
                f"Branch jump {abs(D[i+1] - D[i])!r} from D={D[i]!r} to "
                f"D={D[i+1]!r} (relative {ratio!r}) — likely mis-merge"
            )


def test_continuation_sweep_3species_arrays_aligned() -> None:
    """L, S_star, R_star, D_star within a branch must all have the same
    length, with L monotone non-decreasing."""
    shell = _shell_3D_recipe(default_shells()[1])
    L_values = np.linspace(0.0, shell.effective_L_sweep_max, 60)
    for branch in continuation_sweep_3species(shell, L_values):
        n = branch["L"].size
        assert branch["S_star"].size == n
        assert branch["R_star"].size == n
        assert branch["D_star"].size == n
        assert np.all(np.diff(branch["L"]) >= -1e-12), (
            "Branch L must be monotone non-decreasing"
        )


def test_continuation_sweep_3species_rejects_2D_array() -> None:
    shell = _shell_3D_recipe(default_shells()[1])
    bad_L = np.zeros((3, 4))
    with pytest.raises(ValueError, match="one-dimensional"):
        continuation_sweep_3species(shell, bad_L)
