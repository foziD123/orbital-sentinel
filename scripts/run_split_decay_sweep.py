"""Hopf-hunt parameter sweep for the split-decay 3-species model.

Usage (profile gate first, then full sweep)::

    PYTHONPATH=. .venv/bin/python scripts/run_split_decay_sweep.py --profile-only
    PYTHONPATH=. .venv/bin/python scripts/run_split_decay_sweep.py
    PYTHONPATH=. .venv/bin/python scripts/run_split_decay_sweep.py --grid 10

What this driver does
---------------------

1. **Profile gate.** Times one representative cell (Shell B, ``rho_fraction
   = 0.5``, ``gamma_multiplier = 1.0``, baseline ``eta = (1, 1, 1)``,
   100 L points). Reports the wall time. If it exceeds 90 seconds the
   driver downgrades the per-axis grid resolution from the requested
   value (default 20) to 10 and prints a warning, before launching the
   full sweep.

2. **Full sweep.** For each shell in ``--shells`` (default ``B,C``), for
   each ``(eta_SD, eta_SR, eta_RD)`` triplet in
   ``ETA_TRIPLETS`` (3 of them), runs a 2-D grid over
   ``rho_fraction`` x ``gamma_multiplier``. For every cell it:

   * builds a :class:`SplitDecayConfig` via :meth:`from_shell`,
   * runs :func:`continuation_sweep_split` with 100 L points across
     ``[L_sweep_min, effective_L_sweep_max]``,
   * picks the *lower* coexistence branch (smallest mean ``D``),
   * runs :func:`track_eigenvalues_split` on that branch,
   * runs :func:`detect_hopf` if there's at least one complex point,
   * runs :func:`detect_fold_numerical` to record where the lower
     branch terminated.

3. **Outputs.** For each shell ``X``:

   * ``reports/split_decay_sweep_<X>.csv`` — one row per cell with
     ``shell, rho_fraction, gamma_multiplier, eta_SD, eta_SR, eta_RD,
     hopf_found, hopf_L_c, hopf_omega, fold_found, L_fold, n_complex_pts,
     min_alpha_complex, max_trace_at_lower_branch, leading_alpha_max``.
   * ``reports/split_decay_sweep_<X>_<eta_label>.png`` —
     hopf-detected / no-hopf heatmap on the ``rho_fraction`` x
     ``gamma_multiplier`` grid for the chosen eta triplet.

4. **Summary.** ``reports/split_decay_sweep_summary.md`` with the
   positive/negative outcome decision, per-shell tables, and references
   to the heatmaps. The CLAUDE.md / TODO.md updates are made by hand
   from this summary by the human reviewer.

Quarantine guarantee
--------------------

This script imports only from ``bifurcation_engine.src.split_decay_config``,
``bifurcation_engine.src.fixed_points_split``,
``bifurcation_engine.src.eigenvalues_split``,
``bifurcation_engine.src.hopf_detector_split``,
``bifurcation_engine.src.shell_config`` (read-only), and
``bifurcation_engine.src.hopf_detector`` (the existing detect_hopf, used
unchanged via the alias dict). The 2-D and existing 3-species pipelines
are not touched.
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from bifurcation_engine.src.eigenvalues_split import track_eigenvalues_split
from bifurcation_engine.src.fixed_points_split import continuation_sweep_split
from bifurcation_engine.src.hopf_detector import HopfResult, detect_hopf
from bifurcation_engine.src.hopf_detector_split import (
    FoldNumericalResult,
    detect_fold_numerical,
)
from bifurcation_engine.src.shell_config import ShellConfig, default_shells
from bifurcation_engine.src.split_decay_config import SplitDecayConfig

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SUMMARY_PATH = REPORTS_DIR / "split_decay_sweep_summary.md"

N_L_STEPS_DEFAULT = 100
RHO_MIN = 0.05
RHO_MAX = 0.95
GAMMA_MULT_MIN = 1.0
GAMMA_MULT_MAX = 50.0

PROFILE_BUDGET_SECONDS = 90.0
PROFILE_DOWNGRADE_GRID = 10

# ``(label, (eta_SD, eta_SR, eta_RD))``. Baseline first, then two
# physically-motivated triplets where derelict collisions are more
# fragmenting than active-derelict and active-debris.
ETA_TRIPLETS: list[tuple[str, tuple[float, float, float]]] = [
    ("baseline", (1.0, 1.0, 1.0)),
    ("derelict_x2", (1.0, 2.0, 5.0)),
    ("derelict_x3", (1.0, 3.0, 10.0)),
]


# ---------------------------------------------------------------------------
# Per-cell record
# ---------------------------------------------------------------------------


@dataclass
class CellResult:
    shell_name: str
    rho_fraction: float
    gamma_multiplier: float
    eta_label: str
    eta_SD: float
    eta_SR: float
    eta_RD: float

    branch_found: bool
    n_branches: int
    n_points_lower: int
    n_complex_points: int

    hopf_found: bool
    hopf_outcome: str
    hopf_L_c: float
    hopf_omega: float
    hopf_dalpha_dL: float

    fold_found: bool
    L_fold: float

    min_alpha_complex: float
    max_trace_lower: float
    leading_alpha_max: float
    runtime_seconds: float
    error: str = ""


# ---------------------------------------------------------------------------
# Cell evaluation
# ---------------------------------------------------------------------------


def _select_lower_branch(branches: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray] | None:
    """Pick the lower coexistence branch (smallest mean D).

    Empty list -> ``None``. With a single branch we just return it.
    """
    if not branches:
        return None
    if len(branches) == 1:
        return branches[0]
    means = [float(np.mean(b["D_star"])) if b["D_star"].size else float("inf") for b in branches]
    idx = int(np.argmin(means))
    return branches[idx]


def evaluate_cell(
    shell: ShellConfig,
    rho_fraction: float,
    gamma_multiplier: float,
    eta_label: str,
    eta_triplet: tuple[float, float, float],
    n_L_steps: int,
) -> CellResult:
    """Run one ``(rho_fraction, gamma_multiplier, eta)`` cell."""
    eta_SD, eta_SR, eta_RD = eta_triplet
    t0 = time.perf_counter()

    try:
        cfg = SplitDecayConfig.from_shell(
            shell,
            rho_fraction=rho_fraction,
            gamma_multiplier=gamma_multiplier,
            eta_SD=eta_SD,
            eta_SR=eta_SR,
            eta_RD=eta_RD,
        )
    except ValueError as exc:
        return CellResult(
            shell_name=shell.shell_name,
            rho_fraction=rho_fraction,
            gamma_multiplier=gamma_multiplier,
            eta_label=eta_label,
            eta_SD=eta_SD,
            eta_SR=eta_SR,
            eta_RD=eta_RD,
            branch_found=False,
            n_branches=0,
            n_points_lower=0,
            n_complex_points=0,
            hopf_found=False,
            hopf_outcome="config_invalid",
            hopf_L_c=float("nan"),
            hopf_omega=float("nan"),
            hopf_dalpha_dL=float("nan"),
            fold_found=False,
            L_fold=float("nan"),
            min_alpha_complex=float("nan"),
            max_trace_lower=float("nan"),
            leading_alpha_max=float("nan"),
            runtime_seconds=time.perf_counter() - t0,
            error=str(exc),
        )

    L_max = cfg.effective_L_sweep_max
    L_grid = np.linspace(cfg.L_sweep_min, L_max, n_L_steps)

    branches = continuation_sweep_split(cfg, L_grid)
    n_branches = len(branches)
    lower = _select_lower_branch(branches)

    if lower is None or lower["L"].size < 2:
        return CellResult(
            shell_name=shell.shell_name,
            rho_fraction=rho_fraction,
            gamma_multiplier=gamma_multiplier,
            eta_label=eta_label,
            eta_SD=eta_SD,
            eta_SR=eta_SR,
            eta_RD=eta_RD,
            branch_found=False,
            n_branches=n_branches,
            n_points_lower=int(lower["L"].size) if lower is not None else 0,
            n_complex_points=0,
            hopf_found=False,
            hopf_outcome="no_branch",
            hopf_L_c=float("nan"),
            hopf_omega=float("nan"),
            hopf_dalpha_dL=float("nan"),
            fold_found=False,
            L_fold=float("nan"),
            min_alpha_complex=float("nan"),
            max_trace_lower=float("nan"),
            leading_alpha_max=float("nan"),
            runtime_seconds=time.perf_counter() - t0,
        )

    track = track_eigenvalues_split(lower, cfg)
    n_complex = int(np.sum(track["has_complex_pair"]))

    hopf_outcome = "no_complex_eigenvalues"
    hopf_found = False
    hopf_L_c = float("nan")
    hopf_omega = float("nan")
    hopf_dalpha = float("nan")
    if n_complex >= 1 and track["L"].size >= 2:
        try:
            result: HopfResult = detect_hopf(track["L"], track["alpha"], track["omega"])
            hopf_outcome = result.outcome
            hopf_found = bool(result.found)
            hopf_L_c = float(result.L_c) if result.L_c is not None else float("nan")
            hopf_omega = float(result.omega_at_Lc) if result.omega_at_Lc is not None else float("nan")
            hopf_dalpha = float(result.dalpha_dL_at_Lc) if result.dalpha_dL_at_Lc is not None else float("nan")
        except Exception as exc:  # pragma: no cover - defensive
            hopf_outcome = f"detect_hopf_error: {exc}"

    fold = detect_fold_numerical(lower, L_max)
    fold_found = bool(fold.found)
    L_fold = float(fold.L_fold) if fold.L_fold is not None else float("nan")

    alpha_complex = track["alpha_complex"]
    finite_alpha = alpha_complex[np.isfinite(alpha_complex)]
    min_alpha = float(np.min(finite_alpha)) if finite_alpha.size else float("nan")
    max_trace = float(np.max(track["trace"])) if track["trace"].size else float("nan")
    leading_alpha_max = float(np.max(track["leading_alpha"])) if track["leading_alpha"].size else float("nan")

    return CellResult(
        shell_name=shell.shell_name,
        rho_fraction=rho_fraction,
        gamma_multiplier=gamma_multiplier,
        eta_label=eta_label,
        eta_SD=eta_SD,
        eta_SR=eta_SR,
        eta_RD=eta_RD,
        branch_found=True,
        n_branches=n_branches,
        n_points_lower=int(lower["L"].size),
        n_complex_points=n_complex,
        hopf_found=hopf_found,
        hopf_outcome=hopf_outcome,
        hopf_L_c=hopf_L_c,
        hopf_omega=hopf_omega,
        hopf_dalpha_dL=hopf_dalpha,
        fold_found=fold_found,
        L_fold=L_fold,
        min_alpha_complex=min_alpha,
        max_trace_lower=max_trace,
        leading_alpha_max=leading_alpha_max,
        runtime_seconds=time.perf_counter() - t0,
    )


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


def run_sweep(
    shell: ShellConfig,
    grid: int,
    n_L_steps: int,
    eta_triplets: Iterable[tuple[str, tuple[float, float, float]]] = ETA_TRIPLETS,
) -> list[CellResult]:
    """Run the full ``grid x grid x len(eta_triplets)`` sweep on one shell."""
    rhos = np.linspace(RHO_MIN, RHO_MAX, grid)
    gammas = np.linspace(GAMMA_MULT_MIN, GAMMA_MULT_MAX, grid)

    results: list[CellResult] = []
    total = grid * grid * sum(1 for _ in eta_triplets)
    eta_list = list(eta_triplets)
    total = grid * grid * len(eta_list)
    counter = 0
    for label, eta in eta_list:
        for rho in rhos:
            for gm in gammas:
                counter += 1
                cell = evaluate_cell(
                    shell, float(rho), float(gm), label, eta, n_L_steps
                )
                results.append(cell)
                if counter % max(1, total // 20) == 0:
                    print(
                        f"  [{shell.shell_name}] {counter}/{total} cells done "
                        f"(latest runtime {cell.runtime_seconds:.2f}s, "
                        f"hopf_found={cell.hopf_found})"
                    )
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


CSV_FIELDS = [
    "shell_name",
    "rho_fraction",
    "gamma_multiplier",
    "eta_label",
    "eta_SD",
    "eta_SR",
    "eta_RD",
    "branch_found",
    "n_branches",
    "n_points_lower",
    "n_complex_points",
    "hopf_found",
    "hopf_outcome",
    "hopf_L_c",
    "hopf_omega",
    "hopf_dalpha_dL",
    "fold_found",
    "L_fold",
    "min_alpha_complex",
    "max_trace_lower",
    "leading_alpha_max",
    "runtime_seconds",
    "error",
]


def write_csv(shell: ShellConfig, results: list[CellResult]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"split_decay_sweep_{shell.shell_name}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            writer.writerow({field: getattr(r, field) for field in CSV_FIELDS})
    return path


def write_heatmaps(shell: ShellConfig, results: list[CellResult], grid: int) -> list[Path]:
    """One PNG per ``eta_label``: hopf_found mask on the rho x gamma grid."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return []

    paths: list[Path] = []
    rhos = np.linspace(RHO_MIN, RHO_MAX, grid)
    gammas = np.linspace(GAMMA_MULT_MIN, GAMMA_MULT_MAX, grid)
    for label, _eta in ETA_TRIPLETS:
        cell_subset = [r for r in results if r.eta_label == label]
        if not cell_subset:
            continue
        # Build a grid: rows -> rho, cols -> gamma.
        hopf_grid = np.zeros((grid, grid), dtype=float)
        alpha_grid = np.full((grid, grid), np.nan, dtype=float)
        for r in cell_subset:
            i = int(np.argmin(np.abs(rhos - r.rho_fraction)))
            j = int(np.argmin(np.abs(gammas - r.gamma_multiplier)))
            hopf_grid[i, j] = 1.0 if r.hopf_found else 0.0
            alpha_grid[i, j] = r.min_alpha_complex if math.isfinite(r.min_alpha_complex) else np.nan

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        ax = axes[0]
        im = ax.imshow(
            hopf_grid,
            origin="lower",
            aspect="auto",
            extent=(GAMMA_MULT_MIN, GAMMA_MULT_MAX, RHO_MIN, RHO_MAX),
            cmap="RdYlGn",
            vmin=0.0,
            vmax=1.0,
        )
        ax.set_xlabel("gamma_multiplier (x literature gamma)")
        ax.set_ylabel("rho_fraction (failure share of delta_S)")
        ax.set_title(f"Hopf found ({shell.shell_name}, eta={label})")
        plt.colorbar(im, ax=ax, label="hopf_found (0/1)")

        ax = axes[1]
        im = ax.imshow(
            alpha_grid,
            origin="lower",
            aspect="auto",
            extent=(GAMMA_MULT_MIN, GAMMA_MULT_MAX, RHO_MIN, RHO_MAX),
            cmap="viridis",
        )
        ax.set_xlabel("gamma_multiplier (x literature gamma)")
        ax.set_ylabel("rho_fraction")
        ax.set_title("min alpha (complex pair) on lower branch")
        plt.colorbar(im, ax=ax, label="min alpha")

        plt.tight_layout()
        path = REPORTS_DIR / f"split_decay_sweep_{shell.shell_name}_{label}.png"
        plt.savefig(path, dpi=120)
        plt.close(fig)
        paths.append(path)
    return paths


