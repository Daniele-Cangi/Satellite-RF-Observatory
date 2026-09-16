# Solid Earth displacement at the reference observation epochs

## Physical information and outcome

A full step-1/step-2 lunisolar displacement model derived from IERS
DEHANTTIDEINEL is added to the regularized CODE station coordinates from PR144.
Across the two exposed windows the modeled displacement norm is 0.037-0.160 m;
the five-minute change is 0.00085-0.00440 m. This component therefore matters
far more than the micrometre-scale secular transport over the daily epoch gap.
It is a modeled physical displacement, not a measured coordinate error.

All six pre-execution variants per event retain seven stations and eleven
epochs: **924 station/epoch calibrations**, all qualified by the unchanged
historical checks. The baseline reproduces exactly. The primary model reduces
pooled reference RMS by **0.0670% on G14 and 0.5850% on G12**. G14 DRAO and YELL
worsen; all seven G12 stations improve. No target fitting, target orbit access,
held-out receiver or production estimator modification occurs. These exposed
reference residuals do not establish better satellite-position accuracy.

## Algorithm, attribution and numerical qualification

The [IERS chapter 7 software](https://iers-conventions.obspm.fr/chapter7.php)
provides DEHANTTIDEINEL, ST1IDIU, ST1ISEM, ST1L1, STEP2DIU and STEP2LON.
Original sources, source URLs, SHA-256 and intact license notices are retained
in `iers_reference/`. The renamed Python adaptation is **not IERS software**
and is neither distributed nor endorsed by the IERS Conventions Center.
We acknowledge the IERS software and original authors V. Dehant, P. M. Mathews,
J. Gipson and the subsequent maintainers for the algorithms and coefficients.

`solid_earth_model.py` retains degree 2/3, out-of-phase diurnal/semidiurnal,
latitude-dependent and frequency-dependent diurnal/long-period terms. It uses
geocentric local axes, explicit UTC and TAI-UTC, and TT Julian centuries.
Coefficient tables are extracted from the original DATA statements and pinned.
The Python routines expose each component, reject invalid vectors and undefined
polar longitude, and use explicit time arguments instead of DAT/CAL2JD.

The three published 2009/2012/2015 end-to-end examples match within
1.95e-16 m (test tolerance 1e-12 m). The fourth, 2017 example in the downloaded
header **does not match**: its published expected vector repeats 2015 despite
different station/Sun/Moon inputs. The largest component discrepancy is
23.588215 m; the supplied solar distance is anomalously small. All four inputs,
expected outputs and comparisons remain in the repository and each report.
The fourth is labelled `PUBLISHED_EXAMPLE_MISMATCH`, never counted as a passed
benchmark or silently repaired. The matching examples validate the numerical
adaptation; they do not establish physical accuracy of this event model.

## Celestial inputs, clocks and coordinate convention

`prepare_solid_earth_inputs.py` consumes the pinned raw
[JPL DE440s kernel](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp)
and [IERS Bulletin A finals2000A](https://maia.usno.navy.mil/ser7/finals2000A.all).
It computes only geometric, simultaneous geocentric Sun and Moon vectors.
There are no artificial-satellite states and no optical light-time/aberration
corrections. The full kernel is kept outside the repository; its hash and URL
are in the receipt. Replay uses the small, pinned celestial extract offline.

Skyfield 1.53 with jplephem 2.23, numpy 2.3.3 and sgp4 2.25 produced the extract
(sgp4 is a transitive dependency, not invoked). The producer uses IAU2000A and
ITRS rotation with linearly interpolated observed Bulletin A UT1-UTC and polar
motion. Four EOP rows bracket both windows; extrapolation is rejected. The
producer's source hash is pinned. The retained ICRS/ECEF vector norms also
check rotational consistency. See [Skyfield frame and polar-motion conventions](https://rhodesmill.org/skyfield/accuracy-efficiency.html).
Observed celestial-pole dX/dY are not applied; these are not the internal CODE
ephemeris or a fully qualified error bound on celestial orientation.

At these dates GPST-UTC=18 s, TAI-UTC=37 s and TT-UTC=69.184 s. Every RF epoch
and an additional +18 s control have a retained celestial sample. The tide
routine uses actual UTC fractional hour, as the supplied IERS routine does;
Earth-fixed celestial rotation uses UT1 from EOP. For example, G14 03:55:00
GPST corresponds to 03:54:42 UTC. This removes the earlier ambiguous time tag
for the periodic component without changing the frozen reference RF model.

The primary adds full displacement, including the permanent component, to the
regularized station ARP; it does not enable the commented step-3 removal in
DEHANTTIDEINEL. This matches the distinction in the
[CODE processing summary](https://www.aiub.unibe.ch/download/CODE/CODE_ACN.TXT)
between tide-free station coordinates and a tide model retaining permanent tide.
It does not assert every CODE processing detail has been reproduced. The model
is evaluated at the regularized ARP; separate tidal changes of local antenna
orientation/eccentricity are not modeled.

## Fixed variants and results

The variants were frozen in `f715138` before the event comparisons ran:

| Variant | G14 pooled RMS (m) | G12 pooled RMS (m) |
|---|---:|---:|
| Regularized PR144 baseline | 0.897809488 | 1.018574846 |
| Full solid Earth primary | 0.897207689 | 1.012615683 |
| Degree 2/3 only control | 0.897355980 | 1.012645270 |
| Tide held at window midpoint | 0.897208437 | 1.012635091 |
| Permanent component removed control | 0.894960792 | 1.013219248 |
| GPST misread as UTC control | 0.897209962 | 1.012617377 |

Every G14 variant evaluates 716/734 observed paths, with the same 18 omissions.
Every G12 variant evaluates 747/847, with the same 100 omissions. Frozen reference
identities, code translations, rapid orbits/clocks/biases, full satellite attitude
PCO, troposphere, receiver-clock fitting and SPP checks are unchanged. Station
motion also enters SPP at each epoch, rather than only the first coordinate.
Engineering failures retain the station/case and yield no pooled qualified RMS.

The degree-only control differs from the full displacement by up to 12.35/13.15 mm
for G14/G12. Holding the tide at the window midpoint differs by up to 2.20/1.79 mm.
Misreading GPST as UTC changes displacement by up to 0.264/0.216 mm. Removing
the permanent component changes station position by up to 84.13 mm.
**Its better G14 RMS is not grounds to select that incompatible convention.**
All variants remain visible, and the primary follows the coordinate convention.
Maximum absolute primary receiver-clock changes are 0.08380/0.08882 m,
expressed as range-equivalent values.

| Event | Station | Baseline RMS (m) | Primary RMS (m) |
|---|---|---:|---:|
| G14 | ALGO | 0.746318 | 0.745190 |
| G14 | BOGT | 1.123676 | 1.120734 |
| G14 | DRAO | 1.029281 | 1.034065 |
| G14 | MKEA | 0.714978 | 0.710641 |
| G14 | PIE1 | 0.781560 | 0.776675 |
| G14 | STJO | 0.647877 | 0.645408 |
| G14 | YELL | 1.075232 | 1.077817 |
| G12 | ALGO | 1.031988 | 1.025154 |
| G12 | DRAO | 1.663149 | 1.656626 |
| G12 | STJO | 0.857295 | 0.841570 |
| G12 | YELL | 0.959127 | 0.953604 |
| G12 | BOGT | 0.937338 | 0.933197 |
| G12 | BRAZ | 0.714220 | 0.710825 |
| G12 | AREQ | 0.646551 | 0.645648 |

## Reproduction, provenance and remaining work

The model and celestial producer were frozen in `70ba08c`; celestial products,
six-case runner and initial tests in `f715138`. Both event outputs bind 22 source
files each; all 44 bindings were verified against execution commit `f715138`.
The prior frame reports are hash-pinned, their entire numerical structure is
replayed before the new study, and their source files are checked before use.
Original experiments and executed sources/results remain unchanged.
The first Linux CI run exposed Git normalization of the IERS source manifest:
its committed LF bytes differed from the CRLF manifest used and pinned at
execution. The packaging repair restores those exact captured CRLF bytes under
`-text`; it does not rewrite an output or relax a hash. A repository-blob test
guards against repeating this checkout defect.

```powershell
python -m research.exploratory.solid_earth_study g14 g14-tide-replay.json
python -m research.exploratory.solid_earth_study g12 g12-tide-replay.json
```

Outputs require fresh paths. Celestial preparation can be repeated with the
receipt-matching raw files and recorded optional library versions:

```powershell
python -m research.exploratory.prepare_solid_earth_inputs RAW_DIRECTORY EMPTY_OUTPUT_DIRECTORY
```

The output directory must exist; produced files must not exist. The positioning
runtime and CI need no new dependencies. Tests cover the numerical examples,
local axes, time rollover, permanent-tide sign, all variants, invalid inputs,
tampering, retained failures and complete report replay. Nonlinear SPP coordinates
allow the inherited 3 mm cross-platform replay tolerance; other numerical report
fields use 1e-7 absolute plus 1e-10 relative tolerance. These are computational
replay tolerances, not observational uncertainties.

Pole tide, ocean tidal loading, atmospheric loading, seasonal motion, receiver
code response and physical covariance remain unresolved. Next supply and validate
station-specific ocean-loading constituents and the pole-tide convention before
calling these instantaneous station coordinates. S2/G3 remain incomplete and S3
is not admitted. No smaller uncertainty floor or new confirmation follows here.
