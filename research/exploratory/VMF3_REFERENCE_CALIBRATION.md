# Coordinate-aware atmospheric calibration — 2026-09-17

## Physical result

VMF3 meteorology and separate dry/wet mapping have now been applied to the
**actual reference RF observations** in the two exposed five-minute windows.
All **616/616 station/epoch calibrations** (2 events x 4 modes x 7 stations x 11
epochs) pass the existing checks. The original baseline replays numerically.
No satellite, station or measurement was changed to improve the result.

| Atmospheric mode | G14 pooled reference RMS, m | G12 pooled reference RMS, m |
|---|---:|---:|
| Legacy baseline | 0.8973544853 | 1.0122397166 |
| VMF3 zenith only, legacy mapping | 0.8953537617 | 1.0021086334 |
| Legacy zenith, VMF3 mapping only | 0.8985129379 | 1.0146228903 |
| VMF3 zenith and mapping, primary | 0.8961526146 | 1.0037580436 |

The predeclared full model reduces pooled RMS **0.133935% / 0.837912%**.
The zenith-only diagnostic happens to have lower RMS; it is not selected as a
new physical model after seeing that result. The mapping-only diagnostic worsens
both totals. Every mode remains in the report.

Atmospheric path changes reach **0.392709 m / 0.410847 m** (G14/G12). Refitted
receiver clocks change by up to **0.191049 m / 0.225900 m** in range units.
Thus the raw atmospheric correction cannot be equated to a residual improvement.
RMS is still near one metre; this model does not explain most of the residuals.

## All stations, including worsening cases

| Event | Station | Legacy RMS, m | Full VMF3 RMS, m |
|---|---|---:|---:|
| G14 | ALGO | 0.745004 | 0.733710 |
| G14 | BOGT | 1.121294 | **1.128143** |
| G14 | DRAO | 1.033865 | 1.030417 |
| G14 | MKEA | 0.710836 | **0.716676** |
| G14 | PIE1 | 0.777027 | 0.774650 |
| G14 | STJO | 0.645968 | **0.647700** |
| G14 | YELL | 1.077767 | 1.072434 |
| G12 | ALGO | 1.025195 | **1.026860** |
| G12 | DRAO | 1.655708 | 1.654981 |
| G12 | STJO | 0.840212 | 0.821575 |
| G12 | YELL | 0.953361 | 0.953332 |
| G12 | BOGT | 0.933429 | **0.937646** |
| G12 | BRAZ | 0.710607 | 0.650335 |
| G12 | AREQ | 0.645912 | **0.646130** |

Three of seven stations worsen on each day. Each mode retains the same 716/747
evaluated paths and the prior 18/100 omitted paths out of 734/847 observed paths.
Reports include per-path elevation, dry/wet zenith delay, mapping, correction,
residual and corrected UTC, plus all calibration diagnostics and failures.

Descriptive elevation bands (not new holdouts or selection criteria):

| Event | Elevation | Paths | Legacy RMS, m | Full RMS, m |
|---|---|---:|---:|---:|
| G14 | 10–20 degrees | 151 | 1.190454 | 1.185228 |
| G14 | 20–40 degrees | 303 | 0.961177 | 0.960631 |
| G14 | 40–90 degrees | 262 | 0.561592 | 0.563795 |
| G12 | 10–20 degrees | 218 | 1.432866 | 1.418027 |
| G12 | 20–40 degrees | 288 | 0.879649 | 0.881831 |
| G12 | 40–90 degrees | 241 | 0.627754 | 0.612167 |

## Coordinates, timing and model

The site-wise ALGO catalogue discrepancy is avoided by using the **1-degree
VMF3_OP grids at admitted station coordinates for every site**. The provider's
333 m latitude discrepancy has not been explained or edited. No site-wise
meteorological coordinate replaces an admitted ARP, and no DOMES association is
invented. Spatial interpolation and height transfer remove that dependency.

