# Gate F2.5.34 — discovery failure attribution

Gate F2.5.34 is exclusively offline. It does not reconnect to Kiwi, recover
RF from hashes, change the F2.5.33 thresholds or authorize another window. It
binds the committed outcome receipt and asks a narrower question:

> Which part of `NO_FEATURE_ADMITTED` is actually attributable from the
> retained scalar description?

The answer is: the composite admission failed, but the first failed predicate
is not observable from this receipt.

## Frozen lineage

```text
outcome commit: 51c43c78f7e69d937e2ac25cdbd60b84df415ecf
runtime seal:   77a5f733725e83e758560eb1af7db4ee1a4d3d25
receipt:        session_receipts/gate-f2-5-33-20260819T001930.319362Z.jsonl
receipt hash:   1d0b9c2ff97702f533f7944f2c23c7f782da4bb2427ec3d02a3d3e6279aad62c
prefix hash:    08180d45a0cac8a0fd57b2f6934a3f8347114b416ca25368d8c40c576868ec44
authority:      3f052af8686b37be6e04b85543a5fca30ad05e8536a8d57d796034cc98c6ab52
retention:      COMPLETE
errors:         0
raw RF:         ZERO
```

The exact `_discover_one_feature` function and the earlier scalar audit from
F2.5.22 are source-hashed. Receipt parsing rejects non-finite JSON and any
byte change fails the artifact hash before interpretation.

## What was predicted

F2.5.33 did not reach a physical prediction. Its precondition was narrower:
the A1 discovery window had to yield one common feature satisfying every
unchanged rule below.

| Predicate | Minimum structure admitted |
|---|---|
| joint contrast | a guarded local peak at least `5.0 dB` in the pointwise minimum of the two residual spectra |
| patch validity | a complete normalized spectral neighbourhood in both DDC branches |
| cross-branch structure | neighbourhood correlation at least `0.65` |
| half-window stability | common contrast at least `3.0 dB` in both temporal halves |
| composite admission | at least one candidate satisfying all four predicates |

The transform used eight frames of 512 complex samples per branch, a
two-sided STFT with `nperseg=1024` and `noverlap=512`, log power, temporal
medians, a median-filter residual, fixed DC/edge guards, peak finding,
neighbourhood correlation and half-window checks.

The only proposition falsified by the receipt is therefore:

> This one authorized A1 window contains at least one feature admitted by the
> entire frozen composite rule.

That is not the proposition that the passband contains RF energy, a signal or
an important physical phenomenon.

## Sensor operation

The negative was not produced by a failed qualification path. The receipt
shows:

- two distinct simultaneous SND/IQ handles;
- eight input frames and seven usable timed frames per branch;
- identical `11998.995708 Hz` sample rates;
- no sequence gaps, arrival-order violations, timestamp-step violations or
  server clock error codes;
- `253937919 ns` of common same-clock overlap;
- a normal discovery return and an empty error ledger;
- 16 decoded frames and 8192 IQ samples zeroized after analysis;
- both sockets closed and every transport lease released.

This supports `MEASUREMENT_AVAILABLE_BUT_NO_FALSIFIABLE_FEATURE_ADMITTED`.
It does not support either physical DDC-location hypothesis.

## What the receipt can attribute

| Stage | Receipt state | Attribution |
|---|---|---|
| IQ decode and spectral residual | `EXECUTED` | the discovery returned normally and no description error was logged |
| joint-contrast peak | `UNRESOLVED_FROM_RECEIPT` | no raw peak count or contrast margin was retained |
| normalized patch validity | `UNRESOLVED_FROM_RECEIPT` | no valid/incomplete patch count was retained |
| cross-branch correlation | `UNRESOLVED_FROM_RECEIPT` | no candidate correlation or margin was retained |
| half-window stability | `UNRESOLVED_FROM_RECEIPT` | no candidate half contrasts or margins were retained |
| composite feature admission | `UNSATISFIED` | `NO_FEATURE_ADMITTED`, with every selected-feature scalar null |
| plan freeze and DDC intervention | `NOT_EVALUATED` | zero commands, boundaries, target matches or confirmation |

The outcome therefore has three different classifications at three scopes:

- `FALSIFYING` for the exact composite-discovery proposition in this A1;
- `INCONCLUSIVE` for attribution to any particular internal predicate;
- `NOT_FALSIFIABLE_WITH_THIS_RECEIPT` for
  `H_UPSTREAM_OF_CHANNEL_DDC` versus `H_DOWNSTREAM_CHANNEL_FIXED`.

## Possible false-negative conditions

The following are causal possibilities, not inferred causes:

- the physical structure was shorter, narrower or broader than the frozen
  STFT/median representation;
- it lay in the fixed DC or edge guards;
- a broad common change was removed by the median-filter residual;
- branch response or a local branch artefact reduced the pointwise minimum or
  patch correlation;
- a real transient occupied only one temporal half;
- the roughly `0.34 s` decoded capture or `0.254 s` timed overlap did not
  contain a stable regime;
- the relevant phenomenon did not map to the required common spectral
  morphology.

The artifact cannot rank these possibilities.

## Claims

Authorized:

- the dual-SND and relative-time capability worked in A1;
- the frozen composite discovery rule was unsatisfied;
- the transform completed normally rather than failing qualification or
  serialization;
- the physical hypothesis remained `NOT_EVALUATED`.

Not authorized:

- the passband had no signals or no important information;
- contrast, patch validity, correlation or stability was the specific cause;
- the ADC, receiver or a DDC failed;
- a feature was upstream or downstream of the channel DDC;
- a lower threshold would have yielded a valid result;
- another window would reproduce or reverse this outcome.

## Minimum future conceptual change

Do not change the selector. Add, beside its authoritative result, a
decision-independent scalar `DiscoveryAuditReceipt` containing:

- raw-peak, patch-valid, correlation-pass, half-stability-pass and admitted
  counts;
- the best finite margin to each frozen threshold, with an explicit numeric
  state when unavailable;
- the same pre-analysis artifact hashes and transform version;
- no IQ, STFT, spectrum, spectral patch or waterfall.

This is not a new abstraction. Gate F2.5.22 already expressed the needed
stage counts and candidate margins. F2.5.31 later compressed the negative to
one bit and null selected-feature scalars. The minimum repair for a future,
separately authorized experiment is to restore that descriptive observability
as a sibling receipt while making it structurally unable to alter the
selection decision.

## SHOCK

The failure is not attributable to the sensor, and it is not yet attributable
to a physical model. It is attributable only to the boundary between a rich
multi-stage feature transform and a lossy negative receipt.

The system successfully refused an unfalsifiable intervention, but it threw
away exactly the scalar sufficient statistics needed to learn why the
precondition failed. More RF would not repair this artifact. Better
decision-independent description would.

Gate F2.5.34 stops here. No future runtime change, new threshold, new window or
live authority is included.
