# Gate F2.5.33 — post-commit authority seal

Gate F2.5.33 seals the reviewed F2.5.32 commit and exposes one
default-refusing authority boundary. The assessment and tests are exclusively
offline. No connection, acquisition or physical outcome was produced.

The terminal assessment state is:

`EXACT_RF_RESPONSE_READY_FOR_SEPARATE_AUTHORITY`

This state means that a later caller may explicitly authorize exactly one
execution of the reviewed vertical. It does not itself grant or consume that
authority.

## Bound lineage

The authority envelope binds:

- F2.5.32 commit `eae4d753b3c5f8d9ffd8247fc3758afb9c1ff15d`;
- the canonical F2.5.32 source hash;
- the immutable F2.5.32 plan hash;
- the exact private open-handle integration-surface hash;
- the complete F2.5.33 live-surface source hash;
- Python, NumPy, SciPy and websocket-client versions;
- the one endpoint already present in the reviewed lineage;
- the same-Kiwi, distinct reference/perturbed DDC topology;
- unchanged thresholds, zero retry, one outcome and zero RF persistence.

The assessment also requires the reviewed commit to remain an ancestor, the
F2.5.32 source to have no Git diff from that commit and the repository root to
be the current working directory. Any mismatch fails closed.

## Public authority boundary

The only public live-capable signature is:

```python
run_reviewed_once(*, live_authorised: bool = False)
```

With the default value, the function raises before:

- post-commit assessment;
- receipt creation;
- endpoint lookup;
- WebSocket connector access;
- acquisition or RF transformation.

The caller cannot override endpoint, frequency, delta, timing, thresholds,
feature, connector, receipt path, retries or phase order. Passing `True` is
still insufficient if any seal clause fails.

## Frozen execution order

After a separate explicit authority, and only then, the sealed path is:

```text
explicit authority
        ↓
post-commit seal assessment
        ↓
authority envelope written as first receipt
        ↓
two simultaneous SND connections to the frozen endpoint
        ↓
websocket frame ownership transferred into ephemeral leases
        ↓
exact F2.5.32 open-handle A1 → B → A2 vertical
        ↓
one terminal outcome
        ↓
terminal receipt + socket/RF cleanup
```

There is no retry after any failure and no second window after an outcome.

## Live frame ownership

The small adapter does not interpret Kiwi frames. It only:

- records monotonic arrival at the receive boundary;
- moves the payload into the reviewed per-frame lease;
- clears a mutable websocket-owned source buffer after copying;
- delegates release-before-analysis and later IQ zeroization to the sealed
  F2.5.31/F2.5.32 path;
- closes idempotently.

If one of the two connector attempts fails, any successfully opened peer is
closed and the receipt is terminalized. No single branch can continue as a
substitute experiment.

## Receipt boundary

The authority envelope is necessarily the first JSON Lines event. One
F2.5.32 result is the only outcome event and the existing terminal manifest is
last. Descriptive serialization or retention errors remain separate from the
physical result. No samples, IQ, STFT, spectrum or waterfall enter the receipt.

## Authorized claims

This gate authorizes only that:

- the reviewed F2.5.32 vertical is exact and unchanged;
- its live-facing call surface has one default-false authority bit;
- connector and frame ownership can feed the exact private F2.5.32 seam;
- every mismatch or partial connection fails closed;
- a later single run can be separately authorized.

It does not authorize claims that the endpoint is currently reachable, two
slots are currently available, a retune will qualify, a feature will be
detectable, or either physical hypothesis is true.

## Next boundary

The next admissible action is not more code. It is either:

1. retain the sealed runner without executing it; or
2. receive a new explicit authorization for one live Gate F2.5.33 execution.

That execution must stop after its first terminal outcome. A failed capability,
intervention or detectability clause cannot be retried or repaired by changing
the plan.
