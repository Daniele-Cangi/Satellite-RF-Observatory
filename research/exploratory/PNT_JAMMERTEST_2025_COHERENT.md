# Recorded coherent GPS spoofing: FGI JammerTest 2025

Exploratory development, 11 October 2026. One public recording selected from
metadata before opening its observation payload. No prospective confirmation,
new threshold, uncertainty qualification or historical-outcome change.

**The new archive solves the earlier sparse/ambiguous-input problem for this
case. It does not demonstrate incremental network detection gain.** All 30
requests evaluate, with 283 common satellite/epoch rows. The fixed-coordinate
local control already shows the large inconsistency. The network changes the
median scalar residual from 297.561 to 295.475 m, improving 27 epochs and
worsening three. These are model residuals, not position errors or detection
rates. P2 physical qualification and P3 remain open.

## Candidate and source

[FGI's JammerTest 2025 archive][dataset], DOI
`10.23729/fd-bb2cf9f9-d135-35d4-bda0-46eaca30e2ee`, was published on
30 September 2026. Its inventory has 102 files / 874,580,271 bytes, including
native RINEX observations, navigation, original Septentrio SBF, scenario
metadata and static coordinates. This differs from the [2024 flattened-CSV
qualification](PNT_P2_RECORDING_DECISION.md).

Attribution: Emma Mannfors, Muwahida Liaquat, Zahidul Bhuiyan, Mika Saajasto and
Toni Hammarberg; Finnish Geospatial Research Institute, National Land Survey
of Finland. The published licence is CC BY 4.0.

All six spoofing sidecars, the antenna log and coordinate CSV were inspected.
**2.3.5** was selected because it describes coherent GPS-only simulated driving
with broadcast ephemerides and unchanged simulated time, with a stationary
victim. It avoids repeating gross synthetic date jumps in 2.1.1/2.1.2 and fits
the existing GPS model. Selection did not use residuals, receiver capture,
fix status or detector outcome. Only this scenario's `.25O` and `.25P`
measurement payloads were downloaded. The local `.25P` is retained but not
used as the orbit source; no SBF was decoded.

Metadata discrepancies remain visible: 2.2.5 gives negative latitude where
the [official 2025 catalog][catalog] gives a northern coordinate; 2.3.10 embeds
a 2.3.5/GPS-only description while listing mixed bands; 2.1.2 uses a `J_L1`
filename inside the spoofing directory and describes a ramp unlike the
catalog's constant-power entry. None is silently corrected. Galileo-only
2.3.8 is outside this GPS comparison.

## Coverage and physical assumptions

`JT25_2.3.5_S_MF.25O` is RINEX 3.04, converted by `sbf2rin-16.2.0`, with
899 ordinary continuous one-second epochs, **13:38:20–13:53:18 GPST** on
17 September 2025. Of 8,878 GPS rows, 8,523 have positive finite C1C and
355 lack it. Sixteen native epochs have fewer than four such satellites.
These are structural availability counts, not proof of authentic signals.

C1C/C2W is present in only 2,559 rows / 286 epochs; 6,319 rows lack the pair.
The comparison explicitly uses **C1C at all three receivers**, with ionosphere
and hardware/group-delay biases uncorrected. No C2L substitution or claim of
ionosphere-free observations is made.

The local coordinate comes from the archive's WGS84 antenna coordinate,
converted to ECEF: approximately `[2176375.3242, 622779.9258, 5942950.8811]` m.
It agrees with the antenna log and differs from the RINEX approximate position
by 1.164 m. No victim PVT, code fitting or post-result position adjustment is
used. Survey provenance and coordinate uncertainty are unspecified.

External **TRO1 and KIRU** are approximately 124.1 km and 258.0 km away in ECEF
chord distance. Both daily files have all 2,880 ordinary 30-second epochs.
C1C counts are 33,380 and 31,669; KIRU has 1,006 missing C1C rows. Direct BKG
connections timed out; files came from ESA's public BKG mirror. Their RINEX
XYZ + antenna-offset coordinates are not newly qualified survey truth.
Shared distribution and broadcast products remain shared dependencies.

The antenna log says `EXTERNAL CESIUM`. This is a frequency-standard
declaration, **not an independently bounded UTC acquisition clock**. The read
files do not document its connection to these epochs, steering, UTC
traceability or timestamp uncertainty. Neither this declaration nor continuous
receiver GPST qualifies absolute time or alarm latency. No SBF inspection has
yet established such a witness.

## Identical-set comparison

The shared `reference_codes` / `read_station` reader now has explicit
`native_epochs=True`: original tags and all ordinary epochs without rounding
or resampling. Default 30-second admission is unchanged. KIRU's RINEX 4.01
observations use the [IGS observation layout][rinex], now supported with 4.00.
This extension does not admit RINEX 4 navigation or 4.02 time-tag precision.
Existing time-scale, correction, duplicate and event rejections remain.

Requests cover **13:38:30 through 13:53:00 GPST**, inclusive, every 30 seconds:
every complete reference-grid epoch inside the source interval. Local and
reference tags match exactly. No interpolation, nearest-epoch substitution,
changed tolerance or timestamp repair. The other 869 native epochs are counted
in source coverage, not called network evaluations. All 30 requests evaluate
with 4–10 common GPS satellites.

The existing `pnt.fixed_site.evaluate_epoch` uses healthy broadcast NAV,
two-hour age cap, 10-degree elevation mask, four-satellite minimum, Earth
rotation, troposphere model and six-iteration median clock fit. NAV is
[NOAA's daily composite][nav], not the attacked receiver's `.25P`. Clock fits
are GNSS-derived nuisance parameters, not UTC truth. No local values enter
either remote fit. Standalone and identical-common-set fits both remain in
the [complete result](results/pnt_jammertest_2025_coherent_v1.json.gz).

The scalar is the maximum absolute satellite residual difference relative to
the minimum common PRN: local, KIRU-minus-TRO1 and local-minus-mean-reference
use identical satellites/epochs. No detector threshold or false-alarm budget
is fitted.

The [2025 plan][plan] and sidecar both give naive 15:40–15:50 timestamps. This
split is **conditional on interpreting them as local CEST**, subtracting two
hours and adding the 18-second GPST–UTC offset. It is receiver-tag overlap with
a plan, not independently measured RF activity/capture. Outside rows are not
certified benign.

| Conditional receiver-tag interval | Evaluated | Median local m | Median combined m | Median remote-pair m | Smaller / larger combined |
|---|---:|---:|---:|---:|---:|
| Before nominal transmission | 4 / 4 | 5.296 | 1.112 | 0.928 | 4 / 0 |
| Nominal transmission | 20 / 20 | 299.558 | 297.557 | 1.494 | 17 / 3 |
| After nominal transmission | 6 / 6 | 4.797 | 1.499 | 1.170 | 6 / 0 |
| Entire recording grid | 30 / 30 | 297.561 | 295.475 | 1.389 | 27 / 3 |

Maximum local residual is 1,650.269 m; remote-pair maximum is 2.119 m. The
after-nominal interval still contains a **270.830 m** local residual. The three
worsened epochs, GPST seconds 49,230 / 49,770 / 49,800, remain in the result.
Lower baseline residuals do not establish qualified bounds, false-alarm
reduction or incremental attack detection.

## Reproduce with existing primitives

The compressed result retains every requested epoch, admission, standalone/
matched fit, metric, metadata discrepancy, selection and input hash. Its
implementation is commit `e848596aa533123f6087397160ae75fd0b82e03f`. Raw files
remain outside Git; historical results are unchanged. No new experiment
executor, seal or replay mechanism is added.

Download the selected `.25O`, `.25P`, sidecar, antenna log and coordinate CSV
from Etsin. Public authorization is
`https://etsin.fairdata.fi/api/v3/download/authorize`, with JSON
`{"cr_id":"095782a8-4e31-456e-8719-7021b4c96362","file":"/Static/Spoofing/MF/2.3.5/JT25_2.3.5_S_MF.25O"}`;
fetch the returned `url`. Verify bytes against Metax's dataset `/files`
inventory and retained checksums before parsing. Temporary download URLs
expire; the result retains stable file identities instead of tokens.

Use [ESA's documented anonymous access][esa] for both daily files under
`/bkg/gnss/data/daily/2025/260/`; obtain NOAA NAV from the link below. Match
SHA-256 with `reference_downloads` / `sources` in the result. Install existing
`requirements-positioning.txt`. From the repository root, this example
recalculates retained `epochs`; `INPUTS` contains the original filenames:

```python
from collections import defaultdict
from datetime import date
from pathlib import Path
import csv
import numpy as np
from pnt.fixed_site import read_station, evaluate_epoch
from pnt.model import broadcast_navigation, day_context

root, day = Path('INPUTS'), date(2025, 9, 17)
coordinate = next(csv.DictReader(
    (root / 'ground_truth_static.csv').read_text().splitlines(),
    skipinitialspace=True))
lat, lon = np.deg2rad([float(coordinate['latitude_WGS84_deg']),
                      float(coordinate['longitude_WGS84_deg'])])
h = float(coordinate['ellipsoidal_height_WGS84_m'])
e2 = 6.6943799901413165e-3
n = 6378137.0 / np.sqrt(1 - e2 * np.sin(lat)**2)
xyz = [(n+h)*np.cos(lat)*np.cos(lon), (n+h)*np.cos(lat)*np.sin(lon),
       (n*(1-e2)+h)*np.sin(lat)]
files = {'local': 'JT25_2.3.5_S_MF.25O',
         'TRO1': 'TRO100NOR_S_20252600000_01D_30S_MO.crx.gz',
         'KIRU': 'KIRU00SWE_R_20252600000_01D_30S_MO.crx.gz'}
data, positions = {}, {}
for name, filename in files.items():
    args = {'signals': ('C1C',)}
    if name == 'local':
        args.update(native_epochs=True, position=xyz,
                    position_source='FGI published WGS84 antenna coordinate')
    rows, positions[name], _ = read_station(root / filename, day, **args)
    data[name] = defaultdict(dict)
    for (time, satellite), codes in rows.items():
        data[name][time][satellite] = codes
navigation, _ = broadcast_navigation((root / 'brdc2600.25n.gz').read_bytes())
context = day_context(day)
epochs = [evaluate_epoch(time, {name: rows.get(time, {})
                              for name, rows in data.items()},
                         positions, navigation, context,
                         code_transform=lambda codes: {sv: pair[0]
                                                       for sv, pair in codes.items()})
          for time in range(49110, 49981, 30)]
```

## Decision

This is a usable recorded coherent-spoofing development case with native
observables and contemporary remote context. The stronger P2 claim remains
open: a fixed-coordinate local control already exposes the inconsistency,
and independent timing/verified benign controls are absent. Do not search more
variants here for a passing threshold. The remaining high-value question is
an independently timed inconsistency that reasonable local controls cannot
resolve. The cesium declaration is a lead to qualify, not a witness to assume.

[dataset]: https://etsin.fairdata.fi/dataset/095782a8-4e31-456e-8719-7021b4c96362
[catalog]: https://github.com/NPRA/jammertest-plan/blob/fc0aae6e9a3d7cbeeb09e1e3542444ee72d6ba9a/testcatalog2025.json
[plan]: https://github.com/NPRA/jammertest-plan/blob/fc0aae6e9a3d7cbeeb09e1e3542444ee72d6ba9a/plan-wednesday-2025-09-17.json
[rinex]: https://files.igs.org/pub/data/format/rinex_4.01.pdf
[esa]: https://gssc.esa.int/activities/ftp-and-web-access-to-gnss-repository/
[nav]: https://noaa-cors-pds.s3.amazonaws.com/rinex/2025/260/brdc2600.25n.gz
