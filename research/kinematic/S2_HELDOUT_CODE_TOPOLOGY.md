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
