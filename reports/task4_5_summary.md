# Task 4 & Task 5 — Implementation and Pipeline Report

## Summary

### Code delivered

- `bifurcation_engine/src/eigenvalues.py` — `jacobian` (verbatim from the PDF / CLAUDE.md), `eigenvalue_pair` (uses `numpy.linalg.eigvals`; returns `(alpha, omega)` with the convention that for real eigenvalues `omega = 0` and `alpha = max(Re λ₁, Re λ₂)` since the dominant real part is what governs stability), and `track_eigenvalues` (loops `eigenvalue_pair` over a continuation result, preserves any `branch` column, exposes a boolean `is_complex` array).
- `bifurcation_engine/src/hopf_detector.py` — `HopfResult` dataclass and `detect_hopf`. The detector explicitly distinguishes `no_complex_eigenvalues`, `complex_no_crossing`, `unstable_throughout`, `hopf_detected`, and `grazing` (added defensively for the "alpha touches zero with vanishing slope" edge case). A non-Hopf result is never raised as an error — it is a populated, descriptive `HopfResult`. Super-/sub-critical classification is intentionally deferred to Task 6 (nonlinear integration), per the spec, and `outcome='hopf_detected'` is the interim label when the three Hopf conditions are satisfied.
- `bifurcation_engine/tests/test_eigenvalues.py` and `bifurcation_engine/tests/test_hopf_detector.py` — full coverage of the Jacobian form, the real/complex branching of `eigenvalue_pair`, T5.1 (clean-orbit analytical eigenvalues to `atol=1e-10` across six parameter combinations), and T3.1–T3.5 with a parametric sweep of crossing locations to stress the L_c interpolation.

### Test status

`82 passed, 3 skipped` — the three skips remain on T1.4 (needs Task 6's `integrate_trajectory`), Task 7 (early warning), and the cross-task validation scenarios T5.2/T5.3 (also dependent on Task 6).

### Pipeline results — eigenvalue outcome per shell

I analysed three branches per shell at 201 sampled L values: Case 1 (`D* = 0`), Case 2 lower (smaller `D*`), and Case 2 upper (larger `D*`). The `continuation_sweep` Case-2 tracker (which follows the upper branch and truncates near the saddle-node fold) was also exercised and agreed with the direct analytical sweep.

| Shell | Branch | Outcome | Why |
|---|---|---|---|
| **A — 600 km** (`δ_S=0.02`, `δ_D=0.10`, `β=1e-5`, `γ=1e-7`) | Case 1 | `no_complex_eigenvalues` | T5.1: clean-orbit eigenvalues are `-δ_S` and `β·S* − δ_D`, both real. |
| | Case 2 lower | `complex_no_crossing` | Eigenvalues complex on 179/200 points but `α` stays in `[-0.10, +0.10]` with **the positive-α region living entirely in the real-eigenvalue part** of the branch — within the complex region `α` is strictly negative (stable spiral throughout). |
| | Case 2 upper | `no_complex_eigenvalues` | This is the saddle-like branch: `α ≈ +0.10`, `ω = 0` everywhere. |
| **B — 800 km** (`δ_S=0.005`, `δ_D=0.02`, `β=1.5e-5`, `γ=1.5e-7`) | Case 1 | `no_complex_eigenvalues` | Same as A, by T5.1. |
| | Case 2 lower | `complex_no_crossing` | Complex on 17/135 points; `α` strictly negative wherever the eigenvalues are complex. The branch terminates at the fold near `L ≈ 670`. |
| | Case 2 upper | `no_complex_eigenvalues` | Saddle branch, `α > 0`, `ω = 0`. |
| **C — 1000 km** (`δ_S=0.001`, `δ_D=0.005`, `β=1e-5`, `γ=2e-7`) | Case 1 | `no_complex_eigenvalues` | Same as A, by T5.1. |
| | Case 2 lower | `complex_no_crossing` | Complex on 3/13 points; `α` strictly negative there; only 13 valid points because the fold sits near `L ≈ 30` (very low `L_c` for this drag-poor shell). |
| | Case 2 upper | `no_complex_eigenvalues` | Saddle branch as in A and B. |

**Net result: no Hopf bifurcation is found in any of the three shells with the literature-calibrated parameters.** Across all nine branch analyses, two of the three non-Hopf outcomes appear, both for valid mathematical reasons. There is no `unstable_throughout` because the lower-branch spirals are stable wherever they are spiral.

This matches the explicit caveat in CLAUDE.md ("A Hopf bifurcation is NOT guaranteed — it depends on parameter values") and the geometry of the model: with these parameters, the lower coexistence branch loses existence by colliding with the upper branch in a **saddle-node fold**, not by passing the spiral's real part through zero. To confirm this isn't just an artefact of literature parameters I also swept `γ` on Shell B from `1×` to `50×` its catalogued value — the lower branch keeps reporting `complex_no_crossing` throughout, suggesting the fold-vs-Hopf preference is structural for the 2D source-sink form `S_dot = L − δ_S·S − β·S·D`, `D_dot = β·S·D + γ·D² − δ_D·D`.

This is the kind of finding TODO.md and VALIDATION.md flag as a *legitimate scientific result, not a failure*. Useful next steps (Phase 2 candidates, not Phase 1 work):

- Broader parameter exploration: scan `(β, γ, δ_D)` jointly to map any region where the lower-branch spiral does cross `α = 0` while remaining complex. The detector is now ready to report it cleanly.
- Add a saddle-node detector alongside the Hopf one: the system clearly *does* undergo a fold bifurcation that destroys the safe coexistence equilibrium; that fold is the real "Kessler tipping point" in this model and deserves its own structured output.
- Move to a 3-species form (active satellites / derelicts / debris) as MOCAT-pySSEM uses, where the extra dimension gives the Jacobian room to admit a genuine Hopf.
