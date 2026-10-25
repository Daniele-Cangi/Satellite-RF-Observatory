# Physical complementary readouts and absolute calibration levels

This exploratory increment follows [stable source differentials](STABLE_SOURCE_DIFFERENTIAL.md).
The question is which physical readout operators constrain the remaining source
combinations, once their instrument levels and mechanical reference transfers
are included. It does not acquire independent observations or admit a source
covariance. All archived outcomes remain unchanged.

**18 October 2026 UTC, exploratory result:** none of the 510 full-readout or
300 family-ablation cases meets the benchmark at all three cuts. Adding the
unavailable ideal total-link functional gives 120 passing controls, confined
to G05/G11/G21. G19/G20 still fail on this finite control grid. Relative level
information is enough for those passing controls: the result does not require
an absolute anchor for every source coordinate. One G11 control retains a
numerical SVD failure; no passing or failed result is replaced.

## Scope and support

The same 22 exposed candidates, 440 windows, 63 prepared arcs and five supported
local source designs are retained. Their RF trajectories still have the
archived `BRANCH_SEARCH_INCOMPLETE` terminal; the other 17 preparations remain
insufficient. There is no new RF trajectory fit, RF/MW or CODE state score,
candidate correction, G12 state access, production-floor change or S3 campaign.
The target is the same fixed nominal RF source-to-state sensitivity, not a new
joint estimator covariance or demonstrated orbital accuracy.

Geometry uses only admitted non-target COM/attitude products and terrestrial
coordinates. The schedule is every original reference row whose receive tag
is a multiple of 300 seconds; its hypothetical range bounce epoch is tag minus
0.1 second. This is a fixed geometry schedule, independent of RF values and
held scores. Each scheduled geometry attempt and failure is retained without
replacement. Wet readouts occur once per station/time, not per visible reference;
antenna readouts occur once per reference/body-axis/frequency.

**Equipment, independent data, survey ties and calibration availability are
`NOT_ESTABLISHED`.** A GNSS station coordinate is not evidence of a co-located
laser station or radiometer, and no reflector payload is assumed available.
The nominal zero reflector lever arm is an explicit geometry control, not a
spacecraft parameter. None of the information cases can establish physical
readiness, even if its numerical benchmark passes.

## Physical readout operators

### Two-way range

The observable is half the roundtrip vacuum light-time, `c*(t_rx-t_tx)/2`,
with the transmit epoch held fixed during a source perturbation. The nominal
bounce position is the admitted COM. Both legs include rigid Earth rotation;
the implicit derivative includes COM inertial velocity and ground motion.
It therefore observes a changing projection of RTN error, not three directly
measured RTN coordinates. A centred finite perturbation of the full moving
path independently checks this Jacobian.

Let `u_up,u_down` point from the transmitting/receiving station to the bounce
point, `v` be the bounce velocity and `v_tx,v_rx` the station velocities in the
local inertial frame. Then

```
dt_b/dx = u_up / (c-u_up.v)
dt_rx/dx = [u_down + (c+u_down.v)*dt_b/dx] / (c+u_down.v_rx)
g = c/2 * dt_rx/dx
```

The range row uses `g*B_RTN` for reference orbit coordinates. It uses the same
`g*A_body` for a reflector offset and for the mechanical-origin/COM transfer.
It has no RF antenna PCO or phenomenological code-bias term. Additional nuisance
columns retain station interval zero, timing-scale error, epoch-tag error and
an optical zenith residual. The scale variable is fractional scale times
25,000,000 m; the epoch variable is `c*delta_t` in metres. The optical residual
uses each leg's secant elevation shape with its implicit timing transfer.

This is a conditional local flat-spacetime/rigid-Earth operator, **not an SLR
processor or optical atmosphere accuracy claim**. It does not introduce an
optical refraction model by reusing VMF3. Terrestrial coordinates, nominal
attitude and body-axis orientation remain conditional. Relativistic propagation,
PCV, reflector signatures and time-varying calibration processes need further
models before a real measurement can be admitted.

### Frequency-specific antenna metrology

Independent antenna calibration must refer its electrical PCO to a mechanical
origin and then to the COM. Let `a=ALPHA`, `b=BETA` with `a+b=1`, and let
`d=p2-p1` remain free. For the existing IF source coordinate `theta_ant`,
the raw residual operators are

```
p1 = theta_ant - b*d - origin
p2 = theta_ant + a*d - origin
```

