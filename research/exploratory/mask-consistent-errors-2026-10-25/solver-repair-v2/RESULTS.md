# Numerical repair v2: complete support, insufficient predictive benefit

**The numerical obstruction is removed; the original scientific comparison still fails.**
The pooled 300 s phase RMS improves only 1.646%, below the required 10%.
Three of five folds improve; G20 and G21 worsen. No parameter/threshold search
or further predictive execution follows this result.

Producer: `5bb99767032d68174b2acdb726254b75991e79bf`.
All five predictions were saved before held scoring or comparator access (182.787 s).
The same input and comparator SHA-256 identities, executed-source hashes,
full native scores and every prediction are retained here. The original
baseline predictions are identical to the first execution, and all original
1,248 short-lag and 874 long-lag pairs are evaluated with zero missing keys.

## All original folds

| Fold | 300 s pairs | Baseline phase RMS, mm | Repaired phase RMS, mm | Change |
|---|---:|---:|---:|---:|
| G05 | 203 | 15.852183 | 15.671726 | -1.138% |
| G11 | 174 | 13.042516 | 12.644349 | -3.053% |
| G19 | 38 | 16.760588 | 12.451164 | -25.712% |
| G20 | 261 | 14.692259 | 14.795044 | +0.700% |
| G21 | 198 | 13.824760 | 13.982957 | +1.144% |

| Metric | Original wet baseline | Repaired model |
|---|---:|---:|
| 30 s code RMS, m | 1.283933 | 1.283939 |
| 30 s phase RMS, mm | 9.310372 | 9.259216 |
| 300 s code RMS, m | 1.333436 | 1.333261 |
| 300 s phase RMS, mm | 14.567306 | 14.327502 |

Complete support, original-baseline replay, all secondary 2% limits and
no fold more than 10% worse pass. The 10% primary benefit and at least four
improved folds fail; `passes_all=false`. The large G19 gain remains real on
its 38 pairs but cannot represent the other 836 long-lag pairs.

## Numerical certification

All prefix and all-admitted covariance images retain full rank. The largest
whitening identity infinity-norm defect is 1.193e-6, below the declared 1e-4
budget. Original-coordinate solve backward errors are below 6.42e-16;
process-conditioned whitened solve backward errors are below 2.86e-16.
Every value, limit, dimension, resolution and rank is retained in the prediction
artifact. These certify the implemented conditional numerical model only.

| Fold | Prefix rank / errors | All-admitted rank / errors | Fitted predictive zenith sigma, mm |
|---|---:|---:|---:|
| G05 | 1111 / 1111 | 2252 / 2252 | 3.917590 |
| G11 | 1163 / 1163 | 2383 / 2383 | 3.627567 |
| G19 | 465 / 465 | 960 / 960 | 23.302349 |
| G20 | 1163 / 1163 | 2266 / 2266 | 4.545304 |
| G21 | 875 / 875 | 1716 / 1716 | 4.156043 |

The variance is still fitted only on excluded prefix errors; later admitted
errors condition the final correction. These amplitudes are predictive fits,
not physical wet-delay measurements or calibrated uncertainty. No held values
enter a fit; the already-exposed full archive is decoded as before.

## Interpretation and next boundary

The first four refusals were numerical, not proof of missing physical data.
Once repaired, this particular fixed wet-process correction provides a small
pooled benefit with two worsening folds. It does not meet the stated advance
criterion. Do not promote it as a successful benchmark method or tune rank,
variance bounds or timescale against these same held scores.

This closes the bounded numerical investigation. It neither identifies all
physical sources nor resolves the independent orbit bias-position degeneracy.
S2, physical uncertainty and independent-data confirmation remain open. Further
scientific development needs a distinct physical question/information source,
rather than another administrative gate or parameter sweep on this benchmark.

The [first failure](../RESULTS.md), [unchanged-guard diagnosis](../COVARIANCE_DIAGNOSIS.md)
and [repair method fixed before execution](../SOLVER_REPAIR.md) remain distinct.
