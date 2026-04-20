# TODO — Orbital Sentinel: Bifurcation Engine (Module 1)

Last updated: April 2026 (post-Task-6 sync)
Current phase: Phase 1 — Bifurcation engine (no live data)
Test suite: **113 passed, 2 skipped** (the 2 skipped cover T5.2/T5.3 historical
scenarios and the Task 7 early-warning module — both scheduled below).

The engine is feature-complete through Task 6. Tasks 1–6 plus the saddle-node
fold detector (`detect_fold` in `hopf_detector.py`) are merged and green.
`integrate_trajectory` in `integrator.py` ships with a runaway-ceiling
terminal event and non-negativity enforcement. The Shell-B bifurcation
diagram is in `reports/shell_B_bifurcation.png`.

---

## Status legend
- [ ] Not started
- [~] In progress
- [x] Done
- [!] Blocked — see note

---

## IMMEDIATE: Validation + early-warning module (this sprint)

- [ ] **T5.2 — 2009 Iridium-Cosmos collision scenario** (see VALIDATION.md)
      Use Shell_B_800km with (S0≈500, D0≈2000 + 2000 fragment injection),
      integrate 20 years via `integrate_trajectory`, confirm D decays
      by ≥20% and no runaway. Currently marked skipped in the test suite —
      unskip once the scenario harness is written.

- [ ] **T5.3 — 2007 Chinese ASAT test scenario** (see VALIDATION.md)
      Shell_B_800km (or a dedicated 850 km sub-shell), inject D_spike=3000,
      integrate 30 years, confirm persistence and no cascade. Also currently
      skipped; same unskipping workflow as T5.2.

- [ ] **Implement `src/early_warning.py`** (Task 7)
      Function: `critical_slowing_down(alpha_array, L_array)` — recovery time
      `τ(L) = 1 / |alpha(L)|` with divergence diagnostic as `L → L_fold`.
      Function: `variance_indicator(trajectory, window)` — rolling variance of D(t).
      Function: `autocorrelation_indicator(trajectory, lag=1)` — lag-1 AC of D(t).
      Function: `early_warning_summary(params, current_L)` — traffic-light
      (green/amber/red) keyed to `L_fold` (not Hopf `L_c` — the 2D model
      never produces one; see CLAUDE.md "What the engine has actually found").
      Acceptance tests T4.1–T4.5 in VALIDATION.md.

- [ ] Wire Task 7 into the existing pipeline script and re-run the full
      Shell A / B / C sweep so the dashboard (Module 3) has consistent
      `L_fold`-relative warning curves to consume.

---

## NEXT: Validation and calibration

- [ ] Run the full suite after each change: `pytest bifurcation_engine/tests/ -v`
      (expect 115 passing once T5.2, T5.3, and Task 7 tests are unskipped /
      added).

- [ ] Parameter-regime exploration — extend the γ-sensitivity study already
      done for Shell B to the full (β, γ, δ_S, δ_D) space. Map the boundary
      between "fold-only" regimes (current literature values) and any
      regime that might host a genuine Hopf. This is a publishable result
      regardless of which side the boundary falls on.

- [ ] Produce the equivalent of `reports/shell_B_bifurcation.png` for
      Shells A and C so all three shells have a presentation-ready
      bifurcation diagram with trajectory overlays.

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

- **Hopf bifurcation may not exist** in some or all shells with literature parameters.
  If this happens, document which parameter regime produces it and present the
  parameter exploration as a scientific result. Do not force it.

- **pySSEM gamma extraction** — the quadratic D^2 term is a simplification of
  pySSEM's NASA Breakup Model collision dynamics. Extracting an effective gamma
  requires fitting, which may introduce error. Document clearly.

- **Computational performance** — for the live demo (June 1), continuation sweep
  across L must run in seconds. Profile early. If slow, reduce N_shells or L_steps.
