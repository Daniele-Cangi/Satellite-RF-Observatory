# Paired navigation hypotheses and local controls

The [single-epoch mechanism](PNT_NAVIGATION_WITNESS.md) showed a common
satellite-clock message bias absorbed by the fitted receiver clock. This
extension asks whether that additional **content evidence** remains visible
when local residual and clock-continuity controls are calibrated and applied
over later epochs. It also tests an altered range case that a NAV-only
comparison cannot distinguish. This is exposed software exploration, not
prospective confirmation or a recorded RF attack benchmark.

`python -m pnt navigation-compare` accepts an original observation/NAV pair,
named alternative observation/NAV pairs and named external NAV witnesses.
It reuses the existing observation reader, broadcast admission/propagation,
clock fit, nearest-rank quantile and issue comparator. Model records retain
their original file indices, so an epoch's witness evidence refers to the
actual records used, including when unhealthy records were skipped before
them. All source NAV records are retained without a `toc` filter. An unused
contradiction cannot become a discrepancy for fitted satellites.

Two local controls are evaluated: maximum minus minimum satellite residual,
and absolute change in fitted clock between consecutive 30-second epochs.
Clock steps never bridge an unavailable/failed epoch. Original-only prefix
calibration supplies the 95% nearest-rank threshold for each; exceedance
means strict `>`. The union has no calibrated 5% false-alarm guarantee.
Candidate and evaluation measurements never set the thresholds. Independent
fits must have the same satellite support at both ends of a clock step to
enter a paired comparison. Changed support, missing NAV, all-unhealthy NAV,
failures and incomplete controls remain visible rather than invoking a
fallback or reducing both fits to an easier intersection.

## Inputs and fixed software cases

The original observations are the previously exposed [NYA2 RINEX file][obs]
for 11 September 2024; its antenna coordinate is
`[1202379.31, 252474.6543, 6237786.5417]` m ECEF from the header/antenna
declarations, not an independent survey. GPS C1C/C2W form an ionosphere-free
code. The [NOAA composite GPS NAV][nav] supplies the original model and the
only external message witness. **It is also the parent of the synthetic NAV
variants:** this does not qualify source independence or a local RF recording.

The original-file SHA-256 values are:

- NYA2: `1bd263249839795fe24ac86a2df362d89bf6fe0658b08f635772efbd3c7ab7e0`.
- NOAA: `ef484bb751743dcb37601112c2a6c0b81c7e738b4cb9f2faf4bfb1fa446aace3`.

Calibration is `[28800,30600)` GPST seconds, 60 requested epochs; 59 have
both controls because the first has no previous sample. Evaluation is
`[30600,34200)`, 120 requested epochs. These exposed windows, defaults and
five supplied variants were used without an amplitude/window/threshold
search. No benign ground-truth label is assigned to the original file.

- `serialized_copy`: decode the gzip to ASCII and serialize unchanged lines
  with LF and a final newline. This changes bytes, not compared message fields.
- `common_nav_bias`: add `2048 * 2**-31` s to every record's `af0`.
- `common_nav_drift`: add `16 * 2**-43` s/s to every `af1`; add to `af0`
  the drift at that record's `toc` relative to GPST second 30600, rounded
  to the nearest `2**-31` s unit using half-to-even rounding. It is an
  affine common-clock **model perturbation**, with `af0` quantization;
  mixed satellite `toc` values leave small differential remainders.
- `G02_nav_bias`: the same bias, only in G02 records.
- `unchanged_nav_G02_code_ramp`: retain original NAV; add an identical
  0-to-20 m linear ramp to nonblank G02 C1C/C2W fields on the evaluation
  grid, zero at 30600 and 20 m at 34170. Leave quality characters and
  other observations unchanged. G02 is not used at every epoch.

The NAV variants apply to the complete source file, including their
calibration-period records. They represent alternative already-present NAV
hypotheses, **not takeover transitions** into a running receiver. Their
calibration-period values do not set thresholds. No independent receiver
clock or prior absolute-clock anchor is supplied. All variants are software
files; no RF capture, tracking or hardware oscillator behavior is simulated.

## Results

All six cases retain 180 requested epochs and all 120 evaluation epochs are
comparable. Thresholds are **7.257972102612257 m** residual spread and
**0.9985365159809589 m per 30 s** fitted-clock step.

| Case | Local control union exceedances / 120 | Used-message discordance / 120 | Discordant while both local controls quiet / 120 |
|---|---:|---:|---:|
| Original | 7 | 0 | 0 |
| Serialized copy | 7 | 0 | 0 |
| Common NAV bias | 7 | 120 | 113 |
| Common NAV drift | 9 | 120 | 111 |
| G02 NAV bias | 106 | 106 | 0 |
| Unchanged NAV, G02 code ramp | 74 | 0 | 0 |

The common bias moves the fitted clock by about **285.905 m**, with a maximum
per-satellite residual change of **0.001319 m** across evaluation. The clock
drift's change grows from **0.004321 m** to **1.907487 m**; maximum residual
change is **0.078530 m**. It increases local exceedances from 7 to 9, which
is retained. In both cases external field content is discordant in epochs
where the two stated local controls remain quiet. This quantifies the
mechanism beyond a single fit; it does not establish attack detection gain.

The single-satellite NAV bias is already obvious under these local controls
when G02 is used; the other 14 epochs remain message-compatible. The range
ramp creates 74 local exceedances but **all 120 used-message comparisons
remain compatible**. A match must never be promoted to RF/position/time
authentication. Unchanged payloads can accompany harmful signal manipulation,
as also discussed in [relay-attack research][relay].

