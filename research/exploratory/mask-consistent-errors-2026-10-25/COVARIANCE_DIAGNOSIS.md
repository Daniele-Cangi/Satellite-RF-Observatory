# Diagnose the original covariance-image refusals

Follow up the four retained failures without changing their numerical rule or
producing a new predictive comparison. Reconstruct all five original folds,
including the G19 control, using the same input, masks, endpoint covariance,
source response, prefix cut and inner calibration fits. The original prediction
producer/result at `12a427a` remains immutable. This is exposed-data diagnosis.

For both prefix-only and all-admitted errors, record the original spectral cut,
retained rank, discarded positive eigenvalues, error projections, acceptance
tolerance and the first rejection stage. Independently replay each error from
the raw-factor operator F and admitted whitened inputs: e=F*y_white, C=F*F.T.
The Rayleigh variance of the rejected error direction is evaluated from F
directly and from C, distinguishing nonzero discarded response from loss of
precision or an inconsistent error operator. Spectra and component values are
retained; no held RMS or alternate rank/timescale is used to select a result.

The existing report command gains a diagnostic mode:

```console
python -m research.exploratory.masked_prediction_study --diagnose-mask --output data/mask-covariance-diagnosis-2026-10-25
```

The output directory must be new. This mode does not fit the corrective process
variance, condition new corrections, access the comparison file or run the held
scorer. It saves diagnostic data through the existing report writer and source/
input identities. There is no covariance rescaling, changed guard or new
authority/replay executor. Original outcomes and model criteria stay unchanged.

## Result: the numerical image cut discards positive-variance directions

The [retained diagnostic](covariance-diagnosis.json.gz), produced at
`f3d40d2212d5ba2c780f8013c7d62713b5c54b0a`, reproduces all four refusals.
One five-fold replay took 115.293 s. Every inspected covariance has strictly
positive computed eigenvalues: its smallest is about 2.7182e-8 m2, including
the failing cases. No new correction or held score was computed.

| Fold | First refusal | Retained rank / errors at that stage | Covariance condition number | Discarded error L2, mm | Guard tolerance, micrometres |
|---|---|---:|---:|---:|---:|
| G05 | all admitted | 1382 / 2252 | 1.746e10 | .150694 | .162338 |
| G11 | all admitted | 1461 / 2383 | 1.743e10 | .149334 | .177439 |
| G19 | none | 960 / 960 | 6.466e5 | numerical roundoff | .077216 |
| G20 | all admitted | 1339 / 2266 | 1.736e10 | .151711 | .190875 |
| G21 | prefix | 583 / 875 | 1.018e10 | .089509 | .185455 |

These L2 values are aggregates over admitted diagnostic coordinates, not RMS
errors of the held predictions. G21's all-admitted image also fails (1051/1716
retained directions); G05/G11/G20's prefix images retain every direction.

The guard uses `lambda > 1e-10 * lambda_max`. It therefore imposes an implicit
condition-number ceiling of 1e10. G21 already crosses it in the prefix, while
G05/G11/G20 cross it only after adding later admitted errors. Their largest
eigenvalues rise from about .014 m2 in the prefix to 472-475 m2 in the complete
error vector, raising the cut from about 1.4e-12 to 4.7e-8 m2. G19 remains on a
much smaller spectral scale and never crosses the ceiling. The rule discards
292-927 positive eigen-directions in the failing images, then requires their
error projection to be essentially zero. Those requirements are incompatible
with the observed nonzero components even though the full covariance is positive.

Two independent checks separate this from the alternative explanations:

- The raw-factor error replay agrees with the native refitted errors to better
  than **4.43e-10 m per coordinate**, with total defects below 2.63e-9 m. That is
  far below the rejected projections. An inconsistent error operator is not
  supported as the explanation at this resolution.
- The rejected direction has positive variance when evaluated directly as
  `norm(F.T @ direction)**2`: about 2.72-2.74e-8 m2 at the first failures. This
  agrees with the independently associated quadratic form in C; their absolute
  discrepancies are below 6e-18 m2 there. The dropped variance is not merely a
  negative/zero eigenvalue produced by forming the Gram matrix.

The factor-direction statistics are meaningful only for genuinely discarded
directions. For full-rank images, the tiny projection residual is roundoff;
normalizing that roundoff does not define a scientifically interpretable null
direction. No full-rank Rayleigh statistic is used in this conclusion.

## Consequence and scope

The immediate cause is the numerical rank convention, not evidence that new
physical observations are needed to compute this conditional correction. This
does not establish physical covariance, an accurate orbit, or that removing
the numerical obstruction will improve the original held benchmark.

The next engineering change should distinguish small positive variance from
an unobservable direction, with backward-error/residual checks and a factor or
equilibrated solve. Simply lowering the cutoff until the held scores improve
would not be an acceptable argument. No alternative solver, rank tolerance,
process fit or corrected predictive execution was tested in this diagnosis.
The original 4-fold refusal, the G19-only gain and the incomplete-support
failure remain unchanged. A future corrected execution needs its own retained
result under the same original inputs, masks and acceptance criteria.
