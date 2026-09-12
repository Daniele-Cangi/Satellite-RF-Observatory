# S2 five-root reference residual envelope

## Physical question

Does the structurally qualified ALGO/BOGT/MKEA/PIE1 fit path plus GOLD
code-only held-out path deliver reference residuals within the already declared
S2 capability limits on one distinct real day?

This is not a position estimate. It measures whether real code, carrier-phase
increments, receiver clocks, reference broadcast states and the nominal neutral
delay model form a usable coordinate on the exact five roots.

## Frozen experiment

DOY240 (2026-08-28) is selected as the immediately preceding complete day to
the qualified DOY241 structural artifact. It was fixed without inspecting any
of its five products. There is one attempt, no retry, and no alternate date,
station, field or reference set.

G14 is an exclusion sentinel only, not a selected primary. Its observation rows
and navigation blocks are removed using identity text before any contained
number is converted. All other GPS identities are predeclared as non-target
reference candidates for this qualification.

The first common eleven-endpoint window is selected using only field presence,
blank-or-zero fit-root LLI and non-target broadcast elevation of at least 15
degrees. Four references per station are chosen lexicographically. Observation
magnitudes and residuals cannot affect the window or references.

At every root, dual-frequency C1C/C2W forms the first-order ionosphere-free code
coordinate. An affine receiver-clock offset/drift is fitted to reference codes.
For the four fit roots, dual-frequency L1C/L2W endpoint differences form the
ionosphere-free mean phase-path rate; declared static phase shifts cancel within
each same-satellite interval. GOLD never decodes phase values.

The deterministic limits are inherited unchanged from the hash-bound DOY253 S2
plan: 50 m maximum and 20 m RMS code residual, 30 m alternating-reference clock
difference, plus 0.05 m/s maximum and 0.02 m/s RMS phase-rate residual on fit
roots. They are capability requirements, not calibrated probabilities. If every
root passes, the receipt reports two-times empirical reference envelopes.

Only hashes, selected reference identities and aggregate metrics persist.
Individual observations, residuals, RINEX payloads and navigation payloads do
not persist.

## Claim boundary

Even a pass does not create a total future-target envelope. Direction-specific
antenna phase-center variation, multipath, unflagged slips, future atmosphere,
broadcast-reference error transfer and reference/target correlations remain
`UNRESOLVED`. The run cannot select a target, authorize a primary or authorize
S3.

The one execution terminates with exactly one of:

- `FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_QUALIFIED`
- `FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_NOT_SUPPORTED`
- `FIVE_ROOT_REFERENCE_ENVELOPE_EXECUTION_INVALID`

## Outcome

Not executed. Plan and implementation must first be committed with a clean
working tree.
