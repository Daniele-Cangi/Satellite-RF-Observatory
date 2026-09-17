# Reference errors transported to synthetic position and motion

## Scope and evidence

This exploratory study connects the actual seven receiver coordinates and
reference incidence from September 5 to a synthetic, vacuum, code-only target.
No real target codes, target orbit, inverse target fit or physical covariance
qualification are involved. Existing production uncertainty floors are unchanged.
It extends the earlier calibration-transfer and kinematic sensitivity work with
the chronological, excluded-receiver correction operator.

The fixed design uses 4132 training reference paths, 747 evaluation paths and
77 synthetic target codes (seven stations, eleven epochs at 30 seconds).
Each receiver's shared-satellite correction is learned only from the other six
receivers' first half-hour. Both zero and shared correction alternatives remain.
The synthetic radii are 12, 26 and 42 million metres, with initial tangent speeds
0 and 4000 m/s and inward acceleration 0.5 m/s². Zero initial speed is not a
stationary trajectory. All six designs are reported: five have rank eleven;
the 12-million-metre, 4000 m/s design fails the fixed five-degree mask (3.559°).
No replacement design is selected.

## Error chain

For additive raw errors, the corrected synthetic codes obey
`d = e_target - K_test e_test + mean(S_test) C_other_train e_train`.
Here K averages references within a receiver/epoch; C fits centered reference
contrasts using a minimum-norm satellite-offset gauge. Thus the map includes
training errors, evaluation errors and their explicitly specified correlations.
The code response is mapped through the local eleven-state Jacobian (position,
velocity, acceleration and two clock parameters). Covariance is transported as
`G J Sigma J^T G^T`. This is local linear sensitivity, not a global nonlinear
bound or the complete production calibration iteration.

All amplitudes and covariances are invented scenarios. Outputs are largest-axis
standard deviations, not 95% radii, measured errors or calibrated accuracy.
The retained independent 20 m code control is a synthetic weighting/control;
it does not represent the complete real error budget. Added-mode totals assume
independence from that control explicitly, not as an established physical fact.

## Results at radius 26 million metres, initial speed 4000 m/s

Values below are the added unit-mode principal standard deviations alone.
Time zero is the last observation; +60 s is beyond the observed window.

| Assumed error mode | Correction | Position at 0 (m) | Position +60 s (m) | Velocity at 0 (m/s) |
|---|---|---:|---:|---:|
| Independent 1 m on all raw codes | zero | 34.521 | 44.872 | 0.195714 |
| Independent 1 m on all raw codes | shared | 34.546 | 44.892 | 0.195725 |
| Reference-only persistent station offset, 1 m | either | 57.881 | 57.681 | 0.011554 |
| Reference-only station ramp, 1 m / 300 s | either | 0.349 | 11.976 | 0.196537 |
| Reference-only station process, 1 m, correlation time 60 s | either | 52.217 | 66.031 | 0.276229 |
| Persistent reference-satellite offset, 1 m | zero | 12.974 | 12.965 | 0.018636 |
| Persistent reference-satellite offset, 1 m | shared | <0.000001 | <0.000001 | <0.000001 |
| Identical persistent station offset on references and target | either | numerical zero | numerical zero | numerical zero |

The independent 20 m control alone gives 655.743 m at time zero, 852.378 m
at +60 s and 3.718262 m/s. These figures are conditional synthetic responses.
Across the five valid designs, the 1 m reference-only station offset gives
11.173–165.909 m at time zero. Its centered reference response is zero: residual
RMS cannot constrain this amplitude. A perfectly matched target/reference offset
cancels instead. Physical reference-target coupling therefore matters as much
as the reference residual size. The satellite-mode cancellation is a constructed
mode lying inside the fitted model, not evidence of real error removal. Fitting
also slightly increases independent-noise propagation in this example.

## Frozen versions and replay

Commit `dec7f4a` freezes v1 before execution. Its origin lay at the middle of the
observed window: its +60 s output is interpolation, not forward prediction.
Its unchanged six-case result remains at `results/position_error_v1.json`.
Commit `b2e7792` preserves that result and freezes v2 before execution, moving
the origin and coordinate snapshot to 10:35 GPST, the last observed epoch.
V2 retains every design, including the newly failed elevation-mask case.

Active entry point:

```console
python -m research.exploratory.position_error_checked_v2 NEW_OUTPUT.json
```

The output must not already exist. The wrapper checks pinned sources and plan;
tests additionally bind the wrapper itself to its frozen Git blob and ancestry.
V2 result SHA-256:
`422f09adba2232aa704f5cd9e77272d16431cffc5a4311a198c4cb59d0dad84a`.
Nine tests cover direct least-squares equivalence, receiver exclusion,
blind/common modes, cancellation, rank and forward epoch, full replay,
frozen ancestry, exact v1 result bytes, the admitted pinned-report cohort and
rejection of changed source/report before computation. The frozen runner accepts
one exact report hash; it is not a generic admission boundary for future reports.

## Next physical work

S2 remains open. Use already exposed reference RF to rotate an excluded
reference satellite through a pseudo-target test, excluding it from receiver
clock calibration. Measure the differential reference-to-pseudo-target error
and its temporal/cross-station behavior before promoting a correction. Keep
zero/shared alternatives, unsupported links and every failed case. This can
constrain differential errors but cannot identify a perfectly common product
or station mode. Explicit external bounds or additional independent observables
are still needed for those modes. Do not substitute this synthetic study for a
new target confirmation or reduce the existing uncertainty floor.
