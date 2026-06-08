# Orbital Sentinel

A decision-support simulation tool that applies **bifurcation theory** to model and
anticipate the **Kessler-syndrome tipping point** in Low Earth Orbit (LEO).

Built for **TeSI 2026** (Technology for Social Innovation), a 15-week course run
jointly by **ESADE, UPC, and IED** under the EU **Tech2X / Fusion Point Academy**
programme. The underlying methodology is **HOPFEL**, developed at the European XFEL
by Giovanni Perosa, here translated from Free-Electron-Laser dynamics to orbital
debris dynamics.

---

## What it does

Orbital Sentinel is a full-stack interactive tool. It has a bifurcation engine in
Python, a FastAPI backend, and a React + D3 frontend. For each altitude shell in LEO
the engine:

1. Defines a 2-D source-sink ODE for active-satellite population `S(t)` and
   trackable-debris population `D(t)`.
2. Solves for every fixed point and tracks them across the launch rate `L` via
   warm-started continuation.
3. Computes the Jacobian spectrum along each branch and checks for Hopf and
   saddle-node (fold) bifurcations.
4. Integrates full nonlinear trajectories at sub-critical, critical, and
   super-critical launch rates.
5. Emits early-warning indicators (recovery time, variance, lag-1 autocorrelation)
   and a green / amber / red traffic light keyed to `L_fold`.
6. Overlays the real-world current state from the Space-Track GP catalog on each
   bifurcation diagram.

```
S_dot = L - delta_S * S - beta * S * D
D_dot = beta * S * D + gamma * D^2 - delta_D * D
```

`gamma * D^2` is the Kessler term. Once `D` is large enough, debris-on-debris
cascade dominates atmospheric drag and the population runs away regardless of `S`.

---

## Key scientific findings

### The tipping point is a saddle-node fold, not a Hopf bifurcation

With literature-calibrated parameters, the 2-D model does not host a Hopf
bifurcation on any branch of any shell. The Kessler tipping point manifests as a
**saddle-node (fold) bifurcation**: the stable lower branch and the unstable upper
branch collide and annihilate at `L_fold`, after which no stable equilibrium exists
and `D(t)` runs away.

This result was confirmed to be structural across three independently implemented
model variants:

| Model variant | Description | Hopf found? |
|---|---|---|
| 2-D `(S, D)` | Production model + 50x gamma sensitivity sweep | No |
| 3-species `(S, R, D)` | Adds derelict population `R` | No |
| Split-decay `(S, R, D)` | Separates controlled deorbit from on-orbit failure; 2,400-cell sweep | No |

The trace inequality explains why: as `L` approaches `L_fold` along the lower branch,
the `2*gamma*D*` Kessler term drives the trace positive at the same `L` at which the
fold removes the branch. The fold and the trace instability fire simultaneously,
leaving no window for a Hopf crossing.

### Confirmed fold launch rates

| Shell | Altitude | L_fold [objects/yr] | (S_fold, D_fold) |
|---|---|---|---|
| Shell A | 600 km | ~25,100 | (5.01e3, 4.99e5) |
| Shell B | 800 km | ~670 | (668, 6.65e4) |
| Shell C | 1000 km | ~31.5 | (251, 1.24e4) |

### Real-world current state (Space-Track GP catalog, April 2026)

L_current is a 3-year trailing average (2022-2024, ~2,291 LEO obj/yr) x
altitude-band fraction from the ESA MASTER model.

| Shell | S (live) | D (live) | L_current [obj/yr] | L / L_fold | Status |
|---|---|---|---|---|---|
| Shell A 600 km | 2,157 | 541 | 1,329 | 0.053 | green |
| Shell B 800 km | 620 | 2,259 | 206 | 0.308 | green |
| **Shell C 1000 km** | **545** | **873** | **34.4** | **1.091** | **RED** |

Shell C is past its fold threshold on current launch rates. The red status is driven
by launch rate alone; the historical debris cloud from Fengyun-1C (2007) and
Iridium-Cosmos (2009) has decayed below 950 km by 2026.

> The model is a steady-state warning system. Being above L_fold means no stable
> equilibrium exists, not that catastrophe is immediate. Runaway takes decades from
> the current low-D initial condition. The fold is a structural risk indicator.

---

## The tool

The frontend has four tabs:

- **The Crisis** — plain-language explanation of Kessler syndrome, Shell C red-alert
  status, policy gap analysis, and current international initiatives.
