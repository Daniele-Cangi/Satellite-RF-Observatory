# Native result: no benefit from this fixed residual model

Execution completed on 20 October 2026 (Europe/Rome), on the already exposed real
RF archive and the original five-fold comparison support. This is an assisted,
exploratory transfer of a code mechanism, not a prospective experiment, autonomous
Discover result, full MissNet implementation or blocked-agent demonstration.

**The primary model fails the unchanged success criteria.** It worsens pooled
300-second phase RMS by 1.819%, improves only two of five folds and does not reach
the required 10% pooled improvement. The model and thresholds were not retuned.
No source replacement, second configuration, paid call or new acquisition followed.

## Same-pair native comparison

| Method | 30 s phase RMS, mm | 300 s phase RMS, mm | 30 s code RMS, m | 300 s code RMS, m |
| --- | ---: | ---: | ---: | ---: |
| Original wet baseline replay | 9.310372 | 14.567306 | 1.283933 | 1.333436 |
| Observed-coordinate residual state | 9.320806 | 14.832256 | 1.283933 | 1.333436 |
| Whole-row ablation, same fitted parameters | 9.309239 | 14.549138 | 1.283933 | 1.333436 |

All methods retain all **1,248** original short-lag and **874** long-lag increment
pairs, with zero missing keys. The original wet baseline reproduces the conserved
#131 metrics within the fixed numerical replay tolerance. Native code predictions
are identical; only phase residual corrections differ. The primary short-lag
phase RMS worsens by about 0.112%, within its inherited secondary tolerance.

| Fold | Long-lag pairs | Baseline phase RMS, mm | Observed-coordinate phase RMS, mm | Relative change |
| --- | ---: | ---: | ---: | ---: |
| G05 | 203 | 15.852183 | 16.085513 | +1.472% |
| G11 | 174 | 13.042516 | 13.152090 | +0.840% |
| G19 | 38 | 16.760588 | 16.358601 | -2.398% |
| G20 | 261 | 14.692259 | 15.406601 | +4.862% |
| G21 | 198 | 13.824760 | 13.768012 | -0.410% |

All secondary code/short-phase tolerances pass and no fold worsens by over 10%.
The failed primary improvement and four-of-five requirements still make the
overall outcome **failed**, not a qualified link or partial threshold pass.
Folds share observations and are not five independent replications.

## What the ablation establishes

The learned models have 56/57/51/57/53 eligible channels for G05/G11/G19/G20/G21.
The observed-coordinate variant updates from available coordinates at every
117/117/45/117/93 epoch respectively. The whole-row ablation updates at 0/0/23/0/0
epochs: the first, second, fourth and fifth folds never have a completely observed
eligible-channel vector. Thus that ablation is mostly a no-assimilation control,
not a competitive alternative missing-data estimator. Its small pooled improvement
is concentrated in G19. It must not be oversold as evidence that ignoring data
is generally better.

For this exact model and dataset, adding partial-coordinate assimilation does
not improve the native result over the original baseline or that fixed ablation.
This does not identify the cause. Nonstationarity, low-rank misspecification,
residual construction and learned noise/transition assumptions are possible
explanations, not measured diagnoses. No weights, rank, process law or model
selection search was conducted after observing these outcomes.

The code mechanism was real and could be adapted. Pertinent source code alone
was insufficient to supply a beneficial predictive model. This rejects this
fixed adaptation on this comparison; it does not show that every MissNet model,
state-space strategy or cross-domain transfer would fail. The existing native
calibration already used available reference links: the new tested hypothesis
was additional shared temporal residual structure, not missing-value support
by itself. This experiment also cannot establish that an external suggestion
was necessary for an agent to construct the same model.

## Execution, checks and retained evidence

One native calculation took **20.877 s** on Windows with one BLAS thread. All
five models were fitted and predictions saved before the native held-data scorer
ran. There were no missing predictions on the fixed comparison supports. The
whole historical archive was already exposed/decoded: no new value-blind or
prospective-access claim is made. Estimation functions exclude held numeric
values before fitting; synthetic poisoning regressions cover that boundary.

Executed implementation revision: `de6c83150c616a323ead6fad722947b0493bedb7`.
`predictions-before-scoring.json.gz` retains the models, all baseline/new/ablation
prediction terminals and executed source hashes; `native-scores.json.gz` retains
all native scores, including errors outside the comparison's common support.
`summary.json` retains every per-fold/common-support metric and criterion.
`original-comparison.json` preserves the original comparator values and pair keys.
Source hashes match the two executed Git blobs, and the comparison-input hash
matches its preserved bytes. No executed source changed after the held scores.

Before execution: the 18-test focused regression run passed; after the optimized
Python input-check correction, all six new tests passed (see `focused-tests.xml`).
Those runs overlap and are not additive. Review on the executed source revision
completed without findings. The calculation began while the final Windows/Python
3.10 documentation-CI job for RepoTraction #132 was still running; the sequence
correction was recorded before native calculation. No merge bypassed CI.

Original RF rows, physical source model, raw weights, masks, historical results
and production calibration paths are unchanged. No candidate orbital products
were supplied to the estimator, no new orbital fit/CODE score or G12 state
analysis occurred. S2, physical covariance, source attribution, practical need
and autonomous Discover contribution remain unproven. Retain this negative result
and stop this configuration rather than starting a search for passing weights.
