# Nondispersive network closures and calibration-to-orbit response

## Intervention and information

D=IF code-IF phase and MW cannot see an equal raw metre error in all four
channels. The previous increment identified that null direction and separated
receiver-common cancellation from link-dependent orbital degeneracy. This
increment adds the admitted reference geometry to expose the IF path channel
through **network closure contrasts**, predicts increments on excluded future
links, and decomposes their calibration-to-state response into clock-blind and
cycle-visible input subspaces. Finite perturbations refit both the reference
network and the RF trajectory.

The information is the existing non-target reference orbit/clock/antenna/bias
model and the contemporaneous RF of other links. It is not independent orbital
truth, a new receiver clock measurement, or a physical variance inferred from
small residuals. This is development on the exposed archive. The original
22 candidates, 440 windows and preparation rules remain; candidate products
are excluded before numeric parsing in their own fold, and G12 orbit remains
unopened. No candidate CODE scoring is invoked by this execution.

The [GNSS observable equations](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables)
distinguish nondispersive range/clock/propagation terms from dispersive effects
and carrier ambiguities. For example,
[tropospheric delay affects code and carrier together](https://gssc.esa.int/navipedia/index.php?title=Tropospheric_Delay).
This motivates an error delta added equally to IF code and IF phase, with no
MW/GF change. It does **not** establish that observed phase closure scatter
consists only of troposphere or of a single pure nondispersive stochastic
process. Reference geometry, wind-up, instrument biases, phase errors and
unmodeled propagation can also contribute.

## Calibrated closures and future-link prediction

At an epoch let A be the existing nuisance design in raw link-metre coordinates:
one receiver coefficient with its actual observation-time derivative per site,
plus zero-mean reference-clock error coefficients. Use its thin orthonormal
basis Q from the existing `calibration_transfer.residual_blind_modes` primitive.
The cycle projector C=I-Q Q^T annihilates the **actual** clock design, including
the small geometry/time derivatives. No approximate all-unit incidence matrix
or arbitrary receiver anchor replaces it.

The nominal joint IF/MW reference fit retains constant GF-segment phase/MW
biases and the historical weights. Apply C separately to its IF code and phase
residuals. Retain every link value, epoch clock/cycle rank and 30/300 s
code/phase semivariogram. Segment-matched changes remove constant link levels;
the recorded values remain conditional on full-window fitted float biases,
reference masks and timing. They are in-sample filtered diagnostics, not
independent error variances.

A separate prediction excludes fixed station/SV links in the last third of
reference time. The identity-only rule is SHA-256 of `station/reference`, first
eight bytes interpreted big-endian, modulo 7 equal to zero. Other links remain
available at those later epochs. Remove **all channels** of an excluded row
before rebuilding GF segments and estimating clocks/float biases. A missing
graph/clock remains unsupported; no temporal prior or anchor invents it.

Predict the excluded link's modeled IF clock/path term using the retained
receiver and reference-clock estimates. A phase level can use only its last
prefix float bias with the same original flag/gap base segment. Its later GF
continuity is unobserved and is only a hypothesis. Predictions never inspect
the withheld GF values to select a segment or repair a jump. Score 30/300 s
increments only when both endpoints are excluded, clock predictions exist and
the original base segment matches. An unknown constant phase-bias level cancels
in those increments. Any unobserved future phase change remains in the error.

This is conditional future-**link** transfer with other RF supplied at the same
later times, not a forecast without future network data. Nominal reference
geometry, masks and observation-time linearization were already prepared by
the full reference calibration and are held fixed. Withholding is therefore
not independent nonlinear relinearization of the complete acquisition chain.
The new isolation protects the subsequent GF/ambiguity/clock fit, with this
upstream conditioning explicit. No prospective-blindness claim is made.

Every fold's trajectory estimates, finite probes and predictions precede both
this reference scoring and dedicated excluded candidate-RF scoring. Candidate
CODE products are never opened for a new state score. All unsupported cases,
probe failures and worsening RF results remain visible.

## Complete error response and its null space

The existing `network_clocks.observation_response` differentiates the fixed
reference estimator, including every refitted segment bias. The current
RF-only fitted point supplies the existing `dynamic_fit.linearize` response
after profiling satellite clocks, receiver clock data, station coordinates and
free constant target code-bias contrasts. Masked observations are restored as
zero columns in the original full-data ordering before selecting clock data.
This retains all clock offset/rate/curvature and cross-arc effects.

For one metre delta per admitted reference link/epoch, the reference observable
change is [delta,delta,0] in IF code/phase/MW order. Compose its reference-clock
response with the trajectory response to those clock data to obtain T, six
state coordinates by M reference rows. Candidate RF is held unchanged for
these **reference-only error sensitivities**.

Use the block-diagonal raw-link projector P=diag(Q Q^T) to partition
T_blind=T P and T_cycle=T(I-P). The first input subspace is fitted as epoch
clocks and is invisible to the conditional reference residuals; the second
contains instantaneous network cycles. Its transfer can still involve global
float-bias refitting when geometry or link support changes across epochs.
Their row-space orthogonality gives
T T^T=T_blind T_blind^T+T_cycle T_cycle^T. These are response identities in
Euclidean reference-link metres, **not a fitted physical covariance**.

For each part, sqrt(M) times the largest singular value of its position response
is the largest local position change per metre of coherent reference-row RMS.
Velocity gain is reported separately in mm/s per metre. The reciprocals specify
the coherent input RMS that would yield at most 1 m position or 1 mm/s velocity
under this local linear model and its declared subspace. These are amplitude
requirements on an error functional, not iid sigmas, coverage bounds, achieved
clock precision or measurements of actual errors. A right singular vector
specifies which independent calibration/geometry functional would have to be
constrained; more precise closure measurements cannot constrain P's exact
null direction. Raw row counts and peak amplitudes accompany RMS values.

The leading position right mode in each resolved part supplies a fixed **.01 m
coherent RMS probe**, chosen without CODE or excluded RF. Add it equally to
the reference code and phase rows, refit all reference clocks and float biases,
attach the newly calibrated clock data, and cold-start a new trajectory fit.
The original target RF, GF masks, weight matrices and covariance are preserved.
Compare the finite state change with T delta and record the calibrated closure
change. Unresolved position responses remain explicit at relative numerical
rank tolerance 1e-10; a roundoff mode is not amplified into a physical probe.
Neither probe is a candidate correction or a proposed noise law.

A physically shared receiver-clock disturbance also changes candidate RF.
Its matching candidate contribution can cancel the calibration response, as
verified by the retained full-chain control from #231. The current reference-only
clock-blind sensitivity must **not** be assigned automatically to that shared
physical process. Conversely, small observed closures do not bound an unshared
calibration error in the same fitted nuisance subspace. The target/reference
coupling of a real source needs its own evidence.

The reference observation-time model/derivatives are fixed during finite
probes. Reference nuisance parameters and the nonlinear target trajectory are
refitted, including target light time, Earth rotation and VMF3 at each trial.
This verifies the complete conditional linearized-reference calibration chain,
not a physical bound on upstream reference products or masks. The original
ECEF/GPST, central+J2 and excluded target-RF conventions remain.

## Numerical stability and execution

The derivative now applies the profiled SVD inverse V Sigma^-1 U^T directly,
instead of forming C_beta times the profiled design transpose. The latter
created a small spurious clock response to an exactly orthogonal cycle in a
constant complete graph. The regression retains the same 1e-10 numerical
resolution criterion and verifies that this response is unresolved. Dense GLS
and raw-covariance tests remain passing, including free drift. Fitted reference
means, weights and nominal covariance formulas are unchanged. Historical
artifacts retain their original producers and exact source bytes through Git.

Numerical producer: `da8db1bedf17ef55ad6cfa65e42e588b0163ca42`, based on
`14810889a92c098d4e423440639f5594a2a69d54` (merge #231). Command:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --closures NEW_OUTPUT.json.gz
```

All 30 producer-focused tests pass: nuisance/cycle partition, null-case
resolution, dense transport, future IF/GF poisoning, unavailable future clocks,
full reference-bias/trajectory refits, masked-data covariance response, scoring
order and the historical temporal/shared-structure receipts.

Artifact: [`results/nondispersive_network_closures_v1.json.gz`](results/nondispersive_network_closures_v1.json.gz),
6,968,677 bytes, deterministic gzip timestamp zero, SHA-256
`755d4ebf9377feb3d3e0bfd892e88b45b29529c6d432959e5a10a4c10e8592f6`.
The receipt test replays source/input hashes, all terminals, RF scoring,
closures, excluded-link predictions and the composed response. Singular-vector
signs may differ across LAPACK builds; the retained probe and its response,
rather than a chosen sign, are verified.

The final focused set, including this new receipt, passes **31 tests** in
68.63 s. Linux and Windows CI additionally run the complete repository suites.

The artifact's packed field `clock_measurement_change_m` follows the retained
`clock_requests` ordering. Despite its historical suffix, only clock **offset**
entries are metres; mean-rate and contrast-rate entries are m/s. Six-state
vectors are ECEF position in m and ECEF velocity in m/s at the recorded GPST
epoch. The report never treats the packed clock vector as all-metres.

## Execution and unavailable cases

All three variants retain 22 candidates, 440 preparation windows and 63 prepared
arcs. G05, G11, G19, G20 and G21 have trajectory fits; 17 candidates retain
`INSUFFICIENT_PREPARED_ARCS`. Those are outcomes of these fixed preparations,
not a universal impossibility result for those satellites. Every fitted variant
remains `BRANCH_SEARCH_INCOMPLETE`: at least one internal seed fails, with two
failed seeds for the G19 probes versus one nominally. The additional failed
attempts remain in the artifact. They do not establish two physical orbits or
global uniqueness. Reference calibrations retain their original conditional
acceptance; no failure is relabeled as physical qualification.

The five reference folds contain 25,117 link/epoch row occurrences. They reuse
overlapping observations, not 25,117 independent experiments. Their per-epoch
cycle ranks range from 23 to 31, depending on the fold and visible graph.

## Excluded future links

All five folds support some conditional future-link prediction. Across 61
held-link occurrences, 1,316 of 1,494 excluded rows have observable receiver
and reference clocks. The other **178 remain `UNOBSERVED_NETWORK_CLOCK`** and
receive no prediction. There are 1,270 paired 30 s and 879 paired 300 s
increment errors. Rows, pairs and folds overlap; their counts do not define an
independent population sample.

| Fold | Held links | Predicted / excluded rows | Pairs 30 / 300 s | Code increment RMS 30 / 300 s (m) | Phase increment RMS 30 / 300 s (mm) |
| --- | ---: | ---: | ---: | ---: | ---: |
| G05 | 12 | 285 / 324 | 276 / 203 | 1.420 / 1.460 | 9.857 / 16.075 |
| G11 | 10 | 237 / 276 | 230 / 174 | 1.264 / 1.361 | 9.214 / 13.723 |
| G19 | 12 | 133 / 163 | 124 / 43 | 1.096 / 1.026 | 7.810 / 18.379 |
| G20 | 14 | 363 / 402 | 352 / 261 | 1.310 / 1.325 | 9.256 / 15.268 |
| G21 | 13 | 298 / 329 | 288 / 198 | 1.218 / 1.250 | 9.228 / 14.246 |

The nominal full-fit phase-closure increment RMS is only 4.102–4.638 mm at
30 s and 8.126–8.396 mm at 300 s. These filtered in-sample values are smaller
than the held-link errors; neither quantity is raw sensor precision. The
artifact retains each two-channel mean and uncentered second-moment matrix.
The code/phase cross-moment is negative in four folds at 30 s and positive in
G19; its signs are mixed at 300 s. It is not evidence for one positive shared
nondispersive noise amplitude. No sample moment is substituted for a raw
covariance or used to retune a weight.

All retained future epochs still use other reference RF at those epochs.
Forecasting the whole network with free epoch clocks is explicitly
`UNIDENTIFIABLE_FREE_EPOCH_CLOCKS`. No RF-free clock forecast is claimed.

## What survives calibration and what stays invisible

The clock-blind part contains **99.53–99.83% of the squared position-response
energy** in the declared Euclidean raw-link coordinates. This is a property
of the conditional estimator, not the fraction of measured physical error
variance. Its leading position direction aligns with the largest nominal
conditional position-covariance axis with absolute dot product
0.99941–0.99999. The weak orbital direction and a concrete unmeasured reference
error functional are now connected through the complete estimator.

The following are actual finite recalibration plus cold-start trajectory
refits. Each input has .01 m RMS over all reference rows in its fold; its
peak is much larger than .01 m. These are deliberately constructed coherent
reference-only errors, not observed disturbances or orbital accuracy scores.

| Fold | Clock-blind peak (m) | Clock-blind position change (m) | Clock-blind velocity change (mm/s) | Cycle peak (m) | Cycle position change (m) | Cycle velocity change (mm/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| G05 | .0763 | 686.686 | 109.363 | .3237 | 48.464 | 7.255 |
| G11 | .0944 | 3064.240 | 55.424 | .5419 | 247.198 | 17.777 |
| G19 | .0687 | 3715.336 | 651.715 | .2714 | 259.646 | 44.841 |
| G20 | .0962 | 3233.554 | 495.899 | .5823 | 139.537 | 22.174 |
| G21 | .0670 | 903.356 | 157.357 | .3397 | 72.855 | 14.313 |

For the clock-blind probes, the maximum calibrated code/phase closure change
is below 5.86e-11 m. That is numerical cancellation of a fitted nuisance mode,
not physical measurement precision. Float biases change by less than 1.06e-11 m.
Conditional reference p-values remain 1. Small closure scatter cannot bound
this response. A receiver-common physical disturbance must also perturb the
candidate path; the current table does not include that matching contribution
and cannot be applied to it automatically.

The cycle probes retain **.01 m code-closure RMS**, but only 4.68e-9–1.62e-7 m
phase-closure RMS after refitting. Maximum phase float-bias changes are
.481/.788/.397/.841/.503 m in G05/G11/G19/G20/G21. Nearly all of this phase
cycle signal is absorbed into fitted constant biases. The varying graph and
clock design still transfer part of it through the calibrated clocks to the
target state, even though the phase residuals look unchanged. The code channel
can see it, but the historical 20 m IF-code weighting does not tightly bound
such a .01 m coherent perturbation. The original weights remain unchanged.
This finite result is distinct from the nominal future-link validation; no
claim is made that a separately scored probe passes that validation.

The largest finite-minus-linear position difference is .811 m for a 3.234 km
clock-blind change (about .0251%) and .0121 m for a 259.646 m cycle change.
Corresponding maximum velocity differences are .1322 and .00199 mm/s. The
conditional local derivative predicts these finite interventions well; this
does not turn its first-order response into a global physical bound.

The separate worst-case linear gains imply the following **coherent input
RMS amplitudes**, evaluated in their specified subspaces:

| Fold | Clock-blind RMS for 1 m position (micrometres) | Cycle RMS for 1 m position (micrometres) | Clock-blind RMS for 1 mm/s velocity (micrometres) | Cycle RMS for 1 mm/s velocity (micrometres) |
| --- | ---: | ---: | ---: | ---: |
| G05 | 14.563 | 206.338 | 85.294 | 1351.086 |
| G11 | 3.263 | 40.452 | 39.395 | 533.647 |
| G19 | 2.691 | 38.512 | 15.286 | 222.785 |
| G20 | 3.093 | 71.665 | 19.973 | 450.810 |
| G21 | 11.069 | 137.257 | 62.107 | 689.651 |

Position and velocity maxima can involve different input directions. These
reciprocals constrain a coherent reference-only **functional**, not an iid
noise sigma or a universal per-receiver precision requirement. The retained
right modes specify its time/link geometry. Assigning a physical source to
it requires a justified source model and the corresponding candidate response.
No independent measurement currently bounds those functionals. The nominal
largest conditional position axes remain 44.24/214.00/366.26/200.06/68.46 m;
after either probe they change by less than .047%. Nearly unchanged formal
covariance in the presence of a large coherent state change is not qualified
total uncertainty.

## Excluded candidate RF and adverse outcomes

Each variant retains 339 evaluated station-window pairs plus one unavailable
pair in the five fitted candidates: 313 interleaved temporal holdouts and only
26 beyond all admitted target training. These are predictions from five
trajectories, not 339 independent state reconstructions. Unsupported candidates
and windows remain in the same artifact. No new CODE position/velocity score
or oracle selection is performed.

| Variant | All code RMS (m) | All IF phase-rate RMS (mm/s) | Beyond-training code RMS (m) | Beyond-training IF phase-rate RMS (mm/s) |
| --- | ---: | ---: | ---: | ---: |
| Nominal joint independent | .711769 | 8.570825 | .903600 | 7.813842 |
| Clock-blind probe | .808801 | 8.711013 | 1.023658 | 6.458875 |
| Cycle-visible probe | .718233 | 8.566311 | .921947 | 7.759601 |

Relative to nominal, the clock-blind probe worsens absolute code and phase
errors in 215/339 pairs each; its all-pair code RMS worsens in 5/5 folds and
phase RMS in 4/5. In the 26 genuinely future pairs code worsens in 16 and phase
in 5; future code RMS worsens in 4/5 folds, while phase RMS decreases in all
five. The cycle probe worsens code in 181/339 and phase in 163/339 pairs; its
all-pair code RMS worsens in 4/5 folds and phase in 2/5. Future code worsens
in 18/26 pairs and its RMS in 5/5 folds; future phase worsens in 11/26 pairs
and its RMS in 1/5 folds. All individual values and signs are retained.

The lower future phase RMS for deliberate perturbations is not a validated
correction or a selection criterion. Neither sign nor amplitude was chosen
from those scores, and neither is tuned afterward. MW predictions are
unchanged for these constant-bias variants; nondispersive probes do not create
an additional independent MW observable.

## Physical conclusion and next useful information

The executable addition is a geometry-assisted nondispersive network
contrast, isolated future-link predictions and a full calibration-to-state
response. It identifies two distinct limitations: an exact clock-blind input
subspace, and phase-cycle information that can be absorbed by float biases
while still influencing calibrated clocks. D/MW alone could not expose that
second mechanism. Small post-calibration phase residuals cannot qualify either
the raw common-error budget or the total orbital covariance.

The next useful physical increment is to assign admitted source geometry and
target/reference coupling to these modes, then test its transferable contrasts.
For example, a wet-delay perturbation must use the admitted elevation/VMF3
mapping in both the reference recalibration and the candidate path, reusing
the existing `reference_wet_fit` transfer rather than assigning the unrestricted
reference-only probe to weather. Reference orbit/antenna errors require their
own line-of-sight mapping. Such source restrictions can make cycle information
useful; they do not resolve an exact clock-null functional without independent
timing/bias information or justified geometry. This run supplies the response
and measured excluded-link errors needed to test those hypotheses, not their
physical admission.

S2 remains open. No floor reduction, new covariance law, target-orbit access,
G12 state reveal, historical outcome change, prospective confirmation or S3
advancement follows from this increment.
