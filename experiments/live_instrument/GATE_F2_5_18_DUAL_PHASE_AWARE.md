# Gate F2.5.18 — dual phase-aware qualification envelope

## Outcome

`DUAL_PHASE_AWARE_ENVELOPE_MATERIALIZED_OFFLINE`

Gate F2.5.18 composes two Gate F2.5.17 branch openers concurrently on one
candidate, preserves the existing same-Kiwi topology clauses and places the
corrected control receipts inside one terminal candidate-loop artifact.

No Kiwi endpoint was contacted and no RF data was acquired.

## Frozen execution semantics

- candidate identities and order: unchanged;
- center policy: unchanged and data-independent;
- one endpoint at a time;
- exactly two parallel branches: `reference` and `perturbed`;
- one attempt per endpoint;
- pre-freeze retry: zero;
- post-freeze retry: zero;
- status precondition: none;
- waterfall: absent from the causal path;
- stop: first `DUAL_READY` pair or candidate exhaustion;
- raw RF persistence: zero;
- connector and WebSocket framing: mandatory injection;
- post-commit seal: required before any live authority.

Both branches bind control-plan hash
`c1a2d8fc139e6090ee70500f258b28c9160174a3411908d4b347c959cf6909fd`.
The pair refuses any pre-setup keepalive and keeps remote setup
acknowledgement `NOT_EVALUATED` even when local commands were emitted.

## Pair admission

A candidate reaches `DUAL_READY` only when both corrected branches provide:

- semantic SND/IQ readiness;
- distinct connection objects;
- distinct server channel identifiers;
- independent stream sequence witnesses;
- overlapping GNSS event time;
- distinct atomic receipts.

Two locally complete setup ledgers are necessary but insufficient. They do not
replace either SND readiness or topology evidence.

Explicit server refusal remains `EXPLICIT_PAIR_REJECTED`. A transport or
software failure remains `QUALIFICATION_INCOMPLETE`. Two ready streams with an
invalid topology remain `TOPOLOGY_REJECTED`.

## Offline verification

Synthetic tests demonstrate:

- the two connectors start concurrently;
- both setups contain zero pre-setup keepalive;
- a ready pair preserves every topology clause;
- explicit branch refusal cannot promote topology;
- equal channel IDs reject an otherwise ready pair;
- the candidate loop preserves order and stops at the first ready pair;
- the JSONL terminal artifact closes cleanly;
- no default connector, autonomous runner or live authority exists.

This commit is not executable live by itself. A separate post-commit seal must
bind the exact causal source, environment and envelope before the user can
authorize one qualification outcome.

Gate F2.5.18 stops here.
