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
├── bifurcation_engine/
│   ├── src/
│   │   ├── model.py           ← ODE system: S_dot, D_dot per shell
│   │   ├── fixed_points.py    ← Newton continuation solver
│   │   ├── eigenvalues.py     ← Jacobian + eigenvalue tracker
│   │   ├── hopf_detector.py   ← Hopf bifurcation detection logic
│   │   ├── integrator.py      ← Full nonlinear trajectory integration
│   │   ├── early_warning.py   ← Critical slowing down, variance, autocorrelation
│   │   └── shell_config.py    ← Altitude shell definitions and parameters
│   ├── tests/
│   │   ├── test_model.py
│   │   ├── test_fixed_points.py
│   │   ├── test_hopf_detector.py
│   │   ├── test_early_warning.py
│   │   └── test_validation_scenarios.py
│   ├── notebooks/
│   │   └── engine_demo.ipynb  ← interactive exploration notebook
│   └── requirements.txt
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
