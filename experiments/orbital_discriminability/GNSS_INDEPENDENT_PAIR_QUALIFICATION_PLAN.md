# ALGO/MDO independent-pair qualification plan

Status: `FROZEN_BEFORE_OBSERVATION_BODY_ACCESS`.

This is a bounded proof boundary, not a new gate. It selects one qualification
artifact pair and stops before either compressed RINEX body is opened. The
machine-readable plan is implemented by
`gnss_independent_pair_qualification_plan.py`; manifest SHA-256:

```text
9f6d2ec41717666910b82e03341dbfc9ba6dd8285d481a93f0699e912206c3e4
```

The plan source was frozen at commit
`6bda280` with canonical source SHA-256
`7f5a0959b3280014ac8811efb614331135c26cbcfece61ea6685fca9f79147b0`.

## Physical question

Can two hardware roots outside GOLD/NLIB preserve the frozen G22-relative-G30
continuous-phase coordinate well enough to support a later held-out station
test?

The geometry screen alone cannot answer this. It proved a positive model
margin but did not establish signal identity, event-time coverage, continuity,
receiver lineage or model-blind phase health.

## Metadata-only change of pair

The geometry screen ranked three pairs. Qualification metadata changes the
choice without inspecting any observation body or value.

| Screen rank | Pair | Complete margin m | Metadata decision | Reason |
|---:|---|---:|---|---|
| 1 | DRAO00CAN / WES200USA | 92649.071 | `CAPABILITY_REJECTED` | WES declares a RINEX v2 primary feed; standard RINEX3 locators return 404 on DOY216--218. Mapping generic RINEX2 `L1/L2` to frozen `L1C/L2W` is forbidden. |
| 2 | DRAO00CAN / ALGO00CAN | 75312.298 | available, not selected | Positive and RINEX3-capable, but it retains more shared Canadian federal institutional lineage. |
| 3 | ALGO00CAN / MDO100USA | 47828.042 | `QUALIFICATION_ROLE_SELECTED` | Distinct DOMES, hardware serials, antennas, agencies and primary data centers with a still-large complete margin. |

This is not a fallback after seeing RF. It is capability admission before
payload access. The [IGS station page for WES](https://network.igs.org/WES200USA)
identifies its primary feed as RINEX v2. The [IGS MGEX data page](https://igs.org/mgex/data-products)
documents the long RINEX3 product naming convention used by this plan.

If ALGO/MDO qualification fails, no other pair or date is selected
automatically.

## Independent root evidence

The official IGS site logs freeze these historical configurations before both
DOY217 and DOY219:

| Property | ALGO00CAN | MDO100USA |
|---|---|---|
| DOMES | 40104M002 | 40442M012 |
| Agency | NRCan / Canadian Geodetic Survey | McDonald Observatory; JPL operational contact |
| Primary data center | CDDIS | JPL |
| Receiver | SEPT POLARX5 5.3.2 | SEPT POLARX5 5.7.0 |
| Receiver serial | 3015995 | 3013421 |
| Receiver installed | 2026-03-25 19:19Z | 2026-03-18 14:57Z |
| Antenna | AOAD/M_T NONE | JAVRINGANT_DM SCIS |
| Antenna serial | 303 | 02134 |
| Clock | internal | internal |

The shared receiver manufacturer is not counted as an independent root.
Independence comes from the distinct physical receivers, antennas, sites,
organisations and ingest lineages. Exact header declarations must still match
the frozen site-log configuration during qualification.

Sources:

- [ALGO00CAN](https://network.igs.org/ALGO00CAN)
- [MDO100USA](https://network.igs.org/MDO100USA)
- [RINEX 3.04](https://files.igs.org/pub/data/format/rinex304.pdf)

## Sole qualification role

```text
stations: ALGO00CAN + MDO100USA
date: 2026-08-05 / DOY217
raw GPS window: 05:54:00--07:03:00
cadence: 30 s
raw epochs: 139
```

Only these locators may be materialized after separate authorization:

```text
ALGO00CAN_R_20262170000_01D_30S_MO.crx.gz
MDO100USA_R_20262170000_01D_30S_MO.crx.gz
```

Metadata-only HEAD returned HTTP 200 with content lengths 4,305,409 and
3,560,934 bytes respectively. These numbers and ETags are descriptive, not
artifact identity. Full byte count and SHA-256 remain unknown until complete
materialization, and must be frozen before decode.

No DOY219 product locator appears in the plan.

## Geometry regression

The exact-hash DOY217 broadcast navigation authority was evaluated in RAM on
the qualification grid. Minimum elevations in degrees are:

| Station | G22 | G30 | G01 | G14 | G17 |
|---|---:|---:|---:|---:|---:|
| ALGO00CAN | 41.473 | 32.325 | 50.820 | 59.871 | 39.976 |
| MDO100USA | 51.469 | 51.147 | 21.425 | 57.224 | 70.992 |

All orbital and wrong-orbit links remain above 15 degrees. Navigation is used
only to validate the representative window; the future qualification executor
must not receive an orbit or predicted phase coordinate.

## Model-blind measurement clauses

Core coordinate:

```text
L1C + L2W carrier phase
(ALGO_G22 - ALGO_G30) - (MDO1_G22 - MDO1_G30)
```

Qualification requires:

- RINEX3/4 explicit observable identity;
- expected receiver serial, firmware and antenna declarations;
- `TIME OF FIRST OBS` and `TIME OF LAST OBS` covering the complete window;
- GPS time and exact 30-second epochs;
- all 139 epochs on all four satellite/station links;
- `L1C` and `L2W` present with zero LLI;
- no interpolation or gap bridging;
- geometry-free maximum absolute second difference no greater than
  `0.09514683639918244 m`;
- `C1C/C2W` coverage of at least 95% per link and presence at raw indices
  1, 77, 78 and 137.

`C1C/C2W` are same-path witnesses and cannot correct phase. `S1C/S2W` remain
optional diagnostics and cannot reject the artifact without a new
predeclared quantitative rule.

## Future execution boundary

After separate authorization, the qualifier may make at most two bounded
transport attempts per locator. Resume is allowed only before a complete-file
hash exists and before decoding. Complete artifacts are hashed in RAM, decoded
values remain ephemeral, and all compressed/decoded observation persistence
is zero.

The executor must be orbit-model blind. It may return only:

```text
GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED
GNSS_INDEPENDENT_PAIR_QUALIFICATION_FAILED
GNSS_INDEPENDENT_PAIR_ARTIFACT_MATERIALIZATION_FAILED
GNSS_INDEPENDENT_PAIR_DESCRIPTION_ERROR
```

A pass authorizes only a later review to select and freeze the ALGO/MDO DOY219
primary. A failure closes this pair. Description or transport failure is not a
physical rejection.

## Access boundary

At this freeze point:

- qualification observation body bytes: `0`;
- qualification headers: `0`;
- qualification values: `0`;
- primary product locators: `0`;
- primary headers, payload and values: `0`.

Stop here for review. Do not materialize either qualification body and do not
discover a DOY219 primary product under this commit.
