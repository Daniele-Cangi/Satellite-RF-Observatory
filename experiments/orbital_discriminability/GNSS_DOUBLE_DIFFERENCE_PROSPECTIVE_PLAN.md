# GOLD–NLIB G11/G21 prospective double-difference plan

## State

`PROSPECTIVE_PLAN_FROZEN_AWAITING_MEASUREMENT_AUTHORITY`

No RINEX epoch record or observation field has been decoded. The two complete
compressed artifacts were materialized and hashed, but the only decompressed
content admitted so far ends at each file's first `END OF HEADER` newline.

## Physical question and claim scope

Can the frozen GPS G11 broadcast orbit predict the held-out GOLD00USA–
NLIB00USA dual-frequency carrier-phase double-difference dynamics better than
a prefix-only affine null and the frozen jointly visible G12 orbit alternative?

The result can establish only model-conditioned forward orbital prediction for
this coordinate and these two receiver roots. RINEX PRN labels and the same-day
broadcast navigation product condition target identity; the experiment cannot
independently establish that the signal belongs to G11.

## Time-axis correction before freeze

The geometry-only checkpoint `709317c` labelled its grid as UTC before an
observation header had demonstrated the delivered time system. Both real
headers declare GPS time. GPS was 18 seconds ahead of UTC on 2026-08-03.

The error was not absorbed as a fitted time phase. The physical grid was moved
to UTC = GPS minus 18 seconds and the complete broadcast sweep was rerun with
unchanged elevation, duration, calibration fraction and null families. The old
manifest `68d5f24e...761a12` is historical; the corrected manifest is
`8a97c9fa...63764` and yields 177 qualifying windows.

## Exact artifacts and header boundary

| Station | Product | Bytes | SHA-256 | Header SHA-256 |
|---|---|---:|---|---|
| GOLD00USA | `GOLD00USA_R_20262150000_01D_30S_MO.crx.gz` | 2,197,353 | `815176b9eb57c9032e4007db6c4b639aeeb9225cc4b992b38d16b1b6f773e027` | `b9ecab984789ca10733e1cd2f51cc4f2a54a152f8bdb7e0a98fed530e1416dad` |
| NLIB00USA | `NLIB00USA_R_20262150000_01D_30S_MO.crx.gz` | 2,534,492 | `cdc57171392b0f855fc7a7458e8b2ba8bd68951085e5f01cdfbdb848a7481ac5` | `3c244330482535bd51ba0c53b567070245df84ea51c3483224bc1d590aa56b0c` |

GOLD required 3,086 compressed bytes to emit 215 header lines; NLIB required
1,511 compressed bytes for 55 lines. Neither boundary call emitted bytes after
`END OF HEADER`, and all observation-access counters remain zero.

The parser manifest is
`ef12c103478400cf3a14060f8124f2443f36135c8f24ad25bbba9329f87c441f`.

## Header admission

Both files are RINEX 3.04 / CRINEX 3.0 mixed-system observation products,
cover GPS 2026-08-03 00:00:00 through 23:59:30 at a declared 30-second
interval, and identify the expected independent station roots.

The common frozen GPS signal family is:

```text
phase:   L1C + L2W
code:    C1C + C2W
witness: S1C + S2W and the LLI attached to both phase fields
```

GOLD does not declare a signal-strength unit. S1C/S2W are therefore continuity
and presence witnesses only; no dB-Hz threshold may be inferred. NLIB declares
`DBHZ`.

Neither header contains `RCV CLOCK OFFS APPL`. RINEX 3.04 Table A2 explicitly
defines the missing-record default as 0: receiver clock correction was not
applied. This is recorded as a standard-implied value, not an invented header
field.

## Frozen coordinate

For each station, target and reference:

1. convert L1C and L2W cycles to metres using the exact GPS L1 and L2 carrier
   frequencies;
2. form the first-order ionosphere-free range using fixed coefficients
   `2.54572778016316` and `-1.54572778016316`;
3. form `(GOLD G11 - GOLD G21) - (NLIB G11 - NLIB G21)`;
4. take a central time derivative over the adjacent 30-second epochs, giving a
   60-second baseline at the centre epoch;
5. scale by `-1575420000 / c` to the declared L1-equivalent hertz coordinate.

The first and last epoch of every continuous segment are dropped. A missing or
non-30-second epoch is never bridged. Any LLI, geometry-free phase slip or
clipping/parse ambiguity in any of the eight used phase streams refuses the
affected segment.

## Frozen window

Raw input epochs needed for the central derivative:

```text
GPS labels:  2026-08-03 10:01:30 through 13:14:00
physical UTC: 2026-08-03 10:01:12 through 13:13:42
```

