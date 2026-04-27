# Orbital Sentinel

A decision-support simulation tool that applies **bifurcation theory** to model and
anticipate the **Kessler-syndrome tipping point** in Low Earth Orbit (LEO).

Built for **TeSI 2026** (Technology for Social Innovation) — a 15-week course run
jointly by **ESADE, UPC, and IED** under the EU **Tech2X / Fusion Point Academy**
programme. The underlying methodology is **HOPFEL**, developed at the European XFEL
by Giovanni Perosa, here translated from Free-Electron-Laser dynamics to orbital
debris dynamics.

---

## What the engine does

For each altitude shell in LEO, Orbital Sentinel:

1. Defines a 2-D source–sink ODE for active-satellite population `S(t)` and
   trackable-debris population `D(t)`.
2. Solves for every fixed point and tracks them smoothly across the launch
   rate `L` via a warm-started continuation sweep.
3. Computes the Jacobian spectrum `(α, ω)` along each branch and checks for
   **Hopf** and **saddle-node (fold)** bifurcations explicitly.
4. Integrates the full nonlinear trajectories at sub-critical, critical, and
   super-critical launch rates to verify the predicted tipping behaviour.
5. Emits **early-warning indicators** (recovery time, variance, lag-1
   autocorrelation) and a green / amber / red traffic light keyed to `L_fold`.
6. Overlays the **real-world current state** (live Space-Track GP catalog)
   on the bifurcation diagram so the model has a concrete anchor.

```
S_dot = L − δ_S · S − β · S · D
D_dot = β · S · D + γ · D² − δ_D · D
```

`γ · D²` is the Kessler term — once `D` is large enough, debris-on-debris
cascade dominates atmospheric drag and the population runs away regardless of `S`.

---

## Key scientific findings (Phase 1, April 2026)

### The tipping point is a saddle-node fold, not a Hopf bifurcation

With literature-calibrated parameters, the 2-D model does **not** host a Hopf
bifurcation on any branch of any shell. The Kessler tipping point manifests as a
**saddle-node (fold) bifurcation**: the stable lower branch and the unstable upper
branch collide and annihilate at `L_fold`, after which no stable equilibrium exists
and `D(t)` runs away.

This result was confirmed to be **structural** across three independently implemented
model variants:

| Model variant | Description | Hopf found? |
|---|---|---|
| 2-D `(S, D)` | Production model + 50× γ sensitivity sweep | No |
| 3-species `(S, R, D)` | Adds derelict population `R` | No |
| Split-decay `(S, R, D)` | Separates controlled deorbit from on-orbit failure; 2 400-cell sweep | No |

The trace inequality `tr(J) = −(δ_S + δ_D) + β(S*−D*) + 2γD*` shows why: as
`L → L_fold` along the lower branch, the `2γD*` Kessler term drives the trace
positive at the same `L` at which the fold removes the branch. The fold and the
trace instability fire simultaneously — there is no window for a Hopf crossing.

### Confirmed fold launch rates

| Shell | Altitude | `L_fold` [objects/yr] | `(S_fold, D_fold)` |
|---|---|---|---|
| Shell A | 600 km | ≈ 25 100 | (5.01 × 10³, 4.99 × 10⁵) |
| Shell B | 800 km | ≈ 670 | (668, 6.65 × 10⁴) |
| Shell C | 1000 km | ≈ 31.5 | (251, 1.24 × 10⁴) |

### Real-world current state (Space-Track GP catalog, April 27 2026)

L_current is a 3-year trailing average (2022–2024, ~2 291 LEO obj/yr) ×
altitude-band fraction from the ESA MASTER model.

| Shell | S (live) | D (live) | L_current [obj/yr] | L / L_fold | Traffic light |
|---|---|---|---|---|---|
| Shell A 600 km | 2 157 | 541 | 1 329 | 0.053 | **green** |
| Shell B 800 km | 620 | 2 259 | 206 | 0.308 | **green** |
| **Shell C 1000 km** | **545** | **873** | **34.4** | **1.091** | **RED** |

