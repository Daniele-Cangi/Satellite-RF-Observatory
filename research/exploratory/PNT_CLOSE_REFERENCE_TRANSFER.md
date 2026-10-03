# Does a nearby reference topology improve later residual prediction?

The previous [long-baseline transfer](PNT_REFERENCE_TRANSFER.md) did not show
a consistent useful advantage. This extension tests a different physical
prerequisite: nearby receivers can share more of the propagation error than
the distant NYA2/TRO1/KIRU topology. It reuses `python -m pnt transfer` without
changing its model, support rules, training or evaluation. It adds no detector,
threshold, new executor or prospective experiment.

## Data and coordinate boundary

The public [GFZ WegenerNet archive][archive] exposes unchecked Level-0 Septentrio
logs under CC BY 4.0. W181, W182 and W183 were chosen as the first three station
names on 2024-09-11, first for a midnight intake, then for the previous A/B
windows. All three rotations are retained. There is no outcome-dependent
station/window replacement. This is exploratory public-data development,
not observation-blind or prospective confirmation.

The declared midnight coordinates give baselines W181–W183 **4.632 km**,
W181–W182 **5.261 km** and W182–W183 **9.892 km**. All three receivers are
PolaRx5, with distinct serial numbers but the same firmware/provider. Their
ReceiverSetup coordinates change during the day; antenna type is `Unknown`,
and declared H/E/N offsets are zero. No independent surveyed antenna position,
coordinate uncertainty, benign certification or RF challenge is provided.
Small separation alone does not establish independent truth.

The [retained inputs](../../pnt/tests/fixtures/wegener20240911/README.md) include
all twelve original compressed hourly logs and the converted RINEX inputs.
RTKLIB EX CONVBIN 2.5.1 converts Meas3 to RINEX 3.04 with distinct GPS C1C/C2W
signals. Nine evaluation files contain 360 measurement epochs per receiver,
30 seconds apart, with no SBF CRC failure. The converted OBS has 359 epochs:
the last epoch, 10:59:30, is omitted. It stays missing in all methods; no repair
or replacement is used.

An external `gnss-js@2.6.0` decode agrees with **22,275** common GPS C1C/C2W
pseudoranges within 0.0005 m (RINEX rounding). Its only unmatched finite GPS
codes occur at the omitted final epoch: 22/17/20 for W181/W182/W183. Both
implementations share RTKLIB Meas3 lineage; this is not independent decoder or
physical validation. CONVBIN also reports 201/147/212 non-GPS NAV errors;
retained traces identify BeiDou/SBAS PRNs and count them twice across its two
passes. The calculation uses the unchanged NOAA GPS NAV from the prior study,
not this converted NAV. Other constellations are outside the model.

**Coordinate correction:** the first six calculations used CONVBIN's default
header, which takes the last ReceiverSetup coordinate at approximately 10:00,
during evaluation. Those results remain in `preliminary_late_coordinate_variant`.
An attempted `-hp` override still produced that header; three repeated A results
are retained under `failed_coordinate_override_attempt`, stopped before B.
The final inputs replace only APPROX POSITION XYZ with the midnight declaration,
rounded to 0.1 mm, available before any 08:00 training. The observation body is
identical. This correction was motivated by the metadata boundary, not by
the residual score; windows, stations and model were unchanged. The corrected
run follows numerical exposure and remains exploratory. Earlier declarations
avoid evaluation-time metadata but do not establish target-independent survey
truth. Exact original variant bytes can be reconstructed from retained headers
and the shared observation bodies.

## Method and result

Unchanged training medians per satellite pair and one zero-intercept slope `b`
predict the centered local residual from the mean centered external residual.
Training uses at least five epochs per pair, six qualified pairs per epoch
and twenty eligible epochs. Evaluation compares local `u`, unit `u-v` and
learned `u-b*v` on exactly the same support. Epochs have equal weight; correlated
pairs, stations and windows are not independent trials. No extra covariate,
regularization, coefficient clipping, tuning or reference selection is added.

| Window GPST | Training | Evaluation |
|---|---|---|
| A | 08:00–08:30 | 08:30–09:30 |
| B | 09:30–10:00 | 10:00–11:00 |

Each run has 60 eligible training epochs. Evaluation is 120/120 in A and
119/120 in B, with one explicit `INSUFFICIENT_EVIDENCE` at 10:59:30. Across
the six runs, 717/720 requested receiver-window evaluation rows are scored.
The three omissions represent the same absent epoch across rotations.

