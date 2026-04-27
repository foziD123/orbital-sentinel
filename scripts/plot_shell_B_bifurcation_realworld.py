"""Shell B bifurcation diagram with real-world current-state overlay.

Produces ``reports/shell_B_bifurcation_realworld.png``.

This script is a close copy of ``plot_shell_B_bifurcation.py``, extended to
overlay the current real-world population marker sourced from
``data/real_world/shell_current_state.json`` (produced by
``scripts/fetch_realworld_data.py``).

The original ``reports/shell_B_bifurcation.png`` is **not** overwritten.

New elements on the main bifurcation panel:
  * Vertical dashed line at L_current (orange)
  * Horizontal dotted line at D_current (orange, faint)
  * Star scatter point at (L_current, D_current) labelled "Current state (2026)"
  * Traffic-light annotation in the top-right corner of the main panel
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bifurcation_engine.src.fixed_points import coexistence_fixed_points
from bifurcation_engine.src.hopf_detector import detect_fold
from bifurcation_engine.src.integrator import integrate_trajectory
from bifurcation_engine.src.shell_config import load_shell_by_name

# Colour used for the real-world marker (orange — distinct from all branch colours)
REALWORLD_COLOR = "#e6550d"


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


def _load_realworld(shell_name: str) -> dict:
    """Load the real-world current-state entry for one shell."""
    json_path = REPO_ROOT / "data" / "real_world" / "shell_current_state.json"
    if not json_path.exists():
        raise FileNotFoundError(
            f"Real-world data file not found: {json_path}\n"
            "Run scripts/fetch_realworld_data.py first."
        )
    with json_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    shells = payload.get("shells", {})
    if shell_name not in shells:
        available = list(shells.keys())
        raise KeyError(
            f"Shell {shell_name!r} not found in {json_path}. "
            f"Available: {available!r}"
        )
    return shells[shell_name]


def _traffic_light_label(light: str) -> tuple[str, str]:
    """Return (label_text, facecolor) for the traffic-light box."""
    mapping = {
        "green": ("GREEN — safe margin", "#1b7837"),
        "amber": ("AMBER — approaching fold", "#d95f02"),
        "red": ("RED — at or past fold", "#b2182b"),
    }
    return mapping.get(light, (light.upper(), "#555555"))


def main() -> None:
    shell = load_shell_by_name("Shell_B_800km")
    rw = _load_realworld("Shell_B_800km")

    L_current: float = float(rw["L_current"])
    D_current: float = float(rw["D_current"])
    L_fraction: float = float(rw["L_fraction"])
    traffic_light: str = rw["traffic_light"]
    epoch: str = rw.get("population_source", "see data/real_world/shell_current_state.json")

    L_sweep = np.linspace(0.0, 1.2 * shell.L_sweep_max, 4001)
    fold = detect_fold(shell, L_sweep)
    if fold.L_fold is None or fold.D_star_at_fold is None:
        raise RuntimeError(f"detect_fold did not return a fold: {fold}")
    L_fold = float(fold.L_fold)
    D_fold = float(fold.D_star_at_fold)

    L_low, D_low, L_up, D_up = _case2_branches(shell, L_sweep)

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

    # --- bifurcation diagram (identical to original) ---
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
    ax_main.scatter(
        [L_fold], [D_fold],
        s=110, color="#b2182b", zorder=5, edgecolor="white", linewidth=1.5,
        label=f"Saddle-node fold  L_fold = {L_fold:.1f}",
    )
    ax_main.axvline(L_fold, color="#b2182b", alpha=0.25, linewidth=1.0)
    for name, frac, color, _ in regimes:
        ax_main.axvline(frac * L_fold, color=color, alpha=0.35, linewidth=1.2, linestyle=":")
    ax_main.scatter(
        [0.5 * L_fold], [D0],
        s=45, color="#1b7837", marker="o", zorder=4,
        label=f"Initial condition  (D0 = {D0:.0f})",
    )

    # --- Real-world current state overlay ---
    ax_main.axvline(
        L_current,
        color=REALWORLD_COLOR, linewidth=2.0, linestyle="--", alpha=0.85,
        label=f"L_current = {L_current:.0f} obj/yr  (3-yr avg 2021–2023)",
    )
    ax_main.axhline(
        D_current,
        color=REALWORLD_COLOR, linewidth=1.0, linestyle=":", alpha=0.45,
    )
    ax_main.scatter(
        [L_current], [D_current],
        s=160, color=REALWORLD_COLOR, zorder=6,
        edgecolor="white", linewidth=1.5, marker="*",
        label=f"Current state  D≈{D_current:,}  L/L_fold={L_fraction:.2f}",
    )

    # Traffic-light annotation box (top-right corner of main panel)
    tl_label, tl_face = _traffic_light_label(traffic_light)
    ax_main.text(
        0.97, 0.97,
        f"Shell B traffic light\n{tl_label}",
        transform=ax_main.transAxes,
        ha="right", va="top",
        fontsize=9.5, fontweight="semibold",
        color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor=tl_face, alpha=0.85),
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
    ax_main.legend(loc="upper left", fontsize=9.0, framealpha=0.92)

    ax_main.annotate(
        f"(L_fold, D_fold)\n= ({L_fold:.1f}, {D_fold:.0f})",
        xy=(L_fold, D_fold),
        xytext=(L_fold - 150, D_fold + 18000),
        arrowprops=dict(arrowstyle="->", color="#b2182b"),
        fontsize=9, color="#b2182b",
    )

    # --- trajectory insets (identical to original) ---
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

    fig.suptitle(
        "Kessler tipping point — saddle-node fold — with 2026 real-world current state (Shell B, 800 km)",
        fontsize=12.5, y=0.965, fontweight="semibold",
    )

    out_path = REPO_ROOT / "reports" / "shell_B_bifurcation_realworld.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
