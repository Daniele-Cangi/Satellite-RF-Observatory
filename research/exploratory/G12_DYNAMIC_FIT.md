# G12: shared dynamic RF fit with globally excluded endpoints

## Result and decision

**Current evidence: [v4](results/g12_dynamic_fit_v4.json), after PR #221 review.**
The earlier v1–v3 calculations used historical RF-fitted propagation in
preprocessing. No known target orbit entered them, but their claim of no prior
target-state dependence was too broad. Those bytes remain historical diagnostic
results and are withdrawn as support for independence from earlier fitted
geometry. v4 recomputes propagation within the new fit and records this correction.

**The shared RF fit is implemented and improves some excluded predictions; S2
remains open.** It estimates a common position/velocity and free constant station
code contrasts from real observations, without a target orbit or previously
fitted target state as an initializer or prior. Central and central-plus-J2
variants converge. Neither produces an accepted, qualified reconstruction:
code-only results have an incomplete branch search; code-plus-phase results
fail the unchanged conditional residual test.

For central-plus-J2 code-only fitting, excluded code RMS is **1.071 m**, versus
**2.684 m** for independent short arcs on exactly the same 85 observations.
Most exclusions are interpolation gaps inside the fitted time span. The final
30-second forecast, beyond every training endpoint, **worsens** from 2.108 to
2.334 m across five receivers. Its phase-rate prediction improves, although
phase did not enter this fit. These observations do not establish position
accuracy, prospective confirmation or general forecasting ability.

Adding phase gives a converged but **MODEL_REJECTED** fit: chi-square 352.563
on 173 residual degrees of freedom, p = 2.29e-14 under the historical weights.
Excluded phase-rate RMS improves from 0.02069 to 0.00808 m/s, but code RMS
worsens from 0.943 to 1.111 m. Improving one observable cannot override the
rejection or erase the worsening of another.

The next physical question is the source of the incompatible phase increments:
separate clock-transfer/propagation and trajectory-model contributions using
independent diagnostics at the same times. Establish their uncertainty budgets
before imposing additional constraints. Nominal J2 alone does not resolve this
rejection. Do not lower weights, change masks, promote the result to production
or begin S3 on this evidence.

## Cohort and exclusion boundary

The [full-hour result](G12_FULL_HOUR.md) contains forty adjacent 90-second windows
on 2026-09-05, 10:00–11:00 GPST. Using all their training triads would leak each
window's nominal +90-second holdout into the next window's training start.
This new comparison therefore fixes **even chronological indices only**, then
inherits the historical accepted status separately for each estimator:

- Code only: 17 arcs, 255 training codes, 85 excluded endpoints.
- Code plus phase: 8 arcs, 120 training codes, 80 interval phase rates,
  40 excluded endpoints.
- All forty old case/fit labels remain in each variant, including six whole
  window mask failures, the old code prediction failure and 22 phase rejections.
  Reserved odd windows and rejected/missing even windows are never substituted.

Training is at start, +30 and +60 seconds. Each excluded observation is at +90.
The global `(station, GPST time)` key sets are disjoint across the whole fit,
not just within each local arc. The excluded phase interval shares its first
endpoint with training, but its second endpoint appears in no training arc.
That shared endpoint prevents treating fit and forecast noise as independent;
no predictive confidence interval is claimed here.

There are sixteen code-only and seven phase temporal holdouts, followed by one
beyond-all-training forecast per estimator. Both kinds extrapolate each arc's
own local clock by 30 seconds, but only the last extrapolates the shared
trajectory beyond all training. Code and phase cohorts differ; do not interpret
their aggregate difference as a controlled effect of adding phase.
Historical admission and all RF values are already exposed. This is conditional
development evidence, not an observation-blind selection or new confirmation.

## Estimator and physical scope

`research/kinematic/dynamic_fit.py` fits six shared initial-state parameters,
five zero-mean station-code contrasts across six sites, and the unchanged local
satellite-clock, receiver-clock and ground-coordinate parameters for every arc.
Common constant code bias remains a satellite-clock gauge. Bias contrasts enter
code only; they supply no artificial carrier increment or absolute phase anchor.
No station-bias, orbital radius, energy, velocity or known target-state prior is
introduced. Initialization uses training endpoint codes and independent clock
calibrations through the existing RF multilateration solver.

