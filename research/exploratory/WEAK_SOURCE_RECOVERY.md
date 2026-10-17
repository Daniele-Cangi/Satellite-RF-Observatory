# Weak source combinations: physical recovery and independent information

This exploratory increment follows
[the source-separation study](REFERENCE_SOURCE_SEPARATION.md). It asks which
weak source combinations are numerically stable, whether a known physical
increment can be recovered, which combinations affect the candidate state,
and what independent information would resolve them. The archive is already
exposed; no result here is prospective confirmation or a physical error budget.

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
Clock rows represent independent endpoint observations in metres of light time;
shared endpoints are counted once and interval covariance follows their
signed contrasts. An ideal mixed-functional observation is an information
benchmark, not a claim that an available instrument directly observes it.

The resulting precision is a **source-information diagnostic under declared
weights and measurement assumptions**. It is not added to the RF covariance,
a measured source covariance, prospective coverage or total orbit accuracy.
The 1 m position / 1 mm/s velocity levels are design benchmarks only. No actual
independent measurements, noise floors, CODE state score, G12 state or S3
campaign are admitted in this increment.
