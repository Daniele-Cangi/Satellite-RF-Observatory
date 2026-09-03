# GNSS all-track qualification — description boundary

## Terminal result

```text
QUALIFICATION_DESCRIPTION_ERROR
ANTENNA_TYPE_CHANGED
```

This is not a structural failure, a measurement refusal or an orbital result.
The frozen ALGO DOY229 product reached complete in-memory materialization and
full-file hashing, but header admission stopped before observation-record
traversal.  No primary or reserve has been selected.

## Materialization receipt

| Field | Result |
|---|---|
| product | `ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz` |
| complete bytes | `4,317,738` |
| SHA-256 | `88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24` |
| attempts | `1` |
| hash before decompression | `true` |
| observation values parsed | `0` |
| observation values persisted | `0` |
| compressed/decompressed artifact bytes persisted | `0` |

The server content length, ETag and Last-Modified matched the earlier
descriptive hints.  They remain descriptive metadata; the full-file SHA-256
above is the artifact identity established by this execution.

## Failure attribution

The frozen scanner used the repository's generic `split_twenty` representation
for both `REC # / TYPE / VERS` and `ANT # / TYPE`.  That representation is
appropriate for the receiver record (`3A20`) but not for the antenna record.
RINEX 3.04 Table A2 defines `ANT # / TYPE` as `2A20`: antenna number followed
by one 20-character antenna-type field.  IGS antenna conventions place the
model and radome designation inside that type field.  The scanner instead
compared the model and radome as if they occupied separate second and third
20-character fields.

This establishes a parser/description incompatibility independent of any
observation value.  The failed receipt did not retain the exact encountered
antenna text, so it does **not** authorize the stronger claim that the artifact
hardware differed from station history.  The only authorized attribution is:

```text
header description reached
→ antenna representation rejected by a 3A20-shaped comparison
→ record traversal NOT_EVALUATED
→ exact-six-track topology NOT_EVALUATED
```

Specification source:
<https://files.igs.org/pub/data/format/rinex304.pdf>, Appendix Table A2.

## Anti-drift review

**BLOCK**

The scanner could not compare a standards-conformant `ANT # / TYPE` record to
the frozen `AOAD/M_T / NONE` station description.

**INFORMATION VALUE**

The execution established immutable identity for the selected product and
showed that the current description boundary cannot reach the physical
six-track question.  It learned nothing about whether the six-track topology
exists.

**CURRENT ABSTRACTION**

Hardware continuity remains a useful same-instrument witness, but a third
20-character radome field is not physically necessary and is not present in
the RINEX antenna grammar.  Repairing that interpretation is ordinary parser
maintenance, not a new scientific gate.

**ALTERNATIVES**

1. Repair the antenna parser offline to split the second 20-character field
   into IGS antenna model plus radome, add specification-derived regressions,
   and seek new explicit authority before any second product access.
2. Abandon ALGO DOY229. This avoids a retry but discards a geometry-qualified
   route for a purely descriptive software defect.
3. Remove equipment continuity from admission. This would be faster but would
   weaken the causal link to the frozen observer hardware and is not justified.

**BEST PHYSICAL PATH**

Alternative 1 is the smallest path back to the orbital experiment.  It changes
no geometry, codebook, window, field role or six-track rule.

**STOP**

Do not reopen the artifact in this branch.  First review and freeze the bounded
`2A20` parser repair.  Any repeat materialization requires separate authority;
the present terminal receipt remains immutable.

## Offline parser repair

The bounded repair is now implemented without product access. The shared
header module exposes a dedicated `parse_antenna_two_a20` function while its
legacy receiver-shaped representation remains available to historical
receipts. The ALGO scanner now obtains antenna number and type from exactly two
A20 fields and partitions the IGS type field as A16 model plus A4 radome.

Specification-derived fixtures cover `LEIAR25.R4 / NONE`, the frozen
`AOAD/M_T / NONE` description, refusal of a synthetic third A20 field and an
error receipt that retains both observed and expected normalized model names.
The physical window, observable roles, LLI rule, six-track count and opaque
selection remain unchanged.

The original outcome file is still the execution guard. Calling the repaired
runner against this directory stops at
`QUALIFICATION_EXECUTION_ALREADY_RECORDED` before network access. A future
review must explicitly define a distinct, non-overwriting retry receipt and
authorize one new materialization before the repaired path can be executed.

