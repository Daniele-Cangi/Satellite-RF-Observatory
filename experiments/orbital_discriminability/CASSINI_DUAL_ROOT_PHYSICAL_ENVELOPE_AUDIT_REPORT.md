# Cassini 2005 dual-root physical-envelope closure

Date: 2026-08-22

Outcome: **`CASSINI_DUAL_ROOT_2005_CLOSED_WITHOUT_IQ`**

The four-stream X/Ka coordinate and its nulls remain frozen. This bounded
offline audit evaluated the outcome-independent central physical models already
available on the exact common-transmit grid. It found no defensible complete
uncertainty envelope, so the 2005 vertical closes before detector or IQ access.

## Physical question and information value

**Physical question:** can every nondispersive and receiver-hardware family be
bounded below the frozen Cassini-versus-Saturn-center separation, so that a
negative four-stream result would be interpretable?

**New information:** receiver proper-time/gravity is now explicitly present on
the exact grid; the static relativistic path and applicable media corrections
are quantified; the narrow digital-control continuity is distinguished from
the unbounded end-to-end receiver path.

The satellite hypothesis itself was not tested. No RF observation exists.

## Frozen authority and access boundary

- parent receipt SHA-256:
  `942549a05d37d0926af9a5d65b7891c4c998134a9eb2254c28406982134ec1f8`;
- audit manifest SHA-256:
  `6950e6d1f5c6c219bcdbf989b4c33c4dee32da2dba0d509942517a24a2f6a77c`;
- exact grid: 5,279 one-second common-transmit records;
- calibration prefix / held-out suffix: 1,056 / 4,223 records;
- controlling orbital-versus-Saturn-center separation:
  `0.2995923735627999 Hz p-p`;
- four-stream direct-trajectory timing envelope:
  `0.0000204165223073319 Hz`;
- header access: none;
- IQ/sample/amplitude access: `0 bytes`;
- detector: not implemented.

The exact same prefix affine projection and Saturn-center null were retained.
There was no suffix refit, free time phase, threshold change or null change.

## Exact-grid diagnostics

All values below are evaluated after the frozen calibration-prefix affine
projection. A central or partial value is not an uncertainty bound.

| Physical family | Epistemic state | Held-out non-affine p-p | RMS | Effect on envelope |
|---|---|---:|---:|---|
| receiver proper-time/gravity | modeled central, uncertainty unresolved | `0.0827438002 Hz` | `0.0389961624 Hz` | none |
| static relativistic path | modeled central, remainder unresolved | `0.0000366099 Hz` | `0.0000170679 Hz` | none |
| C10/C60 TRO corrections | partial model | `0.0005488244 Hz` | `0.0002185597 Hz` | none |
| C10/C60 X-band ION diagnostic | first-order structurally cancellable, RF not evaluated | `0.0001857861 Hz` | `0.0000793807 Hz` | none |
| interplanetary plasma | first-order structurally cancellable, higher order unresolved | - | - | none |
| receiver/station hardware | unresolved | - | - | none |
| available media products | partial non-additive control | - | - | none |

The proper-time/gravity central structure is about 27.6% of the controlling
geometric separation. This is important but it is not a `0.0827 Hz` error bar.
The missing quantity is the uncertainty of the predeclared model family.

The weighted maximum adjacent NCO-transform boundary residual is
`0.00000833897 Hz`. It describes digital metadata continuity only. It cannot
bound oscillator/reference curvature, cables, analog paths, cross-band delay,
unknown FIR phase/group delay or station-to-station hardware differences.

## Non-probabilistic causal envelope

The audit retains four distinct states:

- `OBSERVABLE`: measured through the admitted coordinate;
- `MODELED`: a predeclared physical central model exists;
- `BOUNDED`: a finite outcome-independent uncertainty family exists;
- `UNRESOLVED`: no such measurement or bound exists.

No probability was invented and no root-sum-square was used. If every family
were bounded, correlated intervals would combine by a conservative Minkowski
sum. Here none of the seven full families is admitted as bounded. Therefore:

- combined open-term envelope: **unavailable**;
- remaining physical margin: **unknown**;
- maximum admissible detector resolution: **undefined**;
- optimistic zero-open-term ceiling: `0.0998573190 Hz`, explicitly not an
  admission requirement.

## Failure attribution

**Block:** product-specific end-to-end receiver hardware and complete
nondispersive residual families have no outcome-independent finite bound.

**What did not fail:** the exact common-transmit coordinate, joint visibility,
the first-order X/Ka cancellation algebra, the frozen orbital/null separation,
and the timing envelope all remain valid.

**What was not tested:** measurement capacity, model-blind feature extraction,
RF agreement, orbital preference and the physical Cassini hypothesis.

The negative closure therefore concerns the bridge from modeled prediction to
an interpretable measurement, not evidence against Cassini's orbit.

## Stop and change of abstraction

The 2005 DSS-25/DSS-55 vertical is closed without IQ. Repeating a broader
documentation search or implementing a finer detector would not repair the
open causal cut. The next physical route should be selected only if its
instrument configuration supplies outcome-independent hardware and
nondispersive controls, or if its observable cancels them structurally while
retaining orbital-versus-null discriminability.

No new gate was created.
