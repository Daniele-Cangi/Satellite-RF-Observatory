# DOY223 ALGO/MDO prediction seal

## Outcome

`PRIMARY_PLAN_AND_PREDICTION_FROZEN`

The exact-hash NOAA broadcast-navigation product for GPS day 223 was used
offline to compile the already frozen G22-relative-G30 coordinate and all four
predeclared null curves. No ALGO or MDO observation locator, header, payload
byte, or observation value was requested or opened.

This is a proof-boundary artifact, not an orbital measurement and not access
authority for the primary.

## Bound authorities

- Plan manifest SHA-256:
  `2e7598068db8dd5c4fe27ee881340bb7096b8e878fda0a050048a11a70767055`
- Compiler source commit:
  `6647fe3aa6e37f514dc399449a9f88354a3b8464`
- Compiler source SHA-256:
  `0c05d4f5a0464e11fc6d79827adfb33a0f673c8d0be788800205077bafe3ef1e`
- Compiler manifest SHA-256:
  `e15ace782755708541b21fa61dc31c25989880c965ce16e8932a4539d417591c`
- NOAA compressed NAV: 71,403 bytes,
  `deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478`
- NOAA uncompressed NAV: 298,710 bytes,
  `340bf5e84504420d6770476c8f3c9cda78722fcc283cd34385f47b77ba6f4d2e`
- Frozen curve-set SHA-256:
  `6ded9e22e1a32ce2fd4c24f9834a04fcd818f719d1f84465bef8f04c1b82323f`
- Prediction artifact canonical SHA-256:
  `c45df3e1ca2a18bf52bd7f33e31fceaf6c15a9e83d83d1078c3f092c81cbf15b`
- Seal canonical SHA-256:
  `4e94711d88a9c85c232585db83a3b7192713ba0b4900606076e8c386373c57fa`

The transient NAV gzip was deleted after the two artifacts were written and
verified. It is orbital authority, not receiver observation data.

## Frozen curves and regression

The 139 raw epochs run from 2026-08-11 05:24:00 through 06:33:00 GPS at
30-second cadence. Removing the two edge epochs produces 137 feature epochs:
77 calibration and 60 held out.

Every hypothesis uses the same grid and transform:

- `ORBITAL_G22`
- `PREFIX_AFFINE`
- `WRONG_ORBIT_G01`
- `WRONG_ORBIT_G14`
- `WRONG_ORBIT_G17`

The exact compiled curves reproduce the geometry screen:

- prefix-affine held-out separation: 123,441.481064 m peak-to-peak;
- G01 wrong-orbit separation: 55,330.087156 m peak-to-peak;
- G14 controlling separation: 54,990.701677 m peak-to-peak;
- G17 wrong-orbit separation: 194,596.734639 m peak-to-peak;
- pairwise physical guard: 3,142.164149 m;
- remaining controlling margin: 51,848.537528 m;
- minimum modeled elevation: 22.663660077 degrees.

No suffix fit, free time phase, null change, station change, or window change is
available after this seal.

## Access boundary and next decision

At seal time every observation counter is zero. The seal explicitly sets
`primary_access_authorized_by_seal` to `false` and stops before any primary
observation request.

The next physically meaningful decision is a separate review of whether to
authorize the one bounded two-product materialization described by the frozen
DOY223 plan. Selection, geometry, predictions, nulls, witnesses, retry budget,
and stop semantics are already immutable; no further infrastructure work is
needed before that decision.
