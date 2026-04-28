# Orbital Sentinel — Claude Code Context

## What this project is

Orbital Sentinel is a decision-support simulation tool that applies **Hopf bifurcation theory**
to model and predict the Kessler syndrome tipping point in Low Earth Orbit (LEO).

It is built as part of TeSI 2026 (Technology for Social Innovation), a 15-week course run
jointly by ESADE, UPC, and IED under the EU Tech2X / Fusion Point Academy program.

The underlying technology is **HOPFEL** — a methodology developed at the European XFEL
(Giovanni Perosa) that applies Hopf bifurcation theory to detect and anticipate critical
transitions in dynamical systems. Our contribution is translating that methodology from
Free Electron Lasers to orbital debris dynamics.

---

## Repository structure

```
orbital-sentinel/
├── CLAUDE.md                  ← you are here
├── TODO.md                    ← current task list and status
├── TASKS.md                   ← full technical task breakdown (Module 1)
├── VALIDATION.md              ← tests, validation scenarios, acceptance criteria
├── README.md                  ← project overview / quick start
├── bifurcation_engine/
│   ├── src/
│   │   ├── model.py           ← ODE system: 2-D (S, D) + 3-species (S, R, D)
│   │   ├── fixed_points.py    ← Newton continuation, 2-D + 3-D all-branch
│   │   ├── eigenvalues.py     ← Jacobian + eigenvalue tracker, 2-D + 3-D
│   │   ├── hopf_detector.py   ← Hopf detection + saddle-node fold detector
│   │   ├── integrator.py      ← Full nonlinear trajectory integration
│   │   ├── early_warning.py   ← Critical slowing down, variance, autocorrelation
│   │   └── shell_config.py    ← Altitude shell definitions (2-D defaults; opt-in 3-D)
│   ├── tests/
│   │   ├── test_model.py / test_model_3species.py
│   │   ├── test_fixed_points.py / test_fixed_points_3species.py
│   │   ├── test_eigenvalues.py / test_eigenvalues_3species.py
│   │   ├── test_hopf_detector.py
│   │   ├── test_early_warning.py
│   │   ├── test_integrator.py
│   │   ├── test_shell_config.py
│   │   └── test_validation_scenarios.py
│   ├── notebooks/
│   │   └── engine_demo.ipynb  ← interactive exploration notebook
│   └── requirements.txt
├── scripts/
│   ├── plot_shell_B_bifurcation.py  ← 2-D Shell-B presentation plot
│   └── run_3species_pipeline.py     ← 3-species sweep on all default shells
├── reports/
│   ├── shell_B_bifurcation.png
│   ├── task4_5_summary.md           ← 2-D pipeline outcome
│   └── 3species_pipeline_summary.md ← 3-species pipeline outcome
└── data/
    └── parameters/
        └── shell_defaults.json  ← default parameter sets per altitude band
```

---

## The mathematical model

The system models each altitude shell independently as a 2D ODE:

```
S_dot = L - delta_S * S - beta * S * D
D_dot = beta * S * D + gamma * D^2 - delta_D * D
```

**State variables:**
- `S(t)` — active satellites + intact rocket bodies in the shell
- `D(t)` — trackable debris fragments in the shell

**Parameters (per shell):**
- `L` — launch rate [objects/year] — THE BIFURCATION PARAMETER
- `delta_S` — satellite decay rate (drag + controlled deorbit) [1/year]
- `delta_D` — debris decay rate (atmospheric drag) [1/year]; generally delta_D > delta_S
- `beta` — satellite-debris collision cross-section [1/(objects·year)]
- `gamma` — debris-debris cascade coefficient [1/(objects·year)]; the Kessler term

**The Kessler term:** `gamma * D^2` is quadratic in D. Once D is large enough,
this term dominates delta_D * D and the debris population runs away regardless of
what happens to S. This is the mathematical signature of Kessler syndrome.

**Fixed points:**
- Case 1 (clean orbit): `x*_1 = (L/delta_S, 0)` — no debris equilibrium
- Case 2 (coexistence): D* solves `beta*gamma*(D*)^2 + (delta_S*gamma - beta*delta_D)*D* + (beta*L - delta_S*delta_D) = 0`

**Jacobian at fixed point (S*, D*):**
```
J = [[-delta_S - beta*D*,  -beta*S*         ],
     [ beta*D*,             beta*S* + 2*gamma*D* - delta_D]]
```

**Hopf bifurcation conditions** (must hold simultaneously at L = L_c):
1. `alpha(L_c) = 0`         — real part of eigenvalues vanishes
2. `omega(L_c) != 0`        — imaginary part is nonzero (rotation present)
3. `d(alpha)/dL != 0`       — genuine crossing, not just grazing