def write_summary(
    grid: int,
    profile_seconds: float,
    sweep_records: list[tuple[ShellConfig, list[CellResult]]],
) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    any_hopf = any(r.hopf_found for _shell, results in sweep_records for r in results)

    lines: list[str] = []
    lines.append("# Split-Decay Hopf-Hunt Sweep Report\n")
    lines.append("## Setup\n")
    lines.append(
        f"* Grid resolution: {grid} x {grid} per shell, per eta triplet.\n"
        f"* L sampling: {N_L_STEPS_DEFAULT} L points per cell.\n"
        f"* rho_fraction range: [{RHO_MIN}, {RHO_MAX}].\n"
        f"* gamma_multiplier range: [{GAMMA_MULT_MIN}, {GAMMA_MULT_MAX}].\n"
        f"* eta triplets evaluated: {[label for label, _ in ETA_TRIPLETS]}.\n"
        f"* Profile-gate time (Shell B, rho=0.5, gamma_mult=1.0, baseline eta): "
        f"{profile_seconds:.2f}s.\n"
    )
    lines.append("## Headline outcome\n")
    if any_hopf:
        lines.append(
            "**Hopf bifurcation detected** in at least one cell. The "
            "split-decay refinement unlocks a parameter regime in which "
            "the lower coexistence branch loses stability through a "
            "complex eigenvalue pair crossing zero before the saddle-node "
            "fold ends the branch. See per-shell tables below for the "
            "specific cells; downstream, run the followup sustained-limit-"
            "cycle integration at 1.01 * L_c to confirm.\n"
        )
    else:
        lines.append(
            "**No Hopf bifurcation detected** in any cell across all "
            "scanned shells. The trace-inequality argument from CLAUDE.md "
            "appears to extend to the corrected split-decay model: the "
            "lower coexistence branch is either real-spectrum or a stable "
            "spiral throughout, and ends in a saddle-node fold. The "
            "Kessler tipping point remains the fold under this refinement.\n"
        )

    lines.append("## Per-shell breakdown\n")
    for shell, results in sweep_records:
        n_total = len(results)
        n_hopf = sum(1 for r in results if r.hopf_found)
        n_complex = sum(1 for r in results if r.n_complex_points > 0)
        n_fold = sum(1 for r in results if r.fold_found)
        lines.append(f"### {shell.shell_name}\n")
        lines.append(
            f"* Cells: {n_total}\n"
            f"* Cells with complex eigenvalues on the lower branch: {n_complex}\n"
            f"* Cells with a saddle-node fold inside the L window: {n_fold}\n"
            f"* Cells with a Hopf bifurcation detected: {n_hopf}\n"
        )
        if n_hopf:
            lines.append("**Hopf cells:**\n")
            lines.append(
                "| rho_fraction | gamma_mult | eta_label | L_c | omega | dalpha/dL |"
            )
            lines.append("|---|---|---|---|---|---|")
            for r in results:
                if r.hopf_found:
                    lines.append(
                        f"| {r.rho_fraction:.3f} | {r.gamma_multiplier:.2f} | "
                        f"{r.eta_label} | {r.hopf_L_c:.3g} | {r.hopf_omega:.3g} | "
                        f"{r.hopf_dalpha_dL:.3g} |"
                    )
            lines.append("")
        lines.append(
            f"CSV: `reports/split_decay_sweep_{shell.shell_name}.csv` "
            f"(see also heatmaps `reports/split_decay_sweep_"
            f"{shell.shell_name}_*.png`)\n"
        )

    lines.append("## Trace diagnostic\n")
    lines.append(
        "`max_trace_lower` is the maximum value of `tr(J_split)` along the "
        "lower coexistence branch. CLAUDE.md's trace inequality predicts "
        "fold-domination when `tr` reaches zero from below at the same L "
        "as the fold. A genuine Hopf-permitting cell would show "
        "`tr` crossing zero strictly *before* the fold, i.e. "
        "`max_trace_lower > 0` while `min_alpha_complex < 0` somewhere "
        "deeper into the branch.\n"
    )

    SUMMARY_PATH.write_text("\n".join(lines))
    print(f"Wrote summary to {SUMMARY_PATH.relative_to(REPORTS_DIR.parent)}")


