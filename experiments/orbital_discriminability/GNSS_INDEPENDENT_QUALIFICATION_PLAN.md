# Independent GNSS structural qualification plan

Status: `FROZEN_BEFORE_OBSERVATION_RECORD_ACCESS`.

This is a bounded qualification of one distinct historical artifact pair. It
does not select a primary, measure an orbit or reopen the closed 2026-08-03
GOLD/NLIB experiment. The historical terminal remains:

```text
MEASUREMENT_INVALID
TRUNCATED_REQUIRED_OBSERVATION_RECORD
```

## Qualification products

The pair was selected before inspecting observation records. It is the
immediately preceding UTC day at the same two independent station roots. Both
site logs and the product headers place the products inside unchanged
receiver/antenna intervals.

| Station | Exact product | Bytes | SHA-256 | Frozen receiver | Frozen antenna |
|---|---|---:|---|---|---|
| GOLD00USA | `GOLD00USA_R_20262140000_01D_30S_MO.crx.gz` | 2,175,246 | `0da86ed0b7fd2b4436d8e8fa5a4b2abeeadd8590af83544be9e98d1911517fe6` | JAVAD TRE_G3TH DELTA, serial 01538, firmware 4.2.03 | AOAD/M_T NONE, serial 401-B |
| NLIB00USA | `NLIB00USA_R_20262140000_01D_30S_MO.crx.gz` | 2,485,603 | `3a0313973e040adf619a0fb6e1e12415aa8c790d65606bffc1fe84e1545c10fc` | SEPT POLARX5TR, serial 3013995, firmware 5.7.0 | JAVRINGANT_DM SCIS, serial 00841 |

Sources:

- [GOLD site log](https://files.igs.org/pub/station/log/gold00usa_20250130.log)
- [NLIB site log](https://files.igs.org/pub/station/log/nlib00usa_20260310.log)
- [RINEX 3.04 specification](https://files.igs.org/pub/data/format/rinex304.pdf)

Artifacts may exist only in RAM during the run. Compressed bytes are checked
against the frozen size and SHA-256 before Hatanaka decompression. Compressed
and decoded buffers are overwritten after the receipt is produced. No
observation scalar may be serialized.

## Frozen qualification window

```text
GPS start: 2026-08-02T10:05:30
GPS stop:  2026-08-02T13:18:00
cadence:   30 s
raw epochs: 386
satellites: G11, G21
```

The four-minute displacement from the concluded 2026-08-03 window is the
predeclared one-day GPS sidereal-repeat shift. It is not selected from this
artifact's observation records. `TIME OF FIRST OBS` and `TIME OF LAST OBS`
must both declare GPS time and cover the complete frozen window. All 386 epoch
tags must be present on the exact 30-second grid.

The duration preserves the already frozen future sizing requirement:

```text
384 central-difference feature epochs
77 calibration feature epochs
307 held-out feature epochs
```

No calibration or held-out feature is computed in qualification.

## Physical field roles

| Role | Fields | Fatal rule |
|---|---|---|
| `CORE` | `L1C`, `L2W` | Missing/blank/omitted core, invalid scalar or nonzero LLI breaks the link segment. |
| `CYCLE_SLIP_CONTINUITY` | LLI on both phase fields; geometry-free phase continuity | LLI breaks the segment. Geometry-free second-difference violation fails the already selected full-window segment; it cannot move the segment. |
| `SAME_PATH_CODE_WITNESS` | `C1C`, `C2W` | Not fatal at every epoch. Each link/field must have at least 95% presence and be present at raw indices `1, 77, 78, 384`. |
| `OPTIONAL_DIAGNOSTIC` | `S1C`, `S2W` | Never fatal. Magnitudes are neither parsed nor compared because GOLD has no declared unit while NLIB declares dB-Hz. |

The fixed geometry-free rule is:

```text
g(t) = lambda_L1 * L1C(t) - lambda_L2 * L2W(t)
abs(second_difference(g)) <= 0.5 * min(lambda_L1, lambda_L2)
```

Only the violation count is retained. Phase values and derived series are
overwritten.

## Structural classification

For every station, frozen epoch, satellite and relevant field, emit one strict
JSON Lines row with no observation value. Field and continuation states are:

```text
PRESENT
BLANK
TRAILING_FIELD_OMITTED
CONTINUATION_SUPPORTED
CONTINUATION_UNSUPPORTED
RECORD_INVALID
```

An absent satellite record is classified `BLANK` with source-line class
`SATELLITE_RECORD_ABSENT`. RINEX 3 header continuation is supported; a
three-space observation-data continuation is unsupported and fails the run.

## Deterministic segment policy

- no interpolation;
- no gap bridging;
- exact 30-second adjacency only;
- missing core phase, invalid core phase, absent satellite record, nonzero LLI
  or non-observation epoch flag breaks a station/satellite segment;
- maximal segments are reported separately for all four links and for their
  joint intersection;
- the only admissible joint segment is the entire predeclared 386-epoch
  window;
- no later or longer segment may be substituted;
- geometry-free continuity is evaluated only after this structural segment is
  fixed; a violation fails qualification rather than selecting another span.

## Outcome semantics

`GNSS_INDEPENDENT_QUALIFICATION_PASSED` requires exact artifacts and headers,
complete epoch coverage, one full-window joint core segment, zero predeclared
geometry-free violations, admitted same-path code coverage and no unsupported
continuation or invalid record.

Any failed clause yields `GNSS_INDEPENDENT_QUALIFICATION_FAILED`. Neither
outcome selects or authorizes a primary.
