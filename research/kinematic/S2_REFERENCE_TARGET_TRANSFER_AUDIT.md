# S2 reference-to-target causal transfer audit

## Physical question

Can the frozen aggregate DOY240 reference receipt, by itself, provide every
physical contribution needed to form a total envelope for a later target?

This audit is deliberately narrower than a new qualification. It reads one
hash-bound JSON receipt and no source artifact. It does not select a target,
access an orbit, decode an observation, introduce a correction product or
assign a numerical value to missing physics.

## Frozen evidence

The only input is
`results/s2_five_root_reference_envelope_2026240_v1.json`, SHA-256
`3a0f2f0225feded686787484fcc3809062371a0a0358d6018b062e6c92e1dc2f`.
It retains the qualified conditional reference envelopes:

- fit-root phase rate: `0.037339025487426625 m/s`;
- GOLD reference code: `15.121046550571918 m`.

These quantities describe different coordinates. They are retained unchanged
and are not added. Neither is a population-coverage statement or a future
target-direction bound.

## Causal attribution

| Term | What the receipt establishes | Missing transfer quantity | Result |
|---|---|---|---|
| Antenna PCO/PCV | Receiver identity and aggregate reference residuals | Direction-resolved calibrated response, target line of sight and correction uncertainty | `NOT_IDENTIFIABLE_FROM_RECEIPT` |
| Multipath | Four reference directions per root passed aggregate limits | Direction/time-resolved site response and target-geometry coverage | `NOT_IDENTIFIABLE_FROM_RECEIPT` |
| Unflagged cycle slips | Selected reference rows had blank/zero LLI and bounded aggregate phase residuals | Target continuity series, missed-slip sensitivity and mapping to the inverse observable | `NOT_IDENTIFIABLE_FROM_RECEIPT` |
| Future atmosphere | First-order ionosphere-free coordinate and nominal neutral delay were used on reference rays | Future target ray, neutral/higher-order residual uncertainty and temporal transfer | `NOT_IDENTIFIABLE_FROM_RECEIPT` |
| Broadcast reference orbit/clock | Target-free navigation hashes and residuals after affine clock fitting | Error decomposition, cross-satellite covariance and inverse-model projection | `NOT_IDENTIFIABLE_FROM_RECEIPT` |
| Reference/target receiver correlation | Reference-only aggregate residuals; target rows were textually removed | Joint coordinate, shared/differential covariance and target transform convention | `NOT_IDENTIFIABLE_FROM_RECEIPT` |

For each row, the available evidence is `DIAGNOSTIC_ONLY`: it says something
about the observed reference path but supplies no justified transfer rule to a
future target. `UNRESOLVED` therefore never becomes zero.

## Outcome

The one offline execution terminated:

`FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT`

The receipt integrity and conditional reference-path clauses are satisfied.
Directional transfer, temporal transfer, reference/target covariance and the
total future-target physical envelope remain `UNRESOLVED`. No composition was
performed and the total bound is represented as `null`, not as an arbitrary
number.

The first result artifact,
`results/s2_reference_target_transfer_audit_v1.json`, is retained unchanged but
its execution-integrity claim is superseded: post-merge review found incomplete
whole-plan validation, an optional programmatic freeze path, insufficient
object/byte coupling and incomplete finite-number parsing.

The first repaired artifact is
`results/s2_reference_target_transfer_audit_v2.json`, SHA-256
`9a4e2c859a9eb1e096f62f8cf09accc6743ab91a76428f6d684c85419673142b`.
It reproduced the same causal outcome after binding the complete plan, requiring
source commit `4993d37aaeb20a24390acc682f04730ebc1a865a`, loading the receipt only from
its verified path and rejecting every non-finite JSON number. Its frozen audit
implementation SHA-256 is
`83a0a9511afe6878c2ff9c244874517c4ee6d189f65fff2bf7c5daf59bfefeca`.

A second completed review found that v2 still hashed and parsed the receipt in
separate reads, and that its commit-provenance tests were incompatible with
shallow CI and checked one implementation against the working tree. Preserve
v2 unchanged as superseded evidence.

The authoritative artifact is now
`results/s2_reference_target_transfer_audit_v3.json`, SHA-256
`e209a9d00b70e360be6ba1330574a830ca331a5e2b3690c33d8b53c96f04170b`.
It hashes and parses each frozen buffer from one read, binds source commit
`fc20392d44922c0d5e4daa917012b1f3c85801dc`, and resolves the implementation
at that commit under full-history CI. Its implementation SHA-256 is
`ce9f9813b4b05ecbe840818f08ef20e36600e9d6a67d285a6e77ecf806df6965`.
It reproduces the same causal outcome without source, target or orbit access.

## Consequence

DOY240 remains a real admission of the reference coordinate. It cannot alone
authorize a primary or S3. The smallest new evidence must be declared in the
future target coordinate: direction-resolved antenna/site response, target-side
continuity detectability, future-path atmosphere uncertainty, reference-state
covariance projected through calibration, and a shared/differential
reference-target receiver model. Which subset is required depends on the exact
observable and claim chosen before target measurement access.
