# TASKS — Module 1: Bifurcation Engine
## Full technical breakdown with implementation notes

---

## TASK 1 — Shell configuration (`src/shell_config.py`)

**Goal:** Define the data structure for a single orbital shell and its parameters.

**Deliverable:** A `ShellConfig` dataclass and a loader for `shell_defaults.json`.

```python
@dataclass
class ShellConfig:
    shell_name: str          # e.g. "Shell_B_800km"
    altitude_km: float       # representative altitude (midpoint of band)
    L: float                 # launch rate [objects/year] — bifurcation parameter
    delta_S: float           # satellite decay rate [1/year]
    delta_D: float           # debris decay rate [1/year]; must be > delta_S
    beta: float              # collision cross-section [1/(objects*year)]
    gamma: float             # Kessler cascade coefficient [1/(objects*year)]
```

**Literature parameter guidance (starting values only — to be calibrated):**

| Shell | Altitude | delta_S | delta_D | Notes |
|-------|----------|---------|---------|-------|
| A | 550–650 km | ~0.02/yr | ~0.10/yr | Starlink belt; faster drag |
| B | 750–850 km | ~0.005/yr | ~0.02/yr | Most congested historically |
| C | 950–1050 km | ~0.001/yr | ~0.005/yr | Slow drag; highest cascade risk |

For beta and gamma: start with order-of-magnitude estimates from Kessler & Cour-Palais (1978)
and MOCAT paper parameters. Typical values: beta ~ 1e-5, gamma ~ 1e-7.

**Validation:** `delta_D > delta_S` must always hold. Raise `ValueError` if not.

---

## TASK 2 — ODE system (`src/model.py`)

**Goal:** Implement the core differential equations.

```
S_dot = L - delta_S * S - beta * S * D
D_dot = beta * S * D + gamma * D^2 - delta_D * D
```

**Functions to implement:**

```python
def ode_system(t: float, y: np.ndarray, params: ShellConfig) -> np.ndarray:
    """
    Right-hand side of the ODE for scipy.integrate.solve_ivp.
    y = [S, D]
    Returns [S_dot, D_dot]
    """

def s_dot(S: float, D: float, params: ShellConfig) -> float:
    """Satellite population rate of change."""

def d_dot(S: float, D: float, params: ShellConfig) -> float:
    """Debris population rate of change."""
```

**Edge cases to handle:**
- D must never go negative in integration (clip or use event detection)
- S must never go negative
- When D=0: D_dot = 0 (clean orbit is an absorbing state if S also = 0)

---

## TASK 3 — Fixed point solver (`src/fixed_points.py`)

**Goal:** Find equilibria (S*, D*) where S_dot = D_dot = 0, for a given L.

**Analytical fixed points for reference:**

Case 1 (D=0):
```
S* = L / delta_S
D* = 0
```

Case 2 (D != 0): D* satisfies quadratic
```
beta*gamma*(D*)^2 + (delta_S*gamma - beta*delta_D)*D* + (beta*L - delta_S*delta_D) = 0
S* = (delta_D - gamma*D*) / beta
```

**Functions to implement:**

```python
def clean_orbit_fixed_point(params: ShellConfig) -> tuple[float, float]:
    """Returns (S*, D*) for Case 1. Always exists."""

def coexistence_fixed_points(params: ShellConfig) -> list[tuple[float, float]]:
    """
    Returns list of (S*, D*) for Case 2 (can be 0, 1, or 2 solutions).
    Uses quadratic formula. Filters out physically invalid (negative S or D) solutions.
    """

def find_all_fixed_points(params: ShellConfig) -> list[tuple[float, float]]:
    """Returns all physically valid fixed points for current params.L."""

def continuation_sweep(
    params: ShellConfig,
    L_values: np.ndarray
) -> dict[str, np.ndarray]:
    """
    Sweeps L across L_values using Newton continuation.
    At each L step, uses previous solution as initial guess for fsolve.
    Returns dict with keys: 'L', 'S_star', 'D_star', 'branch' (case 1 or 2).
    
    Implementation note: run two separate continuations — one for Case 1 branch
    (always analytical), one for Case 2 branch (use fsolve with warm start).
    """
```

**Numerical notes:**
- Use `scipy.optimize.fsolve` for Case 2 numerical refinement
- Warm-start: solution at L[i] is initial guess for L[i+1]
- Step size for L: start with 50 steps across [0, L_max]; refine near L_c
- If fsolve fails to converge, mark that L value as NaN and continue

---

## TASK 4 — Eigenvalue tracking (`src/eigenvalues.py`)

**Goal:** Compute Jacobian and track eigenvalues along the continuation path.

