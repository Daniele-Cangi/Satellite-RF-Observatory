# Meteorological zenith sensitivity — 2026-09-17

## Question and scope

The current calibration uses `ZHD = 2.3 exp(-0.000116 h)` metres and
`ZWD = 0.1` metres at ellipsoidal height h. How different are weather-dependent
zenith delays on the two already exposed dates? This is an exploratory component
comparison, not an RF residual improvement, physical error bound, target fit,
full VMF3 implementation or new confirmation.

We fix the union of nine fit roots ALGO/BOGT/DRAO/MKEA/PIE1/STJO/YELL/BRAZ/AREQ,
both September 3 and 5, 2026, and all four available UTC epochs 00/06/12/18h.
All **72/72** rows are present and retained. The three original provider files
and receipt are in `inputs/atmosphere/`; no satellite states or RF measurements
are read. The prior station reports supply fourteen coordinate comparisons.
The four weather epochs extend the meteorological time coverage, not RF coverage.

## Result

| Station | Weather wet zenith range, m | Total zenith difference range, m | Maximum absolute common-mapping difference at 10 degrees, m |
|---|---:|---:|---:|
| ALGO | 0.1349–0.1650 | +0.0384 to +0.0594 | 0.3314 |
| BOGT | 0.1238–0.1492 | +0.0402 to +0.0678 | 0.3782 |
| DRAO | 0.0987–0.1459 | -0.0041 to +0.0287 | 0.1600 |
| MKEA | 0.0106–0.0242 | -0.0882 to -0.0683 | 0.4923 |
| PIE1 | 0.0856–0.1532 | -0.0100 to +0.0587 | 0.3278 |
| STJO | 0.0673–0.1830 | +0.0030 to +0.0897 | 0.5008 |
| YELL | 0.0825–0.1899 | -0.0081 to +0.0700 | 0.3907 |
| BRAZ | 0.1485–0.2105 | +0.0601 to +0.1254 | 0.7002 |
| AREQ | 0.0463–0.0941 | -0.0347 to +0.0096 | 0.1938 |

Difference means provider minus legacy model, both at the **provider height**.
The report keeps hydrostatic and wet differences separately. Fixed elevations
10/15/30/60/90 degrees multiply the total zenith difference by the same legacy
factor `1.001/sqrt(0.002001+sin(elevation)^2)` on both sides. These are hypothetical
sensitivity rays, not observed satellite geometry or true VMF3 slant delays.
At zenith the mapping is one. No daily interpolation or 18–24h coverage is claimed.

This identifies a plausible decimetre-scale calibration contribution worth
testing against the approximately 0.9–1.0 m reference RMS. It does not establish
that the atmosphere explains that RMS: fitting receiver clocks, elevation
distribution, antenna response and correlations can alter the residual effect.

## Coordinates and next experiment

Provider heights differ from admitted ARPs by -0.149 to +0.923 m. ALGO also
differs by approximately **0.003 degrees latitude (333 m north)**. Do not silently
substitute these coordinates for the admitted station or assert matching DOMES.
The provider list has rounded geographic coordinates and does not establish
the full monument identity. Other geographic differences remain in the report.

Next use coordinate-aware meteorological products, verify the ALGO discrepancy
and height handling, implement and benchmark separate dry/wet VMF3 mappings,
then replay reference-only RF at actual emission/reception geometry. Extend RF
arcs and split time/elevation before judging residual gains; preserve every site,
missing datum and worsening result. No target fit until calibration and its
uncertainty justify it. S2, new confirmatory campaigns and production stay open.

## Sources, provenance and reproduction

Meteorological products: TU Wien Vienna Mapping Functions Data Server,
[product definitions](https://vmf.geo.tuwien.ac.at/products.html),
[station coordinates](https://vmf.geo.tuwien.ac.at/station_coord_files/gnss.ell),
[terms and attribution](https://vmf.geo.tuwien.ac.at/terms.html).
VMF3_OP is based on operational numerical weather models; column 5/6 are
hydrostatic/wet zenith metres and epochs use UTC MJD. This avoids directly using
target-orbit products, but is not a proof of statistical independence of all
upstream meteorological assimilation. OP is retrospective, not a real-time feed.
See Landskron and Boehm (2018),
[VMF3/GPT3](https://doi.org/10.1007/s00190-017-1066-2).

Source/input freeze `b53f015` preceded the first run. That attempt rejected an
unused negative wet mapping coefficient at GANP (outside the fixed fit pool);
its failure is preserved in `results/atmosphere_zenith_v1_failure.json`.
V2, frozen at `35e5734` before execution, removes the unsupported positivity
restriction on unused mapping coefficients while retaining finite/epoch/duplicate
and zenith/meteo checks. Both source versions remain immutable. The active report
is `results/atmosphere_zenith_v2.json`; input hashes bind original provider bytes.

```powershell
python -m research.exploratory.atmosphere_zenith_v2 NEW_REPORT.json
python -m pytest research/exploratory/tests/test_atmosphere_zenith.py research/exploratory/tests/test_atmosphere_zenith_v2.py -q
```

Use a new report path: the runner refuses overwriting evidence. Tests cover the
legacy mapping against production geometry, units, invalid values, duplicate and
wrong UTC epochs, missing entries, the negative-coefficient regression, replay
and source/input ancestry. Tests do not certify physical uncertainty.
