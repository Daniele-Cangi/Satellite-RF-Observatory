# Temporal and receiver-shared RF covariance through reference calibration

## Intervention and information source

The joint IF/MW increment exposed an unresolved independence assumption:
raw code/phase errors were independent across epochs and links, even when a
receiver could supply the same disturbance to references and the candidate.
This increment propagates explicit temporal and receiver-shared raw-noise
hypotheses through the complete **fixed-weight reference estimator**, including
its fitted ambiguities, and into the candidate RF/clock data. The target fit
uses the resulting full covariance. No floor or raw marginal scale is reduced.

The new reference-only diagnostics use `D = IF_code - IF_phase` and MW.
These remove nondispersive geometry/clock and first-order ionosphere; changes
within the existing GF segments remove constant float bias levels. The
[ESA IF code/carrier equations](https://gssc.esa.int/navipedia/index.php/Code-Carrier_Divergence_Effect)
explain the cancellation. Code-minus-phase at a **single frequency** would
retain ionosphere and is not substituted here. The contrasts still contain
instrumental, multipath, carrier, attitude and admitted reference-bias
correction effects; they are not direct
measurements of pure raw-code noise. An equal metre error in all four raw
channels is invisible to both and remains an unqualified common direction.

Temporal correlation matters to averaging and uncertainty; an independent-
sample formula need not apply to an autocorrelated record, as discussed by
[NIST](https://www.nist.gov/publications/calculation-uncertainty-mean-autocorrelated-measurements?pub_id=151800).
Here the limited archive supports an internal shape diagnostic, not an
independent physical covariance qualification or a population confidence bound.

## Temporal fitting and excluded validation

For each candidate fold, only its admitted non-target reference rows up to
the last target training endpoint enter the diagnostics. The first two thirds
of reference times fit the shape; the last third is validation only. Pairs
crossing that split, a gap or a GF segment boundary do not enter either side.
The archive is already exposed; this is not new prospective blindness.

For `z=[D,MW]` the semivariogram is the mean of
`(z(t)-z(t-lag))(z(t)-z(t-lag))^T/2`, including any mean changes. Normalize each
channel's diagonal by its own 30 s value. A single effective code AR(1)
coefficient rho minimizes squared normalized-shape error at 30/60/90/120 s:
`V(k*30)/V(30) = 1+rho+...+rho^(k-1)`, with `0 <= rho <= .99`.
The 300 s lag is diagnostic only. Boundary fits are retained. Neither the
validation interval nor CODE errors selects rho or a passing replacement.
Observed amplitudes and mean changes are retained, but **never used to rescale
the historical 20 m IF-code/.02 m IF-phase marginal weights**.

This estimates an effective contrast shape. Assigning it to both raw code
bands is a sensitivity assumption; phase endpoints remain temporally white.
Bias trends can contribute to a variogram. Estimated-parameter uncertainty,
nonstationarity and uncertainty in GF segmentation are not propagated into
the local formal covariance. A good shape fit alone would not close the budget.

## Shared receiver diagnostic and covariance hypotheses

At each supported 30 s increment, divide the admitted reference identities
into alternating sorted groups. In each group fit free reference-common changes
and zero-mean receiver contrasts using a Helmert basis. Missing/disconnected
split graphs are unsupported, not repaired with an anchor. Time-center the
two receiver-contrast series separately, and retain their symmetric cross
moment. Disjoint-link noise assumptions are explicit; modes, overlapping
folds and time samples are not independent replications.

The cross moment may be indefinite or negative. It is **not projected into a
positive physical noise covariance**. No receiver-sharing fraction is inferred
from those moments. A fixed fraction f=.5 below is an explicitly unqualified
sensitivity allocation of the same raw marginal weighting variance.

For raw code bands the model covariance between two endpoints is

```text
C_raw[b,c] * rho^(abs(t-u)/30)
  * ((1-f)*I(same receiver AND same satellite) + f*I(same receiver)).
```

For raw phase bands the temporal factor is `I(t=u)`. Code/phase cross-noise is
zero as in the inherited raw scenario. Cross-frequency covariance is preserved
when supplied within each code/phase block. Different receivers are independent
at this raw-noise stage; calibration can subsequently correlate their clocks.
Marginal raw and IF endpoint covariance is unchanged for every rho and f.
Other shared product/ground/propagation errors and a common clock-like term are
not assigned a newly finite amplitude by this model.

Four variants use the same fixed constant biases, geometry, candidate support
and reference mean estimator:

1. `joint_independent`: unchanged IF/MW endpoint-independent baseline.
2. `temporal_code`: reference-informed code rho, independent links (f=0).
3. `temporal_shared`: the same rho, f=.5 for raw code and phase errors shared
   by a receiver across its references and the candidate.
4. `temporal_without_cross`: covariance ablation of (3), removing only the
   candidate-RF/reference-clock cross block. Both marginal blocks and their
   temporal/inter-arc structure remain. This is a counterfactual independence
   error, not a competing physically supported noise law.

## Fixed-estimator response and target refit

The reference estimates retain the original joint IF/MW weights. This is
covariance propagation for **that estimator**, not a new optimal global GLS
reference solution under colored noise. Under a changed noise law, clock
compression may lose information that a full joint reference/target fit could
use. No improved reference mean estimate is claimed from the covariance change.

At epoch t, let G be the fixed clock GLS gain, P=I-AG its residual projector,
B the shared ambiguity/drift design and W the whitening operator. The fitted
ambiguity response is obtained through the existing profiled SVD covariance.
Every requested receiver-clock contrast includes both its direct G response
and the indirect response through those fitted biases. The new reusable
`network_clocks.observation_response` returns the resulting derivative for
every reference observable. Dense GLS tests verify it, including free drift.

Target raw endpoints map into IF code levels and IF/MW increments. Reference
endpoints map through the clock response into the measured clock coefficients.
The complete data covariance is the mapping of the **same** declared raw
processes into both, plus the unchanged ground-coordinate terms. Factorizing
by link and receiver avoids constructing an enormous dense raw covariance.
A separate dense raw-domain test checks all temporal, signed endpoint,
receiver, cross-arc and reference-target terms, including the independent limit.

The covariance sign is material: target and calibrated clock data can respond
to the same receiver disturbance. Dropping their cross block can prevent its
cancellation after nuisance profiling. Giving only the target an extra variance
or perturbing only the final fit does not represent that chain. Existing
shared-P1 end-to-end recalibration/refit regressions remain in the suite.
No residual rescaling, new bias prior or integer-slip repair is introduced.

Only original target training endpoints enter fitting and continuity masks.
Reference/candidate identity admission precedes arithmetic; the covariance
boundary rejects a candidate in its own reference response. All candidate
fits, covariance and RF/MW predictions precede dedicated RF and CODE scoring.
The existing free-GF model, light-time/Earth-rotation/GPST/ECEF conventions,
central+J2 dynamics, propagation and ground assumptions remain unchanged.
G12 orbit remains unopened and no S3 campaign is started.

## Execution and preserved evidence

Numerical producer: `dff8499198ee4212429bdedb3cae2c5c5ed920fa`, based on
merged main `aa11f4ccfc549a21643a8036b431e3752f51818f`. New output:
`results/temporal_shared_rf_v1.json.gz`. Historical results and their exact
producer source bytes remain retained through Git ancestry.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --temporal NEW_OUTPUT.json.gz
```

Result SHA-256: `25ea2da175ab42c2c18be931112cdba011441fe38b9d8e2ed3dc9a44445af80a`
(14,625,546 gzip bytes). Replay checks bind the input/source bytes, preserve
all candidate/window terminals, recompute reference-only diagnostics from
constant-bias residual differences, and verify forecast hashes and scoring.

## Temporal and shared-component results

All five fitted folds have supported temporal training and validation. The
following normalized shape losses compare the fixed rho against independence
on the excluded final third, at the four short lags only:

| Fold | rho at 30 s | Validation loss, temporal | Validation loss, independent | Smallest training cross-moment eigenvalue, m2 |
|---|---:|---:|---:|---:|
| G05 | 0.20359 | 0.005557 | 0.049311 | -0.028834 |
| G11 | 0.21058 | 0.005908 | 0.053661 | -0.024443 |
| G19 | 0.18340 | 0.105749 | 0.252151 | -0.021479 |
| G20 | 0.19978 | 0.004979 | 0.044787 | -0.027549 |
| G21 | 0.24882 | 0.044751 | 0.006523 | -0.010449 |

The temporal shape improves this internal diagnostic in four overlapping
folds but **worsens G21** (.00652 to .04475). It is not selected away there.
At 300 s, the model predicts normalized variograms of 1.225–1.331, while
validation MW gives .995–1.147 and D gives 1.120–1.187. The same fitted
shape therefore does not describe all channels/lags or demonstrate stationarity.

Both training cross-moment eigenvalues are negative in **every** fold.
Validation moments are also non-PSD in every fold (negative definite or
indefinite). Split diagnostics have 29–77 supported training and 14–38
validation epochs; there are no unsupported split epochs in these actual
folds. Their reuse across folds is not independent replication. Finite-record
variation, cross-group dependence and structured link errors can affect these
moments. They are not physical negative variances, proof of no shared error,
or a justification to choose f=.5. That fraction remains a declared sensitivity.

## Trajectories, uncertainty and contrary cases

All 22 candidates, 440 preparation windows and 63 original arcs remain.
Every variant fits five trajectories and retains 17 insufficient-support
candidates. All 1,020 candidate code samples and 680 IF/MW increments remain;
the GF mask removes none in this cohort. Every fit reports
`BRANCH_SEARCH_INCOMPLETE`. The independent G19 baseline retains one failed
interior-Earth initialization; each temporal variant retains two. Every other
case retains one. These are failed numerical/domain seeds, not evidence of
competing physical orbits or of global uniqueness. Snapshot preparation does
not prove that unsupported data could not support another dynamic preparation.

Each quadruple below is **independent / temporal code / temporal shared /
shared without cross block**. CODE shares upstream information with reference
products and is not independent truth. The 126 state comparisons derive from
five trajectories, with only five genuinely future state epochs.

| Candidate | Position RMS, m | Velocity RMS, mm/s | Largest conditional position 1-sigma, m |
|---|---:|---:|---:|
| G05 | 155.982 / 155.984 / 155.998 / 156.223 | 13.035 / 13.035 / 13.039 / 13.070 | 44.240 / 44.245 / 31.577 / 50.939 |
| G11 | 93.565 / 93.595 / 93.446 / 92.277 | 11.901 / 11.902 / 11.904 / 11.915 | 213.998 / 214.000 / 152.455 / 249.176 |
| G19 | 87.981 / 87.970 / 87.935 / 84.656 | 26.547 / 26.547 / 26.539 / 26.127 | 366.259 / 366.262 / 261.518 / 419.527 |
| G20 | 18.288 / 18.299 / 18.292 / 18.374 | 17.006 / 17.004 / 17.011 / 17.022 | 200.055 / 200.060 / 142.741 / 229.703 |
| G21 | 242.392 / 242.412 / 242.484 / 243.099 | 25.470 / 25.473 / 25.487 / 25.570 | 68.455 / 68.459 / 48.809 / 79.322 |

The refreshed independent baseline reproduces #229 position RMS within .1 mm.
Temporal code correlation alone changes position RMS by at most .030 m,
worsening four of five cases; velocity worsens in four cases too. Its formal
axes change by less than .01%. The shared sensitivity improves position RMS
only in G11/G19 and velocity only in G19. No covariance scenario is promoted
from these CODE scores. Previously exposed free-drift/bias failures are not
rerun or reclassified by this constant-bias covariance comparison.

Under the **same f=.5 hypothesis**, deleting just the RF/clock cross block
inflates the largest conditional position axes by factors **1.604–1.634**
and velocity axes by **1.604–1.633**. Modeled maximum RF/clock correlations
before deletion are .571–.574. Proper shared-model velocity axes for
G05/G11/G19/G20/G21 are 5.46/12.69/45.92/22.05/8.71 mm/s; the ablation gives
8.81/20.72/73.65/35.47/14.15 mm/s. This quantifies the error from false
reference-target independence under a declared model, not a measured reduction
of real uncertainty. The unqualified sharing hypothesis itself shrinks axes
about 29% versus independence without a corresponding accuracy improvement.

The ablation can even appear better against CODE: G19 position RMS is
84.66 m versus 87.93 m with the correct cross block. That does not validate
the wrong covariance or supply an oracle-based criterion to choose it.

| Candidate | Position discrepancy at its one genuinely future epoch, m |
|---|---:|
| G05 | 152.005 / 152.005 / 152.022 / 152.228 |
| G11 | 90.288 / 90.318 / 90.159 / 88.932 |
| G19 | 81.109 / 81.097 / 81.064 / 77.907 |
| G20 | 13.117 / 13.100 / 13.088 / 13.064 |
| G21 | 248.216 / 248.238 / 248.313 / 248.989 |

Nominal conditional 95% position ellipsoids include 54/126 CODE rows and
3/5 future positions in every variant. Joint-state inclusion is 34/34/13/44
of 126 and **0/5** genuinely future states in every variant. These correlated
checks neither qualify population coverage nor demonstrate a total physical
error budget. The covariance hypotheses remain conditional on fixed masks,
reference products/geometry, point-estimated rho and unqualified f.

### Excluded RF predictions

There are 339 evaluated receiver pairs and one unavailable pair; 313 are
internal holdouts and 26 genuinely beyond all training. MW bias is constant
in every model, so its zero-rate forecasts and residuals are identical.

| Quantity | Independent | Temporal code | Temporal shared | Without cross |
|---|---:|---:|---:|---:|
| All holdouts: code RMS, m | 0.711769 | 0.709526 | 0.709077 | 0.709438 |
| All holdouts: IF phase RMS, mm/s | 8.570825 | 8.570132 | 8.566657 | 8.566677 |
| All holdouts: MW RMS, mm/s | 5.924112 | 5.924112 | 5.924112 | 5.924112 |
| Internal holdouts: code RMS, m | 0.693451 | 0.691135 | 0.691006 | 0.691143 |
| Internal holdouts: IF phase RMS, mm/s | 8.630719 | 8.630768 | 8.629525 | 8.625713 |
| Internal holdouts: MW RMS, mm/s | 5.911592 | 5.911592 | 5.911592 | 5.911592 |
| Genuine future: code RMS, m | 0.903600 | 0.901966 | 0.898541 | 0.900980 |
| Genuine future: IF phase RMS, mm/s | 7.813842 | 7.803272 | 7.770006 | 7.821087 |
| Genuine future: MW RMS, mm/s | 6.072814 | 6.072814 | 6.072814 | 6.072814 |

Relative to independence, genuine-future aggregate code/phase improve slightly
under temporal code (.903600 to .901966 m; 7.81384 to 7.80327 mm/s) and the
shared sensitivity (.898541 m; 7.77001 mm/s). The ablation worsens future
phase to 7.82109 mm/s. These small RF changes do not establish orbital accuracy
or justify the unmeasured shared amplitude.

Pairwise worsening remains visible below; counts compare each variant against
the current independent baseline on exactly common support:

| Variant | All code worse / 339 | All phase worse / 339 | Future code worse / 26 | Future phase worse / 26 |
|---|---:|---:|---:|---:|
| temporal_code | 169 | 181 | 12 | 8 |
| temporal_shared | 162 | 133 | 7 | 10 |
| temporal_without_cross | 170 | 137 | 10 | 13 |

Reference held-out **mean** diagnostics are identical across variants because
the reference estimator is unchanged: 3,045 codes evaluated/544 unsupported;
2,643 phases evaluated, with 544 unobserved clocks and 402 unassigned
continuity segments; 3,151 MW rows evaluated/438 unsupported. They remain
conditional on the full-network timing linearization and original mask, not
an independent nonlinear holdout. No support loss is presented as an error gain.

## Verification and next physical obstacle

All 44 producer-focused tests and all 13 updated covariance/study/receipt
checks pass. They cover full GLS derivatives, dense raw-domain covariance,
independent limits, shared-factor and cross-block ablation, noiseless state
recovery, candidate admission, validation poisoning, clock-blind modes,
negative cross moments, unavailable temporal shapes, scoring order and exact
source/input/receipt integrity. The producer review completed without findings.
Complete research regressions, final-head Linux/Windows CI and review are
recorded on [PR #230](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/pull/230).
Historical receipt/source tests remain intact, including all scientific merge
ancestry. No frozen hash or outcome is rewritten.

The new executable capability is covariance transport through all fitted
reference biases and clock data into the RF trajectory, with explicit temporal,
receiver-sharing and reference-target dependencies. It resolves an engineering
restriction in the error representation. It does **not** identify a finite total
physical covariance or demonstrate materially better orbit reconstruction.
S2 remains open; no S3 campaign is started.

The next physical obstacle is to identify an admissible positive error
structure rather than force negative cross moments into a receiver-common
variance. A reference-only model must distinguish link/direction-dependent
structure and cross-group dependence from a shared receiver process, then
predict excluded time blocks including G21 and the 300 s scale. The code/phase
allocation and shared amplitude require evidence before the roughly 29%
formal-axis reduction can be interpreted physically. Hyperparameter/mask
uncertainty and the blind common clock-like term still need separate support.
Another GNSS product is not automatically independent information about them.
