# First excluded-error comparison: incomplete numerical support

**This single variant does not pass the original comparison.** It produces a
correction for G19, but four folds stop at the covariance-image check. The G19
gain cannot be pooled as an improvement on the original 874 long-lag pairs.
No new configuration, rank cutoff, covariance floor or process timescale was
tried after this outcome. The earlier #238 negative transfer stays unchanged.

Executed prediction source: `12a427af47e773a91949a7b38a4524a5890d7300`.
One native execution took 116.527 s. All five prediction records were saved
before any held scoring or comparison-metric access. The same native wet
baseline reproduces all 1,248 short-lag and 874 long-lag pairs, with 300 s phase
RMS 14.567306 mm. No new candidate fit, CODE state score or G12 opening occurred.

## All original folds

| Fold | Required 300 s pairs | Baseline phase RMS, mm | New phase RMS, mm | New terminal |
|---|---:|---:|---:|---|
| G05 | 203 | 15.852183 | unavailable | covariance-image check |
| G11 | 174 | 13.042516 | unavailable | covariance-image check |
| G19 | 38 | 16.760588 | 12.451164 | conditional correction evaluated |
| G20 | 261 | 14.692259 | unavailable | covariance-image check |
| G21 | 198 | 13.824760 | unavailable | covariance-image check |

G19's phase RMS improves 25.71% on its 38 retained long-lag pairs. Its 30 s phase
RMS changes from 7.768967 to 7.498967 mm on 118 pairs. The corresponding code
RMS changes from 1.084346 to 1.084505 m (30 s) and .907318 to .906892 m (300 s).
The prefix-only likelihood gives a predictive zenith-process sigma of .023302 m,
with 465 prefix errors and 960 total admitted errors. It is not an independently
measured wet-path amplitude or a qualified physical covariance.

The other four terminals are exactly `prediction errors outside the covariance
image`. The current relative eigenvalue cut and range-consistency check reject
those fits; they do not establish that physical observations are insufficient,
that the Gaussian hypothesis is statistically refuted, or that adding hardware
is necessary. Distinguishing weak discarded directions from numerical error
requires a separate diagnosis of the retained implementation, not lowering the
cut until the held scores improve. No such follow-up was executed here.

All seven inner groups per fold retain their query identities and support
terminals. Missing prefix ambiguities and clocks are not replaced; the native
baseline still has its original outer prediction support. The new method
evaluates only 118/1,248 short-lag and 38/874 long-lag pairs, retaining 1,130 and
836 unavailable keys respectively. Its overall support/benefit criteria fail.
The one-fold gain is not a five-fold result or prospective confirmation.

## Adjacent reporting defect and scoring-only correction

The reused summary function already made `passes_all` false when support was
incomplete. However, it could still label `primary_10_percent` and `secondary`
true using the smaller successful subset. This execution exposed that defect:
the original `summary.json` records those flags, with `passes_all=false`.

Both metric criteria now require complete original support. The unchanged
predictions/native scores were summarized again, without calibration, model
fitting, parameter changes or another native experiment. The separate
`summary-complete-support.json` retains that scoring-only correction and its
source hash. Only original-baseline replay passes; the incomplete method gets
no primary or secondary pass. The first summary remains preserved verbatim.
An explicit partial-support regression prevents this misleading flag from
returning. This does not change any threshold or the original failed outcome.

## Evidence and next implication

The directory retains predictions before scoring, native scores, both summaries
and the 22-test pre-execution report. Prediction artifacts contain input and
executed-source hashes plus all inner/outer terminals. Git retains the exact
producer; historical replay need not pin active engineering to that version.
The regression re-scores the retained predictions on the original RF and checks
source ancestry/bytes, original support and the scoring-only correction.

This realizes an operator-aware direct alternative and preserves a concrete
numerical support failure. It does not validate Gemini's guarantee, demonstrate
that every source parameter must be recovered, or justify another broad search
for models. If this direction continues, the next bounded task is to diagnose
the numerical covariance image on one named failing fold while preserving this
outcome. S2, physical covariance and independent-data confirmation remain open.

The first PR CI attempt stopped before tests: `ubuntu-latest` selected Ubuntu
26.04, for which setup-python has no Python 3.13.5 x64 build. All five affected
workflows now explicitly use Ubuntu 24.04; the official Python version manifest
lists its 3.13.5 build. Python/dependency versions, test commands and Windows
coverage remain unchanged. This infrastructure repair does not rerun or alter
the native scientific comparison.
