# GNSS native-Doppler expanded navigation search

## Outcome

`NO_NATIVE_DOPPLER_GEOMETRY_SHORTLIST_IN_EXPANDED_SET`

The predeclared DOY 219–232 expansion produced no admissible 380-epoch
KIRU00SWE–MAT100ITA window with a target, reference and frozen wrong-orbit
alternative all robustly visible. No observation product was opened.

This preserves the earlier DOY 216–218 refusal rather than rewriting it. The
expansion manifest is bound to that receipt by SHA-256 and changes only the
predeclared navigation days.

## Frozen design

Unchanged from the initial native-Doppler design:

- capability set: KIRU00SWE and MAT100ITA;
- measurement coordinate: dual-frequency `D1C/D2W` first-order
  ionosphere-free L1-equivalent Doppler double difference;
- 30 s grid;
- 380 records: 76 calibration and 304 held out;
- 15 degree minimum elevation at both stations;
- direct trajectory evaluation at independent station shifts of -15 s, 0 s
  and +15 s;
- same epoch and visibility mask for nominal, prefix-affine and wrong-orbit
  hypotheses;
- no post-result window, threshold, null or capability change.

The only expansion was the bounded fourteen-day navigation set DOY 219–232
(2026-08-07 through 2026-08-20).

## Result

| DOY | Max pair records | Pairs >=380 | Max triple records | Triples >=380 | Best triple |
|---:|---:|---:|---:|---:|---|
| 219 | 468 | 14 | 379 | 0 | G14/G20/G22 |
| 220 | 468 | 14 | 379 | 0 | G14/G20/G22 |
| 221 | 468 | 14 | 378 | 0 | G14/G20/G22 |
| 222 | 469 | 14 | 378 | 0 | G14/G20/G22 |
| 223 | 469 | 14 | 378 | 0 | G14/G20/G22 |
| 224 | 469 | 14 | 378 | 0 | G14/G20/G22 |
| 225 | 470 | 15 | 378 | 0 | G14/G20/G22 |
| 226 | 470 | 15 | 378 | 0 | G14/G20/G22 |
| 227 | 469 | 14 | 378 | 0 | G14/G20/G22 |
| 228 | 470 | 13 | 377 | 0 | G14/G20/G22 |
| 229 | 470 | 13 | 377 | 0 | G14/G20/G22 |
| 230 | 470 | 13 | 377 | 0 | G14/G20/G22 |
| 231 | 471 | 13 | 377 | 0 | G14/G20/G22 |
| 232 | 471 | 13 | 376 | 0 | G14/G20/G22 |

The target/reference substrate remains ample and slightly improves across the
interval. The third-orbit overlap moves in the opposite direction. No day
reaches candidate scoring, direct clock-envelope comparison or instrumental
assessment, so there is no primary/reserve shortlist to freeze.

## Bounded parser repairs

Two descriptive defects surfaced before the successful sweep:

1. RINEX navigation records may leave the optional fit-interval field blank.
   The parser now represents that field as unknown instead of indexing a
   nonexistent value.
2. A PRN may lack a non-stale ephemeris at isolated daily epochs. Those epochs
   now become explicit non-visible gaps; they are never interpolated and
   adjacent central-derivative points are conservatively excluded.

Both repairs have synthetic regressions. Neither changes the orbital
hypothesis, the frozen search parameters or the outcome rules.

## Claim and stop

Authorized claim:

> Within broadcast-navigation days 219–232, KIRU/MAT1 and the frozen
> 380-epoch mask, no window supports the same-mask wrong-orbit comparison.

Not authorized:

- that no native-Doppler experiment exists at other stations or durations;
- that the receiver cannot measure Doppler;
- that any orbital hypothesis failed;
- that 379 records would be scientifically sufficient;
- that absence of a jointly visible third satellite should be removed from
  the null contract.

Measurement access remained exactly zero. DOY 214 numeric development remains
unopened, DOY 215 remains closed and no prospective primary was frozen.
Further date expansion is not justified automatically: the physical blocker
is now the experiment shape, not lack of search coverage.
