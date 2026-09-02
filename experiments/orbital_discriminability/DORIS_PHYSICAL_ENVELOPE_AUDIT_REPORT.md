# DORIS PAUB–RIMC physical-envelope audit

Outcome: **`DORIS_PHYSICAL_ENVELOPE_BOUND_UNAVAILABLE`**

This bounded audit does not open an orbit product, a DORIS observation
product, an observation value, or the candidate day. It tests whether the
already qualified exact-coepoch topology is sufficient to define a finite
premeasurement physical envelope. It is not a new gate.

## Physical question and stop

**Physical question:** can every term that survives the exact-coepoch
PAUB-minus-RIMC ionosphere-free quotient be bounded independently of the
target RF values below the frozen orbital-versus-null screening separation?

**New information:** the audit separates exact cancellations, model forms,
descriptive engineering scales and finite uncertainty bounds. It also exposes
that the qualified development topology and the prospective orbital screen do
not share a date or sample grid.

**Why the earlier work could not answer it:** the 128 coepoch records prove a
receiver-side causal topology. They do not quantify transmitter clocks,
propagation, antenna phase, event time or channel-noncommon transformations.

**Stop:** the combined envelope is unavailable, so remaining physical margin,
detector resolution and negative-result interpretability are undefined. No
phase value or candidate product is authorized.

## Frozen evidence boundary

The audit verifies four immutable receipts before evaluation:

| Role | Receipt SHA-256 |
|---|---|
| orbit-only geometry | `1807784b8330a27942b5c2b6136e652720181dd6cd5d814b6ec129f58b450985` |
| development header | `afa1ebf9a3abf926e2b7cecbe4096939e2e86d0c889f453f9ff238ed27355fe6` |
| observable-role audit | `ed6e2e6c00b5b74a02559c2d60dde29069d1d2f529ad2306f463c6264f6cc5c3` |
| exact-coepoch topology | `307fd8dba440b0086a726e704e49aca5c84637102f522251f8e3b4ff897a6000` |

The audit manifest SHA-256 is
`6697bda1fc33f45575c21588264f5f7ebc2879bf2bc27244073fe42c1bfee3ac`.
The frozen source commit is `42d7fe402926eb66064868b888b37f88ea04c139` and
its LF-normalized SHA-256 is
`3d76b59070e7b38dd64a2e9b5773272fd32fdcf25455bdcc8db25b4d9abb1fac`.

## What cancels and what does not

For the exact common receiver epoch and the exact rational L1/L2 phase
combination:

- first-order ionosphere cancels exactly;
- shared receiver clock cancels exactly;
- shared receiver proper time cancels exactly;
- both beacon frequency-shift factors are observed metadata equal to zero;
- only a calibration-prefix constant and affine aging term may be projected;
  there is no held-out refit and no free time phase.

These cancellations are algebraic properties of the coordinate. They are not
claims that every receiver, transmitter or path effect is common.

