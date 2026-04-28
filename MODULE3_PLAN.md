# Module 3 — Early-Warning Dashboard: Architecture Plan
**Date:** April 28, 2026
**Status:** Ready to implement
**Prerequisites:** Module 1 ✅, Module 2 ✅, Step 1 real-world data ✅

---

## What this is

A monitoring panel — the "weather forecast for orbital stability."
Non-technical stakeholders open this page and immediately understand
where each shell stands relative to its tipping point.

No sliders. No interaction. Just a clear, honest status display.

---

## Architecture decisions

**Data: live Space-Track query on page load.**
On every load, the dashboard calls a new FastAPI endpoint `GET /api/live`
which runs the fetch logic from scripts/fetch_realworld_shell_state.py,
queries Space-Track in real time, bins objects into shells, computes
L_current, L_fraction, traffic light, trend arrow, and returns fresh
shell state as JSON. Space-Track credentials stay in the Python environment
— never exposed in the browser.

Query latency is 10–30 seconds. The dashboard shows a full-page loading
state during fetch: spinner + "Fetching live debris data from Space-Track..."
Once data arrives, the page renders completely.

Fallback: if the Space-Track query fails, fall back to
data/real_world/shell_current_state.json and show a banner:
"⚠️ Live query failed — showing last cached snapshot (timestamp)."

**Location: frontend/dashboard.html**
Third page alongside index.html (Simulator) and historical.html (Historical
Validation). All three connected by a shared nav bar.

**One new API endpoint: GET /api/live**
Wraps the existing fetch logic. Returns:
```json
{
  "retrieved_utc": "2026-04-28T15:30:00Z",
  "source": "Space-Track.org GP catalog",
  "shells": {
    "A": {
      "S": 2157, "D": 541,
      "L_current": 1141, "L_fold": 25100,
      "L_fraction": 0.045, "traffic_light": "green",
      "trend": "stable"
    },
    "B": { ... },
    "C": { ... }
  }
}
```

**Trend arrow logic:**
Compare L_current (3yr average) to the previous year's rate from
the same Space-Track data. If rising >5%: "↑ increasing".
If falling >5%: "↓ decreasing". Otherwise: "→ stable".


---

## Page structure

### Header
Title: "Orbital Sentinel — Early Warning Dashboard"
Subtitle: "Live debris monitoring for Low Earth Orbit altitude shells"
Last updated timestamp from shell_current_state.json
One-line explainer: "Green = safely below tipping point.
Amber = approaching critical zone. Red = at or past tipping point."

---

### Section 1 — Shell Status Overview (top of page)

Three large status cards side by side, one per shell.
This is the first thing the audience sees — the answer before the explanation.

**Each card contains:**
- Shell name and altitude (e.g. "Shell B — 800 km")
- Large traffic light indicator (🟢 / 🟡 / 🔴) with status text
- L/L_fold fraction as a progress bar (0% → 100% → past threshold)
- Key numbers displayed as a stat grid:
  - S — active satellites + intact rocket bodies (live count)
  - D — trackable debris fragments (live count)
  - L_current — current launch rate (objects/year, 3yr avg)
  - L_fold — tipping point threshold (objects/year)
  - Trend arrow — ↑ increasing / → stable / ↓ decreasing
- One-sentence plain-language interpretation:
  - Green: "Well within safe operating margin"
  - Amber: "Approaching tipping point — recovery time increasing"
  - Red: "At or past tipping point — launch rate exceeds critical threshold"

**Card colours:**
- Green card: dark green border, light green background
- Amber card: dark amber border, light amber background
- Red card: dark red border, light red background

---

### Section 2 — Early Warning Indicators (per shell)

Three columns, one per shell. Each column shows three indicator charts
stacked vertically. Charts are compact — this is a monitoring panel,
not a research tool.

**Indicator 1: Recovery Time**
- X axis: L (launch rate, 0 → L_fold)
- Y axis: τ = 1/|α| (years)
- Curve: recovery time rising steeply as L → L_fold
- Current L marked as vertical orange line
- Annotation: "Time for debris to return to equilibrium after disturbance"
- Key message: the closer to L_fold, the longer recovery takes

**Indicator 2: Debris Trajectory Variance**
- X axis: time window
- Y axis: rolling variance of D(t)
- Annotation: "Variance inflates as the system approaches the tipping point"

**Indicator 3: Lag-1 Autocorrelation**
- X axis: time window
- Y axis: lag-1 AC of D(t) (0 → 1)
- Reference line at AC = 1.0
- Annotation: "Approaches 1 near the tipping point — system loses memory"

Data source: frontend/data/indicator_curves.json (already exported by
export_frontend_data.py in Module 2).

---

### Section 3 — What the Numbers Mean

Plain-language explainer panel. Two columns:

**Left: The tipping point explained**
"Each shell has a critical launch rate — L_fold — beyond which no stable
low-debris equilibrium exists. Below it, perturbations (collisions, failures)
decay over time. Above it, debris grows without bound regardless of any
action taken."

**Right: What the traffic light means for policy**
- 🟢 Green (L < 80% of L_fold): Wide margin. Standard monitoring.
- 🟡 Amber (80–95% of L_fold): Recovery times lengthening. New constellation
  deployments should be evaluated against remaining margin.
