# Can public references constrain the G12 differential bias?

## Decision

The tested **station-direction error law does not qualify as a transferable
bias correction**. On the exposed September 5 cohort, excluding each reference
satellite from numerical calibration and coefficient fitting increases later
RF RMS from **1.135228 to 1.168020 m** (+2.89%). Four of seven receivers worsen.
In the six-station differential direction relevant to G12, RMS increases from
**0.867602 to 0.929382 m** (+7.12%). Keep zero correction; do not apply this law
to the inverse solver or reduce its uncertainty floor. S2 remains open.

This is a reference-only exploratory transfer diagnostic, not independent
position reconstruction or prospective confirmation. No G12 measurement,
orbit, clock product or oracle error enters calibration or fitting. The
already exposed [G12 full-hour sensitivity](G12_FULL_HOUR.md) supplies a
station-contrast direction **only for scoring after the reference fits**.
Historical outcomes, source bytes and all production criteria are unchanged.

## Physical question and fixed candidate

The full-hour G12 analysis has local rank five for five zero-mean station-bias
contrasts, but its weakest conditional scale is still about 2 km with phase.
Longer coverage alone has not supplied a useful physical bias bound. Can known
reference satellites provide a transferable error law for that differential
mode, without using G12's trajectory?

Test one candidate: each station has three constant ENU coefficients in metres,
with error law `g_s(u) = a_s dot u`. Fit it on 10:00–10:29:30 GPST, predict a
satellite excluded throughout that fit at 10:30–11:00 GPST, and compare against
zero correction. All 22 reference rotations use the same model and split.
There is no alternative-model search, post-result angular cut, coefficient
tuning, clock refit or selected passing subset in this result. This is an
exposed-data development test, not a preregistered experiment.

It tests an effective dual-frequency-code/model residual, which can contain
site, atmosphere, satellite and product errors. It does not identify a pure
receiver hardware bias. A direction law might describe a site-dependent
component; good training rank does not establish its physical completeness.

## Geometry, calibration and clock datum

Reuse the admitted observations, coordinates, reference products and nonlinear
clock calibration of [the excluded-reference study](PSEUDOTARGET_REFERENCE.md).
G12 records remain excluded through that existing input/product boundary.
Remove the pseudo-target from each reference subset before reading its values
in the numerical clock fit; start every fit at zero and retain the existing
minimum-four-reference, convergence and residual checks. No training block
failed here; a failure would invalidate that fold without rescuing a subset.

Geometry features are observation-free nominal vacuum rays, not the previous
measured-code-dependent directions. Iterate light time using the known
reference antenna phase centre and clock, at nominal zero receiver-clock
offset. Times are GPST; antenna positions are ECEF at emission, rotated into
the reception frame with the existing Sagnac convention, then expressed as
unit ENU rays at the admitted terrestrial station coordinates. This introduces
no G12-state prior and makes no claim to exact atmospheric or receiver-time
geometry. The reference orbit/clock and attitude products are the same guarded
CODE products as in the baseline, with the same hashes.

At each station/epoch, centre both residuals and direction columns over the
remaining references. Fit the centred linear problem by SVD. A constant
station term cancels in this clock datum and cannot be independently learned.
For excluded satellite `q`, subtract the predicted contrast

```text
g_s(u_q) - mean[g_s(u_j) for remaining references j]
```

from its historical zero-correction diagnostic error. The mean is over that
station/epoch's actual remaining subset, not over all satellites. The original
zero-calibrated clock datum is retained; this is an error prediction, not a
new physically qualified clock solution. Queries outside the training row
space or at unseen stations are explicit unsupported outcomes, never zero
fallbacks. All 22 real fits have rank 21/21 (three coefficients at seven sites).

**Selection is inherited, not blind:** the baseline admissions were determined
on exposed data with the original mask/model, which included the reference
later treated as a pseudo-target. Numeric recalibration and coefficient fitting
exclude it; the historical selection itself is not recomputed as an independent
held-out selection. Interpret results conditional on those admissions. The
CODE products may also reuse these receivers. Neither limitation permits an
independent-truth or population-coverage claim.

## Complete result

The original 22 x 7 x 61 grid retains all **9,394 slots**: **3,942 predictions**
and **5,452 pseudo-target-not-admitted outcomes**. All evaluated zero errors
have a paired directional prediction. There are 4,552 distinct first-half
numerical clock calibrations; identical reference subsets reuse identical
evaluations across folds.

