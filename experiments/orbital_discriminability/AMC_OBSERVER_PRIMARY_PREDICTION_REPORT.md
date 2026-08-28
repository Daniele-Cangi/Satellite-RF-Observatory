# AMC DOY221 observer prediction seal

## Outcome

```text
AMC_OBSERVER_PRIMARY_PREDICTION_FROZEN
PRIMARY_DOY221_UNOPENED
```

The exact-hash NOAA broadcast-navigation product for GPS day 221 was used
offline to compile the frozen AMC G22-relative-G30 coordinate, the predeclared
affine null, all three wrong-orbit alternatives and the direct `t +/- 15 s`
trajectory family. No AMC observation locator, header, payload byte or
numerical observation value was requested or opened.

This is a prospective prediction, not an orbital result. It grants no executor
or primary-access authority.

## Bound authorities

- prospective-plan manifest SHA-256:
  `0a3c1e3768566da6242d6aaffd6c751a23d6bf167c7f54d0498fe75f365609b0`;
- prospective-plan receipt canonical SHA-256:
  `615cce5046e218f583483175c8774357680d80450d5b97928685f728fb2fb89b`;
- compiler source commit:
  `d254526da7e0cd17ec2335992c61f8e6c628d1bb`;
- compiler source SHA-256:
  `94a0206cfd9d76f495a76256a500d41ac1feb2d8f56a7adf9499d1e8a8164d8c`;
- compiler manifest SHA-256:
  `1d277ed619b69bbb6b113e924202c8c7a6901e0816fd8aeedfa4bc696ef92a4e`;
- NOAA NAV: 71,457 compressed bytes,
  `ac512aaaa875a9807c152785427f0e40316710fad1d72d5d6c584389c997963e`;
- NOAA uncompressed NAV: 294,875 bytes,
  `762c18808dac8cc85b252ce6efe05a2ca87caefb8ebf286e9aabbb475470b771`;
- frozen nominal curve-set SHA-256:
  `5ca0813f5951b4cf8242b69654170db4153e56bfc9c90b0b0fb76cc55d3f0154`;
- frozen timing curve-set SHA-256:
  `e61db141bc507b0a19fcd91cba1a2a4db60c5819c89b9bc8c3709f573c469550`;
- prediction artifact canonical SHA-256:
  `c9f7236f3cc221cb8485fe82f0a739e720ee3725f9dbf7c7fcc54c4167794155`;
- seal canonical SHA-256:
  `83a52b2fbaa8f921532684cc87f292ffb976fb8972e595d21ffa0a645b4bb2f5`.

The transient NAV gzip was deleted after parsing and artifact verification. It
was orbital-model authority, not receiver observation data.

## Frozen physical prediction

The raw GPS grid contains 139 epochs from 05:41:30 through 06:50:30 at
30-second cadence. Raw index zero is the only coordinate anchor. Indices 0--78
are the witness prefix and indices 79--138 are the held-out suffix. No
observation-derived constant, rate, time phase or suffix fit exists.

All hypotheses use the same observer, grid, G30 reference, anchor and
receiver-independent geometric transform:

- `ORBITAL_G22`;
- `FROZEN_AFFINE_NULL`, fixed at `-410.277100928825 m/s`;
- `WRONG_ORBIT_G01`;
- `WRONG_ORBIT_G14`;
- `WRONG_ORBIT_G17`.

The exact held-out orbital-versus-null separations are:

| Alternative | Peak-to-peak (m) | RMS (m) |
|---|---:|---:|
| frozen affine | 162,247.192926 | 52,792.640265 |
| wrong orbit G17 | 162,722.879439 | 53,986.427266 |
| wrong orbit G14 | 220,149.108358 | 351,749.264685 |
| wrong orbit G01 | 498,274.704484 | 534,219.466094 |

The frozen affine remains the controlling alternative. Against the unchanged
`7,339.701235 m` pairwise decision guard, the exact physical margin remains
`154,907.491692 m`.

## Event time and visibility

The compiler propagated every orbital family directly at `t - 15 s`, `t` and
`t + 15 s`; it did not multiply a local slope by clock error. The largest
held-out non-affine timing excursion is `1,138.624941 m`, produced by G22 at
`-15 s`, exactly reproducing the frozen envelope.

All five satellites remain above the 15-degree floor over every required grid
and timing-envelope point. The controlling minimum is G01 at `+15 s`,
`25.725628237 deg`. Joint model visibility is therefore preserved.

## Interpretation and stop

The seal establishes that the exact frozen broadcast ephemeris still produces
the planned discriminating structure on the precise AMC scoring grid. It says
nothing yet about whether the AMC measurement agrees. A future positive result
would test observer-and-pass replication of PIE, while the shared POLARX5TR
receiver family remains an explicit limitation on hardware-design diversity.

The primary remains `SEALED_UNAUTHORIZED`. Building an executor or requesting
the AMC DOY221 artifact requires separate review. No geometry search, null
change, threshold change or prediction refit is justified before that decision.