- 🔴 Red (L ≥ 95% of L_fold): At or past the fold. Structurally past the
  tipping point. Reducing launch rate alone may not restore the safe equilibrium.

---

### Section 4 — Shell C Alert Panel (conditional)

Shown only if Shell C is RED (which it currently is).
A distinct alert box below the main content:

**"⚠️ Shell C is currently past its critical launch threshold"**

"The 1,000 km band has a confirmed tipping point of ~31.5 new objects per
year. The current 3-year average launch rate into this band is ~34.4/yr —
109% of that threshold. The historical debris from the 2007 Fengyun-1C ASAT
test has largely decayed. Shell C is in red status because of current launch
activity, not legacy events."

Link to historical.html: "See historical validation →"

This panel makes the headline finding unmissable for non-technical audiences.

---

## Data requirements

| Data needed | Source |
|-------------|--------|
| S, D, L_current, L_fold, L_fraction, traffic_light, trend per shell | GET /api/live (live Space-Track query) |
| Fallback if live fails | data/real_world/shell_current_state.json |
| Recovery time curves per shell | frontend/data/indicator_curves.json |
| Variance and AC curves per shell | frontend/data/indicator_curves.json |

Check whether indicator_curves.json already contains variance and AC curves.
If missing, extend export_frontend_data.py to add them and re-run before
building the frontend.

---

## Navigation

Update nav bar on all three pages:
- "Simulator" → index.html
- "Historical Validation" → historical.html
- "Dashboard" → dashboard.html (new)

---

## Visual tone

Same palette and typography as index.html and historical.html.
Compact, data-dense but readable. Designed for a non-technical audience
standing in front of a projector — large text, clear colour coding,
minimal jargon. Every number has a label. Every label has a unit.

---

## What not to do

- Do not add live Space-Track querying — static snapshot only
- Do not add interactivity — this is a monitoring display, not a simulator
- Do not show raw eigenvalue data or Jacobian values — translate everything
  into plain language
- Do not claim the indicators are operational — frame as research prototype
- Do not modify bifurcation_engine/ or any existing test files

---

## Prompt for Opus

---

> Before doing anything:
> 1. Read CLAUDE.md, TODO.md, NEXT_STEPS.md, MODULE2_PLAN.md, and MODULE3_PLAN.md in full
> 2. Update CLAUDE.md and TODO.md to record that Module 2 (scenario simulator
>    + historical validation page) is complete. Mark all Module 2 items as [x]
>    in TODO.md. Add a "Module 2 — Completion Status (April 28 2026)" section
>    to CLAUDE.md noting what was built: FastAPI backend, three endpoints,
>    D3 bifurcation diagrams for all three shells, real-world markers, traffic
>    lights, what-if overlay system (5 scenarios max), preset buttons, and
>    historical.html with Iridium-Cosmos and Fengyun-1C validation pages.
>    Do not touch any source files or tests — MD files only.
> 3. Confirm MD updates are done, then proceed to Module 3.
>
> You are implementing Module 3: the early-warning dashboard.
> The full specification is in MODULE3_PLAN.md. Follow it exactly.
>
> Implementation order:
>
> 1. Add GET /api/live endpoint to api/main.py. It wraps the existing
>    fetch logic from scripts/fetch_realworld_shell_state.py — queries
>    Space-Track, bins objects into shells, computes L_current (3yr avg),
>    L_fraction, traffic_light, and trend arrow (compare current year vs
>    previous year: >5% rise = increasing, >5% fall = decreasing, else stable).
>    Returns the full shell state JSON as specified in MODULE3_PLAN.md.
>    Implement a fallback: if Space-Track query fails, load and return
>    data/real_world/shell_current_state.json with a "cached": true flag.
>    Test with curl before touching the frontend.
>
> 2. Check whether frontend/data/indicator_curves.json contains variance
>    and lag-1 AC curves in addition to recovery time. If missing, extend
>    scripts/export_frontend_data.py to add them and re-run it. Show me
>    the updated JSON structure before proceeding.
>
> 3. Create frontend/dashboard.html. Build Section 1 (shell status cards
>    with live data, loading spinner, trend arrows, progress bars) first.
>    Get it rendering correctly with live data before adding charts.
>
> 4. Add Section 2 (indicator charts — recovery time, variance, AC per shell)
>    reusing existing D3 components from chart.js wherever possible.
>
> 5. Add Section 3 (plain-language explainer) and Section 4 (Shell C alert
>    panel — rendered only when Shell C traffic_light === "red").
>
> 6. Update nav bar on index.html and historical.html to include Dashboard link.
>
> 7. Verify full dashboard loads, live query fires, loading spinner appears,
>    and data renders correctly.
>
> Constraints:
> - Space-Track credentials must stay server-side — never in the browser
> - Loading spinner must show during the 10–30 second Space-Track query
> - Fallback to cached JSON if live query fails — show warning banner
> - Do not modify bifurcation_engine/ or any test files
> - Every number must have a label and a unit
> - Frame all output as research prototype, not operational system
> - Reuse existing D3 components from chart.js — do not rewrite it
>
> Report completion of each step before starting the next.
