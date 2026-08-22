# GNSS double-difference measurement postmortem

## Scope and immutable parent result

This is an offline static attribution of the frozen one-shot outcome. It does
not create a new gate, reopen either CRINEX artifact, decode another
observation value, change the prospective plan, modify the sealed decoder, or
authorize a retry.

The authoritative parent result remains:

```text
MEASUREMENT_INVALID
TRUNCATED_REQUIRED_OBSERVATION_RECORD
```

Parent bindings:

- prospective-plan SHA-256:
  `e3eaa0d1974ce4b415182aaa47451174aaa9296b61e31c296f2cda1e8eda86f4`;
- decoder-manifest SHA-256:
  `b77e74de3f713574ac26e5a3016be22577090955bdd794d98528e1b24cb7b56b`;
- terminal-outcome SHA-256:
  `4060e8e3046696f6433ce5226e3d7f524d430cbbd49261fd1041554ab76b5172`.

## What the error proves

The sealed decoder can emit this exact reason only after all of the following
have succeeded:

1. the exact compressed artifact passed filename, byte-count and SHA-256
   validation;
2. Hatanaka decompression returned a RINEX document;
3. the decompressed header declared the frozen GPS signal family;
4. an epoch record was parsed;
5. a satellite record was framed and associated with a declared system;
6. that satellite was G11 or G21 inside the frozen raw epoch window;
7. the header-derived index of one required observable was greater than or
   equal to the number of 16-byte observation fields reconstructed for that
   satellite record.

The six required observables were `C1C`, `L1C`, `S1C`, `C2W`, `L2W` and
`S2W`. The failure happened before the selected field could be parsed as a
number or inspected for LLI.

Therefore the error is not evidence of:

- a failed artifact hash;
- Hatanaka decode failure;
- a malformed epoch line;
- a missing epoch;
- a non-finite value in an existing field;
- a non-zero LLI;
- a geometry-free phase discontinuity;
- excessive calibration residual;
- held-out disagreement with G11;
- preference for the affine or G12 null.

## What the receipt cannot determine

The terminal receipt records only the typed reason. It does not record the
station, GPS epoch, satellite, observable name, header-declared observable
index, parsed field count, source-line count or continuation form at the
failure boundary.

Consequently it cannot distinguish among these explanations:

1. the required observable was absent and trailing blank fields were omitted
   from the delivered record;
2. the record was structurally shorter than its header-declared observable
   list for another product reason;
3. a decoder-native but otherwise valid record continuation was not
   represented by the sealed parser;
4. another formatting condition produced the same short-field boundary.

No one explanation is promoted without evidence. In particular,
`TRUNCATED_REQUIRED_OBSERVATION_RECORD` is not sufficient evidence of file
corruption, receiver failure, loss of lock, or a parser defect.

## Synthetic control

Without accessing either real artifact, the exact frozen Hatanaka 2.8.1 codec
was exercised in RAM on the existing synthetic RINEX fixture:

```text
synthetic RINEX
-> hatanaka.compress(compression="none")
-> hatanaka.decompress(strict=True)
-> sealed parse_plain_rinex_window
```

The round trip produced a `(5, 2, 6)` observation array, preserved the expected
scalar and returned zero LLI. This demonstrates that the parser accepts the
codec's tested native long-record representation. It does not prove that the
unretained failing real record used the same representation.

The existing tests also distinguish an existing-but-blank required field as
`MISSING_OR_NONFINITE_REQUIRED_OBSERVATION`; the real outcome instead reached
the earlier short-field condition.

## Failure attribution

| Layer | Classification | Attribution |
|---|---|---|
| orbital model | `NOT_EVALUATED` | No prediction score was reached. |
| model to prediction | `NOT_IMPLICATED_BY_RECEIPT` | Frozen G11/G21 and G12 curves were not compared with observations. |
| observational capability | `UNRESOLVED` | The complete six-observable topology was not admitted for every required record, but the missing context prevents a narrower cause. |
| receiver transform / Hatanaka | `PARTIALLY_WITNESSED` | Exact artifact and Hatanaka admission passed; the record-layout boundary remains unresolved. |
| feature extraction | `NOT_ENTERED` | No double-difference feature array or calibration statistic was produced. |
| physical orbital hypothesis | `NOT_TESTED` | Neither G11 nor either frozen null was supported or damaged. |

Epistemic classification:

```text
NOT_FALSIFIABLE_WITH_THIS_RECEIPT
```

The negative result is usable only as a refusal of this exact frozen
measurement path. It is not an orbital negative and does not establish that
the general GNSS double-difference mechanism is unsuitable.

## Minimum conceptual change for a future experiment

Do not repair and rerun this primary. A future GNSS experiment needs one
independent, pre-primary capability qualification that proves the exact
decoder-native record topology and continuous availability of the intended
signal family before a separate held-out artifact is assigned the primary
role.

The minimum diagnostic receipt at that boundary must retain only structural
context, never observation values:

```text
station
GPS epoch
satellite
required observable
header-declared index
parsed field count
record/continuation encoding class
typed structural state
```

This would distinguish `FIELD_ABSENT` from `RECORD_ENCODING_UNSUPPORTED` and
`DESCRIPTION_ERROR`. It would not relax missing-data rules or authorize
post-outcome signal substitution.

The qualification artifact and future primary must be independent. Inspecting
the same primary and then redesigning its required signal family would be
post-hoc adaptation, not a repair.

## Closure

The frozen GOLD/NLIB G11/G21 run remains closed with no retry. The large
premeasurement orbital discriminability margin remains a geometry result, not
measurement evidence. The shortest scientifically valid continuation is a new
prospective vertical only if an independent qualification artifact can prove
the required GNSS field topology; otherwise this route should be abandoned
rather than surrounded by more parser infrastructure.
