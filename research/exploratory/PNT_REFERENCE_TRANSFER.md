# Can external residuals predict later local variation?

The previous [software-ramp comparison](PNT_COMPARISON_BENCHMARK.md) did not
demonstrate an advantage from subtracting the mean external geometry residual.
This exercise tests the prerequisite more directly: does the same external
mean predict a component of later local residual variation, even when its
amplitude is learned rather than assumed equal?

The reusable `python -m pnt transfer` command uses the same exposed
NYA2/TRO1/KIRU GPS C1C/C2W recordings and broadcast navigation file. It adds no
RF challenge, benign certification, independent survey or clock witness.
The [complete compressed JSON](results/pnt_reference_transfer_2024255_v1.json.gz)
retains all six runs, input hashes, fits, support, pair innovations/errors,
original diagnostics and requested epochs. Git history and the original
sources reproduce the exercise without an additional executor or seal.

## Method and exposure

Each run learns pair-specific local/external median baselines from training.
Using only pairs with at least five training epochs, it fits one slope `b`
between centered local innovation `u` and mean external innovation `v`:

```text
b = sum_training_epochs(mean_qualified_pairs(u * v))
    / sum_training_epochs(mean_qualified_pairs(v * v))
```

The intercept is zero after the training median subtraction. There is no
coefficient clipping, noise-floor assumption, regularization, reference
selection or subsequent adaptation. Each eligible training epoch has equal
weight regardless of its pair count; at least six qualified pairs per epoch
and 20 eligible training epochs are required. These are development support
rules, not an uncertainty model. Zero external training variation or
insufficient support produces an explicit inconclusive result without fallback.

Later epochs compare `u`, `u-v` and `u-b*v` on identical qualified pairs and
epoch support. The unit correction uses the separate local/external training
medians; it does not replace `compare`'s independently median-centered combined
score or its thresholds. The main metric is the square root of the mean over epochs of
each epoch's mean squared pair error. This avoids treating every pair as an
independent incident and stops epochs with more pairs receiving greater total
weight. It does not remove correlation, geometry changes or selection effects.
Per-epoch maxima, improved/worsened counts and summaries by scored-pair count
remain available. A pair absent from training does not enter any method's score.

Two disjoint development windows on 2024-09-11 are retained, without selecting
one after viewing the result:

| Window (GPST) | Training | Later evaluation |
|---|---|---|
| A | 08:00–08:30 | 08:30–09:30 |
| B | 09:30–10:00 | 10:00–11:00 |

In each window all three receivers take the local role, with the other two
as references. Every run obtains 60/60 eligible training and 120/120 eligible
evaluation epochs. The 08:00–09:30 observations overlap the earlier comparison;
these are exposed development data, not a new independent confirmation sample.
Rotations share physical recordings and the common navigation product. The
two windows and six runs are not six independent incidents.

## Result

Positive MSE reduction means a smaller residual than no correction. Negative
values mean worsening. RMS is in metres of pair-residual innovation, not
position error. Counts refer to epochs within a run, not independent events.

| Window | Local | Learned b | Local RMS | Unit-transfer RMS | Learned-transfer RMS | Learned MSE reduction | Worsened epochs / 120 |
|---|---|---:|---:|---:|---:|---:|---:|
| A | KIRU | 0.1222 | 1.6230 | 1.6503 | 1.6048 | +2.24% | 44 |
| A | NYA2 | -0.0330 | 0.9226 | 1.3599 | 0.9272 | -1.00% | 75 |
| A | TRO1 | 0.0357 | 1.2311 | 1.4228 | 1.2253 | +0.93% | 46 |
| B | KIRU | 0.1338 | 1.5319 | 1.6764 | 1.5310 | +0.12% | 59 |
| B | NYA2 | -0.0222 | 0.9347 | 1.3808 | 0.9351 | -0.10% | 58 |
| B | TRO1 | 0.0853 | 1.2334 | 1.5569 | 1.2381 | -0.76% | 67 |

Unit subtraction worsens all six held-out comparisons. The learned slopes
are small, ranging from -0.0330 to 0.1338, and learned transfer improves three
comparisons while worsening three. Even the largest aggregate improvement
includes 44 worsened evaluation epochs. Cardinality strata also include
worsenings in comparisons with an aggregate improvement. No statistical
significance, uncertainty interval or general population guarantee is inferred
from these correlated exposed observations.

**Decision:** this shared-mean, one-slope model does not show a consistent useful
transfer advantage on this topology. Do not promote it to a detector, and do
not search more regressions on these windows to manufacture a positive result.
The reusable command now measures a physical prerequisite instead of repeating
synthetic attacks that already trigger the local channel. A future extension
must motivate a distinct observable physical effect or a reference topology
that can measure it; it still needs the P2 matched benign/challenge evidence.
This result does not exclude other mechanisms or topologies.

## Claim boundaries

Local values are explicitly admitted in supervised training; this is not
target-independent calibration. A shared component can be a propagation or
model error, a shared instrumental effect or a harmful manipulation. Removing
it does not authenticate the local RF. Contaminated training can teach a
harmful correction. No classifier, detector threshold, equal-false-alarm
comparison, attack attribution or absolute-time verdict is delivered.

Coordinates remain RINEX approximate antenna declarations. GPS ionosphere-free
noise, model errors and the physical/provider/clock dependencies are unchanged
from [the fixed-site tool](../../pnt/README.md). The external mean is formed
from separate receiver fits but matched selection depends on all receivers.
No harmful component is claimed to be distinguishable merely because residuals
are smaller. Original benchmark and historical scientific outcomes are unchanged.

## Reproduce and checks

Use the four exact original sources from the earlier fixed-site exercise:

```console
python -m pnt transfer 2024-09-11 NYA200NOR_R_20242550000_01D_30S_MO.crx.gz brdc2550.24n.gz --reference TRO1=TRO100NOR_S_20242550000_01D_30S_MO.crx.gz --reference KIRU=KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz --start 28800 --train-stop 30600 --stop 34200 --output NEW_TRANSFER.json
```

Rotate each original file into the local argument, naming the other two
`NYA2`, `TRO1` or `KIRU` as applicable. Repeat with boundaries
`34200,36000,39600`. The stored JSON has an ordered `runs` array, window A
then B, each with local roles KIRU, NYA2 and TRO1. Each element's `report`
is the corresponding CLI JSON. The uncompressed aggregate report has SHA-256
`abf433bfd1cef75cb38f1c46fa91c29fab627ea3244a609747c54cbb642ffd8c`.

Regression tests cover a known shared component, local-only changes, a reversed
later relation, changing pair cardinality, untrained pairs, degenerate or
insufficient fits, evaluation poisoning, missing references and actual
parser/model/CLI execution with no overwrite. Existing Linux/Windows CI
already includes these tests. Source-provenance checks preserve historical
modules and evidence.
