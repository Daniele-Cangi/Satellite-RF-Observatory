# DRAO labelled-forward DOY238 integrated plan

**DRAO_DOY238_INTEGRATED_PLAN_FROZEN_ARTIFACT_UNSELECTED**

This is one prospective forward experiment, not a new gate. The prediction and
all decisions are frozen before selecting an observation artifact.

## Physical question

Do the six predeclared DRAO phase paths predict the untouched held-out suffix
better than a prefix-affine null and time-reversed geometry?

## Geometry and detectability

- observer: `DRAO00CAN` / DOMES `40105M002`;
- window: `2026-08-26 04:50:00--05:59:00 GPS`;
- prefix/held-out: `79/60` epochs;
- codebook: `G14/G15/G17/G20/G24/G30`;
- controlling separation: `36418.373424 m`;
- one-model bound `B`: `3971.647489 m`;
- required `3B`: `11914.942466 m`;
- remaining physical margin: `24503.430958 m`.

## Single integrated boundary

The future executor must perform identity, topology, a typed RINEX transform
ledger and model-blind phase/code witnesses before releasing the frozen model
bundle to the scorer. `MARKER NAME` is retained descriptively but never tested
as a literal alias. Scale-factor absence, phase-shift absence, malformed
records and incomplete coverage remain distinct states.

Extra GPS tracks are descriptive. Missing or invalid G14/G15/G17/G20/G24/G30
is fatal. There is no interpolation, gap bridging, held-out refit, free time
phase or post-hash retry.

## Claim boundary

A positive result can support only `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` for
receiver-labelled, model-conditioned tracks. It cannot establish independent
satellite identity, a distributed anomaly or orbit determination.

No DRAO DOY238 observation artifact has been queried or selected. Stop before
every observation locator, header, payload byte, value or score.
