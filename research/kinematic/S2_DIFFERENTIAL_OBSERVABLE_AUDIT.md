# S2 target/reference differential-observable audit

## Physical question

Can a same-station target-minus-reference observable close the six physical
terms that the aggregate DOY240 receipt could not transfer to a future target?

The audit is deliberately offline and target-free. It read only the authoritative
reference-to-target insufficiency receipt and the existing normalized
calibration-transfer study. It selected no target and accessed no observation,
navigation product, orbit, source or network.

## Frozen topology

The candidate topology retains four phase-capable fit roots (ALGO, BOGT, MKEA
and PIE1) and GOLD as a code-only heldout root. Its local calibration error is

```text
corrected target error = e_target - B K e_reference
```

where `K` is the frozen GLS reference-calibration gain. This is an error
coordinate, not a measured satellite range or a physical error budget.

Three epistemic states are kept separate:

- `OBSERVABLE`: a same-path witness could measure the component, but a future
  witness does not count as present evidence;
- `MODELED`: an outcome-independent model supplies an uncertainty family;
  zero is admitted here only for a proved transform invariant inside its exact
  declared subspace;
- `UNRESOLVED`: no current measurement or finite independent bound exists, so
  the component is not assigned zero.

## Algebraic result

On a normalized two-dimensional affine receiver-clock basis, the identical
reference/target mode cancels to a maximum numerical remainder of
`2.6506574712925612e-15`. Reference-only and target-only normalized modes retain
unit response with opposite and equal signs. These values establish the
operator's invariant and distinguish common from differential modes; they have
no physical amplitude or unit.

The ideal first-order ionosphere also cancels in a same-ray L1C/L2W
ionosphere-free combination, conditional on both frequencies and exact frozen
coefficients. This does not cancel neutral atmosphere, higher-order ionosphere,
inter-frequency hardware effects or target/reference ray differences.

## Failure attribution

| Original causal term | What the differential adds | Component still able to absorb a finite margin | Present state |
|---|---|---|---|
| Directional PCO/PCV | No general common-mode invariant | Direction-dependent target/reference antenna response | `UNRESOLVED` |
| Directional multipath | Same receiver does not imply the same arriving ray | Target-direction site response relative to reference rays | `UNRESOLVED` |
| Unflagged slips | LLI and geometry-free phase can become same-path witnesses | Slip below the predeclared witness sensitivity | `UNRESOLVED` |
| Future atmosphere | Ideal first-order dual-frequency ionosphere cancels | Neutral, higher-order and mapping mismatch | `UNRESOLVED` |
| Reference orbit/clock | The `-B K` transfer is explicit | Non-target product error and covariance through calibration/final fit | `UNRESOLVED` |
| Receiver coupling | Identical affine clock mode cancels | Satellite/frequency/channel/direction-dependent hardware and residual cross-covariance | `UNRESOLVED` |

The important distinction is therefore not merely between “available” and
“missing”. A component can be eliminated by an exact transformation, be
prospectively observable, or remain physically unbounded. Partial cancellation
does not close its parent term.

## Frozen outcome

The one execution at source commit
`1b7baa3ffae99f6167b2814cecc9b244e4acfdee` stopped:

`DIFFERENTIAL_OBSERVABLE_HAS_ABSORBING_UNRESOLVED_TERM`

The result is
`results/s2_differential_observable_audit_v1.json`, SHA-256
`47d74243631357d61cfb6a63be67e7635152d67d70242ccf442b64e929c1ceb0`.
All six parent terms remain unresolved, composition was not performed, the
total future-target envelope remains `null`, and S3 is not authorized.

## Consequence

Another aggregate reference-residual run cannot close this boundary. The next
useful physical work must either measure or independently bound the differential
components themselves. In order of causal leverage:

1. characterize non-target reference orbit/clock product uncertainty and
   propagate it through `-B K` and the final inverse fit;
2. define a target-side continuity witness with a frozen missed-slip boundary;
3. provide direction-resolved antenna/site and media envelopes;
4. characterize differential receiver hardware and reference-target cross
   covariance.

This ordering is a development recommendation, not a primary selection or a
new acquisition plan.