Their IF combination is `a*p1+b*p2 = theta_ant-origin`; no equality of the two
frequency offsets is imposed. The same `origin` coordinate enters range with
the opposite transfer sign. It is one shared physical nuisance, not two
independent copies. The raw readout covariance is propagated through this
frequency law. Existing ANTEX values define the admitted model; they are not
reclassified as a new independent antenna calibration.

### Retrieved wet path and component timing

An independently retrieved station zenith wet-path readout has the local law
`retrieved_path = theta_wet + instrument_zero`. It is a retrieved path operator,
not a microwave brightness/radiative-transfer model. Absolute retrieval level,
co-location and mapping/gradient errors need separate physical qualification.

For hardware, the current source coordinate is a total per-link stable IF
bias. A component-delay model can only claim

```
theta_link_IF = ALPHA*(receiver_P1 + transmitter_P1) + link_remainder_IF
```

with the link remainder retained. Independent component readouts do not
constrain an arbitrary total-link coordinate while that remainder is free.
The component incidence and exact gauge are retained in the artifact. No
laboratory component calibration is silently promoted to an observation of
the total link bias. A separate **unavailable total-link closure control** adds
the ideal missing functional only to diagnose this operator gap; it is not a
physical package or evidence of a feasible measurement route.

## Calibration/support observations and stochastic scenarios

Every physical package has a joint readout law `y=H*theta+B*z+noise` and separate
calibration/support readouts `y_cal=C*z+noise_cal`. Whiten both and profile the
same nuisance vector jointly. Calibration/support rows can require mechanical
COM transfer, reflector characterization, timing metrology or optical-path
information; they are not all laboratory zero measurements. No values are
observed or estimated here, and none of these rows is an admitted source prior.

| Level law | What is observed |
|---|---|
| Free | No independent level information. |
| Relative | Orthonormal contrasts within each nuisance type/axis; the common absolute level remains free. |
| Anchored relative | The same contrasts plus one measured first-member anchor per type/axis; the member is fixed by lexical identity. |
| Individually absolute | One independent level/support readout for every eligible nuisance. |
| Ideal control | Eligible levels treated as known, only as an information upper-bound control. |

Frequency differences always remain free; they are not calibration zeros.
Anchor observations retain their uncertainty and resulting common covariance.
The random-readout grid is `.001,.01,.1 m`; the finite calibration/support
sigma grid is `.0001,.001,.01,.1,1 m`, in each declared coordinate's units.
A common numerical sigma across roles is a diagnostic grid, not a universal
instrument specification or an assumption of achievable accuracy.

Two random covariance scenarios use marginal sigma as stated: independent
readouts, or correlation `.5**abs(delta_t/300 s)` within each range link/wet
station, with raw L1/L2 PCO pair correlation .5. Cross-family random errors are
conditionally independent; constant levels and the common COM origin remain
shared. No physical temporal covariance is qualified. Repeating noisy readouts
cannot resolve a free constant level; finite calibration information leaves a
level-uncertainty limit even as the random averaging error decreases.

The fixed finite case schedule has 212 cases per supported fold: 102 full
range+wet+antenna cases, 60 proper-family ablations and 50 unavailable total-link
closure controls. All 1,060 cases retain the three existing absolute source-rank
cuts (`1e-9,1e-10,1e-11` times the original RF source scale). Stronger external
precision does not raise the cut. The existing complete-image/null criterion
and joint 1 m / 1 mm/s design benchmark remain unchanged. Worst unresolved
source/calibration directions at the central cut are algebraic diagnostics,
not measured source or calibration errors.

## Primary physical references

