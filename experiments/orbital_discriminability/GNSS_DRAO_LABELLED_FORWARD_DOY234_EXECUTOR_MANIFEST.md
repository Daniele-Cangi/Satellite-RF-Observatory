# DRAO labelled-forward DOY234 executor

**DRAO_DOY234_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED**

The final member of the original pre-observation shortlist is frozen at source
commit `f3421b3bf78259d1abc61e0d0847cf35556c925f`.  It retains the original DRAO
station, six labelled GPS tracks, 30 s grid, calibration prefix, held-out
suffix, orbital model, prefix-affine null and time-reversed-geometry null.

The controlling guard is `B = 3964.157666752234 m`; the frozen offline
geometry leaves `24316.217426416108 m` after the conservative `3B` guard.

## Description repair frozen before selection

The RINEX 3.04 `SYS / PHASE SHIFT` ledger now distinguishes a valid reference
signal record with an observation code and blank correction from an explicit
numeric correction and from a system-alignment-unknown blank record.  Numeric
corrections are validated but never applied again because stored observations
already include them.  Malformed, conflicting, incomplete or unknown states
stop before measurement admission and authorize no physical claim.

This behavior is covered by a full 139-epoch synthetic vertical, not merely a
unit parser example.  The executor remains model-blind until all structural,
clock, continuity, same-path code and geometry-free witnesses admit the
measurement coordinate.

At freeze there was no DOY234 observation locator, request, header, payload,
value or score.  A separately reviewed immutable artifact-selection receipt
and a separately sealed one-use runner are required before observation access.
