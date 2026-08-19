# Gate F2.5.28 — injected relative-time one-shot

Gate F2.5.28 integrates the topology-derived F2.5.27 temporal plan into one
specific offline phase path. It accepts only injected transient SND frames and
injected discovery/retune probes. It has no WebSocket, endpoint selection,
network connector, live authority, retry or receipt path.

```text
reviewed Gate F2.5.27 commit:
3b678173d5836c8f72696c0a9ea1a7c6a3d25ff8

live execution authorized: false
prefreeze retry: 0
postfreeze retry: 0
RF persistence: ZERO
```

## Sealed inputs

The envelope binds:

- the F2.5.26 and F2.5.27 canonical source hashes;
- the immutable F2.5.27 temporal plan hash;
- Python 3.13.5 and NumPy 2.3.3;
- the exact `observe_relative_snd` source surface;
- the exact `run_one_shot_injected` source surface.

A changed parser, phase order, environment, parent source or one-shot function
produces `SEAL_MISMATCH` before injected execution.

## Frame boundary

For every transient frame, the execution order is fixed:

```text
transient SND bytes in RAM
        ↓
SHA-256 before header or sample analysis
        ↓
SND/IQ geometry and scalar header decode
        ↓
ScalarFrameReceipt + ephemeral complex64 IQ
        ↓
relative-time admission
        ↓
optional read-only discovery/retune views
        ↓
unconditional zeroization in finally
        ↓
receipt-only result
```

The scalar receipt contains artifact hash, byte count, endpoint, role, channel,
sequence, actual server seconds/nanoseconds, GPS-age byte, sample count, sample
rate and monotonic arrival. It contains no body, samples, STFT or waterfall.

Malformed, non-IQ or geometrically invalid frames still retain their
pre-analysis artifact hash. Their state is `QUALIFICATION_ERROR`, never
`CAPABILITY_REJECTED` and never a physical absence.

## Immutable phase gate

The phase order is:

1. `RELATIVE_DUAL_SND_QUALIFICATION`
2. `ONE_TARGET_DISCOVERY`
3. `DISTRIBUTED_RETUNE_QUALIFICATION`
4. `PLAN_FREEZE`
5. `ONE_CONFIRMATION`

F2.5.28 stops before the last two phases. It proves only the access rules:

| Upstream result | Discovery calls | Retune calls | Downstream state |
|---|---:|---:|---|
| frame qualification error | 0 | 0 | all `NOT_EVALUATED` |
| temporal refusal | 0 | 0 | all `NOT_EVALUATED` |
| temporal pass, discovery negative | 1 | 0 | retune and later `NOT_EVALUATED` |
| temporal pass, discovery error | 1 | 0 | retune and later `NOT_EVALUATED` |
| discovery positive, retune error | 1 | 1 | later `NOT_EVALUATED` |
| discovery positive, retune lacks a boundary | 1 | 1 | `INTERVENTION_NOT_QUALIFIED` |
| discovery positive, both boundaries witnessed | 1 | 1 | `RETUNE_QUALIFIED_OFFLINE` |

No callback can make an upstream temporal failure pass. Descriptive callback
exceptions are hashed and recorded separately; they cannot modify physical
state.

## Boundary requirement

A retune probe may claim qualification only when it returns exactly two
retained scalar boundary receipts:

```text
A1_TO_B = BOUNDARY_WITNESSED
B_TO_A2 = BOUNDARY_WITNESSED
```

The runner independently checks their transition identities and states. A
probe returning `claimed_qualified=true` with one missing, duplicated or
unwitnessed boundary is `INTERVENTION_NOT_QUALIFIED`.

These receipts close ordering and stream-continuity cuts. They do not prove a
live command acknowledgement or a spectral translation. That still belongs to
the target-excluded distributed witness.

## RAM and destruction semantics

Discovery and retune receive read-only NumPy views. The owning arrays remain
private to the one-shot function. Its `finally` block overwrites every decoded
complex sample with zero, verifies the arrays, and creates a scalar
`ZeroizationReceipt` before returning.

The returned result includes:

- temporal admission receipt;
- frame and downstream error receipts;
- both command-boundary receipts, when evaluated;
- ordered phase receipts;
- callback counts;
- frame/sample zeroization counts and artifact-set hash.

It cannot include the transient input objects or array views. Strict JSON tests
reject RF-bearing keys and non-finite values.

This is process-level zeroization of the owned decoded arrays, not a claim
about physical RAM remanence. Injected input bytes are immutable and owned by
the caller, so this function cannot overwrite them; it makes no copy that
survives and never returns or writes them. A future live wrapper must own and
release each WebSocket byte object after this boundary. The present gate proves
only that the result retains neither bytes nor decoded arrays.

## Offline outcomes

`TEMPORAL_NOT_ADMITTED`
: Scalar measurements exist but one or more same-clock clauses fail. Discovery
  and retune are inaccessible.

`QUALIFICATION_ERROR`
: Frame or injected software semantics prevent evaluation. No physical
  rejection is authorized.

`NO_FALSIFIABLE_INTERVENTION`
: Relative time passes, but the injected discovery finds no eligible target.

`INTERVENTION_NOT_QUALIFIED`
: Discovery passes, but retune or one of its boundary witnesses does not.

`RETUNE_QUALIFIED_OFFLINE`
: Synthetic inputs pass timing, discovery and both boundary requirements. This
  demonstrates control-flow integration only.

Plan freeze and confirmation are always `NOT_EVALUATED` in this gate.

## Authorized claims

Gate F2.5.28 demonstrates that:

- hashing precedes SND/sample analysis;
- temporal admission is a hard gate on feature access;
- discovery is a hard gate on retune access;
- both predeclared command boundaries are necessary for retune qualification;
- every decoded IQ array is zeroized before the result returns;
- the retained result is strict scalar/hash JSON.

It does not demonstrate that:

- any live Kiwi currently passes F2.5.27;
- the F2.5.25 outcome should be reclassified;
- a live retune is acknowledged or effective;
- an interesting RF feature exists;
- a feature is upstream or downstream of the channel DDC.

## SHOCK

The important runtime object is not the receiver or even the IQ batch. It is
the short-lived permission to let one transformation see the IQ. That
permission is created by satisfied upstream clauses and disappears with the
arrays in `finally`.

This makes `NOT_EVALUATED` executable rather than descriptive: forbidden
phases have a measured callback count of zero.

Gate F2.5.28 stops before a real connector seam and before live authority. The
next admissible step is an offline live-facing wrapper audit using injected
WebSocket frames. Only a later post-commit seal may expose a default-refusing,
one-use authority bit.
