# GNSS structural qualification — bounded forensic closure

## Immutable parent result

The GOLD00USA–NLIB00USA primary remains closed exactly as recorded:

```text
MEASUREMENT_INVALID
TRUNCATED_REQUIRED_OBSERVATION_RECORD
```

Both artifacts are authorized only as:

```text
FORENSIC_DEVELOPMENT_ONLY
NEVER_PRIMARY_AGAIN
NEVER_SCORED_AGAIN
```

No orbital curve, residual, calibration statistic or held-out score was
computed. The compressed artifacts were fetched into RAM, checked against the
frozen byte counts and SHA-256 values before decompression, and overwritten
after a value-blind structural scan. No RINEX or observation value was written
to disk.

## Exact failure topology

GOLD was structurally complete for all 772 required G11/G21 records in the
frozen window. The historical decoder then entered NLIB and reached this first
structural refusal:

| retained field | result |
|---|---|
| station | `NLIB00USA` |
| GPS epoch | `2026-08-03T10:06:00.000000Z` |
| satellite | `G21` |
| required observable | `C2W` |
| header-declared index | `5` (zero based) |
| reconstructed field count | `3` |
| source-line class | `RINEX_3_OBSERVATION_DATA_RECORD` |
| continuation class | `SINGLE_LINE_VARIABLE_LENGTH_RECORD` |
| typed structural state | `TRAILING_FIELD_OMITTED` |

This exactly explains why the sealed decoder emitted its broader historical
reason: it requested `C2W` after only three serialized fields were available.
The new attribution does not rewrite that terminal result.

The [RINEX 3.04 specification](https://files.igs.org/pub/data/format/rinex304.pdf)
states that the 80-column observation-record limit was removed, that readers
must handle variable-length records, and that empty trailing fields may be
missing. Table A3 also defines one satellite observation record as `m`
ordered 16-character fields, with a missing observation represented by zero
or blank. Therefore the observed line proves an omitted trailing field, not a
truncated file, a receiver failure or a continuation defect. It also proves
that the frozen `C2W` requirement was not available at that epoch, so
measurement admission still fails before any physical score.

RINEX 3 header continuation for `SYS / # / OBS TYPES` is supported. A
three-space continuation of a RINEX 3 observation data line is not silently
joined: RINEX 3 removed that wrapping mechanism. Specification-derived tests
freeze both semantics.

## Physical roles of the signal family

`S1C` and `S2W` are not core measurement coordinates.

| Physical role | Smallest fields | Admission meaning |
|---|---|---|
| core phase coordinate | `L1C`, `L2W` | The dual-frequency carrier-phase coordinate can be formed. |
| cycle-slip / continuity witnesses | LLI attached to `L1C` and `L2W`; ordered epoch continuity | Phase continuity is structurally testable without treating SNR as lock truth. |
| same-path code witnesses | `C1C`, `C2W` | Code observations on the same signals witness link availability and support bounded phase/code consistency checks. |
| optional signal-strength diagnostics | `S1C`, `S2W` when present | Descriptive health context only; absence cannot reject the core coordinate. |

The smallest independently qualified family for one final GNSS vertical is
therefore:

```text
L1C + L2W core phase
+ LLI_ON_L1C + LLI_ON_L2W + epoch continuity
+ C1C + C2W same-path code witnesses
S1C/S2W optional
```

This is a qualification requirement, not selection or authority for a new
primary.

## Header and receipt hardening

Header admission now requires both `TIME OF FIRST OBS` and `TIME OF LAST OBS`.
The declared GPS interval must cover the complete frozen raw-input window; a
day-level filename or first epoch alone is insufficient.

Every future field-admission refusal can retain exactly the station, GPS
epoch, satellite, required observable, header index, reconstructed field
count, source-line class, continuation class and typed state. No scalar is
needed for attribution. `DESCRIPTION_ERROR` remains separate and leaves
measurement admission `NOT_EVALUATED`.

The strict typed states are:

```text
FIELD_PRESENT
FIELD_ABSENT
FIELD_BLANK
TRAILING_FIELD_OMITTED
CONTINUATION_SUPPORTED
CONTINUATION_UNSUPPORTED
DESCRIPTION_ERROR
RECORD_INVALID
```

## Closure

```text
GNSS_FAILURE_TOPOLOGY_EXPLAINED
```

The result improves measurement attribution only. It does not support or
damage the G11 orbital hypothesis and does not reopen GOLD/NLIB.