These are correlated epoch counts, not 120 independent attacks. The original
seven exceedances are not certified false alarms. Passing these controls does
not mean C/N0, Doppler, PVT, navigation history, tracking flags, oscillator
limits or an independent-clock check would pass. The comparator retains the
serialization-precision rules of the original NAV diagnostic, including its
coarse-zero limitations. Freshness, provider independence and RF attribution
remain unqualified. **P2 remains open.**

## Reproduction and retained evidence

The [complete CLI report](results/pnt_navigation_comparison_2024255_v1.json.gz)
has 12,484,419 uncompressed bytes and JSON SHA-256
`2e42d44367422c1e87d7e05e5bba88299ec60d72191678eb0de81e3b507faaf4`.
It preserves original and variant input hashes, all compared NAV fields and
external records, thresholds, per-epoch source indices/residuals/clocks,
coverage and paired results. Original reports remain unchanged; replay of
the full JammerTest UBX report after sharing the comparator is identical.

For the NAV variants, start from the decoded original lines. The body starts
after `END OF HEADER`; records have eight lines. Clock fields are characters
22:41 and 41:60 in each first line. Write only modified fields using Python
`f'{float(value):19.12E}'`; preserve all other characters. For drift, use
`Decimal(2) ** -31`, `16 * Decimal(2) ** -43`, and
`((slope * (toc_s - 30600)) / lsb).to_integral_value(rounding=ROUND_HALF_EVEN) * lsb`.
Write each output with LF and a final newline. Required filenames/hashes
are in the retained report. An initial development formatter unnecessarily
rewrote unchanged `af1` fields and serialized decimal zero with a coarse
exponent. It was corrected before retaining v1; all evaluation/paired
summaries remained identical. No criterion or scientific outcome was changed.

For the OBS variant, use `hatanaka.decompress(source, strict=True)` and retain
all decoded lines. The GPS `SYS / # / OBS TYPES` lists C1C at index 0 and
C2W at index 4 in this source. In each G02 record after an epoch line in
the evaluation window, change the nonblank 14-character numeric component
at `3 + 16 * index` to
`f'{float(value) + 20 * (gpst_s - 30600) / 3570:14.3f}'`.
Keep the two quality characters and all remaining fields. This modifies
234 code fields (117 G02 epochs); write LF and a final newline. This precise
transformation should reproduce the `G02_code_ramp.rnx` hash in the report.

With sources and derived files in the current directory:

```console
python -m pnt navigation-compare 2024-09-11 NYA200NOR_R_20242550000_01D_30S_MO.crx.gz brdc2550.24n.gz --case serialized_copy NYA200NOR_R_20242550000_01D_30S_MO.crx.gz serialized_copy.n --case common_nav_bias NYA200NOR_R_20242550000_01D_30S_MO.crx.gz common_nav_bias_v1.n --case common_nav_drift NYA200NOR_R_20242550000_01D_30S_MO.crx.gz common_nav_drift_v1.n --case G02_nav_bias NYA200NOR_R_20242550000_01D_30S_MO.crx.gz G02_nav_bias_v1.n --case unchanged_nav_G02_code_ramp G02_code_ramp.rnx brdc2550.24n.gz --witness NOAA=brdc2550.24n.gz --start 28800 --calibration-stop 30600 --stop 34200 --output NEW.json
```

Use a new output path; the CLI refuses overwrite. The resulting JSON should
match the retained uncompressed report. Tests cover calibration poisoning,
clock gaps, both ends of support changes, witness conflicts, unused records,
filtered source indices, all-unhealthy cases, model failures, unchanged NAV
with altered codes, and CLI reproducibility. Existing Linux/Windows CI runs
these tests without another experiment-specific runner, seal or replay layer.

## Next physical evidence

A bounded source check found additional candidates but did not produce a
decoded, matched benign/NAV-altered recording in this work. [Tuni2025][tuni]
lists authentic/spoofed scenarios as roughly 30 GB raw IQ files per scenario;
[FGI-JSDR][fgi] also primarily exposes raw IQ with a software receiver. Neither
description alone supplies qualified decoded measurements for this benchmark.
[GNSS-WASP's artifacts][wasp-data] are an 8.7 GB archive; its [paper][wasp]
describes reusable models and experimental datasets. The archive was not
downloaded or qualified here. This is a limited metadata check, not a claim
that no suitable public recording exists.

Apply this comparison next to a documented physical benign/altered case with
retained local NAV and observations and contemporaneous external messages;
qualify local controls, timing and source dependencies for the proposed
claim. A software receiver applied to public recorded IQ is a possible
hardware-free route, requiring its own bounded decoding feasibility check.
Do not tune further variants of this exposed file to claim P2 completion.

[obs]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/NYA200NOR_R_20242550000_01D_30S_MO.crx.gz
[nav]: https://noaa-cors-pds.s3.amazonaws.com/rinex/2024/255/brdc2550.24n.gz
[relay]: https://arxiv.org/abs/2204.11641
[tuni]: https://zenodo.org/records/17413258
[fgi]: https://www.maanmittauslaitos.fi/en/research/research/gnss-specialists/fgi-gnss-jamming-and-spoofing-dataset-repository-fgi-jsdr
[wasp-data]: https://zenodo.org/records/14779157
[wasp]: https://www.usenix.org/conference/usenixsecurity25/presentation/tibaldo