The physical phase equation and the distinction between receiver/transmitter
proper time, clocks and propagation follow the IDS/CNES
[DORIS models and solutions](https://ids-doris.org/documents/BC/data/DORIS_models%26solutions_v1.0.pdf).
That document also says that standard DORIS processing adjusts beacon
frequency or frequency-and-drift per pass and that oscillator imperfections
are the dominant hardware error family. This is exactly why an uncharacterized
non-affine transmitter term cannot be set to zero.

## The cross-date boundary

The development evidence is:

- date: 2026-08-30;
- DOR interval: 19:12:45.229949–19:23:18.229949;
- 128 exact-coepoch L1/L2 records over 633 s;
- claim: capability topology only.

The prospective geometry evidence is instead:

- date: 2026-09-02;
- 18,147.766489 Hz controlling affine separation;
- 2.966990 Hz prior-forecast non-affine envelope;
- 18,144.799500 Hz preliminary geometry margin;
- claim: orbit-only screening ceiling.

The two results are deliberately not joined into one numerical measurement
margin. The 633 s development chain shows that this receiver/product family
can produce the required topology; it does not prove candidate-day coverage,
the candidate-day exact grid or the transfer of any nuisance bound.

## Physical-term attribution

The epistemic rule is strict but non-probabilistic:

- `OBSERVABLE` means an independent coordinate measures the term;
- `MODELED` requires both a predeclared central model and an applicable
  uncertainty family;
- `UNRESOLVED` means one of those is absent.

A model equation without its uncertainty is not promoted to `MODELED`.

| Surviving family | What is known | Missing finite input | Class |
|---|---|---|---|
| absolute DOR → coordinate time | the receiver is described as synchronized to *around* 10 μs | a numerical event-time bound and direct `t ± Δt` trajectory envelope | `UNRESOLVED` |
| higher-order ionosphere | first-order `1/f²` is exactly cancelled | path-specific higher-order family using electron content and magnetic field | `UNRESOLVED` |
| differential troposphere | the physical model form is known | exact sites/heights, both slant models and residual intervals | `UNRESOLVED` |
| station/space antenna phase | the header declares the spacecraft PCO vector | exact DPOD coordinates and applicable ground/space PCO/PCV plus attitude lineage | `UNRESOLVED` |
| phase wind-up | it belongs in the phase model | attitude, antenna orientation and one frozen convention | `UNRESOLVED` |
| Shapiro and one-way relativity | ground bias/rate can share the affine nuisance | exact light-time/Earth-rotation model and non-affine remainder interval | `UNRESOLVED` |
| non-affine beacon USOs | system-level stability scales exist | PAUB/RIMC session-applicable interval and prefix-to-suffix rule | `UNRESOLVED` |
| channel switch / noncommon bias | exact epoch and LLI continuity are proven | processing-unit assignment and product-specific noncommon phase bound | `UNRESOLVED` |

The IDS overview describes synchronization to
[around 10 μs](https://ids-doris.org/documents/BC/WhatIsDORIS.pdf), not a
hard ADC/phase-to-coordinate-time interval. The current Sentinel-3 phase-center
review likewise shows that PCO depends on mission calibration lineage and
manufacturer reference-frame interpretation
([IDS 2026 PCO review](https://ids-doris.org/resources/presentations/ids-meetings/i03-2026-4618.html)).

## Quantities that must not become bounds

The published 0.3 mm/s DORIS performance scale corresponds to
`0.002037659667 Hz` at 2.03625 GHz for one link, or
`0.004075319333 Hz` under a symmetric two-link sum. The phase model describes
intrinsic noise as a few millimetres. Both numbers are useful plausibility
checks; neither is a product-specific deterministic envelope for all surviving
terms.

Therefore the audit does **not** subtract them from 18,144.799500 Hz. It also
does not replace missing values with broad invented constants merely because
the geometry screen is large.

## Decision

Every required open family lacks a finite, outcome-independent held-out bound.
The conservative Minkowski sum is consequently unavailable:

```text
combined physical envelope      = unavailable
remaining physical margin       = unknown
maximum detector resolution     = undefined
negative result interpretable   = false
candidate-day access            = not authorized
```

This is not evidence against the Sentinel-3A orbit, against PAUB/RIMC signal
presence, or against DORIS measurement quality. It is a refusal to call an
orbit-only ceiling a measurement margin.

## Smallest next physical choice

The simple two-beacon coordinate should not advance directly to candidate
phase values. A later review has two scientifically distinct options:

1. close all eight intervals outcome-independently on one exact prospective
   grid, including direct time envelopes and channel/USO applicability; or
2. change the observable topology so transmitter-clock and receiver-noncommon
   curvature are measured or cancelled, then recompute orbital-versus-null
   discriminability before any primary access.

The second option is likely the smaller scientific move. The key issue is not
finding another RINEX file: it is adding an independent clock/channel witness
without turning the work into a multi-day full-POD system or weakening the
affine null.

## SHOCK

The shared spaceborne receiver was genuinely useful: it cancelled receiver
clock and proper-time terms exactly. But the independent ground transmitters
that create the desired distributed geometry also introduce independent USO
curvature. Root independence is therefore both the source of information and
a new nuisance path. Topology qualification alone cannot decide whether that
path carries orbit information or transmitter behavior.
