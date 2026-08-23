# GNSS native-Doppler broadcast-model bound audit

## Outcome

`NATIVE_DOPPLER_BROADCAST_MODEL_BOUND_ADMITTED`

This is a navigation-only result. No observation product name, URL, header,
byte or numeric measurement was accessed. The primary plan remains unfrozen
and primary/reserve observation authority remains false.

## What was tested

The compiler validated the already-frozen compressed and decompressed hashes of
the DOY 219--221 BRDM products, decompressed them only in RAM, and selected the
chronologically latest G15/G22 record at every one of the 380 frozen 30 s
epochs per day. Record selection happens before the health test so an older
healthy record cannot hide a newer unhealthy message.

Every selected record was healthy, had a known 4 h fit interval, and was no
older than 7,186 s. The selected RINEX nominal SV-accuracy values were 2.0 m
and, for G15 on portions of DOY 220/221, 2.8 m.

## Model interval

RINEX 3.05 Appendix A6 stores the nominal metre value derived from the LNAV
URA index. IS-GPS-200N defines URA as a conservative RMS signal-in-space range
error indicator and defines legacy integrity against 4.42 times the upper edge
of the corresponding URA category. The audit therefore used:

```text
per-link model interval = 4.42 * upper edge of selected URA category
```

This is `MODELED_INTERVAL_WITH_LEGACY_INTEGRITY_ASSURANCE`, not a deterministic
mathematical worst-case or a calibrated probability for this experiment. It is
also broader than pure orbit error: it includes other signal-in-space terms.
Those overlaps were not subtracted from the existing envelope, making the
composition conservative.

| Role | DOY | Model interval | Frozen maximum | Final margin |
|---|---:|---:|---:|---:|
| Primary candidate | 219 | 10.608 m/link | 64.950176 m/link | 4416.687900 Hz |
| Reserve 1 | 220 | 15.028 m/link | 64.939129 m/link | 4056.552281 Hz |
| Reserve 2 | 221 | 15.028 m/link | 64.926217 m/link | 4055.502832 Hz |

All three candidates preserve a strictly positive margin after the frozen
development envelope, fixed physical path terms, broadcast model interval and
pairwise guard.

## Interpretation

The previous `UNRESOLVED` broadcast-model term is now an outcome-independent
`MODELED` interval rather than zero. This removes the last navigation/model
blocker identified by the transfer audit. It does not itself produce an
orbital observation or authorize the claim.

The next smallest physical step is to freeze the exact DOY 219 prospective
evaluator and its separate observation authority. It must preserve the same
380 epochs, prefix/held-out split, affine null, same-path health witnesses,
model envelope and zero post-freeze retry.

## Primary references

- IGS/RTCM RINEX 3.05: https://files.igs.org/pub/data/format/rinex305.pdf
- IS-GPS-200N: https://archive.gps.gov/technical/icwg/IS-GPS-200N.pdf
