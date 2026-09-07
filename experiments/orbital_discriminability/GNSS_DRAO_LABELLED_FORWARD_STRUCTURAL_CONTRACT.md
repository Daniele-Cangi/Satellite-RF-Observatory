# DRAO labelled-forward structural contract

Status: `DRAO_LABELLED_FORWARD_STRUCTURAL_CONTRACT_FROZEN_UNOPENED`.

This is a bounded capability-admission contract inside the existing DRAO
labelled-forward vertical. It is not a new gate, does not identify or select an
observation product, grants no network or payload authority and cannot produce
an orbital score.

## Information-gain boundary

```text
Physical question:
Can one DRAO DOY237 RINEX observation preserve the six predeclared labelled
phase paths over the complete frozen window, so that the already admitted
orbital-versus-null margin can later be tested?

New information if executed:
Whether the real measurement path has the exact field, time and continuity
topology required by the fixed six-track coordinate.

Why the existing audit cannot answer it:
The orbit-only envelope proves detectability margin but contains no receiver
header, epoch records, observation identities or loss-of-lock indicators.

Minimum experiment:
One complete value-blind structural scan of one later selected DRAO DOY237
30-second mixed-observation product. No fallback product and no score.

Stop condition:
One structural outcome, all downstream physical clauses NOT_EVALUATED, and no
observation values retained or exposed.
```

## Frozen geometry and role

- station: `DRAO00CAN`, DOMES `40105M002`;
- GPS window: `2026-08-25 04:55:00--06:04:00`;
- cadence: 30 seconds;
- raw epochs: 139;
- future prefix: indices 0--78;
- future held-out suffix: indices 79--138;
- required labelled tracks: `G14/G15/G17/G20/G24/G30`;
- extra tracks: descriptive, never fatal and never eligible for substitution;
- artifact identity and locator: unselected;
- product role: structural admission first, possible primary only after a
  separately frozen integrated prediction/executor.

The same artifact may not be replaced because a required PRN is absent or a
clause fails. Structural readiness does not itself make the artifact a primary.

## Header and container admission

The later artifact must be one complete DRAO DOY237 daily 30-second mixed GPS
observation product in RINEX 3 form. Gzip and Hatanaka compression are allowed,
but the complete transport byte count and SHA-256 must be committed before
decompression, and the complete decompressed RINEX must receive its own hash
before record traversal.

The header must establish:

- marker/site identity compatible with DRAO00CAN and DOMES 40105M002;
- receiver `SEPT POLARX5`, version `5.2.0`;
- antenna `TWIVC6050`, radome `SCIS`;
- GPS time system;
- `TIME OF FIRST OBS` no later than the first frozen epoch;
- `TIME OF LAST OBS` no earlier than the last frozen epoch;
- `INTERVAL = 30 s`;
- GPS declarations for L1C, L2W, C1C and C2W;
- explicit handling of `SYS / SCALE FACTOR`, `SYS / PHASE SHIFT` and
  `RCV CLOCK OFFS APPL`.

Spec-defined absence is not the same as an unsupported declaration. A parser
or description failure leaves physical and structural clauses unevaluated; it
does not become a measurement rejection.

## Complete structural scan

The scanner must traverse the whole intended window and emit one structural
state for every required station/epoch/PRN/field tuple. It must not stop at the
first missing field. Allowed states are:

```text
PRESENT
BLANK
TRAILING_FIELD_OMITTED
CONTINUATION_SUPPORTED
CONTINUATION_UNSUPPORTED
RECORD_INVALID
```

Admission requires, for every one of the 139 epochs and every fixed PRN:

- L1C and L2W present;
- C1C and C2W present;
- LLI blank or zero on each present phase field;
- normal epoch flag and exact frozen event-time grid;
- supported record continuation and field indexing.

Missing, blank, omitted or invalid core/code fields, nonzero/invalid LLI,
unsupported continuation, duplicate required records, an off-grid epoch or an
abnormal epoch flag rejects the structure. There is no interpolation, gap
bridging, window shortening, PRN substitution or segment reselection.

## Physical-role separation

| Role | Fields/state | Structural scan may conclude |
|---|---|---|
| core phase coordinate | L1C, L2W | presence and LLI topology only |
| cycle-slip/continuity witness | LLI plus exact epoch grid | declared loss/structural break only |
| same-path code witness | C1C, C2W | complete presence only |
| optional diagnostic | S1C, S2W | nothing; never fatal |

The structural scanner must not parse or expose numeric observation values.
Consequently it cannot evaluate:

- geometry-free phase second differences;
- phase-minus-code peak-to-peak;
- multipath, signal-specific hardware or receiver implementation;
- orbital, affine or time-reversed residuals.

Those clauses remain `NOT_EVALUATED`, not satisfied. Their frozen numerical
limits remain respectively `0.09514683639918244 m` and `1250 m` per track and
may only be applied later without modification in a single integrated proof.

## Receipt and persistence

The retained structural receipt may contain only identity hashes, header
states, counts, field-state coverage, LLI-state counts, epoch-grid coverage,
first/last contiguous indices and typed refusal reasons. It contains no phase,
code, signal-strength or derived scalar and no orbital prediction.

Compressed and decompressed payloads are temporary and must be destroyed after
the structural outcome. Persisted observation values and derived series are
exactly zero.

Transport may retry only before a complete-file hash for timeout or interrupted
transfer. After complete hashing or any decompression: zero retry, zero fallback
date, zero fallback endpoint and zero replacement artifact.

## Future structural outcomes

```text
NO_DRAO_DOY237_ARTIFACT_SELECTED
DRAO_STRUCTURE_ARTIFACT_MATERIALIZATION_FAILED
DRAO_STRUCTURE_DESCRIPTION_ERROR
DRAO_STRUCTURE_TOPOLOGY_REJECTED
DRAO_LABELLED_FORWARD_STRUCTURE_READY_FOR_INTEGRATED_PROOF
```

`STRUCTURE_READY` means only that one fixed artifact has the required complete
topology. It does not mean measurement valid, detectable, orbitally preferred
or selected as a primary.

## Stop

At this freeze point all observation access counters are zero. Stop before any
product lookup. After review, the maximum next action is metadata-only selection
of at most one exact DRAO DOY237 artifact; body access requires separate
authorization.
