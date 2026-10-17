# Geometry-free continuity through clock calibration and RF trajectories

## Intervention and physical meaning

The network-clock study reduced formal orbit covariance while worsening
position discrepancies in several folds. A concrete violated assumption was
already observable: BRAZ/G13 changes geometry-free phase by -.425056 m at
38040 GPST and -.202117 m at 38070, with both LLI fields zero. A scalar clock
common to both frequencies cannot alone cause this combination to change.
Retaining one constant phase ambiguity across such behavior can transfer a
link error into the receiver clocks and then into the candidate trajectory.

This increment implements **free phase boundaries**, propagating their loss
of information through the existing network calibrator and dynamic solver.
It does not subtract a guessed jump, fix integers, or identify the disturbance
as a cycle slip. The same physical intervention is applied on reference links
and on the candidate's already admitted training increments.

The exploratory witness follows the
[ESA geometry-free example](https://gssc.esa.int/navipedia/index.php?title=Detector_based_in_carrier_phase_data:_The_geometry-free_combination):
use a quadratic predictor from ten previous samples and threshold
`1.5*(lambda2-lambda1)*(1-.5*exp(-dt/60))`. During initial/restarted history this
implementation uses a first difference. Thresholds are 56.348 mm at 30 s and
65.999 mm at 60 s. A detection resets history. Original flag, mask and gap
boundaries remain. A 60 s hole is allowed only within an otherwise existing
segment, notably when a link sample is withheld. These example settings are
not a calibrated detector/noise model; ionosphere can trigger a boundary and
some phase jumps remain invisible. No setting is chosen from CODE errors.

## Executable paths and covariance

`reference_network_clocks.py --continuity OUTPUT` reuses the 22-fold preparation
and compares all three variants: original constant-bias network, GF-segmented
network, and GF-segmented network with free link-linear phase/code drift.
The unsegmented/free-drift variant remains in the previous immutable receipt;
it is also compared where relevant below. No variant becomes a production
correction merely because a residual decreases.

On each reference, a witnessed boundary creates another unpenalized float
phase ambiguity. Code remains observed. Clock levels, observation-time
geometry and the joint clock covariance are recalculated, including shared
ambiguities, station/epoch dependencies and cross-arc covariance. The candidate
and all its products are excluded from its network before arithmetic; G12
products remain unopened. References stop at the last target training endpoint.

For the candidate, only epochs present in the original training arcs enter
the witness. Internal holdout and future RF do not supply extra history.
The short three-endpoint arcs consequently use the first-difference warmup
rule. An increment crossing a boundary receives a completely free unknown
jump, algebraically equivalent to dropping that increment. Every code remains
observed. The dynamic solver takes the **principal submatrix** of the retained
observations' covariance, including the full cross-arc covariance: it must not
condition a neighboring increment on the rejected one's correlated noise.
The synthetic regression verifies both the GLS equivalence and trajectory
recovery despite a huge arbitrary value in the discarded increment.

Every seventh network link-epoch is withheld as before. Its GF value cannot
select its own phase ambiguity: segmentation is rebuilt from the retained
rows only. Neighbors on opposite sides of a boundary leave that excluded
epoch's phase segment unsupported, while its code may still be predicted.
This is a **conditional link diagnostic**: rows are linearized at the full
network's timing solution and use the original admitted mask. It is not an
observation-independent replay of nonlinear timing/mask preparation. Target
RF forecasting has a separate boundary: all candidate trajectories, covariance
and predictions are fixed before scoring; no excluded target phase or code
enters its own mask, calibration or fit. Neither diagnostic is new blindness
on this already exposed archive.

Endpoint weights remain code sigma 20 m and phase sigma .02 m, with unchanged
ground/dynamic assumptions. New formal covariance is conditional on the
chosen boundaries and these weights. It omits uncertainty about which
boundaries are physically correct and does not establish a finite total
physical budget, absolute clock datum or independent coverage.

## Execution and preserved evidence

The numerical producer is `f132da4a94822562c95cc8c15f29007e057b024d`.
New results use `results/reference_phase_continuity_v1.json.gz`; the previous
network receipt and both held-out support corrections remain byte-for-byte
unchanged. Git ancestry retains the #225/#226 merges and the complete #227
producer chain. Replay tests check source/input hashes, all candidate/window
terminals, raw witnesses, covariance and RF prediction hashes/scoring.

Result SHA-256:
`bcbac22d75371b372fa45e1c5b3ce8fca2aa91c316142a787a5af869cf75cd62`
(9,949,211 gzip bytes). Reproduce with Python 3.13 and the repository requirements:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --continuity NEW_OUTPUT.json.gz
```

## Results and contrary outcomes

All 22 candidates, 440 preparation windows and the original 63 arcs remain.
Five trajectories fit in every variant; 17 candidates still lack sufficient
prepared arcs. Every fit reports `BRANCH_SEARCH_INCOMPLETE`: four candidates
retain one failed interior-Earth initialization; G19 retains **two** in this
execution, including its freshly refitted unsegmented baseline. Snapshot
numerical root counts can vary; none of these failed seeds is a competing
physical orbit or a proof of global uniqueness. The old receipt's counts
remain unchanged. Successful unsegmented estimates reproduce the prior run.

The raw full archive has 15 witnesses in 7,568 available rows before the
study's time/elevation/gap admission. Actual calibration retains **five unique
link transitions**, reused 19 times across the five overlapping folds:
BOGT/G06 36690, BRAZ/G21 37500, BRAZ/G13 38040 and 38070, DRAO/G31 39450 GPST.
Fold counts for G05/G11/G19/G20/G21 are 5/5/1/5/3. Boundaries are determined
without CODE. On the candidates' actual prepared training samples the warmup
witness rejects **zero of 680 increments**; all 1,020 candidate code samples
also remain. Thus this archive's trajectory changes come entirely through
reference recalibration. The target masking path is exercised synthetically.

Maximum reference phase residuals fall from .272–.406 m to .044–.048 m with
constant segmented biases. Training interval mean-clock values move by up to
.816–1.654 mm/s by fold, while formal orbit axes barely change. These are
model differences, not a measured clock error or a qualified error component.

In each triple below the order is **unsegmented constant / GF constant /
GF free drift**. CODE remains a shared-upstream diagnostic, not independent
truth. The 126 state rows derive from five trajectories; only one epoch per
trajectory is beyond all training.

| Candidate | Position RMS, m | Velocity RMS, mm/s | Largest conditional position 1-sigma, m |
|---|---:|---:|---:|
| G05 | 158.42 / 155.98 / 134.52 | 12.568 / 13.034 / 10.741 | 44.24 / 44.24 / 130.03 |
| G11 | 231.96 / 93.53 / 187.91 | 3.138 / 11.898 / 24.022 | 213.95 / 214.01 / 275.22 |
| G19 | 50.16 / 87.99 / 57.86 | 23.866 / 26.549 / 20.443 | 366.27 / 366.27 / 733.32 |
| G20 | 122.41 / 18.30 / 65.43 | 21.183 / 17.006 / 21.408 | 200.04 / 200.06 / 250.07 |
| G21 | 251.71 / 242.37 / 171.70 | 26.102 / 25.468 / 22.869 | 68.46 / 68.46 / 149.38 |

GF segmentation with constant biases improves position discrepancies in four
of five trajectories but worsens **G19**. Velocity worsens in G05, G11 and
G19. Relaxing phase/code drift still matters. Against the **previous
unsegmented free-drift** result, GF/free drift improves position only in
G11/G20; it worsens G05 (126.63 to 134.52 m), G19 (28.90 to 57.86 m), and G21
(168.20 to 171.70 m). No stability variant is selected using these scores.

| Candidate | Position discrepancy at its one genuinely future epoch, m |
|---|---:|
| G05 | 153.55 / 152.00 / 130.66 |
| G11 | 233.04 / 90.26 / 185.88 |
| G19 | 48.91 / 81.11 / 50.26 |
| G20 | 114.84 / 13.10 / 64.23 |
| G21 | 257.00 / 248.20 / 176.50 |

Nominal conditional 95% position ellipsoids include 54/126 CODE rows and
3/5 genuinely future positions in **every** variant. Joint state inclusion
is 31/34/54 of 126, and 1/0/3 of the five future epochs. These correlated
checks are not a coverage estimate and do not qualify the physical budget.

| RF comparison | Evaluated receiver pairs | Code RMS, m | Phase-rate RMS, mm/s |
|---|---:|---:|---:|
| All holdouts, including genuine future | 339 + 1 unavailable | .71023 / .71177 / .71259 | 8.5250 / 8.5708 / 8.5604 |
| Beyond all training | 26 | .88764 / .90361 / .89385 | 6.8972 / 7.8139 / 7.7252 |

Both segmented variants worsen **both genuinely future RF aggregates**.
Relative to constant unsegmented clocks, code worsens in 170/339 and 182/339
pairs, phase in 161/339 and 143/339. Among the 26 genuinely future pairs,
code worsens in 17/26 and 15/26, phase in 20/26 and 19/26. The previous
unsegmented free-drift forecasts were .88704 m and 6.9303 mm/s; the segmented
free-drift forecasts worsen those aggregates too. Better reference training
residuals and several better CODE positions therefore do **not** justify
promoting either variant to a physical correction.

### Network excluded-phase support

Code keeps 3,045 evaluated and 544 unsupported rows out of 3,589 in every
variant. Phase evaluates 3,045 / 2,643 / 2,639 rows. Segmented variants retain
**402 additional unsupported phase rows** whose ambiguity cannot be assigned
from nearby retained training data; these are not 402 observed slips. Free
drift adds four unidentified slopes. All remain in the denominator. Folds
reuse observations/products and are not independent replications.

To separate a support change from prediction quality, the following RMS uses
only the **2,639 phase rows supported by all three variants**:

| Candidate | Common rows | Phase prediction RMS, mm |
|---|---:|---:|
| G05 | 594 | 22.66 / 15.92 / 11.31 |
| G11 | 635 | 23.56 / 16.76 / 10.75 |
| G19 | 269 | 14.42 / 12.82 / **588.85** |
| G20 | 640 | 31.91 / 17.90 / **36.97** |
| G21 | 501 | 29.58 / 15.39 / 10.44 |

The G19 free-drift maximum is **7.875 m** and G20's is **.730 m**. Neither
GF segmentation nor a small training cost resolves weak short-segment slopes.
Conditional interpolation improves under constant biases on the common rows,
but the missing support, nonlinear preprocessing qualification above, free
drift failures and worsening future RF remain decisive limits.

## Verification

The 39 focused tests pass across dynamic fitting, the network, wet-response
regressions and the new continuity receipt. Checks cover full/marginal joint
covariance, recovery after an arbitrary discarded increment, reference-link
injection and recalibration, causal/flag/gap behavior, GF-null slips, candidate
and future poisoning, excluded-GF poisoning, scoring order, historical source
provenance and immutable result integrity. Relevant complete research
regressions and final Linux/Windows CI are recorded on
[PR #228](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/pull/228).
The implementation review of the producer completed without findings;
final revision review/status belongs to that PR, not a frozen receipt.

## What GF alone cannot establish

For GPS, simultaneous slips of 77/60 cycles give **zero GF change** but an
IF change of 14.652613 m. The test suite explicitly retains this blind mode.
The 9/7 combination gives only 3.172 mm GF change but 1.717545 m IF change,
also below this witness's threshold. Smooth temporal instrumental/attitude
effects and common code/phase terms are additional unqualified directions.
The [ESA multifrequency discussion](https://gssc.esa.int/navipedia/index.php/Examples_of_multi-frequency_Cycle-Slip_Detectors)
describes complementary combinations and their code-noise limitations.

A concrete additional observable is the Melbourne-Wubbena combination, in
metres, for raw code P1/P2 and carrier cycles L1/L2:

```text
MW = lambda_W*(L1-L2) - (f1*P1+f2*P2)/(f1+f2)
lambda_W = c/(f1-f2)
```

It changes by 14.652613 m for 77/60 and 1.723837 m for 9/7. Under the explicit
hypothetical assumption of equal independent single-band code endpoint noise
sigma_P, the noise of an adjacent MW difference is
`sqrt(2*(f1^2+f2^2))/(f1+f2)*sigma_P = 1.007669*sigma_P`, ignoring phase noise.
A six-sigma separation would require sigma_P below **2.424 m** for 77/60 and
**.285 m** for 9/7. These are information requirements, not measured noise or
detection probabilities. Temporal code multipath/bias and cross-frequency
correlation must be qualified; the inherited 20 m IF weighting does not supply
that qualification. Another correlated GNSS clock product is not that missing
observable.

For the two exposed BRAZ/G13 transitions above, the raw-field MW differences
are +.104568 m and -.708050 m. These are measured combinations, not estimated
integer corrections. Their code-noise/bias budget is unqualified and the two
combinations do not uniquely identify the disturbance's cause.

MW recombines the same raw RF; it is not an independent extra measurement.
Any joint IF/GF/MW fit must retain the covariance and rank of the four raw
code/phase channels. Its useful addition would be the currently unused
frequency-dependent code combination with a justified temporal bias model.
An equal metre change in both codes and both phase paths cancels from GF and
MW, so these witnesses alone still cannot bound a common clock-like term.

The next S2 investigation should combine the complementary raw observables
with receiver/reference shared-error shapes and qualified temporal code/phase
stability. It must retain GF-null and common-mode counterexamples and carry
any newly supported information through the same calibration/trajectory
paths. Segmentation by itself cannot qualify wind-up, absolute code bias,
reference/ground/propagation/dynamic errors or the total physical uncertainty.
S2 remains open; no S3 campaign is started.
