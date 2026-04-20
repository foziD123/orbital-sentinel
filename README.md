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
2. Solves for every fixed point analytically and tracks them smoothly across
   the launch rate `L` via a warm-started continuation sweep.
3. Computes the Jacobian spectrum `(α, ω)` along each branch and checks for
   **Hopf** and **saddle-node (fold)** bifurcations explicitly.
4. Integrates the full nonlinear trajectories at sub-critical, critical, and
   super-critical launch rates to verify the predicted tipping behaviour.
5. Produces presentation-ready bifurcation diagrams with trajectory overlays.

```
S_dot = L − δ_S · S − β · S · D
D_dot = β · S · D + γ · D² − δ_D · D
```

`γ · D²` is the Kessler term — once `D` is large enough, debris-on-debris
cascade dominates atmospheric drag and the population runs away regardless
of `S`.

---

## Key scientific finding (Phase-1, April 2026)

With literature-calibrated parameters, the 2-D model does **not** host a Hopf
bifurcation on any branch of any of the three default shells. The Kessler
tipping point instead manifests as a **saddle-node (fold) bifurcation**: the
stable lower branch and the unstable upper branch of Case-2 coexistence
equilibria collide and annihilate at a critical launch rate `L_fold`, after
which no coexistence equilibrium exists and `D(t)` runs away.

The lower branch does enter a stable-spiral regime (complex eigenvalues with
α < 0), but α never crosses zero — the equilibrium disappears via the fold
first. A γ-sensitivity sweep on Shell B (1× to 50× the literature value) did
not change this. The preference for a fold over a Hopf is therefore a
**structural feature of the 2-D model**, not a numerical accident.

**Confirmed fold launch rates:**

| Shell   | Altitude  | `L_fold` [objects/yr] | `(S_fold, D_fold)`       |
|---------|-----------|-----------------------|--------------------------|
| Shell A | 600 km    | ≈ 25 100              | (5.01 × 10³, 4.99 × 10⁵) |
| Shell B | 800 km    | ≈ 670                 | (668, 6.65 × 10⁴)        |
| Shell C | 1000 km   | ≈ 31.5                | (251, 1.24 × 10⁴)        |

The three qualitative trajectory regimes are validated for every shell:
below the fold `D(t)` relaxes onto the lower branch; at the fold it hovers
near the merged marginal fixed point; above the fold it runs away. Shell B's
bifurcation diagram with trajectory overlays lives at
`reports/shell_B_bifurcation.png`.

Further discussion and the fold-vs-Hopf argument is in
[`CLAUDE.md`](CLAUDE.md) under *"What the engine has actually found"*.

---

## Repository layout

```
orbital-sentinel/
├── README.md                  ← this file
├── CLAUDE.md                  ← project context + scientific findings
├── TASKS.md                   ← full technical task breakdown (Module 1)
├── TODO.md                    ← current task list and status
├── VALIDATION.md              ← tests and acceptance criteria
├── bifurcation_engine/
│   ├── src/
│   │   ├── shell_config.py    ← altitude-shell definitions and parameters
│   │   ├── model.py           ← ODE system: s_dot, d_dot, ode_system
│   │   ├── fixed_points.py    ← closed-form and continuation solvers
│   │   ├── eigenvalues.py     ← Jacobian + (α, ω) tracker
│   │   ├── hopf_detector.py   ← Hopf + saddle-node fold detectors
│   │   ├── integrator.py      ← full nonlinear RK45 trajectories
│   │   └── early_warning.py   ← critical-slowing-down indicators (WIP)
│   ├── tests/                 ← 113 passed, 2 skipped as of post-Task-6 sync
│   ├── notebooks/
│   │   └── engine_demo.ipynb
│   └── requirements.txt
├── data/parameters/
│   └── shell_defaults.json    ← default parameter sets per altitude band
├── scripts/
│   └── plot_shell_B_bifurcation.py
└── reports/
    ├── shell_B_bifurcation.png
    └── task4_5_summary.md
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

Dependencies (pinned in `bifurcation_engine/requirements.txt`):

- `numpy ≥ 1.24`, `scipy ≥ 1.10`, `matplotlib ≥ 3.7`
- `pytest ≥ 7.4`, `pytest-cov ≥ 4.1`
- `dataclasses-json ≥ 0.6`

---

## Quick start

### Run the test suite

```bash
export PYTHONPATH="$(pwd)"
pytest bifurcation_engine/tests/ -v
```

Expected result: **113 passed, 2 skipped**. The two skipped tests cover the
2009 Iridium–Cosmos and 2007 Fengyun-1C historical scenarios plus the Task-7
early-warning module, all tracked in [`TODO.md`](TODO.md).

### Detect the fold for a single shell

```python
from bifurcation_engine.src.shell_config import default_shells
from bifurcation_engine.src.hopf_detector import detect_fold
import numpy as np