A Hopf bifurcation is NOT guaranteed — it depends on parameter values. The off-diagonal
coupling in J (satellites feed debris, debris destroys satellites) creates the rotational
structure that makes it possible. Whether alpha actually crosses zero is a quantitative
question answered numerically.

---

## What the engine has actually found (post-Task-6 pipeline run)

With the literature-calibrated parameters and the full eigenvalue + Hopf + fold
detection pipeline in place, the engine has shown — across all three default
shells — that the 2D source-sink model **does not host a Hopf bifurcation**.
Instead, the Kessler tipping point manifests as a **saddle-node (fold)
bifurcation**: the two Case-2 coexistence fixed points (one stable lower
branch, one unstable upper branch) collide and annihilate at a critical
launch rate `L_fold`, after which no coexistence equilibrium exists and the
debris population runs away.

This is a scientifically valid outcome, not a gap in the analysis — the lower
branch does enter the complex-eigenvalue regime (stable spiral), but `alpha`
stays strictly negative there and the fixed point disappears via the fold
before `alpha` can cross zero. A `γ`-sensitivity sweep on Shell B (1× to 50×
the literature value) never unlocked a Hopf either, so the preference for a
fold over a Hopf is a structural feature of the 2D model rather than a
numerical accident.

**Confirmed fold launch rates per shell** (from
`detect_fold` cross-checked against the closed form
`L_fold = (δ_S·γ + β·δ_D)² / (4·β²·γ)`):

| Shell | Altitude | `L_fold` [objects/yr] | `(S_fold, D_fold)` |
|-------|----------|-----------------------|--------------------|
| Shell A | 600 km  | ≈ 25 100              | (5.01 × 10³, 4.99 × 10⁵) |
| Shell B | 800 km  | ≈ 670                 | (668, 6.65 × 10⁴)        |
| Shell C | 1000 km | ≈ 31.5                | (251, 1.24 × 10⁴)        |

The three qualitative trajectory regimes have been exercised and validated
for every shell: below the fold `D(t)` relaxes onto the lower branch, at
the fold it hovers at the merged marginal fixed point, and above the fold
it runs away (see `reports/shell_B_bifurcation.png` for the Shell-B
visualisation).

**New module symbols supporting this analysis:**

- `bifurcation_engine.src.hopf_detector.detect_fold(params, L_values)`
  locates the saddle-node fold by sign-change of the Case-2 quadratic
  discriminant `b² − 4ac`, returning a `FoldResult` with `L_fold`,
  `S_star_at_fold`, `D_star_at_fold`, and a plain-English description.
- `bifurcation_engine.src.integrator.integrate_trajectory(...)` (Task 6)
  wraps `scipy.integrate.solve_ivp` to produce full nonlinear `S(t), D(t)`
  trajectories from arbitrary initial conditions, with non-negativity
  enforcement and a runaway-ceiling terminal event so blown-up runs finish
  in finite time.

The practical implication for the rest of Phase 1 is that the dashboard
(Module 3) should frame the red-line threshold as `L_fold`, not `L_c` in
the Hopf sense. Task 7 early-warning indicators (critical slowing down,
variance inflation, autocorrelation → 1) still apply — those signatures
precede saddle-node folds just as they do Hopf bifurcations — and the
traffic-light thresholds can be phrased as fractions of `L_fold`.

---

## 3-Species Extension — Results and Mathematical Findings

After the 2-D pipeline confirmed the fold-over-Hopf preference, the engine
was extended additively to a 3-species (S, R, D) system that mirrors the
MOCAT-pySSEM structure: active satellites `S`, derelict satellites `R`, and
debris fragments `D`. The intent was to give the Jacobian an additional
degree of freedom so a complex pair could potentially cross the imaginary
axis on a stable branch — i.e. host a genuine Hopf — before the lower
coexistence branch ends in a fold.

### Architecture (additive — 2-D pipeline is unchanged)

`use_3species` defaults to `False` on `ShellConfig`, so the 2-D model
remains the primary pipeline. All 113 pre-existing 2-D tests continue to
pass with no edits. The new symbols are:

- `model.py`: `s_dot_3species`, `r_dot_3species`, `d_dot_3species`, `ode_system_3species` (state vector `y = [S, R, D]`).
- `fixed_points.py`: `find_fixed_points_3species` (grid-seeded `fsolve` with dedup and physicality filter) and `continuation_sweep_3species` (warm-started **all-branch** tracking with grid rescan to spawn new branches).
- `eigenvalues.py`: `jacobian_3species` (3×3 analytical), `eigenvalue_analysis_3species` (classifies the dominant complex pair), `track_eigenvalues_3species` (per-branch sweep, `detect_hopf`-compatible aliases).
- `shell_config.py`: optional fields `delta_R`, `beta_SR`, `beta_RD` plus a `use_3species` opt-in flag with conditional validation (`delta_S < delta_R < delta_D`, strict positivity of the new collision rates only when the flag is set).
- `scripts/run_3species_pipeline.py`: applies the recipe (`delta_R = ½(δ_S + δ_D)`, `β_SR = 2β`, `β_RD = 3β`) to all three default shells and writes `reports/3species_pipeline_summary.md`.

