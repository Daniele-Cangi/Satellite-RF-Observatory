# CODE polar-motion contribution: daily reconstruction and a phase-free bound

## Outcome and decision

The two CODE daily polar-motion offsets/rates were evaluated at the same eleven
UTC instants used for each exposed event. All 159 harmonics in the official
DESAI2016 coefficient file were retained in a phase-independent norm bound.
Under the same mean/secular-pole convention, the resulting bound on the change
in **solid-Earth pole displacement** from the prior Bulletin A input is:

| Quantity | Upper value |
|---|---:|
| DESAI2016 polar-vector norm, all phases | 1.234748 milliarcseconds |
| Its solid-pole station displacement, any location | 0.0407467 mm |
| CODE daily model versus previous input, plus all phases: G14 | 0.0443324 mm |
| CODE daily model versus previous input, plus all phases: G12 | 0.0430039 mm |

This particular term is too small to explain roughly metre-scale reference
residuals. It does not bound actual Earth-orientation errors, a different mean
pole model, other subdaily terms, ocean pole loading, celestial-body orientation,
or inverse-position errors. It is not a 95% confidence interval.

Do not repeatedly rerun the reference calibration to optimize this contribution.
The next useful physical work is reference-only atmospheric-delay and receiver
response characterization over wider time/elevation coverage. Complete EOP
phase reconstruction remains an optional precision follow-up; it is not a
prerequisite for that investigation. The 2010/2018 mean-pole convention difference
from PR146 remains separate and unresolved.

## Why the planned full ERP reconstruction was narrowed

The [IGS product user guide, section 5.2.4](https://files.igs.org/pub/resource/pubs/UsingIGSProductsVer21_cor.pdf)
explains that published terrestrial orbit products already embody their ERP
conventions. A consumer working directly in ITRF must not apply another ERP
rotation to them. Consistent ERP plus subdaily terms are needed for an inertial
formulation. Our reference path consumes terrestrial SP3 coordinates.

Earth orientation still enters local pole deformation and Sun/Moon transforms.
Here we isolate the former. The official coefficients allow us to bound its
subdaily contribution **without asserting an unvalidated harmonic time/phase
implementation**. The daily pole model is reconstructed; the full instantaneous
CODE EOP is not. UT1, LOD, nutation and a new Sun/Moon transformation are outside
this calculation. No satellite state, RF observation, inverse fit or heldout was
loaded, and no existing estimator or report was changed.

## Sources, epochs and units

The exact daily COD0OPSRAP ERP files were acquired and bound in PR147. Each has
one noon MJD offset and X/Y rate row. The [IGS ERP version 2 format](https://files.igs.org/pub/data/format/erp.txt)
and the files' own headers give microarcseconds and microarcseconds/day. The
bounded within-day model is

`p_daily(t) = 1e-6 * (p_noon + rate * (UTC_fraction_of_day - 0.5))`.

GPST is converted to UTC using the same 18-second offset as the preserved
celestial inputs. No evaluation outside the declared day is accepted. This
linear offset/rate construction is an explicit model, not a claim to reproduce
Bernese's complete interpolation or subdaily buffering implementation.

[AIUB DESAI2016.SUB](https://www.aiub.unibe.ch/download/BSWUSER54/MODEL/DESAI2016.SUB)
is retained byte-for-byte with its receipt. Its polar coefficients are in
0.001 mas (microarcseconds). The separate UT coefficients are not treated as
polar angles. All 159 rows, column ordering, units, finite values and unique
harmonic argument tuples are checked. The fundamental-argument polynomials
and harmonic periods are not used to manufacture phase predictions.
The model is attributed in the file to Desai and Sibois (2016),
[doi:10.1002/2016JB013125](https://doi.org/10.1002/2016JB013125).

The earlier Bulletin A xp/yp samples are read from the pinned PR145 celestial
input, without changing its interpolation. The new receipt binds those bytes
and both ERP files. No new observation acquisition was needed.

## Bound derivation

For harmonic k, form the two-by-two polar coefficient matrix

`A_k = [[Xcos, Xsin], [Ycos, Ysin]] * 1e-6` in arcseconds.

For any phase, its polar vector is `A_k @ [cos(phi), sin(phi)]`. The second
vector has unit norm. Consequently

`||sum_k polar_k|| <= B = sum_k largest_singular_value(A_k)`.

This triangle bound permits every harmonic to have an independent phase, so it
also encloses any physically linked set of phases. It is conservative, not an
observed maximum, and does not need TT/UT1 phase choices. Numerical SVD evaluates
the mathematical bound for the supplied rounded coefficient model; this is not
interval arithmetic or a bound on coefficient/physical-model error.

For the IERS solid-pole equations, longitude rotates the pole difference into
orthogonal components a/b. At colatitude theta, the local displacement map has
columns `[-.033*sin(2*theta), -.009*cos(2*theta), 0]` and
`[0, 0, .009*cos(theta)]`, in metres per arcsecond. Their norms are at most
0.033 and 0.009 and the columns are orthogonal. ECEF rotation preserves norm.
Thus the global operator norm is at most **0.033 m/arcsecond**.

For any station, with the same mean pole in the old/new model,

`||delta displacement|| <= .033 * (||p_daily - p_previous|| + B)`.

The previous mean pole cancels in this difference. This cancellation does not
justify mixing two different mean-pole conventions. The formula applies only
to the specified solid-pole component, not all station displacement mechanisms.
All 22 sample comparisons are retained in the report; no station or epoch is
selected to improve the result.

## Reproduction and validation

Model, inputs and initial tests were committed at `829a422` before execution.
The immutable result is `results/erp_polar_bound_v1.json`. Run to a new file:

```powershell
python -m research.exploratory.erp_polar_bound NEW_REPORT.json
python -m pytest research/exploratory/tests/test_erp_polar_bound.py -q
```

Tests independently exercise analytic harmonic matrices, arbitrary phase
combinations, the latitude-dependent pole operator, daily units/rates/epoch
limits, malformed spectra/ERP, tampering, exact report replay and source/input
binding to the execution commit. Phase sampling supports the implementation;
the inequalities above, not sampled maxima, justify the bound.

Production, prospective covariance and S2/G3 admission remain unchanged. The
report explicitly leaves full instantaneous CODE EOP unqualified.
