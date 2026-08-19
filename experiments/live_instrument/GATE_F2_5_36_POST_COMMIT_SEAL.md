# Gate F2.5.36 — audited-vertical post-commit seal

Gate F2.5.36 seals the committed F2.5.35 successor without opening a network
connection or consuming an authority. The only live-capable function is
default-refusing:

```python
run_reviewed_once(*, live_authorised: bool = False)
```

With its default value it raises before assessment, receipt creation or
connector access.

## Reviewed lineage

```text
F2.5.35 commit:
  cc2136e129e5856eea43d88aa568e6416715c2a0

F2.5.35 source:
  b13523f10edaab9b7eda9615f05ecfd6ab611bd40a499a28005dcaf087e46c86

inherited F2.5.32 plan:
  45c9d39c8d2ede4ebbf456bce400e0ac113aee305b81601c2734ffd5a96741d3

decision/audit surface:
  1f70f9ce97026b6abee04e05499e9f94343823fe1db4c9735b478afaa9115578

audited integration surface:
  138b789e5354e93cda06468a08936fd5fd7fda8a5f47a6bb493fd7e67251027d

reviewed F2.5.33 connector source:
  a69f25b9a98482b84dc8c3b404984fe72c5b555a45f28efd27c5d0ae15e27917

live surface:
  49256851ef91002f01e24ccb3642bcbc2e40f7aa5099f2ec00f8adbec9b73733

authority envelope:
  37f9a442274f45e165549d8e5910179d84d3f63b46342b8133cfdaf2e39c32dc
```

The assessment verifies that the reviewed commit is an ancestor, the
F2.5.35 source has no Git diff, every source and surface hash matches, the
numerical environment is exact and execution is launched from the repository
root.

## Frozen execution envelope

The envelope fixes:

- endpoint `dl1bajkiwisdr.ddns.net:8074`;
- two simultaneous SND connections on the same Kiwi;
- distinct fixed-reference and perturbed DDC branches;
- the existing A1→B→A2 phase order;
- the inherited F2.5.32 plan and unchanged thresholds;
- decision-first, non-authoritative scalar audit semantics;
- the reviewed F2.5.33 live connector and mutable-frame ownership adapter;
- no waterfall and no `ext_api` admission role;
- zero retry before and after freeze;
- exactly one outcome window and first-terminal-outcome stop;
- one default repository receipt path with no caller override;
- strict decision, scalar audit and hash-only receipt content;
- zero RF persistence.

The public caller cannot change endpoint, frequency, sample geometry,
threshold, audit builder, transformation, retry, receipt path or connector.

## Guard order

```text
explicit authority
  -> post-commit seal
  -> authority envelope as first receipt event
  -> two fixed SND connectors
  -> one audited F2.5.35 outcome
  -> terminal manifest
```

Partial connector failure closes the peer and terminalizes the receipt.
Normal execution delegates socket and IQ cleanup to the reviewed F2.5.35
outer owner.

## Receipt semantics

A future authorized result would contain:

- authority envelope and its hash;
- one `F2535RunResult`;
- the authoritative physical `F2532RunResult`;
- the sibling scalar discovery audit or a typed description-error hash;
- phase, clause, command and boundary scalar receipts when evaluated;
- the terminal prefix hash and retention manifest.

It cannot contain IQ, samples, waterfall, STFT, spectrum, normalized patches
or candidate arrays. Strict JSON rejects non-finite values.

## Offline verification

Synthetic tests establish that:

- default refusal precedes all work;
- any source, environment, envelope or live-surface change fails closed;
- the authority event is first and exactly one audited outcome is emitted;
- a negative discovery retains closed scalar stage counts;
- the receipt contains no RF-derived arrays or non-standard numbers;
- partial dual-connector failure closes the admitted peer;
- the terminal manifest is emitted on both success and failure paths.

These tests do not provide a live outcome.

## State

```text
assessment: AUDITED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY
live execution authorized: false
authority consumed: false
network activity: zero
raw RF persistence: ZERO
```

Gate F2.5.36 stops here. A later user decision may either retain the runner
unused or authorize one exact execution. Such an authority would permit zero
retry and exactly one terminal outcome; it would not authorize code changes or
a second window.
