# AMC observer primary executor report

## Frozen outcome

`AMC_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED`

The experiment-specific one-shot executor is frozen offline. It accessed zero
AMC DOY221 locator responses, headers, payload bytes, observation values and
orbital scores. The seal does not grant live authority. There is no primary
outcome file and the one-use authority marker has not been created.

## Physical purpose

The executor can produce one new piece of satellite information: whether the
already frozen G22 orbital prediction is prospectively preferred to the affine
and G01/G14/G17 alternatives on the held-out AMC observer interval. It does not
create a reusable acquisition system or change the proof contract.

## Frozen bindings

- source commit: `b31a987987578a24fdc0594c44d00abf787f8510`
- source SHA-256: `d87cde21fe8b0ff4e6265e4e460c1c24aaad6a2a590f85d0b8e830fa9975ef63`
- executor manifest SHA-256: `d30cd0eb4f6fac2b3e73303f5dcd7764d6fb9ce4bcc8e475b13dad2c5ec9c344`
- executor seal SHA-256: `0b6ffe5af82b15404b7a546e8203df6415a68e0ba373c03500d31d4645f44893`
- prediction SHA-256: `c9f7236f3cc221cb8485fe82f0a739e720ee3725f9dbf7c7fcc54c4167794155`
- prediction seal SHA-256: `83a52b2fbaa8f921532684cc87f292ffb976fb8972e595d21ffa0a645b4bb2f5`
- plan manifest SHA-256: `0a3c1e3768566da6242d6aaffd6c751a23d6bf167c7f54d0498fe75f365609b0`
- qualified header transform SHA-256: `b717042b94b2febc3e93294463cba37ecedc9837bbe7e16fd3368d028463fbdd`

The sole logical product is
`AMC400USA_R_20262210000_01D_30S_MO.crx.gz`. Its complete-file byte count and
SHA-256 intentionally remain unknown until an independently authorized
materialization.

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
persistent result is one aggregate outcome and its non-value receipts.

## Measurement and scoring contract

Admission requires the full 139-epoch AMC G22/G30 grid, L1C/L2W phase with
blank-or-zero LLI, event-time deviation no larger than 15 seconds,
geometry-free second-difference health and C1C/C2W same-path availability. The
fixed ionosphere-free phase-minus-code witness must remain within 1,250 m
peak-to-peak for each satellite. Exceeding that witness is `NOT_DETECTABLE`,
not a measurement-invalid or negative orbital result.

Raw index zero is the sole anchor. No constant, rate, free time phase or suffix
refit is permitted. Only raw indices 79 through 138 are scored. Models are
ordered by peak-to-peak residual, RMS residual and frozen name; a physical
preference requires a strictly greater than `7,339.701234647398 m` pairwise
advantage. Measurement, description and materialization failures remain typed
and cannot become physical outcomes.

## Verification and stop

The bounded executor, prediction and plan suite covers adversarial authority,
retry, memory erasure, witness, no-fit, transform and strict-JSON behavior. The
exact seal regression binds the hashes above.

The stop remains `STOP_BEFORE_PRIMARY_ACCESS_FOR_SEPARATE_REVIEW`. A later live
run requires explicit authority for exactly this seal hash and the frozen
one-use token. The present commit and seal alone authorize no observation.