# ---------------------------------------------------------------------------
# Profile gate
# ---------------------------------------------------------------------------


def profile_one_cell(shell_B: ShellConfig, n_L_steps: int) -> float:
    """Time a single representative Shell-B cell. Returns wall seconds."""
    print(
        f"\n[profile] Running Shell B / rho_fraction=0.5 / gamma_mult=1.0 / "
        f"baseline eta with {n_L_steps} L points..."
    )
    cell = evaluate_cell(
        shell=shell_B,
        rho_fraction=0.5,
        gamma_multiplier=1.0,
        eta_label="baseline",
        eta_triplet=(1.0, 1.0, 1.0),
        n_L_steps=n_L_steps,
    )
    print(
        f"[profile] runtime = {cell.runtime_seconds:.2f}s  "
        f"branch_found={cell.branch_found}  "
        f"n_complex={cell.n_complex_points}  "
        f"hopf_found={cell.hopf_found}  "
        f"hopf_outcome={cell.hopf_outcome}"
    )
    return cell.runtime_seconds


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--shells",
        default="B,C",
        help="Comma-separated shell letters or names (default: B,C).",
    )
    p.add_argument(
        "--grid",
        type=int,
        default=20,
        help="Per-axis grid resolution; downgrades to 10 if profile gate trips.",
    )
    p.add_argument(
        "--n-L-steps",
        type=int,
        default=N_L_STEPS_DEFAULT,
        help="Number of L points per continuation sweep.",
    )
    p.add_argument(
        "--profile-only",
        action="store_true",
        help="Run only the profile gate and exit.",
    )
    p.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip the profile gate (use the requested grid as-is).",
    )
    return p.parse_args()


