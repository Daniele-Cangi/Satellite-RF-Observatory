# ALGO/MDO DOY219 primary executor freeze

## Physical question

For the already frozen ALGO00CAN/MDO100USA DOY219 coordinate, does one
independent held-out observation prefer the frozen broadcast-orbit G22 curve
over the prefix-affine and three wrong-orbit nulls by more than the frozen
pairwise physical guard?

This document freezes only the smallest one-shot executor needed to answer
that question. It adds no geometry, candidate, threshold, null, window or
physical claim.

## Exact binding

- source commit: `6ad6e1762e8ae7d3414f30777dd17c56190e8f7d`;
- source SHA-256: `1954a080d358191c9b19e36895ce0bf3edb9889d983a7e4ca3eca2c85625e5eb`;
- executor-manifest SHA-256: `3a70af31fa8a241087167794dc94a8acaaf661e4315c472e00650c5f94997823`;
- executor-seal SHA-256: `8ba4a2ad060e7c607d5110087d17947f62954a6afc25b8ca8a596680d82fb387`;
- plan-manifest SHA-256: `4bae4d9aa655579263de00e84b6d374a8263b8196122ef024bd39ccfdd804756`;
- prediction SHA-256: `f88b7a9185203fea00a4587335b2018172c5a894409bb5cb13d481d3e9996c0c`;
- prediction-seal SHA-256: `f8585632bc5f5ea6f3f94441fae35d58b53ab181bcbeeda32c3daf8747e07793`;
- qualified header-transform SHA-256: `7f106a5486ddd05cad12e034b4b7a14c87fc97ad77e77f73f660755c344d09bf`.

The executable seal records two prior descriptive HEAD requests and zero
observation headers, payload bytes or values. The complete-file SHA-256 and
byte count for each primary artifact remain unknown until an authorized
execution.

## One-shot boundary

An execution requires both a separate authority token and the exact executor
seal hash. It performs one materialization attempt for each frozen locator,
hashes both complete compressed artifacts before decoding either, admits the
frozen receiver/header transform, and then evaluates only the frozen
coordinate and hypotheses. There is no retry, substitution, reserve, fallback
or outcome overwrite.

The executor writes one strict-JSON aggregate receipt. Compressed RINEX,
decoded RINEX and observation values remain in RAM only and are overwritten.
Materialization and description errors cannot become physical outcomes.

## Outcome semantics

- `MEASUREMENT_INVALID`: a predeclared measurement-admission clause failed;
- `NOT_DETECTABLE`: the prefix calibration residual exceeds the derived
  one-model envelope of `1771.1285336133258 m`;
- `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`: the orbital curve is best by strictly
  more than the frozen `3542.2570672266515 m` pairwise guard;
- a named frozen-null preferred outcome: that null is best by the same rule;
- `AMBIGUOUS`: no best curve clears the guard.

The seal itself grants no access authority. The frozen state is:

`PRIMARY_EXECUTOR_FROZEN_OBSERVATION_UNOPENED`

The stop condition remains a separate review before any primary GET, header
access or observation decode.
