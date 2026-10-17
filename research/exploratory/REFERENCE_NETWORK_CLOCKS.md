# Reference-only code/phase network clocks

## Physical intervention

The shared-wet experiment leaves the mean interval-clock weights responsible
for 81–97% of the **assumed conditional variance** along the weakest position
direction. It does not measure those clocks' physical error. Independent
per-station medians also discard the fact that multiple receivers observe the
same reference, and that clock offsets and increments use the same sources.

This increment implements an executable network calibrator, then passes its
joint clock measurements to the existing RF dynamic fit. It separates
receiver changes from a reference satellite's clock-product error shared by
its receiving stations. The intervention is one calibration model, with an
explicit sensitivity to phase/code bias stability, not a residual-selected
correction or a new orbit solver.

For admitted station s, reference q and epoch t, after the existing precise
geometry, OSB code translation and VMF3 propagation model:

```text
code residual(s,q,t)  = J(s,q,t) c(s,t) - e(q,t)
phase residual(s,q,t) = J(s,q,t) c(s,t) - e(q,t) + a(segment)
free-drift variant: add d(segment) (t - segment_start) / 3600
```

The clock derivative J includes the observation-time geometry response; the
geometry is recalculated until the estimated receiver clocks stabilize.
Receiver clocks and reference errors are free at every observed epoch. Float
phase/code offsets a are free per station/reference segment. No integer
ambiguity fixing is applied to the IF phase. The additional d is unpenalized,
in metres per hour, and represents a loss of the constant phase/code bias
assumption. It is not a calibrated stochastic model of wind-up or electronics.

The clock network chooses zero mean reference error at each epoch as its
datum. The common physical clock/product datum is not qualified by this
convention. Conditional covariance in that datum must not be interpreted as
an absolute clock bound. A disconnected receiver/reference graph fails rather
than silently anchoring another receiver.

The measurement model uses code sigma 20 m and phase endpoint sigma .02 m,
declared before scoring. These inherit the existing RF endpoint scales; they
are not inferred from the network residuals or demonstrated physical noise
laws. The old .01 m/s receiver mean-rate weighting is retained in the freshly
refitted baseline; the new variant derives its conditional clock information
from reference endpoints and graph geometry. Production defaults and every
historical floor/result remain unchanged.

## Implementation and correlations

`research/kinematic/network_clocks.py` profiles the receiver/reference clocks
per epoch with the existing GLS calibration-transfer primitive, then solves
the shared float ambiguities by SVD. Constant ambiguity cancellation is
equivalent to differencing within an admitted segment. Retaining phase levels
also couples code offsets and phase changes across epochs and arcs.

The clock covariance contains a conditional epoch block and the shared
ambiguity response. Transforming endpoint clocks into endpoint offset,
60-second mean and interval half-difference therefore retains offset/rate,
station, endpoint and cross-arc correlations. `dynamic_fit.fit` accepts an
optional covariance for all chronological arc observations and whitens them
jointly before profiling local nuisance parameters. Its historical independent
arc path remains the default and is tested against the joint block limit.

The information diagnostic conditions the fitted covariance on hypothetical
**independent** interval mean-rate measurements at 1e-5, 1e-4, 1e-3 and 1e-2 m/s.
It includes local/global cross covariance. These are additional-information
requirements within the conditional model, not admitted measurements or
promised physical accuracies. Another product sharing the same GNSS data is
not automatically such independent information.

## Access, support and predictions

Each of the original 22 candidate folds excludes its own orbit, clock, bias,
antenna and attitude records before numeric product parsing. Its own RF never
enters its network calibration. Other folds may use it as a reference. G12
products remain excluded throughout. No historical fitted candidate state
initializes any new trajectory.

The baseline RF preparation is repeated unchanged: all 440 windows and their
terminals remain, including insufficient support and RF geometry ambiguity.
Primary comparisons use the same prepared arcs. References can use the
existing full 30-second grid only up to the last target training endpoint.
For internal temporal holdouts, later training references may constrain
shared segment biases: these are not forecasts beyond all training. The final
future prediction uses the original fitted mean clock, with no future network
data and no quadratic clock extrapolation.

LLI rejection, gaps and elevation-mask exits break phase segments. Zero or
blank LLI is not proof of physical continuity. Unflagged jumps are neither
repaired nor removed: their residuals and model rejection remain visible.
Every seventh link-epoch is withheld deterministically for a separate network
fit. Missing clock or segment support remains in the denominator. Withholding
an entire time block leaves its free epoch clocks unidentifiable; the model
reports that fact instead of adding an unstated temporal prior.

