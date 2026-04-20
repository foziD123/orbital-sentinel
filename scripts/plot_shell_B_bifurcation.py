"""Generate the Shell_B_800km bifurcation diagram + trajectory overlays.

Produces ``reports/shell_B_bifurcation.png`` containing:

* a large left panel showing ``D*`` versus launch rate ``L`` with the
  stable lower Case-2 branch (solid), the unstable upper Case-2 branch
  (dashed), and the saddle-node fold point marked in red,
* three right panels showing ``D(t)`` at ``L = 0.5 * L_fold``, ``L_fold``,
  ``1.5 * L_fold`` — the three regimes that replace the Hopf/limit-cycle
  diagnostics for this 2D model.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for headless rendering

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import detect_fold
from bifurcation_engine.src.integrator import integrate_trajectory
from bifurcation_engine.src.shell_config import load_shell_by_name


def _case2_branches(shell, L_values):
    """Return parallel arrays of the lower and upper Case-2 roots across L."""
    L_low, D_low, L_up, D_up = [], [], [], []
    for L in L_values:
        local = replace(shell, L=float(L))
        roots = sorted(coexistence_fixed_points(local), key=lambda sd: sd[1])
        if roots:
            L_low.append(L)
            D_low.append(roots[0][1])
        if len(roots) == 2:
            L_up.append(L)
            D_up.append(roots[1][1])
    return (
        np.asarray(L_low),
        np.asarray(D_low),
        np.asarray(L_up),
        np.asarray(D_up),
    )


def main() -> None:
    shell = load_shell_by_name("Shell_B_800km")

    L_sweep = np.linspace(0.0, 1.2 * shell.L_sweep_max, 4001)
    fold = detect_fold(shell, L_sweep)
    if fold.L_fold is None or fold.D_star_at_fold is None:
        raise RuntimeError(f"detect_fold did not return a fold: {fold}")
    L_fold = float(fold.L_fold)
    D_fold = float(fold.D_star_at_fold)
    S_fold = float(fold.S_star_at_fold or 0.0)

    # Branches for the diagram.
    L_low, D_low, L_up, D_up = _case2_branches(shell, L_sweep)

    # Common IC: lower stable fixed point at 0.5 * L_fold (mirrors the
    # pipeline report in the console).
    at_half = replace(shell, L=0.5 * L_fold)
    roots = sorted(coexistence_fixed_points(at_half), key=lambda sd: sd[1])
    S0, D0 = roots[0]

    t_final = min(10.0 / shell.delta_S, 2.0e4)
    regimes = [
        ("0.5 L_fold (below)", 0.5, "#1b7837", "stable lower branch"),
        ("1.0 L_fold (at fold)", 1.0, "#d95f02", "marginal (fold point)"),
        ("1.5 L_fold (above)", 1.5, "#b2182b", "runaway"),
    ]
    trajectories = []
    for _, frac, _, _ in regimes:
        local = replace(shell, L=frac * L_fold)
        traj = integrate_trajectory(
            S0, D0, local, (0.0, t_final), runaway_ceiling_D=1e10
        )
        trajectories.append(traj)

    # ------------------------------------------------------------------
    # Figure
    # ------------------------------------------------------------------
    fig = plt.figure(figsize=(14.0, 7.5))
    gs = GridSpec(
        3, 2,
        width_ratios=[1.9, 1.0],
        hspace=0.45,
        wspace=0.25,
        left=0.07,
        right=0.98,
        top=0.86,
        bottom=0.09,
    )
    ax_main = fig.add_subplot(gs[:, 0])
    ax_below = fig.add_subplot(gs[0, 1])
    ax_fold = fig.add_subplot(gs[1, 1])
    ax_above = fig.add_subplot(gs[2, 1])

    # --- bifurcation diagram -------------------------------------------
    ax_main.plot(
        L_low, D_low,
        color="#1b7837", linewidth=2.3,
        label="Stable lower branch (Case 2)",
    )
    ax_main.plot(
        L_up, D_up,
        color="#762a83", linewidth=2.0, linestyle="--",
        label="Unstable upper branch (Case 2, saddle)",
    )

    # Fold point in red, annotated.
    ax_main.scatter(
        [L_fold], [D_fold],
        s=110, color="#b2182b", zorder=5, edgecolor="white", linewidth=1.5,
        label=f"Saddle-node fold  L_fold = {L_fold:.1f}",
    )
    ax_main.axvline(L_fold, color="#b2182b", alpha=0.25, linewidth=1.0)

    # Mark the three regimes along the L axis.
    for name, frac, color, _ in regimes:
        ax_main.axvline(frac * L_fold, color=color, alpha=0.35, linewidth=1.2, linestyle=":")

    # IC marker.
    ax_main.scatter(
        [0.5 * L_fold], [D0],
        s=45, color="#1b7837", marker="o", zorder=4,
        label=f"Initial condition  (D0 = {D0:.0f})",
    )

    ax_main.set_xlim(0.0, 1.1 * shell.L_sweep_max)
    ax_main.set_ylim(bottom=0.0)
    ax_main.set_xlabel("Launch rate  L  [objects / year]", fontsize=11)
    ax_main.set_ylabel("Equilibrium debris  D*  [objects]", fontsize=11)
    ax_main.set_title(
        f"Shell B @ 800 km  |  "
        f"β = {shell.beta:g}, γ = {shell.gamma:g}, "
        f"δS = {shell.delta_S:g}, δD = {shell.delta_D:g}",
        fontsize=11, pad=8,
    )
    ax_main.grid(True, alpha=0.25)
    ax_main.legend(loc="upper left", fontsize=9.5, framealpha=0.92)

    # Annotate fold coordinates.
    ax_main.annotate(
        f"(L_fold, D_fold)\n= ({L_fold:.1f}, {D_fold:.0f})",
        xy=(L_fold, D_fold),
        xytext=(L_fold - 150, D_fold + 18000),
        arrowprops=dict(arrowstyle="->", color="#b2182b"),
        fontsize=9, color="#b2182b",
    )

    # --- trajectory insets --------------------------------------------
    axes_traj = [ax_below, ax_fold, ax_above]
    for ax, traj, (name, frac, color, classification) in zip(
        axes_traj, trajectories, regimes
    ):
        ax.plot(traj["t"], traj["D"], color=color, linewidth=1.8)
        ax.axhline(D_fold, color="#b2182b", alpha=0.4, linewidth=1.0, linestyle=":")
        ax.set_title(f"{name}  →  {classification}", fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.set_ylabel("D(t)", fontsize=9)
        if frac == 1.5:
            ax.set_yscale("log")
        ax.tick_params(labelsize=8.5)
    axes_traj[-1].set_xlabel("time  t  [years]", fontsize=9)

    # Shared figure title.
    fig.suptitle(
        "Kessler tipping point in the 2D source-sink model is a saddle-node"
        " fold, not a Hopf bifurcation",
        fontsize=13, y=0.965, fontweight="semibold",
    )

    out_path = Path("reports/shell_B_bifurcation.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
