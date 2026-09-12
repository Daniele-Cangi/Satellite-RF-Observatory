# S2 four-fit/one-heldout topology audit

## Physical question

Can the frozen temporal code plus interval-phase structure retain a locally
identifiable state with four of the five header-qualified roots, while the fifth
root remains excluded for a genuinely held-out code prediction?

## New information and minimum experiment

The earlier five-root audit put every root into the fit and therefore could not
answer this question. This audit evaluates all five deterministic
leave-one-root-out partitions over the exact 181 target-free, jointly visible
synthetic cases already retained by that audit. It reuses the same endpoint
times, covariance, persistent bias box, +30/+60 second held-out prediction and
100 m/10 km limits.

Every partition is retained. A conditionally usable case requires four-root
local rank, no more than 10 km conditional fit envelope, visibility of the fifth
root at both future endpoints and positive held-out physical slack at both. At
least 20 such cases and zero rank failure are required before a partition can
be called conditionally available.

This produces no real measurement admission or target/orbit evidence. Positive
slack remains conditional on the inherited error assumptions; every unresolved
receiver, atmosphere, continuity, truncation and nonlinear term stays open.

## Stop condition

The run must stop after the five partitions with exactly one terminal:

- `FOUR_FIT_ONE_HELDOUT_CONDITIONALLY_AVAILABLE`
- `FOUR_FIT_ONE_HELDOUT_NOT_SUPPORTED`

No new root, source, date, target, orbit or observation value may enter, and the
synthetic family and thresholds cannot be changed after execution.

## Execution provenance repair

The first local invocation supplied a syntactically valid but incorrect source
commit suffix. Its generated JSON had SHA-256
`04c9d312078a665356597453272978dd176f8b9dea311674740f0f5e09915c0c` and is
classified execution-invalid: no numerical outcome from it is authoritative.
It accessed no network, target, orbit or observation value. A compact receipt is
retained while the non-authoritative generated JSON is discarded.

The runner now requires a clean tree, exact equality between the declared
40-character commit and `HEAD`, and byte equality of the committed plan and
implementation before calculation. No scientific parameter was changed.
