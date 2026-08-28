# PIE DOY223 observer prediction seal

## Outcome

```text
PIE_OBSERVER_PRIMARY_PREDICTION_FROZEN
PRIMARY_DOY223_UNOPENED
```

The exact-hash NOAA broadcast-navigation product for GPS day 223 was used
offline to compile the already frozen PIE G22-relative-G30 coordinate, the
predeclared affine null, all three wrong-orbit alternatives and the direct
`t +/- 15 s` trajectory family. No PIE observation locator, header, payload
byte or numerical observation value was requested or opened.

This is the prospective prediction, not an orbital result. It grants no
executor or primary-access authority.

## Bound authorities

- prospective-plan manifest SHA-256:
  `5fef155739849280fced56a5967460df7be0b6e9ae1522aadbc61b6d667a6867`;
- prospective-plan receipt canonical SHA-256:
  `7291cc19b0400b1b16367d6786090bc0f7ddd1473e83195a3b7abe4951b14a1b`;
- compiler source commit:
  `db0ff58c092f48cb5cea09bffd494b7a639be848`;
- compiler source SHA-256:
  `b1cecd12f2a72fad4526d824713f7f1a716f6e0b69bc8e40f4370a05ab5b382e`;
- compiler manifest SHA-256:
  `59bd0270787d61de1bcb73200f20ba93521fa9a1f366c567914899151c1dc5c0`;
- NOAA NAV: 71,403 compressed bytes,
  `deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478`;
- NOAA uncompressed NAV: 298,710 bytes,
  `340bf5e84504420d6770476c8f3c9cda78722fcc283cd34385f47b77ba6f4d2e`;
- frozen nominal curve-set SHA-256:
  `acdf11390aa6ce4d7506fc733d53f968ac0cdfb977b99ef43dfe388d77d39586`;
- frozen timing curve-set SHA-256:
  `048315df7a536a7e71fce6e0f0fbdd54e8a1ce60d1b2bc7d0cefdc8d9421dff8`;
- prediction artifact canonical SHA-256:
  `a86a360fcbf9e1aa05e112bae1e2d1158b729f6e2fe9b4418a89883c72aacbc9`;
- seal canonical SHA-256:
  `446b65682cf9bfe7eac5d4fe63a1c709dc0ebaf9f75a681214f925b0f111e4e9`.

The transient NAV gzip was deleted after parsing and artifact verification.
It was orbital-model authority, not receiver observation data.

## Frozen physical prediction

The raw GPS grid contains 139 epochs from 05:42:00 through 06:51:00 at
30-second cadence. Raw sample zero is the only coordinate anchor. Indices
0--78 are the witness prefix and indices 79--138 are the held-out suffix.
No observation-derived constant, rate, time phase or suffix fit exists.

All hypotheses use the same observer, grid, reference satellite, anchor and
receiver-independent geometric transform:

- `ORBITAL_G22`;
- `FROZEN_AFFINE_NULL`, fixed at `-343.3209190383492 m/s`;
- `WRONG_ORBIT_G01`;
- `WRONG_ORBIT_G14`;
- `WRONG_ORBIT_G17`.

The exact held-out orbital-versus-null separations are:

| Alternative | Peak-to-peak (m) | RMS (m) |
|---|---:|---:|
| frozen affine | 190,232.341335 | 61,614.475088 |
| wrong orbit G14 | 190,422.080294 | 298,439.403661 |
| wrong orbit G17 | 300,101.772943 | 266,358.171687 |
| wrong orbit G01 | 580,945.440923 | 677,568.731298 |

The frozen affine remains the controlling alternative. Against the unchanged
7,899.820878 m pairwise decision guard, the exact physical margin remains
182,332.520457 m.

## Event time and visibility

The compiler propagated every orbital family directly at `t - 15 s`, `t`
and `t + 15 s`; it did not use slope multiplied by clock error. The largest
held-out non-affine timing excursion is 1,418.145584 m and is produced by G22
at `-15 s`, exactly reproducing the frozen envelope.

All five satellites remain above the 15-degree floor over every required grid
and timing-envelope point. The controlling minimum is G01 at `+15 s`,
17.801627769 degrees. Joint model visibility is therefore preserved.

## Interpretation and stop

The seal adds one prospective fact: the exact frozen NAV transformation still
produces the planned positive discriminability on the precise future scoring
grid. It produces zero information about whether the PIE measurement agrees.

The primary remains `SEALED_UNAUTHORIZED`. Building an executor or requesting
the PIE DOY223 artifact requires separate review. No further geometry,
capability search, null change or prediction refit is justified before that
decision.
