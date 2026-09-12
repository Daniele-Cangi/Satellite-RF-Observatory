# S2 DRAO code-only header qualification

This is the smallest physical follow-up authorized by the closed code-only
held-out topology audit. It is a new, single-station code-coordinate
qualification, not a continuation or repair of the failed eight-root
carrier-phase audit.

## Physical question

Can the one frozen DRAO product expose an explicit, reversible C1C/C2W
ionosphere-free code coordinate with a complete-day GPST declaration and no
unqualified applied clock, DCB or PCV transform?

## New information produced

Only a hash-bound header receipt and a code-coordinate transform ledger. A
positive result qualifies neither observation-record continuity nor any error
envelope, target value, orbit or orbital score.

## Frozen artifact and stop rule

The sole product is
`DRAO00CAN_R_20262420000_01D_30S_MO.crx.gz`, DOY242 (2026-08-30), from the
already used BKG public archive. DOY242 is the nearest earlier complete day not
used by the closed chain. There is one attempt, no retry, no alternate date,
station or code field, and no relaxation from named C1C/C2W.

The complete compressed artifact must be materialized in memory and hashed
before the header parser runs. Decompression stops at `END OF HEADER`; Hatanaka
body decoding and all observation/target access are absent. Raw payload and
header text are destroyed rather than persisted.

The only outcomes are:

- `DRAO_CODE_HEADERS_QUALIFIED`
- `DRAO_CODE_HEADERS_NOT_QUALIFIED`
- `DRAO_CODE_HEADER_EXECUTION_INVALID`

If qualified, the next blocker is a separately frozen, non-target structural
continuity and physical-envelope qualification. S3 remains unauthorized.

## Frozen outcome

The one attempt terminated `DRAO_CODE_HEADERS_NOT_QUALIFIED`. The BKG product
was available (HTTP 200), and all 2,891,896 compressed bytes were materialized
and hashed before parsing. Its SHA-256 is
`5064142f469f2adba4d5b2e561007794fa59f4a50f1b12549830ebb0bb321de1`.
The parser exposed 276 header lines and zero observation-body lines.

Admission stopped at `UNSUPPORTED_NAMED_CODE_FORMAT`. Consequently the product
does not provide the frozen RINEX 3.04/3.05 named-observable coordinate needed
to distinguish C1C from C2W under this contract. A legacy code label cannot be
silently promoted to C1C or C2W because that would erase tracking-code identity
and change the predeclared physical coordinate after access.

This is a capability rejection, not a parser failure and not evidence that DRAO
lacks measurements. No observation record, observation value, target identity,
navigation product or orbit was accessed. DRAO is closed for this code-only
held-out route; neither another date nor a relaxed code-field alias is authorized.
The result SHA-256 is
`214cbc3c19f059d933b381a33aa003dcda3952ad32f8b8e8e955ec94c371c242`.
