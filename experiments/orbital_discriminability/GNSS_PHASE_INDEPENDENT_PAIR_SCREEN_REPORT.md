# GNSS independent-pair geometry screen

## Terminal outcome

```text
INDEPENDENT_PAIR_GEOMETRY_SHORTLISTED
```

This is an observation-blind geometry result. It does not qualify a receiver,
freeze a prospective experiment or extend the existing GOLD/NLIB claim.

## Physical question

Does the frozen G22-relative-G30 continuous-phase geometry retain a positive
held-out discriminability margin on a station pair that is disjoint from the
consumed GOLD00USA/NLIB00USA hardware and geography?

The new information is whether the repeated-pass result can next be challenged
outside the systematics shared by GOLD/NLIB. A single extra station would not
answer that question because the observable is a four-link, two-station,
two-satellite coordinate. The minimum clean geometry therefore needs two new
station sites.

## Frozen scope before ranking

The bounded candidate set was fixed at six official IGS sites before pair
ranking. Only official station identity, coordinates, current equipment and
site-log metadata were read. No observation-product locator, header or value
was discovered or opened.

| Station | DOMES | Receiver at snapshot | Antenna | Equipment effective |
|---|---|---|---|---|
| DRAO00CAN | 40105M002 | SEPT POLARX5 5.2.0 | TWIVC6050 SCIS | 2021-09-02 |
| WES200USA | 40440S020 | TRIMBLE ALLOY 6.50 | TWIVC6150 SCIS | 2026-07-15 |
| ALGO00CAN | 40104M002 | SEPT POLARX5 5.3.2 | AOAD/M_T NONE | 2026-03-25 |
| PIE100USA | 40456M001 | SEPT POLARX5TR 5.7.0 | ASH701945E_M NONE | 2026-03-10 |
| AMC400USA | 40472S005 | SEPT POLARX5TR 5.6.0 | TPSCR.G5C NONE | 2025-08-28 |
| MDO100USA | 40442M012 | SEPT POLARX5 5.7.0 | JAVRINGANT_DM SCIS | 2026-03-18 |

The receipt retains the official page and log URL, byte count and SHA-256 for
every station. These are `CANDIDATE_SITE_ROOTS`, not yet qualified historical
hardware roots: receiver serial, clock lineage and exact DOY 219 configuration
remain part of the next admission question.

## Frozen model and scoring

- Date and raw grid: DOY 219, 2026-08-07 05:46:00--06:55:00 GPS,
  139 epochs at 30 s.
- Feature grid: 137 central-difference epochs, 77 calibration-prefix epochs
  and 60 untouched held-out epochs.
- Orbital coordinate: ionosphere-free continuous phase for G22 relative to
  G30, differenced across the two stations.
- Nulls: prefix affine plus frozen wrong-orbit alternatives G01, G14 and G17.
- Visibility: G22, G30 and every wrong-orbit alternative must remain jointly
  at or above 15 degrees at both stations on the complete grid.
- Timing: station-specific direct trajectory evaluation at every combination
  of `-15 s` and `+15 s`; no local-slope approximation.
- Remaining physical terms: the same conservative phase-coordinate
  troposphere, broadcast-orbit, higher-order ionosphere, antenna/phase-windup,
  multipath/hardware, station/EOP/relativity, satellite-clock remainder and
  RINEX quantization intervals used by the frozen G22/G30 experiment.
- Comparison: the one-model term sum is doubled before comparison with the
  closest null.

The legacy troposphere helper embedded the names GOLD/NLIB. The screen applies
the unchanged equation locally to candidate station identifiers rather than
promoting that accidental name coupling into a general abstraction.

## Complete pair ranking

All 15 predeclared pairs clear the conservative geometry screen. Values below
are held-out phase-coordinate peak-to-peak metres after the frozen prefix
affine projection.

