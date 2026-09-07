# DRAO DOY232 model-blind qualification executor

**DRAO_DOY232_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED**

This bounded implementation materializes the already frozen DRAO capability
question. It is not a new gate, a general GNSS adapter or an orbital
experiment. It has not opened or decoded the DOY232 RINEX artifact, and DOY233
remains unselected, unfrozen and unauthorized.

```text
Physical question:
Can the exact DRAO DOY232 artifact preserve the six-track phase coordinate and
close the predeclared capability reserve without receiving an orbital model?

New information if separately executed:
Whether the DRAO measurement path can make a later negative DOY233 result
interpretable.

Why the existing receipts cannot answer it:
They bind artifact identity but contain no RINEX header, structural coverage,
phase continuity or same-path witness evidence.

Minimum experiment:
One model-blind in-RAM qualification of the exact DOY232 artifact.

Stop condition:
One typed qualification outcome, complete cleanup and DOY233 still untouched.
```

## Frozen artifact and authority

- product: `DRAO00CAN_R_20262320000_01D_30S_MO.crx.gz`;
- complete byte count: `2,904,457`;
- complete SHA-256:
  `fca688310e9bd48a70452e0f9409a24d4b036add44ee31024ca1d76e130fe8d3`;
- source commit: `d227f19335a7237f6f2e7176c9a5a34f8ddaeea1`;
- canonical source SHA-256:
  `737c1e9f5fb09994970c2b86e28262219bb959155f3aaa5b4b8d55c30a28fa25`;
- executor manifest SHA-256:
  `2156fdf81b88498276f51a8903260df58c1249d56835ba02df19414f8b1041cf`;
- seal SHA-256:
  `9f021dcf9da8961eef114b423950d064035eb8df69ec346225dcf9fa82bb6a5e`.

The source/manifest values above are copied from the seal and are checked by
tests; they must not be edited manually. The seal grants no live authority. A
separate one-use token is required and is consumed before any network request.

## Exact transform ledger

The RINEX 3.04 semantics are frozen before header exposure:

1. `SYS / SCALE FACTOR`: divide a stored observation by the declared scale
   factor; absence means specification-defined unity.
2. `SYS / PHASE SHIFT`: the RINEX observation already equals the original
   phase plus the declared correction. The executor requires explicit L1C/L2W
   coverage for every selected satellite and never applies that shift a
   second time.
3. `RCV CLOCK OFFS APPL = 0`: when an epoch receiver-clock value is present,
   apply `t=t_r-dt`, `C=C_r-dt*c` and `L=L_r-dt*f`. When the header says the
   correction was applied, do not apply it again.
4. Mapping an epoch to the frozen grid does not reduce the already frozen
   `[-15 s,+15 s]` event-time envelope.
5. TGD is never applied to carrier phase.

The semantics source is the official
[RINEX 3.04 specification](https://files.igs.org/pub/data/format/rinex304.pdf).
An unsupported or conflicting declared transform is a typed topology refusal;
a software description failure remains `QUALIFICATION_DESCRIPTION_ERROR` and
does not become physical evidence.

## Model-blind qualification

The executor retains the frozen 139 epochs, six satellites and four required
observables. It scans every structural cell and emits exactly 5,004 rows with
no observation scalar. Observation values and derived arrays exist only in
RAM and are erased after evaluation.

The physical checks are unchanged:

- 100 percent L1C/L2W and C1C/C2W coverage;
- zero/blank LLI only;
- geometry-free phase second difference no greater than
  `0.09514683639918244 m`;
- six-track common-mode centering;
- per-track constant-plus-rate fit on the first 79 epochs only;
- no held-out refit;
- at most `1,250 m` held-out phase-code witness peak-to-peak per track.

The executable contains no orbit, navigation, assignment, null or score
input. It cannot locate or access DOY233.

## Verification and boundary

The new synthetic suite covers scaling, phase shift, receiver-clock
correction, exact grid mapping, full six-track admission, blank/omitted fields,
LLI, geometry-free discontinuity, physical-witness rejection, strict JSON,
zero observation-value persistence and pre-network authority refusal. The
complete bounded DRAO regression set passes `70` tests. The generic suite was
started but intentionally stopped after 22 percent because the known Windows
filesystem bottleneck made it disproportionate; no failure had occurred.

The only next action after review is one separately authorized DOY232
qualification. It may return one of the six already frozen outcomes. It must
stop after that outcome and cannot select, inspect or score a DOY233 product.
