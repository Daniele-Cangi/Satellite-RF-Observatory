# Weak source combinations: physical recovery and independent information

This exploratory increment follows
[the source-separation study](REFERENCE_SOURCE_SEPARATION.md). It asks which
weak source combinations are numerically stable, whether a known physical
increment can be recovered, which combinations affect the candidate state,
and what independent information would resolve them. The archive is already
exposed; no result here is prospective confirmation or a physical error budget.

The retained subspaces are stable under equivalent coordinates and rotations
of the same clock-basis space, but not under the rank threshold: the selected directions rotate
substantially. All 30 exact linear controls recover their identified source
projection; all 20 weak finite physical probes fail the injected-functional
criterion. The projected finite forward defect is 14--1282 times the intended
weak signal. This execution therefore does **not qualify physical recovery of
the weak source combinations**. Their selected centimetre-scale perturbations
have very small local candidate-state effects, unlike the much larger wet-field
probe of the preceding study. Large formal source uncertainty is not a measured
physical amplitude or an orbital error bound.

## Physical model and retained boundary

The existing source module and runner are extended. Every own candidate is
excluded from numeric reference product/RF arithmetic, including the new
perturbation provider. The previous source-separation artifact is verified
before decoding, and its original bytes remain immutable. Its nominal RF-only
state and derivative are used for local sensitivity and after-fit comparisons;
new trajectory fits always cold-start from their RF initializer.

The preceding model held reference emission and relativistic clock response
fixed in its APC Jacobian. The new complete derivative also differentiates
those terms. A reference product perturbation is constant in its admitted
RTN frame over the fold. The perturbed COM velocity includes the derivative
of that moving frame. The existing emission solver then recomputes the
relativistic correction, clock and emission epoch. Admitted attitude maps
body antenna offsets at that epoch; the full Sagnac and VMF3 paths follow.
A constant RTN product-trajectory residual is a model of a product error;
it is not asserted to be a new gravitationally propagated satellite orbit.
Antenna PCV and a physical source-process covariance remain outside this law.

The implementation uses `delta_rel = -2 r.v / c^2` and the implicit emission
derivative. With product clock derivative `cdot` and source clock derivative
`dc`, `dtx = -dc/(1+cdot)` for a fixed measured code. The range/atmosphere
Jacobian includes the resulting APC time shift, reception-frame rotation
and satellite clock term. For hardware bias, the declared physical law is a
P1-only constant correction yielding the requested IF code shift: P1 changes
by `-b_IF/alpha` before emission inference. Its IF phase timing response and
constant MW response are included. The latter remains profiled by the existing
free MW segment level. This is one specified hardware law, not identification
of all raw-channel biases.

