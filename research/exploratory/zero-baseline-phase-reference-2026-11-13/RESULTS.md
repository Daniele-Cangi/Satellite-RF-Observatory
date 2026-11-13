# Zero-baseline wide-lane reference with receiver epoch alignment

Exploratory follow-up on the two exposed [WUT receiver windows](../known-wide-lane-2026-11-12/RESULTS.md).
The question is whether the carrier phases on a common antenna can supply
wide-lane labels independently of the two satellites' MW codes. No G12
observations or target state are opened.

## Compared models

At a shared antenna, range and propagation cancel in simultaneous receiver
differences. The same nominal GPS timestamp can still describe two true
reception times. Let receiver A's reported time lead B's by tau. The
between-satellite carrier phase at A, evaluated at B's reception time, is
approximately its measured value plus tau times its rate in cycles per
second. Apply that correction separately to L1C and L2W before testing
their DD integers. A nominal epoch match alone cannot guarantee this
cancellation. [Receiver time misalignment](https://doi.org/10.1017/S0373463315000053)

Estimate tau as the median of (C1C_A − C1C_B) / c among at least three
simultaneous GPS satellites outside the pair. Use a central one-second
difference of the carrier between-satellite difference at A for the rate.
No coefficient is fitted to the result or to MW. The clock observable
includes code path delays and remains a proxy for true epoch alignment.
Test the nominal alignment and reverse the correction sign as controls.

Require all 300 one-second epochs to have admitted L1C and L2W at the
four endpoints. Reject LLI flags and missing phase. In each band, every
available corrected sample in the first minute must support the same
integer with a diagnostic 0.10-cycle per-band error allowance. All usable
corrected samples in the remaining four minutes must support that prefix
integer. The centered rate excludes the first and last window epochs and
the prefix endpoint next to the split. There is no ambiguity repair.

Score the original, uncorrected MW at the eight held 30 s epochs. This
deliberately asks whether the observable used in the earlier studies
agrees with the phase reference. Retain the signed held MW mean minus
the conditional label N1 − N2. This effective offset includes any residual
noise and code/phase timing effects. The alignment uses C1C from other
satellites, so the labels do not use the pair's MW code, but neither
the receiver hardware nor all measurement errors are independent.

## Results

| Start (GPST) | Scheduled | Missing phase / flag | Scored without alignment | Scored with opposite sign | Scored with physical sign |
|---|---:|---:|---:|---:|---:|
| 00:00 | 465 | 429 | 9 | 6 | 36 |
| 12:00 | 465 | 420 | 3 | 2 | 45 |

Among all 81 complete-phase cases, the physical sign produces agreement
between the prefix and held per-band phase integers. The largest deviation
from an indicated integer after alignment is 0.0441 cycles per band.
Nearest MW integer agrees in all 81 scored cases. There are 849 cases
without full phase coverage. They were not scored. The three comparisons
use the same input and search space and retain every rejection.

Eight of 81 held effective offsets exceed 0.10 wide-lane cycles in absolute
value. The maximum is 0.177 cycles. Six satellite pairs are scored in both
windows. The median magnitude of their between-window offset changes is
0.056 cycles and the maximum is 0.112 cycles for G04–G26. The latter exceeds
a 0.10-cycle transfer allowance in this comparison. These are descriptive,
dependent cases, not a real-world wrong-fix rate or a calibrated transfer
bound. Both windows share receivers, date and antenna.

## What would make the reference independent

The alignment isolates a measurable mechanism, but proximity to the integer
cannot rule out a whole-cycle offset in either band's independently defined
phase convention. The 0.10-cycle phase-error allowance has not been
established by metrology. Repeating uncalibrated RINEX windows would still
leave that degree of freedom and could only characterize empirical drift.

A useful next source supplies synchronous GPS L1/L2 phase with a logged or
independently characterized receiver epoch difference and a per-band phase
delay characterization or independently anchored integer labels. The
largest sampled L1 inter-satellite phase rate here is 6765 cycles/s. To give
unmeasured timing a 0.025-cycle allocation within a candidate uncertainty
budget would require an alignment uncertainty below about 3.7 microseconds
at that rate, before bounding other terms. The exact budget must come from
the new instrument setup. A shared frequency reference alone does not
authenticate the receiver's phase origin. A same-antenna, common-clock
calibration with measured path and phase offsets is a candidate once these
properties are documented. [Receiver phase bias calibration](https://doi.org/10.1515/jogs-2017-0014)

The observed WUT transfer range does not qualify the distributed #245
network. The orbital solver remains float.

## Reproduction

Use the four WUT window prefixes described in the previous report and a fresh
output path.

    python -m research.exploratory.zero_baseline_phase_reference --cache data/known-wide-lane-wut --output data/wut-alignment.json

The [archived results](results.json.gz) include source hashes, the three
variants, all pair outcomes and the six between-window comparisons.