[ILRS](https://ilrs.gsfc.nasa.gov/docs/AOGS_ILRS_0708.pdf) defines the roundtrip
time observable and its optical/reflector corrections; the [spacecraft COM
information](https://ilrs.gsfc.nasa.gov/missions/spacecraft_parameters/index.html)
explains the required reflector-to-COM transfer. [IGS antenna guidance](https://www.igs.org/wg/antenna/)
distinguishes frequency-specific phase-centre models and reference points.
The [JPL radiometry study](https://ipnpr.jpl.nasa.gov/progress_report/42-226/42-226F.html)
gives a physical route to wet-path readouts. [BIPM calibration guidance](https://webtai.bipm.org/ftp/pub/tai/publication/gnss-calibration/guidelines/bipmcalibration_guidelines_v40.pdf)
describes delay-transfer references and retained calibration uncertainty.
These references motivate observable types and missing metrology. No precision,
equipment coverage, calibration value or independent data is imported from them.

## Retained results

All five supported folds prepared their readout operators. The 17 insufficient
preparations and all five archived RF `BRANCH_SEARCH_INCOMPLETE` terminals are
unchanged. The catalog has the following **hypothetical readout occurrences**,
not independent observations acquired from the world; folds share their archive.

| Fold | Scheduled/prepared two-way geometries | Unique station wet-path readouts | Raw frequency/axis antenna readouts | Nuisance coordinates | Evaluated / planned operator cases |
|---|---:|---:|---:|---:|---:|
| G05 | 609 / 609 | 72 | 126 | 219 | 212 / 212 |
| G11 | 623 / 623 | 72 | 126 | 219 | 211 / 212 |
| G19 | 261 / 261 | 30 | 120 | 210 | 212 / 212 |
| G20 | 628 / 628 | 72 | 126 | 219 | 212 / 212 |
| G21 | 512 / 512 | 60 | 126 | 219 | 212 / 212 |

There are 2,633/2,633 prepared range geometries, 306 wet and 624 antenna
readout occurrences across the folds, attached to the same 25,117 reference-row
occurrences. All 510 full-readout cases and 300 family ablations evaluated;
none passes the full-cut benchmark. Of 250 unavailable total-link controls,
249 evaluated, 120 pass and 129 fail the benchmark. The remaining G11 control
retains `PHYSICAL_OPERATOR_CASE_FAILED: SVD did not converge`: observation
sigma .01 m, correlated noise .5, free calibration levels and total-link
control sigma .01 m IF. It was not retried or replaced, and no precision result
is issued for that terminal. This numerical failure is distinct from a failed
physical-information benchmark.

### Absolute levels remove aliases, but do not guarantee precision

The full catalog has 156 eligible calibration/support coordinates (150 for
G19); frequency differences contribute 63 additional free coordinates (60 for
G19). Relative calibration leaves **11 common levels** free, one per eligible
type/axis group. Anchored relative calibration observes one member of each
of those groups plus all contrasts. These are 11 distinct required support
observations in this declared calibration graph, not one universal datum or
proof that every level must be measured in an operational design.

At raw readout sigma .01 m, finite calibration/support sigma .001 m and
independent random errors, the central-cut position-axis diagnostics are:

| Fold | Free levels, identified projection only (m) | Relative levels (m) | Anchored relative (m) | Ideal known levels (m) |
|---|---:|---:|---:|---:|
| G05 | 858.99 | 849.26 | 847.78 | 847.72 |
| G11 | 7.799 | 1.951 | 1.692 | 1.668 |
| G19 | 177.95 | 6.351 | 3.918 | 3.875 |
| G20 | 12.285 | 2.202 | 2.114 | 2.080 |
| G21 | 604.99 | 598.61 | 597.47 | 597.38 |

These are conditional local image scales, not orbital errors. Free-level
cases do not issue complete state precision at the central cut. Relative,
anchored and ideal cases do issue it there at the numerical null tolerance;
that does not make their large sigmas pass, nor does it imply robustness at
the other cuts. For anchored relative calibration, G05/G11/G21 still have an
unresolved state functional at the coarse `1e-9` cut. Every cut remains in the
artifact rather than selecting the most favourable rank.

The central-cut unresolved-direction diagnostics show the mechanism. With
free levels, antenna/COM-origin/reflector tradeoffs dominate. Relative levels
leave an approximately equal orbit/antenna mixture (L2 fractions about .7071
and .7071) in G05/G11/G20/G21. Anchoring removes that dominant calibration
alias; their remaining central-cut source nulls are almost entirely bias
coordinates with very small response in the fixed state map. G19 instead
retains an orbit/bias mixture (norm fractions .9706/.2407) even with ideal
levels. These are cut-dependent algebraic directions, not physical error
estimates. A small null response does not cure weak **resolved** combinations:
they still drive the large conditional precision scales in the table.

### Component hardware calibration leaves an operator gap

The archive has 65,65,56,66,61 total-link bias coordinates for G05/G11/G19/G20/G21,
respectively, but only 27,27,26,27,27 receiver/transmitter component-delay
readouts in the declared additive law. Counts alone are not the proof: for
any change of a total-link bias, its unrestricted remainder can change by the
same amount while every independently measured component stays fixed. Thus
component calibration supplies zero additional information on the arbitrary
total-link source vector under this retained law. This remains true with
perfect component precision. Restricting or removing the remainder would be
a new physical source hypothesis, not a consequence of calibration.

The unavailable total-link closure controls deliberately supply that missing
functional to locate the gap. At fixed physical-readout sigma .01 m, finite
support-calibration sigma .001 m, both noise laws and every tested total-link
sigma `.0001,.001,.01,.1,1 m IF`:

| Fold | Free levels | Relative levels | Anchored relative | Individually absolute | Ideal known levels |
|---|---|---|---|---|---|
| G05 | none | all five sigmas | all five | all five | all five |
| G11 | none, one SVD failure retained | all five | all five | all five | all five |
| G19 | none | none | none | none | none |
| G20 | none | none | none | none | none |
| G21 | none | all five | all five | all five | all five |

Every passing entry passes all three source cuts. Relative calibration still
leaves common absolute calibration levels free, but those levels need not prevent
the fixed state functional from meeting its benchmark once the missing link
information is supplied. This is why the useful research target is the
observable functional, not full absolute identification of every coordinate.
The total-link control is unavailable; these are not successful physical
measurement packages.

Even the strongest tested total-link control (.0001 m IF) with ideal levels
and independent random errors gives worst position/velocity axis scales
across cuts of: G05 .23167 m / .03049 mm/s; G11 .48034 m / .04379 mm/s;
G19 2.39256 m / .22179 mm/s; G20 1.16859 m / .16760 mm/s;
G21 .24693 m / .03449 mm/s. G19/G20 fail the position benchmark despite
conditionally estimable state images. This identifies a remaining precision/
geometric-leverage limit **at the fixed .01 m physical-readout scenario**;
it does not prove an exact universal null or exclude finer/better-supported
independent measurements outside this grid.

## Provenance and validation

Numerical producer: `d71c322d19a6b77832e53bd6d422a3f588a768d6`, descending from
main merge `660cc7696f4b6730c8689a2c06fdf497625422ae` (#236). Main passed all
11 checks before this branch was created, including 1980 Linux and 1981 Windows
positioning tests. The existing runner executed once:

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --physical-observables research/exploratory/results/physical_observable_operators_v1.json.gz
```

The retained gzip artifact is 2,086,228 bytes, SHA-256
`510327524edba59d8face5a081e8aecd3d0b600d5db2f6c655ad0497987a480b`.
Its literal parent hash is checked before decoding; input and selected source
hashes plus the full Git producer anchor the calculation. The old source
profile and coupled RF sensitivity are copied unchanged. The existing generic
clock/float increment projector now also accepts column matrices, allowing
matrix replay without a new source fit. No source or calibration values are
estimated by this increment.

Local validation: 11 focused tests and 37 relevant regression tests passed,
then the retained receipt passed: 49 distinct tests. Tests compare the moving
fixed-transmit range derivative with an independently perturbed full path,
propagate raw L1/L2 and COM-origin uncertainty, verify the repeated-readout
calibration limit, compare joint profiling with an independent Schur calculation,
and demonstrate the unrestricted hardware gauge. The runner test poisons
candidate products and all fresh RF data, and forbids new RF/source fits and
state scores. The receipt verifies producer ancestry and Git source blobs,
all candidates/readouts/cases/failures, the immutable parent profile and a G19
geometry/catalog/information replay under relative and anchored calibration.

## Consequence for the next physical question

This is the appropriate route because it separates three issues that the
identity-coordinate benchmark could not resolve: physical measurement
projection, common calibration datum and unobserved total-link remainder.
A blanket absolute anchor on every coordinate is not the result. Determine
which calibration levels affect the required state functional and which cancel.
For G05/G11/G21 the decisive missing input in these controls is an independent
constraint on the total stable-link functional; for G19/G20 the tested ranging/
antenna geometry and precision remain limiting after that ideal addition.

The next useful evidence is an explicit physical decomposition of the link
remainder and independently qualified observations/metrology for its relevant
components, together with real coverage, COM transfers and calibration
correlations. Keep that decomposition testable against reference-only data;
do not set an unexplained remainder to zero. Establish actual measurement
availability before translating these hypothetical scales into an acquisition
proposal or an instrument requirement. S2 remains open.
