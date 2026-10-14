# G12: measured interval clocks and free satellite-clock curvature

## Result and decision

**The clock extension removes the previous phase incompatibility under the
declared conditional weights. It does not close S2.** Position becomes slightly
less constrained, excluded phase predictions worsen relative to v4, and one
initialization branch still fails. Training residuals do not establish accuracy.

The [result](results/g12_interval_clocks_v1.json) retains four development
variants: central / central+J2 gravity, each with independent reference endpoint
errors / an added station-common endpoint-error component. All use the same
eight inherited phase arcs, 120 training codes, 80 training phase increments,
40 excluded receiver/endpoints and historical selection outcomes. No replacement
windows, target orbit/clock product, historical fitted geometry or state prior
enters the estimator. This is exposed-data development, not confirmation.

## Clock model and conditional covariance

At each receiver, retain both G12-excluding reference rates `a1`, `a2`:

```text
m = (a1+a2)/2
c = (a1-a2)/2
b(t) = b_end + m*t + c*h(t)
h(-60)=0, h(-30)=30, h(0)=0       piecewise linear between tags
```

This reproduces both measured increments. Coefficients remain nuisance
observations with covariance, not exact corrections. Every trial recomputes
receive time, geometric light time and VMF3. Constant station-code contrasts
remain free and absent from phase increments.

Each arc also has a free satellite clock `b0+b1*x+b2*x²`, where `x` is transmit
GPST relative to its endpoint. Curvature has no prior or penalty. Full clock,
light-time/state/ground derivatives enter the shared solver. This avoids forcing
an arc-common curved path into trajectory; it does not identify a clock fault.

For +30 s predictions, receiver clocks retain the original fitted mean rate;
their contrast is not extrapolated. The satellite clock uses the linear endpoint
tangent after `x=0`. No quadratic forecast follows the
[failed reference-trend test](G12_PHASE_DIAGNOSTIC.md). All variants' predictions
are fixed before excluded target RF is scored. Only the last five predictions
lie beyond all training times; the other 35 are temporal holdouts.

Code sigma 20 m, phase-endpoint sigma .02 m, receiver-offset sigma 2 m,
historical mean-rate sigma .01 m/s and ground sigma .5 m remain unchanged.
Phase increments retain the shared-middle-endpoint negative covariance.

For the new clock shape, assume three iid reference endpoint errors with sigma
`sqrt(1800)*.01 m`. The two interval rates have covariance
`.01² * [[4,-2],[-2,4]]`; `(m,c)` have covariance
`diag(.01²,3*.01²)`, preserving the historical mean-rate variance.
Receiver offset versus increments and distinct arcs are assumed independent.
The second scenario adds one common endpoint-error process of equal amplitude
across all receivers per arc. Whiten the full within-arc covariance jointly.
This does not reduce any original marginal floor. Neither scale is fitted to
G12 residuals or to overlapping-reference LOO scatter.

These are sensitivity assumptions. Absolute/shared reference errors,
offset-increment and cross-arc correlation, propagation, force error and bias
stability remain unqualified. Two scenarios cannot bound them or establish
population coverage. No residual scaling shrinks the formal covariance.

## Same-cohort evidence

The independent-endpoint variants give:

| Metric | Central | Central + J2 |
|---|---:|---:|
| Weighted training cost / residual dof | 0.2203 / 165 | 0.2117 / 165 |
| Excluded code RMS, 40 pairs, m | 0.8896 | 0.8817 |
| Excluded phase-rate RMS, 40 pairs, mm/s | 8.553 | 8.358 |
| Final beyond-training code RMS, 5 pairs, m | 1.2598 | 1.2517 |
| Final beyond-training phase RMS, 5 pairs, mm/s | 6.597 | 6.678 |
| Largest formal position 1-sigma axis, m | 1510.28 | 1510.29 |
| Largest formal velocity 1-sigma axis, m/s | 0.1786 | 0.1786 |
| Largest formal code-bias contrast axis, m | 274.24 | 274.25 |

All four retain `BRANCH_SEARCH_INCOMPLETE`: one candidate and one interior-Earth
initialization failure per variant, without fallback. The conditional global
design has rank 11 (six state parameters, five bias contrasts), scaled condition
about 1.97 million; nuisance rank checks pass. These local statements depend on
the clock/dynamics/bias model and do not prove global uniqueness.

The upper-tail residual p-value is numerically 1.0 at the unchanged .01
threshold. Cost about .21 for 165 dof is also extremely small: flexible clocks
and conservative/unqualified weights can explain it. This is not the probability
that the physical model is correct. The original v4 rejection stays unchanged.

Against **v4 on the identical phase cohort**, J2 code improves 1.1108 -> .8817 m,
while phase worsens 8.076 -> 8.358 mm/s. Code worsens in 13/40 pairs, phase in
23/40. The final five predictions improve 1.7463 -> 1.2517 m in code and
6.824 -> 6.678 mm/s in phase, but phase remains worse than the historical
short-arc baseline (6.429 mm/s). Against that short-arc baseline, J2 worsens
18/40 code and 7/40 phase pairs. The report's `old_same_cohort_rms` names the
short-arc baseline; `v4_same_cohort` separately retains the prior shared fit.

The J2 position shifts about 869 m from v4; no target orbit is consulted to call
either more accurate. Its largest formal position axis grows 1390 -> 1510 m,
and largest velocity axis .0804 -> .1786 m/s. Added common-reference errors give
nearly identical states, costs and axes (J2 code .8817 m, phase 8.358 mm/s).
Common clock freedom absorbs much of this particular common process; this does
not prove robustness to arbitrary shared systematic errors with other spatial
projections.

## Missing physical information and next check

The [reference-state diagnostic](REFERENCE_STATE_VALIDATION.md) now evaluates
this model on all 22 original candidates with per-fold exclusion. Four produce
trajectories with 66–210 m RMS discrepancies against the shared CODE reference;
other support/numerical failures remain visible. This is conditional evidence,
not physical covariance qualification or a new G12 confirmation.

This removes a demonstrable model restriction without adding physical data.
Qualification still needs an independently supported joint clock/propagation
error budget and absolute position/motion evaluation with the target orbit
excluded from estimation. Additional geometry must constrain receiver-differential
ranges; another station-common correction alone cannot supply that information.
This study does not prove a particular added station or time span sufficient.

Next, evaluate this model's absolute-state error and uncertainty on real
reference targets excluded from their own calibration, before a new prospective
G12 confirmation. Reuse existing data and qualification primitives.

## Reproduction

```console
python -m research.exploratory.g12_interval_clocks NEW_OUTPUT.json
python -m pytest research/kinematic/tests/test_clock_observations.py research/exploratory/tests/test_g12_interval_clocks.py -q
```

The existing result mechanism binds input/source/weather hashes and retains all
branch terminals, predictions and worsening cases. Already exposed JSON is
parsed completely; numerical training excludes future target and reference
values. This is not a value-blind access claim.

The shared solver retains its default linear-clock API. Tests recover synthetic
state/bias with nonlinear clocks, derive joint endpoint/common covariance,
check derivatives by direct perturbation including propagation, poison excluded
values/historical geometry, and retain failures. The old diagnostic test loads
its exact v4 solver from Git; historical hashes/results remain unchanged.
Existing Linux/Windows CI discovers these tests without another workflow.