Shell C is past its fold threshold on current launch rates — even though its debris
count (873) is low, because the Fengyun-1C (2007) and Iridium-Cosmos (2009) fragments
have decayed below 950 km by 2026. The RED status is driven by launch rate alone.

> *The model is a steady-state warning system: being above L_fold means no stable
> equilibrium exists, not that catastrophe is immediate. Runaway takes decades from
> the current low-D initial condition. The fold is a structural risk indicator, not
> a real-time alarm.*

---

## Repository layout

```
orbital-sentinel/
├── README.md
├── CLAUDE.md                        ← full scientific context + findings
├── TASKS.md                         ← technical task breakdown
├── TODO.md                          ← current task list and status
├── VALIDATION.md                    ← acceptance criteria
├── NEXT_STEPS.md                    ← session handoff / roadmap
├── bifurcation_engine/
│   ├── src/
│   │   ├── shell_config.py          ← altitude-shell parameters + loader
│   │   ├── model.py                 ← 2-D + 3-species ODEs
│   │   ├── fixed_points.py          ← continuation solver (2-D + 3-species)
│   │   ├── eigenvalues.py           ← Jacobian + (α, ω) tracker (2-D + 3-species)
│   │   ├── hopf_detector.py         ← Hopf + saddle-node fold detectors
│   │   ├── integrator.py            ← RK45 nonlinear trajectories
│   │   ├── early_warning.py         ← CSD indicators + traffic-light summary
│   │   ├── split_decay_config.py    ← split-decay (κ_S / ϱ_S) config
│   │   ├── model_split.py           ← split-decay ODE
│   │   ├── fixed_points_split.py    ← split-decay continuation
│   │   ├── eigenvalues_split.py     ← split-decay Jacobian + tracker
│   │   └── hopf_detector_split.py   ← split-decay fold detector
│   ├── tests/                       ← 231 passed, 1 skipped
│   ├── notebooks/
│   │   └── engine_demo.ipynb
│   └── requirements.txt
├── data/
│   ├── parameters/
│   │   └── shell_defaults.json      ← literature-calibrated shell parameters
│   └── real_world/
│       └── shell_current_state.json ← live Space-Track snapshot (Apr 2026)
├── scripts/
│   ├── plot_shell_B_bifurcation.py           ← Shell B diagram (math only)
│   ├── plot_shell_B_bifurcation_realworld.py ← Shell B diagram + real-world marker
│   ├── fetch_realworld_data.py               ← Space-Track / Celestrak data pull
│   └── run_split_decay_sweep.py              ← 2 400-cell Hopf-hunt sweep
└── reports/
    ├── shell_B_bifurcation.png
    ├── shell_B_bifurcation_realworld.png
    ├── kessler_fold_summary.md
    ├── split_decay_sweep_summary.md
    └── split_decay_sweep_Shell_{B,C}_*.{csv,png}
```

---

## Installation

Requires **Python ≥ 3.10**.

```bash
git clone git@github.com:foziD123/orbital-sentinel.git
cd orbital-sentinel

python3 -m venv .venv
source .venv/bin/activate

pip install -r bifurcation_engine/requirements.txt
```

---

## Quick start

### Run the test suite

```bash
pytest bifurcation_engine/tests/ -v
```

Expected: **231 passed, 1 skipped**. The skip covers the historical-scenario
module (T5.2 Iridium–Cosmos 2009, T5.3 Fengyun-1C 2007) pending the NASA ODQN
data pull — tracked in [`TODO.md`](TODO.md).

### Detect the fold for a single shell

