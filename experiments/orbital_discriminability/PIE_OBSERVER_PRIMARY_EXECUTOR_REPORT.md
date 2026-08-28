# PIE observer primary executor report

## Frozen outcome

`PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED`

The experiment-specific one-shot executor is frozen offline. It accessed zero
PIE DOY223 headers, payload bytes, observation values and orbital scores. The
seal does not grant live authority. There is no primary outcome file and the
one-use authority marker has not been created.

## Physical purpose

The executor can produce one new piece of satellite information: whether the
already frozen G22 orbital prediction is prospectively preferred to the
affine and G01/G14/G17 alternatives on one held-out PIE observer interval. It
does not create a reusable acquisition system or change the proof contract.

## Frozen bindings

- source commit: `c9334e45025e837a11cc62eec084b1e0495a58e2`
- source SHA-256: `aaa59603eec7dc3139bb4f935faa899e9a8158708c877d8356c459500cf9727a`
- executor manifest SHA-256: `68d0b9ccadfc6f97cbf522784c4c6957352d231739c27f69ef6c0ba1353fb4e3`
- executor seal SHA-256: `3b15c0c899756c48c80a6339cb6c6e20a0f493f379f8b439c445caf1bf033e2b`
- prediction SHA-256: `a86a360fcbf9e1aa05e112bae1e2d1158b729f6e2fe9b4418a89883c72aacbc9`
- prediction seal SHA-256: `446b65682cf9bfe7eac5d4fe63a1c709dc0ebaf9f75a681214f925b0f111e4e9`
- plan manifest SHA-256: `5fef155739849280fced56a5967460df7be0b6e9ae1522aadbc61b6d667a6867`
- qualified header transform SHA-256: `5988af21e1812ab17c63a2d547eb0babd5ca754c2a5bbeebb6e9ef263d4ec672`

The sole logical product is
`PIE100USA_R_20262230000_01D_30S_MO.crx.gz`. The product's complete-file byte
count and SHA-256 intentionally remain unknown until an independently
authorized materialization.

## One-shot boundary

The executor accepts only the documented anonymous GSSC web-session transport
and has no fallback. It permits at most two attempts before a complete-file
hash, and only for timeout or transport interruption. Description errors have
zero retry. Before the first network operation it persists a one-use authority
consumption marker; an existing marker or outcome refuses execution. After a
complete hash or any decoding begins there is no retry, new window, endpoint
change or product substitution.

Compressed and decoded products and all phase, code and derived coordinate
arrays exist only in RAM and are explicitly erased. The only permitted
persistent result is an aggregate outcome and its non-value receipts.

## Measurement and scoring contract

Admission requires the full 139-epoch G22/G30 grid, L1C/L2W phase with zero
LLI, event-time deviation no larger than 15 seconds, geometry-free
second-difference health, and C1C/C2W same-path availability. The fixed
ionosphere-free phase-minus-code witness must remain within 1,250 m
peak-to-peak for each satellite. Exceeding that witness is `NOT_DETECTABLE`,
not a measurement-invalid or negative orbital result.

Sample zero is the sole anchor. No constant, rate, free time phase or suffix
refit is permitted. Only raw indices 79 through 138 are scored. Models are
ordered by peak-to-peak residual, RMS residual and frozen name; a physical
preference requires a strictly greater than 7,899.820878397492 m pairwise
advantage. Measurement, description and materialization failures remain typed
and cannot become physical outcomes.

## Verification and stop

The bounded executor, prediction and plan suite passes, including adversarial
authority, retry, memory-erasure, witness, no-fit and strict-JSON tests. An
exact seal regression binds the hashes above.

The stop remains `STOP_BEFORE_PRIMARY_ACCESS_FOR_SEPARATE_REVIEW`. A later live
run requires explicit authority for exactly this seal hash and the frozen
one-use token. The present commit and seal alone authorize no observation.
