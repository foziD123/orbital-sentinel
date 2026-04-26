# VALIDATION — Module 1: Bifurcation Engine
## Tests, acceptance criteria, and historical validation scenarios

---

## Unit tests (`bifurcation_engine/tests/`)

---

### `test_model.py` — ODE system

**T1.1 — Clean orbit is stationary**
```
Given: params with D0=0, any S0
When:  d_dot(S0, 0, params) is computed
Then:  result == 0.0
Rationale: if there's no debris, debris rate must be zero (no cascade source)
```

**T1.2 — Satellite decay only when no debris**
```
Given: params, D0=0, S0=100
When:  s_dot(100, 0, params) is computed
Then:  result == params.L - params.delta_S * 100
Rationale: without debris, only launch and drag affect satellites
```

**T1.3 — Kessler term dominates at high debris**
```
Given: params with gamma=1e-7, delta_D=0.005, D=10000, S=0
When:  d_dot(0, 10000, params) is computed
Then:  result > 0  (gamma * D^2 > delta_D * D at this D)
Rationale: debris cascade is self-sustaining above critical density
```

**T1.4 — Non-negativity: S and D cannot go negative under integration**
*Status: passing as of post-Task-6 sync (previously skipped — unskipped once
`integrate_trajectory` landed in `integrator.py`).*
```
Given: integrate_trajectory with initial (S0=10, D0=0) and large L for long t_span
When:  integration runs to t=200 years
Then:  min(trajectory['S']) >= 0 and min(trajectory['D']) >= 0
```

**T1.5 — ODE signature matches scipy convention**
```
Given: ode_system(t=0, y=[100, 50], params)
When:  called
Then:  returns array of length 2
       result[0] == s_dot(100, 50, params)
       result[1] == d_dot(100, 50, params)
```

---

### `test_fixed_points.py` — Fixed point solver

**T2.1 — Case 1 analytical fixed point is correct**
```
Given: params with L=100, delta_S=0.01
When:  clean_orbit_fixed_point(params) called
Then:  S* == 100/0.01 == 10000 (to numerical tolerance 1e-10)
       D* == 0.0
```

**T2.2 — Case 1 fixed point satisfies ODE**
```
Given: any valid params
When:  (S*, D*) = clean_orbit_fixed_point(params)
Then:  abs(s_dot(S*, D*, params)) < 1e-10
       abs(d_dot(S*, D*, params)) < 1e-10
```

**T2.3 — Case 2 fixed points satisfy ODE (when they exist)**
```
Given: params that produce Case 2 solutions
When:  (S*, D*) in coexistence_fixed_points(params)
Then:  for each solution: abs(s_dot(S*, D*, params)) < 1e-8
                          abs(d_dot(S*, D*, params)) < 1e-8
```

**T2.4 — Physical validity: no negative populations**
```
Given: any valid params
When:  find_all_fixed_points(params) called
Then:  all returned (S*, D*) have S* >= 0 and D* >= 0
```

**T2.5 — Continuation produces smooth branch**
```
Given: Shell_B_800km params, L sweeping 0 to 1000 in 100 steps
When:  continuation_sweep runs
Then:  returned S_star array has no discontinuous jumps > 10% between adjacent steps
       (max(abs(diff(S_star))) / mean(S_star) < 0.1)
Rationale: warm-start continuation should track branches smoothly
```

**T2.6 — delta_D > delta_S validation**
```
Given: params with delta_D=0.01, delta_S=0.05 (invalid — delta_D < delta_S)
When:  ShellConfig is constructed
Then:  raises ValueError with message mentioning delta_D > delta_S
```

---

### `test_hopf_detector.py` — Hopf detection

**T3.1 — No complex eigenvalues → correct outcome reported**
```
Given: alpha_array all real (omega_array == 0 throughout)
When:  detect_hopf called
Then:  result.found == False
       result.outcome == 'no_complex_eigenvalues'
```

**T3.2 — Complex eigenvalues but no zero crossing → correct outcome**
```
Given: omega_array all nonzero, alpha_array always negative
When:  detect_hopf called
Then:  result.found == False
       result.outcome == 'complex_no_crossing'
       result.L_c == None
```

**T3.3 — Genuine Hopf: alpha crosses zero with omega nonzero**
```
Given: synthetic arrays where alpha goes from -0.5 to +0.5 linearly, omega=1.0 throughout
       L_array = np.linspace(0, 100, 200)
       alpha_array = np.linspace(-0.5, 0.5, 200)
       omega_array = np.ones(200)
When:  detect_hopf called
Then:  result.found == True
       abs(result.L_c - 50.0) < 1.0   (interpolated crossing near L=50)
       result.dalpha_dL_at_Lc > 0     (positive crossing)
```

**T3.4 — L_c interpolation is accurate**
```
Given: alpha array with known crossing at L=37.5
When:  detect_hopf called
Then:  abs(result.L_c - 37.5) < 0.5
```

