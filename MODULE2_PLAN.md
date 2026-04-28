# Module 2 — Scenario Simulator: Architecture Plan
**Date:** April 27, 2026
**Status:** Ready to implement — plan approved
**Prerequisite:** Module 1 complete (248 passed, 0 skipped, 0 failed) ✅

---

## What the user sees

Three bifurcation diagrams side by side, one per shell (A 600km, B 800km, C 1000km),
all visible simultaneously. Each shows the D* vs L equilibrium curve with the
real-world current position marked as an orange star.

A control panel lets the user build what-if scenarios sequentially. Each scenario
adds a new overlay curve to all three diagrams at once. A traffic light per shell
updates as scenarios are added. Up to 5 overlays before a "clear all" resets the view.

---

## Tech stack

```
frontend/
  index.html
  app.jsx              ← React (state management, scenario list, UI)
  chart.js             ← D3 (bifurcation diagrams, overlays, markers)
  styles.css

api/
  main.py              ← FastAPI, 3 endpoints
  engine_bridge.py     ← thin wrapper around existing bifurcation engine

scripts/
  export_frontend_data.py   ← pre-computes base curves, dumps to frontend/data/
```

**Runtime on demo day:**
- `uvicorn api.main:app --port 8000` in one terminal
- Open `frontend/index.html` in browser — that's it
- Everything runs offline, no internet required

---

## Architecture: hybrid pre-computed + live API

### On page load (pre-computed, instant — no API call)
```
frontend/data/base_curves.json        → bifurcation diagrams render immediately
frontend/data/shell_current_state.json → real-world markers placed
frontend/data/indicator_curves.json   → recovery time / variance curves
```
Page is fully functional the moment it opens. If FastAPI isn't running,
the base view still works — critical for demo reliability.

### On what-if scenario (live API, ~3–5 seconds)
```
User sets parameters
  → POST /api/whatif
  → engine runs continuation sweep for all three shells
  → returns new bifurcation curves + L_fold + traffic light per shell
  → new coloured overlay curve added to each diagram
  → traffic lights update
```

---

## API contract

### GET /api/base
Returns pre-computed base data for all shells. Fallback only — rarely called
since static JSON files handle this.

### POST /api/whatif
**Request body:**
```json
{
  "L_multiplier": 2.0,
  "debris_removal_rate": 0.0,
  "gamma_multiplier": 1.0,
  "label": "Starlink doubles"
}
```

**Response:**
```json
{
  "label": "Starlink doubles",
  "color": "#E76F51",
  "shells": {
    "A": {
      "L_fold_new": 25100,
      "L_current_new": 2282,
      "traffic_light": "green",
      "curve": [{"L": 0, "D_star": 0}, ...]
    },
    "B": {
      "L_fold_new": 670,
      "L_current_new": 354,
      "traffic_light": "green",
      "curve": [...]
    },
    "C": {
      "L_fold_new": 31.5,
      "L_current_new": 68.8,
      "traffic_light": "red",
      "curve": [...]
    }
  }
}
```

All three shells are computed in a **single API call** — not three separate
calls — to avoid race conditions and reduce total latency.

### DELETE /api/whatif/clear
Clears server-side scenario state. Frontend resets to base view.

---

## What-if scenario presets

Three preset buttons pre-fill the parameter inputs. User can also enter
custom values. Each scenario gets a unique colour assigned automatically.

| Preset | L_multiplier | debris_removal_rate | gamma_multiplier | Narrative |
|--------|-------------|---------------------|-----------------|-----------|
| Starlink doubles | 2.0 | 0 | 1.0 | What if launch cadence doubles? |
| ESA removes 5/yr | 1.0 | 5 | 1.0 | What if active removal starts? |
| Major collision | 1.0 | 0 | 1.5 | What if a large fragmentation event occurs? |

Overlay colour palette (assigned in order):
`#E76F51, #2A9D8F, #E9C46A, #9B5DE5, #F72585`

Soft cap: 5 overlays maximum. After 5, "Clear all scenarios" button appears
prominently. Clearing resets all overlays and traffic lights to base state.

---

## Bifurcation diagram spec (per shell, D3)