**Jacobian at (S*, D*):**
```
J = [[-delta_S - beta*D*,   -beta*S*              ],
     [ beta*D*,              beta*S* + 2*gamma*D* - delta_D]]
```

**Functions to implement:**

```python
def jacobian(S_star: float, D_star: float, params: ShellConfig) -> np.ndarray:
    """Returns 2x2 Jacobian matrix at fixed point (S*, D*)."""

def eigenvalue_pair(S_star: float, D_star: float, params: ShellConfig) -> tuple[float, float]:
    """
    Returns (alpha, omega) where:
    - alpha = real part of eigenvalues (both have same real part for complex pair)
    - omega = |imaginary part| (0 if eigenvalues are real)
    Uses numpy.linalg.eigvals.
    """

def track_eigenvalues(
    continuation_result: dict,
    params: ShellConfig
) -> dict[str, np.ndarray]:
    """
    Computes (alpha, omega) at each (S*, D*) along the continuation path.
    Returns dict with keys: 'L', 'alpha', 'omega', 'is_complex'.
    """
```

**Physical interpretation of eigenvalue signs:**
- alpha < 0, omega = 0: stable node (monotone return to equilibrium)
- alpha < 0, omega != 0: stable spiral (oscillatory return — Hopf precursor region)
- alpha = 0, omega != 0: Hopf bifurcation point
- alpha > 0, omega != 0: unstable spiral (limit cycle may exist)
- alpha > 0, omega = 0: unstable node

---

## TASK 5 — Hopf detector (`src/hopf_detector.py`)

**Goal:** Determine whether and where a genuine Hopf bifurcation occurs.

**Output dataclass:**

```python
@dataclass
class HopfResult:
    found: bool
    L_c: float | None            # critical launch rate, None if not found
    outcome: str                 # one of: 'hopf_supercritical', 'hopf_subcritical',
                                 #         'no_complex_eigenvalues', 
                                 #         'complex_no_crossing', 'unstable_throughout'
    description: str             # human-readable explanation
    alpha_at_Lc: float | None    # should be ~0 if found
    omega_at_Lc: float | None    # should be != 0 if found
    dalpha_dL_at_Lc: float | None  # sign confirms genuine crossing
```

**Detection logic:**

```python
def detect_hopf(
    L_array: np.ndarray,
    alpha_array: np.ndarray,
    omega_array: np.ndarray
) -> HopfResult:
    """
    Step 1: Check if any eigenvalues are complex (omega != 0 anywhere).
            If not: return outcome='no_complex_eigenvalues'.
    
    Step 2: Among complex-eigenvalue region, check if alpha crosses zero.
            Use sign change detection: find i where alpha[i] < 0 and alpha[i+1] > 0
            (or vice versa), with omega[i] != 0.
            If no crossing: check if alpha is always negative (stable spiral, safe)
            or always positive (unstable throughout). Return accordingly.
    
    Step 3: If crossing found, interpolate to find L_c precisely.
            Compute d(alpha)/dL at crossing via finite difference.
            If |d(alpha)/dL| < tolerance: warn that crossing may be grazing.
    
    Step 4: Classify supercritical vs subcritical.
            Requires integrating the full nonlinear system at L slightly above L_c
            and checking if a stable limit cycle appears (supercritical) or the
            system diverges (subcritical). This is called from integrator.py.
    """
```

**Important:** All three non-Hopf outcomes are scientifically valid results.
The code must report them clearly, not treat them as errors.

---

## TASK 6 — Trajectory integrator (`src/integrator.py`)

**Goal:** Integrate the full nonlinear ODE forward in time and detect limit cycles.

```python
def integrate_trajectory(
    S0: float,
    D0: float,
    params: ShellConfig,
    t_span: tuple[float, float],
    t_eval: np.ndarray | None = None,
    rtol: float = 1e-6,
    atol: float = 1e-9
) -> dict:
    """
    Integrates the system using scipy.integrate.solve_ivp (method='RK45').
    Returns dict: {'t': array, 'S': array, 'D': array, 'success': bool}
    Enforce S >= 0 and D >= 0 throughout (add non-negativity event or post-clip).
    """

def check_limit_cycle(
    trajectory: dict,
    transient_fraction: float = 0.5
) -> dict:
    """
    After discarding the first transient_fraction of the trajectory,
    checks whether D(t) exhibits sustained oscillation.
    Returns: {'oscillating': bool, 'amplitude': float, 'period_estimate': float}
    Heuristic: if std(D[transient:]) / mean(D[transient:]) > threshold → oscillating.
    """

def sweep_trajectories_above_Lc(
    params: ShellConfig,
    L_c: float,
    n_steps: int = 5
) -> list[dict]:
    """
    Integrates trajectories at L = L_c * [1.01, 1.05, 1.1, 1.2, 1.5].
    Used to confirm supercritical Hopf: limit cycle amplitude should grow as sqrt(L - L_c).
    Returns list of trajectory dicts with L value attached.
    """
```

