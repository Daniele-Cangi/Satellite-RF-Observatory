# Local ocean loading and solid-Earth pole tide

## What was learned

The bounded comparison adds station-specific FES2014b ocean tidal loading and
solid-Earth pole deformation to the preserved PR145 lunisolar baseline. All six
variants on each exposed event complete: **924 station/epoch calibrations**,
with unchanged reference sets, masks, thresholds and observed-path denominators.

Local ocean displacement norms are 1.08-19.00 mm, solid pole norms 0.411-3.887 mm,
and combined norms 1.95-22.56 mm. The combined 2018-pole variant raises pooled
reference RMS by **0.01636% on G14** and lowers it by **0.03713% on G12**.
Four G14 stations and three G12 stations worsen. These small changes do not
explain the main roughly metre-scale residuals in these short windows. They do
not measure improved target-position accuracy or a prospective uncertainty.

The local load component is relative to solid Earth (`CMC:NO`). Consistency of
the centre-of-mass correction (CMC) with the paired terrestrial orbit products
remains explicitly unqualified. No target fit, orbit, excluded receiver or
production estimator modification is involved. S2/G3 remain incomplete.

## Data association and the CMC distinction

The [CODE FES2014b BLQ catalogue](https://www.aiub.unibe.ch/download/BSWUSER54/REF/FES2014b.BLQ)
contains all nine fit station codes. Only their complete blocks plus the common
header are retained, with raw/extract hashes in `inputs/ocean_loading/`.
The rows supply amplitudes in metres and Greenwich phase lags in degrees for
M2, S2, N2, K2, K1, O1, P1, Q1, Mf, Mm and Ssa. Row order is radial, west,
south; HARDISP returns **up, south, west**, which we convert to ENU as
`[-west, -south, up]` before rotation into ECEF.

BLQ entries have approximate geographic coordinates and short names, not DOMES
monuments. Great-circle horizontal separations from the admitted station ARPs
are 1.03-7.08 m, well below the 10 km spatial reuse guidance in the
[Bernese 5.2 manual, section 24.7.9](https://www.bernese.unibe.ch/docs/DOCU52.pdf).
All fourteen station/day associations and separations remain across the two reports;
this is geographic association, not a false assertion of exact BLQ monument
identity. Height is retained but not used as a horizontal separation test.

The BLQ header says `CMC:NO` and includes eleven geocentric CMC coefficient
pairs. [Onsala's CMC description](https://barre.oso.chalmers.se/loading/cmc.html)
defines a translation using cosine and positive sine coefficients. Its effect
must be consistent with orbit processing. The Bernese manual (sections 5.4.1
and 24.7.9) describes handling these translations in the Earth-fixed/inertial
orbit transformations. The [CODE analysis summary](https://www.aiub.unibe.ch/download/CODE/CODE_ACN.TXT)
also declares ocean-tide centre-of-mass treatment. Consequently we do **not**
blindly add the header translation to stations while consuming published
Earth-fixed SP3 positions. Those descriptions alone do not prove the exact
convention of our paired products; `code_loading_frame_alignment_qualified`
remains false.

For scale only, summing each harmonic's Frobenius norm of its 3-by-2 cosine/sine
coefficient matrix gives a phase-independent translation-norm envelope of
**19.130441 mm**. This is a conservative envelope for that eleven-term model,
not a measured CMC error, a bound on actual frame error, a 95% interval or a
contribution to an approved total error budget. It is not applied to calibration.

## Original HARDISP execution and numerical validation

The [IERS HARDISP package](https://iers-conventions.obspm.fr/content/chapter7/software/hardisp/)
by Duncan Agnew expands the eleven supplied harmonics into 342 constituents.
All twelve original Fortran files, URLs, hashes and intact IERS software license
notices are retained in `loading_reference/`. They are unmodified. We acknowledge
the IERS Conventions Center and Duncan Agnew's software in producing these results.
The Python build/receipt wrapper is our work and is not endorsed by IERS.

`prepare_ocean_loading.py` verifies the sources and compiles them with gfortran
using `-O2 -std=legacy`. Compiler identity, executable hash and source hashes
are recorded. It first runs the published 2009-06-25 01:10:45 UTC examples for
Onsala and Reykjavik, 24 hourly samples each. **All 48 samples match all three
published components exactly at the printed six-decimal-metre precision** in
the recorded run. The fixed validation tolerance is 2 micrometres across builds.
This is numerical agreement, not physical validation of the loading model.

The same executable computes eleven 30-second samples for each of the fourteen
station/day pairs, with actual UTC = GPST - 18 s. Output resolution is 1 micrometre;
no claim is made below that output precision. The original ETUTC leap-second
table includes the 2017 step used at these dates. Preparation requires a Fortran
compiler, while ordinary replay and estimation use the pinned output and add
no positioning-runtime dependency. A compiler-conditional test rebuilds the
original program and reproduces both benchmarks and every station time series.

## Solid-Earth pole convention

Observed xp/yp values at each UTC instant come from the already pinned IERS
Bulletin A interpolation used by PR145. The model implements the
[IERS chapter 7 update, equations 21, 25 and 26](https://iers-conventions.obspm.fr/content/chapter7/icc7.pdf).
Geocentric latitude is used; input pole angles are arcseconds and displacement
coefficients are converted from millimetres to metres. The 2018 secular pole is
`xs = 55 + 1.677*(t-2000)` and `ys = 320.5 + 3.460*(t-2000)` in milliarcseconds.
Here t uses elapsed UTC calendar seconds from 2000-01-01 divided by 365.25 days.

An explicit control uses the post-2010 linear branch of
[IERS 2010 table 7.7](https://iers-conventions.obspm.fr/conventions/content/tn36.pdf):
`xs = 23.513 + 7.6141*(t-2000)`, `ys = 358.891 - 0.6287*(t-2000)`.
Their modeled station displacements differ by up to **4.091 mm**.
The old CODE summary's generic IERS-2010 label does not resolve the exact modern
pole realization. Both variants are retained without choosing by residual RMS.
This implements solid-Earth pole tide; ocean pole loading is a distinct effect
and is not included. Nor are the archived Bulletin A values assumed identical
to CODE's own estimated EOP realization.

## Fixed comparisons and results

| Variant | G14 pooled RMS (m) | G12 pooled RMS (m) |
|---|---:|---:|
| PR145 solid-Earth baseline | 0.897207689 | 1.012615683 |
| Add local ocean loading | 0.897350249 | 1.012190898 |
| Add 2018 solid pole | 0.897211944 | 1.012663678 |
| Add local ocean + 2018 pole | 0.897354485 | 1.012239717 |
| Local ocean + 2010 pole control | 0.897356409 | 1.012176848 |
| Reversed ocean horizontal signs + 2018 pole control | 0.897256402 | 1.012798039 |

Every G14 variant evaluates 716/734 observed paths with 18 explicit omissions;
every G12 variant evaluates 747/847 with 100 omissions. Baseline residual replay
is exactly zero. All seven stations and all eleven epochs remain in every case.
Engineering failures would retain their station and case and suppress a pooled
qualified RMS. Satellite products, bias translations, attitude, troposphere,
clock fitting and SPP consistency checks retain their earlier conventions.

The ocean displacement changes by at most 0.676/0.349 mm over the G14/G12 window;
solid pole changes are below 0.21 micrometres. Maximum receiver-clock changes
for the combined variant are 4.145/10.212 mm expressed as range equivalents.
A numerically better wrong-sign or older-convention control is not a reason to
select that model.

| Event | Station | Baseline RMS (m) | Ocean + 2018 pole RMS (m) |
|---|---|---:|---:|
| G14 | ALGO | 0.745190 | 0.745004 |
| G14 | BOGT | 1.120734 | 1.121294 |
| G14 | DRAO | 1.034065 | 1.033865 |
| G14 | MKEA | 0.710641 | 0.710836 |
| G14 | PIE1 | 0.776675 | 0.777027 |
| G14 | STJO | 0.645408 | 0.645968 |
| G14 | YELL | 1.077817 | 1.077767 |
| G12 | ALGO | 1.025154 | 1.025195 |
| G12 | DRAO | 1.656626 | 1.655708 |
| G12 | STJO | 0.841570 | 0.840212 |
| G12 | YELL | 0.953604 | 0.953361 |
| G12 | BOGT | 0.933197 | 0.933429 |
| G12 | BRAZ | 0.710825 | 0.710607 |
| G12 | AREQ | 0.645648 | 0.645912 |

## Reproduction and next useful step

The model, original Fortran sources and producer were frozen in `3d8e85d` before
station time-series preparation. The products, new runner and tests were frozen
in `aa910d1` before event calibration. Both reports bind 37 source files each;
all **74 source bindings** match execution commit `aa910d1`. The complete PR145
reports and earlier frame studies are pinned and numerically replayed before
this comparison. No old source, input or report was changed.

```powershell
python -m research.exploratory.ocean_pole_study g14 g14-loading-replay.json
python -m research.exploratory.ocean_pole_study g12 g12-loading-replay.json
# Optional original-Fortran regeneration (gfortran on PATH):
python -m research.exploratory.prepare_ocean_loading NEW_BUILD_DIRECTORY EXISTING_EMPTY_OUTPUT_DIRECTORY
```

Output files must not exist. Tests cover pole signs/axes/units and convention
changes, U/S/W conversion, missing/duplicate/invalid BLQ records, geographic
associations, manifest repository bytes, tamper rejection, all failure cases,
original Fortran reproduction and complete report replay. Replay keeps the
inherited 3 mm SPP-coordinate tolerance and 1e-7 absolute plus 1e-10 relative
comparison elsewhere; these are computational tolerances only.

Next resolve CMC and pole/EOP pairing from evidence specific to the orbit
products, without applying a duplicate translation. Then investigate the larger
remaining station/media/receiver terms over broader reference geometry rather
than treating millimetre-scale corrections as an explanation of metre-scale
residuals in these windows. Atmospheric tides, ocean pole loading, seasonal
motion, code response and physical covariance remain unresolved; instantaneous
site-position qualification and a new confirmatory event are not claimed.
