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

## Contacts and external validators

- **Giovanni Perosa** (giovanni.perosa@xfel.eu) — HOPFEL technology owner, European XFEL.
  Validate that bifurcation framing is scientifically sound.
- **Prof. Josep Joaquim Masdemont** (UPC/IEEC) — astrodynamics expert, accessible via Juan Ramos.
  Validate orbital mechanics assumptions.
- **Dr. Tim Flohrer** (Tim.Flohrer@esa.int) — Head of ESA Space Debris Office.
  Validate debris population parameters and real-world relevance.
- **Richard Linares** (MIT ARCLab) — MOCAT-pySSEM principal investigator.
  Validate pySSEM integration approach.
