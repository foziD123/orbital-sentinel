# The Kessler Tipping Point as a Saddle-Node Fold

**A non-specialist scientific summary of the Orbital Sentinel result.**

Phase 1, Bifurcation Engine — Module 1.
Project: Orbital Sentinel (TeSI 2026, ESADE / UPC / IED, Tech2X /
Fusion Point Academy).
Methodology: HOPFEL — Hopf-bifurcation-theoretic detection of critical
transitions in dynamical systems, originally developed at European
XFEL (Giovanni Perosa) for Free Electron Lasers, transferred here to
orbital debris dynamics.

---

## What the model does

Each altitude shell of Low Earth Orbit is treated as an independent
two-population system. The two populations are:

* `S(t)` — active satellites and intact rocket bodies in the shell,
* `D(t)` — trackable debris fragments in the shell.

They evolve under three competing processes:

* **Launches**, at a constant rate `L`. This is the parameter we want
  to control. `L` is measured in *objects placed into that shell per
  year*. It is the one quantity policymakers can actually move:
  international agreements, licensing regimes, and operator self-
  restraint all set `L`.
* **Drag and disposal**, which slowly remove satellites and debris from
  the shell. Drag dominates at low altitudes; controlled deorbit
  dominates at moderate altitudes. The model captures this with two
  decay rates: one for `S`, one for `D`.
* **Collisions**, which destroy active satellites *and* simultaneously
  produce more debris. Two collision channels matter: satellite-debris
  and debris-debris. The debris-debris term is the Kessler self-
  cascade — it grows quadratically in `D`. Once `D` is high enough,
  this term dominates everything else and the debris population runs
  away regardless of what is being launched, deorbited, or removed.

The launch rate `L` enters the equations linearly, but it is the only
control knob that distinguishes one operating point from another. As
`L` is raised from zero, the equilibrium debris population in each
shell rises smoothly along a stable lower branch. This is the regime
in which orbital operations are sustainable — perturbations decay back
to the equilibrium, and the shell remains usable. The question Phase 1
of the project answers is: at what `L` does this stable equilibrium
disappear, and what happens when it does?

The answer turns out not to be a Hopf bifurcation, as the original
HOPFEL methodology might have suggested by analogy with FELs. It is a
**saddle-node fold**. The rest of this document explains what that
means, what the numbers are, and why the result is robust.

---

## What a saddle-node fold is

For each shell, the model has *two* coexistence equilibria when the
launch rate is below a critical value `L_fold`:

* a **lower branch**, with relatively few debris fragments, on which
  perturbations relax back exponentially. This is the "everything is
  fine" branch. It is what we observe today on Shell B and Shell C.
* an **upper branch**, also with debris in equilibrium with launches
  and removal, but unstable. Any perturbation pushes the system off
  this branch, downward toward the lower branch or upward toward
  runaway. Physically, the upper branch is the threshold above which
  collisional fragmentation outpaces drag.

As `L` is increased, the lower branch's debris equilibrium rises and
the upper branch's drops. They move toward each other. At
`L = L_fold`, the two equilibria collide, merge into a single
marginally-stable point at a finite debris value, and **vanish**. For
`L > L_fold` neither coexistence equilibrium exists. The clean-orbit
equilibrium `D = 0` is still a mathematical solution of the equations
past the fold, but it is not physically reachable from an
already-contaminated shell — there is no way to remove the debris
that is already in orbit just by changing `L` — and it is anyway
unstable to any perturbation that introduces debris into the shell.
In practice, therefore, the debris population enters a runaway regime
governed by the Kessler self-cascade and the shell becomes unusable.

This collide-and-disappear pattern is, in the language of dynamical
systems, a saddle-node bifurcation — also called a fold. It is
codimension-one, meaning a single parameter change (`L`) causes it,
and it is structurally stable, meaning small modelling refinements do
not remove it.

The Hopf bifurcation hypothesised by the HOPFEL methodology when
applied to Free Electron Lasers does not appear in this model class.
The mathematical reason is given two sections down. The result is not
a failure of HOPFEL but a refinement: bifurcation theory does identify
the Kessler tipping point correctly. That point happens to be a fold
rather than a Hopf.

---

## The numbers, by shell

The bifurcation engine has located the fold with full numerical
precision on three reference shells, and has cross-checked each result
against a closed-form analytical formula derived from the model's
Case-2 quadratic discriminant. The results are:

| Shell | Altitude | `L_fold` (objects launched into the shell per year) |
|-------|----------|-----------------------------------------------------|
| Shell A | 600 km | ≈ 25,100 |
| Shell B | 800 km | ≈ 670 |
| Shell C | 1,000 km | ≈ 31.5 |

To put those numbers in context:

* **Shell A (600 km).** `L_fold` of about 25,100 objects per year is
  large because atmospheric drag at 600 km is strong: orbits decay on
  timescales of a few years and debris is naturally cleaned out.
  Shell A is where most of the current Starlink constellation sits.
  At this altitude the operating margin is wide; we are not the
  binding constraint here.