All candidates' fits, conditional covariances and RF predictions are completed
before dedicated RF/CODE scoring. This preserves execution order on an
already exposed archive, not new blindness or prospective confirmation. CODE
shares upstream data with the reference chain and remains diagnostic.

## Verification and results

The reusable tests compare the profiled network covariance against full GLS,
including cross-epoch covariance. A shared reference perturbation, a receiver
perturbation and a single-link phase discontinuity are recalibrated through
the complete network. Candidate/product poisoning and future-value poisoning
check the access boundary. A rejected network model can retain an algebraic
orbit fit for sensitivity analysis, but its public terminal is
`REFERENCE_CALIBRATION_MODEL_REJECTED`; target residual acceptance does not
override reference model rejection.

Execution results are recorded in `results/reference_network_clocks_v1.json.gz`.
An initial development run was interrupted during G06 preparation after two
G05 algebraic fits, before any RF/CODE scoring, to include free phase drift
and withheld links. It produced no completed result artifact. The completed
execution retains all three variants and all failures.

All 22 candidates and 440 preparation windows remain. The same 63 arcs support
G05, G11, G19, G20 and G21; 17 candidates lack sufficient prepared arcs. Every
variant retains one interior-Earth seed failure per trajectory and the terminal
`BRANCH_SEARCH_INCOMPLETE`. This is neither two competing physical orbits nor
global uniqueness. The newly refitted baseline reproduces the v3 result.

In each table, the order is **baseline / constant-bias network / free-drift
network**. CODE discrepancies are diagnostic, not independent errors.

| Candidate | Position RMS, m | Velocity RMS, mm/s | Largest conditional position 1-sigma, m |
|---|---:|---:|---:|
| G05 | 156.13 / 158.42 / 126.63 | 12.544 / 12.568 / 11.527 | 754.40 / 44.24 / 130.03 |
| G11 | 88.51 / 231.96 / 305.96 | 13.022 / 3.138 / 20.690 | 4123.29 / 213.95 / 274.92 |
| G19 | 146.01 / 50.16 / 28.90 | 28.113 / 23.866 / 13.881 | 6857.00 / 366.27 / 733.32 |
| G20 | 66.20 / 122.41 / 158.07 | 22.209 / 21.183 / 18.976 | 3717.61 / 200.04 / 250.02 |
| G21 | 210.30 / 251.71 / 168.20 | 19.266 / 26.102 / 22.916 | 1252.93 / 68.46 / 149.38 |

Constant-bias position RMS worsens for four of five trajectories. Free drift
improves three and worsens G11/G20. These outcomes do not select a production
correction. The 126 state rows come from five trajectories. CODE positions lie
inside the nominal conditional 95% ellipsoids in 126/126 baseline rows but only
54/126 rows in **each** network variant. For the five genuinely future epochs
the counts are 5/5 versus 3/5 and 3/5. Those correlated diagnostics are not a
coverage estimate; they directly oppose interpreting smaller formal covariance
as qualified physical accuracy.

| Candidate | Position discrepancy at its one genuinely future epoch, m |
|---|---:|
| G05 | 152.41 / 153.55 / 122.05 |
| G11 | 83.06 / 233.04 / 307.87 |
| G19 | 141.70 / 48.91 / 19.99 |
| G20 | 77.02 / 114.84 / 152.79 |
| G21 | 214.72 / 257.00 / 172.30 |

| RF comparison | Evaluated pairs | Code RMS, m | Phase rate RMS, mm/s |
|---|---:|---:|---:|
| All temporal holdouts, including genuine future | 339 + 1 unavailable | .76870 / .71023 / .71314 | 8.48537 / 8.52504 / 8.51468 |
| Beyond all training | 26 | .84029 / .88764 / .88704 | 6.97953 / 6.89720 / 6.93034 |

On all 339 paired predictions, code worsens in 139/144 and phase in 195/185
cases for constant/free drift respectively. On the 26 genuine-future receiver
predictions, code worsens in 14/26 and phase in 8/26 for either network variant.
The aggregate code improvement mixes internal holdouts with genuinely future
prediction; it must not conceal the latter's worsening.

