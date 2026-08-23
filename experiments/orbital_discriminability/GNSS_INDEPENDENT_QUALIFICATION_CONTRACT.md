# Draft contract — independent GNSS qualification then distinct primary

Status: `DRAFT_NOT_EXECUTED`. This is not a new gate, a target selection or
authority to access another observation product.

## Role separation

1. One independently chosen qualification artifact is frozen by product ID,
   station, recording interval, byte count and SHA-256. It is used only to
   qualify the exact parser, header coverage and value-blind record topology.
2. A later primary must be a distinct immutable artifact with a different
   SHA-256 and recording interval. It remains unopened until orbit, stations,
   satellites, window, nulls, missing-data rules and detector/transform
   manifests are frozen.
3. The qualification artifact can never become the primary. The primary can
   never be used to repair qualification rules.

## Qualification clauses

- Exact artifact identity is verified before decompression.
- `TIME OF FIRST OBS` and `TIME OF LAST OBS` are present, declare GPS time and
  cover the complete proposed raw window.
- The common GPS family contains core `L1C` and `L2W`, same-path `C1C` and
  `C2W`, LLI positions attached to both phase fields, and ordered epochs.
- `S1C` and `S2W` are optional diagnostics and cannot block the coordinate.
- Every required link record is attributed as `FIELD_PRESENT`, `FIELD_BLANK`,
  `TRAILING_FIELD_OMITTED`, `FIELD_ABSENT`, continuation state or
  `RECORD_INVALID`, using only the frozen structural receipt fields.
- Any structural refusal terminates qualification. A receipt-generation
  failure is `DESCRIPTION_ERROR` and leaves qualification `NOT_EVALUATED`.
- No orbital score and no observation value are retained during structural
  qualification.

## Later primary clauses

Only after an independent artifact satisfies every qualification clause may a
separate prospective plan name a primary. That plan must retain the project’s
existing orbit-first geometry, calibration-prefix, held-out suffix and frozen
null discipline. No replacement primary, field substitution or threshold
change is permitted after opening it.

Permitted pre-primary terminal outcomes are:

```text
INDEPENDENT_STRUCTURE_QUALIFIED
NO_INDEPENDENT_STRUCTURE_QUALIFICATION
QUALIFICATION_DESCRIPTION_ERROR
```

No contract outcome implies selection of a station, satellite, pass or
primary product.
