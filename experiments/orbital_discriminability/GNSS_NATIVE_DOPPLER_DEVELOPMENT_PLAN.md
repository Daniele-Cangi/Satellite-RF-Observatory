# Native Doppler development plan (DOY 214 only)

## Authority and scope

This is a development-only numeric access plan for the two exact, already
qualified DOY 214 KIRU/MAT1 observation products.  It grants no access to the
DOY 219--221 orbitality shortlist, does not reopen the closed DOY 215 outcome,
and authorizes no orbital result.

The physical purpose is narrow: determine whether the predeclared native
RINEX Doppler coordinate can be decoded deterministically and characterize a
conservative development residual envelope before any future prospective
observation is frozen.

## Frozen measurement surface

- Stations: `KIRU00SWE`, `MAT100ITA`.
- Satellites: target `G20`, reference `G22`.
- Epochs: every 30 s from `2026-08-02T15:41:00 GPS` through
  `2026-08-02T19:47:00 GPS`, inclusive (493 records).
- Numeric fields: `D1C`, `D2W`.
- Same-path health witnesses: `C1C`, `S1C`, `C2W`, `S2W`.
- RINEX Doppler sign: positive for an approaching satellite.
- L1-equivalent ionosphere-free link coordinate:

  `alpha*D1C + beta*(f1/f2)*D2W`, where
  `alpha=f1^2/(f1^2-f2^2)` and `beta=-f2^2/(f1^2-f2^2)`.

- Network coordinate:

  `(KIRU_G20-KIRU_G22)-(MAT1_G20-MAT1_G22)`.

The parser receives no navigation file, TLE, predicted trajectory, orbital
residual, future-product identity, or primary/reserve information.

## Frozen development evaluation

The complete 493-record coordinate is retained only in RAM.  All 114
contiguous 380-record windows are evaluated; none is selected from the
measurements.  For each window:

1. compile the broadcast-navigation G20/G22 network curve independently;
2. subtract it from the measured coordinate;
3. fit only a constant and slope on the first 76 records;
4. apply that frozen prefix fit to the remaining 304 records;
5. report held-out peak-to-peak and RMS residuals.

The largest held-out peak-to-peak residual over all 114 windows is the
development residual envelope.  A separate analytic F14.3 Doppler
quantization bound is projected through the same affine operator and added
linearly.  Twice that sum is the provisional pairwise guard.  This is a
conservative, non-probabilistic development bound; it is not a calibrated
confidence interval and cannot by itself authorize a future negative result.

## Admission and refusal

The development coordinate is admitted only if both exact artifact hashes and
byte counts match before decompression, all 493 epochs and all four links are
present, every selected scalar is finite, epoch cadence is exactly 30 s, and
the declared GPS time and receiver-clock policy match the qualification
receipt.  Missing Doppler or same-path witnesses are `MEASUREMENT_INVALID`;
parser, decompression, or description failures are `DEVELOPMENT_ERROR`.

Allowed terminal states are:

- `NATIVE_DOPPLER_DEVELOPMENT_ENVELOPE_FROZEN`
- `DEVELOPMENT_MEASUREMENT_INVALID`
- `DEVELOPMENT_ERROR`

No threshold, target, reference, signal, epoch, window length, calibration
length, transform, or outcome may change after the first numeric scalar is
decoded.

## Persistence and stop condition

Compressed inputs exist only in an ephemeral quarantine during the run.
Decompressed RINEX and all numeric arrays are overwritten in `finally` paths.
Only hashes, counts, finite aggregate bounds, minima/maxima needed for future
admission, and the transform manifest may be committed.  No observation
scalar, epoch series, RF sample, phase value, or per-epoch Doppler value may be
persisted.

Stop after one development outcome and a frozen transform manifest.  Do not
freeze or open a future primary.
