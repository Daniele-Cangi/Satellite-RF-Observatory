# Post-DRAO labelled-forward structural change of abstraction

**DRAO_CORE_STRUCTURE_PROVEN_TRANSFORM_RECEIPT_UNRESOLVED**

This is an offline audit of frozen receipts. It does not create a gate, reopen
the DOY237 artifact, select another artifact or evaluate any measurement or
orbital score.

```text
Physical question:
Can the two description failures be placed at the correct causal boundary
without weakening the final orbital test?

New information produced:
The marker literal is not an independent identity root. Transform semantics
are not part of record topology, but remain a hard precondition before numeric
measurement interpretation.

Why the existing outcome could not answer it:
The runtime collapsed representation and parser states into two booleans.

Minimum experiment:
An offline comparison of the immutable outcome with authority frozen before
DOY237 access and with the already retained composite identity roots.

Stop condition:
One disposition for identity, structure and transforms; zero artifact access.
```

## Result

The immutable runtime output remains `DRAO_STRUCTURE_TOPOLOGY_REJECTED`. The
epistemic audit remains `DRAO_STRUCTURE_DESCRIPTION_ERROR`. Neither record is
rewritten.

The change is where the clauses belong:

```text
composite station/artifact identity       SATISFIED
record and continuity topology            SATISFIED
artifact-specific numeric transform       UNRESOLVED_BY_RECEIPT
physical witnesses                        NOT_EVALUATED
orbital-versus-null score                  NOT_EVALUATED
```

This does not turn DOY237 into a primary and does not authorize a score.

## Identity: remove the marker literal from the causal path

Before DOY237 access, the frozen change-of-abstraction decision had already
declared `MARKER NAME` a descriptive consistency field rather than a
standalone station key. The same authority bound station identity through:

- the frozen BKG artifact and site ID `DRAO00CAN`;
- DOMES `40105M002`;
- receiver `SEPT POLARX5`, version `5.2.0`;
- antenna/radome `TWIVC6050 SCIS`;
- the frozen GPS date and observation interval.

All of those roots passed in the retained receipt. Therefore the composite
identity root is satisfied. The unretained marker value remains
`UNRESOLVED_DESCRIPTIVE_NOT_FATAL`: this audit neither claims that it equalled
`DRAO` nor that it contradicted DRAO.

This is not a post-outcome relaxation. It applies a decision that was frozen
before the artifact was opened and removes a representation-dependent field
which carries no additional independent identity root.

## Structure: the positive result is real and narrow

The retained value-blind facts prove the complete required record topology:

- 139 of 139 normal epochs on the exact grid;
- 834 of 834 required satellite/epoch pairs;
- C1C, C2W, L1C and L2W present on every required pair;
- L1C/L2W LLI blank or zero throughout;
- one complete 139-epoch segment for each of G14/G15/G17/G20/G24/G30.

The maximum claim is `CORE_RECORD_TOPOLOGY_SATISFIED`. It says nothing about
numeric continuity, phase/code agreement, detectability or orbit.

## Transforms: relocate, do not erase

`SYS / SCALE FACTOR` and `SYS / PHASE SHIFT` cannot make an observable field
present or absent and cannot change an LLI or epoch-grid fact. They therefore
do not belong inside structural-topology admission.

They do remain mandatory before interpreting numeric observations:

| Term | Structural role | Numeric role | Current state |
|---|---|---|---|
| `SYS / SCALE FACTOR` | none | map stored values to declared units; specified absence means unity | `UNRESOLVED_BY_RECEIPT` |
| `SYS / PHASE SHIFT` | none | record the already-applied static phase correction and prevent double application | `UNRESOLVED_BY_RECEIPT` |
| `RCV CLOCK OFFS APPL` | event-time/coordinate boundary | control epoch and observation clock correction | `SATISFIED` |

A valid static per-track phase offset is annihilated by the frozen second-time
difference and by a prefix constant or affine projection. That invariance does
not permit us to assume that this artifact had a valid/default declaration:
the receipt discarded the evidence needed to distinguish absence, valid
coverage, malformed syntax and conflict. Scale semantics likewise cannot be
invented.

The correct causal order is therefore:

```text
record topology
-> attributable transform ledger
-> numeric physical witnesses
-> frozen orbital-versus-null score
```

`UNRESOLVED` does not become zero, a default, or a measurement rejection.

## Disposition of DOY237

The artifact is closed as `CONSUMED_STRUCTURAL_EVIDENCE_ONLY`:

- core structure: proven;
- transform ledger: unresolved;
- integrated-proof readiness: false;
- primary admission: false;
- same-artifact reopen/retry: forbidden;
- fallback artifact: not selected.

The positive structure cannot be promoted into measurement validity. Equally,
the receipt failure cannot reject the DRAO measurement path.

## What not to build next

Do not repair and replay the same parser, introduce another structural gate or
select a fallback artifact merely because this receipt was incomplete. Those
actions would optimize description machinery rather than test an orbit.

If DRAO remains the selected physical route after review, the minimum future
vertical is one integrated labelled-forward execution. It must retain the
composite identity and typed transform ledger before numeric conversion, run
the already frozen model-blind witnesses, and only then allow the frozen
orbital/null comparison. Any failed admission clause leaves every downstream
claim `NOT_EVALUATED`. There is zero post-hash retry and no held-out refit.

This audit does not begin that vertical: it stops before geometry search,
product selection, network, header, payload, measurement or score.
