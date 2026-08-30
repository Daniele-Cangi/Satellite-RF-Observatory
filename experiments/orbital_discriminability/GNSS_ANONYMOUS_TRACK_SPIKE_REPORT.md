# Anonymous-track and sealed-code-witness mechanism spike

## Outcome

```text
ANONYMOUS_TRACK_SEALED_WITNESS_MECHANISM_DISCRIMINATIVE
```

This is a synthetic interface-mechanism result. It uses the already frozen
blind-orbit prediction bundle as a closed development fixture and accesses no
AMC observation value, product, header or locator. It does not admit a real
raw-GNSS capability or authorize acquisition.

## Physical question

Can orbital dynamics rank an anonymous simultaneous track pair while the
code-derived identity remains outside the scorer, then expose agreement or
disagreement only after the orbital score receipt is immutable?

The spike implements exactly two information branches:

```text
synthetic same-clock tracks A and B
    -> A-B orbital scorer
    -> opaque score receipt
    -> score receipt SHA-256

separate synthetic code witness
    -> witness SHA-256 before scoring
    -> unavailable to orbital scorer

after score hash exists
    -> reveal orbital mapping and code witness
    -> CONCORDANT / DISCORDANT / UNRESOLVED
```

The scorer source contains no PRN token, mapping seal, orbital compiler,
decoder or network client. It accepts only two 139-point tracks, eleven opaque
curves and one pairwise guard.

## Frozen synthetic surface

The six normal hypotheses are the five closed orbital candidates plus the
prefix-affine null. Each orbital candidate also receives one frozen
track-order-reversed curve, producing eleven opaque hypotheses in one scoring
loop. The affine curve is sign invariant and is not duplicated.

Every hypothesis receives exactly one prefix constant and one linear rate.
The untouched 60-epoch suffix is ordered by peak-to-peak residual, RMS and
opaque identifier. No held-out refit, free time phase, candidate-dependent
transform or post-result sign choice is allowed.

## Required controls

| Scenario | Orbital result | Post-hash witness result | Meaning |
| --- | --- | --- | --- |
| correct model | G22 relative to G30, `18,763.152833 m` margin | `ORBIT_CODE_CONCORDANT` | positive mechanism control |
| wrong-orbit truth | G06 relative to G30, `20,942.529492 m` margin | `ORBIT_CODE_CONCORDANT` | the scorer does not automatically choose G22 |
| code/orbit discordance | G22 relative to G30, `18,763.152833 m` margin | `ORBIT_CODE_DISCORDANT` | code identity cannot silently override orbital dynamics |
| reversed track order | G22 relative to G30, reversed orientation, `18,762.945166 m` margin | `ORBIT_CODE_CONCORDANT` | permutation is a frozen hypothesis, not a post-hoc sign flip |
| G22/affine midpoint | `AMBIGUOUS`, `0.207666 m` margin | `ORBIT_ASSIGNMENT_UNRESOLVED` | the frozen guard is not weakened to force a result |

Each opaque score receipt is hashed before its corresponding identity reveal
and contains zero code-identity token or track value.

## Detectability boundary

On the exact synthetic G22 fixture, before applying any real-capability
envelope, the controlling preference margin is:

```text
18,763.716564789 m
```

The closed historical development guard is `7,339.701234647 m`, leaving a
synthetic remainder of `11,424.015330141 m`. This number proves a non-empty
mechanism region; it is not transferred to an unknown raw receiver.

For a future capability, the complete conservative pairwise non-affine
envelope must remain strictly below the exact-fixture preference margin. No
calibrated probability is invented.

## Terms that remain open for real data

| Term | State |
| --- | --- |
| sample-zero event time and sample-rate accuracy | `OPEN_TERM` |
| common oscillator constant/rate | cancelled by A-B or prefix-projected in the synthetic topology |
| differential non-affine oscillator behavior | `OPEN_TERM` |
| ionosphere and other propagation structure | `OPEN_TERM` |
| cycle slip or mid-window ambiguity | `MEASUREMENT_INVALID_BEFORE_SCORE` |
| missing/non-finite track epoch | `MEASUREMENT_INVALID_BEFORE_SCORE` |
| track order | explicit frozen hypothesis family |

Consequently:

```text
real capability admission = NOT_EVALUATED_OPEN_TERMS
```

An unresolved term is not zero merely because the synthetic control passed.

## Evidence boundary

The code witness and orbital tracks share the same hypothetical samples and
front-end. They are orthogonal features, not independent hardware roots. The
mechanism can test whether code structure and orbital dynamics agree after
separate commitments; it cannot by itself claim hardware-independent
confirmation.

The spike also does not demonstrate that real below-noise GNSS carriers can be
tracked anonymously, that the required civilian dual-frequency signals exist,
or that a public artifact supplies defensible ADC-bound UTC. Those are
capability-admission questions, not quantities to infer from RINEX L1C/L2W.

## Immutable ledger

- spike source SHA-256:
  `7f4288f8c1283be62a06fab08de9fe57d58bcda94d17883d69a0ea30cd7e8d60`;
- pure scorer source SHA-256:
  `8722ebbf17f0be58c1d61e0383f3d9457124d7c812f63b22bb65b0bc937dec24`;
- frozen prediction bundle SHA-256:
  `a36aed59f32ee9b409778e44a0b661aebbf83c0675c58473c6655ad562c82ee2`;
- frozen mapping seal SHA-256:
  `b719a2bf17e66fcafa3597c4018d6acd039bdac4e33ecb173795646ff47245db`;
- synthetic receipt SHA-256:
  `a843d189f1bacfa361204035daa898ef3a257cc465b7d63ba28adf355117fa97`;
- observation access: zero network requests, locators, headers, payload bytes
  and values.

## Stop and next boundary

Stop before capability search or observation. After review, the maximum next
action is consideration of one explicitly bounded raw-GNSS capability set.
Such a review must retain `NO_CAPABILITY_AVAILABLE` and
`NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT` as valid terminals, demonstrate every
open term before sample access, and avoid both a receiver catalog and another
PRN-labelled RINEX replication.
