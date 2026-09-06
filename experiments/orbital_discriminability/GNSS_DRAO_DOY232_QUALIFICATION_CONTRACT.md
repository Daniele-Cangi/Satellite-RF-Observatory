# DRAO DOY232 qualification contract

**DRAO_DOY232_QUALIFICATION_CONTRACT_FROZEN**

This is the reviewed boundary between the admitted DRAO model-side envelope
and any observation artifact. It is not a new gate, does not select a product
and authorizes no DRAO locator, header or payload access.

```text
Physical question:
Can one distinct DRAO DOY232 artifact preserve the six-track phase coordinate
and close the predeclared capability reserve without receiving an orbital
model?

New information if later executed:
Whether this measurement path can make a negative DOY233 orbital result
interpretable.

Why the model-side result cannot answer it:
It proves positive geometric margin, but signal identity, receiver/header
agreement, record continuity and the all-epoch phase-code witness remain
capability-dependent.

Minimum experiment:
One model-blind qualification of one exact DOY232 DRAO artifact on the already
frozen 139-epoch window and six-satellite codebook.

Stop condition:
Stop before locator selection. After a later qualification, stop with DOY233
still unselected regardless of pass or failure.
```

## Frozen roles

- DOY230/DOY231 remain closed and are never reopened.
- DOY232, `2026-08-20 01:19:00--02:28:00 GPS`, is qualification-only and
  never scored.
- DOY233 remains a possible later primary, unselected, unfrozen and
  unauthorized.
- Observer: `DRAO00CAN` / DOMES `40105M002`.
- Codebook: `G07/G08/G09/G21/G27/G30`.
- Grid: 139 epochs at 30 seconds; 79 prefix and 60 held-out epochs.

No fallback station, date, signal family or shorter segment is permitted.

## Header and transform admission

The future artifact must be RINEX 3 with explicit GPS observation identities.
Its marker, receiver and antenna must agree with the independently frozen DRAO
metadata: SEPT POLARX5 5.2.0 and TWIVC6050/SCIS. `TIME OF FIRST OBS`,
`TIME OF LAST OBS`, `INTERVAL` and the GPS time system must cover the complete
window. Unknown or conflicting identity is a topology rejection, not a
descriptive error.

The decoder must apply RINEX `SYS / SCALE FACTOR`, `SYS / PHASE SHIFT` and
`RCV CLOCK OFFS APPL` semantics explicitly. Absence of `SYS / SCALE FACTOR`
means only the unity behavior defined by the specification; an unsupported
declared phase shift or clock-offset state is not silently ignored. TGD is not
applied to carrier phase.

The measurement coordinates are frozen as:

```text
IF_PHASE_s = a * lambda_L1 * L1C_s + b * lambda_L2 * L2W_s
IF_CODE_s  = a * C1C_s             + b * C2W_s
W_s        = IF_PHASE_s - IF_CODE_s

a = 2.5457277801631601
b = -1.5457277801631601
```

Phase is decoded in cycles and converted to metres; code is decoded in
metres. S1C/S2W are optional diagnostics and cannot admit or reject the path.

## Clause-level qualification

All clauses are independently evaluated. A receipt failure leaves downstream
clauses `NOT_EVALUATED`; it cannot become a physical rejection.

1. One exact compressed artifact is bound by byte count and SHA-256 before
   decoding. The decoded artifact also receives a hash.
2. Every expected epoch and satellite record exists on the exact grid.
3. L1C and L2W are present at every one of the 139 epochs for every satellite.
   Missing, blank, omitted or invalid phase and every nonzero LLI break the
   track. There is no interpolation or gap bridging.
4. C1C and C2W are present at every epoch for every satellite. Coverage is
   exactly 100%; six tolerated missing epochs from the earlier 95% rule are no
   longer possible.
5. The geometry-free phase coordinate has no absolute second difference above
   `0.09514683639918244 m`. A violation rejects the qualification; it cannot
   select another segment.
6. The phase-code witness is common-mode centered with
   `C = I - (1/6)11T`. A constant plus rate is fitted independently per track
   on the first 79 epochs, with no held-out refit. Each held-out witness must
   remain at or below `1,250 m` peak-to-peak. The proven common-mode gain bound
   of two then closes, rather than assumes, the frozen `2,500 m` reserve.

Observation scalars and derived series may exist only ephemerally in RAM in a
separately authorized execution. The structural receipt contains states and
counts plus only the two predeclared continuity/witness summaries. It never
contains an observation value or orbital score.

## Outcome semantics

```text
NO_QUALIFICATION_ARTIFACT_AVAILABLE
QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED
QUALIFICATION_DESCRIPTION_ERROR
QUALIFICATION_TOPOLOGY_REJECTED
QUALIFICATION_PHYSICAL_WITNESS_REJECTED
DRAO_QUALIFICATION_PASSED_PRIMARY_STILL_SEALED
```

Passing means that every capability clause needed by the unchanged
`3,387.960685290 m` conditional envelope is testable and satisfied on DOY232.
It does not select, open or authorize DOY233. Failing closes this staged DRAO
route; it does not choose a replacement artifact.

The strict executable manifest hash is
`667be5b59b9da90c11710c9c6ae4c3d6ff24b06d73ac0337136b4371e8051e72`.

## Current boundary

At this freeze, qualification and primary locator, header, payload and value
access are all zero. The next maximum action, after review, is selection of at
most one exact DOY232 artifact. DOY233 must remain completely untouched.
