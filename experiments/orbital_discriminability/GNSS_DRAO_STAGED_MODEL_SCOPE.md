# DRAO staged model-side scope

This is a bounded change of abstraction after the closed DOY230/DOY231 DRAO
plan. It is not a new gate and it grants no observation-product access.

```text
Physical question:
Does the model-only part of the DRAO six-track common-mode envelope leave
enough of the frozen guard for a separately qualified, all-epoch measurement
witness?

New information produced:
The exact non-affine effects of a common +/-15 s event-time shift, broadcast
clock curvature and the DOY233 broadcast-orbit accuracy family on the same
six-track held-out coordinate.

Why the closed experiment cannot answer it:
Its receipt retained shifted visibility but destroyed the shifted range
curves, and it required product-dependent clauses before product selection.

Minimum experiment:
One exact-hash DOY233 broadcast-navigation product, evaluated in memory on the
already frozen DRAO geometry. Retain model curves and bounds; retain no
navigation payload and access no observation locator, header or value.

Stop condition:
Stop before qualification-product selection unless the model-side envelope
plus the complete-witness conditional reserve fits inside the unchanged
7,339.701234647398 m guard.
```

## Frozen roles

- Observer: `DRAO00CAN`, unchanged coordinates and station metadata.
- Structural/measurement qualification candidate: DOY232, 2026-08-20,
  `01:19:00--02:28:00 GPS`; artifact unselected.
- Possible later primary: DOY233, 2026-08-21,
  `01:14:30--02:23:30 GPS`; artifact unselected.
- Codebook: `G07/G08/G09/G21/G27/G30`.
- Grid: 139 epochs at 30 s; prefix 79, held-out 60.
- Null and one-clutter topology: unchanged, but no prospective primary plan is
  frozen by this scope.

DOY230 and DOY231 retain only their immutable roles in the closed plan. They
will not be reopened, relabelled or used as qualification/primary data.

## Model-only authority

The only permitted transient input is NOAA NGS
`brdc2330.26n.gz`, 70,893 bytes, SHA-256
`35e51e28aee55160723444c5f3a19a9f5048ca8c49e07fa90e2a16e832003bbf`.
Its uncompressed bytes must hash to
`f81333d83325df29e734936ea65474d64c4cc8d37049bf80d39e9ccf2dc241f8`.
The payload must be destroyed after compilation.

## Two-stage envelope

Model-side terms are evaluated before any observation product:

- direct common event-time shift on all six trajectories;
- broadcast-orbit accuracy family from the selected ephemerides;
- non-affine broadcast satellite-clock shape intentionally omitted by the
  range-only orbital coordinate;
- conservative troposphere and station/EOP/relativity intervals.

Capability-conditional reserve is not declared observed. It is admitted only
if a later, distinct qualification proves the exact signal/scale format and a
future primary enforces complete C1C/C2W coverage at every core-phase epoch:

- higher-order ionosphere: 2 m common-mode p-p;
- antenna PCV/phase wind-up: 4 m common-mode p-p;
- phase-minus-code hardware/multipath witness: 2,500 m common-mode p-p;
- RINEX F14.3 phase quantization: 0.0017238368006440115 m common-mode p-p;
- epoch-common receiver clock: exact zero after ensemble centering;
- track/signal implementation remainder: included in the complete
  phase-minus-code witness, never assumed common.

Ninety-five percent witness coverage is no longer sufficient. No missing
witness epoch may be bridged or assigned a zero error.

## Boundary

No DRAO locator, observation header, payload byte, phase/code value or orbital
score may be accessed. A positive model-side result authorizes only review of
one DOY232 qualification contract. It does not select that artifact and does
not freeze or authorize the DOY233 primary.
