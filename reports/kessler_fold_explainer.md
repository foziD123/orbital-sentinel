# Orbital Sentinel: From Hopf Search to Kessler Fold

**Phase 1 bifurcation-engine explainer**

**Project:** Orbital Sentinel, TeSI 2026  
**Purpose:** Explain what was tested, why a Hopf bifurcation was not found, and why the saddle-node fold is now the operational Kessler tipping point.

---

## Executive Summary

Orbital Sentinel began with a Hopf-inspired critical-transition question: can increasing launch pressure push a low-Earth-orbit shell from a stable operating state into oscillatory instability? The answer from the Phase 1 model family is no. The engine repeatedly found complex eigenvalues, meaning oscillatory recovery can exist, but it did not find a Hopf bifurcation: the real part of the complex pair never crossed zero while the stable branch still existed.

Instead, the mathematically dominant transition is a saddle-node fold. As the launch rate rises, the stable low-debris equilibrium and an unstable high-debris threshold move toward each other. At the fold launch rate, `L_fold`, those equilibria collide and disappear. Above that threshold, the model no longer has a sustainable coexistence equilibrium for active satellites and debris. That disappearance is the Kessler tipping point in this model class.

This is not a failed result. It is the central scientific finding: bifurcation theory still identifies a critical threshold, but the threshold is a fold rather than a Hopf bifurcation.

---

## The Core Question

The project models each altitude shell as a dynamical system with launch rate as the main control parameter. The policy question is:

> How many objects can be launched into a shell per year before the shell loses its sustainable equilibrium?

The original Hopf hypothesis asked whether the stable equilibrium might lose stability through oscillations. In a Hopf bifurcation, a stable fixed point becomes unstable while a rotating mode appears. In orbital-debris language, that would mean satellite and debris populations begin to cycle rather than simply relax to a steady state.

The fold hypothesis is different. In a saddle-node fold, the safe equilibrium does not become cyclic. It vanishes. That is a stronger form of tipping point because there is no longer a nearby stable operating state to return to.

---

## Model Family Tested

Three versions of the debris model were implemented and tested.

### 1. Two-population source-sink model

The production model tracks:

- `S(t)`: active satellites and intact objects in the shell.
- `D(t)`: trackable debris fragments.

The model is:

```text
dS/dt = L - delta_S*S - beta*S*D
dD/dt = beta*S*D + gamma*D^2 - delta_D*D
```

The `gamma*D^2` term is the Kessler cascade term. It represents debris-debris fragmentation and becomes dominant at high debris density.

### 2. Three-species model

The first extension adds a derelict population:

- `S(t)`: active satellites.
- `R(t)`: derelict satellites and intact rocket bodies.
- `D(t)`: debris fragments.

This was important because a Hopf bifurcation is more plausible in three dimensions than in the two-population model. The derelict compartment introduces an additional feedback pathway:

```text
S -> R -> D -> S/R
```

That pathway can produce complex eigenvalues and spiral-like recovery.

### 3. Split-decay three-species refinement

The corrected three-species model separates controlled disposal from failure into derelicts:

- `kappa_S*S`: controlled disposal, leaves the orbital shell.
- `rho_S*S`: failed or retired spacecraft that become derelicts.

It also adds fragment-yield multipliers, so derelict collisions can produce more debris than smaller debris-object collisions. This was the most Hopf-friendly version of the Phase 1 model family because it added both a delay-like derelict state and tunable debris-production channels.

---

## How Hopf Was Tested

For each model, the engine computed equilibrium branches as launch rate `L` was varied. At every equilibrium, it built the Jacobian matrix and tracked the eigenvalues.

A Hopf bifurcation requires three conditions:

1. A complex conjugate eigenvalue pair exists.
2. The real part of that pair crosses zero.
3. The crossing occurs with nonzero speed while the equilibrium still exists.

The tests therefore did not merely ask whether eigenvalues were complex. They asked whether the complex pair actually crossed from stable to unstable on a valid equilibrium branch.

The detector reported separate non-Hopf outcomes:

- `no_complex_eigenvalues`: the spectrum was real.
- `complex_no_crossing`: a complex pair existed, but its real part stayed negative.
- `unstable_throughout`: the branch was already unstable.
- `grazing`: a degenerate touch rather than a genuine crossing.
- `hopf_detected`: all Hopf conditions satisfied.

No tested scenario produced `hopf_detected`.

---

## What Was Tested