* **Shell B (800 km).** `L_fold` of about 670 objects per year. This
  is the historically most congested band — the 2009 Iridium-Cosmos
  collision happened at 789 km and the 2007 Chinese ASAT test debris
  spread through this shell. Drag is weaker here, so the same number
  of launches produces a much higher steady-state debris population
  than at 600 km. Sustained launch rates into this shell of a few
  hundred objects per year are within the operating margin; rates
  approaching a thousand are not.
* **Shell C (1,000 km).** `L_fold` of about 31.5 objects per year.
  This shell is critically vulnerable. Drag at 1,000 km is too weak
  to remove debris on operationally relevant timescales (decades to
  centuries). The Iridium and original OneWeb constellations operate
  here. The fold sits at a launch rate that is below current
  cumulative annual placements into the band when historical
  constellations are summed, which is the formal expression of the
  policy concern that this altitude is already past or near its
  carrying capacity.

These `L_fold` values are properties of the parameter set, not
measurements of where the system is today. Whether a given shell is
near, at, or past its fold is a separate question — answered by the
early-warning indicators described below.

---

## Why this is the right tipping point

The lower branch loses existence at the fold because the Jacobian of
the system develops a zero eigenvalue at `L = L_fold` — equivalently,
the Jacobian's determinant goes to zero — and the two coexistence
branches collide and annihilate. A complex eigenvalue pair *does*
appear on the lower branch in many parameter regimes, giving the
system a stable spiral recovery structure rather than a simple
exponential one; but the real part of that complex pair remains
strictly negative throughout the spiral region, until the branch
terminates at the fold. There is therefore no window in which the
real part crosses zero on a still-existing stable branch. The model
reaches a saddle-node fold before any Hopf crossing can occur.

The natural follow-up question — why the real part of the complex
pair never crosses zero on the still-existing branch — is answered by
the *trace inequality* derived analytically in `CLAUDE.md`. The
Jacobian's trace is the sum of its diagonal entries and also the sum
of the eigenvalue real parts; as long as the trace stays negative on
the lower branch, the real parts cannot all be positive, so the
spiral cannot lose stability. Computing the trace symbolically reveals
four sink-like contributions (drag and disposal, two decay channels,
the active-derelict collision sink) plus one term that grows with the
equilibrium debris population — the Kessler self-cascade. As `L` is
pushed toward the fold, the equilibrium debris value on the lower
branch rises steeply: the slope `dD*/dL` of the equilibrium curve
develops a square-root singularity at `L_fold` even though the debris
value itself remains finite there. The Kessler self-cascade term in
the trace grows correspondingly. By the time the Kessler term would
otherwise flip the trace positive, the lower branch has already
terminated at the fold. The trace inequality therefore explains *why
no Hopf appears* — it is not the mechanism of the fold itself. The
fold mechanism is the Jacobian's determinant going to zero; the trace
inequality is the no-Hopf side of the same story.

Because the fold mechanism only requires the lower-branch debris
value to grow monotonically with `L` and the Kessler self-cascade to
be quadratic in `D`, and because the trace inequality only requires
the self-cascade to dominate as the lower branch approaches its
terminus, the conclusion is structural. It does not depend on the
particular numerical values of `β`, `γ`, the decay rates, or any of
the other parameters in the model. This is **not** a numerical
accident.

---

## Why the result is robust

The project tested three independently implemented model variants and
ran a focused parameter sweep at the level of greatest concern:

1. **The 2-D `(S, D)` source-sink model** — the production model.
   Tested on three reference shells with a 50-fold sensitivity sweep
   on the Kessler self-cascade coefficient `γ`. Result: every shell
   ends in a saddle-node fold; no Hopf is ever observed.
2. **The 3-species `(S, R, D)` extension** — adds derelict satellites
   as a separate population, with three collision channels (active-
   debris, active-derelict, derelict-debris) and an asymmetric
   active-derelict reaction. Same three reference shells, all-branch
   continuation, 200 launch-rate samples per shell. Result: same
   outcome on every branch on every shell.
3. **The split-decay refinement** — splits the satellite decay rate
   into a controlled-disposal channel (the satellite leaves orbit
   altogether) and a failure-into-derelict channel (the satellite
   stays in orbit as junk), adds three fragment-yield multipliers
   (derelict collisions can produce more fragments than active-
   satellite collisions), and corrects the active-derelict term to be
   symmetric. A 20×20×3 grid in (failure share, Kessler multiplier,
   yield triplet) was scanned on Shells B and C — the two shells most
   likely to host a Hopf — for a total of **2,400 parameter
   combinations**.

The headline number from the split-decay sweep is **0**: zero Hopf
bifurcations across all 2,400 combinations. On Shell B 89% of cells
even produced complex eigenvalues on the lower branch — meaning the
spiral structure that *could* host a Hopf was present — but in every
single one of those cells the spiral's rotation rate stayed bounded
away from an unstable crossing, because the trace mechanism described
above destroyed the equilibrium first. The fold-over-Hopf preference
is the same across all three model variants, exactly as the trace
inequality predicts.