RMS below is metres of pair-residual innovation, **not position accuracy**.
Positive MSE reduction means improvement over local-only prediction.

| Window | Local | Learned b | Local RMS | Unit RMS | Learned RMS | Learned MSE reduction | Worsened / scored epochs |
|---|---|---:|---:|---:|---:|---:|---:|
| A | W181 | 0.1383 | 0.9254 | 1.2143 | 0.9176 | +1.664% | 49/120 |
| A | W182 | 0.2206 | 1.2579 | 1.3823 | 1.2435 | +2.287% | 45/120 |
| A | W183 | 0.0715 | 1.2122 | 1.3613 | 1.2046 | +1.254% | 39/120 |
| B | W181 | 0.0620 | 0.9190 | 1.2814 | 0.9173 | +0.372% | 55/119 |
| B | W182 | 0.0670 | 1.3867 | 1.5261 | 1.3827 | +0.571% | 54/119 |
| B | W183 | 0.1131 | 1.2330 | 1.4515 | 1.2300 | +0.492% | 61/119 |

Learned transfer improves aggregate MSE in 6/6 comparisons, by 0.372–2.287%,
equivalent to only about 0.186–1.150% RMS reduction. Unit subtraction worsens
all six, by 20.746–94.437% MSE. Learned coefficients remain small. Worsenings
remain visible by epoch and pair-count stratum; even B/W183 worsens more
scored epochs than it improves. No significance interval or population
performance is inferred from this small, correlated, exposed sample.

The late-coordinate preliminary variant also improves all six aggregate
learned comparisons, by 0.531–1.344% MSE, while unit transfer worsens all six.
Its different scores show that coordinate handling matters even after training
median subtraction. Neither coordinate declaration is a verified survey.

**Decision:** this topology supports a small descriptive transfer effect,
but does not demonstrate a useful security advantage. Keep uncorrected residuals
as the baseline and this transfer as exploratory diagnostics. Do not search more
regressions on these windows for a larger gain. The prior distant-site result
is unchanged; this comparison changes receivers, geometry and environment,
so it does not isolate baseline distance as the cause. A worthwhile next step
must add matched challenge/benign evidence or a physically distinct observable,
not more administrative gates or another slope variant.

Shared errors can include harmful manipulations; subtracting them is not RF
authentication. No spoofing detection rate, equal-false-alarm benefit, attack
attribution, position accuracy or absolute-time verification is established.
P2 remains open. The NAV-content results and historical experiments are untouched.

## Reproduction and checks

From the repository root, using the retained converted inputs:

```console
python -m pnt transfer 2024-09-11 pnt/tests/fixtures/wegener20240911/W181_fixed.obs.gz pnt/tests/fixtures/gfz20240911/brdc2550.24n.gz --reference W182=pnt/tests/fixtures/wegener20240911/W182_fixed.obs.gz --reference W183=pnt/tests/fixtures/wegener20240911/W183_fixed.obs.gz --start 28800 --train-stop 30600 --stop 34200 --output NEW_CLOSE_TRANSFER.json
python -m pytest pnt/tests/test_close_reference_transfer.py pnt/tests/test_transfer.py -q
```

Rotate W181/W182/W183, then repeat with `34200,36000,39600`. The unchanged CLI
refuses output overwrite. To regenerate OBS, decompress and concatenate original
08/09/10 logs in time order, run the pinned converter command in provenance,
then replace only the coordinate header with the recorded midnight ECEF values.
Converter timestamp/path comments change on a fresh conversion; retained
fixed-column inputs provide exact portable replay. Binary archive/hash, optional
cross-check package integrity, source hashes, coordinates, failed attempts and
rounding/coverage checks are in the existing-style provenance receipt.

The [complete result](results/pnt_close_reference_transfer_2024255_v1.json.gz)
retains six primary, six preliminary and three repeated/aborted-attempt reports,
including all training/evaluation rows, exclusions, fits, innovations, errors,
support strata and source hashes. Uncompressed: 38,342,928 bytes, SHA-256
`1164dbd845b3717032a8f5db99bc3c17968903503f4537a2299c82e0082238d0`.
Regression tests replay every primary report, including the shared missing
epoch and all worsening outcomes, and reconstruct the original variant inputs.
Existing Linux/Windows CI includes the tests without new external dependencies.

[archive]: https://isdc-data.gfz.de/gnss/WegenerNet/
