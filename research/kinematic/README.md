# Kinematic research — S0/S1 delivered, S2 pending

The approved project is `docs/SCIENTIFIC_ROADMAP.md`. Website and remote-service
work are paused. The first deliverable is complete: read-only archive diagnosis
and an idealized code/range-rate synthetic comparison, with explicit failure
cases. See `results/REPORT.md` and the machine-readable reports alongside it.

## Scope

This package is a development research prototype, not an RF estimator. It uses
known common ideal times, fixed receivers, Euclidean ranges, an affine shared
clock, and independent known noise. It omits light-time, rotating-frame effects,
propagation, individual receiver-clock calibration and actual Doppler conversion.
Its local covariance excludes systematic/truncation envelopes. Nominal criteria
passing is permission to investigate S2, not permission to use it on real RF
data or claim satellite accuracy, velocity confirmation or global 95% coverage.

Code and code/range-rate fits estimate the same 11 parameters on the same code
samples. Thus the reported comparison isolates the added ideal observable in
this model; it is not a benchmark against the full real-data v1 pipeline.
The holdout receiver and forecast times are absent from fit/initialization.
Synthetic truth is supplied only to generation/evaluation; initialization is
derived from codes and, when available, rates. Finite multistart branch checks
are diagnostics, not a global uniqueness proof.

The case count is 40 nominal fits (20 paired noise seeds), 2 noiseless fits,
and 8 stress fits. No RF source or target orbit was accessed. The failed-model
forecasts are diagnostic values and must not be relabelled accepted predictions.
The paired nominal runs all converged and passed their nominal residual test.

## Reproduce

Use `requirements-positioning.txt` and run from the repository root:

```text
python -m pytest research/kinematic/tests -q
python -m research.kinematic.diagnose PATH_TO_NEW_DIAGNOSIS.json
python -m research.kinematic.synthetic PATH_TO_NEW_STUDY.json
```

Report writers refuse to overwrite an existing output. Compare numerical
results with sensible floating-point tolerance across platforms. The committed
report records exact source bytes and runtime versions at execution time;
the imported v1 source hashes can differ with checkout line endings. It does
not claim externally trusted timestamping or byte-identical numerical execution.

## Next bounded work: S2 observation model

1. Derive the receiver-tagged code/rate model with distinct transmit/receive
   times and Earth rotation. Validate it against an independent synthetic
   generator before admitting any real target measurements.
2. Define Doppler sign, carrier frequency, units, clock-drift calibration and
   missing/lock-discontinuity handling for the supported RINEX signals.
3. Propagate temporal/shared correlations and quantify kinematic truncation.
   The injected jerk is detected by precise rates even when code-only residuals
   do not reject it: a shorter arc or a richer model needs prior justification.
4. Complete exact campaign manifests, code freeze and access history before
   S3 acquisitions. A symbolic target/date blueprint is not ready to execute.

Do not edit the five frozen experiments, lower their floors, use the target
orbit to initialize, or present the synthetic error reduction as measured RF
improvement. Updates to research results must retain the previous report and
identify what changed in the design or implementation.