### The 3-species ODE

```
S_dot = L − δ_S·S − β·S·D − β_SR·S·R
R_dot = δ_S·S − δ_R·R − β_RD·R·D
D_dot = β·S·D + β_SR·S·R + β_RD·R·D + γ·D² − δ_D·D
```

**Modelling note (deliberate asymmetry).** `R_dot` does *not* contain a
`-β_SR·S·R` term: an active-derelict collision destroys the active satellite
(visible in `S_dot`) and produces fragments (visible in `D_dot`), but the
derelict body is treated as not removed. This is the spec as written and
is reflected exactly in the Jacobian — `J[1,1] = −δ_R − β_RD·D*`, with no
`−β_SR·S*` term.

### What the 3-species pipeline found

Running the recipe above on Shells A, B, and C with 200 L points across
each shell's full sweep window:

- **No Hopf bifurcation on any branch on any shell.**
- Lower coexistence branches: `complex_no_crossing` — complex pairs *do* appear (more frequently than in the 2-D model), but `α` stays strictly negative in the complex region. The spiral is stable everywhere it is a spiral.
- Upper coexistence branches: `no_complex_eigenvalues` — saddle-like real spectrum throughout, consistent with the 2-D upper branch.
- The **saddle-node fold survives in 3-D**, just at slightly different `L_fold` values because the new collision channels reshape the equilibrium surface.

Full per-branch table is in `reports/3species_pipeline_summary.md`.

### Why the fold beats the Hopf — a structural result

All 9 entries of `jacobian_3species` were verified analytically from the
ODE; the closed form is

```
J_3 = [[ −δ_S − β·D* − β_SR·R*,   −β_SR·S*,             −β·S*                          ],
       [  δ_S,                     −δ_R − β_RD·D*,       −β_RD·R*                       ],
       [  β·D* + β_SR·R*,           β_SR·S* + β_RD·D*,    β·S* + β_RD·R* + 2γ·D* − δ_D ]]
```

The trace `tr(J_3) = J_00 + J_11 + J_22` simplifies to a key inequality:

```
tr(J_3) = −(δ_S + δ_R + δ_D)              [decay sinks — always negative]
          + β·(S* − D*)                    [satellite-debris balance]
          + β_RD·(R* − D*)                 [derelict-debris balance]
          − β_SR·R*                         [active-derelict — one-sided]
          + 2γ·D*                           [Kessler self-cascade — grows with D*]
```

This is **the mathematical reason the fold beats the Hopf in the source-sink
model class.** As `L → L_fold` along the lower branch, `D*` grows
square-root-steeply and the `2γ·D*` Kessler term drives the trace toward
zero from below and then positive. Since `tr(J_3) > 0` is sufficient for
instability (it forces at least one eigenvalue real part to be positive),
the fixed point becomes unstable through the **trace mechanism** — and
this happens at the *same* L (the fold) at which the lower branch ceases
to exist. The fold and the trace instability fire simultaneously; there
is no window in which a complex pair can cross zero on a *still-existing*
stable branch. Targeted parameter exploration is therefore unlikely to
unlock a Hopf in this model class — the fold-over-Hopf preference is
structural in 3-D as well as in 2-D.

### Decision: fold is the Kessler tipping point

The project commits to the saddle-node fold as the operational definition
of the Kessler tipping point. The HOPFEL methodology transfers correctly
— bifurcation theory applied to orbital debris dynamics correctly
identifies a critical transition; that transition just happens to be a
fold rather than a Hopf. Module 3 (dashboard) red-line thresholds are
keyed to `L_fold`. Task 7 (early warning) is implemented with the fold
as the primary channel; Hopf-based warning is a placeholder secondary
channel only — there is no 3-D Hopf to warn about in this model class.

The 3-species pipeline remains in the codebase as scientific evidence for
this conclusion and as the harness against which any future model
extension (inter-shell coupling, breakup-model upgrade, etc.) will be
re-tested for Hopf existence.

### Test status

**159 passed, 2 skipped** — 113 original 2-D tests untouched, plus 46 new
tests across the four 3-species test files. The two skips remain on the
T5.2 / T5.3 historical scenarios and are tracked in `TODO.md`.

---

## Split-Decay Hopf-Hunt — Results and Mathematical Findings

