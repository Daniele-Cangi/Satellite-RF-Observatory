# Joint IF and Melbourne–Wubbena information through the RF trajectory

## Physical intervention

GF-only continuity has exact and near-null phase-slip modes. In particular,
77/60 GPS L1/L2 cycles give zero GF change but 14.652613 m in IF phase;
9/7 cycles give only 3.172 mm GF but 1.717545 m IF phase. The unused
frequency-dependent code contrast can expose these directions through MW.
This increment puts that contrast into the existing reference calibrator and
candidate trajectory fit, preserving its correlation with IF code and phase.
It adds no observations by merely changing basis, and does not turn an
instrumental ambiguity or a training residual into an integer-slip diagnosis.

The [ESA measurement combinations](https://gssc.esa.int/navipedia/index.php/Combination_of_GNSS_Measurements)
and [MW formulation](https://gssc.esa.int/navipedia/index.php/Detector_based_in_code_and_carrier_phase_data:_The_Melbourne-W%C3%BCbbena_combination)
provide the frequency algebra. In metres, with raw vector
`x = [P1, P2, phi1, phi2]` and `phi_i = lambda_i L_i`, this implementation uses

```text
IF_code  = alpha P1 + beta P2
IF_phase = alpha phi1 + beta phi2
GF_phase = phi1 - phi2
MW       = -(f1 P1 + f2 P2)/(f1+f2) + (f1 phi1 - f2 phi2)/(f1-f2)
alpha = f1^2/(f1^2-f2^2), beta = -f2^2/(f1^2-f2^2).
```

The four-by-four transform T is invertible. Its covariance is `T C_raw T^T`;
IF/GF/MW are not independent measurements. A free ionosphere per link/epoch
occupies GF alone in this basis. Profiling that nuisance leaves the
**principal IF-code/IF-phase/MW covariance**, not its covariance conditioned
on GF as an exact measurement. Under the first raw-noise scenario below,
IF-phase/GF correlation is .9714; false conditioning would manufacture extra
phase precision. GF remains the existing causal continuity witness. No GF
forecast is possible under the free link-epoch ionosphere model.

A second degeneracy is just as material: an arbitrary MW bias at each endpoint
profiles MW out too, leaving exactly the original IF marginal likelihood.
Useful extra information therefore depends on temporal instrumental/bias
stability, not on frequency algebra alone. Equal metre errors in all four raw
channels cancel from both GF and MW and still pass into both IF observables.
These combinations alone cannot bound a common nondispersive clock-like term.

## Raw covariance and temporal assumptions

The historical IF endpoint weighting sigmas remain 20 m code and .02 m phase.
They do not identify the four-channel covariance. Two explicit sensitivity
scenarios preserve those same IF marginals:

- Equal independent code bands and equal independent phase bands. Single-band
  sigmas are 6.715341 m code and .006715341 m phase; endpoint MW sigma is
  4.785037 m and IF-code/MW correlation is -.35523.
- Equal code bands correlated at rho=.5, independent phase bands. Single-band
  code sigma becomes 9.002981 m; endpoint MW sigma is 7.816888 m and
  IF-code/MW correlation is -.45464. The IF marginals remain unchanged.

The candidate state is reported in ECEF metres and metres/second at GPST;
central gravity plus J2, receive/transmit-time and Earth-rotation conventions,
propagation and terrestrial-coordinate assumptions are inherited unchanged
from the prior trajectory study. No new dynamical or ground prior is added.

Code/phase cross-noise, temporal, receiver-shared and link-shared noise are zero
in these weighting scenarios. None is inferred or qualified by this archive;
no residual rescaling is performed. The independent-band scenario gives an
adjacent MW-difference weighting sigma of 6.767 m: the 77/60 and 9/7 changes
are only about 2.17 and .255 times that assumed scale. This is no qualified
detector. Ignoring phase noise, six-sigma separation of the 9/7 case would
require single-band code sigma below .285 m under the equal-independent-band
assumption, plus evidence for temporal bias stability; the inherited IF floor
does not supply it. Full within-endpoint correlations,
adjacent differences' signed shared-endpoint correlations, and the calibrated
clocks' station/epoch/cross-arc covariance are retained. Shared physical errors
outside these scenarios still require a budget; the synthetic end-to-end
perturbation below is a sensitivity demonstration, not that budget.

Four preselected variants are executed without CODE-based choice:

1. `network_gf_segments`: refreshed prior GF-segmented constant-bias IF baseline.
2. `joint_independent`: first raw covariance; constant reference IF-phase and
   MW float bias per GF segment; constant candidate MW bias per receiver/arc,
   eliminated by differencing (MW rate prediction zero).
3. `joint_free_drift`: first raw covariance; additional unpenalized reference
   IF-phase and MW linear drifts per supported segment, and a free candidate
   MW rate per receiver/arc. Singleton reference slopes and candidate slopes
   with no retained MW increments are unidentifiable, not fixed to zero for
   forecasting. Candidate IF code bias remains constant; this does not relax
   every possible temporal bias.
4. `joint_correlated_code`: second raw covariance, constant biases as in (2).

Reference MW uses the existing C1C-to-C1W correction translated back by alpha
into P1, with P2 unchanged. Candidate products remain excluded; its MW uses
raw RF and unknown constant levels disappear in increments. No absolute
candidate OSB, previous solution or target orbit is admitted.

## Executable paths and boundaries

`reference_network_clocks.py --combinations OUTPUT` reuses the same 22-fold
preparation, network profiling, clock transport and dynamic solver. Reference
MW has no direct geometric or clock derivative; its noise correlation and
bias stability can still change the joint clock estimate. Candidate MW rates
have zero orbital/clock derivative; their correlation with IF residuals carries
the incremental information. GF-witnessed candidate boundaries remove both
IF and MW increments by taking the retained covariance's principal submatrix;
code is retained. A free MW rate is allocated only where actually observed.

This is **not an MW continuity detector**. The GF mask only supplies known
boundaries; a GF-null jump remains in both observables unless another
supported boundary is supplied. The new synthetic negative controls inject
77/60 and 9/7 slips below the GF threshold. The joint constant-bias model is
rejected in both cases, with a severely biased algebraic state (about 26.5 km
in the 77/60 toy case). Supplying the known synthetic boundary and removing
both IF and MW increments restores the state through the existing free-jump
path. The boundary in that test is supplied knowledge, not an inferred real
slip. The implementation does not claim automatic repair or immunity to
GF-null disturbances. An MW-aware real-data boundary needs a justified
temporal code/phase noise and bias model; these unqualified endpoint weights
do not provide one. Adding a threshold now would conceal that missing
information rather than qualify it. Reference MW has the same limitation.

All trajectories, local conditional covariance and RF/MW predictions for all
candidates and variants are fixed before dedicated RF, MW and CODE scoring.
Only original candidate training epochs enter the fit and continuity witness.
Forbidden candidate products and own-fold reference RF are removed before
numeric parsing. The archive is already exposed: this order is not new
prospective blindness. G12 orbit remains unopened; no S3 campaign is started.

The deterministic every-seventh reference-link diagnostic reconstructs its GF
segmentation without excluded GF values. MW support is assessed separately:
a segment bias can predict MW even at an epoch with an unobserved receiver
clock. Conversely an unsupported MW drift does not discard supported IF code.
The diagnostic still uses rows linearized at the full-network timing solution
and the original admitted mask. It is conditional on that preparation, not an
independent nonlinear holdout replay.

The end-to-end synthetic test adds a common raw P1 error at one receiver/epoch
to its references and candidate. Recalibrating the network, transporting its
clock data and refitting the target changes the state differently from changing
only target observations with old clock data. This guards the full shared-error
path; its one-metre amplitude is not an uncertainty qualification.

## Execution and preserved evidence

Numerical producer: `b23afe60d675f03d64f5917b23555a617e34eb40`, descended from
merged main `4083e00e3197f24c21af6e929bc79e2152b3fc6e`. Historical network,
correction and continuity artifacts remain unchanged. The new receipt is
`results/joint_rf_combinations_v1.json.gz`. Reproduce with Python 3.13 and the
repository requirements, choosing a new output path:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --combinations NEW_OUTPUT.json.gz
```

Result SHA-256: `a7b864b74b4952277f26f4a6a8b06680aae4c6e63d744ff8ff64fdeebd6e857c`
(14,191,872 gzip bytes). The provenance regression checks the input hashes,
exact producer source bytes through Git, all terminals, transformed covariance,
RF/MW prediction hashes and rescoring against the original admitted extracts.

## Results and contrary outcomes

All 22 candidates, 440 preparation windows and 63 arcs remain. Every variant
fits five trajectories and retains 17 insufficient-support candidates. The
candidate witness removes zero of 680 IF increments; all 1,020 code samples
and 680 MW increments are retained. Every fit is `BRANCH_SEARCH_INCOMPLETE`.
G19's refreshed IF baseline retains two failed interior-Earth initializations;
the joint variants retain one, as do all other candidates. A changed numerical
seed count does not demonstrate resolved physical ambiguity or global uniqueness.
Snapshot preparation's unsupported cases do not prove that a different dynamic
preparation could not use their data.

In each quadruple below the order is **GF baseline / joint independent /
joint free drift / joint code rho=.5**. CODE shares upstream information with
reference products; it is a diagnostic, not independent truth. The 126 state
rows derive from five trajectories, with only five genuinely future epochs.

| Candidate | Position RMS, m | Velocity RMS, mm/s | Largest conditional position 1-sigma, m |
|---|---:|---:|---:|
| G05 | 155.983 / 155.982 / 134.520 / 155.983 | 13.034 / 13.035 / 10.741 / 13.034 | 44.242 / 44.240 / 130.034 / 44.241 |
| G11 | 93.534 / 93.565 / 187.898 / 93.567 | 11.898 / 11.901 / 24.021 / 11.900 | 214.005 / 213.998 / 275.214 / 214.003 |
| G19 | 87.988 / 87.981 / 57.880 / 87.995 | 26.549 / 26.547 / 20.447 / 26.549 | 366.271 / 366.259 / 733.318 / 366.267 |
| G20 | 18.298 / 18.288 / 65.415 / 18.293 | 17.006 / 17.006 / 21.408 / 17.006 | 200.062 / 200.055 / 250.070 / 200.060 |
| G21 | 242.372 / 242.392 / 171.708 / 242.383 | 25.468 / 25.470 / 22.870 / 25.470 | 68.458 / 68.455 / 149.382 / 68.457 |

With constant biases, MW moves the initial position vector by only
.006–.034 m under independent-band noise (.003–.033 m for rho=.5). It
improves position RMS in G05/G19/G20 and worsens G11/G21 under the first
scenario. The largest position and velocity formal axes shrink by only about
**.0033%**, or .0012% with rho=.5. This is a negligible conditional gain;
it is not a physically defensible reduction of the total error budget.

The large changes under free drift mostly reproduce the already exposed
IF-only free-drift behavior: adding MW to that prior model changes position
RMS by at most .022 m. Those tens-of-metres differences from the constant-bias
baseline must not be attributed to newly independent MW information. Free
bias rates still have a major effect on the inferred trajectory and formal
uncertainty. Candidate MW free rates reach .01892 m/s.

| Candidate | Position discrepancy at the one genuinely future epoch, m |
|---|---:|
| G05 | 152.005 / 152.005 / 130.662 / 152.005 |
| G11 | 90.256 / 90.288 / 185.866 / 90.289 |
| G19 | 81.112 / 81.109 / 50.280 / 81.120 |
| G20 | 13.105 / 13.117 / 64.225 / 13.108 |
| G21 | 248.196 / 248.216 / 176.511 / 248.207 |

All variants include 54/126 CODE positions and 3/5 future positions in nominal
conditional 95% ellipsoids. Joint-state inclusion is 34/34/54/34 of 126 and
0/0/3/0 of the five future epochs. These correlated comparisons do not qualify
coverage. Even hypothetical independent mean-clock-rate measurements at
.1 mm/s leave the largest position sigma near 41/202/338/185/64 m for the
five candidates under the constant joint model. Clock precision alone does
not remove the remaining geometry/bias modes.

### Excluded RF and new MW forecasts

All RF/MW comparisons retain 339 evaluated receiver pairs and one unavailable
pair; 313 are internal holdouts and 26 genuinely beyond all training.
Constant MW forecasts predict zero rate, independently of the raw covariance
scenario. Free-drift forecasts extrapolate only the fitted training rate.

| Quantity | GF baseline | Joint independent | Joint free drift | Joint rho=.5 |
|---|---:|---:|---:|---:|
| All holdouts: code RMS, m | 0.71177148 | 0.71176895 | 0.71259091 | 0.71177135 |
| All holdouts: IF phase RMS, mm/s | 8.570830 | 8.570825 | 8.560372 | 8.570831 |
| All holdouts: MW RMS, mm/s | not predicted | 5.924112 | 7.150087 | 5.924112 |
| Internal holdouts: code RMS, m | 0.69345237 | 0.69345106 | 0.69541255 | 0.69345266 |
| Internal holdouts: IF phase RMS, mm/s | 8.630722 | 8.630719 | 8.626111 | 8.630724 |
| Internal holdouts: MW RMS, mm/s | not predicted | 5.911592 | 7.111416 | 5.911592 |
| Genuine future: code RMS, m | 0.90361384 | 0.90360002 | 0.89384689 | 0.90360987 |
| Genuine future: IF phase RMS, mm/s | 7.813873 | 7.813842 | 7.725201 | 7.813872 |
| Genuine future: MW RMS, mm/s | not predicted | 6.072814 | 7.600201 | 6.072814 |

The constant independent-band model improves genuinely future code RMS by
only .000014 m and phase-rate RMS by .000031 mm/s: no material physical
advance. Code worsens in 155/339 pairs (10/26 future), phase in 171/339
(13/26 future), mostly by tiny amounts. For rho=.5 the counts are 179/339
(11/26) and 181/339 (13/26). Free drift worsens code in 168/339 (11/26),
phase in 150/339 (13/26) against the constant IF baseline; its aggregate
changes remain dominated by the previously known phase-drift assumption.
No variant is selected or promoted from these scores.

New MW forecasting is executable but **free drift worsens** RMS from
5.924 to 7.150 mm/s over all holdouts and 6.073 to 7.600 mm/s in genuine
future data. It worsens 231/339 pairs, including 18/26 future pairs. Small
training residuals cannot justify learning a deterministic temporal bias rate
from two noisy increments or rescaling the covariance to those residuals.

### Network support and common-case diagnostics

All variants retain 3,045 evaluated and 544 unsupported code rows out of
3,589. Constant models evaluate 2,643 phase rows; free drift evaluates 2,639,
with 402 unsupported continuity segments and four unidentified slopes in
addition to the 544 unobserved clock rows.

MW can evaluate **508 rows without an observed epoch clock**. Constant models
have 3,151 evaluated and 438 unsupported MW rows; free drift retains four
additional unidentified MW slopes, giving 3,147 evaluated. Compare only the
3,147 common MW rows when judging prediction quality: RMS is .239434 m
(independent constant), .254893 m (free drift), and .241382 m (rho=.5
constant); respective maxima are 1.935, 3.520 and 2.148 m. Missing support is
not an improvement in error.

On the 2,639 common phase rows, constant independent MW changes the baseline
RMS from 16.2530 to 16.2527 mm. Free drift remains poor: G19 RMS .588849 m,
maximum 7.875273 m; G20 maximum .729803 m. MW has not removed the unstable
short-segment IF slopes. These overlapping folds are not independent trials.

## Verification and next physical task

The complete local research regression run passes 912 tests, with one skip:
the optional HARDISP producer requires gfortran; its pinned products still
replay. All 15 updated combination and immutable-receipt checks also pass,
including both GF-null negative controls. Final validation is recorded on
[PR #229](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/pull/229),
along with final-head Linux/Windows CI and Codex review. The source revision
already passed all 19 CI checks. Historical source/receipt tests remain in
the suite; no hash or historical outcome is rewritten.

The new capability is a rank/covariance-correct IF/MW likelihood, reference
calibration, observable-specific unsupported outcomes and genuinely excluded
MW forecasts. The observed orbital information gain is negligible at these
weights and geometry. S2 remains open: no finite total uncertainty, absolute
clock datum or slip-robust reconstruction is established.

The next concrete research task is to qualify the temporal raw-code/phase
and receiver-shared error model before using MW to infer extra boundaries or
stable bias rates. The .285 m per-band code requirement for six-sigma separation
of the 9/7 case is about 24 times smaller than the first scenario's weighting
sigma. Under independent samples and constant biases alone, averaging would
require about 555 samples per side at 30 s cadence (about 4.6 hours); temporal
multipath and bias correlation can invalidate that gain. This is an information
requirement, not a proposed blind campaign or measured precision. Existing
reference-only data can first test bias-rate extrapolation and temporal/shared
error shapes, retaining unsupported slopes and GF-null counterexamples. Any
common nondispersive error still needs separately justified clock/path
information or additional geometry; MW cannot supply its absolute bound.