def _resolve_shells(spec: str, all_shells: list[ShellConfig]) -> list[ShellConfig]:
    by_letter = {
        s.shell_name.split("_")[1] if "_" in s.shell_name else s.shell_name: s
        for s in all_shells
    }
    by_full = {s.shell_name: s for s in all_shells}
    out: list[ShellConfig] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if token in by_full:
            out.append(by_full[token])
        elif token in by_letter:
            out.append(by_letter[token])
        else:
            raise SystemExit(
                f"Unknown shell name {token!r}. Available: "
                f"{[s.shell_name for s in all_shells]}"
            )
    return out


def main() -> None:
    args = parse_args()
    all_shells = default_shells()
    targets = _resolve_shells(args.shells, all_shells)
    shell_B = next((s for s in all_shells if "800km" in s.shell_name or s.shell_name.endswith("_B")), None)

    grid = args.grid
    profile_seconds = float("nan")
    if not args.skip_profile:
        if shell_B is None:
            print("[profile] Shell B not found among defaults; skipping profile gate.")
        else:
            profile_seconds = profile_one_cell(shell_B, args.n_L_steps)
            if profile_seconds > PROFILE_BUDGET_SECONDS:
                print(
                    f"[profile] WARNING: cell took {profile_seconds:.1f}s > "
                    f"{PROFILE_BUDGET_SECONDS:.0f}s budget. "
                    f"Downgrading grid resolution from {grid} to "
                    f"{PROFILE_DOWNGRADE_GRID}."
                )
                grid = PROFILE_DOWNGRADE_GRID

    if args.profile_only:
        return

    sweep_records: list[tuple[ShellConfig, list[CellResult]]] = []
    for shell in targets:
        print(f"\n=== Sweeping {shell.shell_name} on {grid}x{grid} grid x {len(ETA_TRIPLETS)} eta triplets ===")
        results = run_sweep(shell, grid, args.n_L_steps)
        csv_path = write_csv(shell, results)
        png_paths = write_heatmaps(shell, results, grid)
        print(f"  wrote CSV: {csv_path.relative_to(REPORTS_DIR.parent)}")
        for p in png_paths:
            print(f"  wrote heatmap: {p.relative_to(REPORTS_DIR.parent)}")
        sweep_records.append((shell, results))

    write_summary(grid, profile_seconds, sweep_records)


if __name__ == "__main__":
    main()