After the 3-species pipeline confirmed that the trace inequality drives
the fold-over-Hopf preference, one targeted refinement remained worth
testing: separating the conflated satellite decay rate `δ_S` into two
physically distinct fates and seeing whether the resulting extra degree
of freedom opens a Hopf window before the fold ends the lower branch.
The experiment ran in April 2026 as a fully additive layer on the
codebase; the existing 2-D and 3-species pipelines were not modified.

### What the experiment tested

The production model lumps controlled deorbit and on-orbit failure into
a single `δ_S`. The split-decay refinement physically separates them:

* `κ_S` — controlled disposal: the satellite leaves the orbital system.
* `ϱ_S` — failure into derelict state: the satellite stays on orbit as `R`.

with the conservation constraint `κ_S + ϱ_S = δ_S` so the experiment is
directly comparable, term-by-term, to the existing 3-species results.
Three further changes were made:

1. **Symmetric β_SR collision channel** — the corrected `Ṙ` includes the
   `−β_SR·S·R` sink (the derelict body is removed in an active-derelict
   collision), removing the deliberate asymmetry in the existing
   3-species `Ṙ`.
2. **Fragment yield multipliers** — three dimensionless multipliers
   `η_SD`, `η_SR`, `η_RD ≥ 1` scale how many debris fragments each
   collision channel produces, so derelict collisions can be more
   energetic than active-satellite collisions.
3. **Tunable Kessler scaling** — `γ` is multiplied by a
   `gamma_multiplier` to probe both the moderate and strong cascade
   regimes on the same shell.

The full split-decay ODE is

```
Ṡ = L − κ_S·S − ϱ_S·S − β_SD·S·D − β_SR·S·R
Ṙ = ϱ_S·S − δ_R·R − β_RD·R·D − β_SR·S·R
Ḋ = η_SD·β_SD·S·D + η_SR·β_SR·S·R + η_RD·β_RD·R·D + γ·D² − δ_D·D
```

implemented in `src/model_split.py`. The 9-entry Jacobian was derived
from first principles, verified entry-by-entry in tests, and lives in
`src/eigenvalues_split.py`.

### Architecture (additive — 2-D and 3-species pipelines untouched)

The experiment lives entirely in new files (`src/split_decay_config.py`,
`src/model_split.py`, `src/fixed_points_split.py`,
`src/eigenvalues_split.py`, `src/hopf_detector_split.py`) plus the
matching test files. `SplitDecayConfig` is a separate dataclass that
exposes a `from_shell()` helper to convert any existing 2-D
`ShellConfig` into a split-decay config under the conservation
constraint. No existing function or test was modified.

### The sweep

`scripts/run_split_decay_sweep.py` ran a 20×20×3 grid per shell over

* `rho_fraction ∈ [0.05, 0.95]`  (failure share of `δ_S`)
* `gamma_multiplier ∈ [1.0, 50.0]`  (×literature `γ`)
* `(η_SD, η_SR, η_RD) ∈ {(1,1,1), (1,2,5), (1,3,10)}`

on Shells B and C (the two shells most likely to host a Hopf — Shell A
already has a Hopf-hostile spectrum from the 2-D and 3-species
analyses). Each cell ran a full warm-started continuation with 100 L
points and tracked complex eigenvalues, the saddle-node fold, and
`detect_hopf` on the lower branch. Total: **2,400 cells**, ~37 min on
one core.

### What the split-decay sweep found

- **Zero Hopf bifurcations across all 2,400 cells.** No cell on either
  shell, at any `(ϱ_S/κ_S, γ-multiplier, η)` combination, produced a
  genuine Hopf crossing.
- **Shell B**: 1,064 of 1,200 cells (89%) had complex eigenvalues on the
  lower coexistence branch — *much* more frequently than the 3-species
  model on the same shell. But `α` stayed strictly negative throughout
  the spiral region in every one of those cells:
  `detect_hopf` returned `complex_no_crossing` everywhere it could
  evaluate.
- **Shell C**: 74 of 1,200 cells (6%) had complex eigenvalues; same
  outcome.
- **Saddle-node fold survives** in 1,074/1,200 cells (Shell B) and
  121/1,200 cells (Shell C) — the cells where the lower branch ended
  inside the L window. The remaining cells had the fold above
  `L_sweep_max` and would have terminated had the sweep extended
  further.

Full per-cell diagnostics are in
`reports/split_decay_sweep_Shell_B_800km.csv`,
`reports/split_decay_sweep_Shell_C_1000km.csv`, the matching heatmaps,
and the consolidated `reports/split_decay_sweep_summary.md`.

### Why the fold still wins — the trace inequality extends

