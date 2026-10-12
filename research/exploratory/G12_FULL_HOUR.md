# G12: what the full exposed hour adds to bias identifiability

Exploratory follow-up of 12 October 2026 to the
[geometry decision](G12_BIAS_GEOMETRY_DECISION.md), using only previously exposed
2026-09-05 RF observations, GPST 10:00-11:00. No target orbit/clock product or
oracle-error report is opened. The inverse solver, 20 m code floor, 10 degree
elevation mask, conditional covariance and historical outcomes are unchanged.

**Result:** the earlier geometry supplies useful additional local information,
but does not close S2. Twelve phase fits can now contribute, including seven
from the first half-hour. The weakest formal scale for shared constant bias
contrasts is about 1,993 m. This concerns bias coefficients under conditional
weights, not position accuracy or a physical uncertainty bound. The analysis
profiles information at existing RF fits; it does not estimate a new shared
bias-corrected trajectory.

## Calibration and qualification

Reuse `reference_phase_clock` with an explicit evaluation boundary at 10:00.
Its default remains the original 10:30 boundary. The GPS-only reference extract,
precise reference products and reference-derived elevation admission exclude G12.
No target observation supplies a clock estimate.

The extension supplies 720 receiver/time clock estimates, with zero unqualified
clock blocks. Every second-half estimate and held-out reference diagnostic is
**exactly identical** to the retained GPS-only v2 report. The full report retains
6,708 held-out reference diagnostics, 130 rejected observations, 722 paths below
the reference mask, 59 reference-model failures, 20 unbridged intervals and the
unsupported YELL station. The median estimator's held-out RMS is 0.000514 m/s;
its maximum absolute discrepancy remains 0.028286 m/s. These diagnostics share
upstream products and do not establish an absolute clock or transfer bound.
BOGT worsens when the earlier observations are included: its median diagnostic
RMS grows from 0.000284 to 0.000583 m/s and its maximum from 0.002072 to
0.016154 m/s. That discrepancy remains in the report rather than being removed
to improve the calibration summary.

Use forty disjoint 90 s windows: fit three endpoints over 60 s, then predict the
fourth endpoint. Select ALGO/DRAO/AREQ/BOGT throughout, STJO before 10:30 and BRAZ
afterward, according to the already exposed structural coverage. Selection does
not search residuals or the oracle for another receiver or passing window.
Receiver-time, light-time, Earth rotation and ECEF state conventions are inherited
unchanged from the [original interval model](REAL_TARGET_INTERVAL.md).

| Outcome | First 20 windows | Original last 20 windows | Full hour |
|---|---:|---:|---:|
| Window reaches corrected RF fits | 14 | 20 | 34 |
| Window fails original elevation mask | 6 | 0 | 6 |
| Code fit and excluded prediction accepted | 13 | 20 | 33 |
| Code fit/prediction failure | 1 | 0 | 1 |
| Phase fit and excluded prediction accepted | 7 | 5 | 12 |
| Phase model rejected | 7 | 15 | 22 |

The six whole-window failures start at GPST seconds 37260 through 37710 and
retain STJO elevations 9.926 down to 7.630 degrees. At start 37170 the code
fit's excluded prediction encounters STJO at 9.927 degrees; it remains
`FIT_OR_PREDICTION_FAILED`. No mask reduction or substitute station rescues it.
The original twenty second-half outcomes and fitted states are reproduced.
Excluded RF predictions/residuals remain in the JSON for every admitted fit;
their existence is not an independent accuracy or confirmation result.

## Information across changing receivers

Reuse the whitened QR nuisance elimination from `g12_bias_geometry`: eliminate
each arc's entire position/motion, clock and station-correction design. Keep the
60 s trajectories separate rather than fitting an hour-long quadratic orbit.

Each five-station arc has four zero-mean bias contrasts. Map those contrasts to
five contrasts over the six distinct receivers, removing the arc-local common
offset through its target-clock gauge. The four common stations connect STJO
and BRAZ across the two subsets. Tests show that a receiver absent from all
admitted arcs remains unconstrained, rather than acquiring a fictitious bound.

