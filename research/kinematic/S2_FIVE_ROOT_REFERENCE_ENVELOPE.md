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

The single execution terminated
`FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_QUALIFIED`. All five complete observation
products and the mixed-navigation product were materialized and hash-bound.
Between 736 and 949 G14 rows per station were removed by identity before numeric
conversion; thirteen G14 navigation blocks were removed before numerical
navigation parsing.

The frozen selection chose the first possible window, 00:00:00--00:05:00 GPST.
ALGO, PIE1 and GOLD use G04/G07/G08/G09; BOGT uses G02/G04/G08/G16; MKEA uses
G04/G06/G07/G09. This choice used only structure and non-target broadcast
elevation.

All roots passed every predeclared deterministic residual limit. The controlling
fit-root phase result is ALGO: 0.018669513 m/s maximum and 0.012776768 m/s RMS.
The other maximum phase residuals are 0.008685919 m/s at BOGT, 0.002090777 m/s
at MKEA and 0.003456786 m/s at PIE1. GOLD's code-only result is 7.560523 m
maximum and 1.877082 m RMS. The two-times conditional reference envelopes are
therefore:

- fit phase rate: 0.037339025 m/s;
- GOLD code: 15.121047 m.

Individual observations and residuals were not persisted. Their admitted grids
are represented only by SHA-256 hashes. The complete result is
`results/s2_five_root_reference_envelope_2026240_v1.json`, SHA-256
`3a0f2f0225feded686787484fcc3809062371a0a0358d6018b062e6c92e1dc2f`.

This is the first real numerical admission of the exact four-fit/one-heldout
path, but it remains conditional on one five-minute reference window. The total
future-target physical envelope remains `UNRESOLVED`; no target was selected,
no target orbit was accessed and S3 remains unauthorized.
