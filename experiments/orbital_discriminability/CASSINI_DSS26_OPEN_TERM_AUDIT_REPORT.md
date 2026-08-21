# Cassini DSS-26 physical-envelope audit

Date: 2026-08-20

Outcome: **`CASSINI_OPEN_TERM_BOUND_UNAVAILABLE`**

This is a bounded metadata-only audit of the seven physical terms already
declared by the DSS-26 compiler. It is not a new gate. The complete RSR
artifact was not opened, read, re-hashed or decoded during this audit. DSS-14
primary and reserve remain sealed and unopened. The development role is now
closed.

## Frozen comparison

The authoritative prior outcome remains
`CASSINI_OPEN_TERM_CAN_ABSORB_HELDOUT_SEPARATION`. The only controlling
signature is the real-NCO orbital prediction against the calibration-prefix
affine recorded-baseband null:

```text
held-out peak-to-peak = 0.06391264328448062 Hz
```

The affine null was neither removed nor weakened. The much larger
steering-only and Saturn-barycenter differences remain non-controlling. No free
time phase and no held-out refit were introduced.

The exact committed header grid was reconstructed from its descriptive receipt:
`9,651` representative epochs at one-second cadence from
`2005-06-06T17:50:01.500500Z` through
`2005-06-06T20:30:51.500500Z`. The first `1,931` records are the unchanged
calibration prefix; the final `7,720` are held out.

## Seven-term attribution

Each available central curve received the same two-parameter affine fit on the
calibration prefix. The table reports the untouched suffix residual. A central
model is not an uncertainty bound: it is shown diagnostically and contributes
zero envelope reduction unless a deterministic error limit is documented.

| Existing term | Provenance | Central non-affine p-p | Central non-affine RMS | Admitted bound | Reason |
|---|---|---:|---:|---|---|
| `PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY` | `INDEPENDENT_OF_TARGET_RF` | `0.006576306361 Hz` | `0.003107892424 Hz` | unavailable | IERS weak-field Sun/Earth/Saturn central model; no mission-specific truncation/error bound |
| `RELATIVISTIC_PROPAGATION_LIGHT_TIME` | `INDEPENDENT_OF_TARGET_RF` | `0.000094837846 Hz` | `0.000044307088 Hz` | unavailable | IERS static-body central diagnostic; omitted bodies/moving-body and higher-order terms are not bounded |
| `EARTH_TROPOSPHERE` | `INDEPENDENT_OF_TARGET_RF` | `0.014731094273 Hz` | `0.008013625910 Hz` | unavailable | exact applicable TSAC TRO coefficients plus documented seasonal central model; `FITSIG` and approximate elevation mapping are not hard error limits |
| `EARTH_IONOSPHERE` | `INDEPENDENT_OF_TARGET_RF` | `0.000053973624 Hz` | `0.000025103316 Hz` | unavailable | exact applicable TSAC line-of-sight ION coefficients; `FITSIG` is not a hard residual limit |
| `INTERPLANETARY_PLASMA` | `UNKNOWN` | unavailable | unavailable | unavailable | the bounded SAGR1 ancillary set contains no applicable solar-plasma calibration and no independent finite ray-path bound was found |
| `STATION_HARDWARE_DELAY` | `UNKNOWN` | unavailable | unavailable | unavailable | DSN-wide statistical/generic stability does not bind the actual 2005 DSS-26 end-to-end receive chain |
| `AVAILABLE_MEDIA_CALIBRATION` | `INDEPENDENT_OF_TARGET_RF` | `0.014677120649 Hz` | `0.007988724846 Hz` | unavailable | ION and TRO exist, but this is a non-additive coverage control and may not be counted again as a third medium |

No outcome-conditioned product was used. In particular, the central values
above did not reduce the envelope merely because they are numerically small.

The ION product is the DSCC-10/SCID-82 interval
`2005-06-06T15:35Z`–`2005-06-07T05:40Z`. The TRO computation uses the two
DSCC-10 intervals that meet at `18:00:00/18:00:00.001Z`, together with the
documented seasonal central model. The exact source byte counts and SHA-256
values are in the receipt. These are calibration metadata, not target RF.

## Timing and detector consequence

The existing RSR first-sample bound remains `100 ns`. Direct frozen-trajectory
evaluation at `t - 100 ns` and `t + 100 ns` gives a conservative maximum
absolute frequency envelope of `0.000002806089 Hz`; the two-sided term is
`0.000005612177 Hz`. Because this scale approaches binary64 cancellation in the
frequency factor, the recorded number conservatively retains that numerical
floor rather than subtracting it away.

The frozen detectability inequality is:

```text
signature > 3 R_f + 2 E_t + open_term_envelope
```

Since the seven-term envelope is unavailable, both the remaining physical
margin and the maximum admissible detector resolution are **unavailable**.
Only a best-case upper ceiling can be stated: if every unresolved physical term
were exactly zero, then `R_f < 0.021302343702 Hz`. That number is not an
admission requirement and does not authorize detector implementation.

## Why DSS-26 closes here

The problem is not a demonstrated model failure and not a demonstrated absence
of carrier. The metadata path has reached a regime in which the model-conditioned
NCO leaves only `63.9 mHz` of non-affine orbital structure, while pass-specific
hard uncertainty bounds for media and station hardware are absent. Continuing
into IQ would therefore produce a measurement whose negative result could not
be attributed cleanly.

The smallest next physical step is **header-only evaluation of the two remaining
Cassini candidates**, but only after explicit role reassignment. It would test
whether their real NCO transforms preserve a larger orbital-versus-affine
baseband residual without touching IQ. The current DSS-14 primary and reserve
remain sealed under the present authority. A fixed-NCO search is broader;
phase-continuous analysis does not close the physical terms; multi-frequency
differencing is physically promising but requires a larger measurement design.

## Reproducibility and sources

- Audit source SHA-256:
  `71da141120c51e6a2e7a88df859ba47f3c11dec98a8cfd15bcff82b2118277ba`.
- Audit manifest SHA-256:
  `5144a6c74c82ec0a33ac250ae2703f8ddb6d87762a60166a00299f326ab15f67`.
- Exact runtime: SpiceyPy `7.0.0`, NumPy `2.3.3`, and the four already frozen
  exact-hash kernels; no new trajectory kernel was selected.
- [IERS proper-time model](https://iers-conventions.obspm.fr/content/chapter10/tn36_c10.pdf)
- [IERS gravitational propagation model](https://iers-conventions.obspm.fr/content/chapter11/tn36_c11.pdf)
- [JPL astrodynamic constants](https://ssd.jpl.nasa.gov/astro_par.html)
- [DSN frequency and timing](https://deepspace.jpl.nasa.gov/dsndocs/810-005/304/304C.pdf)
- [DSN media-calibration interface](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/cors_0103/document/trk_2_23_000531.txt)
- [Applicable ION product](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/cors_0103/sagr1_ancillary/ion/s11sags2005_152_2005_181.ion)
- [Applicable TRO product](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/cors_0103/sagr1_ancillary/tro/s11sags2005_152_2005_184.tro)
