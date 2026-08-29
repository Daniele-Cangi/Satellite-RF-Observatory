# Blind-orbit primary executor freeze

## State

```text
BLIND_ORBIT_PRIMARY_EXECUTOR_FROZEN_UNOPENED
```

This is the experiment-specific one-shot executor for the already frozen AMC
DOY226 blind-orbit assignment. It creates no gate or reusable adapter. The
primary product remains unqueried and unopened at this freeze.

```text
network requests: 0
product locators queried: 0
primary headers: 0
primary payload bytes: 0
primary observation values: 0
measurement scores: 0
```

## Frozen bindings

| Item | Binding |
| --- | --- |
| source commit | `07f31033258fcee87071b128cad48f74b2d6f946` |
| executor source SHA-256 | `70a1c0cc1af1aeed1b58fd52a02cfafd310652dd01eb3c2e140cb61231d247c4` |
| executor manifest SHA-256 | `d26bf3498d9e6c382e0ef9c57b5c5a6111d8540e089efee72dc6c5d8c539c4d9` |
| executor seal SHA-256 | `2d385f73a0e6a5a8038fe875262b10022f95c04b4e9116f3ab0ecc87b95cd1be` |
| plan receipt SHA-256 | `b35ccbee73762f7d9a8957f4d72c34ae684447a24fab055712708e064fbf3d9f` |
| opaque bundle SHA-256 | `a36aed59f32ee9b409778e44a0b661aebbf83c0675c58473c6655ad562c82ee2` |
| prediction/scorer seal SHA-256 | `2403358fed46293a1c44a9a7576a52c4cac547507abec1da1be5db1c7ff711f4` |
| mapping seal SHA-256 | `b719a2bf17e66fcafa3597c4018d6acd039bdac4e33ecb173795646ff47245db` |

The frozen runtime dependencies are Python 3.13.5, NumPy 2.3.3, Hatanaka
2.8.1 and Requests 2.32.4.

## One-shot order

The executor enforces this order:

```text
one-use authority marker
-> exact GSSC product materialization
-> recomputed complete byte count and SHA-256
-> in-RAM Hatanaka/RINEX decode
-> structural and physical admission
-> one finite unlabelled 139-point coordinate
-> opaque scorer
-> canonical opaque score receipt
-> persisted score-receipt hash
-> mapping reveal
-> one terminal outcome
-> RAM buffer erasure
```

The mapping file is hash-checked but not parsed during frozen-input
validation. Its semantic content is read only after both the opaque score
receipt and the receipt of its hash exist. The scorer receives no PRN,
product, observer, navigation or mapping input.

The executor recomputes the complete artifact byte count and SHA-256 before
calling the decoder, even when a materializer supplies a receipt. A mismatch
is a descriptive failure and cannot become a physical rejection. Only timeout
or interrupted transport can use the second pre-hash attempt; no retry or
substitution exists after a complete hash or decode.

The size-limit path explicitly erases any partial primary payload. Hatanaka
content/format failures remain measurement-invalid, while an unexpected
decoder API or software failure is descriptive and cannot reject the physical
measurement.

## Frozen terminal semantics

Pre-score outcomes are:

```text
PRIMARY_ARTIFACT_MATERIALIZATION_FAILED
PRIMARY_DESCRIPTION_ERROR
BLINDING_INVALID
MEASUREMENT_INVALID
NOT_DETECTABLE
```

Post-score outcomes are:

```text
BOUNDED_TRUE_ORBIT_PREFERRED
BOUNDED_ALTERNATIVE_ORBIT_PREFERRED
FROZEN_AFFINE_NULL_PREFERRED
AMBIGUOUS
```

Only `BOUNDED_TRUE_ORBIT_PREFERRED` authorizes the bounded claim already
written in the prospective plan. An alternative, affine-null or ambiguous
result is retained as a scientific negative or unresolved result, not retried.

## Stop boundary

The seal itself grants no live authority. The next maximum action is one
separately authorized execution against exactly
`AMC400USA_R_20262260000_01D_30S_MO.crx.gz`; no alternate station, day,
product, window, candidate, threshold or null is permitted.