```python
from bifurcation_engine.src.shell_config import load_shell_by_name
from bifurcation_engine.src.hopf_detector import detect_fold
import numpy as np

shell_B = load_shell_by_name("Shell_B_800km")
fold = detect_fold(shell_B, L_values=np.linspace(1.0, 1200.0, 4001))
print(fold.description)
# → Shell_B_800km: saddle-node fold at L ≈ 670.0 objects/yr,
#   merged coexistence equilibrium (S*, D*) ≈ (6.68e+02, 6.65e+04).
```

### Get the early-warning traffic light

```python
from bifurcation_engine.src.early_warning import early_warning_summary

summary = early_warning_summary(shell_B, L_values=np.linspace(1.0, 1200.0, 4001),
                                fold_result=fold)
print(summary["fold_channel"]["traffic_light"])   # green / amber / red
print(summary["fold_channel"]["L_fraction"])       # L_current / L_fold
```

### Integrate a trajectory past the fold

```python
from bifurcation_engine.src.integrator import integrate_trajectory
from dataclasses import replace

params_above = replace(shell_B, L=1.5 * fold.L_fold)
traj = integrate_trajectory(S0=668.0, D0=1.0, params=params_above)
print(f"D(t_end) = {traj['D'][-1]:.2e}, terminated_early = {traj['terminated_early']}")
# → Runaway: terminated early at the runaway_ceiling_D.
```

### Regenerate the bifurcation diagrams

```bash
# Math-only diagram
.venv/bin/python scripts/plot_shell_B_bifurcation.py

# With real-world current-state marker (requires shell_current_state.json)
.venv/bin/python scripts/plot_shell_B_bifurcation_realworld.py
```

### Refresh the real-world data (Space-Track account required)

```bash
.venv/bin/python scripts/fetch_realworld_data.py \
    --user your@email.com --pass yourpassword
# Falls back to Celestrak, then ESA SER 2024 hard-coded values if unavailable.
```

---

## Status

**Module 1 — bifurcation engine: complete.** 231 passed, 1 skipped.

| Item | Status |
|---|---|
| `shell_config.py` — altitude-shell parameters | done |
| `model.py` — 2-D + 3-species ODEs | done |
| `fixed_points.py` — continuation solver | done |
| `eigenvalues.py` — Jacobian + eigenvalue tracker | done |
| `hopf_detector.py` — Hopf + fold detectors | done |
| `integrator.py` — RK45 nonlinear trajectories | done |
| `early_warning.py` — CSD indicators + traffic light | done |
| 3-species `(S, R, D)` extension | done |
| Split-decay Hopf-hunt (2 400-cell sweep) | done — zero Hopf found |
| Step 1 — real-world current-state pull (Space-Track) | done |
| T5.2 — Iridium–Cosmos 2009 historical scenario | pending NASA ODQN pull |
| T5.3 — Fengyun-1C 2007 historical scenario | pending NASA ODQN pull |
| Module 2 — scenario simulator | scheduled |
| Module 3 — early-warning dashboard | scheduled |
| Phase 2 — MOCAT-pySSEM parameter calibration | scheduled |

---

## Roadmap

- **Step 2 — historical scenarios.** Pull pre- and post-event debris counts from
  the NASA Orbital Debris Quarterly News for the Iridium–Cosmos (2009) and
  Fengyun-1C (2007) events; unskip T5.2 and T5.3; target 233 passed, 0 skipped.
- **Module 2 — scenario simulator.** Configurable launch-rate trajectories,
  deorbit policies, and constellation-deployment scenarios; per-shell forward
  integration to 2050; scenario-comparison plots and CSV outputs.
- **Module 3 — dashboard.** Interactive bifurcation diagram with live current-state
  marker, traffic-light banner, and the three early-warning indicator curves.
  Target: runs in seconds on a laptop for the **1 June 2026** demonstration.
- **Phase 2 — pySSEM calibration.** Replace literature parameters with data-driven
  `(β, γ, δ_S, δ_D)` extracted from MIT ARCLab's MOCAT-pySSEM calibrated runs.