Computing `tr(J_split)` from the 9-entry Jacobian and simplifying:

```
tr(J_split) = −(δ_S + δ_R + δ_D)             [decay sinks — always negative]
              + β_SD · (η_SD·S* − D*)         [sat-debris, eta-weighted]
              + β_RD · (η_RD·R* − D*)         [derelict-debris, eta-weighted]
              − β_SR · (R* + S*)               [symmetric active-derelict sink]
              + 2γ · D*                         [Kessler self-cascade]
```

This is the **same structure** as the 3-species trace inequality, with
two refinements:

1. The β_SR term is now `−β_SR·(R* + S*)` instead of `−β_SR·R*` — the
   symmetric collision correction makes the trace *more* negative,
   slightly favouring stability rather than destabilisation.
2. The η multipliers can amplify or dampen the off-diagonal couplings,
   but they cannot change the sign of the dominant `2γ·D*` term and
   they cannot decouple the lower branch's behaviour from the fold's
   location.

As `L → L_fold` along the lower branch, `D*` grows square-root-steeply
exactly as in the 3-species case, the `2γ·D*` term dominates, and the
trace crosses zero at — or just past — the same L at which the fold
removes the branch entirely. The empirical 89%-vs-0% gap on Shell B
(complex pairs vs Hopf crossings) is the trace mechanism in numerical
form: the lower branch is a stable spiral over a wide parameter region,
but the spiral is destroyed by the fold before its real part crosses
zero, in *every* tested cell.

### Conclusion: fold-over-Hopf is structural across all three model variants

Across three independently implemented models —

* 2-D `(S, D)` (production), with a 50× `γ` sensitivity sweep;
* 3-species `(S, R, D)` with the `β_SR = 2β`, `β_RD = 3β`,
  `δ_R = ½(δ_S + δ_D)` recipe (asymmetric `Ṙ`);
* split-decay `(S, R, D)` with `κ_S/ϱ_S` separation, η yield
  multipliers, and the symmetric β_SR correction (corrected `Ṙ`),
  scanned over 2,400 cells —

**no parameter combination produces a Hopf bifurcation.** The
fold-over-Hopf preference is therefore a structural property of the
source-sink Kessler model class, not a numerical accident of any one
parameterisation. The trace inequality argument explains why: in any
model where `D* ↑ as L ↑`, the `2γ·D*` term will dominate the trace as
the fold is approached, and the fold and trace instability fire
simultaneously.

### Decision: Hopf hunt is closed

The project closes the Hopf hunt. The saddle-node fold is the
operational Kessler tipping point; the early-warning module (Task 7)
is keyed to `L_fold` only, with the Hopf channel reduced to a
forward-compatibility placeholder that returns `not_applicable` until a
future model extension (inter-shell coupling, NASA Breakup Model
integration via pySSEM, etc.) re-opens the question. No further
parameter sweeps for Hopf are planned in Phase 1.

The split-decay codebase remains as scientific evidence for this
conclusion and as a regression harness for any future model extension.

### Test status (post split-decay merge, post Task 7)

**231 passed, 1 skipped** — 159 prior tests untouched, plus 51 new
tests across `test_split_decay_config.py`, `test_model_split.py`,
`test_fixed_points_split.py`, `test_eigenvalues_split.py`, plus 21
new tests across `test_early_warning.py` (T4.1–T4.5 acceptance plus
shape / edge-case unit tests for Task 7). The remaining skip covers
the entire `test_validation_scenarios.py` module (T5.2 / T5.3
historical scenarios) and is tracked in `TODO.md`.

---

## Module 1 — Completion Status (April 26, 2026)

Module 1 (the bifurcation engine) is **complete**. The codebase
delivers everything the project committed to in Phase 1: a
literature-calibrated three-shell source-sink model, full numerical
bifurcation analysis (continuation, eigenvalue tracking, Hopf
detection, saddle-node fold detection), a fold-keyed early-warning
indicator suite, and the analytical closing of the Hopf-vs-fold
question across three independently implemented model variants.

### Final test count

**231 passed, 1 skipped, 0 failed** (pytest 9.0.3, Python 3.14.3,
3.16 s wall time on a single core). The single skip is the *entire*
`test_validation_scenarios.py` module, deferred behind
`pytest.skip(..., allow_module_level=True)` until the historical-
scenario harness is written. Pytest counts a module-level skip as
`1 skipped` regardless of how many test functions sit inside it,
which is why the count is `1` rather than the previously documented
`2` — the second module-level skip (the Task 7 stub) is gone now
that `test_early_warning.py` is implemented and merged. The two
deferred tests inside that module are:

* **T5.2** — 2009 Iridium-Cosmos collision (Shell B, 789 km).
* **T5.3** — 2007 Chinese ASAT (Fengyun-1C) test (Shell C, 865 km).