The trajectory uses the [previously declared central/J2 force approximations](G12_DYNAMICS_FEASIBILITY.md)
in uniformly rotating ECEF, with Coriolis/centrifugal terms. GPST reception tags
are corrected by fitted receiver clocks; geometric light time determines emission,
and Earth rotation maps the emitted position to the reception frame. Satellite
clock slopes use transmit GPST. Phase measurements are **interval mean rates**
from endpoint paths, not instantaneous Doppler. The code epoch is 10:01 GPST;
the phase epoch is 10:04 GPST. State vectors at these different epochs cannot
be subtracted directly as a model disagreement.

Training now consumes raw codes and phase increments. Clock means are rebuilt
from the admitted reference-only reports. Historical target-state, propagation,
elevation and clock-prior arrays are not used numerically. The old fit statuses
still determine the explicitly exposed comparison cohort; this is not blind
selection. VMF3 is recomputed at the current shared trajectory and fitted
receiver clocks/ground at each optimizer evaluation, with its sensitivities
included in the joint Jacobian. Excluded paths use the same propagation function
at the fitted geometry and original 10-degree mask. Predictions for
all four variants are fixed and hashed before scoring any excluded values.
No future observation determines a propagation correction or light time.
This remains the declared additive delay approximation on geometric vacuum
light time, not a complete radiative propagation model or physical error budget.

Weights remain 20 m code sigma, 0.02 m phase-endpoint sigma, 2 m receiver-clock
offset sigma, 0.01 m/s receiver-clock slope sigma and 0.5 m ground-coordinate
sigma. Endpoint differencing retains within-arc phase correlations. Separate
arc covariance blocks, repeated station coordinates and reference calibrations
are treated as independent only for this conditional development model. Shared
errors, temporal correlations, propagation changes, bias stability, RF antenna
motion, force omissions and terrestrial-frame orientation remain unqualified.
Residuals never rescale the covariance.

The optimizer whitens the complete data and calibration rows, eliminates local
nuisances by QR, and solves the remaining shared state/bias system by SVD. The
resulting 11-parameter local design is full rank. Its covariance is the marginal
shared block, with local nuisance freedom retained, not the covariance obtained
by holding clocks/ground fixed. Rank and small residuals do not imply physical
identifiability with a justified total uncertainty.

## Complete comparison

Values include diagnostic predictions from rejected/incomplete fits. Phase-rate
columns use m/s, code columns metres; worsening counts compare absolute errors
on the same receiver/time pairs.

| Fit | Status | Excluded pairs | Code RMS / old | Phase RMS / old | Code / phase worsened |
|---|---|---:|---:|---:|---:|
| Code, central | BRANCH_SEARCH_INCOMPLETE | 85 | 1.067 / 2.684 | 0.01243 / 0.08349 | 29 / 18 |
| Code, central + J2 | BRANCH_SEARCH_INCOMPLETE | 85 | 1.071 / 2.684 | 0.01234 / 0.08349 | 28 / 17 |
| Code + phase, central | MODEL_REJECTED | 40 | 1.165 / 0.943 | 0.00806 / 0.02069 | 22 / 7 |
| Code + phase, central + J2 | MODEL_REJECTED | 40 | 1.111 / 0.943 | 0.00808 / 0.02069 | 20 / 7 |

| Fit | Final forecast code RMS / old | Final forecast phase RMS / old |
|---|---:|---:|
| Code, central | 2.297 / 2.108 | 0.02307 / 0.12194 |
| Code, central + J2 | 2.334 / 2.108 | 0.02444 / 0.12194 |
| Code + phase, central | 1.844 / 1.317 | 0.00675 / 0.00643 |
| Code + phase, central + J2 | 1.746 / 1.317 | 0.00682 / 0.00643 |

