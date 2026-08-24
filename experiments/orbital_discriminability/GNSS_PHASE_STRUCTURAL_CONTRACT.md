# G22/G30 phase structural-only contract

Status: `FROZEN_BEFORE_OBSERVATION_PRODUCT_DISCOVERY`.

This is not a new gate, a prospective experiment, or authority to open a
RINEX observation product. It freezes the value-blind boundary that must be
reviewed before the independent DOY 216 qualification pair can be touched.
The machine-readable contract is implemented by
`gnss_phase_structural_contract.py`; its canonical manifest SHA-256 is
`76c42055467c9b63e05911dc21611b6e26b0d9206f808b0c74b2f9c1696bcc86`.

## Frozen roles and geometry

The contract is bound to source geometry commit
`0a994396e8b286e040496113dbb40e0b6e8207ed` and to the exact phase-geometry
receipt SHA-256
`228359ad8e65dfe0191562ca601c6f47dad44ab36bab07736c63e8f9188f293c`.

| Role | Geometry | Raw GPS window | Access state |
|---|---|---|---|
| independent structural qualification | GOLD/NLIB, G22/G30, DOY 216 | 2026-08-04 04:47:00--07:59:30 | locator only; not discovered, materialized or opened |
| later prospective primary candidate | GOLD/NLIB, G22/G30, DOY 220 | 2026-08-08 04:30:30--07:43:00 | sealed, undiscovered and unauthorized |

Each raw window contains exactly 386 epochs at 30 seconds. The phase feature
uses raw indices 1--384; indices 1--77 are the frozen calibration prefix and
78--384 are the held-out suffix. Neither an absent record nor a later longer
segment may move those boundaries.

The predeclared qualification locators are the GOLD00USA and NLIB00USA daily
30-second mixed-observation products for DOY 216. A locator is not an artifact
identity: byte count and SHA-256 remain unknown until a later authorized
materialization, and no number has been invented here.

## Structural clauses

- `L1C` and `L2W` are the core phase fields on all four station/satellite
  links.
- LLI on both phase fields and the exact 30-second epoch grid are structural
  continuity witnesses. Missing core, nonzero/invalid LLI, an off-grid epoch,
  any nonzero epoch flag (including the RINEX power-failure flag), unsupported
  continuation or invalid record breaks the segment.
- No interpolation or gap bridging is permitted. The only structurally
  admissible joint segment is the entire predeclared 386-epoch window.
- `C1C` and `C2W` are same-path code witnesses. They need not be present at
  every epoch, but each station/satellite/field must reach 95% presence and be
  present at raw indices 1, 77, 78 and 384. They cannot correct or tune the
  phase score.
- `S1C` and `S2W` remain optional and cannot reject anything without a
  separate quantitative rule and coherent units.
- `TIME OF FIRST OBS`, `TIME OF LAST OBS`, GPS time, 30-second interval,
  receiver/antenna configuration and complete raw-window coverage are fatal
  header clauses.
- The existing conservative event-time interval remains -15 to +15 seconds.
  A structural receipt cannot tighten ADC-to-GPS binding.

The later scanner must traverse the complete intended window and classify
every relevant field as `PRESENT`, `BLANK`, `TRAILING_FIELD_OMITTED`,
`CONTINUATION_SUPPORTED`, `CONTINUATION_UNSUPPORTED` or `RECORD_INVALID`.
It must not stop at the first missing field and may retain no observation
scalar.

## Critical clause boundary

Geometry-free phase continuity is not structural. Computing its already
predeclared 0.09514683639918244 m second-difference limit requires actual
phase scalars even if those scalars are erased immediately. Therefore this
contract records it as `NOT_EVALUATED_BY_STRUCTURAL_ONLY_CONTRACT`.

This prevents the central category error:

```text
fields present + zero LLI != physical phase continuity proven
```

A successful value-blind scan can yield only
`GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW`. It cannot yield measurement
admission, detectability, an orbital score or a prospective outcome. A later,
separately reviewed authority would be required to evaluate phase health on
the qualification artifact.

## Frozen outcomes

```text
GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW
GNSS_PHASE_STRUCTURE_REJECTED
GNSS_PHASE_STRUCTURE_DESCRIPTION_ERROR
GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED
```

The description-error outcome leaves every physical and structural decision
`NOT_EVALUATED`; it is not a rejection.
Likewise, inability to materialize either complete artifact is
`GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED`: structure and physical clauses
remain `NOT_EVALUATED`.

## Exact next authority, not yet granted

The maximum next action is bounded discovery, complete-file materialization
and hashing, header admission and a value-blind structural scan of only the
two predeclared DOY 216 qualification locators. Phase/code scalars remain
forbidden. DOY 220 headers and payload remain forbidden. No orbital score may
run. Transport or description retry is permitted only before complete-file
hashing.

At this freeze point: no observation product was discovered or materialized,
no header was opened, and zero observation payload bytes or values were
accessed.
