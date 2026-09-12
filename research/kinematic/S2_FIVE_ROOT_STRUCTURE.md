# S2 five-root target-free structural qualification

## Physical question

Can the exact topology selected offline—ALGO, BOGT, MKEA and PIE1 in the fit,
with GOLD reserved for code-only held-out prediction—materialize a simultaneous
11-endpoint measurement structure on a distinct real day?

## New information produced

This run can establish only source materialization, header/receiver/transform
continuity, complete-day epoch topology, code/phase field presence, phase LLI
continuity and the existence of at least one structurally capable common
window. It cannot establish measurement accuracy, a physical error envelope,
a target identity, an orbit or a position.

## Frozen execution

DOY242 (2026-08-30) is the nearest earlier complete day to the five successful
DOY243 header ledgers. It is frozen before any access to these five artifacts;
there is no alternate date, station, field or retry. DRAO's separately closed
DOY242 artifact is not part of this topology and provides no admission evidence.

Every complete compressed artifact is materialized and SHA-256 hashed before
Hatanaka decoding. The scanner traverses the complete decoded day but interprets
only headers, epoch tags, satellite-row identity, required-field presence and
L1C/L2W LLI characters. It never converts an observation substring to a number.
Decoded and compressed payloads remain ephemeral.

An 11-epoch interval is structurally capable only if all four fit roots retain
at least five stable C1C/C2W/L1C/L2W rows with blank-or-zero phase LLI, GOLD
retains at least five stable C1C/C2W rows, and at least one satellite identity is
common to every root. Removing that unselected common identity must leave at
least four structural reference identities at each root. Candidate identities
are counted but neither selected nor persisted.

The run stops at one of:

- `FIVE_ROOT_STRUCTURE_QUALIFIED`
- `FIVE_ROOT_STRUCTURE_NOT_QUALIFIED`
- `FIVE_ROOT_STRUCTURE_EXECUTION_INVALID`

A pass authorizes only a separately frozen, distinct-artifact reference-only
numerical qualification. It does not authorize a primary target or S3.