- **X axis:** L (launch rate, objects/year), range 0 → 1.2 × L_fold_base
- **Y axis:** D* (debris equilibrium count), log scale
- **Lower branch:** solid blue line — the stable operating state
- **Upper branch:** dashed blue line — the instability threshold
- **L_fold line:** red dashed vertical — labelled "Point of no return"
- **Real-world marker:** orange star at (L_current, D_current) with tooltip
- **What-if overlays:** each scenario adds its own coloured curve + L_fold line
  in matching colour
- **Traffic light:** coloured dot (🟢/🟡/🔴) in top-right corner of each diagram
- **Shell label:** "Shell A — 600 km" etc. as diagram title
- **Tooltip on hover:** shows exact L, D*, distance to L_fold as percentage

---

## Latency and UX strategy

| Interaction | Behaviour |
|-------------|-----------|
| Slider drag | Debounce 400ms — API call fires only after user stops moving |
| What-if button | Shows spinner + "Computing..." for duration of API call |
| API timeout >8s | Toast error: "Computation failed — try again" — existing overlays preserved |
| Page load | Instant — static JSON, no API dependency |
| FastAPI down | Page still loads and shows base curves — graceful degradation |

---

## Failure handling for demo day

- Base curves load from static files — diagram works even if API is down
- What-if failures show a non-blocking toast, don't break existing overlays
- No CDN dependencies — bundle everything locally
- Single laptop, single user — no concurrency issues expected
- Test the full flow the night before: start FastAPI, open browser, run all
  three presets, verify overlays appear correctly

---

## Build order

Build and verify each step before moving to the next.
Do not start the API before the static diagrams render correctly.

**Step 1 — Export script**
`scripts/export_frontend_data.py`
Runs the bifurcation engine on all three shells, exports:
- `frontend/data/base_curves.json` — lower + upper branch curves per shell
- `frontend/data/shell_current_state.json` — copy of existing real-world state
- `frontend/data/indicator_curves.json` — recovery time, variance, AC curves
Verify JSON structure before proceeding.

**Step 2 — API layer**
`api/engine_bridge.py` — import existing engine functions, expose
`compute_whatif(L_multiplier, debris_removal_rate, gamma_multiplier)` → dict

`api/main.py` — FastAPI with three endpoints. Test with curl before
touching the frontend:
```bash
curl -X POST http://localhost:8000/api/whatif \
  -H "Content-Type: application/json" \
  -d '{"L_multiplier": 2.0, "debris_removal_rate": 0, "gamma_multiplier": 1.0, "label": "test"}'
```

**Step 3 — Static diagrams**
`frontend/chart.js` — D3 component rendering base curves for one shell first,
then generalise to three. Get the axes, lower branch, upper branch, and L_fold
line rendering correctly with static data before adding any dynamic behaviour.

**Step 4 — React shell**
`frontend/app.jsx` — wire static JSON to D3 charts, render all three shells
side by side. Add real-world markers and traffic lights. Page should look
complete at this point with no interactivity yet.

**Step 5 — What-if panel**
Add the control panel: preset buttons, parameter sliders/inputs, scenario list.
Connect to API. Add loading states. Add overlay curve rendering in D3.

**Step 6 — Overlay management**
Scenario list showing active overlays with colour swatches and labels.
Individual remove buttons per overlay. "Clear all" button after 5 overlays.
Traffic light updates per shell per scenario.

**Step 7 — Polish**
- Responsive layout (works on the demo laptop screen size)
- Tooltips on diagram hover
- Smooth D3 transitions when overlays are added/removed
- Colour contrast and readability check
- Test all three presets end-to-end

---

## Prompt for Opus/Composer

Paste this prompt at the start of the implementation session:

---

> Read CLAUDE.md, TODO.md, TASKS.md, and MODULE2_PLAN.md before doing
> anything. Summarise current state in one paragraph, then proceed.
>
> You are implementing Module 2 of Orbital Sentinel: the interactive
> scenario simulator. The full architecture is specified in MODULE2_PLAN.md.
> Follow the build order exactly — do not skip steps or build ahead.
>
> Start with Step 1: write scripts/export_frontend_data.py, run it, and
> show me the structure of the output JSON files before proceeding to Step 2.
>
> Constraints:
> - Do not modify any file in bifurcation_engine/ — the engine is complete
>   and must remain untouched
> - The frontend must work with base curves even if FastAPI is not running
> - All three shells must be computed in a single /api/whatif call
> - Maximum 5 what-if overlays before clear-all is required
> - Test each step before moving to the next
>
> Report completion of each step before starting the next.