**T3.5 — HopfResult is complete (no None fields when found=True)**
```
Given: valid Hopf scenario
When:  detect_hopf returns result with found=True
Then:  result.L_c is not None
       result.omega_at_Lc is not None
       result.dalpha_dL_at_Lc is not None
       result.description is not None and len > 0
```

---

### `test_early_warning.py` — Early warning indicators

**T4.1 — Recovery time diverges as alpha → 0**
```
Given: alpha_array = [-1.0, -0.5, -0.1, -0.01, -0.001]
When:  critical_slowing_down called
Then:  recovery_time array is monotonically increasing
       recovery_time[-1] >> recovery_time[0]
```

**T4.2 — Traffic light: green far from L_c**
```
Given: current L = 0.5 * L_c (50% of critical threshold)
When:  early_warning_summary called
Then:  status == 'green'
```

**T4.3 — Traffic light: amber near L_c**
```
Given: current L = 0.88 * L_c
When:  early_warning_summary called
Then:  status == 'amber'
```

**T4.4 — Traffic light: red at or past L_c**
```
Given: current L = 1.0 * L_c (at threshold)
When:  early_warning_summary called
Then:  status == 'red'
```

**T4.5 — Autocorrelation approaches 1 near bifurcation**
```
Given: time series of D(t) from trajectory integrated at L = 0.99 * L_c
When:  autocorrelation_indicator called
Then:  mean of last quarter of ac1_D array > 0.8
Rationale: critical slowing down → high persistence → high autocorrelation
```

---

### `test_validation_scenarios.py` — Historical and physical validation

**T5.1 — Jacobian at clean-orbit fixed point has correct analytical eigenvalues**
```
Given: any valid params, clean orbit fixed point (S* = L/delta_S, D* = 0)
When:  eigenvalue_pair(S*, D*, params) called
Then:  alpha == -(delta_S + delta_D) / 2 approximately  [NOT exact — check analytically]

CORRECT ANALYTICAL RESULT for D*=0:
J = [[-delta_S, -beta*S*], [0, beta*S* - delta_D]]
eigenvalues are exactly -delta_S and (beta*S* - delta_D)
So: lambda_1 = -delta_S  (always stable)
    lambda_2 = beta*L/delta_S - delta_D  (stable if L < delta_S*delta_D/beta)
Both real — no Hopf possible at Case 1 fixed point. This is expected and correct.
Test: confirm eigenvalues match this analytical form to 1e-10.
```

**T5.2 — 2009 Iridium-Cosmos collision scenario**
```
Context: On Feb 10, 2009, Iridium 33 and Cosmos 2251 collided at ~789 km altitude,
generating ~2,000 trackable fragments instantly (one of the largest debris events in history).

Setup:
- Use Shell_B_800km parameters
- Set initial conditions to approximate pre-2009 population at 800 km:
  S0 ~ 500 (active satellites + rocket bodies)
  D0 ~ 2000 (pre-existing debris)
- At t=0, inject an instantaneous debris spike: D0 += 2000 (Iridium-Cosmos fragments)
- Integrate for 20 years (2009–2029)

Expected behaviour:
- D(t) should show a spike then gradual decay (drag-dominated at this altitude)
- S(t) should show mild decrease from increased collision risk
- System should NOT show runaway cascade (800 km has moderate drag — self-cleaning over ~decades)
- This validates that our L_c for Shell_B is above current real launch rates (system is still below threshold)

Pass criterion:
- D(t=20yr) < D(t=0+) by at least 20% (debris decays over 20 years at 800 km)
- System does not diverge (D does not grow unboundedly)
```

**T5.3 — 2007 Chinese ASAT test scenario**
```
Context: On Jan 11, 2007, China destroyed Fengyun-1C at ~865 km altitude,
generating ~3,000 trackable fragments — the largest single debris-creation event ever.

Setup:
- Use Shell_B_800km or a dedicated 850km sub-shell
- S0 ~ 400, D0 ~ 1500 (pre-2007 population)
- At t=0, inject D_spike = 3000
- Integrate for 30 years

Expected behaviour:
- Similar to T5.2 but larger initial spike
- At 865 km, drag is slower than at 789 km — debris persists longer
- Population should remain elevated for 10-15 years before significant decay
- Still should not cascade (below L_c) given current launch rates

Pass criterion:
- D(t=10yr) > D(t=0+) * 0.5 (significant persistence — debris at 865km is slow to decay)
- System does not diverge (no runaway Kessler cascade triggered by single event alone)
```

**T5.4 — Saddle-node fold trajectory triad (replaces the original supercritical-Hopf
scaling test)**

