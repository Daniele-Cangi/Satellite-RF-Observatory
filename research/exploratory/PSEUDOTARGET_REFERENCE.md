# Excluded-reference differential RF test

## Result

On the exposed September 5 RF data, excluding each reference satellite from
both receiver-clock calibration and shared-offset training leaves a pooled
differential code RMS of **1.135228 m without correction** and **1.132307 m
with correction**: only **0.2573%** improvement. This does not reproduce the
larger benefit obtained when the satellite's own offset could be learned.
The experiment therefore provides no basis for promoting the shared correction
as a general improvement for an unseen target.

All 22 declared reference rotations fitted the remaining 21 offsets at rank 20
plus one fixed clock gauge. All 3942 admitted test paths were evaluated with
both alternatives. The complete 22 × 7 × 61 grid contains another 5452 slots
where the pseudo-target was not admitted in the baseline data; these are retained
explicitly, not replaced. No numerical or remaining-reference failure occurred.

| Receiver | Zero RMS (m) | Shared RMS (m) |
|---|---:|---:|
| ALGO | 1.293018 | 1.292335 |
| AREQ | 0.731519 | 0.719799 |
| BOGT | 1.271290 | 1.276964 |
| BRAZ | 0.659555 | 0.661637 |
| DRAO | 1.643005 | 1.642010 |
| STJO | 0.934982 | 0.928068 |
| YELL | 1.173711 | 1.161389 |

Five receivers improve and two worsen. Maximum absolute differential residuals
are 8.566475 m / 8.665187 m. These maxima are observations, not future bounds.

## What is excluded and what is evaluated

The plan and implementation were frozen at `c9c3917` before this calculation.
Every fold excludes one reference from **all** first-half receiver-clock fits
and shared-satellite coefficient training. First-half times are 10:00–10:29:30
GPST; second-half times are 10:30–11:00 GPST. The seven stations and baseline
reference admissions remain fixed, including the original ten-degree mask.

At each epoch, the clock is recalculated from the remaining references starting
at zero, iterating the actual CODE rapid orbit/clock, antenna-attitude, site
coordinates and VMF3 model. For shared correction, subtract the trained offsets
from reference range-minus-model values before estimating the receiver clock.
The pseudo-target code and model are accessed for evaluation only after that
clock is fixed. Its coefficient is never estimated or applied.

The diagnostic retains minimum four remaining references and the existing
reference residual/split thresholds. It checks clock closure at 1 micrometre
with at most eight iterations. Observed closures stayed below that threshold
in two or three iterations. It does **not** repeat the production SPP ground
coordinate check; `EVALUATED` is a diagnostic outcome, not full event admission.

This uses known reference states to evaluate differential RF errors, not to
recover an independent position. G12 remains excluded from observations and
orbit parsing; none of the closed target events is refitted. Upstream CODE
products may reuse these receivers, so this is not statistically independent
truth. No physical covariance or uncertainty floor is qualified or reduced.

## Clock gauge and correlations

Each shared fit fixes the mean of the 21 remaining satellite coefficients to
zero. The unseen pseudo-target's constant offset cannot be learned. Consequently
the raw shared residual includes this explicit clock convention; its pooled
mean of −0.073103 m is not evidence of an absolute clock bias. Likewise, the
near-zero pooled mean of the zero alternative follows the leave-one-out algebra
and does not establish unbiased absolute measurements.

Removing the across-station mean separately for each pseudo-target/epoch gives
RMS **0.845685 → 0.838392 m**, a **0.8623%** change on the same 3761 values in
1076 blocks with at least two receivers. Another 181 evaluated values cannot
support this spatial contrast. This is a descriptive projection, not a fitted
correction or a complete covariance model; it also removes any real common mode.

Exact-time Pearson pairs are retained individually, including insufficient
sample and zero-variance outcomes. At least ten pairs are required to report a
coefficient; this threshold is not a significance test. With zero correction:

| Separation | Supported links | Median correlation | Range |
|---|---:|---:|---:|
| 30 s | 71 | 0.1214 | −0.4602 to 0.9773 |
| 60 s | 71 | −0.0400 | −0.4266 to 0.9320 |
| 150 s | 68 | 0.0286 | −0.3646 to 0.7609 |
| 300 s | 67 | −0.0096 | −0.7834 to 0.5187 |

The 118 supported simultaneous receiver pairs have median −0.0096 and range
−0.5409 to 0.4034; shared correction gives median −0.0091 and range −0.5409
to 0.4233. These short, overlapping series share calibration references and
products. Small median correlation does not justify independent errors, and
strong individual correlations cannot be attributed to one physical source.

As a numerical control, exact zero-correction recalibration differs from the
simple leave-one-out transformation of baseline centered residuals by at most
0.000002113 m in this cohort. That agreement validates the approximation here;
the exact recalculation, rather than the approximation, generated the report.

## Reproduction and tests

```console
python -m research.exploratory.pseudotarget_checked_v2 NEW_OUTPUT.json
```

The output must not exist. The checked entry point binds plan and executed
sources. The original wrapper remains frozen; review identified that it used
the hash-helper module before the nested input chain checked that helper.
Wrapper v2, frozen at `1ec9ee8`, checks the helper bytes with standard-library
SHA-256 before importing the analysis. Numerical sources and the original
report are unchanged; this strengthens subsequent replay validation without
claiming a retroactive independent bootstrap check.
The existing admitted-input chain checks observations, coordinates,
reference products and model sources, including its recorded line-ending
compatibility. The complete report is `results/pseudotarget_v1.json`, SHA-256
`d12c3d1b57520569b39c9faacb1c0089065f229d60ad87fa709806201f50c823`.

Ten tests cover exclusion (including poisoned training pseudo-target codes),
nonlinear closure and correction sign, failures and disconnected training,
exact-time statistics, complete report/statistics replay, actual nonlinear
sample recalibration at every receiver, and frozen source/wrapper integrity.
CI replays the complete stored statistics and a numerical sample; a full raw
22-fold regeneration is available through the command above, not claimed as
part of every CI run.

## Decision and next measurement

Keep zero correction as the development baseline and shared correction as an
experimental alternative. The small, mixed benefit does not justify promoting
it or shrinking the 20 m production floor. S2 remains open.

Next isolate a named differential observable using **reference-only dual-frequency
code minus carrier phase**, with signal pairing, header transforms, continuity
and slips checked explicitly. Its constant ambiguity must be handled using
training data, not absorbed using the test interval. This can distinguish
code-versus-phase noise/multipath behavior from range and clock terms that cancel
in the combination; it does not by itself separate every hardware/media term
or bound modes common to both observables. Reuse the exposed cohort where
available, retain unsupported cases, and exclude G12 as text before parsing any
additional observations. Do not repeat pooled RMS optimization or start S3
from this diagnostic alone.