Station positions retain the previous regularized coordinate, solid-Earth tide,
ocean loading CMC:NO and 2018 solid-pole model. The study consumes the sealed
position components and replays the complete prior calibration baseline. It does
not claim these positions are physically complete instantaneous station truth.

Four complete original weather grids cover Sep 3 00/06 UTC and Sep 5 06/12 UTC.
The adapter follows TU Wien's gridded algorithm: temporal interpolation; pressure
and exponential wet-delay transfer from grid height to the station's ellipsoidal
height; separate VMF3 mappings with Niell hydrostatic height correction; spatial
interpolation of zenith delays and mapping factors separately. It deliberately
rejects extrapolation, polar caps and the longitude seam, outside this study's
site domain. It is not yet a worldwide product adapter.

Reception time is the observed GPST tag minus receiver clock/C; UTC then subtracts
18 seconds for these dates. Meteorology uses that reception epoch. Reference
emission-time state, attitude, antenna offsets, clock/bias products and rotation
during light time remain as in the baseline. Both clock and ground-coordinate
checks use the selected atmosphere at their trial station/clock values.

## Validation and evidence

The Python model agrees with the unchanged original TU Wien `vmf3_grid.f90`
in **88/88 cases**, maximum absolute difference **2.23e-15** in mapping factors
or zenith metres. Cases cover every admitted site/day, both RF endpoints,
10/30/90 degree elevations and four additional grid/epoch/altitude controls.
This is numerical implementation agreement, not atmospheric accuracy validation.
The original routine's May 2026 grid-reading correction is present. The driver
provides its documented type and closes the retained orography unit between
independent calls; original routine bytes remain unchanged.

- `f15497f`: source, original routine, four grids, orography and receipt frozen
  before the benchmark. The original full downloaded bytes are recoverable from
  pinned gzip artifacts; both compressed and uncompressed hashes are checked.
- `b3d5866`: four-mode RF runner and benchmark evidence frozen before RF replay.
- `results/vmf3_benchmark_v1.json`: complete original/Python benchmark comparison.
- `results/g14_vmf3_reference_v1.json` and `g12_vmf3_reference_v1.json`: all modes,
  paths and calibration outcomes. Previous studies and production are unchanged.

```powershell
python -m research.exploratory.vmf3_reference_study g14 NEW_G14_REPORT.json
python -m research.exploratory.vmf3_reference_study g12 NEW_G12_REPORT.json
python -m research.exploratory.benchmark_vmf3 PATH_TO_GFORTRAN NEW_WORK_DIR NEW_BENCHMARK.json
python -m pytest research/exploratory/tests/test_vmf3_grid.py research/exploratory/tests/test_vmf3_reference.py -q
```

Tests cover units/height signs, zenith normalization, temporal interpolation,
grid ordering/epoch/finite checks, unsupported domains, numerical benchmarks,
receiver time conversion, exact RF cohort, target exclusion, complete replay,
failure retention, immutable report hashes and source/input commit ancestry.

## Limitations and next work

No target position was fitted or evaluated, no uncertainty floor changed, and no
new confirmation was performed. These short, previously exposed windows cannot
qualify temporal covariance or population performance. Gradients, receiver code
antenna response, multipath, correlated product errors and longer RF coverage
remain open. The next experiment should broaden reference-only RF time/elevation
coverage and test time-held-out predictions before fitting additional corrections.
Preserve all worsening stations and failure denominators. S2 remains in progress.

Sources: TU Wien [VMF products](https://vmf.geo.tuwien.ac.at/products.html),
[original grid routine](https://vmf.geo.tuwien.ac.at/codes/vmf3_grid.f90),
[terms and attribution](https://vmf.geo.tuwien.ac.at/terms.html);
Landskron and Boehm, [VMF3/GPT3](https://doi.org/10.1007/s00190-017-1066-2).
Height-transfer and hydrostatic-height references are credited in the original
source (Kouba 2008; Niell 1996). Numerical weather products avoid direct use of
target-orbit products; this is not proof of statistical independence of upstream
meteorological assimilation.
