# Wide-lane uncertainty on causal reference arcs

This exploratory study uses the exposed reference extract and the causal
decision ledger from #244. It models scalar wide-lane double differences (DDs)
on the latest joint arc at the 10:30 GPST cut. Each 300 s block contains ten
30 s samples from the same four link arcs. The prediction file records the
prefix fit and forecasts before held scoring.

## Temporal uncertainty

Of 4,851 DD configurations, 4,572 lack a joint arc at the cut and 100 lack
two complete prefix blocks. The 179 fitted configurations each have six
scheduled held blocks. There are 829 scored blocks, 69 first blocks with lost
arc support and 176 scheduled blocks after that loss. The 11:00 endpoint lies
outside a complete held block.

The two fixed covariance shapes are IID and AR(1) with correlation 0.5 per
300 s. For prefix means y, each model uses GLS with constant mean and
covariance s^2 R, where R_ij = rho^|i-j|. The residual quadratic divided by
K-1 estimates s^2. The future prediction adds r' R^-1 (y - mean) to the GLS
mean, where r contains the correlations to the future block. Its variance
factor is 1 - r' R^-1 r + (1 - r' R^-1 1)^2 / (1' R^-1 1). Both the
prediction interval and the mean interval use K-1 Student degrees of freedom
under their respective Gaussian covariance assumptions. The correlation 0.5
is a sensitivity choice set before the run.

| Model | Inside nominal 95% | Observed coverage | Median 99% mean halfwidth |
|---|---:|---:|---:|
| IID | 765 / 829 | 92.28% | 0.224 cycles |
| AR(1), rho = 0.5 | 781 / 829 | 94.21% | 0.431 cycles |

On the same 829 blocks, the archived #243 predictions also cover 765. The 12
archived scored blocks that lose support in this replay all contain the causal
BRAZ/G05 break at 10:59:30 GPST and were outside the #243 interval. They are
retained as arc losses here. The counts share links, epochs and arc selection.
The observed proportions describe this replay. Physical coverage remains
unqualified under both models.

## Sensitivity to residual DD bias

For a float mean m, random-error halfwidth h and assumed absolute residual DD
bias bound B, the compatible integers lie in [m - h - B, m + h + B]. Here h
is the nominal 99% halfwidth for the prefix mean. The forecast coverage in the
table above concerns future block means. The following counts concern the
integer compatibility set under each assumed bias bound.

| Assumed B (wide-lane cycles) | IID singletons | AR(1) singletons | Same singleton in both |
|---|---:|---:|---:|
| 0 | 154 | 146 | 137 |
| 0.10 | 162 | 135 | 133 |
| 0.25 | 163 | 120 | 120 |
| 0.50 | 133 | 88 | 88 |

All columns use the 179 fitted configurations. An interval can gain a single
integer as it widens from an empty set. The prefix artifact records empty,
singleton and multiple sets for every scenario. A bound of 0.10 wide-lane
cycles corresponds to about 8.6 cm of effective DD bias.

A free constant residual DD bias remains confounded with the integer. Adding
an integer k to the ambiguity and subtracting k from the bias gives the same
measurements. The physical support is therefore unbounded in all 179
configurations. Narrow-lane uncertainty also remains open. A physical
wrong-fix rate needs calibrated bias bounds and independent validation with
trusted integer labels. As a sizing example, 299 independent issued fixes
with zero errors give a one-sided 95% binomial upper bound below 1%. That
example requires representative independent trials with known outcomes.
[GNSS ambiguity validation](https://repository.tudelft.nl/record/uuid%3A339741e7-5e53-4f6f-9417-4e6c94f00a51)
[Exact binomial confidence limits](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm)

## Reproduction

    python -m research.exploratory.real_phase --wide-lane-uncertainty --inputs research/exploratory/inputs/real_phase/observations_gps_only_v2.json --output data/wide-lane-uncertainty-2026-11-12

Use a fresh output directory. The archived [prefix predictions](predictions-before-scoring.json.gz)
bind the reference extract, causal ledger and producer ea80110e12b217acc65869c8c99de73b71364c86.
The [held scores](scores.json.gz) retain each scheduled outcome and the first
loss epoch and link. Forty-three focused tests passed.