| Rank | Candidate pair | Controlling null | Separation m | Pairwise envelope m | Remaining margin m | G22/G30 min elev deg | All-model min elev deg |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | DRAO00CAN + WES200USA | G01 | 96588.530 | 3939.458 | 92649.071 | 25.222 | 19.405 |
| 2 | DRAO00CAN + ALGO00CAN | G01 | 79119.626 | 3807.328 | 75312.298 | 25.222 | 19.405 |
| 3 | ALGO00CAN + MDO100USA | G14 | 51370.299 | 3542.257 | 47828.042 | 32.236 | 21.322 |
| 4 | DRAO00CAN + MDO100USA | G14 | 44314.490 | 1682.334 | 42632.156 | 25.222 | 19.405 |
| 5 | WES200USA + MDO100USA | G01 | 45418.811 | 3672.601 | 41746.210 | 33.184 | 21.322 |
| 6 | DRAO00CAN + AMC400USA | G14 | 40940.670 | 2177.167 | 38763.503 | 25.222 | 19.405 |
| 7 | ALGO00CAN + PIE100USA | G01 | 39074.063 | 3568.097 | 35505.966 | 32.236 | 21.055 |
| 8 | DRAO00CAN + PIE100USA | G14 | 33313.061 | 1708.174 | 31604.887 | 25.222 | 19.405 |
| 9 | WES200USA + PIE100USA | G01 | 21801.051 | 3698.582 | 18102.468 | 33.184 | 21.055 |
| 10 | ALGO00CAN + AMC400USA | G01 | 21619.693 | 4037.090 | 17582.604 | 32.236 | 26.683 |
| 11 | PIE100USA + AMC400USA | G14 | 7627.608 | 1936.396 | 5691.213 | 41.558 | 21.055 |
| 12 | WES200USA + ALGO00CAN | G17 | 10802.079 | 5799.382 | 5002.697 | 32.236 | 32.236 |
| 13 | PIE100USA + MDO100USA | G17 | 4983.451 | 1440.321 | 3543.130 | 45.307 | 21.055 |
| 14 | WES200USA + AMC400USA | prefix affine | 6758.153 | 4167.707 | 2590.447 | 33.184 | 26.683 |
| 15 | AMC400USA + MDO100USA | G14 | 3373.820 | 1910.556 | 1463.264 | 41.558 | 21.322 |

The deterministic shortlist is therefore:

1. DRAO00CAN + WES200USA;
2. DRAO00CAN + ALGO00CAN;
3. ALGO00CAN + MDO100USA.

## Selected minimum vertical

DRAO00CAN + WES200USA is the recommended pair for the next bounded
qualification. It has the largest complete physical margin, retains every
model satellite above 19.405 degrees and is geographically disjoint from
GOLD/NLIB. Its reported receiver families are also vendor-distinct. That last
fact is useful metadata, not yet proof of the historical hardware roots.

For this pair:

- controlling null: `WRONG_ORBIT_G01`;
- controlling separation: `96588.529939 m`;
- one-model physical envelope: `1969.729223 m`;
- pairwise comparison envelope: `3939.458447 m`;
- remaining physical margin: `92649.071493 m`;
- direct timing term contribution to the pairwise envelope:
  `3272.607705 m`;
- broadcast-orbit contribution to the pairwise envelope: `312.559861 m`.

The screen therefore leaves a large geometry margin, but it authorizes no
measurement claim. The coordinate still requires both new stations and all
four G22/G30 phase links.

## Exact residual blocker

Before a prospective plan can be frozen, DRAO/WES must pass a separate,
observation-value-blind capability qualification that establishes:

1. exact historical receiver serial, antenna and clock lineage for both sites
   on DOY 219, proving two independent hardware roots rather than two station
   names;
2. full `TIME OF FIRST OBS` / `TIME OF LAST OBS` coverage of the 139-epoch
   window and 30 s event-time semantics consistent with the frozen `+/-15 s`
   envelope;
3. `L1C + L2W` carrier phase with LLI at both satellites and stations as the
   core coordinate and continuity cut;
4. geometry-free phase continuity with no interpolation, gap bridging or
   nonzero LLI inside the deterministic segment;
5. same-path `C1C + C2W` witnesses under a predeclared quantitative admission
   rule; `S1C/S2W` remain optional diagnostics;
6. one distinct qualification artifact under unchanged receiver configuration
   before the separate DRAO/WES DOY 219 primary is selected or accessed.

If these facts cannot be established, the correct result is capability
refusal. The large model margin cannot substitute for measurement admission.

## Stop and provenance

- Observation product locators discovered: `0`
- Observation products opened: `0`
- Observation headers opened: `0`
- Observation payload bytes accessed: `0`
- Observation values accessed or persisted: `0`
- Prospective plan frozen: `false`

The screen source is commit
`5df12420b33c27b76748a7861ead69a9efffec70`. The source SHA-256 is
`21fef40bca1ce99caae4731cc4b6d13c0cd52fdb80ba7b1f2f2cbe31775be466`.
The exact LF receipt SHA-256 is
`24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c`.

Stop here. No observation discovery, capability artifact selection or primary
access is authorized by this result.