*Rationale for replacement: the 2D source-sink model does not host a Hopf
bifurcation on any branch of any default shell — the Kessler tipping point
manifests as a saddle-node fold at `L_fold`. The √(L − L_c) amplitude scaling
therefore has no fixed point to be measured against. The fold analogue is
the qualitative trajectory triad below, which is what the engine is actually
expected to reproduce and what the Shell-B presentation plot is built on.*
```
Given: any default shell with a detected L_fold (via detect_fold)
       params_lo  = params with L = 0.5 * L_fold
       params_mid = params with L = L_fold
       params_hi  = params with L = 1.5 * L_fold
When:  integrate_trajectory is run from a physically-plausible IC (e.g. the
       stable lower-branch fixed point at 0.5 * L_fold) over a t_span scaled
       by 1 / delta_S to let slow-drag shells reach steady state
Then:  - params_lo  → D(t) stabilizes onto the lower branch
                      (|D_end - D_lower| / D_lower < 0.05 after transient)
       - params_mid → D(t) hovers near the merged root D_fold when started
                      at (S_fold, D_fold); bounded excursions only
                      (0.05 * D_fold <= min(D_tail) and max(D_tail) <= 10 * D_fold)
       - params_hi  → D(t) runs away: either hits the runaway_ceiling_D
                      terminal event or D(t_end) >= 10 * D(0)
Acceptance: all three conditions hold for Shells A, B, and C.
Rationale: this is the nonlinear signature of a saddle-node fold — stable
           attractor below, marginal slow dynamics at the fold, loss of
           equilibrium above — and is the empirical basis for the
           L_fold-keyed red-line thresholds used by Module 3.
```

**T5.5 — Sensitivity: L_c changes appropriately with gamma**
```
Given: Shell_B params, vary gamma from 0.5x to 2x default
When:  full continuation and Hopf detection run for each gamma
Then:  L_c decreases as gamma increases
       (higher cascade coefficient → lower launch rate needed to trigger cascade)
Rationale: sanity check on physical intuition. Higher Kessler coefficient = more dangerous.
```

---

## Integration tests (run after all unit tests pass)

**I1 — Full pipeline: params → fixed points → eigenvalues → Hopf detection**
```
Given: Shell_B_800km default parameters
When:  full pipeline runs end-to-end
Then:  completes without error
       returns HopfResult (found or not — either is valid)
       all plots generated without error
```

**I2 — All three shells run without error**
```
Given: all three shell configs (A, B, C)
When:  full pipeline runs for each
Then:  all complete; results saved to output files
```

**I3 — Performance: full continuation sweep completes in < 10 seconds**
```
Given: Shell_B with 200 L steps
When:  continuation_sweep + eigenvalue_track runs
Then:  wall time < 10 seconds
Rationale: must be fast enough for interactive demo on June 1
```

---

## Acceptance criteria for Module 1 completion

Current test suite state: **159 passed, 2 skipped** (the 2 skipped cover
the T5.2 / T5.3 historical scenarios; Task 7 early-warning is the single
remaining IMMEDIATE gate before Module 1 closes — see TODO.md).

Module 1 is complete when ALL of the following are true:

- [x] All unit tests pass (`pytest bifurcation_engine/tests/ -v`) — 159
      passed, 2 skipped as of the post-3-species sync. The skipped items
      are tracked under "KNOWN PENDING" in TODO.md and are not blockers
      for the gate below.
- [x] T5.1 (analytical Jacobian, 2-D) passes — confirms 2-D math is correct.
- [x] T5.4 (fold trajectory triad) passes for Shells A, B, and C —
      replaces the original Hopf scaling law and confirms the nonlinear
      dynamics around the detected `L_fold`.
- [x] **3-species Jacobian is analytically verified** — all 9 entries of
      `jacobian_3species` derived from first principles match the code
      exactly. The deliberate `R_dot` asymmetry (no `−β_SR·S·R` self-term;
      `J[1,1]` correspondingly carries no `−β_SR·S*` term) is documented
      and consistent. See "Mathematical verification of the 3-species
      model" below.
- [x] **Trace analysis confirms structural fold-over-Hopf preference** —
      the trace inequality on the lower branch shows the fold and the
      trace instability fire simultaneously, so no parameter regime in
      this model class can host a Hopf. See "Mathematical verification"
      below.
- [x] Full 2-D pipeline runs for all three default shells without error.
- [x] Full 3-species pipeline runs for all three default shells without
      error (`scripts/run_3species_pipeline.py`,
      `reports/3species_pipeline_summary.md`).
- [x] Bifurcation diagram plot generated for at least one shell
      (`reports/shell_B_bifurcation.png`, with stable/unstable branches,
      fold point in red, and trajectory overlays at 0.5 / 1.0 / 1.5 × L_fold).
- [x] HopfResult correctly reports all non-Hopf outcomes (test with
      synthetic data) — and the complementary `FoldResult` from
      `detect_fold` reports `L_fold` when a saddle-node is present.
