# Kinematic research — S0/S1 and S2a delivered

The approved project is `docs/SCIENTIFIC_ROADMAP.md`. Website and remote-service
work are paused. The first deliverable is complete: read-only archive diagnosis
and an idealized code/range-rate synthetic comparison, with explicit failure
cases. See `results/REPORT.md` and the machine-readable reports alongside it.

S2a adds the receiver-time vacuum model, independent inertial validation,
GPS Doppler field conversion, reference-only affine clock fitting and correlated
joint estimation. See [equations and remaining S2b work](S2_MODEL.md) and
[S2a results](results/S2_REPORT.md). Full RF qualification remains pending;
S2a does not authorize S3 acquisition.

The first [S2b bridge](S2B_REFERENCE_BRIDGE.md) now imports bounded GPS RINEX
reference observations and navigation, fits clock offset/drift from codes and
checks unused Doppler with correlated uncertainty. Its
[six-case report](results/S2B_REPORT.md) includes all rejections. Fixtures are
invented; receiver qualification and the total inverse-error budget remain open.

## Preserved S1 study

The original S1 modules `model.py` and `synthetic.py` are a development
research prototype, not an RF estimator. They use
known common ideal times, fixed receivers, Euclidean ranges, an affine shared
clock, and independent known noise. They omit light-time, rotating-frame effects,
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
python -m research.kinematic.s2_validation PATH_TO_NEW_S2_STUDY.json
python -m research.kinematic.s2b_validation PATH_TO_NEW_REFERENCE_STUDY.json
python -m research.kinematic.uncertainty_study PATH_TO_NEW_UNCERTAINTY_STUDY.json
python -m research.kinematic.joint_study PATH_TO_NEW_JOINT_STUDY.json
python -m research.kinematic.physical_source_study PATH_TO_NEW_PHYSICAL_STUDY.json
python -m research.kinematic.phase_bridge_study PATH_TO_NEW_PHASE_BRIDGE_STUDY.json
```

Report writers refuse to overwrite an existing output. Compare numerical
results with sensible floating-point tolerance across platforms. The committed
report records exact source bytes and runtime versions at execution time;
the imported v1 source hashes can differ with checkout line endings. It does
not claim externally trusted timestamping or byte-identical numerical execution.

## S2 scope and remaining work

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

S2a delivers the vacuum geometry and synthetic clock/correlation checks in
items 1–3. Real headers and receiver conventions, reference-residual generation,
propagation and a total inverse-error envelope are still required. The exact
boundary and the remaining S2b tasks are updated in `S2B_REFERENCE_BRIDGE.md`.

The subsequent local inverse-error module transports a full input covariance
through the fixed S2a estimator to position, velocity and excluded predictions.
It adds uncertain ground coordinates/holdout clocks and separate affine
systematic modes including fit distortion under constant jerk. See
[S2_INVERSE_UNCERTAINTY.md](S2_INVERSE_UNCERTAINTY.md) and
[its synthetic report](results/S2_UNCERTAINTY_REPORT.md). This does not supply
a total nonlinear envelope or recalibrate the old residual test for new errors.

The separate [joint estimator](S2_JOINT_FIT.md) now fits RF, clock and ground
coordinate observations with one declared covariance, including cross blocks.
Its residual test and local uncertainty use the same weights. The
[paired synthetic report](results/S2_JOINT_REPORT.md) retains all sixteen
noise pairs and both mismatch stresses. Real covariance qualification,
nonlinear/selection calibration and total error bounds remain open.

The [physical-source audit](S2_PHYSICAL_SOURCES.md) finds only four Doppler
declarations in the archived G14 pool, with none for GOLD. The separate
reference phase-increment adapter explores interval-mean rates and their
correlations; it does not substitute them into the instantaneous-rate fit.
See the [audit and synthetic report](results/S2_PHYSICAL_REPORT.md).

The [phase-reference bridge](S2_PHASE_REFERENCE_BRIDGE.md) now imports full
code/phase RINEX fixtures, fits clocks from codes and checks unused phase
increments with the same endpoint model and complete residual covariance.
Its nine-case study detects the injected unflagged slip but retains a small
undetected common drift. It is not yet an inverse phase estimator or RF
qualification; see [the report](results/S2_PHASE_BRIDGE_REPORT.md).

Do not edit the five frozen experiments, lower their floors, use the target
orbit to initialize, or present the synthetic error reduction as measured RF
improvement. Updates to research results must retain the previous report and
identify what changed in the design or implementation.
## Interval inverse prototype

The separate [interval estimator](S2_INTERVAL_INVERSE.md) compares endpoint
codes with/without interval-mean phase observations, retaining full covariance
and an excluded-interval prediction. Its [report](results/S2_INTERVAL_REPORT.md)
is synthetic and does not qualify real receivers or authorize S3.

```text
python -m research.kinematic.interval_study NEW_REPORT.json
```
## Interval systematic sensitivity

The [systematic sensitivity study](S2_INTERVAL_SYSTEMATICS.md) distinguishes
deterministic state bias from residual detection power for six fixed temporal
templates. Its [report](results/S2_SYSTEMATICS_REPORT.md) retains both signs;
the amplitudes are synthetic assumptions, not qualified physical limits.

```text
python -m research.kinematic.systematics_study NEW_REPORT.json
```
## Shared reference/target calibration

The [shared calibration study](S2_SHARED_CALIBRATION.md) derives compressed
clocks from explicit synthetic reference-code residuals and preserves target
cross covariance. Its [report](results/S2_SHARED_CALIBRATION_REPORT.md) includes
an accepted but biased curvature case; the reference-phase gate remains separate.

```text
python -m research.kinematic.shared_calibration_study NEW_REPORT.json
```
## Reference phase gate before shared target fitting

The [shared phase gate](S2_SHARED_PHASE_GATE.md) tests unused reference phase
increments before target loading. Its [eight-case report](results/S2_SHARED_PHASE_REPORT.md)
retains the smaller curvature that still passes despite a biased position.

```text
python -m research.kinematic.shared_phase_study NEW_REPORT.json
```
## Slow shared-path calibration

The [quadratic calibration prototype](S2_SLOW_CALIBRATION.md) estimates slow
shared path terms from reference codes, retains correction uncertainty, and
compares affine/quadratic fits and excluded predictions in a fixed development
study. [Results](results/S2_SLOW_CALIBRATION_REPORT.md) are not independent RF confirmation.

```text
python -m research.kinematic.slow_calibration_study NEW_REPORT.json
```
## Frozen-model validation outside the quadratic basis

The [separate synthetic validation](S2_SLOW_VALIDATION.md) retains six fixed
shape comparisons and eight paired noise trials, including rejections and
excluded-band misses. [Report](results/S2_SLOW_VALIDATION_REPORT.md).

```text
python -m research.kinematic.slow_validation NEW_REPORT.json
```

## First real reference-only qualification attempt

The frozen DOY252 attempt stopped on an undeclared descriptive `MARKER TYPE`
condition before any observation number was parsed. Its generated physical
terminal is not scientifically authorized; the audited outcome is
`QUALIFICATION_EXECUTION_INVALID`. No capability was rejected, no target field
was inspected and no payload was persisted. See
[S2_REAL_REFERENCE_QUALIFICATION.md](S2_REAL_REFERENCE_QUALIFICATION.md).
The hardened distinct DOY253 attempt retained complete source receipts and
qualified ALGO/BOGT structure, then closed `PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED`
at DRAO because its legacy `WAVELENGTH FACT L1/2` phase-scale transform was not
part of the frozen RINEX-3 ledger. This is a bounded set-level refusal, not a
claim that DRAO or carrier phase is generally unusable.

The follow-up [header-only transform audit](S2_PHASE_TRANSFORM_HEADER_AUDIT.md)
preserved two execution-invalid attempts, then closed on mature DOY243 evidence
with `PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED`. ALGO, BOGT, MKEA, PIE1 and GOLD
had complete identity/coverage and exact identity scale/phase-shift ledgers.
DRAO, STJO and YELL failed the frozen composite RINEX format admission before
their transform ledger was produced. The exact offending descriptor component
was not retained, so no narrower format claim is authorized. Eight source
artifacts were hashed in RAM; zero observation/body lines, navigation products
or measurement values were exposed or persisted. Do not search another date to
make this exact set pass; S3 remains unauthorized.

The subsequent [five-root feasibility audit](S2_FIVE_ROOT_FEASIBILITY.md) uses
only the qualified ALGO/BOGT/MKEA/PIE1/GOLD coordinates and an explicitly
synthetic, target-free geometry family. All 181 jointly visible cases have full
local rank, but the conditional code+phase envelope at +60 s spans 0.501–83.332
km and only 65 cases meet 10 km. Exactly five fit roots also leave no independent
held-out root, while the total physical error envelope remains unresolved. Its
terminal is `FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE`; this result does not
authorize S3 or select a target/date.
