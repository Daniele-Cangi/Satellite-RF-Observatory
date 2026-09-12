# S2 code-only held-out topology

This bounded offline audit asks whether one of the three already known terrestrial
roots can close the missing excluded-receiver topology without requiring its
carrier phase. It does not reopen DRAO, STJO or YELL, infer why their phase-header
audit failed, access a new artifact, select a target/date or use a target orbit.

The five phase-capable roots remain the fit set. DRAO, STJO and YELL are compared
only through copied terrestrial coordinates over the exact 181 target-free
synthetic cases retained by the previous feasibility result. The comparison
requires held-out visibility at +30 and +60 seconds and transports the frozen
fit covariance and persistent fit-root code/rate bias box into an absolute
code prediction.

For each endpoint the audit computes:

```text
100 m absolute held-out criterion
  - conditional two-sided 95% Gaussian prediction half-width
  - fit-root affine systematic box
  = maximum remaining physical affine slack
```

The slack is not evidence that receiver, atmosphere or timing errors are that
small. A negative slack rejects the geometry under the frozen conditional design;
a positive slack merely states the largest still-unresolved physical envelope
that a future code-coordinate qualification could occupy.

The code-only contract requires C1C and C2W at both frozen endpoints, the exact
ionosphere-free code transform, header scale/applied-correction/clock semantics,
full temporal coverage and a non-target receiver-clock calibration. It explicitly
does not require L1C/L2W phase transforms, LLI or signal-strength fields.

This audit cannot authorize S3. The previous five-root fit margin is not uniform,
the candidate code coordinate remains unaccessed and every physical envelope
term marked `UNRESOLVED` must remain nonzero until independently bounded.

## Frozen result

The source was frozen at commit `e57e4634f4ca9f755b90690ba52040c512397585`
before the calculation. The result is
`HELDOUT_CODE_TOPOLOGY_CONDITIONALLY_AVAILABLE`, with this ground-only ranking:

| Candidate | Visible predecessor cases | Positive slack at both endpoints | Median slack over endpoints | Slack range |
|---|---:|---:|---:|---:|
| DRAO00CAN | 181/181 | 180 | 12.530 m | −1.363–19.735 m |
| YELL00CAN | 173/181 | 40 | −7.009 m | −69.912–17.505 m |
| STJO00CAN | 154/181 | 32 | −21.911 m | −83.259–15.633 m |

DRAO is the only plausible next qualification candidate, but is not admitted.
Its conditional Gaussian half-width is about 40.4–41.6 m and the transported
fit-root affine box is about 39.6–60.3 m. Together they consume nearly all of
the frozen 100 m held-out criterion before any unqualified DRAO clock, multipath,
troposphere, higher-order ionosphere, time-tag or model-truncation contribution.

The sole DRAO-negative case is not a low-elevation failure. At 20,000 km,
direction 14, tangent-1 4 km/s, DRAO elevation is 81.275 degrees; at +60 s its
41.072 m Gaussian and 60.291 m affine terms already total 101.363 m. High
visibility therefore does not imply an independent predictive direction: the
held-out line of sight can still align with a weak/bias-sensitive fit mode.

Because no target orbit may select one of the favorable cases, a future plan
would need an outcome-independent physical bound and a predeclared rule evaluated
after the five-root fit but before opening DRAO target values. Every attempted
event, including those stopped for insufficient prospective slack, must remain
in the denominator. This is selection on fit-side information, not an orbit
lookup or a held-out residual fit.

The plan SHA-256 is
`2c4f01292ffd036090b641f1adb31b86a62eca817c6aa8703fe0a4a2d61fca57`.
The result SHA-256 is
`d70bd0d8f81217fb2cb1fd4899d18b14d035a86113a72798fc5a7f7224f4cafa`.
No candidate artifact, target value, orbit or navigation product was accessed.

The smallest next physical step is one distinct, bounded, header/structure-only
DRAO code-coordinate qualification. It must stop on any unresolved C1C/C2W
scale, applied correction, timing or coverage clause. Passing it would still
leave a separate non-target, reference-only error-envelope qualification before
any primary target can be frozen.
