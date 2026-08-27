# ALGO/MDO DOY223 primary contract

## Status

`PRIMARY_PLAN_FROZEN_OBSERVATION_UNOPENED`

This is the proof boundary for one new ALGO/MDO primary. It is not a new gate,
does not reopen DOY219 and performs no observation request.

## Physical question

Does the frozen broadcast G22-relative-G30 geometry predict the held-out
continuous-phase coordinate

```text
(ALGO_G22 - ALGO_G30) - (MDO1_G22 - MDO1_G30)
```

better than the same-prefix affine null and the frozen G01, G14 and G17
wrong-orbit alternatives?

DOY217 established only the model-blind measurement capability. DOY219 ended
at `PRIMARY_ARTIFACT_MATERIALIZATION_FAILED` before a complete artifact,
header, measurement or score existed. The new information is therefore
whether the orbital preference can be observed on one genuinely new pass.

## Frozen primary

- date: 2026-08-11 / GPS DOY223;
- stations: ALGO00CAN and MDO100USA;
- raw window: 05:24:00 through 06:33:00 GPS, inclusive;
- held-out start: 06:03:00 GPS;
- cadence: 30 s;
- raw/feature epochs: 139/137;
- calibration/held-out feature epochs: 77/60;
- target/reference: G22/G30;
- wrong orbits: G01, G14 and G17;
- core phase: L1C and L2W;
- same-path code witnesses: C1C and C2W;
- interpolation and gap bridging: forbidden.

The two logical observation products are frozen without contacting them:

| Station | Product |
| --- | --- |
| ALGO00CAN | `ALGO00CAN_R_20262230000_01D_30S_MO.crx.gz` |
| MDO100USA | `MDO100USA_R_20262230000_01D_30S_MO.crx.gz` |

Each product has an ordered, closed BKG/CDDIS mirror set. A mirror is transport
for the same frozen logical product; it cannot change station, date, cadence,
window, feature, threshold or null. No fallback product, date, station pair or
second window exists.

## Frozen model geometry

The exact DOY223 NOAA/NGS broadcast-navigation authority is:

- compressed product: `brdc2230.26n.gz`, 71,403 bytes,
  SHA-256 `deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478`;
- uncompressed RINEX 2.11: 298,710 bytes,
  SHA-256 `340bf5e84504420d6770476c8f3c9cda78722fcc283cd34385f47b77ba6f4d2e`.

The orbit-only screen fixed:

| Alternative | Held-out non-affine peak-to-peak |
| --- | ---: |
| prefix affine | 123,441.481064 m |
| wrong orbit G01 | 55,330.087156 m |
| wrong orbit G14 | 54,990.701677 m |
| wrong orbit G17 | 194,596.734639 m |

G14 controls. The conservative pairwise envelope is 3,142.164149 m, leaving
51,848.537528 m. All required model tracks are jointly visible for the full
139-epoch interval; the minimum model elevation is 22.663660 degrees.

## Transport versus observation

The old zero-retry rule incorrectly made a transient TCP failure terminal even
when no artifact existed. This contract separates the states.

During `MATERIALIZING`, and only before complete-file hashing and any header or
value decode:

- at most two attempts per frozen mirror and four per product;
- at most 900 seconds wall-clock per product;
- 30-second connect and 180-second idle timeouts;
- resume only against the same mirror with a stable validator;
- never append a partial response from one mirror to another;
- a restart may use only the next mirror in the frozen order;
- partial bytes remain in quarantine.

The first complete-file SHA-256 defines artifact identity. Once both complete
hashes exist, network attempts are zero. Any header access, decoding,
measurement admission or scoring is non-retryable. There is no scientific
retry, second window, threshold change or feature substitution.

This does not weaken prospectivity: retries can repair transport delivery but
cannot inspect or adapt to the observation.

## Admission and outcome semantics

Both artifacts must cover the complete frozen grid, match the prior qualified
receiver/antenna configuration, expose every L1C/L2W link with zero LLI,
satisfy the frozen C1C/C2W witness rule and pass the unchanged geometry-free
continuity limit.

A transport failure is `PRIMARY_ARTIFACT_MATERIALIZATION_FAILED`; it is neither
`MEASUREMENT_INVALID` nor an orbital result. Measurement or detectability
failure remains separate. If admitted, one and only one held-out comparison
may prefer the orbital model, one named null, or return `AMBIGUOUS`.

## Bindings and stop

- geometry receipt canonical SHA-256:
  `2e5af124d25475900eb8b8f88535bb5ac70da10f6f2f3a796fe6f66699b330b3`;
- selected-row SHA-256:
  `15b9d49ff9a35740f6fb72207bbec58ec2671d6d7ece890caaf26c10b12b0ac4`;
- plan source commit:
  `4c400331e861391e97be632ca98c3e94e60ed4a2`;
- plan source SHA-256:
  `49f50ac7ab28b0e204e87633a8f623899990ee08b152e1a60287e77f96d99549`;
- plan manifest SHA-256:
  `2e7598068db8dd5c4fe27ee881340bb7096b8e878fda0a050048a11a70767055`.

At freeze, observation locator requests, HEAD requests, headers, payload bytes
and values are all zero. The plan grants no execution authority.

The next maximum work is an offline exact-hash DOY223 prediction seal. It must
freeze the complete orbital and null curves needed by the later scorer, still
before any observation request. Stop there for review.
