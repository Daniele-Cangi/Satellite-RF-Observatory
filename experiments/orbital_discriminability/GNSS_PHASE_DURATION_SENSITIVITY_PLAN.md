# G22/G30 phase-duration sensitivity — offline change of abstraction

Status: `FROZEN_BEFORE_CALCULATION`.

This is not a new gate and does not repair the rejected DOY 216 artifact.

```text
Physical question:
Can a shorter, geometry-only G22/G30 window retain positive orbital-versus-null
phase margin while increasing the joint elevation guard?

New information produced:
The shortest tested held-out duration that still supports two distinct
unopened dates with positive complete physical margin, plus its geometric
guard and controlling null.

Why the existing experiment cannot answer it:
The former 386-epoch topology was inherited from the differentiated-frequency
coordinate. Continuous phase may not require a 153.5-minute held-out suffix.

Minimum experiment:
Four existing exact-hash broadcast NAV products, fixed GOLD/NLIB and G22/G30,
one predeclared duration grid, unchanged prefix-affine/wrong-orbit nulls and
unchanged conservative phase envelope.

Stop condition:
Stop after the duration table. Do not discover or open another observation
product and do not freeze a replacement primary.
```

## Frozen inputs

- navigation: exact-hash DOY 217, 218, 219 and 220 products already present;
- stations: GOLD00USA and NLIB00USA;
- target/reference: G22/G30;
- step: 30 seconds;
- pre-roll: 60 epochs (30 minutes), unchanged;
- calibration prefix: 77 phase-feature epochs (38.5 minutes), unchanged;
- tested held-out suffixes: 60, 120, 180, 240 and 307 epochs, corresponding
  to 30, 60, 90, 120 and 153.5 minutes;
- raw epochs: calibration + held-out + two endpoint guards;
- one guard-maximizing window per date/duration, earliest tie;
- minimum geometric elevation: 15 degrees on all four target/reference links;
- nulls: prefix constant/rate fit on the 77 calibration epochs and every other
  GPS orbit jointly visible over the same guarded block;
- physical envelope: direct plus/minus 15-second trajectory timing, bounded
  troposphere, carrier-phase quantization and the same six path families,
  linearly summed and doubled for model-versus-null comparison.

The rejected DOY 216 coverage and summary are forbidden numerical inputs.
Only its terminal outcome hash may establish that the old topology is closed.
DOY 216 is excluded from every candidate role because its measurement
structure has already been seen. Observation products for DOY 217--220 remain
unopened and are not inputs.

## Selection semantics

A duration is `ROLE_PAIR_PHYSICALLY_AVAILABLE` only when at least two distinct
unopened dates retain strictly positive remaining physical margin and a real
jointly-visible wrong-orbit alternative. The shortest tested such duration is
reported; this is a grid result, not a mathematical global minimum.

Dates within that duration are ranked by joint elevation guard, then remaining
physical margin, then date. This ranking is diagnostic only. It does not
assign qualification, primary or reserve roles and does not authorize RINEX
access.

Allowed terminal results:

```text
PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE
NO_SHORTER_WINDOW_PHYSICAL_MARGIN
```

No threshold, duration, null, station, satellite or envelope term may change
after calculation begins.
