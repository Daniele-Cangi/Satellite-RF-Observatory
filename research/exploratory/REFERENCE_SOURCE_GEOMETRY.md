# Wet-source geometry and coupled reference/candidate response

## New information and scope

The preceding network-closure increment exposed a large reference-only state
sensitivity, but did not assign that arbitrary link pattern to a real physical
source. This increment restricts the perturbation to **one constant signed
zenith wet residual per station**. Its admitted VMF3 mapping differs for each
reference and for the candidate. The same station vector must cross both the
reference-clock calibration and the candidate path.

The [GNSS observable model](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables)
and [tropospheric delay model](https://gssc.esa.int/navipedia/index.php?title=Tropospheric_Delay)
motivate a wet delay affecting code and carrier equally, with a separate wet
elevation mapping. The particular error amplitude, constancy over the hour,
isotropy and attribution to weather are **assumptions of this restricted
development model**, not measurements supplied by those equations or by VMF3.
Other propagation, reference-product and instrument errors can imitate it.

The executable addition estimates those coefficients using only non-candidate
reference RF after profiling all clocks and phase/MW float biases; predicts
excluded future links with that fitted shape; and composes the physical source
response through calibration and trajectory fitting. It reuses the existing
network runner, wet propagation model, calibration derivative and dynamic
solver. It introduces no new experiment framework or authority.

The same 22 candidates, 440 windows and preparation rules remain. Each fold
excludes its own candidate products before numeric parsing. Candidate geometry
for the response comes from the current RF-only estimate, never a CODE state.
It supplies a local sensitivity evaluation, not a propagated state seed for
the new fits. Every trajectory fit starts from the ordinary RF initializer.
No new candidate CODE state score is performed and G12 orbit remains unopened.

## Reference source information

For station s and reference q, the raw path column is
`G_r(s,q,t,s)=M_wet(s,q,t)`, repeated in IF code and IF phase and zero in MW.
Reference geometry uses the admitted non-target product chain, station
coordinates, clock-corrected observation time and the existing VMF3 mapping.
Recorded times remain GPST seconds; atmospheric evaluation uses UTC MJD with
the inherited 18 s conversion. All coordinates and state vectors retain the
existing ECEF, emission/reception and Earth-rotation conventions.

At each epoch profile the actual clock design with its GLS gain K_e. Whiten
`(I-A_e K_e) G_r` with the **original** endpoint weighting covariance, then
remove the globally profiled ambiguity left-singular-vector space U:

```text
J = (I-U U^T) stack[ W_e (I-A_e K_e) G_r,e ]
z_hat = J^+ r_whitened
C_z = V diag(1/singular_value^2) V^T
```

This is the Frisch–Waugh–Lovell joint source solution, including every phase
and MW float bias. No residual variance rescales C_z. It is **conditional
parameter precision under historical weights**, not a measured weather-process
covariance. Full rank concerns this restricted model and nuisance set; it
does not identify a unique physical cause or bound omitted error families.

The 1e-10 numerical resolution threshold is relative to the original weighted
source design, rather than a wholly projected near-zero matrix. A source
exactly absorbed by clocks remains `SOURCE_RANK_DEFICIENT`; projection
roundoff cannot invent a source estimate. Unresolved bases remain explicit,
without a ridge, arbitrary anchor or zero-amplitude null completion. Negative
inferred total wet delay is retained as a failed necessary physical-domain
check; coefficients are not clipped to improve predictions.

## Excluded-link transfer

Reuse the fixed SHA-256 link rule and last-third exclusion of the preceding
increment. Remove all channels of each excluded link before rebuilding GF
segments, fitting its source coefficients or estimating clocks/biases. Fit z
from the retained reference network, subtract G_r z, refit the clock/bias
network and predict an excluded link as `clock_prediction + M_wet z`. A phase
level uses only its last prefix float bias in the same original flag/gap base
segment; later GF values cannot choose or repair a segment. Paired increments
cancel unknown constant phase levels. An unresolved source model is a terminal
outcome, not a fallback to nominal clocks.

Full-window source estimates never enter this separate training fit. Other
links at the excluded later epochs remain admitted. Geometry, masks and
observation-time linearization were prepared by the nominal full calibration,
so this is **conditional future-link transfer**, not an independently
relinearized acquisition experiment or an RF-free future clock forecast. The
archive and preceding scores are already exposed. Ordering estimates and
predictions before dedicated scoring creates no new prospective blindness.

## Both physical paths and finite checks

Let L be the current RF trajectory's response in original observation ordering,
with masked IF/MW increments restored as zero columns. Apply the reference
network's complete fixed-estimator response to G_r to obtain R_r, including
all refitted float biases. Build G_c from the RF-only fitted candidate geometry:
code has M_wet, phase rates its interval differences, and MW/clock/ground model
rows are zero. Clock-data rows themselves contain mixed units: offset metres,
mean-rate m/s and contrast-rate m/s, explicitly recorded in the artifact.

A **positive assumed wet-model correction** increases candidate modeled delay
and subtracts the same source's modeled delay from reference observations.
Its conditional state responses are therefore

```text
T_reference = -L_clock R_r
T_candidate = -L G_c
T_coupled   = T_reference + T_candidate
```

The common source vector is summed through both paths before computing a
gain. Treating the appearances as independent would lose their signed cross
terms. The three reported responses distinguish cancellation from constructive
addition without assuming that either occurs for every geometry.

The leading position right mode of T_coupled supplies a fixed **.01 m coherent
RMS over station zenith coordinates**, selected without source-estimate
amplitudes, CODE or excluded RF scores. This is not .01 m per raw link, a peak
bound or a noise sigma. The artifact retains all station coefficients, peaks
and induced reference path amplitudes. The same vector is used for the
reference-only, candidate-only and coupled finite interventions.

For the reference path, rerun the candidate-excluding network calibration with
shifted zenith wet models, including observation-time relinearization and all
clock/float-bias refits. Reference support and GF segments must match; a change
is retained as failure, with no replacement. Reusing nominal **reference clock**
centres initializes this numerical recalibration, not a candidate orbit. For
the candidate path, recompute VMF3 at each nonlinear trial's current geometry.
Every trajectory fit is cold-started from RF. Predictions use the same shifted
wet path at their excluded endpoint.

Hold the nominal trajectory weighting matrix fixed while comparing model
means. The recomputed reference-clock covariance change is recorded in its
dimensionless whitened metric, but is not admitted as a new noise law. The
conditional global covariance remains distinct from total uncertainty. The
original additive-delay-to-vacuum-light-time convention is preserved.

Synthetic controls verify the source profile against dense joint GLS, reject
a wholly clock-aliased wet design, poison excluded IF/GF values, and compare
all three response maps with full recalibration/trajectory refits. A shared
receiver-clock **drift** cancels only when its candidate contribution is
included. In this fixture, a constant receiver offset has negligible
reference-only state response through its trade with free code contrasts, so
it is not used as evidence for a material state cancellation.
The numerical resolution threshold remains unchanged.

## Execution and reproducibility

Numerical producer: `4e42110c32f35ce406559d5056402050456b8911`, based on
`708a4530197d4e6fa3ea72304cceed7251671bf6` (merge #232). Its **65 focused tests**
pass in 77.83 s, including source geometry/admission, dense GLS, complete
reference/candidate refits, clock-drift cancellation, scoring order and the
historical wet, temporal, shared-structure and closure regressions/receipts.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --sources NEW_OUTPUT.json.gz
```

The runner refuses an existing output. Historical artifacts and their original
source bytes remain immutable through Git ancestry. This execution creates a
new gzip artifact with timestamp zero; the new receipt verifies its hashes,
all terminal counts, source profiles, both response paths, conditional
future-link predictions and excluded RF scoring. It does not rerun every
nonlinear trajectory fit inside CI.

Artifact: [`results/wet_source_coupling_v1.json.gz`](results/wet_source_coupling_v1.json.gz),
8,094,718 bytes, SHA-256
`5bc2598b04ac628bd74d33a645019615cd2c23eb6112512a70c7727b9b8ed213`.
The execution completed without a global preparation failure. The new receipt
passes in 24.60 s: **66 focused tests verified**, including the 65 producer
tests. Local runtime: Python 3.13.7, NumPy 2.3.3, SciPy 1.17.1, BLAS/OMP threads 1.

All four variants retain 22 candidates, 440 windows and 63 prepared arcs. The
five supported folds are G05/G11/G19/G20/G21. Each variant has five
`BRANCH_SEARCH_INCOMPLETE` fits, each with one failed internal initialization;
17 `INSUFFICIENT_PREPARED_ARCS` outcomes remain. These failures establish
neither two physical orbits nor global uniqueness. Fixed snapshot preparation
does not prove universal data insufficiency for the unsupported candidates.
The five reference folds reuse 25,117 row occurrences, not independent trials.

## What the reference geometry can estimate

All five full-window profiles and all five excluded-link training profiles
resolve **6/6** station coefficients in this restricted model. Full-window
residual corrections range from -2.770 to +60.455 mm; the sole negative one is
STJO in the shorter G19 fold. Training-only corrections range from -4.998 to
+49.936 mm. Every fitted total wet delay remains positive at its recorded
reference samples. This passes a necessary domain check, not a weather-accuracy
or physical-source attribution test.

| Fold | Full-profile correction range (mm) | Conditional marginal precision range (mm) | Minimum fitted total reference wet (m) |
| --- | ---: | ---: | ---: |
| G05 | 13.452 to 42.002 | 1.694 to 4.653 | .104754 |
| G11 | 13.933 to 36.774 | 1.635 to 4.695 | .104833 |
| G19 | -2.770 to 60.455 | 5.289 to 19.050 | .110134 |
| G20 | 14.035 to 42.276 | 1.853 to 4.735 | .105049 |
| G21 | 16.600 to 45.549 | 1.958 to 6.359 | .106626 |

The precision column is sqrt(diag(C_z)) under the original endpoint weights
and their independent raw-link/epoch scenario. Earlier temporal/shared-error
results did not qualify that scenario as physical covariance. The many reused
RF rows, six coefficients and five overlapping folds do not become independent
weather measurements. Bias, propagation and reference-product errors omitted
from this restricted source set can project onto the same fitted shape.

## Transfer to excluded reference links

Both models retain **1,316 predictions out of 1,494 excluded rows** over 61
held-link occurrences. The same 178 rows remain `UNOBSERVED_NETWORK_CLOCK`,
with no extrapolation or source fallback. Phase levels have a usable prefix
in 1,298 rows; 18 predicted clocks have no admitted phase-bias level. Their
constant level is unnecessary for the paired increment scores. The separate
held-link clock/bias and source fits never use the excluded IF/GF values;
the upstream nominal geometry/time conditioning remains explicit.

| Fold | Pairs 30 / 300 s | Phase increment RMS at 30 s, clock-only -> wet (mm) | Phase increment RMS at 300 s, clock-only -> wet (mm) |
| --- | ---: | ---: | ---: |
| G05 | 276 / 203 | 9.857 -> 9.881 | 16.075 -> 15.852 |
| G11 | 230 / 174 | 9.214 -> 9.207 | 13.723 -> 13.043 |
| G19 | 124 / 43 | 7.810 -> 7.770 | 18.379 -> 17.007 |
| G20 | 352 / 261 | 9.256 -> 9.287 | 15.268 -> 14.692 |
| G21 | 288 / 198 | 9.228 -> 9.307 | 14.246 -> 13.825 |

At 300 s the wet shape lowers phase RMS in all five folds, pooled
**15.113 -> 14.595 mm** over 879 pairs. At 30 s it worsens three folds and
pooled RMS, **9.247 -> 9.274 mm** over 1,270 pairs. Absolute phase errors
worsen in 647/1,270 short pairs and 413/879 long pairs. The five-fold agreement
at 300 s is exploratory transfer evidence for this structured component, not
five independent confirmations or a measured stochastic wet covariance.

Code increment RMS changes from 1.287255 to 1.287290 m at 30 s and from
1.335618 to 1.335590 m at 300 s. Code RMS worsens in every fold at 30 s and in
G21 at 300 s; absolute code errors worsen in 608/1,270 and 382/879 pairs.
Across all 1,316 predicted levels, code RMS worsens from .973382 to .974135 m.
Across the 1,298 supported phase levels, phase RMS improves from 21.194 to
16.574 mm, with per-fold phase-level RMS improving in all five. All individual
levels, increments, means, second moments and missing cases are retained.

No lag or sign is selected afterward, and no smaller raw floor is inferred
from these filtered predictions. The constancy assumption transfers better on
some diagnostics than others. Other RF at the same later epochs is still
required; the whole future network remains unidentifiable with free epoch
clocks. Upstream nominal timing/mask conditioning remains as stated above.

## Coupled finite state response

All five source recalibrations preserve reference support and GF segments.
The nominal-whitened change in recalculated clock covariance is at most
2.12e-7; trajectory weights nevertheless remain exactly the nominal ones.
Every source probe has .01 m **station-zenith RMS**, peaks .0177–.0214 m,
and produces .0211–.0278 m RMS reference path changes with .0635–.1193 m
peaks. These coordinates differ from the preceding arbitrary raw-link probes;
their numerical gains must not be compared as though the input error spaces
were identical. Minimum total reference wet under each finite probe remains
at least .0813 m at its recorded samples.

The table gives actual full recalibration and fresh RF trajectory refits, using
the **same** zenith vector within each fold. Changes are state differences at
the fitted ECEF/GPST epoch, not CODE discrepancies or measured orbital errors.

| Fold | Position change reference / candidate / coupled (m) | Velocity change reference / candidate / coupled (mm/s) |
| --- | ---: | ---: |
| G05 | 2.675 / .915 / 3.515 | .166 / .059 / .137 |
| G11 | 3.481 / 3.175 / 6.605 | .265 / .236 / .434 |
| G19 | 4.271 / 14.250 / 15.184 | .686 / .809 / 1.313 |
| G20 | 7.715 / 10.253 / 17.092 | 1.179 / .913 / 2.089 |
| G21 | 3.130 / .439 / 3.378 | .372 / .046 / .346 |

**Position contributions add constructively in all five selected modes**:
the coupled norm exceeds either partial norm. Velocity partly cancels in G05
and G21. Shared-source coupling is therefore not a presumption of cancellation;
the receiver-clock control and the actual wet geometry answer different
physical questions. Neither perturbing calibration alone nor adding independent
copies of the two responses represents this common source.

Maximum finite-minus-linear position differences are .000092 m for the
reference path, .000423 m for the candidate path and .000418 m for the coupled
path. Maximum corresponding velocity differences are .0000158/.0000731/.0000731
mm/s. Full conditional reference relinearization and nonlinear target refits
agree with the local composition at these amplitudes. This verifies a restricted
source response, not a global nonlinear physical bound.

The coupled leading position direction has absolute alignment
.150/.857/.521/.949/.540 with the largest nominal conditional position axis in
G05/G11/G19/G20/G21. It is not automatically the clock-blind weak direction of
the previous unrestricted link-error analysis. Nominal largest position axes
remain 44.24/214.00/366.26/200.06/68.46 m, changing by less than .0003% in
these fixed-source fits. The source's unknown uncertainty is not marginalized
into those nominal axes; they remain conditional, not a total error budget.

## Information requirements in this source geometry

The coupled singular-value gains give the following **coherent zenith-vector
RMS amplitudes** for 1 m position or 1 mm/s velocity in the local model. They
are sufficient vector-norm limits within this family, not iid sigmas or
achieved physical measurement precision.

| Fold | Zenith RMS for 1 m position (mm) | Zenith RMS for 1 mm/s velocity (mm) | Leading normalized wet functional for 1 m position (mm) | Reference conditional precision of that functional (mm) |
| --- | ---: | ---: | ---: | ---: |
| G05 | 2.845 | 25.343 | 6.969 | 1.974 |
| G11 | 1.514 | 16.162 | 3.709 | 2.119 |
| G19 | .659 | 7.157 | 1.613 | 9.440 |
| G20 | .585 | 4.085 | 1.433 | 1.975 |
| G21 | 2.960 | 21.478 | 7.251 | 2.404 |

For unit right mode q, the functional is q^T z. Its conditional reference
precision is sqrt(q^T C_z q); its 1 m leading-mode requirement is 1/sigma_max,
whereas the full-vector RMS requirement includes sqrt(6). A separate independent
measurement of this functional could constrain that **one** mode at the stated
scale if the source law were valid. Other modes and error families would still
need bounds. Reference precision projected through this functional corresponds
to .283/.571/5.852/1.378/.331 m under the declared weighting model. These are
precision diagnostics, not true orbit uncertainties or terms added to a new
total covariance. In particular, temporal/shared raw errors remain unqualified.

The result supplies a concrete geometry and precision target for independent
zenith-delay information, rather than treating a generic calibrated clock
residual as a weather measurement. It also identifies the shorter G19 window
as much less informative under this source model. No such independent
meteorological error measurement is admitted in this execution.

## Candidate RF predictions and remaining obstruction

Each variant retains 339 evaluated station-window pairs and one unavailable
pair: 313 interleaved temporal holdouts and only 26 beyond all respective
training, from five trajectories. These probe predictions do **not** apply
the data-estimated wet coefficients to the candidate; they use the fixed
geometric intervention described above. Source-fit transfer and finite state
response remain distinct results.

| Variant | All code RMS (m) | All IF phase-rate RMS (mm/s) | Beyond-training code RMS (m) | Beyond-training phase-rate RMS (mm/s) |
| --- | ---: | ---: | ---: | ---: |
| Nominal | .711769 | 8.570825 | .903600 | 7.813842 |
| Reference-only probe | .711918 | 8.571361 | .904094 | 7.811761 |
| Candidate-only probe | .711804 | 8.571025 | .903878 | 7.812305 |
| Coupled probe | .711953 | 8.571563 | .904373 | 7.810225 |

The coupled probe worsens absolute code/phase errors in 172/339 and 164/339
pairs, with all-pair RMS worsening in 4/5 folds for both channels. For the 26
genuinely future pairs, code worsens in 16 and phase in 13; future RMS worsens
in 3/5 folds for each. The reference-only case worsens 176/339 code and 169/339
phase errors, and 15/26 future code and 7/26 future phase errors. Its future
code RMS worsens in 5/5 folds, phase in 2/5. The candidate-only case worsens
168/339 code and 167/339 phase errors, and 16/26 future code and 12/26 future
phase errors; future RMS worsens in 3/5 and 2/5 folds. MW predictions remain
unchanged in these constant-bias variants. None of these small RF differences
selects a probe sign, correction, weight or claim of position accuracy.

The new information is useful: the restricted wet field is conditionally
estimable from reference geometry, has measurable long-lag transfer and a
verified joint state response. It does not qualify source attribution, a raw
stochastic error law or the absolute reference datum. A constant station wet
field cannot be promoted from its improved 300 s phase scores while ignoring
the short-lag and code worsening.

The next concrete obstruction is to separate this admitted wet shape from
other nondispersive source geometries and stable link biases, while retaining
their matching candidate coupling. Reference orbit/antenna errors need their
own admitted line-of-sight mapping; an unknown target-product error must not
be imported as a candidate prior. Independent wet information would test the
specific millimetre-scale functionals above, while timing/bias information is
still needed for the remaining clock-blind directions. Another supplier alone
does not establish an independent datum.

S2 remains open. No new physical covariance, production floor, historical
outcome, G12 state reveal or S3 campaign follows from this increment.
