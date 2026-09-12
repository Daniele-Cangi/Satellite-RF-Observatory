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
