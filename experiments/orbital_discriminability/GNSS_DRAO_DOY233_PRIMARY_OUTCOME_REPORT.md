# DRAO DOY233 integrated primary outcome

**MEASUREMENT_INVALID**

The single authority bound to runner seal
`eca7b78efb2420c2b714e4cd878e7d825196b314a74d4d9db336bb0fff50303a`
was consumed after merge commit
`71af3f40bc6558bb26bdeb0c1f336b13ea336eae`. The exact frozen artifact was
materialized once, completely hashed before decompression, inspected only in
memory and then erased.

The artifact identity and transport clauses passed:

```text
artifact: DRAO00CAN_R_20262330000_01D_30S_MO.crx.gz
complete bytes: 2886587
complete SHA-256: 6c25fc9934bf90a861bf9637398a6ab436a820d7c47e2cb611e85ce00d09d903
materialization attempts: 1
frozen HTTP identity matched: true
```

The structural admission then stopped on the frozen cardinality clause:

```text
required complete opaque tracks: 7
observed complete opaque tracks: 8
reason: COMPLETE_OPAQUE_TRACK_COUNT_NOT_SEVEN:8
```

No track was selected, excluded or revealed after this mismatch. Geometry-free
continuity, the seven all-exclusion same-path witnesses and the opaque
10,087-hypothesis score were not evaluated.

## Claim boundary

This receipt authorizes only these statements:

- the exact selected compressed product was completely materialized and hashed;
- the frozen parser reached the complete-track cardinality check;
- eight tracks satisfied the parser's frozen definition of complete structural
  availability, not the exactly seven required by the prospective contract;
- measurement admission failed before any orbital score.

It does not authorize an orbital negative, a null preference, satellite
identity, an explanation for the eighth track, or a post-hoc choice of seven
tracks. In particular, `8` is a structural count and is not evidence that one
track is physical clutter.

## Irreversibility and persistence

The one-shot authority is consumed. This product will not be retried, rescored
or repaired by changing the cardinality rule. The persisted evidence consists
only of the authority, complete-artifact hash and terminal outcome receipts:

```text
authority receipt SHA-256:       49b876855e582fdc6963d8b327ba337dcc37b2ca3c53ce4bb0c07480d175f9b0
materialization receipt SHA-256: 50e357d1049197a52f057d7fe8c93fb614ea4cc7446054ddd366833c1ec79e06
outcome receipt SHA-256:         9ef6c615944ac6a91fc8a095592be9cc735af39c126b7b23142181744025caed
```

Compressed bytes, decoded RINEX, observation values and derived series were
not persisted. `orbital_score` and every downstream clause remain
`NOT_EVALUATED`.

The next scientific action, if any, requires a change-of-abstraction review.
It must ask whether fixed track cardinality is physically necessary or merely
an inherited convenience. It is not another execution of DOY233 and does not
authorize another artifact.
