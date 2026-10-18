# Stable physical differentials and complementary source observations

This exploratory increment follows [weak-source recovery](WEAK_SOURCE_RECOVERY.md).
It asks whether the failed finite recovery was limited by arithmetic,
nonlinearity or identifiability, and which complementary independent observables
would constrain the source functionals affecting a fixed nominal RF solution.
The archive is exposed. No new confirmation or physical covariance is admitted.

**18 October 2026, exploratory result:** stable arithmetic resolves the tiny
physical forward increments, but it does not identify the complete frozen weak
functionals. Their identifiable projections recover in 20/20 finite probes;
all 20 complete weak amplitudes remain unresolved at the declared source cut.
Complementary information needs several source families, and unknown
calibration levels can prevent the benchmark even with very small random
measurement error. The prior #235 failures remain unchanged.

## Physical differential and numerical checks

The existing reference geometry module evaluates the same declared local source
law: constant reference RTN product residuals, body-frame antenna offsets,
station wet corrections and a P1-only constant IF hardware correction. COM
velocity includes the same centred 0.5-second RTN-frame difference. The implicit
emission equation, relativistic clock, admitted SLERP attitude, reception-frame
Earth rotation and VMF3 delay all follow the perturbed source.

The numerical path uses Python's portable `decimal` arithmetic with 50 digits.
It starts from the exact values of the already admitted binary64 polynomial
coefficients, clock samples, quaternion-derived orientation/rate and weather
fields. This adds computational precision, not information or physical accuracy
to those products. Orbit interpolation remains on the admitted stencils; crossed
clock/attitude intervals and unsupported atmosphere domains fail explicitly.
The original ten-degree reference mask at zero receiver clock is checked for
every finite intervention, retaining a support failure instead of clipping.
Rotations are evaluated by converged small-angle series. Range differences use
`(2 r.dr + dr.dr)/(rho_new+rho_old)` rather than subtracting binary64 absolute
ranges. Clock and atmospheric increments are combined before conversion back
to binary64. No extra platform-dependent `longdouble` precision is assumed.

Source Jacobians use the implicit emission derivative and analytic geometry
in this arithmetic. The path/clock time derivative is centred at `1e-8 s`;
central source differences at `1e-12 m` independently check the Jacobian.
Every 128th admitted row, in original row order, is checked again at 35 digits,
including its six physical probes. Sampling is fixed by identity/order, not
held scores. Derivative and increment agreement are retained with their counts.

The receiver-clock derivative is also recomputed from the stable geometric
Jacobian. Its meteorological time term uses a centred one-second weather
slope multiplied by the light-time conversion. At the unchanged nominal
receiver-clock centres, code and phase affine intercepts are updated by
`(new_derivative-old_derivative)*centre`. A separate frozen historical-clock
profile isolates the effect of this derivative repair. The reception-time,
reference-clock datum and free-clock nuisance law remain conditional.

The prior #235 source directions, amplitudes and signs are reused without
reselection: strong positive .01/.1 m, weak positive/negative .01/.1 m, all in
total Euclidean source-coordinate norm. All 30 physical probes remain in the
denominator. Their exact linear controls pass through the same clock/float
residual projector. Recovery uses the identifiable source projection with the
same `1e-3` relative criterion. A scalar injection is explicitly unidentifiable
when it has more than `1e-8` norm in the source null space; returning zero is not
successful recovery of that missing functional.

For each weak +/- pair the odd and even parts are separated before evaluation.
The odd increment tests the linear derivative with the quadratic term removed;
the even part measures finite curvature. Both amplitudes and all failures are
retained. More precise arithmetic does not force a finite nonlinear signal
to obey a linear inverse model.

