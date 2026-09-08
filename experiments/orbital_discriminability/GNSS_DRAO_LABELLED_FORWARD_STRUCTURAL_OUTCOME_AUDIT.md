# DRAO labelled-forward structural outcome audit

**DRAO_STRUCTURE_DESCRIPTION_ERROR**

The one-use runtime record remains immutable:

```text
DRAO_STRUCTURE_TOPOLOGY_REJECTED
HEADER_CLAUSE_UNSATISFIED:MARKER_SITE_DRAO
HEADER_CLAUSE_UNSATISFIED:SCALE_AND_PHASE_SHIFT_SEMANTICS_SUPPORTED
```

That record does not authorize a measurement-path or structural-topology
rejection. Both controlling predicates lost distinctions required by the
frozen contract, so the epistemically valid terminal is a description error.
The artifact is not reopened and the runtime output is not rewritten.

## What the execution established

The exact 2,849,014-byte artifact was hashed before decompression as
`bf9cc66a9a109566cd7011ddb9768b5f00a195d7d4b282bee536432dc97ec967`.
The complete 23,676,145-byte decoded RINEX was hashed before traversal as
`2b8cf9d4cde28a2f3568a1c79032eff7b9152d95e2cd93e6ec6b220284409c38`.

The value-blind record topology itself is complete:

- all 139 expected epochs exist with normal flag and 0.0 s grid deviation;
- every G14/G15/G17/G20/G24/G30 track spans indices 0--138;
- C1C, C2W, L1C and L2W are present in all 834 required satellite/epoch pairs;
- L1C and L2W LLI are blank or zero in all 834 pairs each;
- 604 additional GPS track records were counted as descriptive only;
- no observation scalar was converted or persisted;
- no physical witness, orbital model or score was evaluated.

This supports `CORE_RECORD_TOPOLOGY_SATISFIED`. It does not yet support
integrated-proof readiness.

## Failure attribution

### Marker/site identity

The frozen contract requires marker/site identity *compatible* with
`DRAO00CAN`, DOMES `40105M002` and the independently frozen hardware identity.
The runner instead repeated the already documented over-narrow predicate:

```text
normalize(MARKER NAME) == "DRAO"
```

The receipt did not retain the observed marker or alias relationship. DOMES,
receiver and antenna all passed, but the missing marker evidence prevents us
from distinguishing a real contradiction from a four-character/nine-character
representation difference. No cause is inferred.

### Scale and phase-shift semantics

The contract requires explicit handling and explicitly says that
specification-defined absence is not an unsupported declaration. The runner
reused a legacy parser that requires explicit per-satellite phase-shift
coverage, caught every parser exception and reduced all cases to one false
boolean. The receipt therefore cannot distinguish:

- a specification-defined default or absence;
- incomplete declared coverage;
- malformed syntax;
- an actually unsupported transform.

Consequently `TRANSFORM_SEMANTICS_UNRESOLVED_BY_RECEIPT` is the maximum
authorized statement.

## Consequence

The runtime result is preserved, but the following claims are forbidden:

```text
DRAO_IDENTITY_CONTRADICTION
DRAO_TRANSFORM_SEMANTICS_UNSUPPORTED
DRAO_MEASUREMENT_PATH_REJECTED
MEASUREMENT_VALID
ORBITAL_SIGNATURE_DETECTABLE
ORBITAL_MODEL_PREDICTIVELY_PREFERRED
```

The one structural authority is consumed with zero retry. No fallback date,
artifact, endpoint or PRN is selected. The next permissible work is an offline
change-of-abstraction review using only the frozen receipts and independent
documentation; it is not another parser gate or another access to this
artifact.
