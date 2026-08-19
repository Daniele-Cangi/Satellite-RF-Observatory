# Gate F2.5.35 — scalar discovery-audit integration

Gate F2.5.35 is an offline successor. It does not modify the frozen
F2.5.31–34 sources, acquire data, open a Kiwi connection, change a discovery
threshold or grant live authority.

Its sole purpose is to prevent a future `NO_FEATURE_ADMITTED` from compressing
all internal rejection cuts into one uninterpretable bit.

## Frozen lineage

```text
reviewed Gate F2.5.34 commit:
  f8d003c44cf4b9e98cea2ff6fd3c746bbb61b1e4

reviewed Gate F2.5.34 source:
  96ff3d14bce70e6874841d33a0329ba23739277d3289415e9df7d842eccedeb0

reviewed Gate F2.5.32 vertical source:
  d38a3bdf4669ed7b0e27d9cff1399d9fd2744b4bdc909e7e687cb88a2b7daf1b
```

The F2.5.33 receipt remains frozen and attributable. This gate does not claim
to recover any missing statistic from that historical artifact.

## The boundary

The new discovery path derives one immutable decision basis from the same
ephemeral A1 arrays and then materializes two sibling receipts:

```text
same pre-analysis frame hashes
          |
          v
unchanged feature selector
          |
          +--> DiscoveryReceipt          authoritative
          |
          +--> ScalarDiscoveryAuditReceipt descriptive only
```

The `DiscoveryReceipt` retains the exact F2.5.31 schema and remains the only
input to intervention control flow. On both negative and positive synthetic
IQ, its fields and receipt hash are identical to the frozen selector.

The audit is bound to the decision hash and to all 16 A1 frame hashes. Its
constructor refuses a stage count that does not close or conflicts with the
decision state.

## Scalar sufficient statistics

The sibling receipt stores only:

- valid-grid bin count;
- raw peak count;
- patch-incomplete and patch-valid counts;
- correlation-fail and correlation-pass counts;
- half-stability-fail and half-stability-pass counts;
- admitted-feature count;
- best valid joint contrast and its margin from `5.0 dB`;
- best patch-valid correlation and its margin from `0.65`;
- best correlation-passing half-window contrast and its margin from `3.0 dB`;
- explicit `FINITE` or `NOT_EVALUATED` numerical states;
- selector, transform, STFT geometry and threshold provenance;
- `candidate_arrays_persisted=false` and `raw_rf_persistence=ZERO`.

No IQ, STFT matrix, spectrum, waterfall, normalized patch or candidate array
enters the receipt.

The counts obey these invariants:

```text
raw peaks = patch incomplete + patch valid
patch valid = correlation below + correlation pass
correlation pass = half-stability below + half-stability pass
half-stability pass = admitted features
```

These equalities make a negative attributable without turning the audit into
a second selector.

## Description-error semantics

The decision is constructed before the audit. If audit construction fails,
the path returns:

```text
state: DESCRIPTION_ERROR
decision_receipt_hash: preserved
description_error_type: typed
description_error_hash: SHA-256
physical_decision_affected: false
```

The selection decision is neither replaced by `QUALIFICATION_ERROR` nor
recomputed. The integrated vertical follows the same phase and physical
outcome as it would with a complete audit.

## Offline integration evidence

The full injected F2.5.32 lifecycle now has an audited successor:

- a negative zero-feature A1 produces `NO_FALSIFIABLE_INTERVENTION` with a
  complete stage audit;
- forcing the audit builder to fail produces the same decision, same phase
  states, zero retune commands and `NOT_EVALUATED` physical state;
- a positive synthetic upstream case produces the same discovery receipt,
  two command boundaries, clause states and
  `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED` outcome as the frozen evaluator;
- all decoded IQ and derived spectral arrays are destroyed before return;
- the integration exposes no connector, endpoint or live-authority surface.

This proves evaluator equivalence for the deterministic fixtures. It is not a
live physical result.

## Claims

Authorized:

- a future negative can identify the first admission stage at scalar
  resolution;
- the audit is causally downstream of, and non-authoritative over, selection;
- audit failure cannot alter downstream physical control flow;
- the existing frozen thresholds and physical evaluator remain unchanged;
- the receipt retains no RF-derived arrays.

Not authorized:

- any statement about the missing F2.5.33 stage counts;
- any statement about current Kiwi availability or RF conditions;
- a new live execution;
- a lower threshold or adapted feature family;
- a physical upstream/downstream outcome from this offline gate.

## Next admissible step

Gate F2.5.35 must first be committed. A separate offline Gate F2.5.36 may then
seal that exact commit, source, selector-equivalence surface, numerical
environment, receipt shape, zero-retry rule and one-outcome runner. The seal
must default-refuse execution.

Only after review of that post-commit seal may a new, single-use authority be
considered. Gate F2.5.35 itself stops before both network and authority.
