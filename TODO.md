# TODO — Orbital Sentinel: Bifurcation Engine (Module 1)

Last updated: April 26, 2026 — **Module 1 complete**.
Current phase: Phase 1 — Bifurcation engine (no live data).
Test suite: **231 passed, 1 skipped, 0 failed** (the skip is the
entire `test_validation_scenarios.py` module covering T5.2/T5.3
historical scenarios — deferred behind a module-level
`pytest.skip(..., allow_module_level=True)`, not forgotten).

The engine is feature-complete: Tasks 1–7 plus the saddle-node fold
detector, the additive 3-species (S, R, D) extension, and the
additive split-decay Hopf-hunt experiment. Three independently
implemented model variants (2-D, 3-species, split-decay) and 2,400
split-decay cells agree: no parameter regime produces a Hopf
bifurcation. The fold-over-Hopf preference is structural — see
CLAUDE.md "3-Species Extension", "Split-Decay Hopf-Hunt", and
"Module 1 — Completion Status" — so the early-warning module is
keyed entirely to `L_fold`, with the Hopf channel reduced to a
forward-compatibility placeholder for future model extensions.

---

## Status legend
- [ ] Not started
- [~] In progress
- [x] Done
- [!] Blocked — see note

---

## IMMEDIATE: data pulls (unlocks Module 2 + closes T5.2 / T5.3)

Module 1 is closed; the next blocking item is data, in two parallel
streams. Both streams are public-domain or open-data and require no
credentials beyond a free registration.

- [x] **Our World in Data — current-state pull.** Completed April 27,
      2026. Population counts (S, D) from ESA Space Environment Report
      2024 / Celestrak GP TLE catalog (ESA fallback used; network
      sandbox blocked live fetch). Launch rates from ESA SER 2024 +
      Aerospace Corp 2024 Annual Launch Report altitude histogram.
      Deliverables: `data/real_world/shell_current_state.json`,
      `reports/shell_B_bifurcation_realworld.png` (real-world marker
      overlaid on bifurcation diagram), and CLAUDE.md updated.
      Key finding: Shell A → green (L/L_fold=0.056), Shell B → green
      (L/L_fold=0.32), **Shell C → RED (L/L_fold=1.14)** — the 1000 km
      band appears to already be past the fold threshold, consistent
      with published scientific assessments. Step 2 (NASA ODQN
      historical pull) is now unblocked.

- [ ] **NASA ODQN historical-data pull.** Extract initial conditions
      and post-event debris counts from the NASA Orbital Debris
      Quarterly News for the two skipped historical scenarios:
      * **T5.2 — 2009 Iridium-Cosmos collision (Shell B).** Pre-event
        `S(t0), D(t0)` for Shell B at the start of 2009; post-event
        debris injection from the published Iridium-33/Cosmos-2251
        breakup catalogue.
      * **T5.3 — 2007 Chinese ASAT (Fengyun-1C) test (Shell C).**
        Pre-event `S(t0), D(t0)` for Shell C at the start of 2007;
        post-event debris injection from the published Fengyun-1C
        breakup catalogue.
      Once the data is in, write the historical-scenario harness in
      `tests/test_validation_scenarios.py` (replacing the module-level
      skip), and unskip T5.2 / T5.3 individually. Target: full suite
      at **233 passed, 0 skipped** before the June 1 demonstration.

---

## DONE: Task 7 — early-warning module

Merged April 2026, fold-keyed only (Hopf channel is a forward-
compatibility placeholder).

- [x] `src/early_warning.py` implements the four functions exactly as
      specified in `TASKS.md` Task 7 and `VALIDATION.md` T4.1–T4.5:
      `critical_slowing_down(L_array, alpha_array)`,
      `variance_indicator(trajectory, window=50)`,
      `autocorrelation_indicator(trajectory, lag=1, window=50)`,
      `early_warning_summary(params, L_values, fold_result,
      hopf_result=None)`.
- [x] Traffic-light thresholds: green `< 0.80 · L_fold`,
      amber `0.80 ≤ · < 0.95`, red `≥ 0.95`. Hopf channel returns
      `not_applicable` whenever `hopf_result is None` or
      `hopf_result.found is False`.
- [x] T4.1–T4.5 acceptance tests pass against the packaged Shell B
      parameters and the real `detect_fold` / `integrate_trajectory`
      machinery. Plus 16 unit tests covering shape and edge-case
      behaviour for each function.
- [x] Full test suite: **231 passed, 1 skipped**.

---

## DONE: split-decay Hopf-hunt experiment

Merged April 2026, additively, with no edits to any 2-D, 3-species, or
existing test code.

- [x] `SplitDecayConfig` dataclass with `from_shell` constructor and
      full validation (κ_S + ϱ_S = δ_S conservation, η ≥ 1, strict
      δ_S < δ_R < δ_D ordering).
- [x] `model_split.py` — split-decay ODE with κ_S/ϱ_S separation,
      η_SD/η_SR/η_RD yield multipliers, and the corrected symmetric
      `−β_SR·S·R` sink in `Ṙ`.
- [x] `fixed_points_split.py` — grid-seeded `find_fixed_points_split`,
      warm-start `continuation_sweep_split` with all-branch tracking.
