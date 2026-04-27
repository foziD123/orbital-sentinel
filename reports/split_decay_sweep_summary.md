# Split-Decay Hopf-Hunt Sweep Report

## Setup

* Grid resolution: 20 x 20 per shell, per eta triplet.
* L sampling: 100 L points per cell.
* rho_fraction range: [0.05, 0.95].
* gamma_multiplier range: [1.0, 50.0].
* eta triplets evaluated: ['baseline', 'derelict_x2', 'derelict_x3'].
* Profile-gate time (Shell B, rho=0.5, gamma_mult=1.0, baseline eta): nans.

## Headline outcome

**No Hopf bifurcation detected** in any cell across all scanned shells. The trace-inequality argument from CLAUDE.md appears to extend to the corrected split-decay model: the lower coexistence branch is either real-spectrum or a stable spiral throughout, and ends in a saddle-node fold. The Kessler tipping point remains the fold under this refinement.

## Per-shell breakdown

### Shell_B_800km

* Cells: 1200
* Cells with complex eigenvalues on the lower branch: 1064
* Cells with a saddle-node fold inside the L window: 1074
* Cells with a Hopf bifurcation detected: 0

CSV: `reports/split_decay_sweep_Shell_B_800km.csv` (see also heatmaps `reports/split_decay_sweep_Shell_B_800km_*.png`)

### Shell_C_1000km

* Cells: 1200
* Cells with complex eigenvalues on the lower branch: 74
* Cells with a saddle-node fold inside the L window: 121
* Cells with a Hopf bifurcation detected: 0

CSV: `reports/split_decay_sweep_Shell_C_1000km.csv` (see also heatmaps `reports/split_decay_sweep_Shell_C_1000km_*.png`)

## Trace diagnostic

`max_trace_lower` is the maximum value of `tr(J_split)` along the lower coexistence branch. CLAUDE.md's trace inequality predicts fold-domination when `tr` reaches zero from below at the same L as the fold. A genuine Hopf-permitting cell would show `tr` crossing zero strictly *before* the fold, i.e. `max_trace_lower > 0` while `min_alpha_complex < 0` somewhere deeper into the branch.