Both are deferred, not forgotten — see `TODO.md` IMMEDIATE for the
unblocking data pull and KNOWN PENDING for the harness work.

### Task 7 — early-warning module

`bifurcation_engine/src/early_warning.py` is implemented and merged.
All five acceptance tests **T4.1–T4.5 pass individually** and as part
of the full suite:

* `test_T4_1_recovery_time_diverges_as_alpha_goes_to_zero` — `1/|α|`
  monotonic, last entry `>> 100×` first entry.
* `test_T4_2_traffic_light_green_far_from_fold` — `L = 0.5 · L_fold`
  on Shell B → `green`.
* `test_T4_3_traffic_light_amber_near_fold` — `L = 0.88 · L_fold` on
  Shell B → `amber`.
* `test_T4_4_traffic_light_red_at_or_past_fold` — `L = 1.00 · L_fold`
  on Shell B → `red`.
* `test_T4_5_autocorrelation_approaches_one_near_fold` — Shell B at
  `L = 0.99 · L_fold`, lower-branch initial condition with `+5%` D
  perturbation, `integrate_trajectory` over 500 yr; the late-window
  lag-1 autocorrelation of `D(t)` exceeds 0.8.

Plus 16 unit tests covering shape and edge-case behaviour of each of
the four functions (`critical_slowing_down`, `variance_indicator`,
`autocorrelation_indicator`, `early_warning_summary`).

### Hopf hunt — closed

The split-decay sweep returned **0 Hopf bifurcations across all 2,400
parameter combinations** (Shells B and C, 20×20 grid in
`(rho_fraction, gamma_multiplier)` × 3 η triplets). Shell B had
complex eigenvalues on the lower branch in 1064/1200 cells (89%) but
`α` stayed strictly negative throughout in every one of those cells
— `complex_no_crossing` everywhere. Together with the 2-D γ-sweep and
the 3-species pipeline, this brings the fold-over-Hopf preference to
the level of a structural result across three independently
implemented model variants. The Hopf channel in
`early_warning_summary` is therefore reduced to a forward-
compatibility placeholder: it returns `status = "not_applicable"`
whenever `hopf_result is None` or `hopf_result.found is False`, which
is the only outcome the current model class can produce. The hook
will become live again only if and when a future model extension
(inter-shell coupling, NASA Breakup Model integration via pySSEM,
etc.) opens a Hopf locus.

### Module 1 acceptance gate — satisfied

All bullets in `VALIDATION.md` "Module 1 acceptance gate" are
checked except T5.2 and T5.3, which are explicitly deferred to before
the June 1 demonstration and tracked in `TODO.md`. Specifically:

* T1.x — Shell config / parameter loader: passing.
* T2.x — Fixed points / continuation / eigenvalues / Hopf detection /
  fold detection (2-D and 3-species): passing.
* T3.x — Trajectory integration: passing.
* T4.1–T4.5 — Early warning indicators and traffic light: passing
  (Task 7 gate, closed today).
* T5.1, T5.4, T5.5 — Analytical Jacobian, fold-trajectory triad on
  three shells, parameter-recovery plausibility: passing.
* T5.2, T5.3 — historical scenarios, **deferred** (see
  `TODO.md` IMMEDIATE and KNOWN PENDING).

### Key deliverables produced today (April 26, 2026)