| Admitted design | Arc count | Profile rank | Weakest singular value, per m | Formal weakest-coefficient scale, m |
|---|---:|---:|---:|---:|
| Code, shared constant contrasts | 33 | 5/5 | 1.93699e-4 | 5,163 |
| Code + phase, shared constant contrasts | 12 | 5/5 | 5.01852e-4 | 1,993 |
| Code, constant + linear drift | 33 | 10/10 | 9.16556e-8 | 10,910,413 |
| Code + phase, constant + linear drift | 12 | 10/10 | 4.60455e-4 | 2,172 |

Rank uses the existing 1e-10 relative rule after nuisance elimination. It is not
the earlier single-arc 38/40 or 39/40 full-model rank. The drift coefficient is
the bias change in metres across the admitted endpoint span (3,510 s for code,
3,060 s for phase), with its change inside each arc included; it is not m/s.
The older half-hour constant-phase scale was 16,119 m for four contrasts over
five receivers. The full-hour table has a different parameter domain and an
additional receiver, so this is not a position-accuracy improvement factor.
Halving/doubling the derivative step at the same fitted points gives a phase
constant-bias scale of 1,990-1,996 m and drift scale of 2,168-2,176 m. All four
designs retain their ranks, and their scales change by less than one percent;
the numerical check does not qualify the underlying physical covariance.

All scales are reciprocals of local profile singular values, under the original
conditional covariance and block-independent arc weights. Shared reference
products, temporal correlations, bias stability, nonlinear behavior and total
physical uncertainty remain unqualified. A full local rank does not make those
assumptions true. In particular, permitting code-bias drift exposes much weaker
code-only information; it must not be hidden by requiring constant bias.

## Physical decision and next measurement

The phase constant-bias weak direction, normalized to maximum absolute station
amplitude one, is approximately:

```text
ALGO     DRAO     AREQ     BOGT     STJO     BRAZ
-0.323   -1.000   +0.448   +0.291   -0.100   +0.683
```

The sign is arbitrary; the pattern is a differential mode, not a diagnosis that
a named station is faulty. A useful additional constraint must measure or bound
an effective station-code bias projection with a nonzero component along this
mode, independently of the target orbit. A common clock offset has no such
component. Constant carrier ambiguities also prevent code-minus-phase levels
from furnishing the missing absolute anchor.

The next physical question is whether reference-only public observations and
compatible signal-bias/clock products can establish that differential constraint
and demonstrate its transfer across viewing conditions. The required bound must
include signal conventions, propagation/multipath, clock-calibration dependencies
and shared products; reference RMS alone is insufficient. Its precision must
follow a declared position-error budget and the measured bias-to-position
response, rather than an oracle error or a convenient threshold. If such transfer
cannot be justified, a compatible independently calibrated range/delay constraint
or genuinely different qualified geometry is needed. No instrument purchase or
availability of that measurement is assumed here.

The full-hour availability question is now answered. Do not continue adding
windows administratively, lower the mask or start S3 on these exposed data.
Resolve or bound the remaining physical mode before claiming independent
position/motion reconstruction with defensible uncertainty.

## Reproduce

From the repository root, using `requirements-positioning.txt`:

```console
python -m research.exploratory.reference_phase_clock NEW_CLOCK.json --phase-input research/exploratory/inputs/real_phase/observations_gps_only_v2.json --after-gpst-s 36000
python -m research.exploratory.g12_full_hour NEW_HOUR.json --clock-report NEW_CLOCK.json
python -m pytest research/exploratory/tests/test_reference_phase_clock.py research/exploratory/tests/test_g12_full_hour.py research/exploratory/tests/test_g12_bias_geometry.py -q
```

[Full-hour calibration](results/reference_phase_clock_full_hour_v1.json) and
[full-hour qualification/information](results/g12_full_hour_v1.json) retain
input/source hashes, all failures, all forty cases and admitted profiles. The
original interval, calibration and bias reports remain unchanged. Active code
reuses the existing calibration, solver, covariance and profiling primitives;
historical source versions remain in Git. No new authority, seal or checked
executor is introduced.
