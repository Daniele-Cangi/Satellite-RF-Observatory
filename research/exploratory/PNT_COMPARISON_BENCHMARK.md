# Development comparison: local geometry and external witnesses

The reusable `python -m pnt compare` command tests a specific implementation
question: whether external residuals make controlled local code changes more
distinguishable from the original recording's variation. It operates on the
same previously exposed NYA2/TRO1/KIRU observations and NOAA broadcast NAV as
the [fixed-site exercise](PNT_FIXED_SITE_ANALYSIS.md). No new source, physical
attack, independently surveyed position or independent clock is obtained.

The [complete JSON report, stored with standard gzip compression]
(results/pnt_comparison_2024255_v1.json.gz) retains original source hashes,
parameters, fitted baselines, thresholds, scores and every original/challenge
epoch, including exclusions. Original input files remain external. Git history
and the recorded inputs reproduce this exercise without an additional seal
or experiment executor.

## Method and exposure

The chosen development window is 08:00–09:30 GPST on 2024-09-11, split into
three consecutive 30-minute windows: baseline fitting, threshold calibration
and evaluation. Each has 60 requested and eligible epochs. Selection is for
development on an exposed corpus, not observation-blind confirmation or a
certified benign sample. No parameter or threshold was retuned after this run.

The score uses all trained satellite pairs: the maximum absolute innovation
relative to their training medians. Local, mean external and local-minus-
external scores use identical satellites and qualified pairs. A separate
channel retains between-reference disagreement. Each threshold is the 95th
percentile nearest-rank score from the calibration window, with strict `>`
exceedance. Five training samples per pair and 20 calibration epochs are
minimum development support rules, not a scientific uncertainty budget.

Five ramp families have requested endpoints of 2, 5 and 10 m. Code changes
enter C1C/C2W before propagation/clock fitting. Geometry displacement uses
ECEF +X and the existing range model with zero nuisance clock for the change.
The training-only support rule chooses G02; the external fault affects KIRU,
the first reference name alphabetically. G02 leaves matched support in the
last 14 evaluation epochs. Single-satellite ramps therefore have **46/60**
eligible epochs and a largest evaluated shift of 7.63 m for the requested
10 m endpoint; geometry and common-clock ramps have 60/60. The unsupported
epochs are inconclusive, not silently removed or counted as missed attacks.

PR #173 review identified a missing support check: an observed satellite can
have no trained pair in the score. G04 is matched in all 60 evaluation epochs
here but has no trained pair. Single-satellite ramps now require at least one
qualified pair containing the perturbed satellite at that epoch, including
when trained partners disappear. The G04 counterexample becomes 60 retained
inconclusive epochs per satellite-ramp family; baselines and thresholds are
unchanged. The published default G02 report still reproduces byte for byte.

## Result

| Channel | Threshold (m) | Calibration exceedances / 60 | Original evaluation exceedances / 60 |
|---|---:|---:|---:|
| Local geometry | 2.85 | 3 | 6 |
| Mean external geometry | 2.57 | 3 | 19 |
| Local minus external | 3.84 | 3 | 9 |
| Between-reference disagreement | 5.28 | 3 | 3 |

Identical calibration exceedance counts do **not** imply identical evaluation
behavior: the combined method already exceeds its threshold more often than
the local method on the original evaluation recording. Those recordings lack
independent benign labels, so these are original-data exceedances, not measured
false-alarm rates. Adjacent epochs and pair scores are correlated.

Selected ramp responses are shown below; the full report retains all 15 cases.
The count is threshold exceedances, including those already present in the
original recording. New exceedances and first-new-exceedance delays relative
to the original are also retained in the JSON; a count is not attack recall.

| Ramp, requested endpoint | Eligible / requested | Local exceedances | Combined exceedances | Diagnostic implication |
|---|---:|---:|---:|---|
| Local satellite, 2 m | 46/60 | 15 | 10 | Combined is less sensitive for this perturbation |
| Local satellite, 10 m | 46/60 | 39 | 28 | Larger change still does not give a combined benefit |
| Geometry displacement, 5 m | 60/60 | 40 | 40 | Counts equal while original exceedance counts differ |
| Geometry displacement, 10 m | 60/60 | 50 | 48 | Local channel also responds strongly |
| Shared satellite, 10 m | 46/60 | 39 | 9 | Combined adds no exceedance beyond its original nine |
| One external satellite, 10 m | 46/60 | 6 | 24 | Faulty reference can contaminate the combined channel |
| Common local clock, 10 m | 60/60 | 6 | 9 | No new geometry exceedances; fitted clock changes by about 10 m |

The external fault also causes 24 reference-disagreement exceedances, including
21 new ones. This provides a warning about the comparison's references, not
attribution of a cyber incident. The shared perturbation's cancellation is
useful for diagnosing common/model effects under this assumed perturbation;
it is also a blind mode if a harmful manipulation preserves that contrast.

**Decision:** this implementation still does not demonstrate an incremental
RF detection benefit or equal-false-alarm advantage. The straightforward
mean-reference correction is not justified as a superior detector by this
corpus. The reusable comparison now exposes thresholds, changing support,
reference contamination and worsening cases rather than hiding them in an
aggregate alert count. Do not tune this exercise into a positive result.

P2's stronger claim still needs a suitable documented benign/challenge
recording with contemporaneous references and justified local truth. A new
physical mechanism or better reference topology must have a concrete reason
to improve the comparison; repeating wrappers or the same obvious attack is
not the next scientific contribution.

## Reproduce

Use the four exact original files identified by the report and the earlier
fixed-site exercise. At the repository revision containing this report:

```console
python -m pnt compare 2024-09-11 NYA200NOR_R_20242550000_01D_30S_MO.crx.gz brdc2550.24n.gz --reference TRO1=TRO100NOR_S_20242550000_01D_30S_MO.crx.gz --reference KIRU=KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz --start 28800 --train-stop 30600 --calibration-stop 32400 --stop 34200 --output NEW_COMPARISON.json
```

The stored `.json.gz` is ordinary gzip-compressed JSON; decompress it to compare
against the CLI output. Repeated execution produced identical uncompressed
report bytes. The original fixed-site and TEXBAT/JammerTest outcomes remain
unchanged. This is a development benchmark, not prospective confirmation.
