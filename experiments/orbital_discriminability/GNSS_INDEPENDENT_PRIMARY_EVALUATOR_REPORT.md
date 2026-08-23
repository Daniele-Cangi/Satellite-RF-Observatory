# KIRU–MAT1 primary evaluator seal

## Outcome

EVALUATOR_FROZEN_PRIMARY_BLOCKED

The deterministic evaluator for the already frozen KIRU00SWE–MAT100ITA
G20/G22 primary is now materialized and sealed. This work was entirely
offline and used synthetic RINEX fixtures only. Neither DOY 215 product was
opened, hashed, downloaded, decompressed or inspected.

This is not a new gate and it is not a measurement result.

## Seal

- source commit:
  770d255eae80a1929eb12102b166dc915fe43908;
- evaluator source SHA-256:
  a4070a975ab402d0640d4818bdf6001a0d0380034d3715af8ed227558e4bff8b;
- canonical runtime-manifest SHA-256:
  6f88aef8e2ccfd05e70aba947f38c94ac4f722bc7978a6dd8a0578af06beaa8d;
- evaluator seal SHA-256:
  b2e09192345db050d61ae843ba01095f50b1deef5f2d9603c9365634519d8807;
- prospective Markdown SHA-256:
  763fa4c5c2b5ea77faaedc75c753c360fd848294ab789a8868d1e91458b2c000.

The seal records hatanaka 2.8.1, ncompress 1.0.2 and numpy 2.3.3.
A future access authority must bind all five identities, the exact two
product names and a single-run flag. The prospective plan still does not
authorize that authority.

## Frozen measurement transform

The parser accepts only KIRU00SWE and MAT100ITA, the exact 380-record
30-second GPS grid, G20 and G22, and
C1C/L1C/S1C + C2W/L2W/S2W. It preserves fixed-width RINEX semantics,
including three-space continuation and the Hatanaka final 14-character value
case. A representation outside that frozen grammar is
PRIMARY_EVALUATION_ERROR; it is not physical rejection.

After finite-value, code/SNR-presence, zero-LLI and geometry-free
second-difference admission, the evaluator applies:

    L1C/L2W phase cycles
      -> exact wavelengths
      -> first-order ionosphere-free path
      -> (KIRU G20 - KIRU G22) - (MAT1 G20 - MAT1 G22)
      -> 60 s central derivative
      -> L1-equivalent hertz

There is no smoothing, interpolation, cycle-slip repair, free time phase or
suffix fit. Decompressed bytes, station arrays, observed features and all
hypothesis arrays are overwritten in finally blocks. Receipts accept only
finite standard JSON scalars.

## Frozen inference order

The broadcast curves H_G20, H_AFFINE and H_G14 are compiled on the
same grid. The nominal prefix-only constant and slope are fitted on 76
features. If its prefix residual exceeds 354.8594372656104 Hz peak-to-peak,
the outcome is NOT_DETECTABLE and no held-out scorer is called.

Only an admitted measurement reaches the 302-record suffix. Preference
requires the winner's residual peak-to-peak plus the strict
709.7188745312208 Hz guard to be less than both alternatives. Equality is
AMBIGUOUS.

## Failure boundaries

- ARTIFACT_MATERIALIZATION_FAILED occurs before decompression and carries no
  physical decision. Bounded resume of the same historical product remains
  possible at that stage.
- PRIMARY_EVALUATION_ERROR is a software or descriptive failure and cannot
  modify the physical decision.
- MEASUREMENT_INVALID is limited to frozen artifact/header/value,
  continuity, LLI and discontinuity clauses; detectability and held-out
  comparison remain NOT_EVALUATED.
- after the first decompression byte, every terminal outcome has zero retry
  and authorizes no alternate product, signal or window.

## Verification

The new synthetic suite contains 19 tests covering the exact grid, RINEX field
boundaries, missing same-path witnesses, descriptive versus epistemic failure,
LLI and geometry-free refusal, all three hypothesis preferences,
NOT_DETECTABLE short-circuiting, strict guard equality, deterministic
coordinate construction, strict JSON, seal/authority binding, premeasurement
materialization failure and RAM overwrite.

The full versioned offline suite passes when the separately sealed Cassini
kernel job is excluded. That job requires its exact external kernel root and
is intentionally not part of generic offline execution.

## Remaining blockers

Before primary analysis, all of the following remain required:

1. a separate explicit authority receipt bound to the prospective Markdown,
   source commit, source hash, seal hash and exact products;
2. complete quarantine materialization of both DOY 215 products;
3. exact byte-count and full SHA-256 receipts completed before decompression;
4. the already frozen exact-hash broadcast navigation artifact;
5. one output path that does not exist, followed by one zero-retry execution.

Until those conditions are separately authorized and satisfied, the correct
state remains EVALUATOR_FROZEN_PRIMARY_BLOCKED.
