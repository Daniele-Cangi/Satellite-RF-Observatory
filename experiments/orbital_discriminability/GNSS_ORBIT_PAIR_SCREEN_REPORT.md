# GOLD/NLIB bounded GPS orbit-pair screen

## Physical question

> Is the failed 386-epoch GOLD/NLIB geometry specific to G11/G21, or does the
> same station pair contain another GPS target/reference geometry that retains
> a 30-minute acquisition guard and a held-out distinction from frozen nulls?

This comparison produces information about orbital geometry. It does not
search for an observation product, qualify an instrument, or score RF/GNSS
measurements.

## Frozen comparison

- Stations: GOLD00USA and NLIB00USA.
- Candidate dates: 2026 DOY 216--220 only.
- Input: five exact-hash broadcast-navigation products only.
- Pairs: every unordered pair among the healthy GPS ephemerides present in
  each product.
- Grid: 30 seconds in GPS time.
- Guard: all four station/satellite links at or above 15 degrees for 60
  pre-roll epochs and 386 raw experiment epochs.
- Feature grid: the central 384 epochs, preserving the existing two-edge
  derivative convention.
- Split: 77 calibration-prefix features and 307 held-out features.
- Nulls: a prefix-only affine model and every other target GPS broadcast orbit
  that is jointly visible throughout the same guarded block. Both use the
  identical frozen suffix.

For each pair/date, the window maximizes the minimum four-link elevation over
the complete 446-epoch guarded block. The earliest window wins an exact tie.
This happens before null scoring and is independent of observation values.

## Complete bounded result

Each day exposed 31 satellites and 465 unordered pairs. Four pair/date
candidates per day survived both the complete guard and the requirement for a
jointly visible wrong-orbit alternative: 20 candidates in total. The other
2,305 pair/date cases were attributed structurally as follows:

| DOY | No complete guard | No jointly visible wrong-orbit null | Rankable |
|---:|---:|---:|---:|
| 216 | 449 | 12 | 4 |
| 217 | 449 | 12 | 4 |
| 218 | 449 | 12 | 4 |
| 219 | 450 | 11 | 4 |
| 220 | 450 | 11 | 4 |

G05 had 239 broadcast-unavailable grid epochs on DOY 219. Those epochs were
treated as non-bridgeable geometry gaps. No other satellite/day contained a
stale-ephemeris grid point under the frozen four-hour rule.

## Ranked shortlist

| Rank | DOY | Pair | Raw GPS window | Guarded minimum | Affine separation | Closest wrong orbit | Wrong-orbit separation | Controlling |
|---:|---:|---|---|---:|---:|---|---:|---:|
| 1 | 220 | G14/G17 | 05:07:00--08:19:30 | 23.620 deg | 556.646 Hz | G22 | 403.375 Hz | 403.375 Hz |
| 2 | 216 | G14/G17 | 05:23:30--08:36:00 | 23.613 deg | 553.633 Hz | G22 | 401.872 Hz | 401.872 Hz |
| 3 | 219 | G14/G17 | 05:11:00--08:23:30 | 23.660 deg | 559.150 Hz | G22 | 401.725 Hz | 401.725 Hz |

The recurrence of G14/G17 with G22 as the controlling alternative across
independent dates is useful orbit-model evidence that the ranking is not a
single-day edge effect. It is not measurement evidence.

## Frozen selection and stop

```text
GNSS_ORBIT_PAIR_GEOMETRY_SELECTED
```

Exactly one geometry is retained:

```text
date:              2026 DOY 220
target/reference:  G14 / G17
pre-roll:          04:37:00--05:06:30 GPS
raw window:        05:07:00--08:19:30 GPS
feature window:    05:07:30--08:19:00 GPS
wrong-orbit null:  G22
controlling held-out separation: 403.37545402996614 Hz peak-to-peak
```

The selection is geometry-only. No observation product was discovered or
selected, no header was opened, and zero observation bytes or values entered
the calculation.

## Remaining blocker

Before this can become a prospective plan, the candidate-specific physical
envelope must be propagated through the same coordinate and 77/307 affine
projection. In particular, timing, differential troposphere, broadcast orbit,
higher-order ionosphere, antenna/wind-up, multipath/hardware, station/EOP/
relativity, satellite-clock remainder, and RINEX phase quantization must not
consume the 403.375 Hz controlling separation.

Only after a positive pairwise margin exists may a distinct structural
qualification artifact be identified. Observation discovery before that audit
would reverse the orbit-first causal order.

The strict receipt is `GNSS_ORBIT_PAIR_SCREEN_RECEIPT.json`; its SHA-256 is
`bc6b172cd750a8071c5841dd187752c66c2b855e6abf2e77d8e54d2b4488a609`.
