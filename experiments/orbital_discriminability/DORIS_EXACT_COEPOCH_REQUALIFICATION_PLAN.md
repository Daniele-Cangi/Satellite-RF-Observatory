# DORIS exact-coepoch development requalification

This is a bounded continuation of the DORIS observable-role audit, not a new
gate and not an orbital experiment.

## Physical question

Does the already selected development pair PAUB–RIMC contain a contiguous
480-second chain in which both L1/L2 phase observations carry one identical
DOR receiver epoch and satisfy the frozen phase-continuity rules?

## New information produced

A positive result would establish the receiver-side topology needed for the
exact-coepoch inter-beacon quotient. A negative result would close the
dual-phase-only route for this development artifact. Neither result admits a
measurement or evaluates an orbit.

## Frozen authority

- product: `s3arx26242.001.Z`;
- compressed byte count: `1,869,420`;
- compressed SHA-256:
  `240d84518beb409dceb5cf1816f02621e9def8c9bf750c9c340cad4f6fbd7add`;
- expected decompressed byte count: `7,564,590`;
- expected decompressed SHA-256:
  `9edb37c8a354602c20985a07edb87c594bcd9678d496e6e70ee0b4ee4f20db64`;
- expected frozen header SHA-256:
  `47311d675dc0130a42676e423827bd63a4ac3b9083664c52741f5f75d185012a`;
- role: `DEVELOPMENT_EXACT_COEPOCH_REQUALIFICATION_ONLY_NEVER_PRIMARY`.

Candidate DOY245 remains forbidden.

## Frozen structural transform

The complete compressed file must be materialized and its identity verified
before decompression. The streaming parser may represent only:

- exact DOR epoch tag;
- epoch flag and declared record count;
- three-character station identity;
- L1/L2 blank/nonblank state;
- L1/L2 flag 1 and flag 2.

The parser consumes the rest of each station record only to maintain the
RINEX boundary. It never converts, returns or persists any observation
magnitude and does not evaluate C1/C2 values or flags.

An exact-coepoch sample exists only when D46 and D40 occur under the identical
epoch record. Both stations must have L1 and L2 present, phase flag 1 in
`blank/0/1`, and phase flag 2 in `blank/0`. No interpolation or nearest-neighbor
matching is allowed. Consecutive exact-coepoch samples may be at most 10 s
apart. A nonpositive or larger gap, a phase discontinuity, a power-failure
boundary or a special event cuts the chain.

The minimum duration is frozen at 480 s from first to last exact-coepoch tag.
It is not reduced after inspection.

## Frozen outcomes

```text
DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED
DORIS_EXACT_COEPOCH_TOPOLOGY_INSUFFICIENT
```

An identity, header, stream, count, decompressor or structural violation stops
with its exact typed exception and cannot be reinterpreted as either physical
outcome.

`QUALIFIED` authorizes only the statement that the shared receiver
clock/proper-time cancellation topology is structurally available. It does
not authorize `MEASUREMENT_VALID`, orbital prediction, null comparison or a
candidate-day download.

## Execution and cleanup

One materialization attempt is permitted. There is no alternate product,
station pair, duration, gap threshold or retry chosen after inspection. The
receipt must bind the source commit, source SHA-256 and this plan's SHA-256.
The compressed quarantine artifact must be destroyed after the scalar receipt
is produced; no uncompressed file may be created.

## Stop condition

Stop immediately after one outcome and cleanup. If qualified, the next work is
an offline envelope for the still-open event-time, propagation, antenna,
relativistic, oscillator and receiver-noncommon terms—not observation-value
access.

