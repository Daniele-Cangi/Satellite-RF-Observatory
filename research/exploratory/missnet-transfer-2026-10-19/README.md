# Assisted observed-coordinate predictive transfer — 19 October 2026

Preparation for one exploratory native test on already exposed real RF rows.
This follows RepoTraction #132 (including its recorded PyKalman selection
violation); MissNet in ImputeGAP is an eligible code reference. It is an
operator-assisted transfer, not an autonomous Discover or blocked-agent result.

## Fixed mechanism and comparison

Use the exact stable differential input at SHA-256
`56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020`, with the same
five folds G05/G11/G19/G20/G21 and original hash-selected last-third held links.
No acquisition, paid model call, candidate orbital state, CODE score or G12 read.

Reuse the native wet-source prediction, including its unchanged original raw
weights, source null test, prefix ambiguity and native scorer. Fit one rank-one
phase-residual model on the final prefix continuity segment of each channel,
using 20 observed-entry ALS iterations, at least eight observations/channel,
AR(1) prefix moments with rho clipped to [-.98,.98], and prefix error variances.
The zero-filled SVD seed is only numerical initialization; missing coordinates
are never accepted as observed values or physically estimated source amplitudes.
A channel or model without sufficient support remains unsupported.

At each epoch select the observed residuals AND matching loading coordinates
before updating one shared latent state, following the operation in
[MissNet lines 195–217](https://github.com/eXascaleInfolab/ImputeGAP/blob/a18d5c5f619d05dced8348619150b4a06e138f8d/imputegap/wrapper/AlgoPython/MissNet/main.py#L195-L217).
Add its predicted residual to the native phase prediction; code predictions are
unchanged. Model variances are predictive assumptions, not qualified physical
covariance or new raw-error floors. Clustering, graphical lasso, EM, smoothing,
external checkpoints and additional dependencies are not imported.

The existing native clock calibration already handles available links. The new
candidate is the shared temporal residual model beyond those free epoch clocks,
not the invention of partial-observation linear algebra. No claim that an
external source was necessary, or that this is a novel algorithm, follows.

A fixed ablation uses identical fitted parameters but discards an entire epoch
if any coordinate is absent. It tests whether partial-coordinate information,
rather than merely a temporal prior, contributes. It is not another tuned model
and cannot replace a failed primary result. Gaps over 60 s reset the residual
state. An observed channel crossing its prefix GF segment is not assimilated.
The original unobserved held continuity hypothesis remains explicitly conditional.

The native calibration is fitted on ALL admitted observations, including later
other-link observations. Prefix residuals therefore condition on that admitted
calibration; this is not a wholly causal training-prefix forecast. Only the new
latent parameters use prefix residuals. Held RF, GF, MW, code and phase values
are excluded before segmentation, normalization, parameter fitting and updates.
All five folds' predictions are saved before held scoring. No held-score tuning,
source replacement, new query or second fitted configuration follows a failure.

`original-comparison.json` carries the original #131 comparison and exact common
pair keys, derived before this test from its conserved five direct methods. Its
original comparison SHA and commit are retained. Do not intersect the denominator
with successful new predictions: missing keys remain explicit failed coverage.
Retain 1,248 short-lag and 874 long-lag pairs. Primary success is at least 10%
lower pooled 300 s phase RMS than the wet baseline; both code RMS values and
30 s phase RMS must be within 2% of the metric-wise best original direct method.
At least four of five folds must improve primary phase RMS, with none over 10%
worse. Every fold, terminal, missing prediction and worsening is retained.
The wet baseline replay must reproduce its original metrics to numerical
tolerance before any gain can be credited. The comparison file's Git bytes are
preserved across Windows/Linux text checkouts.

These are the previously exposed #131 exploratory comparison criteria, not a new
independent practical necessity, prospective threshold or significance test. A
positive outcome would show predictive usefulness on this conditional benchmark;
it would not demonstrate orbital accuracy, physical attribution, qualified
uncertainty, S2 completion, autonomy or a blocked development agent being helped.

## Reproduction

After RepoTraction #132 review corrections and relevant local regressions, run:

```text
python -m research.exploratory.masked_prediction_study --comparison research/exploratory/missnet-transfer-2026-10-19/original-comparison.json --output data/missnet-transfer-2026-10-19
```

The output directory must be new. The computation uses ordinary source control,
the existing native preparation/scorer and gzip JSON reports, with no new runner
or audit infrastructure. Unit tests cover available-coordinate information,
shared-mode transfer, held-value poisoning and missing comparison support.
Native outcome is negative; see [RESULTS.md](RESULTS.md). Relevant regressions and Linux/Windows CI are required
before integration. Historical files and production paths remain unchanged.

Execution-sequence correction before the first native calculation (20 October,
Europe/Rome): the original preparation unnecessarily placed this unpaid local
exploratory calculation after all documentation CI. Both review corrections are
resolved and relevant local tests pass; the calculation may proceed while the
remaining Windows job runs. Full applicable CI is still required before merge.
No model, parameter rule, input, holdout, scoring or acceptance criterion changes.