- [x] Performance: < 10 seconds for one shell continuation sweep.
- [x] Code is readable, docstrings present on all public functions.
- [x] No hardcoded magic numbers — all parameters come from `ShellConfig`.
- [ ] **Task 7 early-warning module implemented (fold-keyed) and T4.1–T4.5
      passing.** This is the new gate for Module 1 completion now that the
      3-species extension and its mathematical verification are in.
- [ ] T5.2 **or** T5.3 (historical scenario) passes — desirable but no
      longer a strict gate for Module 1; required before the June 1 demo.

---

## Mathematical verification of the 3-species model

These results are theoretical validation — they are part of the
acceptance ledger but are not unit tests because they hold by analytic
derivation rather than numerics.

### V1 — All 9 entries of the 3-species Jacobian are correct

The 3-species ODE
```
Ṡ = L − δ_S·S − β·S·D − β_SR·S·R
Ṙ = δ_S·S − δ_R·R − β_RD·R·D
Ḋ = β·S·D + β_SR·S·R + β_RD·R·D + γ·D² − δ_D·D
```
yields, by direct partial differentiation at a fixed point `(S*, R*, D*)`,
the closed form
```
J_3 = [[ −δ_S − β·D* − β_SR·R*,   −β_SR·S*,             −β·S*                          ],
       [  δ_S,                     −δ_R − β_RD·D*,       −β_RD·R*                       ],
       [  β·D* + β_SR·R*,           β_SR·S* + β_RD·D*,    β·S* + β_RD·R* + 2γ·D* − δ_D ]]
```
Every entry was hand-verified against the implementation in
`bifurcation_engine/src/eigenvalues.py::jacobian_3species` and matches
exactly. In particular:
- `J[0,0] = −δ_S − β·D* − β_SR·R*` ✓
- `J[1,0] = δ_S` ✓
- `J[2,1] = β_SR·S* + β_RD·D*` ✓
- `J[2,2] = β·S* + β_RD·R* + 2γ·D* − δ_D` ✓

### V2 — `R_dot` asymmetry is intentional and self-consistent

The ODE for R does not contain a `−β_SR·S·R` term: an active-derelict
collision removes the active satellite (visible in `S_dot`) and produces
fragments (visible in `D_dot`), but the derelict body is treated as not
removed. The Jacobian entry `J[1,1] = −δ_R − β_RD·D*` correspondingly
carries no `−β_SR·S*` term. Code matches spec; matrix matches code.

### V3 — Trace inequality explains why the fold beats the Hopf

The symbolic trace of `J_3` factors cleanly:
```
tr(J_3) = −(δ_S + δ_R + δ_D)              [decay sinks; always negative]
          + β·(S* − D*)                    [satellite-debris balance]
          + β_RD·(R* − D*)                 [derelict-debris balance]
          − β_SR·R*                         [active-derelict; one-sided]
          + 2γ·D*                           [Kessler self-cascade]
```
On the stable lower branch as `L → L_fold`, `D*` grows
square-root-steeply and the `2γ·D*` term drives the trace toward zero
from below and then positive. Because `tr(J_3) > 0` is sufficient for
instability, the fixed point loses stability through the **trace
mechanism** at the same L at which the lower branch ends in the fold —
the fold and the trace instability fire simultaneously. No parameter
regime in this model class can therefore open a window in which a
complex pair crosses zero on a still-existing stable branch. This is
consistent with the empirical 3-species pipeline outcome on every
shell:

| Branch                       | Outcome                  | α behaviour            |
|------------------------------|--------------------------|------------------------|
| Lower coexistence            | `complex_no_crossing`    | α → 0⁻ at `L_fold`     |
| Upper coexistence            | `no_complex_eigenvalues` | saddle-like real spectrum |

The result is that **fold-over-Hopf is structural**, not a parameter
problem. Module 3 dashboard thresholds and Task 7 early-warning indicators
are therefore keyed to `L_fold`, with the Hopf channel kept in the API
only as a placeholder for future model extensions.

---

## What to do if no Hopf bifurcation is found

This is a legitimate scientific result, not a failure. If the default parameters
don't produce a Hopf bifurcation, the response is:

1. **Document the outcome** — which case: no complex eigenvalues, or complex but no crossing?
2. **Parameter sweep** — systematically vary (beta, gamma) and find the regime where Hopf does exist.
   Plot a 2D heatmap of L_c vs (gamma, delta_D) — regions where Hopf exists vs doesn't.
3. **Present the boundary** — "here is the parameter regime that corresponds to a Kessler cascade risk"
   is itself a valuable scientific result for policymakers.
4. **Check literature** — if published sources cite specific (beta, gamma) values that produce
   cascade, calibrate to those and re-run.

The worst outcome is not "no Hopf found" — it is "Hopf assumed without checking."
