# ALGO/MDO independent-pair qualification outcome

Terminal outcome:

```text
GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED
```

This is a measurement-path result, not an orbital result. It admits the
ALGO00CAN/MDO100USA pair for a later primary-selection review. It does not
select, discover, open, or score any DOY219 observation product.

## Frozen execution identity

The executor was committed before observation access:

```text
source commit
6410ab195b2b6b535bcb57c357fce5300e8fffae

executor source SHA-256
9f2f81daf251caa6dfc9bc07225f8d5a300597969417da2a4566cab53b1aa155

executor manifest SHA-256
7aee72bac1660518769240eca4fd627067877fba0cda0a56519e514bd51d7e24

proof-plan manifest SHA-256
9f6d2ec41717666910b82e03341dbfc9ba6dd8285d481a93f0699e912206c3e4
```

Both complete products were materialized in RAM and hashed before the first
decode. Each succeeded on its first transport attempt.

| Station | Frozen product | Bytes | SHA-256 |
|---|---|---:|---|
| ALGO00CAN | `ALGO00CAN_R_20262170000_01D_30S_MO.crx.gz` | 4,305,409 | `339b4de652b3b9f1cbdf60804834fe97ff5dbf374e042e4871f5b761c5cfd821` |
| MDO100USA | `MDO100USA_R_20262170000_01D_30S_MO.crx.gz` | 3,560,934 | `fe7df3b7186519c108a192b2549f2b42f20fac353f6f38238db27b51164e0552` |

The compressed and decoded products were overwritten in memory after the
receipt was calculated. Neither representation was persisted.

## Header and transform admission

The real headers agree with the pre-access site-log identity:

| Property | ALGO00CAN | MDO100USA |
|---|---|---|
| RINEX | 3.05 | 3.04 |
| Receiver | SEPT POLARX5, serial 3015995, 5.3.2 | SEPT POLARX5, serial 3013421, 5.7.0 |
| Antenna | AOAD/M_T NONE, serial 303 | JAVRINGANT_DM SCIS, serial 02134 |
| Interval | 30 s | 30 s |
| Declared span | 00:00:00--23:59:30 GPS | 00:00:00--23:59:30 GPS |
| Required family | L1C, L2W, C1C, C2W | L1C, L2W, C1C, C2W |

No `SYS / SCALE FACTOR` record was present. The declared phase-shift records
are retained in the transform ledger; their static offsets are invariant under
the frozen second-time-difference health operator. `RCV CLOCK OFFS APPL`
defaults to zero under the cited RINEX semantics at both stations.

## Clause results

The exact 2026-08-05 05:54:00--07:03:00 GPS window contains all 139 expected
epochs on ALGO-G22, ALGO-G30, MDO1-G22 and MDO1-G30. The sole maximal segment
on every link is the complete 4,140-second window.

All 3,336 inspected station/epoch/satellite/observable structural states are
`PRESENT`. L1C/L2W have zero-or-blank LLI throughout. C1C/C2W have 100 percent
coverage on every link and are present at raw indices 1, 77, 78 and 137.

The frozen geometry-free second-difference limit is
`0.09514683639918244 m`. The observed aggregate maxima are:

| Station | Satellite | Maximum absolute second difference m |
|---|---|---:|
| ALGO00CAN | G22 | 0.0034601762890815735 |
| ALGO00CAN | G30 | 0.022172391414642334 |
| MDO100USA | G22 | 0.0035014115273952484 |
| MDO100USA | G30 | 0.004712935537099838 |

There are zero threshold violations. No orbit, navigation model, prediction,
null, residual, or orbital score was available to the qualifier.

## Receipt boundary

| Receipt | SHA-256 |
|---|---|
| `GNSS_INDEPENDENT_PAIR_QUALIFICATION_OUTCOME.json` | `cf26a411a0b77b79e951a21516c06333d26e7cc879f1dff09ce2e6eaa2fe3090` |
| `GNSS_INDEPENDENT_PAIR_QUALIFICATION_SUMMARY.json` | `68f14d331509f4bed96176314cab4428d80292d28da5a88430f4068948384493` |
| `GNSS_INDEPENDENT_PAIR_QUALIFICATION_COVERAGE.jsonl` | `544e1b6d584c3bb2e666d1cb5190743c60a9f2758bebd6fa4d656e714ad08b19` |

The JSON Lines receipt contains only the predeclared structural keys. It has
3,336 rows, strict JSON, no observation-value key, no non-finite scalar and no
phase, code or signal-strength value. The aggregate summary reports 1,112
phase scalars parsed transiently and zero persisted.

## Authorized and unauthorized claims

Authorized:

- the two frozen DOY217 artifacts were complete and hashable;
- ALGO/MDO expose the required explicit signal family and hardware identity;
- the complete joint qualification window, phase/LLI continuity, code witness,
  and model-blind geometry-free health clauses passed;
- ALGO/MDO may enter a separate review for one distinct primary.

Unauthorized:

- any orbital preference or satellite-identity claim;
- any statement about a DOY219 observation product;
- transfer of DOY217 continuity to another day without a new header and
  admission boundary;
- fallback to another pair, date, duration, field or threshold.

## Stop

The next maximum action is metadata-only selection and freezing of one
distinct ALGO/MDO DOY219 primary. This outcome does not authorize opening that
primary. No additional qualification run is permitted.
