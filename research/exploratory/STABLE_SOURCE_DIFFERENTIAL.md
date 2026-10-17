# Stable physical differentials and complementary source observations

This exploratory increment follows [weak-source recovery](WEAK_SOURCE_RECOVERY.md).
It asks whether the failed finite recovery was limited by arithmetic,
nonlinearity or identifiability, and which complementary independent observables
would constrain the source functionals affecting a fixed nominal RF solution.
The archive is exposed. No new confirmation or physical covariance is admitted.

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
reference clocks, phase/MW floats and station instrument offsets. Nuisance
columns are normalized before their `1e-12` SVD rank test. Calibration noise
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