- [x] `eigenvalues_split.py` — `jacobian_split` (9 entries
      analytically verified entry-by-entry), `eigenvalue_analysis_split`,
      `track_eigenvalues_split` with `detect_hopf`-compatible aliases.
- [x] `hopf_detector_split.py` — `detect_fold_numerical` (closed-form
      discriminant trick does not apply once R is coupled with three
      collision channels, so the fold is detected by branch-termination
      under warm-started continuation).
- [x] `scripts/run_split_decay_sweep.py` with embedded profile gate
      (Shell B / `ρ=0.5` / `γ_mult=1.0` / baseline η — measured 0.92 s
      per cell, well inside the 90 s budget).
- [x] **Sweep result:** zero Hopf bifurcations across 2,400 cells
      (Shells B and C, 20×20 grid in `(rho_fraction, gamma_multiplier)`,
      3 η triplets). Shell B had complex eigenvalues on the lower
      branch in 89 % of cells (1064/1200), but `α` stayed strictly
      negative throughout — `complex_no_crossing` everywhere. Shell C:
      complex pairs in 6 % of cells, same outcome.
- [x] **Mathematical conclusion:** the trace inequality from the
      3-species analysis extends to the corrected split-decay model.
      The fold-over-Hopf preference is **structural** across all three
      independently implemented model variants (2-D, 3-species,
      split-decay). No further parameter sweeps for Hopf are planned.
- [x] CSVs, heatmaps, and `reports/split_decay_sweep_summary.md`
      written. 51 new tests added (210 passed, 2 skipped overall).

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

## NEXT: Pre-demo polish (non-blocking)

- [ ] Run the full suite after each change: `pytest bifurcation_engine/tests/ -v`
      (expect **231 passed, 1 skipped** today; **233 passed, 0
      skipped** once T5.2 and T5.3 are unskipped after the ODQN pull).

- [ ] Produce the equivalent of `reports/shell_B_bifurcation.png` for
      Shells A and C so all three shells have a presentation-ready
      bifurcation diagram with trajectory overlays. This will be
      re-done after the IMMEDIATE data pulls so the diagrams can
      include the "where are we today" marker.

---

## KNOWN PENDING

- [ ] **T5.2 — 2009 Iridium-Cosmos collision scenario** (see VALIDATION.md).
      Currently skipped at module level in
      `test_validation_scenarios.py`. **Now unblocked pending the NASA
      ODQN historical-data pull in IMMEDIATE above** — once the pre-
      and post-event `(S, D)` numbers for Shell B are in,
      writing the harness and unskipping the test is mechanical.
      Not a blocker for the Module 1 acceptance gate (which is
      already satisfied), but required before the June 1 demo.

- [ ] **T5.3 — 2007 Chinese ASAT test scenario** (see VALIDATION.md).
      Same status as T5.2: module-skipped today, **unblocked pending
      the NASA ODQN historical-data pull** for Shell C / Fengyun-1C.

---

## LATER: Modules 2 and 3, Phase 2 integration

### Module 2 — Scenario simulator

Module 2 starts **after the IMMEDIATE data pulls are complete**. It
takes the calibrated bifurcation engine and current-state markers
from Module 1 and wraps them in a what-if scenario harness:
configurable launch-rate trajectories, deorbit policies, and
constellation-deployment scenarios; per-shell forward integration
out to 2050; comparison of where each scenario lands relative to
`L_fold` and the green / amber / red traffic light from Task 7.
Output: scenario-comparison plots and a per-scenario summary CSV.

### Module 3 — Early-warning dashboard

Module 3 wraps Modules 1 and 2 in an interactive dashboard for the
ESA / academic / policy audience identified in CLAUDE.md. Inputs:
shell selection, launch-rate slider, debris-removal toggle, and
optional historical scenario overlays. Outputs: live bifurcation
diagram with the "where are we today" marker, traffic-light banner,
the three critical-slowing-down indicators (recovery time,
variance, autocorrelation), and a one-line policy interpretation.
Built on the fold-keyed `early_warning_summary` API from Module 1.

### Phase 2 integration (calibration + live data)

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
      Compute "where we are now" relative to L_fold for each shell.
      Cross-check against the Our World in Data pull from IMMEDIATE
      to confirm the two sources agree at the order-of-magnitude
      level. This powers the Module 3 dashboard.

---

## KNOWN RISKS

- **Hopf bifurcation does not exist** in any of the three independently
  implemented source-sink model variants (2-D, 3-species, split-decay)
  for any tested parameter regime — including the 2,400-cell split-decay
  sweep on Shells B and C. The trace inequality in CLAUDE.md shows this
  is structural rather than a parameter accident. The project has
  committed to the saddle-node fold as the Kessler tipping point;
  early warning is keyed to `L_fold`. No further parameter sweeps for
  Hopf are planned in Phase 1.

- **pySSEM gamma extraction** — the quadratic D^2 term is a simplification of
  pySSEM's NASA Breakup Model collision dynamics. Extracting an effective gamma
  requires fitting, which may introduce error. Document clearly.

- **Computational performance** — for the live demo (June 1), continuation sweep
  across L must run in seconds. Profile early. If slow, reduce N_shells or L_steps.