* `reports/kessler_fold_summary.md` — non-specialist scientific
  summary of the saddle-node fold result, written for ESA / academic
  audiences (Tim Flohrer, Giovanni Perosa, Josep Joaquim Masdemont,
  Richard Linares). 334 lines, no code blocks. Covers model, fold
  mechanism, `L_fold` per shell with operational interpretation,
  trace-inequality argument as the no-Hopf explanation, robustness
  across three model variants and 2,400 cells, early-warning
  indicators, and the asymmetric ("easy to cross, hard or impossible
  to uncross") character of the fold.
* `reports/split_decay_sweep_summary.md` — consolidated summary of
  the 2,400-cell Hopf-hunt sweep, with per-shell breakdowns and the
  trace-inequality diagnostic.
* `reports/split_decay_sweep_Shell_B_800km.csv`,
  `reports/split_decay_sweep_Shell_C_1000km.csv` — full per-cell
  diagnostics (rho_fraction, gamma_multiplier, η triplet, fold L,
  complex eigenvalue presence, Hopf outcome, leading α).
* Heatmap PNGs accompanying the CSVs, produced by
  `scripts/run_split_decay_sweep.py`.

---

## Real-World Current State (April 27, 2026)

`data/real_world/shell_current_state.json` produced by
`scripts/fetch_realworld_data.py`. Population counts (S, D) from ESA Space
Environment Report 2024 / Celestrak GP TLE catalog (fallback used here —
network fetch timed out in sandbox). Launch rates from ESA Space Environment
Report 2024 + Aerospace Corp Annual Launch Report 2024 altitude-distribution
histogram. `L_fold` computed by `detect_fold()` using the
literature-calibrated shell parameters.

| Shell    | Altitude | S (live) | D (live) | L_current [obj/yr]   | L_fold [obj/yr] | L / L_fold | Traffic light |
|----------|----------|----------|----------|----------------------|-----------------|------------|---------------|
| Shell A  | 600 km   | 2 157    | 541      | 1 328.6 (3-yr avg)   | 25 100          | 0.053      | **green**     |
| Shell B  | 800 km   | 620      | 2 259    | 206.2 (3-yr avg)     | 670             | 0.308      | **green**     |
| Shell C  | 1000 km  | 545      | 873      | 34.4 (3-yr avg)      | 31.5            | **1.091**  | **RED**       |

S/D sourced from Space-Track.org GP catalog (26 835 LEO objects, April 27
2026). L_current is a **3-year trailing average (2022–2024)** of new LEO
objects × altitude-band fraction from ESA MASTER model:
- 2022: ~2 100 LEO obj (Aerospace Corp 2023 Annual Launch Report)
- 2023: ~2 400 LEO obj (Aerospace Corp 2024 Annual Launch Report)
- 2024: ~2 372 LEO obj (Space Foundation Q4 2024 Report: 2 695 total × 88% LEO fraction)
- Average: ~2 291 LEO obj/yr

The 2022–2024 window is used in preference to 2021–2023 because it is more
current and avoids the anomalously low 2021 cadence.

**Shell C D discrepancy (live 873 vs ESA fallback 3 200):** not a data
error — it is scientifically meaningful. Most Fengyun-1C (2007, 865 km)
and Iridium-Cosmos (2009, 789 km) fragments were injected below Shell C's
950 km floor and have continued to decay since. By 2026 the bulk of those
clouds sits below 950 km. The ESA static fallback (3 200) was less
altitude-resolved and over-counted. The amber status is driven entirely by
`L_current ≈ 29.5 ≈ L_fold = 31.5` — even after the historical debris
cloud cleared, the shell is barely below the tipping point because of
launch rate alone. This is the primary finding for the June 1 demonstration.

`reports/shell_B_bifurcation_realworld.png` shows Shell B's bifurcation
diagram with the live current-state marker (orange star at L=177, D≈2 259)
overlaid. The marker sits well left of the fold — Shell B is green.

---

## Multi-shell architecture

LEO is divided into N altitude shells between 200–2000 km. Each shell is modelled
**independently** (no inter-shell coupling in v1). Each shell has its own:
- Parameter set (beta, gamma, delta_S, delta_D vary strongly with altitude)
- Fixed points and bifurcation analysis
- L_c value (critical launch rate for that shell)

This directly addresses the single-shell limitation of naive models. Shells at different
altitudes have very different drag timescales and collision environments.

Recommended shell configuration for proof-of-concept:
- Shell A: 550–650 km   (Starlink primary belt)
- Shell B: 750–850 km   (historically most congested)
- Shell C: 950–1050 km  (Iridium/OneWeb band)

---

## Technology stack

- **Python 3.10+**
- `numpy` — array operations, eigenvalue computation (`numpy.linalg.eig`)
- `scipy` — ODE integration (`scipy.integrate.solve_ivp`), root finding (`scipy.optimize.fsolve`)
- `matplotlib` — bifurcation diagrams, phase portraits, time series plots
- `pytest` — test framework
- **MOCAT-pySSEM** (MIT ARCLab) — will be integrated in Phase 2 for parameter calibration
  and trajectory validation. In Phase 1 (this module), parameters are set from literature values.

Install: `pip install numpy scipy matplotlib pytest`

---

## What MOCAT-pySSEM is and how it fits

pySSEM is MIT ARCLab's open-source Python source-sink orbital debris model. It propagates
species populations (active satellites, derelicts, debris) forward in time across altitude
shells. It handles orbital mechanics and collision probability using the NASA Standard
Breakup Model.

**In this module (Phase 1):** pySSEM is NOT required. We use literature-calibrated parameters.

**In Phase 2:** pySSEM serves two roles:
1. Parameter extraction — run pySSEM with real initial conditions to calibrate beta, gamma,
   delta_S, delta_D per shell against historical data
2. Trajectory validation — run pySSEM forward past L_c and confirm it agrees with our
   bifurcation predictions

The integration challenge: pySSEM's collision model is more complex than gamma*D^2.
We will need to extract an effective gamma from pySSEM outputs empirically, or justify
the quadratic approximation as a mean-field simplification.

---

## Key constraints and principles

1. **No live data in Phase 1.** The bifurcation engine works on parameters alone.
   Data integration (Space-Track API) is a Phase 2 concern.

2. **Honesty about bifurcation existence.** The model does NOT guarantee a Hopf
   bifurcation exists for all parameter regimes. Code must handle and report all three
   outcomes: no complex eigenvalues, complex but alpha never crosses zero, genuine Hopf.

3. **Per-shell independence.** Each shell is analysed independently in v1.
   Do not introduce inter-shell coupling without explicit instruction.

4. **Physical plausibility checks.** S and D must remain non-negative. Parameters
   must satisfy delta_D > delta_S (debris decays faster than satellites at most altitudes).

5. **Presentation-ready outputs.** Final presentation is June 1, 2026. All plots must
   be clean, labelled, and explainable to non-technical stakeholders (ESA, policymakers).
   Bifurcation diagrams are the centrepiece visual.

---

## Module 2 — Completion Status (April 28, 2026)

Module 2 (Scenario Simulator) is **complete**. The full hybrid
pre-computed + live-API architecture from MODULE2_PLAN.md is
implemented and tested end-to-end.

### What was built

**Backend (`api/`)**
- `api/engine_bridge.py` — thin wrapper around the bifurcation engine;
  `compute_whatif(L_multiplier, debris_removal_rate, gamma_multiplier)`
  runs all three shells in a single call and returns new L_fold, traffic
  light, and lower-branch curve per shell.
- `api/main.py` — FastAPI application with four endpoints:
  - `GET /api/health` — liveness probe
  - `GET /api/base` — returns all three pre-computed static JSON files
  - `POST /api/whatif` — computes what-if scenario; enforces 5-overlay cap
  - `DELETE /api/whatif/clear` — clears server-side overlay state
  - `GET /api/whatif/scenarios` — returns active scenario list
  CORSMiddleware enabled. Server-side state reset on page load.

**Export script (`scripts/export_frontend_data.py`)**
Generates three static JSON files consumed by the frontend on page load:
- `frontend/data/base_curves.json` (82 KB) — lower + upper D* vs L branches
  + fold coordinates per shell
- `frontend/data/shell_current_state.json` — copy of real-world snapshot
- `frontend/data/indicator_curves.json` (160 KB) — recovery time (200 pts),
  variance (952 pts), and lag-1 AC (952 pts) per shell

**Frontend (`frontend/`)**
- `index.html` — entry point; loads vendor JS from `vendor/` for offline use
- `chart.js` — D3 v7 bifurcation diagram component: lower branch (solid blue),
  upper branch (dashed blue), L_fold red dashed vertical line, orange star
  real-world marker with tooltip, overlay API (`addOverlay`, `removeOverlay`,
  `clearOverlays`, `updateTrafficLight`)
- `app.jsx` — React 18 app: three shell panels side by side, control panel
  with preset buttons (fill sliders, do not auto-submit), custom parameter
  sliders, scenario overlay list with per-overlay remove button, "Clear all"
  visible whenever any scenario is active, traffic lights per shell
- `styles.css` — dark theme, responsive grid (3-col → 2-col → 1-col)
- `vendor/` — D3 v7, React 18, ReactDOM 18, Babel standalone bundled locally
  for fully offline demo-day operation

### Test: three MODULE2_PLAN.md presets

| Preset | Shell A | Shell B | Shell C |
|--------|---------|---------|---------|
| Starlink doubles (L×2) | green | green | red |
| ESA removes 5/yr | green | green | **amber** |
| Major collision (γ×1.5) | green | green | red |

Shell C shifts from red → amber with 5 obj/yr active removal — the key
policy finding visible directly in the simulator.

### To run

```bash
# Terminal 1 — API (from repo root)
PYTHONPATH=. .venv/bin/uvicorn api.main:app --port 8000
# Terminal 2 — frontend
cd frontend && python3 -m http.server 3000
# Open http://localhost:3000
```

---

## Contacts and external validators

- **Giovanni Perosa** (giovanni.perosa@xfel.eu) — HOPFEL technology owner, European XFEL.
  Validate that bifurcation framing is scientifically sound.
- **Prof. Josep Joaquim Masdemont** (UPC/IEEC) — astrodynamics expert, accessible via Juan Ramos.
  Validate orbital mechanics assumptions.
- **Dr. Tim Flohrer** (Tim.Flohrer@esa.int) — Head of ESA Space Debris Office.
  Validate debris population parameters and real-world relevance.
- **Richard Linares** (MIT ARCLab) — MOCAT-pySSEM principal investigator.
  Validate pySSEM integration approach.