The conventions follow ESA Navipedia's
[relativistic clock correction](https://gssc.esa.int/navipedia/index.php/Relativistic_Clock_Correction)
and [emission/reception frames](https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation).
Direct finite product and hardware-time perturbations test the complete
analytic derivatives independently of the source-profile algebra.

## Stability and candidate relevance

The declared source metric is Euclidean metres across the listed source
coordinates. The whitening law remains the historical independent raw-link/
epoch weighting scenario. This is not an inferred physical stochastic law.
The source Jacobian is profiled after all epoch clocks and phase/MW floats.
The original source scale is retained before profiling.

Three relative rank thresholds, `1e-9`, `1e-10`, `1e-11`, are reported together.
None is chosen from held scores. Signed permutations, orthogonal coordinate
rotations and a global metre-to-millimetre conversion preserve the declared
metric. Their retained projectors and ranks are compared rather than demanding
individual singular-vector signs or orientations. An equivalent rotated basis
of the same zero-mean reference-clock space is also refitted. It does not add
an independent datum or impose an arbitrary reference anchor. Separately,
setting the observation-time clock derivatives to one is a **different-model
ablation**, not an equivalent choice of coordinates or a proposed correction.

Let `J=U S V^T` be the profiled reference source design and `T` its complete
source-to-candidate state map. `T` includes the calibration path and the same
station wet field on the candidate path; the remaining source columns are
explicitly reference-specific. Within the retained band below `1e-8` of the
original scale, the leading position response of `T V / S` selects a weak
combination. This targets weak combinations relevant to the candidate rather
than merely the smallest singular value. The strongest reference singular
vector is the recovery control. Selection uses training geometry and the
archived RF-only local derivative, never CODE or excluded scores.

## Known increments and finite recalibration

The fixed amplitudes are **.01 and .1 m total source-coordinate norm**, not
per-link RMS or measured source sigma. Each fold plans positive strong probes
at both amplitudes and positive/negative weak probes at both amplitudes: six
reference interventions. A negative total sampled wet delay or changed
support/segments is retained as a failed probe, with no clipping or replacement.

Each intervention computes the complete model-subtracted reference rows at
the nominal receiver clock centres. The change of the receiver-clock
linearization coefficient times that centre is removed to recover the finite
physical observation increment. These are incremental synthetic networks:
unknown real residuals and phase/MW levels do not supply the known truth.
A parallel noiseless control uses the exact linear source design. Both pass
through the same clock/float/source fitting. Recovery is evaluated against
the identifiable projection of the injected source, not a forced completion
of its null coordinates. Full projection error and the injected scalar
functional are reported separately; the declared relative recovery criterion
is `1e-3` for each. A conservative floating-point forward-difference scale is
retained to distinguish unresolved tiny signals from physical model failure.

The two positive weak probes additionally rerun the complete observation-time
reference calibration and cold-start the candidate RF trajectory. Candidate
wet geometry is recomputed during that fit. Target weights stay at their
nominal values to isolate the mean-model intervention; recomputed source/
clock parameter precision does not become a new noise law. All interventions,
recoveries and candidate predictions precede dedicated RF/MW scoring.
The fixed free-reference-clock nuisance law remains conditional. This is not
a new experiment identifying the true physical source amplitudes.

## Hypothetical independent information

For each of the three source-rank cases, the retained reference information
is compressed as `S_r V_r^T`. Hypothetical independent measurement rows `H/sigma`
are appended to it, preserving its unresolved source directions. No missing
source direction receives zero uncertainty. The augmented numerical rank
threshold is `1e-12` relative to its own largest singular value; a state or
weak functional must annihilate the remaining null space to relative `1e-8`
before complete conditional precision is issued.

The designs observe wet, RTN, antenna or stable hardware source coordinates,
wet plus RTN, all source coordinates, unique receiver-clock endpoints, or
an ideal measurement of the selected mixed weak functional. Coordinate
measurement sigmas are the fixed scenarios `.0001, .001, .01, .1, 1 m`.
Clock rows represent ideal observations of source-induced endpoint shifts in
metres of light time; shared endpoints are counted once and intervals are not
counted as additional independent measurements. An ideal mixed-functional observation is an information
benchmark, not a claim that an available instrument directly observes it.

Position and velocity diagnostic sigmas are the square roots of the largest
eigenvalues of their separate 3-by-3 state-information image covariance blocks.
They are largest principal-axis one-sigma scales, not RMS position errors.

The resulting precision is a **source-information diagnostic under declared
weights and measurement assumptions**. It is not added to the RF covariance,
a measured source covariance, prospective coverage or total orbit accuracy.
The 1 m position / 1 mm/s velocity levels are design benchmarks only. No actual
independent measurements, noise floors, CODE state score, G12 state or S3
campaign are admitted in this increment.

The retained rows also permit a geometry-only comparison of the selected mode
at each rank threshold: repeat the `T_pos V_weak / S_weak` selection with that
threshold, normalize the resulting source vector, and report its absolute
dot product with the canonical `1e-10` vector. This compares orientations
without attaching meaning to SVD signs. Only the canonical direction receives
the six finite interventions; changing that direction after scoring is not
part of this execution. The reported projected forward defect is computed by
applying the same whitened clock/float residual projector to each stored finite
increment and comparing it to `J delta`. Neither diagnostic uses held scores.

The `receiver_clock_endpoints` information design is specifically an **ideal
observation of the source-induced calibration shift** `K_endpoint G delta`.
It uses unique endpoint rows, with the declared free-reference-clock law and
nominal calibration map held fixed. It does not augment the full RF likelihood
with a real external receiver-clock measurement, its receiver/reference-clock
nuisances and calibration noise. Consequently its sigma grid is an optimistic
source-functional benchmark, **not an instrument timing requirement**. Actual
clock-assisted source/state precision would require that joint likelihood and
would also change the calibration/state response. The direct source-coordinate
measurement scenarios do not have this additional clock-translation issue;
they remain hypothetical observations of the stated constant-fold sources.

## Retained execution and stability results

Executed on 17 October 2026 with Python 3.13 and one OpenBLAS/OMP thread.
The numerical producer is `a52202088aa2204507e0e5d3f37fb489b31a0f80`,
the direct parent of the original result commit `0bf04a3f6531643cef1642d4d8a9abfd97658da5`.
Both local Git and the GitHub Git-commit API verify that ancestry; the offline
receipt additionally requires `git merge-base --is-ancestor PRODUCER HEAD`. Run:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --weak-sources research/exploratory/results/weak_source_physical_recovery_v1.json.gz
```

The retained compressed artifact has 14,963,675 bytes and SHA-256
`917202d0184c4bed1b8925d98818df6c4e0a14af1ad2b9eb2524f5dd001b3717`.
It binds the prior artifact, original inputs, weather receipt and producer
source bytes. All 22 candidates, 440 windows, 63 prepared arcs and 25,117
reference-row occurrences are retained. All 30 planned finite interventions
are prepared without support/domain failures. Each RF amplitude retains 17
`INSUFFICIENT_PREPARED_ARCS` and five `BRANCH_SEARCH_INCOMPLETE` outcomes;
each supported fit still has its failed interior branch. No rejection is
relabeled as physical qualification.

| Fold | Source count | Rank 1e-9 / 1e-10 / 1e-11 | Position gain at those cuts (m per unit weighted reference norm) | Mode alignment with canonical: 1e-9 / 1e-11 |
|---|---:|---|---|---|
| G05 | 197 | 121 / 129 / 133 | 843.81 / 862.88 / 1058.77 | 0.8077 / 0.0156 |
| G11 | 197 | 122 / 129 / 132 | 14.19 / 17.84 / 76.76 | 0.1832 / 0.0076 |
| G19 | 182 | 104 / 110 / 115 | 550.69 / 558.96 / 563.40 | 0.0652 / 0.1344 |
| G20 | 198 | 121 / 130 / 133 | 11.51 / 23.61 / 180.26 | 0.0200 / 0.0048 |
| G21 | 193 | 116 / 124 / 128 | 609.31 / 613.78 / 766.29 | 0.8512 / 0.0156 |

At the canonical cut, equivalent source transforms retain the same ranks;
the largest projector difference is `1.80e-8`, and normalized singular-value
differences are below `2.32e-16`. Rotating the same reference-clock basis
changes the profiled design by at most `4.99e-14` relatively and preserves each
rank. In contrast, the different-model unit-clock-derivative ablation gives
ranks 123, 123, 105, 124, 117. This is model sensitivity, not evidence that a
coordinate change supplies information. The canonical modes mix RTN, antenna
and stable bias coordinates; their wet-coordinate norm is only
`1.36e-8`--`3.09e-7` of total source norm. They are not pure wet-delay modes.

## Physical recovery and state response

| Injected mode / forward path | Identified projection recovered | Injected functional recovered |
|---|---:|---:|
| Strong / exact linear | 10/10 | 10/10 |
| Weak / exact linear | 20/20 | 20/20 |
| Strong / finite physical | 0/10 | 10/10 |
| Weak / finite physical | 0/20 | 0/20 |

The largest relative source-projection error in the exact linear controls is
`1.90e-7`; the largest strong finite injected-functional error is `2.18e-8`.
Finite full source-projection errors are 1.59--84.73 relative to the injected
identifiable projection. Weak injected-functional errors are .0844--48.66,
well above the fixed `.001` criterion. The strong functional survives while
small forward errors populate other weak source coordinates.

The per-observable forward-difference scale is `2.13e-7 m`. After clock/float
profiling, weak finite-minus-linear defects exceed their intended linear
signal by 13.91--1281.76, across both signs and amplitudes. Strong defects are
small relative to their observable signal. Subtracting finite model paths in
double precision therefore does not resolve these tiny weak contrasts. This
is a computational/conditioning limit of this recovery test, not evidence
that the corresponding physical sources cannot exist, and it does not isolate
roundoff from every derivative approximation or nonlinear remainder. A stable
differential forward calculation is needed before using these probes to
qualify physical recoverability.

The cold-start state changes are compared with the archived nominal RF fit
only after fitting. Entries below are position-vector norms in micrometres;
"discrepancy" is the norm of the vector difference, not a difference of norms.

| Fold | 1 cm: linear / finite / discrepancy (um) | 10 cm: linear / finite / discrepancy (um) |
|---|---|---|
| G05 | 49.724 / 53.135 / 6.498 | 497.238 / 493.280 / 4.058 |
| G11 | 0.223 / 53.281 / 53.170 | 2.233 / 44.199 / 43.208 |
| G19 | 0.596 / 56.464 / 56.018 | 5.958 / 53.432 / 49.193 |
| G20 | 0.402 / 51.551 / 51.925 | 4.017 / 102.225 / 106.106 |
| G21 | 38.726 / 43.506 / 10.910 | 387.256 / 387.305 / 12.623 |

The finite-minus-linear clock change is at most `2.75e-6 m`. G05 and G21
show the expected small state response, but in G11/G19/G20 numerical fit and
forward differences exceed the tiny predicted state increment. These are not
validated absolute position errors or a bound over the full weak subspace.
No source representative estimated from real residuals is applied to the
candidate.

## Independent-information findings

All results below are conditional source-information diagnostics. Across all
three reference-rank cases, no tested wet-only, orbit-only, antenna-only,
bias-only, wet+orbit or single ideal weak-functional design reaches the joint
1 m / 1 mm/s benchmark at any grid sigma. Many partial designs leave a state
functional unresolved. Their retained-projection numbers are not complete
precision and can be nonmonotone when the augmented numerical rank changes;
no measurement requirement is inferred from those unstable values.

Observing **every** source coordinate independently closes all source nulls.
The coarsest tested sigma reaching both benchmarks is unchanged across the
three reference cuts:

| Fold | Independent coordinates | Coarsest passing sigma (m per coordinate) | Position / velocity diagnostic sigma at that grid point (m / mm/s), canonical cut |
|---|---:|---:|---|
| G05 | 197 | 1 | 0.7048 / 0.1020 |
| G11 | 197 | 0.1 | 0.8288 / 0.0813 |
| G19 | 182 | 0.001 | 0.6138 / 0.0564 |
| G20 | 198 | 0.001 | 0.6198 / 0.0890 |
| G21 | 193 | 0.1 | 0.4175 / 0.0507 |

These are sufficient scenarios on the tested grid, not necessary optimal
instrument precisions or evidence that such independent measurements exist.
In particular, the 1 mm result for G19/G20 assumes measurements of all 182/198
source coordinates, including hardware biases and antenna offsets, under the
stated constant-fold law. It does not justify adding a 1 mm prior.

Even the ideal endpoint-source-shift design reaches the benchmark only in G05
(at sigma .001 m or smaller); its other four folds fail even at .0001 m.
An exact measurement of one selected mixed weak direction does not resolve
the other state-relevant combinations. Thus neither a single source family
nor a single selected weak functional provides the tested complete solution.
A practical proposal needs complementary physical observables, their joint
nuisance model and covariance; the clock scenario above is only an ideal
source-functional bound.

## Excluded RF and MW diagnostics

Every variant emits 340 supported prediction pairs: 339 are evaluable and one
is unavailable. Of the evaluated pairs, 313 are interleaved holdouts and 26
are beyond all candidate training. Predictions remain conditional on upstream
nominal timing, geometry/masks and the allowed contemporaneous reference RF;
they are not a forecast of an entirely unobserved future network.

| Variant | All-pair code RMS (m) | All-pair phase-rate RMS (mm/s) | Beyond-training code RMS (m), n=26 | Beyond-training phase-rate RMS (mm/s) |
|---|---:|---:|---:|---:|
| nominal | 0.711768948 | 8.570824659 | 0.903600016 | 7.813841828 |
| weak_001m | 0.711766717 | 8.571116970 | 0.903600055 | 7.813842650 |
| weak_010m | 0.711747532 | 8.573829316 | 0.903600362 | 7.813838966 |

At 1 cm all-pair phase-rate RMS worsens in all five folds; at 10 cm it
worsens in four. Beyond-training code worsens in four folds at each amplitude.
All outcomes remain in the artifact. MW-rate RMS is unchanged (5.924112210
mm/s over all 339 pairs, 6.072814191 mm/s over the 26 beyond-training pairs),
as expected for these mean geometric/wet and stable-level interventions.
No variant is selected from these very small score changes.

## Decision and next scientific obstacle

The proposed increment was useful: it separates coordinate stability from
threshold sensitivity, and algebraic recovery from finite physical recovery.
The selected weak combinations are not yet physically qualified. Their very
small finite state effects also argue against treating arbitrary formal source
amplitudes as an observed orbital error budget.

The next useful work is a stable differential evaluation of the weak reference
contrasts, followed by complementary independent source functionals with an
explicit joint observation model. Demonstrate recovery and state-relevant
information at physically defensible amplitudes before selecting an actual
measurement design. A smaller SVD cutoff, a ridge, a clock anchor or a tuned
floor does not supply that evidence. S2 remains open; G12, CODE state scoring
and S3 remain outside this increment.

Validation: 66 focused regression tests passed (160.02 s); the final six
boundary/physics unit tests passed again (7.91 s); the new offline receipt
passed (20.81 s), then passed again with the explicit ancestry check (12.52 s).
The receipt verifies artifact/producer/input hashes, all
prediction scores and denominators, and replays G19 geometry, physical recovery
and the canonical independent-information grid. Historical receipts remain
unchanged.
