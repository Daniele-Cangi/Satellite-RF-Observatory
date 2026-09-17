# Fixed-RF CODE rapid/final comparison

Exploratory paired-product sensitivity on the September 5 reference hour.
This compares two processing streams of the same analysis center. It is not
an independent orbit truth, a target-position estimate or a covariance model.

## Result

All **847 station epochs qualify**, with exactly the same **8074 evaluated
paths**, 4132 training and **3942 test** paths. Changing the reference package
reduces the zero-model test RMS by **2.17%**, from 1.009796 to 0.987925 m.
All seven stations improve. After fitting shared-satellite corrections on
each package's training half, the test RMS is almost unchanged between
packages: **0.931068 versus 0.931178 m** (a difference of 0.11 mm in aggregate
RMS, not a submillimetric positioning accuracy claim).

| Model | Rapid test RMS (m) | Final test RMS (m) | Supported / all test paths |
|---|---:|---:|---:|
| Zero | 1.009796 | 0.987925 | 3942 / 3942 |
| Shared satellite | 0.931068 | 0.931178 | 3942 / 3942 |
| Station direction | 0.978263 | 0.960175 | 3942 / 3942 |
| Station/satellite | null | null | 2801 / 3942 |

The final shared-satellite fit improves its own zero baseline by **5.74%**
and the directional fit by **2.81%**, both at all seven stations. The
station/satellite model retains all **1141 unsupported paths**, with a null
whole-cohort score; STJO worsens even on its supported subset.

Transferring **rapid-trained** shared-satellite coefficients to final test
residuals gives **0.934770 m**, a **5.38%** gain over the final zero baseline,
again improving every station. No final test values enter that training.
This supports persistence across these two product streams; it does not
establish that the learned correction has an independent physical origin.

The RMS of final-minus-rapid test contrasts is **0.069890 m**, with descriptive
residual correlation **0.997792**. This product change shifts the residuals
but does not remove their dominant structure. There is no evidence here
that simply replacing rapid with final products solves the roughly metre
scale residual or qualifies a target-position uncertainty model.

Evidence: `results/final_reference_v1.json`, SHA-256
`51faab82e28ac2a82d1bf4814bfb9f15cb1c6712fb51e3bf555d67ea29f7aaf3`.

The next useful experiment is spatial transfer: estimate the shared-satellite
correction from six stations' training half and test the seventh station's
later half, rotating the excluded station. Preserve unseen-reference and
rank-deficient blocks instead of silently removing them. Use the exposed
rapid/final reference rows as development data, without a target fit or new
acquisition. This asks whether the improvement transfers beyond receivers
that contributed to the local correction fit. The upstream product network
can still contain the excluded station, so it remains conditional validation.

## Fixed experiment

The seven stations, 22 reference satellites, G12 exclusion, September 5
10:00–11:00 GPST RF codes, station displacement series, gridded VMF3 weather
and antenna calibration are exactly those of `DAY_REFERENCE_PREDICTION.md`.
The first 30 minutes train; the remaining 61 epochs test. All four candidate
models and their support/identifiability rules remain unchanged.

Crucially, reference links come from the frozen rapid calibration. Final
geometry cannot silently remove or replace a link. A failed final calibration
suppresses the comparison rather than rescuing a favorable subset. The
935 original below-mask paths remain omitted in both versions.

Change together: CODE rapid orbit, 30-second clock, OSB code biases and
30-second ORBEX attitude become their paired `COD0OPSFIN` products for DOY248.
The final ERP file supplies convention evidence, not a second rotation of
terrestrial orbits or new station displacements. Fixed IERS-derived loading
coordinates remain a common background in both variants.

Both orbit headers declare IGc20, IGS20_2425, FES2014b with the ocean-loading
CMC flag Y, and ORB:CoN/CLK:CoN. Final ERP declares IAU2000R06 and DESAI2016.
Clock and bias headers agree on CODE.BIA and GPS C1W/C2W. Attitudes retain the
explicit ECEF-to-body convention. The final SP3 describes the middle day of
a three-day solution; this is retrospective calibration, not a forecast.

All acquisition URLs and compressed/decoded/extracted hashes are retained in
`inputs/final_reference_v3/receipt.json`. Mixed downloaded files are filtered
by textual satellite identity before numerical state parsing. Neither G12
states nor receiver clock records are admitted to the comparison.

## Acquisition failures retained

1. `5b20664` froze the source filenames and comparison before acquisition.
   The v1 producer selected the orbit and then rejected the native final
   RINEX clock 3.04 because the old reader accepts only 2.00. Its receipt and
   orbit extract remain under `inputs/final_reference/`.
2. `99c4f28` froze a dedicated native 3.04 reader and the unchanged scientific
   choices. The v2 acquisition then encountered Latin-1 accented author names
   in Bias-SINEX bibliographic comments. Its receipt and extracts remain under
   `inputs/final_reference_v2/`. No RF calibration ran in either attempt.
3. `2441fd0` froze v3 acquisition, decoding bias metadata losslessly as Latin-1
   before the existing reference/signal/block selection. The selected bias
   extract is ASCII; no numerical values or selected records are rewritten.
   Already downloaded orbit/clock/bias bytes were reused by pinned hash;
   receipt timestamps identify local verification separately from HTTP access.
   Attitude and ERP were downloaded once. All five selected products succeeded.

The native clock reader preserves 3.04 source headers and uses its expanded
satellite-name field. It recognizes CODE's observed mixed legacy/3.04 header
padding only for an explicit set of labels. It rejects wrong time systems,
antenna/signal/bias conventions, missing or duplicate 30-second samples and
nonfinite values. It does not disguise final data as rapid or as format 2.00.
Format reference: [IGS clock 3.04 specification](https://files.igs.org/pub/data/format/rinex_clock304.txt).

## Execution and interpretation

`5799b2e` froze all final extracts and the analysis before RF evaluation.
The active offline entry point checks the frozen analysis and product adapter:

```text
python -m research.exploratory.final_reference_checked NEW_REPORT.json
```

The baseline input/provenance chain, baseline report, final receipt and
acquisition source manifest are checked before calculation. Output creation
is exclusive; existing reports are not overwritten. Git ancestors preserve
the two pre-calibration failures and the successful input/analysis freeze.

Local fits use only their respective training residuals. A separately labelled
diagnostic transfers the rapid-trained shared-satellite correction to final
test residuals. Centered final-minus-rapid contrasts measure sensitivity of
these fixed RF data to the paired product change. They do not measure the
distance of either product family from physical truth.

Receiver clocks are recalibrated at each test epoch. The scores concern
within-station/epoch clock-free contrasts, not absolute future RF. Products
may contain measurements from these same stations. Repeated improvements
cannot establish independent physical corrections, general satellite
position accuracy or a defensible prospective uncertainty radius.

## Verification and review

Eleven focused tests pass locally, including full numerical replay (210.85 s).
All five retained compressed archives were independently re-extracted after
execution and matched their recorded raw, decoded and restricted hashes.
The full scientific suite also runs on Linux and Windows in CI.

Review identified missing test coverage for changes to the checked CLI wrapper
itself. The freeze regression now compares that entire file byte-for-byte with
its independently resolved `5799b2e` Git blob, in addition to the runtime pins
for analysis and adapter. This preserves the actually executed wrapper and
makes later changes fail CI without rewriting the historical calculation.
The wrapper is not a security boundary against a party able to rewrite both
the checkout and its tests/history; a self-declared hash inside that mutable
wrapper would not provide such authentication either.