shells = default_shells()
shell_B = shells["Shell_B_800km"]

fold = detect_fold(shell_B, L_values=np.linspace(1.0, 2000.0, 400))
print(fold.description)
# → Shell_B_800km: saddle-node fold at L ≈ 670.10 objects/yr,
#   merged coexistence equilibrium (S*, D*) ≈ (6.68e+02, 6.65e+04).
```

### Integrate a trajectory past the fold

```python
from bifurcation_engine.src.integrator import integrate_trajectory
from dataclasses import replace

params_above_fold = replace(shell_B, L=1.5 * fold.L_fold)
traj = integrate_trajectory(
    S0=shell_B.L / shell_B.delta_S,
    D0=1.0,
    params=params_above_fold,
)
print(f"D(t_end) = {traj['D'][-1]:.2e}, terminated_early = {traj['terminated_early']}")
# → Runaway: terminated early at the runaway_ceiling_D.
```

### Regenerate the Shell-B bifurcation diagram

```bash
export MPLCONFIGDIR="$(pwd)/.mplcache" PYTHONPATH="$(pwd)"
.venv/bin/python scripts/plot_shell_B_bifurcation.py
# → writes reports/shell_B_bifurcation.png
```

---

## Status

**Phase 1 — bifurcation engine, no live data.**

Feature-complete through Task 6 (integrator). Tasks 1–6 plus the saddle-node
fold detector (`detect_fold` in `hopf_detector.py`) are merged and green.

| Task                                   | Status       |
|----------------------------------------|--------------|
| 1. `shell_config.py`                   | done         |
| 2. `model.py`                          | done         |
| 3. `fixed_points.py`                   | done         |
| 4. `eigenvalues.py`                    | done         |
| 5. `hopf_detector.py` + `detect_fold`  | done         |
| 6. `integrator.py`                     | done         |
| 7. `early_warning.py`                  | next up      |
| T5.2/T5.3 historical-scenario tests    | next up      |
| Bifurcation diagrams for Shells A & C  | next up      |
| Phase 2 — MOCAT-pySSEM calibration     | scheduled    |
| Phase 2 — Space-Track live ingestion   | scheduled    |

See [`TODO.md`](TODO.md) for the full task list and
[`VALIDATION.md`](VALIDATION.md) for the acceptance criteria.

---

## Roadmap beyond Phase 1

- **Phase 2 — parameter calibration.** Integrate MIT ARCLab's
  **MOCAT-pySSEM** to extract effective `(β, γ, δ_S, δ_D)` per shell from
  calibrated runs, replacing the current literature values with data-driven
  ones. The quadratic `γ · D²` term is a mean-field simplification of
  pySSEM's NASA Standard Breakup Model, so an effective γ will need to be
  fit empirically.
- **Phase 3 — live dashboard.** Connect the **Space-Track API** (OMM format
  — legacy TLE catalog numbers overflow mid-2026) to feed current per-shell
  populations as initial conditions, then compute "where are we now
  relative to `L_fold`" for each shell. This powers the early-warning
  traffic-light dashboard keyed to fractions of `L_fold`.

---

## Scientific context and validators

The framing and findings in this repo are intended to be validated against
external subject-matter experts before publication or presentation:

- **Giovanni Perosa** — European XFEL, HOPFEL methodology owner. Confirms
  the bifurcation framing is scientifically sound.
- **Prof. Josep Joaquim Masdemont** — UPC/IEEC. Validates the orbital
  mechanics and per-shell parameter assumptions.
- **Dr. Tim Flohrer** — Head of the ESA Space Debris Office. Validates
  debris-population parameters and real-world relevance.
- **Richard Linares** — MIT ARCLab. Reviews the pySSEM integration plan.

The final demonstration target is **1 June 2026**, when the full multi-shell
bifurcation diagram and the `L_fold`-keyed early-warning dashboard must run
in seconds on a laptop for an interactive stakeholder demo.

---

## Licence

Not yet licensed — course project. A licence decision will be made jointly
with ESADE, UPC, IED, and the HOPFEL methodology owner before any external
release.
