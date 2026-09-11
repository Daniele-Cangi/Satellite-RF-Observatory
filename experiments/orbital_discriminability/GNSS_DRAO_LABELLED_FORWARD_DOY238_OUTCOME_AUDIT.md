# DRAO labelled-forward DOY238 outcome audit

**DRAO_DOY238_DESCRIPTION_ERROR_FROZEN_NO_PHYSICAL_OUTCOME**

The one-use run materialized the exact selected product on its first transport
attempt. The complete 2,852,212-byte file was hashed as
`1e1e77bac8661abba2cc54b85f1deee2ba470729b1dbf9000b0cdc4d50c81cc4`
before decompression. The runner then stopped with the immutable outcome
`PRIMARY_NOT_EVALUATED / DESCRIPTION_ERROR / PHASE_SHIFT_MALFORMED`.

This is not a measurement rejection and contains no evidence for or against
the orbital prediction. DOY238 is consumed and cannot be reopened, retried or
rescored.

## Clause attribution

The complete artifact hash and decompression succeeded. Deterministic control
flow also shows that composite identity, window coverage, the required GPS
observable declaration and scale-factor parsing had passed before the phase
ledger raised. Complete epoch/PRN topology, model-blind witnesses and every
orbital/null score remained `NOT_EVALUATED`. The runtime outcome's generic
clause map said the artifact hash was not evaluated; this audit corrects that
description without modifying the immutable outcome.

No observation scalar was read: header validation stopped before epoch-record
traversal. No compressed artifact, decoded RINEX or observation value was
persisted.

## What is and is not known

The implementation gap is confirmed. The parser forced every phase-shift
record with an observation code through numeric conversion, so a blank numeric
correction was not representable. RINEX 3.04 section 5.2.12 explicitly permits
an observation code with the rest of the record blank for an uncorrected
reference signal. Preexisting receipts in this repository independently retain
real records such as `G L1C` and `G L2W` in precisely that form.

The exact DOY238 header line was intentionally not retained and its volatile
buffer was erased. We therefore do **not** assert that this exact syntax caused
the target failure. The narrow authorized attribution is a phase-shift
description error plus a confirmed parser coverage hole; the precise target
record remains unresolved.

## Next physical path

DOY238 is not repaired or replayed. If the DRAO route continues, the smallest
independent opportunity is the still-unconsumed rank-3 DOY234 geometry from the
pre-observation shortlist. Before selecting its observation artifact, a new
source-specific executor must distinguish reference-signal blank correction,
explicit numeric correction, system-level unknown alignment and malformed or
conflicting syntax. It must otherwise preserve the same witness limits, null
discipline and outcome semantics allowed by that geometry.
