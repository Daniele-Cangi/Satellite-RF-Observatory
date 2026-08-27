# ALGO/MDO next-primary orbit screen

## Outcome

`NEXT_PRIMARY_GEOMETRY_SELECTED`

The closed DOY 219 ALGO/MDO experiment remains immutable as
`PRIMARY_ARTIFACT_MATERIALIZATION_FAILED`. This screen did not retry, reopen,
rescore or substitute that experiment. It selected a new geometry before any
new observation-product discovery or access.

## Physical question

Does a new ALGO/MDO pass of G22 relative to G30 preserve a positive held-out
orbital-versus-null margin after the already frozen phase-coordinate physical
envelope?

The bounded candidates were DOY 221--223. The station roots, target, reference,
wrong-orbit family, 30 s cadence and 77/60 calibration/held-out partition were
fixed before navigation access. All five model satellites had to remain above
15 degrees at both stations for every one of the 139 raw epochs.

## Model authority

The inaccessible BKG transport and the Earthdata login response from CDDIS
produced no navigation input and no screen outcome. The final frozen authority
uses NOAA/NGS Daily Global Navigation File RINEX 2.11 products. These contain
broadcast ephemerides, not receiver observations.

| DOY | Product | Compressed bytes | Compressed SHA-256 |
| --- | --- | ---: | --- |
| 221 | `brdc2210.26n.gz` | 71,457 | `ac512aaaa875a9807c152785427f0e40316710fad1d72d5d6c584389c997963e` |
| 222 | `brdc2220.26n.gz` | 71,479 | `e56961025c43476f57a4c087adc20b9ce7f073192394607a17f57a26ff34a025` |
| 223 | `brdc2230.26n.gz` | 71,403 | `deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478` |

The complete byte counts and hashes for compressed and uncompressed products
are retained in the receipt. The temporary navigation copies were destroyed
after the sweep.

## Ranking

Each day supplied 165 complete candidate windows. The order below is by the
frozen remaining physical margin, followed by controlling separation, minimum
model elevation and earliest start.

| Rank | DOY | Raw window (GPS) | Held-out start (GPS) | Controlling null | Separation (m p-p) | Pairwise envelope (m p-p) | Remaining margin (m) | Minimum model elevation |
| ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | 223 | 2026-08-11 05:24:00--06:33:00 | 06:03:00 | wrong-orbit G14 | 54,990.702 | 3,142.164 | 51,848.538 | 22.664 deg |
| 2 | 222 | 2026-08-10 05:28:00--06:37:00 | 06:07:00 | wrong-orbit G14 | 54,953.592 | 3,135.302 | 51,818.290 | 22.711 deg |
| 3 | 221 | 2026-08-09 05:32:00--06:41:00 | 06:11:00 | wrong-orbit G14 | 54,916.068 | 3,128.079 | 51,787.990 | 22.759 deg |

The three dates are scientifically almost tied: DOY 223 leads DOY 222 by only
30.248 m of remaining margin. The choice is nevertheless deterministic and was
not informed by receiver data availability or values.

## Selected geometry

The selected raw interval is 2026-08-11 05:24:00--06:33:00 GPS
(05:23:42--06:32:42 UTC). The held-out suffix begins at 06:03:00 GPS.

Minimum joint elevations over the window are:

| Satellite role | PRN | Minimum elevation |
| --- | --- | ---: |
| wrong orbit | G01 | 22.664 deg |
| controlling wrong orbit | G14 | 57.653 deg |
| wrong orbit | G17 | 37.688 deg |
| target | G22 | 39.237 deg |
| reference | G30 | 34.699 deg |

The prefix-affine null is much farther away (123,441.481 m p-p); wrong-orbit
G14 controls at 54,990.702 m p-p. The conservative pairwise physical envelope
is 3,142.164 m p-p. Its largest contribution is the direct +/-15 s station
event-time trajectory envelope (2,477.178 m pairwise), followed by broadcast
orbit accuracy (312.560 m pairwise). The remaining physical margin is positive
by 51,848.538 m.

## Interpretation and stop

The result establishes only that DOY 223 has a discriminative model geometry
for the already scoped ALGO/MDO measurement family. It is not a GNSS
measurement, not an orbital score and not evidence that the two observation
artifacts exist or are structurally admissible.

Observation access remained exactly zero: no observation locator, product,
header, payload byte or value was read. No prospective plan is frozen yet.
The next maximum action is to freeze one distinct-primary contract for DOY 223,
including bounded historical-download resume before complete-file hashing and
strict zero retry after observation admission. Only after that freeze may the
two exact observation artifacts be materialized.

Receipt SHA-256:
`2e5af124d25475900eb8b8f88535bb5ac70da10f6f2f3a796fe6f66699b330b3`.

Frozen source commit:
`7a5d88633fdb086590eaf29c1fad2e6b4d3ead59`.
