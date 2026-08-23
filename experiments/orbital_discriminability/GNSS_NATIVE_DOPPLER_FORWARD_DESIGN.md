# GNSS native-Doppler forward design

## Outcome

`NO_NATIVE_DOPPLER_GEOMETRY_WITH_FROZEN_NULL_SUPPORT`

The bounded navigation-only search did not freeze a new KIRU00SWE–MAT100ITA
primary. No observation product was opened and no Doppler, phase, code, SNR or
LLI value entered this result.

## Physical question

Can a native dual-frequency RINEX Doppler coordinate support a future
held-out KIRU/MAT1 orbital-versus-null comparison without integrating carrier
phase?

The proposed measurement coordinate was frozen before the navigation search:

```text
D1C/D2W
  -> first-order ionosphere-free L1-equivalent Doppler
  -> target-reference at KIRU
  -> target-reference at MAT1
  -> KIRU-MAT1 double difference
  -> prefix calibration
  -> held-out nominal versus affine and wrong-orbit nulls
```

RINEX Doppler uses the positive-for-approaching sign convention documented in
the official [RINEX 3.04 specification](https://files.igs.org/pub/data/format/rinex304.pdf).
The prior exact-hash, value-blind DOY 214 qualification receipt proves only
that both station headers declare `D1C` and `D2W`; it does not prove numeric
occupancy, noise, continuity or detector resolution.

## Frozen geometry design

- capability set: `KIRU00SWE`, `MAT100ITA`;
- development role retained: DOY 214, still numeric-value unopened;
- DOY 215 retained as a closed invalid primary and never reopened;
- candidate navigation days: DOY 216, 217 and 218;
- cadence: 30 s;
- fixed window: 380 epochs (76 calibration, 304 held out);
- minimum elevation: 15 degrees at both stations;
- direct independent station-clock shifts: -15 s, 0 s and +15 s;
- nulls: frozen prefix-affine and another jointly visible broadcast orbit;
- all hypotheses require the same epoch and robust visibility mask.

Only the three public IGS broadcast-navigation products were materialized.
Their compressed and decoded byte counts and SHA-256 values are frozen in
`GNSS_NATIVE_DOPPLER_FORWARD_DESIGN_RECEIPT.json`.

## Admission result

| DOY | Maximum two-satellite continuity | Pairs reaching 380 | Maximum three-satellite continuity | Triples reaching 380 | Controlling triple |
|---:|---:|---:|---:|---:|---|
| 216 | 467 | 14 | 379 | 0 | G14/G20/G22 |
| 217 | 467 | 14 | 379 | 0 | G14/G20/G22 |
| 218 | 467 | 14 | 379 | 0 | G14/G20/G22 |

The nominal target/reference geometry is not the blocker: fourteen satellite
pairs per day sustain the frozen length. The wrong-orbit null requires a third
satellite on exactly the same robust mask, and the best triple falls one
30-second epoch short on every predeclared day. Therefore no candidate reaches
the direct clock-envelope or instrumental-assessment stages.

This is not a sensor failure, a negative RF/GNSS observation or evidence
against an orbital hypothesis. It is a premeasurement refusal: the bounded
candidate set cannot support the frozen comparison while preserving its null.
Reducing the window to 379 after seeing the result would be a post-hoc design
change and was not performed.

## Authority and stop

- observation products opened: 0;
- observation bytes accessed: 0;
- numeric Doppler values decoded: 0;
- numeric carrier-phase values decoded: 0;
- development numeric access authorized: false;
- future primary access authorized: false;
- prospective plan frozen: false;
- new gate created: false.

The exact blocker is
`PREDECLARED_NAVIGATION_SET_HAS_NO_380_EPOCH_THREE_SATELLITE_ROBUST_WINDOW`.
Any wider date search or changed window length would be a new premeasurement
design decision, not a retry of this result.
