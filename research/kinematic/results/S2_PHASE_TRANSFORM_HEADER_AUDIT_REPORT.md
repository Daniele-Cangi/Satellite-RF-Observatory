# S2 phase-transform header audit — result

## Terminal

```text
PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED
```

The final evidence is DOY243 (2026-08-31 GPST), selected and committed before
access after two separately audited execution-invalid attempts.  This run is the
declared stop: no later date or station substitution is authorized.

## Execution history

| Plan | Access | Authoritative result | Reason |
|---|---:|---|---|
| DOY251 v1 | 8 compressed artifacts, 0 RINEX headers | `HEADER_AUDIT_EXECUTION_INVALID` | Incorrect CRINEX label in parser and synthetic fixture |
| DOY254 v2 | 8 HTTP 404, 0 artifacts | `HEADER_AUDIT_EXECUTION_INVALID` | Full-day product requested before its final epoch |
| DOY243 v3 | 8 complete artifacts, header-only | `PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED` | Three of eight roots failed the frozen format admission |

The v3 source/plan/code freeze is commit
`8551d7172f27cb6f75f8af189c30fa70e1be407e`.  Its result SHA-256 is
`1d8a0bd32cf22106070b74ae73ec83afd1e910cc0b4ac14e51e4d70161078a5b`.

## Root results

| Root | Header admission | Version | Required value divisor | Required phase shift | Legacy wavelength | Applied GPS DCB/PCV |
|---|---|---:|---|---|---|---|
| ALGO00CAN | qualified | 3.05 | 1 | 0 cycles | absent | absent |
| BOGT00COL | qualified | 3.04 | 1 | 0 cycles | absent | absent |
| MKEA00USA | qualified | 3.04 | 1 | 0 cycles | absent | absent |
| PIE100USA | qualified | 3.04 | 1 | 0 cycles | absent | absent |
| GOLD00USA | qualified | 3.04 | 1 | 0 cycles | absent | absent |
| DRAO00CAN | rejected | unknown | not evaluated | not evaluated | not evaluated | not evaluated |
| STJO00CAN | rejected | unknown | not evaluated | not evaluated | not evaluated | not evaluated |
| YELL00CAN | rejected | unknown | not evaluated | not evaluated | not evaluated | not evaluated |

The three rejections are exactly `UNSUPPORTED_OBSERVATION_FORMAT`.  That check
combines allowed version, observation-file type and GPS/mixed declaration.  The
runner did not retain which component differed.  Inferring a particular version
or treating the failure as proof of an incompatible phase scale is unauthorized.

## What this establishes—and does not

It establishes an exact header transform ledger for five products and an exact
admission failure for the complete fixed eight-root set.  It also establishes
that both RINEX scale mechanisms must remain distinct: `SYS / SCALE FACTOR`
divides stored numbers; legacy `WAVELENGTH FACT L1/2` governs ambiguity spacing
and does not itself rescale stored carrier cycles.

It does not qualify observation values, continuity, receiver noise, atmosphere,
reference navigation, an error envelope, target measurements or an inverse
position.  The run exposed zero observation body lines and persisted zero payload
bytes.  S3 remains unauthorized.

The smallest future scientific decision is no longer “try another day.”  It is
whether a separately justified measurement design can work with a capability set
whose format and transforms are predeclared before value access.  That decision
requires a new reviewed plan and independent evidence; it is not taken here.