| Test stage | Scope | Result |
|---|---:|---|
| 2D default shells | Shells A, B, C across analytical branches | No Hopf; lower branch either real-stable or stable spiral |
| 2D gamma sensitivity | Shell B, `gamma` swept from 1x to 50x | No Hopf; fold remains dominant |
| 3-species continuation | Shells A, B, C, all tracked branches, 200 launch samples per shell | No Hopf; complex pairs appear but do not cross |
| Split-decay sweep | Shells B and C, 20 x 20 x 3 grid | 0 Hopf bifurcations in 2,400 parameter combinations |

The split-decay sweep was the strongest stress test. It scanned:

- `rho_fraction` from 0.05 to 0.95.
- `gamma_multiplier` from 1.0 to 50.0.
- Three fragment-yield triplets: baseline, derelict x2, and derelict x3.

Shell B produced complex eigenvalues in most scanned cells, so the model did have the rotational structure needed for a possible Hopf. However, the complex pair remained stable until the equilibrium branch ended at the fold.

---

## Key Numerical Findings

For the two-population production model, the detected fold launch rates are:

| Shell | Altitude | `L_fold` |
|---|---:|---:|
| Shell A | 600 km | about 25,100 objects/year |
| Shell B | 800 km | about 670 objects/year |
| Shell C | 1,000 km | about 31.5 objects/year |

These values are model outputs, not direct measurements of the current real-world launch rate. They should be read as threshold properties of the calibrated shell parameters.

The physical interpretation is clear:

- Shell A has a high threshold because atmospheric drag is strong enough to remove debris relatively quickly.
- Shell B is much more fragile because drag is weaker and the historical collision environment is more congested.
- Shell C is the most vulnerable because debris remains for decades to centuries, so even low sustained launch pressure can push the system toward the fold.

---

## Why Hopf Was Not Found

The Hopf search failed for a specific mathematical reason. The model often develops complex eigenvalues, so the system can recover in a damped oscillatory way. But the damping does not vanish before the lower equilibrium branch terminates.

In other words:

```text
complex eigenvalues appear
      but
real part stays negative
      until
the stable branch ends at the fold
```

The fold is detected by the disappearance of the coexistence equilibria. Mathematically, a saddle-node fold corresponds to a zero eigenvalue of the Jacobian at the collision point between branches. In the 2D analytical model, the same event is visible through the vanishing discriminant of the Case-2 fixed-point quadratic. The branch slope becomes singular as the fold is approached.

That is why the result is fold-before-Hopf, not Hopf-before-fold.

---

## What the Saddle-Node Fold Means

Below `L_fold`, the model has two coexistence equilibria:

- A lower stable branch: the sustainable operating state.
- An upper unstable branch: the threshold separating recovery from runaway.

As launch rate increases, these branches approach each other. At `L = L_fold`, they collide. Beyond that point, the sustainable equilibrium is gone.

This is the mathematical version of the Kessler point of no return:

- Below the fold, perturbations can decay back to the safe branch.
- Near the fold, recovery becomes very slow and early-warning signals grow.
- Above the fold, the model predicts runaway debris growth unless active removal or other interventions change the state of the shell.

The fold is therefore more policy-relevant than a Hopf result would have been. A Hopf threshold would mean the system becomes oscillatory and unstable, but a stable state might return after reducing launch pressure. A fold means the stable state has disappeared. Simply lowering future launch rate may not be enough; the debris state itself must be changed.

---

## Early-Warning Interpretation

The early-warning indicators should be keyed to `L_fold`, not to a Hopf critical value.

Recommended interpretation:

- Green: `L < 0.80*L_fold`.
- Amber: `0.80*L_fold <= L < 0.95*L_fold`.
- Red: `L >= 0.95*L_fold`.

The quantitative indicators are the standard critical-slowing-down signals:

- Recovery time increases as the leading eigenvalue approaches zero.
- Variance in debris trajectories grows.
- Lag-1 autocorrelation approaches one.

These indicators are valid for saddle-node folds as well as Hopf bifurcations. The warning channel remains useful even though the underlying bifurcation is a fold.

---

## Final Finding

Orbital Sentinel tested the Hopf hypothesis seriously across increasing model complexity:

1. A two-population source-sink model.
2. A three-species model with derelicts.
3. A split-decay, yield-weighted three-species refinement.

Across these scenarios, no Hopf bifurcation was found. The robust finding is that the Kessler tipping point appears as a saddle-node fold: the sustainable equilibrium branch collides with an unstable threshold branch and disappears.

This should be the central Phase 1 result:

> The critical launch threshold for each shell is `L_fold`, the saddle-node fold rate, not a Hopf critical rate.

Future work can still revisit Hopf behavior when adding inter-shell coupling, delayed policy response, active debris removal feedback, or the NASA Standard Breakup Model through MOCAT-pySSEM. Under the current Phase 1 source-sink model class, however, the saddle-node fold is the correct operational tipping point.
