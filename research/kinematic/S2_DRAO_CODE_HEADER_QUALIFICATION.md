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
