# GNSS native-Doppler orbitality geometry

## Outcome

`NATIVE_DOPPLER_ORBITALITY_GEOMETRY_SHORTLIST_READY`

The KIRU00SWE–MAT100ITA native-Doppler route has three navigation-only
candidate windows with positive orbital-versus-affine margin after direct
station-clock trajectory envelopes. No observation product or numeric
measurement value was opened.

## Claim boundary

This design asks only whether a frozen orbital curve predicts held-out
non-affine structure better than a prefix-calibrated affine alternative.

The maximum future claim is:

`ORBITAL_MODEL_PREDICTIVELY_PREFERRED`

It cannot authorize `SPECIFIC_ORBIT_PREFERRED`. The wrong-orbit hypothesis was
not weakened or made easier; it was removed from this experiment because
specific identity is a later and distinct claim-ladder step. The concluded
three-satellite searches remain authoritative evidence that the current
KIRU/MAT1, 380-epoch topology cannot test both steps simultaneously.

## Frozen coordinate

```text
D1C/D2W
  -> first-order ionosphere-free L1-equivalent Doppler
  -> target-reference at KIRU
  -> target-reference at MAT1
  -> KIRU-MAT1 double difference
  -> 76-record prefix affine calibration
  -> 304-record held-out orbital-versus-affine comparison
```

Unchanged parameters:

- 30 s grid and 380 records;
- 15 degree minimum elevation at both stations;
- direct independent station-clock shifts of -15 s, 0 s and +15 s;
- no local-slope clock approximation;
- no observation-informed target, reference, window or nuisance selection.

## Navigation-only shortlist

| Role | DOY | Target/reference | GPS window | Non-affine p-p | Clock envelope p-p | Remaining | Minimum shifted elevation |
|---|---:|---|---|---:|---:|---:|---:|
| Primary candidate | 219 | G15/G22 | 16:20:00–19:29:30 | 6752.925150 Hz | 9.388576 Hz | 6743.536574 Hz | 15.049791° |
| Reserve 1 | 220 | G15/G22 | 16:16:00–19:25:30 | 6752.640160 Hz | 9.406306 Hz | 6743.233854 Hz | 15.041427° |
| Reserve 2 | 221 | G15/G22 | 16:12:00–19:21:30 | 6752.166209 Hz | 9.426102 Hz | 6742.740107 Hz | 15.033625° |

All fourteen DOY 219–232 days have at least thirteen robust target/reference
pairs of the frozen length. G15/G22 is the best day-level candidate throughout
the set. The roughly four-minute daily shift is consistent with the repeated
GPS geometry represented by the broadcast ephemerides.

## What remains unknown

The large navigation margin is not yet a detectability result. The following
remain unmeasured for native RINEX Doppler:

- numeric `D1C/D2W` occupancy and continuity at both stations;
- effective quantization and receiver-specific Doppler resolution;
- noise, clipping, missing epochs and same-path code/SNR witness behavior;
- whether the dual-frequency combination preserves the predicted curvature;
- a conservative measurement envelope after prefix-affine projection.

Therefore every shortlisted row still has
`negative_result_interpretable = false`. The exact next blocker is
`SEPARATE_AUTHORITY_FOR_DOY214_NATIVE_DOPPLER_NUMERIC_DEVELOPMENT`.

## Authority

- DOY 214 numeric values opened: false;
- candidate observation products opened: false;
- observation bytes accessed: 0;
- DOY 215 reopened: false;
- prospective primary plan frozen: false;
- specific-orbit claim authorized: false;
- new gate created: false.

The next bounded physical step is development-only measurement
characterization on the already-qualified DOY 214 artifacts. Primary and
reserve observation products must remain unopened until that measurement
envelope and a complete prospective plan are frozen.