| Receiver | Paired paths | Zero RMS (m) | Direction RMS (m) |
|---|---:|---:|---:|
| ALGO | 518 | 1.293018 | 1.379760 |
| DRAO | 576 | 1.643005 | 1.620468 |
| STJO | 529 | 0.934982 | 0.888816 |
| YELL | 563 | 1.173711 | 1.107151 |
| BOGT | 509 | 1.271290 | 1.386178 |
| BRAZ | 686 | 0.659555 | 0.815078 |
| AREQ | 561 | 0.731519 | 0.775614 |
| All | 3,942 | 1.135228 | 1.168020 |

Maximum absolute error changes from 8.566475 to 8.486455 m. This small maximum
decrease does not reverse the pooled RMS degradation. Both statistics are
observations, not future bounds. The near-zero pooled mean of the zero
alternative follows leave-one-out clock algebra, not demonstrated absence of
absolute bias. The directional mean is -0.023887 m.

The closest first-half non-excluded ray at the same station is 0.0746–44.3298
degrees from the evaluated ray (median 23.0705 degrees). Full algebraic rank
therefore does not mean close angular coverage or validated physical transfer.
No prediction is filtered by that angle after evaluation.

## Projection onto the exposed G12 weak mode

Use the unit-norm, zero-mean station weights from the full-hour constant-bias,
code-plus-phase sensitivity:

| ALGO | DRAO | AREQ | BOGT | STJO | BRAZ |
|---:|---:|---:|---:|---:|---:|
| -0.236300 | -0.731773 | +0.328131 | +0.213221 | -0.073425 | +0.500146 |

For each pseudo-target/epoch, project its six simultaneous error values onto
this vector. Zero-mean weights remove a common satellite-clock component.
Require all six stations; do not replace missing sites or renormalize weights.
Of **1,342 declared blocks**, only **32** support this comparison: **19 G05**
and **13 G11**. The other **1,310** remain explicit insufficient-coverage cases.

Projection RMS worsens 0.867602 -> 0.929382 m and maximum absolute projection
worsens 2.335592 -> 2.833451 m. G05 RMS is 0.834777 -> 0.842158 m; G11 is
0.913458 -> 1.043834 m. The projection mean decreases, 0.399297 -> 0.220454 m,
but the full error does not. These are correlated, overlapping tests on two
known references, with shared products and calibration. They do not bound
G12's bias projection or establish a station-error covariance. No target
orbit or RF prediction is fitted in this study.

## What is still missing

Without a qualified transfer assumption, reference records alone cannot bound
an arbitrary target-specific station error: adding `lambda * w` to G12's
effective bias leaves all reference-only records unchanged while moving its
projection `w dot b_G12` by `lambda`. This describes the missing information,
not a proof that every possible physical model or public dataset must fail.
The tested linear direction law supplies no evidence to resolve it here.

A useful independent measurement would constrain that **effective differential
projection**, with matching signal combination, reference-clock convention,
viewing conditions and a justified error budget. An absolute site-bias label
or another reference pooled RMS alone is insufficient. A longer interval with
better simultaneous directional coverage could test transfer more strongly,
but coverage by itself cannot justify the failed law.

The next distinct physical question is whether independently declared orbital
dynamics can connect the existing short arcs and resolve the bias/position mode
without importing the target's orbit, radius or propagated state. Establish
observability and model-error limits first; do not treat a dynamical constraint
as automatically true or convert its conditional covariance into a total bound.
That question is **not executed in this study**. No new prospective experiment,
solver change or administrative gate is introduced here.

## Reproduction and validation

```console
python -m research.exploratory.reference_bias_transfer NEW_OUTPUT.json
python -m pytest research/exploratory/tests/test_reference_bias_transfer.py -q
```

Choose a new output filename. The complete report is
[`results/reference_bias_transfer_v1.json`](results/reference_bias_transfer_v1.json).
It records all fits, station/time/satellite slots, unsupported mode blocks,
input/product hashes and the two new source hashes. Input reports are
`day_reference_v1.json`, `pseudotarget_v1.json` and `g12_full_hour_v1.json`;
their hashes and the existing admitted-input chain preserve the source data.
Git preserves the implementation version. No new checked wrapper or authority
layer is needed.

Eight tests cover recovery of a known transferable law, poisoned excluded and
future values, unsupported directions, complete training failures, missing
station coverage, clock-mode cancellation, observation-free Sagnac geometry,
the real-target boundary and complete stored score/coverage replay. CI runs
them in the existing Linux/Windows positioning matrix. Full numerical raw-data
regeneration is available through the command above; it is not claimed as part
of every CI run.