The method uses the standard [decimal context arithmetic](https://docs.python.org/3.13/library/decimal.html)
and the existing [emission/reception convention](https://gssc.esa.int/navipedia/index.php/Satellite_Coordinates_Computation).
No new physical accuracy is imported from these sources.

## Complementary observation laws

All 15 nonempty subsets of wet, orbit, antenna and stable-bias coordinates are
tested at the fixed sigma grid `.0001, .001, .01, .1, 1 m`. Three hypothetical
observation laws distinguish independent measurements, same-family/same-axis
correlation .5, and an unknown common calibration offset for each family/axis.
The last law uses only Helmert contrasts, profiling the unsupported absolute
levels without a prior. It does not grant an instrument's zero point for free.
None of these are actual external measurements or an admitted source prior.

The full stable source spectrum is compressed, then direct observation rows
are added. Rank sensitivity is reported at `1e-9`, `1e-10`, `1e-11` times the
**original reference source scale**. This absolute cut stays fixed as sigma
changes; stronger external precision does not raise the rank threshold and
silently discard reference information. Unresolved directions remain unbounded.
Position and velocity diagnostic sigmas are the largest principal-axis
one-sigma scales of the corresponding source-information image blocks.

External-clock scenarios use a joint likelihood. Each unique requested clock
endpoint adds a row observing the receiver-clock nuisance itself, with an
unpenalized instrument offset per station. Same-epoch error correlations 0 and
.5 and the same sigma grid are compared. RF and external rows are whitened
with their declared covariance and profiled jointly over epoch receiver/
reference clocks, phase/MW floats and station instrument offsets. External
random errors are independent between epochs in these declared scenarios;
temporal stability is not physically qualified. Nuisance columns are normalized before their `1e-12` SVD rank test. Calibration noise
and source coupling therefore remain in the source likelihood; the ideal
source shift `KG` is not treated as a directly observed quantity.

Clock-only information and its combinations with direct wet, antenna,
wet+antenna and wet+antenna+bias observations are retained. Direct source
measurements in these combinations are independent scenarios with the same
metre sigma, not claims about a real instrument package. Actual time-transfer
equipment requires delay calibration ([BIPM guidelines](https://webtai.bipm.org/ftp/pub/tai/publication/gnss-calibration/guidelines/bipmcalibration_guidelines_v40.pdf));
using another GNSS solution sharing the same products is not evidence of
independence. Antenna offsets and PCV are distinct parts of the
[IGS antenna model](https://www.igs.org/wg/antenna/); this source law still does
not model PCV or qualify an antenna measurement campaign.

## Mapping the scenarios to real observables

The operators below are a research proposal, not available measurements for
these archived folds. A passing hypothetical family set still needs a physical
measurement operator, matched time/frame coverage and an independence record.

| Quantity | Candidate observable | What the current scenario assumes or still lacks |
|---|---|---|
| Wet delay | Independently calibrated, co-located water-vapour radiometry | A constant station zenith residual and its calibration level; raw radiometry, gradients, weather flags and mapping errors need their own model. |
| Receiver clock | Time referenced to the actual observation latching epoch, with calibrated transfer delays | The joint clock model includes an unknown station instrument offset and declared temporal/epoch covariance scenarios; another GNSS clock estimate sharing the RF/products is not an independent input. |
| Satellite antenna | Independent body-frame, frequency-specific ground/provider calibration | Direct IF PCO coordinates are idealized; current ANTEX values are already part of the admitted product model. PCV and calibration correlations remain outside the source law. |
| Hardware delay | Independent raw-channel timing-chain calibration | The P1-only IF law is specified, but a per-link stable bias can also contain effects that a single laboratory hardware-delay measurement does not observe. A component-level operator is required. |
| Reference orbit | Independent tracking, where spacecraft equipment and geometry permit | The identity RTN observation is an ideal information benchmark. Actual laser range supplies a line-of-sight projection with reflector-to-COM, station, timing and atmospheric nuisances; it is not a direct three-coordinate measurement. |

[JPL radiometry work](https://ipnpr.jpl.nasa.gov/progress_report/42-226/42-226F.html)
provides a concrete physical route to wet-path information. The timing-channel
interpretation follows the [BIPM reception-time recommendation](https://www.bipm.org/en/committees/cc/cctf/20-2015/resolution-5).
[ILRS](https://ilrs.gsfc.nasa.gov/) describes the range observable, and its
[spacecraft-parameter guidance](https://ilrs.cddis.eosdis.nasa.gov/missions/spacecraft_parameters/)
requires the reflector-to-centre-of-mass correction. These references establish
observable types, not coverage or achieved accuracy in this archive. No external
data, satellite equipment assumption or calibration sigma is imported here.

## Candidate boundary and interpretation

The previous artifacts are verified by their literal SHA-256 before decoding;
original source bytes and all closed outcomes remain immutable. Candidate own
products and RF are excluded before reference arithmetic and checked again
at the stable geometry and joint-information boundaries.

The archived RF state/observation derivative is used only to define local
source-to-state sensitivities. The reference calibration and candidate wet
paths are propagated together, with source-specific orbit/antenna/bias columns
remaining reference-only. No new candidate trajectory fit or RF/MW score is
performed: this increment qualifies arithmetic and studies source information.
All 22 candidates, 440 windows, 63 arcs, 17 insufficient preparations and five
archived incomplete branch searches remain visible.

The information target is the fixed nominal RF sensitivity under its declared
weights. It is not the covariance of a newly clock-assisted RF/state estimator,
a measured source process, total orbital accuracy or a minimum instrument
specification. Both source null response and the full conditional-image scales
must pass before issuing the joint 1 m / 1 mm/s design benchmark. No benchmark
result is added to RF covariance. G12 state, CODE state scores, production
floors and S3 remain outside this increment.

## Retained results

The same 22 candidates, 440 windows, 63 prepared arcs and 25,117 admitted
reference-row occurrences are retained. Seventeen candidates remain
`INSUFFICIENT_PREPARED_ARCS`; five have `STABLE_DIFFERENTIAL_PREPARED` for this
local calculation. Their archived RF fits remain `BRANCH_SEARCH_INCOMPLETE`.
That new preparation label does not change the old fit outcome. All 30 physical
probes prepared successfully, without replacing a direction or amplitude.

### Precision, clock derivative and identifiability

Across 200 sampled reference rows, all source-Jacobian entries agree after
binary64 conversion between 35 and 50 digits. The analytic and independent
central source derivatives also agree at that output precision. All six
physical increments agree between precisions on those sampled rows. These are
sampled numerical checks of this physical law, not accuracy of the input
products or proof about every possible intervention.

| Fold | Rows | Sources | Prior / stable G with historical clock / stable clock rank at 1e-10 | Stable ranks at 1e-9 / 1e-10 / 1e-11 | Frozen weak direction in unresolved subspace at 1e-10 |
|---|---:|---:|---|---|---:|
| G05 | 5906 | 197 | 129 / 129 / 128 | 121 / 128 / 132 | 0.2231 |
| G11 | 6040 | 197 | 129 / 129 / 128 | 122 / 128 / 132 | 0.7158 |
| G19 | 2335 | 182 | 110 / 110 / 106 | 104 / 106 / 113 | 0.9380 |
| G20 | 6090 | 198 | 130 / 130 / 129 | 121 / 129 / 133 | 0.06875 |
| G21 | 4746 | 193 | 124 / 124 / 122 | 116 / 122 / 127 | 0.2465 |

The last column is a norm fraction, not its square. The maximum receiver-clock
coefficient change by fold is 4.34e-9 to 5.10e-9. Although small, it changes a
nearly degenerate source design. Holding the historical clock derivatives and
intercepts fixed preserves its central ranks; repairing them exposes additional
unresolved components of the old frozen directions. This is sensitivity to the
specified numerical cut and clock law, not proof of an exact physical null or
of globally stable eigenvectors. The reference-only information fails the full
state-image benchmark in all five folds at all three cuts.

### Finite recovery and matched arithmetic comparison

| Probe/control | Identified source projection within 1e-3 relative error | Complete injected scalar functional |
|---|---|---|
| Strong exact linear controls | 10/10 | 10/10 recovered |
| Weak exact linear controls | 20/20 | 20/20 unresolved |
| Strong finite physical increments | 6/10 | 10/10 recovered |
| Weak finite physical increments | 20/20 | 20/20 unresolved |
| Weak odd physical increments | 10/10 | 10/10 unresolved |

The four strong projection failures are the .1 m probes of G05, G11, G20 and
G21. Their relative errors are .00574, .00646, .00514 and .00862; finite
curvature can excite weak source combinations even when the injected strong
scalar is recovered. No nonlinear source inverse is fitted here. The weak
finite identified-projection errors range from 2.76e-10 to 8.41e-9, but that
success excludes their unresolved components by definition. It cannot be
reported as complete weak-source recovery. Reported scalar errors in the
artifact compare against the identifiable projection; the explicit unresolved
status takes precedence over a small projected scalar error.

To isolate arithmetic, replay the old and new physical increment blocks through
one historical-clock network with the new stable source Jacobian. If `P` is its
fixed clock/float residual projector, compare `||P dy_old-J theta||` and
`||P dy_stable-J theta||` with exactly the same `J theta`, directions, weights
and nominal clock centres. The maximum per-observable old/stable difference
for the 20 weak probes is 1.96e-8 m. Their weighted forward defect changes from
5.92e-6--1.02e-5 to 5.11e-16--3.01e-12; relative to their linear signals it
changes from 13.9--1282 to 2.21e-8--6.44e-5. These weighted norms are
dimensionless. This comparison is independent of the receiver-clock repair.

In the stable-clock design, the weak even terms at .1 m are approximately
100 times those at .01 m. The odd-minus-linear weighted norm ranges from
1.20e-16 to 1.29e-14 over all ten pairs. This separates the small physical
curvature from the old cancellation. It does not eliminate source degeneracy,
qualify a stochastic source process or change the old 0/20 weak scalar outcome.
The receipt independently reconstructs this comparison on adverse fold G19.

### Complementary source information

There are 1,125 direct-source scenario grid points: five folds, 15 family
subsets, three observation laws and five sigmas. Every point retains all three
absolute-cut sensitivity results. The following are the coarsest **tested**
sigmas that meet the joint 1 m / 1 mm/s source-image benchmark at every cut,
for an inclusion-minimal passing family set at that sigma. A missing entry
means no passing grid point, not an infinite precision requirement.

| Fold | Independent direct observations | Same-family/axis correlation .5 | Unknown family/axis zero points |
|---|---|---|---|
| G05 | orbit + antenna + bias, 1 m | orbit + antenna + bias, 1 m | orbit + antenna + bias, .1 m |
| G11 | orbit + antenna + bias, .1 m | orbit + antenna + bias, .1 m | orbit + antenna + bias, .1 m |
| G19 | wet + orbit + antenna + bias, .001 m | wet + orbit + antenna + bias, .001 m | none through .0001 m |
| G20 | wet + orbit + antenna + bias, .001 m | wet + orbit + antenna + bias, .001 m | wet + orbit + antenna + bias, .0001 m |
| G21 | orbit + antenna + bias, .1 m | orbit + antenna + bias, 1 m | orbit + antenna + bias, .1 m |

No proper subset of the reported family set passes at that sigma, and no
smaller family set passes elsewhere on this grid. Adding wet observations
also passes wherever orbit+antenna+bias already does. No individual family
passes in any fold. These are minimal sets within these ideal coordinate
operators and this finite grid, not universal necessities for every possible
observable. Correlation can improve contrast information at fixed marginal
sigma; its benefit is specific to the covariance and source geometry.

For the independent minimal sets in the table, the worst position/velocity
axis sigmas across cuts are respectively: G05 .70484 m / .10199 mm/s;
G11 .82911 m / .08136 mm/s; G19 .61381 m / .05637 mm/s;
G20 .61984 m / .08900 mm/s; G21 .41788 m / .05075 mm/s.
A uniform all-family 1 mm scenario therefore passes all five folds, but a
uniform unknown-zero-point scenario does not. The free-offset G19 failure
illustrates why random precision cannot substitute for calibration of an
informative absolute level.

### Genuine external-clock likelihood

Another 250 grid points combine five folds, ten clock sigma/correlation
scenarios and five complementary source sets. Each point again retains three
source cuts. Clock observations alone never meet the benchmark. Among the
tested complements, only **clock + wet + antenna + bias** passes in any fold:

| Fold | Coarsest passing clock/direct-source sigma, independent station errors | Same-epoch correlation .5 |
|---|---|---|
| G05 | .01 m | .01 m |
| G11 | none through .0001 m | none through .0001 m |
| G19 | none through .0001 m | none through .0001 m |
| G20 | none through .0001 m | none through .0001 m |
| G21 | .001 m | .01 m |

The sigma here is in metres of light-time for the clock and in metres for each
ideal direct-source coordinate. Station offsets are free in both columns.
These are joint calibration-information calculations with RF noise, unlike the
prior ideal `KG` observation. The target remains the fixed nominal RF
sensitivity map, not the covariance of an external-clock-assisted state fit.
The failures remain visible; a passing clock package cannot be inferred for
G11, G19 or G20 from these operators or this sigma grid.

## Provenance and validation

Numerical producer: `e762b4b28e026ae1076f505779e9f77206ef7a35`, descending from
main merge `8f333d88b2b933a49227ea31c4b26e4a18cc38cd` (#235).
Single retained execution used the existing runner:

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.exploratory.reference_network_clocks --stable-sources research/exploratory/results/stable_source_differential_v1.json.gz
```

The gzip artifact is 10,568,132 bytes with SHA-256
`56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020`.
It binds input/source bytes and both literal parent hashes before decoding.
The original #235 and #234 artifacts and source versions are unchanged.
The offline receipt checks producer ancestry and Git source blobs, all
candidate/row/failure denominators, precision samples and information laws.
It reconstructs a G19 physical increment from admitted raw products, source
recovery, coupled reference/candidate transfer from the archived derivative,
the matched arithmetic comparison and a correlated joint-clock/source scenario.

Local checks: 87 focused regression tests passed, followed by seven final
physics/boundary/integration tests (six overlap the earlier run), and the
retained receipt test passed: 89 distinct tests. Candidate-poisoning tests
cover products and own RF before parsing; integration forbids a new RF fit or
state score. Linux/Windows CI retains the complete positioning suite. Its
job timeout is 25 minutes because the merged #235 Windows job already took
about 19 minutes including setup. No tests or scientific criteria were removed.

## Research consequence

The useful next physical question is which actual measurement operators
constrain the unresolved orbit/antenna/bias mixtures, particularly G19/G20,
without assuming perfect calibration levels. Start from the declared raw
observable, model its common offset and temporal correlation, and test its
intersection with the stable source null space before assigning an instrument
precision. Wet radiometry plus independently calibrated timing, antenna and
hardware information are complementary candidates; direct identity RTN rows
must be replaced by realistic tracking geometry and its nuisances. No such
measurement is admitted by this increment, and no numerical source correction
is applied to an RF solution.
