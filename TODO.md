# TODO — Orbital Sentinel: Bifurcation Engine (Module 1)

Last updated: April 2026 (post 3-species extension)
Current phase: Phase 1 — Bifurcation engine (no live data)
Test suite: **159 passed, 2 skipped** (the 2 skipped cover T5.2/T5.3
historical scenarios; Task 7 early-warning is the single remaining IMMEDIATE
priority).

The engine is feature-complete through Task 6 plus the saddle-node fold
detector and the additive 3-species (S, R, D) extension. The 3-species
pipeline confirms that the fold-over-Hopf preference is structural — see
CLAUDE.md "3-Species Extension — Results and Mathematical Findings" — so
all early-warning work targets the **fold** as the operational tipping
point.

---

## Status legend
- [ ] Not started
- [~] In progress
- [x] Done
- [!] Blocked — see note

---

## IMMEDIATE: Task 7 — early-warning module (single next priority)

This is now the only remaining module in the bifurcation engine before the
June 1 presentation. T5.2 / T5.3 (historical scenarios) remain skipped in
the test suite and are tracked separately under "KNOWN PENDING" below.

- [ ] **Implement `src/early_warning.py`** (Task 7) — fold-based warning.

      Primary channel — fold-keyed indicators:
      * `critical_slowing_down(alpha_array, L_array)` — recovery time
        `τ(L) = 1 / |α(L)|` along the stable lower branch, computed from
        the **leading eigenvalue real part** at each fixed point. As L
        approaches `L_fold`, `α → 0` and τ diverges — the same critical
        slowing down signature that precedes Hopf bifurcations also
        precedes saddle-node folds, which is the published mathematical
        result the indicator relies on.
      * `variance_indicator(trajectory, window)` — rolling variance of `D(t)`.
      * `autocorrelation_indicator(trajectory, lag=1)` — lag-1 AC of `D(t)`.
      * `early_warning_summary(params, current_L)` — traffic-light
        (green / amber / red) keyed to `L_fold`:
        - green if `L < 0.80 · L_fold`
        - amber if `0.80 · L_fold ≤ L < 0.95 · L_fold`
        - red if `L ≥ 0.95 · L_fold`

      Secondary channel — Hopf-keyed indicators (placeholder only):
      The 2-D model has no Hopf and the 3-D extension found none either
      (see `reports/3species_pipeline_summary.md`); the Hopf channel
      stays in the API for forward compatibility but always returns
      "not applicable for this shell" until a future model extension
      surfaces a genuine Hopf locus.

      Acceptance tests: T4.1–T4.5 in VALIDATION.md (rephrased around
      `L_fold`).

- [ ] Wire Task 7 into the existing pipeline script and re-run the full
      Shell A / B / C sweep so the dashboard (Module 3) has consistent
      `L_fold`-relative warning curves to consume.

---

## DONE: 3-species (S, R, D) extension

Merged April 2026, additively, with no edits to any 2-D function or test.

- [x] `ShellConfig` extended with `delta_R`, `beta_SR`, `beta_RD`,
      `use_3species` and conditional validation; default remains 2-D.
- [x] `model.py` extended with `s_dot_3species`, `r_dot_3species`,
      `d_dot_3species`, `ode_system_3species`.
- [x] `fixed_points.py` extended with `find_fixed_points_3species`
      (grid-seeded `fsolve` with dedup) and `continuation_sweep_3species`
      (warm-started, all-branch tracking).
- [x] `eigenvalues.py` extended with `jacobian_3species`,
      `eigenvalue_analysis_3species`, `track_eigenvalues_3species`.
      All 9 Jacobian entries analytically verified.
- [x] `scripts/run_3species_pipeline.py` and
      `reports/3species_pipeline_summary.md` produced.
- [x] **Result:** no Hopf bifurcation found on any shell on any branch.
      Lower coexistence branches return `complex_no_crossing`; upper
      branches return `no_complex_eigenvalues`. The saddle-node fold
      survives in 3-D and remains the operational Kessler tipping point.
- [x] **Mathematical verification:** the trace inequality
      `tr(J_3) = −(δ_S + δ_R + δ_D) + β·(S*−D*) + β_RD·(R*−D*) − β_SR·R* + 2γ·D*`
      shows the `2γ·D*` Kessler term drives the trace positive at the
      same L at which the lower branch ends in the fold. Fold and trace
      instability fire simultaneously — the fold-over-Hopf preference is
      **structural**, not a parameter problem. See CLAUDE.md.

---

## NEXT: Validation and calibration

- [ ] Run the full suite after each change: `pytest bifurcation_engine/tests/ -v`
      (expect 162 passing once T5.2, T5.3 are unskipped and Task 7 tests
      are added).

- [ ] Produce the equivalent of `reports/shell_B_bifurcation.png` for
      Shells A and C so all three shells have a presentation-ready
      bifurcation diagram with trajectory overlays.

---

## KNOWN PENDING

- [ ] **T5.2 — 2009 Iridium-Cosmos collision scenario** (see VALIDATION.md).
      Currently skipped in the test suite. Will be unskipped once the
      historical-scenario harness is written; not a blocker for the
      Module 1 acceptance gate, but required before the June 1 demo.

- [ ] **T5.3 — 2007 Chinese ASAT test scenario** (see VALIDATION.md).
      Same status as T5.2.

---

## LATER: Integration (Phase 2)

- [ ] Install and explore MOCAT-pySSEM: `pip install pyssem`
      Run example-sim.json to confirm it works
      Understand output format (species populations per shell per timestep)

- [ ] Extract effective parameters (beta, gamma, delta_S, delta_D) per shell
      from pySSEM calibrated runs — replace literature values with data-driven ones

- [ ] Connect Space-Track API to get current population per shell
      Free registration at space-track.org
      Query: all objects in LEO, binned by altitude, classified by type
      Use OMM format (NOT legacy TLE — catalog number overflow expected mid-2026)

- [ ] Feed real current S(t0), D(t0) per shell as initial conditions
      Compute "where we are now" relative to L_c for each shell
      This powers the early-warning dashboard (Module 3)

---

## KNOWN RISKS

- **Hopf bifurcation does not exist** in either the 2-D or 3-D source-sink
  model class with any tested parameter regime, and the trace analysis in
  CLAUDE.md shows this is structural rather than a parameter accident. The
  project has committed to the saddle-node fold as the Kessler tipping point;
  early warning is keyed to `L_fold`. No further parameter sweeps for Hopf
  are planned.

- **pySSEM gamma extraction** — the quadratic D^2 term is a simplification of
  pySSEM's NASA Breakup Model collision dynamics. Extracting an effective gamma
  requires fitting, which may introduce error. Document clearly.

- **Computational performance** — for the live demo (June 1), continuation sweep
  across L must run in seconds. Profile early. If slow, reduce N_shells or L_steps.