This is a strong statement about the science. The fold is not
contingent on any particular parameterisation. It survives every
modelling refinement we have tried, and the analytical argument
explains why.

---

## Reading the early warning

The bifurcation engine emits four early-warning indicators, all keyed
to `L_fold`. They are designed to be readable both by automated
dashboards and by human policy teams.

The first three are quantitative time-series indicators of *critical
slowing down* — the universal signature that any codimension-one
bifurcation casts ahead of itself. As the launch rate approaches the
fold:

* **Recovery time** of the debris population after a small
  perturbation grows without bound. This is `1 / |α|`, where `α` is
  the leading eigenvalue real part at the lower-branch equilibrium.
  Far from the fold, recovery is fast (years). Close to the fold, it
  diverges (decades, centuries). The indicator clips at a configurable
  display ceiling so dashboards remain readable.
* **Variance** of `D(t)` in a sliding window inflates. Even small
  fluctuations are not absorbed back into the equilibrium efficiently
  near the fold, so they accumulate.
* **Lag-1 autocorrelation** of `D(t)` in a sliding window approaches
  one. Near the fold, consecutive observations of `D(t)` are nearly
  indistinguishable because the system is moving slowly through state
  space.

The fourth indicator is the policy-level summary: a green / amber /
red traffic light keyed to the current launch rate as a fraction of
`L_fold`:

* **Green** when `L < 0.80 · L_fold`. The shell has wide operating
  margin. Routine monitoring is appropriate; there is no urgency.
* **Amber** when `0.80 · L_fold ≤ L < 0.95 · L_fold`. The shell is in
  the critical-slowing-down band where the time-series indicators
  begin to inflate visibly. Recovery times have lengthened
  noticeably; new constellations should be evaluated against the
  margin remaining; debris-removal investments deliver outsized
  returns.
* **Red** when `L ≥ 0.95 · L_fold`. The shell is on or past the fold.
  The traffic light is keyed to `L_fold` rather than the lower
  amber-red threshold so that dashboards distinguish "operationally
  uncomfortable" (amber) from "structurally past the tipping point"
  (red).

The Hopf channel of the indicator API is reserved for future model
extensions (inter-shell coupling, NASA Standard Breakup Model
integration via MOCAT-pySSEM). Under the current model class it
always reports `not_applicable`, because no Hopf locus exists.

---

## Implications

The most important implication of the saddle-node fold is what it
*does not* admit. A Hopf bifurcation can be approached and then
backed away from: a launch-rate cut applied just past the Hopf
restores the stable equilibrium. A saddle-node fold cannot. Past
`L_fold` the lower-branch equilibrium **does not exist any more**, and
no operational change to the launch rate can recreate it on
human-relevant timescales. The shell's debris population enters a
runaway regime governed by the Kessler self-cascade; the stable
equilibrium is gone, and reducing `L` below `L_fold` after the fact
does not restore it. Recovery is possible only by *active debris
removal*, on timescales set by the very slow drag clock of the shell
(decades at 800 km, centuries at 1,000 km). This asymmetry — easy to
cross, hard or impossible to uncross — is the formal mathematical
expression of why the Kessler tipping point is a tipping point at all.
Operating in green territory, with margin, is therefore
qualitatively different from operating in amber and recovering. The
former has options; the latter is racing the clock.

---

## Reproducibility and external validation

All numerical results in this document are reproducible from the
public Orbital Sentinel codebase: the bifurcation engine is implemented
in Python (NumPy, SciPy, matplotlib, pytest), and the complete pipeline
on three shells runs in seconds on a laptop. Test coverage stands at
231 passing tests with one skipped historical-scenarios module
(reserved for the 2009 Iridium-Cosmos and 2007 Chinese ASAT
reproductions, scheduled before the June 2026 demonstration). The
saddle-node fold values quoted in this document are within
floating-point tolerance of the closed-form analytical solution of the
Case-2 discriminant, so the numbers are not a numerical artefact.

External validators consulted on the methodology and the orbital
mechanics are listed in the project's `CLAUDE.md`: Giovanni Perosa
(European XFEL, HOPFEL methodology owner), Prof. Josep Joaquim
Masdemont (UPC / IEEC, astrodynamics), Dr. Tim Flohrer (Head of the
ESA Space Debris Office), and Richard Linares (MIT ARCLab,
MOCAT-pySSEM). Their feedback informs Phase 2 of the project, in
which parameters will be calibrated against the MOCAT-pySSEM
breakup model and current Space-Track catalogue data.

---

*Document version: April 2026, post Task 7. Companion files:
`reports/3species_pipeline_summary.md`,
`reports/split_decay_sweep_summary.md`, `reports/task4_5_summary.md`,
and `reports/shell_B_bifurcation.png`. Full mathematical detail and
trace-inequality derivation: `CLAUDE.md`.*