- **Simulator** — interactive what-if tool. Adjust launch rate multiplier, debris
  removal rate, and cascade intensity. Traffic lights update in real time across all
  three shells.
- **Bifurcation Analysis** — full bifurcation diagrams with real-world current-state
  markers, early-warning indicator curves, and the scientific methodology.
- **Take Action** — a formal petition to the European Commission drafted under the
  European Citizens' Initiative regulation (EU) 211/2011, plus links to the ESA Zero
  Debris Charter and MEP contact search.

---

## Repository layout

```
orbital-sentinel/
├── README.md
├── CLAUDE.md                          full scientific context and findings
├── TODO.md                            task status
├── VALIDATION.md                      acceptance criteria
├── bifurcation_engine/
│   ├── src/                           engine source (model, solver, indicators)
│   ├── tests/                         231 passed, 1 skipped
│   ├── notebooks/engine_demo.ipynb
│   └── requirements.txt
├── api/
│   ├── engine_bridge.py               compute_whatif() wrapper
│   └── main.py                        FastAPI: /api/base, /api/whatif, /api/live
├── mission-control/
│   └── orbital-sentinel-repo/
│       ├── frontend/
│       │   ├── index.html             entry point
│       │   ├── app.jsx                4-tab React app
│       │   ├── scene.js               Three.js globe
│       │   ├── styles.css
│       │   └── data/                  pre-computed JSON (runs offline)
│       │       ├── base_curves.json
│       │       ├── indicator_curves.json
│       │       └── shell_current_state.json
│       └── backend/
│           ├── .env.example           credential template
│           └── README.md
├── frontend/
│   └── vendor/                        D3 v7, React 18, Babel (offline bundle)
├── scripts/
│   ├── export_frontend_data.py        pre-computes frontend JSON files
│   └── fetch_realworld_data.py        Space-Track / Celestrak data pull
├── data/
│   ├── parameters/shell_defaults.json
│   └── real_world/shell_current_state.json
├── petition/
│   └── PETITION_BLUEPRINT.txt         ECI petition blueprint
└── reports/
    ├── kessler_fold_summary.md
    └── split_decay_sweep_summary.md
```

---

## Installation

Requires **Python 3.10+**.

```bash
git clone git@github.com:foziD123/orbital-sentinel.git
cd orbital-sentinel

python3 -m venv .venv
source .venv/bin/activate

pip install -r bifurcation_engine/requirements.txt
pip install fastapi "uvicorn[standard]" pydantic
```

---

## Running the tool

### Step 1 — Pre-compute static data (run once)

```bash
PYTHONPATH=. python scripts/export_frontend_data.py
```

Writes three JSON files into `mission-control/orbital-sentinel-repo/frontend/data/`
so the diagrams render even when the API server is not running.

### Step 2 — Start the API server

Without live Space-Track data (uses cached April 2026 snapshot):

```bash
PYTHONPATH=. .venv/bin/uvicorn api.main:app --port 8000
```

With live Space-Track data:

```bash
PYTHONPATH=. \
  SPACETRACK_USER="your@email.com" \
  SPACETRACK_PASS="yourpassword" \
  .venv/bin/uvicorn api.main:app --port 8000
```

A free Space-Track account can be created at https://www.space-track.org/auth/createAccount.
Without credentials the tool falls back to the cached snapshot automatically and
works fully.

### Step 3 — Serve the frontend

```bash
cd mission-control/orbital-sentinel-repo/frontend
python3 -m http.server 3000
```

Open http://localhost:3000.

---

## Engine only

### Run the tests

```bash
pytest bifurcation_engine/tests/ -v
```

Expected: **231 passed, 1 skipped**.

### Detect the fold for a single shell

```python
from bifurcation_engine.src.shell_config import load_shell_by_name
from bifurcation_engine.src.hopf_detector import detect_fold
import numpy as np

shell_B = load_shell_by_name("Shell_B_800km")
fold = detect_fold(shell_B, L_values=np.linspace(1.0, 1200.0, 4001))
print(fold.description)
# Shell_B_800km: saddle-node fold at L ~670.0 objects/yr
```

### Get the traffic light

```python
from bifurcation_engine.src.early_warning import early_warning_summary

summary = early_warning_summary(shell_B, L_values=np.linspace(1.0, 1200.0, 4001),
                                fold_result=fold)
print(summary["fold_channel"]["traffic_light"])   # green / amber / red
print(summary["fold_channel"]["L_fraction"])       # L_current / L_fold
```


