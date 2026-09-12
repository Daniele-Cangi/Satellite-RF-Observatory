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

## Frozen result

The corrected, provenance-bound execution terminated
`FOUR_FIT_ONE_HELDOUT_CONDITIONALLY_AVAILABLE`. All five partitions retained
full local rank for all 181 predecessor cases. This shows that the temporal
code plus interval-phase coordinate can preserve local identifiability with
four fit roots; the earlier need for a sixth root was partly an allocation
assumption, not a universal receiver-count law.

The partition ranking is:

| Held-out root | Rank failures | Held-out-visible cases | Conditionally usable | Median fit envelope at +60 s | Held-out slack range |
|---|---:|---:|---:|---:|---:|
| GOLD00USA | 0 | 181 | 62 | 17.733 km | 7.046–27.215 m |
| PIE100USA | 0 | 181 | 60 | 17.660 km | 1.567–28.357 m |
| MKEA00USA | 0 | 181 | 0 | 38.070 km | −1153.928–−20.190 m |
| BOGT00COL | 0 | 181 | 0 | 33.089 km | −1450.111–−128.696 m |
| ALGO00CAN | 0 | 181 | 0 | 121.449 km | −1085382.992–−11.923 m |

For GOLD held out, every 12,000 km case (4), every 20,000 km case (28) and
30 of 44 cases at 30,000 km are conditionally usable. PIE1 retains 4, 28 and
28 respectively. Neither partition retains a usable case at 45,000 or
60,000 km. GOLD and PIE1 overlap on 59 cases; this is a robust partition
distinction within the frozen family, not one isolated favorable point.

The held-out margins for GOLD and PIE1 are positive across all retained
endpoints, but the four-root fit envelope remains highly nonuniform. GOLD's
+60 second envelope spans 0.583–90.050 km, while PIE1 spans 0.549–85.560 km.
The terminal therefore authorizes no actual event selection, S3 run or real
measurement claim. Real five-root code/phase continuity and the total physical
error envelope remain unresolved, and a future selection rule must not inspect
a target orbit to choose one of the 62 favorable synthetic analogues.

The authoritative result is
[`results/s2_four_fit_one_heldout_v1.json`](results/s2_four_fit_one_heldout_v1.json),
SHA-256 `e1998956c673af44b7580b5ce15929c512cb101a65494841b2c1815f4cea3aec`.
Its source commit is `b8c0a1f1d56dc42aa2280be60a2cf907b9d2cacc`.

The smallest next physical step is a distinct, target-free reference-only
qualification of exactly ALGO, BOGT, MKEA and PIE1 as fit roots plus GOLD as a
code held-out root. It must establish complete common-window structure,
unchanged hardware identities, the frozen code/phase transforms and an
outcome-independent physical error envelope before any target or primary is
selected.
