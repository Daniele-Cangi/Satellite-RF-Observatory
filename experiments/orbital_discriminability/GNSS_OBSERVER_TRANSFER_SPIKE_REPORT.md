# GNSS observer-transfer mechanism spike

## Outcome

```text
OBSERVER_TRANSFER_MECHANISM_DISCRIMINATIVE
```

This is a synthetic, offline mechanism result. It does not select an observer,
station, date, signal, locator or observation artifact. It authorizes no
measurement and makes no new claim about the already consumed GOLD/NLIB or
ALGO/MDO products.

## Frozen authority

The compiler accepts only the two closed aggregate GOLD/NLIB receipts:

| Role | Outcome | Canonical SHA-256 |
|---|---|---|
| DOY 220 primary | `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` | `66adf39fa1b10cbf43bdb712ebf4d1f3d8f598203caaa8fa2a41601fea511f9d` |
| DOY 219 repeated pass | `ORBITAL_MODEL_REPEATED_PASS_PREFERRED` | `629865857ccc3b17c54db14aefee60fe26eaf9b0c5ded7525c07bcdba30399da` |

Their observation values are not reopened or rescored. The synthetic observer
is explicitly `SYNTHETIC_C_NO_CAPABILITY_ROLE`.

The frozen receipt is
[`GNSS_OBSERVER_TRANSFER_SPIKE_RECEIPT.json`](GNSS_OBSERVER_TRANSFER_SPIKE_RECEIPT.json):

- byte count: `12,010`;
- SHA-256: `e60e130e051626ebbae02aa655ade26071fd1dddd7f79a4f7ff131d476d3f4c5`;
- source commit: `2c1464f586d0db1e12e39c0be72e4b75505d6d2e`;
- source SHA-256: `c07ec3c904f9874fcb2dca73b334753f7efd4029d850be9ae9796a4a57591dca`;
- manifest SHA-256: `62b029855f2a52d258223e70d77d2ae7da55306f5fea559d67a65d8115f423da`.

## Mechanism under test

The test asks whether a target-minus-reference ionosphere-free phase
coordinate at one unseen observer can retain a frozen orbital distinction
without reproducing a complete two-station measurement:

```text
Q_C(t) = IF_phase(C,target,t) - IF_phase(C,reference,t)
Q'_C(t) = Q_C(t) - Q_C(t_0)
```

The sample-zero anchor removes one constant integer ambiguity only. There is
no receiver-rate parameter, free time phase, suffix fit, interpolation or
post-hoc anchor. A common receiver-clock curve containing constant, rate and
non-affine components cancels exactly in the simultaneous satellite
difference; signal-specific hardware does not cancel.

The deterministic fixture contains 139 epochs at 30 s cadence: 79 witness
prefix epochs and 60 untouched confirmation epochs. All target, reference and
wrong-orbit trajectories remain above `62.823 deg`, against a frozen `15 deg`
guard.

## Held-out discriminability

Every family receives the identical grid and anchor operator.

| Frozen alternative | Held-out separation, peak-to-peak |
|---|---:|
| adversarial zero-intercept affine null | `1,703.225 m` |
| wrong orbit 1 | `9,638.439 m` |
| wrong orbit 2 | `15,321.807 m` |

The controlling affine rate is derived from the target prediction alone before
any observer-C value exists. It is not fitted to the synthetic observation.

The one-model physical envelope is `143.442 m`; the conservative pairwise
comparison envelope is `286.883 m`. The remaining synthetic margin is
`1,416.342 m`. The largest contribution is the direct trajectory envelope for
a common event-time error of `+/-15 s`: `109.269 m` one-model and `218.538 m`
pairwise. This uses the trajectories at `t +/- delta_t`, not a local slope
approximation.

The signal-specific multipath/hardware term remains
`REQUIRES_PREDECLARED_C_PREFIX_ADMISSION`. A future C witness prefix may apply
that already declared admission rule, but may not fit or select an orbit. The
bound is not inherited from observers A/B and an unresolved term is never set
to zero.

## Anti-confirmation stress

A physically different synthetic orbit, rather than the nominal target, is
also used as truth. With the same fixed anchor and zero observation-derived
nuisance parameters, the scorer selects `WRONG_ORBIT_1`; the nominal target
retains a `9,638.439 m` residual. The mechanism therefore does not prefer the
target automatically.

## Interpretation and stop boundary

The spike establishes that the one-new-observer topology can preserve a
falsifiable orbital-versus-affine distinction for at least one high-elevation
GNSS-like geometry under the complete inherited interval ledger. It does not
establish that a real Internet artifact can meet the timing, phase-continuity,
signal-identity, same-path-witness and hardware-admission requirements.

The next permissible step, after review, is bounded orbit-only ranking of an
explicit observer set against this exact coordinate and envelope. Artifact
discovery may begin only after one observer geometry passes. No primary or
measurement is frozen by this report.