Feature grid after dropping derivative edges:

```text
GPS labels:  10:02:00 through 13:13:30
physical UTC: 10:01:42 through 13:13:12
384 feature records
```

The first 77 feature records are calibration only:

```text
GPS calibration: 10:02:00 through 10:40:00
UTC calibration:  10:01:42 through 10:39:42
```

The remaining 307 records are held out:

```text
GPS confirmation: 10:40:30 through 13:13:30
UTC confirmation:  10:40:12 through 13:13:12
```

No suffix sample may fit a nuisance, choose a signal, change a transform or
alter an admission threshold.

## Physical envelope

The physical-envelope manifest is
`6428cd6b4de8bba5bfa11de79466a914472f38ce8df1fceae67bed973aa80218`.
All terms receive the same calibration projection under every hypothesis.

| Term | One-model held-out p-p bound |
|---|---:|
| direct station time shift, independently ±15 s | 18.454110 Hz |
| differential troposphere, each ZTD in [0, 3.5] m | 0.079251 Hz |
| RINEX ionosphere-free phase quantization | 0.017468 Hz |
| broadcast-orbit path interval | 162.134013 Hz |
| higher-order ionosphere | 20.266752 Hz |
| antenna PCV and phase wind-up | 40.533503 Hz |
| multipath and signal-specific hardware admission limit | 40.533503 Hz |
| station displacement, EOP and relativity | 40.533503 Hz |
| satellite-clock retarded-time remainder | 40.533503 Hz |

The bounds are summed linearly: 363.085606 Hz for one model. Pairwise model
comparison reserves twice that amount, 726.171212 Hz. No independence or
Gaussian probability is assumed.

The controlling frozen separation is 2,146.796809 Hz peak-to-peak against the
prefix-affine null. The G12 alternative separation is 2,927.015464 Hz. The
remaining pairwise physical margin is therefore 1,420.625597 Hz.

## Frozen nulls and score

For each hypothesis `H`, fit only a constant and slope to
`observed - H` on the 77 calibration records. Freeze those two coefficients,
then compute:

```text
S(H) = peak_to_peak(heldout_observed - heldout_H - frozen_prefix_affine)
```

The hypotheses are:

- `H_G11`: frozen G11/G21 broadcast geometry;
- `H_AFFINE`: no orbital curve, only the calibration-prefix affine model;
- `H_G12`: frozen G12/G21 geometry with identical transforms and complexity.

`H_G11` is predictively preferred only if:

```text
S(H_G11) + 726.1712115799801 Hz
    < min(S(H_AFFINE), S(H_G12))
```

Symmetric inequalities authorize a null-preferred result. Otherwise the
outcome is `AMBIGUOUS`.

## Measurement admission and outcomes

Before scoring, all four station/satellite links must provide non-missing
C1C/L1C/S1C and C2W/L2W/S2W at every required raw epoch. LLI, epoch continuity,
Hatanaka decoding, central-difference support and code/phase same-path checks
are physical-measurement clauses, not descriptive metadata.

Allowed terminal outcomes are:

- `MEASUREMENT_INVALID` — artifact, decode, timing, gap or slip clause fails;
- `NOT_DETECTABLE` — the calibration prefix exceeds the frozen combined
  admission envelope or same-path witnesses cannot preserve the coordinate;
- `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`;
- `PREFIX_AFFINE_NULL_PREFERRED`;
- `WRONG_ORBIT_G12_PREFERRED`;
- `AMBIGUOUS`.

No outcome authorizes satellite identity, orbit reconstruction, repeated-pass
consistency or a claim about GNSS receivers outside GOLD/NLIB.

## Access and stop rule

Measurement access is not authorized by this plan. A later explicit authority
may decode exactly one deterministic pass over these two immutable artifacts.
There is no alternate target, reference, station, signal family or window after
freeze. Software description failures may be repaired only before any score is
emitted; they cannot select a new observation or change the physical decision.

The run must stop after its first terminal outcome.

## Outcome-independent sources

- [RINEX 3.04](https://files.igs.org/pub/data/format/rinex304.pdf)
- [IERS Chapter 9 propagation models](https://iers-conventions.obspm.fr/content/chapter9/icc9.pdf)
- [IGS station GOLD00USA](https://network.igs.org/GOLD00USA)
- [IGS station NLIB00USA](https://network.igs.org/NLIB00USA)
- [IGS CORS guidelines](https://files.igs.org/pub/resource/guidelines/Guidelines_for_Continuously_Operating_Reference_Stations_in_the_IGS.pdf)
