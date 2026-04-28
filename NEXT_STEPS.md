# Orbital Sentinel — Next Steps Plan
**Last updated:** April 27, 2026
**Status:** Module 1 complete (248 passed, 0 skipped, 0 failed). Steps 1 and 2 done.
**Next session starts at Step 3.**

---

## Where we are

Module 1 is done. The bifurcation engine is complete, tested, and documented.
The Kessler tipping point is confirmed as a saddle-node fold across three model
variants and 2,400 parameter combinations. Early-warning indicators are
implemented and passing. The Hopf question is closed.

**Step 1 (real-world current state) is done.** Shell C is RED at L/L_fold=1.091.
`data/real_world/shell_current_state.json` and `reports/shell_B_bifurcation_realworld.png`
are produced.

**Step 2 (NASA ODQN historical scenarios) is done.** 248 passed, 0 skipped, 0 failed.
T5.2 (Iridium-Cosmos 2009) and T5.3 (Fengyun-1C 2007) are implemented and passing.
Historical data: `data/historical/iridium_cosmos_2009.json` and `data/historical/chinese_asat_2007.json`.

---

## Step 1 — Our World in Data pull
**Priority: IMMEDIATE — do this before Module 2**
**Estimated effort: half a day for Opus**

### What it is
Extract current real-world S (active satellites + rocket bodies) and D (debris
fragments) population estimates per shell from publicly available processed
Space Force data. No registration required.

### What Opus needs to do
1. Fetch the Our World in Data / Space Force LEO object dataset (tracked objects
   by type and altitude, 1958 to present)
2. Bin objects into the three reference shells:
   - Shell A: 550–650 km
   - Shell B: 750–850 km
   - Shell C: 950–1050 km
3. Map active satellites + rocket bodies → S, debris fragments → D per shell
4. Estimate L_current (recent annual launch cadence into each band)
5. Compute L_fraction = L_current / L_fold for each shell
6. Apply traffic light: green / amber / red per shell based on L_fraction
7. Write results to `data/real_world/shell_current_state.json`
8. Produce updated bifurcation diagram for Shell B with real-world current
   point marked: `reports/shell_B_bifurcation_realworld.png`

### Deliverables
- `data/real_world/shell_current_state.json`
- `reports/shell_B_bifurcation_realworld.png`
- Short note added to CLAUDE.md with the real-world L_fraction values

### Why this matters
This is the "where are we today" marker. When you show the bifurcation diagram
to ESA or at the June 1 presentation, the audience needs to see a dot on the
curve. Without it the diagram is pure math. With it, it's a warning system.

---

## Step 2 — NASA ODQN historical data for T5.2 and T5.3
**Priority: IMMEDIATE — must be done before June 1 demo**
**Estimated effort: half a day for Opus**

### What it is
Source pre-event population estimates for the two historical validation
scenarios that are currently skipped in the test suite. Unskip them and get
them passing.

### The two scenarios
- **T5.2 — 2009 Iridium-Cosmos collision** (February 10, 2009, ~789 km → Shell B)
  Pre-event S and D counts for Shell B before the collision occurred.
- **T5.3 — 2007 Chinese ASAT test** (January 11, 2007, FY-1C at ~850 km → Shell C)
  Pre-event S and D counts for Shell C before the ASAT fragmentation event.

### What Opus needs to do
1. Fetch relevant NASA Orbital Debris Quarterly News issues (2007 Q1, 2009 Q1)
   — these are publicly available PDFs from NASA's Orbital Debris Program Office
2. Extract pre-event population estimates for the relevant altitude bands
3. Write initial conditions to:
   - `data/historical/iridium_cosmos_2009.json`
   - `data/historical/chinese_asat_2007.json`
4. Unskip T5.2 and T5.3 in `test_validation_scenarios.py`
5. Run the full test suite — target: 231+ passed, 0 skipped, 0 failed
6. If tests don't pass with raw ODQN numbers, document what calibration was
   needed and why — do not force them to pass, document the gap honestly

### Deliverables
- Two JSON files with historical initial conditions
- Unskipped and passing T5.2 and T5.3 (or honest documentation of the gap)
- Final test count update in CLAUDE.md

### Why this matters
The June 1 demo needs to show the model reproduces known historical events.
"We validated against the Iridium-Cosmos collision" is a sentence that lands
with ESA. Without it the model is unvalidated against reality.

---

## Step 3 — Module 2: Scenario Simulator
**Priority: AFTER Steps 1 and 2**
**Scope to be planned in a dedicated session**

### What it is
The interactive browser-based frontend. React + D3.js. Users manipulate
parameters via sliders and see the bifurcation diagram update in real time.

### What it needs from Module 1 (which is why Steps 1 and 2 come first)
- Confirmed L_fold values per shell ✓ (done)
- Real-world current S, D, L_current per shell (Step 1)
- Early-warning indicator curves ✓ (done)
- Validated historical scenarios for credibility (Step 2)

### What the simulator will show
- Bifurcation diagram with current real-world position marked
- Sliders: launch rate L, debris removal rate, constellation size
- Three what-if scenarios: Starlink doubles, ESA removes 5 objects/year,
  major collision event tomorrow
- Traffic light updating in real time as sliders move
- Early-warning panel: recovery time, variance, autocorrelation curves

### Planning note
Do not start Module 2 until Step 1 is complete. The UI needs real data
attached from day one — synthetic placeholders are not acceptable for the
June 1 demo.

---

## Prompt to give Opus at the start of next session

> Read CLAUDE.md, TODO.md, TASKS.md, and VALIDATION.md and summarise current
> state before doing anything. Then proceed with Step 1 of NEXT_STEPS.md:
> the Our World in Data pull. Do not start Step 2 until Step 1 deliverables
> are confirmed.

---

## June 1 checklist (work backwards from here)

- [x] Module 1: Bifurcation engine complete
- [x] Task 7: Early-warning indicators implemented and passing
- [x] Hopf hunt closed, fold confirmed as tipping point
- [x] kessler_fold_summary.md and PDF produced
- [x] Step 1: Real-world S/D/L data per shell (Shell C RED, L/L_fold=1.091)
- [x] Step 2: T5.2 and T5.3 historical scenarios passing (248 passed, 0 skipped)
- [ ] Module 2: Scenario simulator (React + D3)
- [ ] Module 3: Early-warning dashboard
- [ ] Phase 2: pySSEM parameter calibration
- [ ] Phase 2: Space-Track live data integration
- [ ] Business model slide (already in proposal scope)
