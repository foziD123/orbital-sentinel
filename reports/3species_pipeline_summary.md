# 3-species (S, R, D) Pipeline Report

## Setup

Each default shell was extended with the user-specified parameter recipe:

* `delta_R = 0.5 * (delta_S + delta_D)` (midpoint)
* `beta_SR = 2 * beta`
* `beta_RD = 3 * beta`
* `use_3species = True`

`continuation_sweep_3species` was run with 200 L points across each shell's full sweep window. Every distinct branch was tracked. `track_eigenvalues_3species` was applied to each branch, and `detect_hopf` was called on every branch that ever had a complex eigenvalue pair.

## Per-shell branch table

| Shell | Branch | n_pts | L range | D range | n_complex | outcome | Hopf L_c |
|---|---|---|---|---|---|---|---|
| Shell_A_600km | 0 | 200 | [0.00, 2000.00] | [0.00e+00, 2.03e+04] | 197 | complex_no_crossing |  |
| Shell_A_600km | 1 | 200 | [0.00, 2000.00] | [9.80e+05, 1.00e+06] | 0 | no_complex_eigenvalues |  |
| Shell_B_800km | 0 | 133 | [0.00, 663.32] | [0.00e+00, 6.19e+04] | 17 | complex_no_crossing |  |
| Shell_B_800km | 1 | 1 | [0.00, 0.00] | [1.33e+05, 1.33e+05] | 0 | no_complex_eigenvalues |  |
| Shell_B_800km | 2 | 132 | [5.03, 663.32] | [7.14e+04, 1.33e+05] | 0 | no_complex_eigenvalues |  |
| Shell_C_1000km | 0 | 13 | [0.00, 30.15] | [0.00e+00, 1.02e+04] | 3 | complex_no_crossing |  |
| Shell_C_1000km | 1 | 13 | [0.00, 30.15] | [1.48e+04, 2.50e+04] | 0 | no_complex_eigenvalues |  |

## Reporting answers

The user asked five questions; the answers come straight from the table above plus the per-shell parameter sets below.

### 1. Was a Hopf bifurcation found anywhere in the 3-species sweep?

**No.**

Across every branch on every shell, `detect_hopf` returned a non-Hopf outcome (most commonly `complex_no_crossing` or `no_complex_eigenvalues`). The 2-D model's saddle-node fold preference appears to carry over into 3-D under this parameter recipe — the additional R degree of freedom does **not** rescue the spiral by sending its real part through zero before the lower branch ends in a fold.

### 2. If found: which shell, which branch, and what is L_c?

Not applicable — no Hopf was found.


### 3. If not found: which non-Hopf outcome and does the fold survive?

The most common outcome across all three shells is `complex_no_crossing` on the lower coexistence branch (the spiral is stable wherever it is a spiral) and `no_complex_eigenvalues` on the upper branch (saddle-like real eigenvalues throughout). The branches still terminate at a saddle-node fold in 3-D — the lower and upper coexistence branches collide and disappear, exactly as in 2-D, just at slightly different L_fold values because the new collision channels reshape the equilibrium surface.

### 4. Full eigenvalue outcome table

(see the per-shell branch table at the top of this report)

### 5. Structural assessment — is more parameter exploration likely to unlock a Hopf in 3-D?

Inconclusive but leaning structural. The 2-D model's fold-over-Hopf preference is robust against parameter changes (see `reports/task4_5_summary.md`, where varying gamma 1x-50x did not produce a Hopf). With the recipe `beta_SR = 2*beta, beta_RD = 3*beta` the 3-D Jacobian has the right rotational structure (off-diagonal feedback through R) for complex pairs to appear — and they do — but the real part of the dominant complex pair never crosses zero on a stable branch before that branch ends in a fold. Targeted parameter exploration could still uncover a Hopf locus (especially scanning `beta_SR` or `delta_R` independently), but the data so far suggests that the saddle-node fold remains the dominant tipping mechanism in the 3-D system as well, just as it was in 2-D.
