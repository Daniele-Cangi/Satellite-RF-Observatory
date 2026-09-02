# DORIS exact-coepoch development requalification

## Outcome

```text
DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED
```

The exact PAUB–RIMC development pair contains a contiguous dual-phase chain
that exceeds the frozen 480 s requirement using identical receiver epoch tags,
not temporal overlap or nearest-neighbor matching.

This is a structural topology result. Measurement admission, event-time
admission, orbital prediction and null scoring remain `NOT_EVALUATED`.

## Frozen execution

The scanner and plan were committed as
`7d954f576f000bd84d5a6b3bdc23f744bba7cb4c` before access. The source and plan
SHA-256 values are bound in the receipt.

One copy of the exact development artifact was materialized:

- `s3arx26242.001.Z`;
- `1,869,420` compressed bytes;
- SHA-256
  `240d84518beb409dceb5cf1816f02621e9def8c9bf750c9c340cad4f6fbd7add`.

The complete compressed hash was verified before decompression. The streaming
scan then reproduced the previously frozen uncompressed identity:

- `7,564,590` bytes;
- `94,830` lines;
- SHA-256
  `9edb37c8a354602c20985a07edb87c594bcd9678d496e6e70ee0b4ee4f20db64`;
- `16,704` epoch records;
- `39,024` station records.

There was one materialization, one scanner invocation and zero retry. The
compressed quarantine artifact was destroyed after the scalar receipt was
formed. No uncompressed artifact was created.

## Exact-coepoch result

Across the complete stream:

- PAUB/D46 and RIMC/D40 occur under the identical DOR epoch 196 times;
- 186 of those pairs have both L1/L2 fields present and zero discontinuity;
- five coepoch pairs carry a left-side phase discontinuity;
- five carry a right-side phase discontinuity;
- the longest valid exact-coepoch segment contains 128 paired epochs;
- it runs from `2026-08-30T19:12:45.229949+00:00` through
  `2026-08-30T19:23:18.229949+00:00`;
- its first-to-last duration is exactly `633.0 s`;
- a second valid segment contains 58 paired epochs over `283.0 s`.

The admitted sample semantic is:

```text
IDENTICAL_DOR_EPOCH_TAG_NO_INTERPOLATION_MAX_10_SECOND_GAP
```

The earlier 633 s intersection was therefore not an accidental overlap of two
offset grids: for PAUB–RIMC it corresponds to a real simultaneous receiver
chain. The old receipt was still correct to refuse that stronger claim because
its algorithm had not tested exact epoch identity.

## What this closes

Together with the preceding outcome-independent algebra, this result closes
one specific causal cut:

```text
synchronous L1/L2 per beacon
        ↓ ionosphere-free phase
same receiver epoch for PAUB and RIMC
        ↓ left-minus-right difference
shared receiver clock and receiver proper time cancel symbolically
```

Per-target C1/C2 time-reference-valid flags are not required for that exact
common-receiver cancellation. This does not make C1/C2 unimportant in a
complete DORIS clock solution and does not establish absolute event time.

## What remains open

The quotient still cannot be compared with an orbital prediction until the
following are bounded with outcome-independent models or calibration:

- absolute DOR-to-coordinate-time error over the chosen interval;
- higher-order ionosphere;
- differential troposphere;
- beacon coordinates, phase centers and antenna maps;
- phase wind-up;
- Shapiro and one-way relativistic terms;
- non-affine differential ground-oscillator behavior;
- channel-switch or receiver-noncommon bias.

The phase magnitudes needed to form the quotient were never decoded. Hence the
result is not `MEASUREMENT_VALID`, not an orbital detection and not support for
Sentinel-3A identity.

## Scope and cleanup

- numerical L1/L2/C1/C2 values decoded: zero;
- numerical observation values persisted: zero;
- C1/C2 values or flags evaluated: zero;
- candidate DOY245 access: zero;
- orbital prediction and score: zero;
- compressed and uncompressed artifact retention: zero.

## Scientific consequence

The DORIS route survives. Its useful independence is not two receiver hardware
roots but two independently located beacon-to-spacecraft propagation paths
sampled by one simultaneous receiver. Shared receiver hardware is a benefit at
this causal boundary because exact simultaneity turns its clock and proper-time
terms into common mode.

The next smallest physical step is an offline envelope audit for the remaining
terms and the absolute event-time bridge on this already proven 633 s topology.
Observation magnitudes and candidate-day access remain unauthorized until that
envelope leaves a positive orbital-versus-null margin.