Network withholding evaluates 3045 of 3589 link-epochs in either variant;
544 have no observed clock/reference/segment support after withholding and
are retained. These folds overlap and share products. Constant-bias phase
prediction RMS is 22.3–30.5 mm by candidate. Free drift gives 18.6–24.4 mm in
four candidates but **565.7 mm for G19**, with a 7.865 m maximum on an excluded
link-epoch. Weak short-segment slope information must not become a transferable
phase correction. These failures remain even though training cost decreases.

All joint network global chi-square p-values round to one under the declared
mixed code/phase weights. Nevertheless phase residual maxima are .272–.406 m
with constant biases and .227–.454 m with free drift. A global low cost with
conservative code weights does not establish local phase continuity, a noise
law, or absolute timing precision. The public network status remains
`CONDITIONAL_MODEL_ONLY`, never physical qualification.

The synthetic one-metre reference-common perturbation changes receiver
contrasts by at most 4.1e-8 m in the numerical network model. This is a
cancellation check, not a measured clock precision. A single-link phase
perturbation leaks .119–.161 m into the largest receiver contrast; the retained
residual distinguishes it from a common reference clock but cannot make the
receiver estimate immune to arbitrary link errors.

### What extra timing information would constrain

For the **free-drift** fits, hypothetical independent interval mean-clock
measurements give the following largest conditional position sigmas:

| Candidate | Present, m | At 1 mm/s, m | At .1 mm/s, m | At .01 mm/s, m |
|---|---:|---:|---:|---:|
| G05 | 130.03 | 57.44 | 41.19 | 40.42 |
| G11 | 274.92 | 218.57 | 202.23 | 198.88 |
| G19 | 733.32 | 368.08 | 337.95 | 332.06 |
| G20 | 250.02 | 214.02 | 185.29 | 181.98 |
| G21 | 149.38 | 79.42 | 64.27 | 63.14 |

For a 60-second mean, .1 mm/s corresponds to about 20 ps of accumulated clock
difference (sigma * 60 / c). These are hypothetical independent observations,
not Internet time-service capabilities or existing GNSS clock precision.
Within this conditional model the gain already approaches a plateau there:
simply tightening receiver mean-clock weights cannot remove the remaining
geometry/bias/model limitations. Small residuals and another correlated orbit
or clock product cannot supply that independent information.

As an additional algebraic requirement calculation from the stored free-drift
global covariance C, conditioning its constant code-contrast block b on an
independent sigma=.01 m measurement uses
`C - C[:,b] (C[b,b] + sigma^2 I)^(-1) C[b,:]`. The largest position sigmas remain
58.12, 190.66, 384.03, 233.16 and 91.61 m respectively. Those hypothetical bias
measurements alone also do not qualify or solve the full physical budget.

The next concrete obstacle is to bound or identify the phase/code temporal
terms and their propagation/reference coupling, using the observed continuity
witnesses rather than attributing every common residual to receiver clocks.
The calibrator and joint solver are usable for that intervention; neither
network variant is promoted to a qualified physical correction.

The exposed BRAZ/G13 anomaly also has a geometry-free change of -0.425056 m
at GPST 38040 and -0.202117 m at 38070, while both LLI fields remain zero.
The [geometry-free combination](https://gssc.esa.int/navipedia/index.php?title=Detector_based_in_carrier_phase_data%3A_The_geometry-free_combination)
removes a scalar clock common to the two frequencies. Such a clock alone
therefore cannot explain this witness; ionosphere, instrumental changes,
tracking/phase discontinuities and other frequency-dependent errors are not
distinguished by it. No causal cycle-slip diagnosis or automatic repair is
claimed, and absence of a geometry-free jump would not qualify continuity.

## Remaining physical scope

Common product-clock datum, reference orbit and attitude errors, code/phase
bias stability, phase wind-up, unflagged continuity, terrestrial coordinates,
atmosphere and force-model errors, and shared reference/target errors remain
unqualified. The supplied diagonal endpoint noise is one declared conditional
component, not a claim that these omitted physical sources are zero.

Clock definitions on IF code and phase instrumental terms follow the
[ESA measurement model](https://gssc.esa.int/navipedia/index.php/Combining_pairs_of_signals_and_clock_definition).
[Carrier wind-up](https://gssc.esa.int/navipedia/index.php/Carrier_Phase_Wind-up_Effect)
is phase-specific and depends on antenna orientation; no target attitude or
unsupported receiver orientation is introduced to correct it here. A free
linear link drift exposes one consequence of relaxing stability, without
claiming to represent all temporal behavior. No finite total uncertainty,
global uniqueness, population coverage, S2 completion or S3 campaign follows.