---

## TASK 7 — Early warning indicators (`src/early_warning.py`)

**Goal:** Compute the three early-warning signals that precede a Hopf bifurcation.

These signals appear as the system approaches L_c from below (alpha → 0):

```python
def critical_slowing_down(
    L_array: np.ndarray,
    alpha_array: np.ndarray
) -> dict:
    """
    As L → L_c, alpha → 0, meaning the system recovers more and more slowly
    from perturbations. The recovery time ~ 1/|alpha| diverges at L_c.
    Returns: {'L': array, 'recovery_time': array}
    recovery_time[i] = 1 / |alpha[i]| (clip at some maximum for display)
    """

def variance_indicator(
    trajectory: dict,
    window: int = 50
) -> dict:
    """
    Rolling variance of D(t) over a sliding window.
    Variance increases as system approaches bifurcation.
    Returns: {'t': array, 'variance_D': array}
    """

def autocorrelation_indicator(
    trajectory: dict,
    lag: int = 1
) -> dict:
    """
    Lag-1 autocorrelation of D(t) in sliding windows.
    Approaches 1.0 as system slows down near bifurcation (critical slowing down).
    Returns: {'t': array, 'ac1_D': array}
    Uses numpy.corrcoef or manual formula.
    """

def early_warning_summary(
    params: ShellConfig,
    L_values: np.ndarray,
    hopf_result: HopfResult
) -> dict:
    """
    Combines all three indicators into a single summary dict for dashboard consumption.
    Returns traffic-light status: 'green' (far from L_c), 'amber' (within 20%),
    'red' (within 5% or past L_c).
    Threshold logic: compute L_fraction = L / L_c. 
    green if L_fraction < 0.8, amber if 0.8–0.95, red if > 0.95.
    """
```

---

## TASK 8 — Default parameter file (`data/parameters/shell_defaults.json`)

Create a JSON file with starting parameters for three shells.
These are order-of-magnitude estimates from literature — to be refined.

```json
{
  "shells": [
    {
      "shell_name": "Shell_A_600km",
      "altitude_km": 600,
      "L_default": 200,
      "L_sweep_min": 0,
      "L_sweep_max": 2000,
      "delta_S": 0.02,
      "delta_D": 0.10,
      "beta": 1e-5,
      "gamma": 1e-7,
      "notes": "Starlink primary belt. Fast drag, delta_D >> delta_S."
    },
    {
      "shell_name": "Shell_B_800km",
      "altitude_km": 800,
      "L_default": 100,
      "L_sweep_min": 0,
      "L_sweep_max": 1000,
      "delta_S": 0.005,
      "delta_D": 0.02,
      "beta": 1.5e-5,
      "gamma": 1.5e-7,
      "notes": "Most historically congested shell. Iridium-Cosmos collision occurred here."
    },
    {
      "shell_name": "Shell_C_1000km",
      "altitude_km": 1000,
      "L_default": 50,
      "L_sweep_min": 0,
      "L_sweep_max": 500,
      "delta_S": 0.001,
      "delta_D": 0.005,
      "beta": 1e-5,
      "gamma": 2e-7,
      "notes": "Slow drag. Highest long-term cascade risk. Some argue already past no-return."
    }
  ]
}
```

---

## TASK 9 — Plots and outputs

All plots must be clean, labelled, and presentable to non-technical stakeholders.

**Required plots:**

1. **Bifurcation diagram** (centrepiece):
   - x-axis: Launch rate L
   - y-axis: Equilibrium debris density D*
   - Solid line = stable branch, dashed = unstable
   - Vertical line at L_c
   - Current real-world L marked (Phase 2)

2. **Eigenvalue track**:
   - x-axis: L
   - Two panels: alpha(L) and omega(L)
   - alpha panel: horizontal zero line, L_c marked

3. **Phase portrait** (S vs D plane):
   - Multiple trajectories at L < L_c and L > L_c
   - Fixed points marked
   - Limit cycle visible when L > L_c (if supercritical)

4. **Time series** (S(t) and D(t)):
   - At L slightly above L_c
   - Shows sustained oscillation confirming limit cycle

5. **Early-warning panel** (3 subplots):
   - Recovery time vs L
   - Variance vs L (or t)
   - Autocorrelation vs L (or t)
   - Traffic light overlay
