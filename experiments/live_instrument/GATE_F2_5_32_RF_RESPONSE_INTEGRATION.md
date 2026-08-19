# Gate F2.5.32 — open-handle RF-response integration

Gate F2.5.32 is exclusively offline. It integrates the reviewed distributed,
target-excluded RF witness into the exact open-handle A1/B/A2 lifecycle built
by Gate F2.5.31. Both sockets and every SND frame are injected. No connector,
authority bit or observation is present.

The terminal materialisation state is:

`RF_RESPONSE_INTEGRATED_OFFLINE`

This means that the vertical path can distinguish intervention validity,
detectability and physical hypothesis outcomes on synthetic IQ. It is not a
live Kiwi result.

## Frozen inheritance

The plan binds the reviewed F2.5.31 commit, source hash and plan hash. It keeps
unchanged:

- two simultaneous channels on the same Kiwi topology;
- eight A1, B and A2 analysis frames per branch;
- the 750 Hz technical retune delta;
- the 0.8-second settling interval;
- the 1024-point STFT geometry;
- minimum contrast, half-window contrast, fingerprint correlation and
  prediction tolerance from `MotherPlan`;
- zero retry, zero RF persistence and no runtime overrides.

No threshold was adapted to obtain a passing synthetic outcome.

## Evaluation order

The order is causal, not merely descriptive:

```text
dual open SND handles
        ↓
relative-time admission + A1 feature discovery
        ↓
A1 → B → A2 command boundaries and full continuity
        ↓
target-excluded distributed RF witness
        ↓
immutable target prediction/control hash
        ↓
target reveal at the frozen B/A2 positions
        ↓
one outcome + unconditional RF destruction
```

The target-independent witness is the existing F2.5.22 transform. It removes
the target neighbourhood at zero, both signed delta positions and both signed
half-delta positions before correlation. It then requires:

- at least 64 usable non-target bins;
- a common A-state fingerprint on both branches;
- a fixed reference fingerprint through A1/B/A2;
- a perturbed fingerprint that translates uniquely by one signed delta;
- a return to A2;
- the same translation on even and odd spectral-bin folds.

The function never evaluates target identity or target motion. If this witness
does not qualify, no target B/A2 match is called and no target plan exists.

## Plan freeze and target reveal

After the witness resolves a translation orientation, the runner constructs a
target fingerprint only from the already admitted A1 feature. It freezes:

- the upstream-of-channel-DDC B interval;
- the channel-fixed B interval;
- reference-fixed and A2-return intervals;
- wrong-sign, half-delta and off-feature negative controls;
- the inherited thresholds and witness artifact hashes.

The target-plan hash is materialised before any target matcher reads B or A2.
The same in-RAM phase arrays are used; therefore this gate proves evaluator
ordering and lifecycle integration, not temporal independence or a prospective
live confirmation.

## Outcome semantics

`INTERVENTION_INVALID`
: A command boundary/session continuity fails, or the target-excluded RF
  structure does not select one unique non-zero translation. Target hypotheses
  remain `NOT_EVALUATED`.

`NOT_DETECTABLE`
: Either the target-independent witness lacks usable RF structure, or a valid
  intervention is followed by failure of the frozen target detectability
  envelope. This is distinct from evidence for either physical hypothesis.

`UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`
: The valid distributed witness translates on the perturbed branch, the
  reference remains fixed, the target matches only the translated B interval,
  controls remain absent and A2 returns.

`DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`
: The independent distributed witness translates, while the target matches
  only its frozen channel-fixed B interval and returns at A2.

`AMBIGUOUS`
: Intervention and detectability are valid, but both predictions match, a
  negative control matches, or the result otherwise fails to select exactly
  one frozen hypothesis.

Earlier capability, topology, temporal, discovery and qualification failures
remain separate operational outcomes. A descriptive exception cannot become a
physical decision.

## Cleanup and receipts

Each phase artifact hash is derived from SND hashes bound before spectral
analysis. Returned receipts contain only finite scalars, enums and hashes.
Every decoded array, including settling frames, is overwritten in the one
outer `finally`; both handles close there and strict JSON serialization rejects
non-finite values. No spectrum, STFT, IQ, waterfall or transport payload is
persisted.

## Authorized claims

This gate authorizes only that the offline vertical path:

- keeps the exact two handles through the RF evaluation;
- evaluates command/time topology before RF structure;
- evaluates a target-excluded RF witness before target motion;
- freezes predictions and controls before target B/A2 matching;
- implements all five reviewed physical outcome semantics;
- destroys all ephemeral RF before return.

It does not prove external RF origin, transmitter identity, remote tune
acknowledgement, live endpoint behavior or either DDC-location hypothesis in a
real observation.

## SHOCK

An open socket and a correctly ordered tune command still do not constitute an
intervention. The decisive admission object is an RF coordinate transform that
survives outside the target region. Conversely, once that distributed witness
is present, a second hardware root is unnecessary for this per-channel causal
cut: the fixed sibling DDC branch is the cleaner control.

The next admissible work is a separate post-commit offline seal audit. It must
bind this exact integration surface and refuse authority by default. Only a
later, separately authorized single execution may consume an authority bit.
