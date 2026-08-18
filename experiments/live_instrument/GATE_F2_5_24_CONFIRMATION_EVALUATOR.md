# Gate F2.5.24 — offline post-freeze confirmation evaluator

Gate F2.5.24 closes the code path that Gate F2.5.23 deliberately left open.
It evaluates an already frozen one-target plan against one injected,
independent A1/B/A2 artifact set. It does not connect to a Kiwi, acquire IQ,
authorize an execution or persist RF.

## Bound input

The evaluator is bound to reviewed Gate F2.5.23 commit
`7e8cfe39bcb9afec295ea520018d47260e67416b`. The input plan already fixes:

- one target fingerprint and its A-state coordinate;
- the measured diagnostic translation and orientation;
- disjoint upstream-of-channel-DDC and channel-fixed B intervals;
- wrong-sign, half-magnitude and off-feature controls;
- the target-excluded distributed witness rule;
- one confirmation window and zero post-freeze retry;
- all numerical thresholds and transform versions.

Changing any of those fields changes the plan hash and constitutes a different
trial.

## Evaluation precedence

The confirmation is evaluated in this order:

```text
event after freeze + six distinct pre-analysis hashes
  -> exact channel, tuning and command ledger
  -> continuous, clean event-time streams
  -> target-excluded distributed retune witness
  -> witness orientation equals frozen orientation
  -> target detectability in both A1 branches and fixed reference
  -> the two frozen B predictions and three negative controls
  -> A2 return
  -> one terminal outcome
```

The target cannot rescue the intervention. If the distributed fingerprint is
not uniquely translated, fixed on the reference and returned in A2, target
clauses are `NOT_EVALUATED`. If the intervention is valid but the target
detectability envelope is lost, the result is `NOT_DETECTABLE`, not an
intervention failure and not support for either hypothesis.

## Outcome semantics

- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`: the target matches only the frozen
  translated B interval, the reference remains fixed, controls are absent and
  A2 returns.
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`: the distributed witness translates,
  but the target matches only its frozen channel coordinate.
- `AMBIGUOUS`: the measurement topology and target envelope are valid, but
  both predictions, neither prediction, or a negative control matches.
- `INTERVENTION_INVALID`: event time, artifact identity, stream continuity,
  command/tuning ledger, distributed translation or frozen orientation does
  not admit target evaluation.
- `NOT_DETECTABLE`: the distributed witness has insufficient usable structure,
  or a valid intervention does not preserve the target detectability envelope.

“Upstream of channel DDC” is a scope-limited coordinate claim. It is not a
synonym for external RF and does not exclude an antenna, front-end, ADC or
shared-clock artifact.

## Offline verification

Deterministic fixtures use the same immutable plan and causal topology for all
five allowed outcomes. They cover unique upstream and channel-fixed matches,
both/neither prediction, a positive negative-control, unresolved and
undetectable witnesses, loss of target detectability, pre-freeze event time and
an invalid tune-command ledger. Tests also prove that invalid admission stops
before profile extraction and that receipts contain only strict scalar
metadata and six artifact hashes.

The module deliberately has no connector, live runner, endpoint selection,
retry path or capture default. IQ arrays exist only inside injected test
artifacts and never reach JSON. `raw_rf_persistence` remains `ZERO`.

## Stop condition

Gate F2.5.24 stops after offline evaluator integration and tests. It produces
no physical observation. A future live confirmation would first require a
separate commit-specific review and explicit authority; the frozen plan still
permits only one independent confirmation and no retry.
