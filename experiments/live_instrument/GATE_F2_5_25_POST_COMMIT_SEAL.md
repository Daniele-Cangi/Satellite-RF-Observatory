# Gate F2.5.25 — post-commit seal for one-target confirmation

Gate F2.5.25 binds the reviewed F2.5.24 evaluator to one exact prospective
execution surface. Assessment and tests are offline. No Kiwi connection,
acquisition or authority consumption occurred while creating this seal.

## Reviewed boundary

The seal binds:

- F2.5.24 commit `f08c4f2f8178a497c024dcc9f0cf64886e09d8ab`;
- the F2.5.24 clause order, five allowed outcomes and immutable threshold rule;
- every causal source by canonical-LF SHA-256;
- Python, NumPy, SciPy and websocket-client versions;
- the complete authority-facing source surface;
- the previously demonstrated endpoint only;
- zero pre-freeze retry, zero post-freeze retry and one confirmation window;
- strict receipt-first execution and zero RF persistence.

The public surface is only:

```python
run_reviewed_once(live_authorised=False)
```

Endpoint, frequency, feature, delta, thresholds, duration, connector, receipt
path, retry and outcome policy cannot be supplied by the caller. Default
refusal occurs before seal assessment, receipt creation or connector access.

## Same-session correction

The audit exposed a real execution-boundary issue. F2.5.23's injected
materializer correctly closes its context when its offline task ends. Reusing
that function in a live wrapper would therefore close both SND channels before
the independent confirmation.

The sealed surface does not modify or bypass F2.5.23. It composes the reviewed
primitives directly and keeps the same two channel connections open only for:

```text
fresh direct dual-SND qualification
  -> one-target discovery
  -> target-excluded distributed retune qualification
  -> immutable plan freeze
  -> qualification-ledger closure
  -> one independent A1/B/A2 confirmation
  -> one outcome
  -> channel close
```

The qualification command ledgers are measured and cleared after witness
qualification. The confirmation therefore begins with empty reference and
perturbed ledgers; only its own B and A2 commands may appear in the F2.5.24
receipt. This is a causal boundary, not permission to modify the plan.

## Failure and stop semantics

- Failure to requalify dual SND stops before discovery.
- Failure to discover one target stops before retune.
- Failure of the target-excluded witness stops before freeze.
- A capture or software exception consumes the one execution and closes the
  context; it does not authorize retry.
- A valid frozen plan permits exactly one confirmation evaluated by F2.5.24.
- Channel-close or receipt-description errors remain descriptive and cannot
  replace an already produced physical result.

The five confirmation outcomes remain:

- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`;
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`;
- `AMBIGUOUS`;
- `INTERVENTION_INVALID`;
- `NOT_DETECTABLE`.

The first two remain coordinate claims relative to the channel DDC. Neither
means “external RF”, identifies a transmitter or excludes shared
antenna/front-end/ADC/clock causes.

## Offline verification

Tests prove that:

- every commit, causal hash, environment and control-surface seal matches;
- default refusal precedes all effects;
- a blocked pre-freeze phase never enters confirmation;
- a valid plan reaches confirmation only with an empty command ledger;
- the confirmation capture preserves frozen center, delta and event-time
  boundary;
- the same-session context is always given a close attempt;
- a close-description failure leaves the confirmation result unchanged;
- receipts are strict scalar metadata with no samples, STFT or waterfall.

## Stop condition

Gate F2.5.25 ends with
`EXACT_ONE_TARGET_CONFIRMATION_READY_FOR_SEPARATE_AUTHORITY`. This state does
not grant or consume live authority. A subsequent explicit authorization may
consume this surface once. Without that authorization the only legal action is
offline inspection.
