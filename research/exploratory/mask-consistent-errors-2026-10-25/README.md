# Conditional RF correction from excluded prediction errors

One exposed-data development comparison following the G20 learning-target
diagnosis in #239. The original #238 transfer and its negative outcome remain
unchanged. This is a direct native alternative, not another external retrieval,
new measurement, prospective confirmation or candidate-orbit reconstruction.

The [first execution](RESULTS.md) fails full comparison support: G19 improves,
four folds are rejected by the covariance-image check. The original execution
and a separate scoring-only completeness correction are retained.

## Single model and information boundary

Reuse the stable RF archive at SHA-256
`56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020`.
Keep its five existing folds and native wet-source baseline, original endpoint
weights, fixed timing/geometry, source estimability tests and continuity law.
No candidate products, G12 state, new acquisition or paid model call is used.

The archive is already exposed and decoded; this is a numerical-use boundary,
not process-wide value blindness. The original outer hash-selected links are
removed in the last third before their numerical use by estimation or
segmentation. Seven inner groups use the same link hash
modulo seven. For each group, remove its whole code/phase/MW/GF rows after two
thirds of the outer prefix (four ninths of the full time span), refit the native
clock/float/wet model and predict those excluded rows. Only afterward read their
admitted phase labels to form the errors. Existing prefix ambiguity/continuity
is conditional; an absent reference clock or unsupported source functional
remains unavailable. Inner failures and every query identity/status are retained.

For an inner calibration K_g, its error operator is A_g=I_g-K_g; the queried
outer error instead uses the original outer calibration. Derivatives include
epoch clocks, global segment ambiguities and the fitted wet-source refits.
Transport the same admitted endpoint covariance through ALL these operators,
including cross-group, cross-time and outer-error cross-covariance. The covariance
of projected in-sample residuals is not substituted for that error covariance.
No diagonal-only update, scalar leverage approximation, ridge or arbitrary
completion of a missing clock is used.

The one extra predictive hypothesis is a zero-mean varying zenith wet path per
station, independent between stations, with exponential time correlation of
fixed 300 s scale. This is an explicit predictive assumption, not measured
weather covariance. The existing wet mappings affect IF code and phase together,
and each inner/outer error applies its own complete operator to that field.
Only one common process variance is estimated by marginal likelihood on the
excluded errors at or before the original prefix cut. A fitted variance zero
is retained explicitly; lack of a resolved process response is unsupported.
The broad log-variance interval [-32,20] and PSD relative image cut 1e-10 are
numerical rules, not physical floors. A parameter optimum at the upper limit
or values outside the retained covariance image fails explicitly.

The Gaussian correction conditions on all admitted error observations, including
other links after the prefix and later than a queried epoch. This is conditional
missing-link reconstruction, not a causal residual filter, whole-network future
forecast or proof of 300 s predictive persistence. The 300 s score is an increment
lag. Unlike #238's rank-one ALS process, the field basis here uses the existing
station wet mappings; no new spatial loadings, rank or timescale is searched.
This is one direct operator-aware model, not an isolated ablation of only one
line of the earlier learner. Its code and phase corrections are both retained.

## Unchanged comparison and failure rules

Retain the original 1,248 short-lag and 874 long-lag pairs and all five folds.
No intersection with the successful new outputs may shrink that denominator.
Replay the wet baseline (300 s phase RMS 14.567306 mm) to its original numerical
tolerance. Primary success remains at least 10% lower pooled 300 s phase RMS,
at least four improved folds and no fold more than 10% worse. Both code RMS
values and 30 s phase RMS must stay within 2% of the metric-wise best original
direct method. No new signed-product gate or changed threshold is introduced.

Save every fold's predictions before scoring any held observations or opening
the comparison metrics. Preserve all unsupported predictions, covariance/fit
failures and worsening cases. A failed model does not silently substitute the
wet baseline. No alternate process, hyperparameter configuration or held-score
tuning follows the native outcome. This exposed comparison can test usefulness
on the existing benchmark; it cannot prove population generalization, physical
covariance, complete source identification or S2 completion.

## Reproduction

The existing report command gains one option; no new executor or authority:

```console
python -m research.exploratory.masked_prediction_study --mask-consistent --comparison research/exploratory/missnet-transfer-2026-10-19/original-comparison.json --output data/mask-consistent-errors-2026-10-25
```

The output directory must be new. The existing source/input identities,
predictions-before-scoring artifact and native scorer bind the execution.
Tests check the complete response against a perturbed native refit, exact
Gaussian covariance transport with shared noise, covariance-image rejection,
prefix-only variance fitting, actual inner exclusion, poisoned outer RF and
failure without baseline fallback. Linux/Windows CI remains enabled unchanged.
