# KIRU/MAT1 G15/G22 native-Doppler primary plan

## Status

`PLAN_FROZEN_PRIMARY_BLOCKED`

This document freezes one prospective historical held-out experiment. It does
not authorize network access, artifact materialization, header inspection or
numeric observation decoding. A later one-use authority must bind the exact
committed evaluator seal before either observation product is requested.

This is the next physical vertical inside the existing GNSS work. It creates no
new gate and no reusable framework.

## Physical question

Does the frozen G15/G22 broadcast orbital geometry predict the KIRU00SWE minus
MAT100ITA dual-frequency native-Doppler coordinate during the held-out suffix
better than a prefix-calibrated affine non-orbital null?

## New information produced

A single result can determine whether an outcome-independent orbital curve is
prospectively preferred over the frozen affine alternative on two independent
receiver/antenna/clock roots. It cannot establish satellite identity, prefer a
specific orbit over another orbit, or generalize beyond this pass.

## Why the existing work cannot answer it

The DOY 214 development outcome measured only the path envelope. The DOY
219--221 navigation audits established geometry and model detectability but
opened zero observation bytes. None compared a previously unseen DOY 219
native-Doppler suffix with the orbital and affine hypotheses.

## Exact scope

- stations: `KIRU00SWE`, `MAT100ITA`;
- independent measurement roots:
  `KIRU00SWE_RECEIVER_ANTENNA_CLOCK` and
  `MAT100ITA_RECEIVER_ANTENNA_CLOCK`;
- target/reference: `G15` / `G22`;
- signal family: `C1C,D1C,S1C,C2W,D2W,S2W`;
- coordinate:
  `(KIRU_G15-KIRU_G22)-(MAT1_G15-MAT1_G22)` after the frozen
  `D1C/D2W` L1-equivalent ionosphere-free transform;
- epoch system: GPS;
- first epoch: `2026-08-07T16:20:00 GPS`;
- final epoch: `2026-08-07T19:29:30 GPS`;
- cadence: 30 s;
- records: 380;
- calibration prefix: first 76 records, through
  `2026-08-07T16:57:30 GPS`;
- held-out suffix: final 304 records, beginning
  `2026-08-07T16:58:00 GPS`;
- missing epochs or links allowed: zero;
- post-freeze retry, alternate endpoint, day, window, satellite, signal or
  transform: zero.

## Frozen products

Only these future observation products may be materialized:

- `KIRU00SWE_R_20262190000_01D_30S_MO.crx.gz`
- `MAT100ITA_R_20262190000_01D_30S_MO.crx.gz`

Their predeclared source directory is
`https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/219/`. Complete byte counts and
SHA-256 values are deliberately unknown before materialization. A future
materialization receipt must record them after each complete download and
before any decompression or parsing. An incomplete download may be resumed
only before complete-file hashing and before decoding.

The model product is the exact frozen
`BRDM00DLR_S_20262190000_01D_MN.rnx.gz`, compressed SHA-256
`12246e0e614f0a16c9bd7329ddd637fb541d478160d944131023aa9faeffcc3d`,
decompressed SHA-256
`8d5126ae5a7a8ad1e718c11a1c575c0961de1c57845ca15da4081e65e5709b5d`.

## Transform ledger

```text
RINEX D1C,D2W at each station/satellite
→ alpha*D1C + beta*(L1/L2)*D2W
→ station target-minus-reference
→ KIRU minus MAT1
→ observed 380-point L1-equivalent Doppler coordinate
```

The extractor receives no orbital trajectory. Navigation enters only after
both station arrays and all same-path witnesses have passed structural
admission.

`C1C,C2W,S1C,S2W` are witnesses, not fitted corrections. No phase value is
decoded. No measurement or per-epoch derived series is persisted.

## Admission and same-path witnesses

Before held-out scoring:

1. both complete compressed artifacts match the future materialization
   receipt before decompression;
2. all 380 epochs and all four G15/G22 station links are present at 30 s;
3. every selected D/C/S scalar is finite;
4. code and SNR witnesses are positive on every link;
5. the orbital-model prefix residual peak-to-peak is at most
   `1.7027139799721753 Hz`;
6. prefix dispersive-network peak-to-peak is at most
   `0.2717166666666344 Hz`.

During the held-out suffix:

- cadence and all fields must remain complete and finite;
- each station/satellite/signal SNR must not fall below that same link's
  calibration-prefix minimum;
- held-out dispersive-network peak-to-peak must not exceed
  `0.2717166666666344 Hz`.

Health can refuse detectability but cannot fit either hypothesis. No absolute
dB-Hz threshold is invented.

## Hypotheses and nuisance model

`H_ORBITAL` is the exact G15/G22 KIRU/MAT1 broadcast curve from the frozen
navigation product. `H_AFFINE` is zero geometric structure. Both hypotheses
receive their own constant plus slope fit on the same 76-record prefix. No
suffix fit, free time phase, spline, warp or per-sample correction is allowed.

The score is held-out residual peak-to-peak. A hypothesis wins only when its
score is more than `2326.8486747825173 Hz` below the alternative score. That
guard already includes the DOY 214 measurement-path envelope, conservative
physical path terms, the admitted 10.608 m/link broadcast model interval and
the pairwise multiplier. Equality is `AMBIGUOUS`.

## Outcomes

- `ARTIFACT_MATERIALIZATION_FAILED`: identity was not established before
  decode; every physical clause is `NOT_EVALUATED`;
- `MEASUREMENT_INVALID`: required epochs, links or selected fields are invalid;
- `NOT_DETECTABLE`: measurements exist but a frozen prefix or held-out health
  clause fails;
- `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`;
- `PREFIX_AFFINE_NULL_PREFERRED`;
- `AMBIGUOUS`;
- `PRIMARY_EVALUATION_ERROR`: descriptive/software failure; physical decision
  is `NOT_EVALUATED`.

The claim ceiling is `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`.

## Minimum experiment and stop condition

After a separately reviewed one-use authority, materialize exactly the two
observation products and the already-frozen navigation product, hash before
decode, run the sealed evaluator once, persist one strict scalar receipt, erase
all compressed observations, decompressed RINEX and arrays, and stop after the
first terminal outcome. There is no second window or retry after plan freeze.