Each fit retains one initial multilateration branch inside Earth that cannot be
propagated in the declared exterior-Earth model. It is not silently discarded
to label the search complete. The converged code solution passes the conditional
residual test (cost about 0.37 on 210 degrees of freedom), but branch failure
prevents an accepted outcome. The very small code cost relative to the assumed
20 m sigma is not permission to reduce that historical floor.

For the J2 phase fit, the whitened cost splits into code **0.254**, phase
**351.873**, independent reference-clock measurements **0.435**, and ground
coordinates **0.000267**. Almost all incompatibility lies in the phase block
of this declared model. That decomposition localizes the diagnostic, but does
not identify its physical cause or establish that the clock transfer is correct.

The formal weakest bias-contrast standard deviation is about **523 m** with code
and **257 m** with phase. The largest local 95% position semiaxis at each fit's
own epoch is about **7.79 km** and **3.89 km**, respectively. These are conditional
Gaussian scales, especially inappropriate as confidence claims for a rejected
model. They are not physical accuracy, coverage, a total error bound or a
comparison on identical cohorts. No target orbit/oracle was opened to assess
absolute accuracy or tune the model.

## Numerical correction and retained attempts

[v1](results/g12_dynamic_fit_v1.json), produced by commit `1e1dcca`, retains the
first four-variant run: code converged; both phase fits ended with numerical
line-search failures. [v2](results/g12_dynamic_fit_v2.json), produced by
`64c31fe`, retains the same failures after a joint-metric convergence diagnostic.
Neither phase failure is rewritten as an accepted fit or scored retrospectively.

[v3](results/g12_dynamic_fit_v3.json), produced by commit `51c17ad`, corrects
the Jacobian instead of relaxing
the scientific test. Integrated state-transition matrices use the analytic
central/J2 rotating-frame force derivative. Implicit light-time derivatives
include Earth rotation, station coordinates and both clocks. Differentiate
endpoint paths first, then apply the interval operator, with an exactly zero
additive satellite-clock derivative for phase. This avoids noisy finite
differences of already-differenced large ranges. Final proposed joint steps are
below 1.5e-6 in the fixed whitened-data metric; the numerical tolerance is 1e-4.
Weights, cohorts, masks, constant-bias model and p = 0.01 residual threshold stay
unchanged. All original output bytes and their producer versions remain in Git.

v4 removes the historical propagation dependency identified in review and
includes the atmospheric state, receiver-clock and ground sensitivities. These
differentiate the small delay first, then chain through the current geometric
light-time derivatives; no historical fitted state enters that calculation.
All four fits converge with final joint steps below 1.7e-6, using the same
numerical tolerance. The residual rejection and forecast worsening persist.
Tests poison cached propagation, elevations and clock priors as well as old
states and excluded RF. CI branch-retention assertions check every actually
returned root exactly once, rather than a platform-dependent root count;
state/bias accuracy tolerances and failure semantics are unchanged.

## Reproduction and checks

```console
python -m research.exploratory.g12_dynamic_fit NEW_OUTPUT.json
python -m pytest research/kinematic/tests/test_dynamic_fit.py research/kinematic/tests/test_orbital_dynamics.py research/exploratory/tests/test_g12_dynamic_fit.py -q
```

Run an older version from its producer commit to reproduce that numerical attempt.
The reports retain input/producer hashes, pinned weather receipt, all old status
labels, training/exclusion keys, every branch history/failure, fitted clocks/
ground/biases, marginal covariance, fixed predictions and all paired residuals.
Git and the existing replay/input checks suffice; no new authority or wrapper
is introduced. Historical independent-arc results and production code are unchanged.

Tests cover synthetic state/bias recovery with visible failed branches; force,
variational and observation derivatives against independent perturbations;
analytic circular motion and conserved central dynamics; constant code bias
absent from phase; rejection before target decoding; duplicate training keys;
strict covariance; poisoned future RF/historical fitted states; complete real
cohorts, retained rejections/worsenings and scoring replay. Existing Linux/Windows
CI discovers these tests without changing its coverage. Full numerical fitting
is reproducible with the command above, not claimed as part of each CI run.
