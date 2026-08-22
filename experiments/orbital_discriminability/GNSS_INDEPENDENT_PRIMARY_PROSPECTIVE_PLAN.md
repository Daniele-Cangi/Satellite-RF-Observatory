# KIRU–MAT1 G20/G22 independent GNSS prospective plan

## State

`PROSPECTIVE_PLAN_FROZEN_PRIMARY_BLOCKED`

This plan freezes one historical held-out forward comparison before either
DOY 215 primary header or payload is opened. It does not authorize access.
The two DOY 214 qualification products are concluded and cannot be rescored or
used to choose any primary parameter.

No new gate is created. This is the proof freeze for the physical vertical
selected by the navigation review and admitted by the bounded qualification.

## Physical question and information produced

Can the broadcast G20 orbital geometry predict the held-out KIRU00SWE–
MAT100ITA dual-frequency carrier-phase double-difference dynamics better than
both a prefix-only affine alternative and the frozen jointly visible G14
orbital alternative?

A successful run can produce the first real result in this repository that
passes `MEASUREMENT_VALID` and compares an observer-coupled orbital prediction
against frozen nulls on an independent temporal suffix. It cannot independently
identify G20: RINEX PRN labels and the same-day broadcast navigation product
condition the target identity.

## Frozen lineage

- navigation review receipt SHA-256:
  `87a869afa1fa6a66e0cc4144c2ca7f261364e33867fe5ced9b9ee9620257df78`;
- DOY 214 qualification receipt SHA-256:
  `5e2d319ba633dce788bfa0a8b8961fa228a4b6ffd0ed47787b92c59520b37f0d`;
- qualification manifest SHA-256:
  `bcd504f9e3a0e2b70bf62ee566fdcdc6154e43a7063d6bbe8921ad2ba292210c`;
- value-blind qualification parser source SHA-256:
  `ada26cf0ac30ea556af480cf3590b5ff7b61b0e26bb762e766a87de95114be18`;
- hardened envelope source SHA-256:
  `da8f2bb9f1779c1e6e4bdad0466428bf9034b4dd90bea1d8cc36abfb14c17bc8`;
- hardened broadcast screen source SHA-256:
  `1018c0cb2cdeff17d17e78e0f2c082b73e2ac7baccc138f55b64d0ba2d8324a0`.

The exact broadcast navigation source is
`BRDM00DLR_S_20262150000_01D_MN.rnx`, 8,503,101 bytes, SHA-256
`a8be80bbc5ad857381b8b4d662a08c9fb56a015b78c928d084f32799077aeb24`.
Its compressed source is 1,406,096 bytes, SHA-256
`261225401bdeaae1c5ea102c76b5b663fa999c6945821b10b6b4967731fe0f78`.
It is a broadcast ephemeris model, not receiver evidence.

## Frozen measurement roots and primary products

The independent roots are:

- `KIRU00SWE_RECEIVER_ANTENNA_CLOCK`, station coordinates
  `67.857350°, 20.968442°, 390.9 m`;
- `MAT100ITA_RECEIVER_ANTENNA_CLOCK`, station coordinates
  `40.649061°, 16.704544°, 534.5 m`.

Only these primary products may later be materialized:

| Station | Exact product | Pre-access HEAD length |
|---|---|---:|
| KIRU00SWE | `KIRU00SWE_R_20262150000_01D_30S_MO.crx.gz` | 5,113,772 bytes |
| MAT100ITA | `MAT100ITA_R_20262150000_01D_30S_MO.crx.gz` | 4,255,324 bytes |

Their full SHA-256 values are deliberately unknown. A later authority may
materialize each complete artifact in quarantine, verify the exact filename
and predeclared byte count, and record its SHA-256 before any decompression.
A changed filename, byte count, station or day is
`ARTIFACT_MATERIALIZATION_FAILED`, not a measurement result.

Bounded range-resume is permitted only for transport interruption before the
complete-file hash and before any decompression. It may not change mirror,
product, day or byte count. Once either primary is decompressed, there is zero
retry, zero alternate artifact and one terminal receipt.

## Frozen header and signal requirements

The primary header must declare:

- an observation product for the expected station marker;
- 30-second epochs in GPS system time;
- `RCV CLOCK OFFS APPL = 0`, either explicitly or by the documented RINEX
  default;
- all six selected GPS fields `C1C`, `L1C`, `S1C`, `C2W`, `L2W`, `S2W`.

The signal family was selected on DOY 214 before primary occupancy was seen
and may not change. Extra observables are ignored. A different supported RINEX
minor version is not evidence of failure by itself, but any change that the
frozen field parser cannot describe is `PRIMARY_EVALUATION_ERROR`, not
`MEASUREMENT_INVALID`.

Epoch labels remain GPS system time during parsing. The physical trajectory
uses `UTC = GPS - 18 s`. No fitted time phase is allowed. Independent station
time error remains the existing direct `t ± 15 s` trajectory envelope; it is
not estimated from the held-out observations.

## Frozen coordinate and transform

For each station and each of G20/G22:

1. parse finite `L1C` and `L2W` carrier phase in cycles;
2. convert to metres using exact GPS L1 `1,575,420,000 Hz`, GPS L2
   `1,227,600,000 Hz` and `c = 299,792,458 m/s`;
3. form the first-order ionosphere-free path with coefficients
   `2.54572778016316` and `-1.5457277801631601`;
4. form `[(KIRU G20 - KIRU G22) - (MAT1 G20 - MAT1 G22)]`;
5. take the central derivative across adjacent 30-second records, producing a
   60-second baseline at the centre epoch;
6. scale by `-1,575,420,000 / c` to L1-equivalent hertz.

The first and final raw records support the derivative and do not become
features. No smoothing, interpolation, time warp, phase unwrapping selected
from the primary, cycle-slip repair or suffix correction is permitted.

## Frozen primary window

Raw records:

```text
GPS: 2026-08-03 16:02:30 through 19:12:00
UTC: 2026-08-03 16:02:12 through 19:11:42
records: 380
```

Feature records after derivative edges:

```text
GPS: 2026-08-03 16:03:00 through 19:11:30
UTC: 2026-08-03 16:02:42 through 19:11:12
records: 378
```

Calibration prefix:

```text
GPS: 2026-08-03 16:03:00 through 16:40:30
UTC: 2026-08-03 16:02:42 through 16:40:12
records: 76
```

Held-out suffix:

```text
GPS: 2026-08-03 16:41:00 through 19:11:30
UTC: 2026-08-03 16:40:42 through 19:11:12
records: 302
```

No held-out record may choose a field, fit a nuisance, change an admission
rule or modify a null.

## Measurement admission

Before feature construction, both station files must contain every one of the
380 exact epochs, both satellites and all six frozen fields. No missing epoch
or field is interpolated or bridged.

Every used scalar must parse from the RINEX 14-character value coordinate and
be finite. Code and SNR are same-path presence witnesses only; no magnitude
threshold is applied. LLI attached to every used phase field must be blank or
zero. No nonzero LLI is repaired.

For every station/satellite stream, the absolute second difference of
`lambda1*L1C - lambda2*L2W` must not exceed
`0.09514683639918244 m`, half the shortest used carrier wavelength. This rule
is a frozen discontinuity admission bound, not a posterior uncertainty model.

Failures of artifact identity, field presence, finite parsing, epoch
continuity, LLI or geometry-free continuity produce `MEASUREMENT_INVALID`.
Clauses downstream of the first failure are `NOT_EVALUATED`.

## Frozen physical envelope

The selected geometry has minimum elevations KIRU G20 `15.2072715°`, KIRU
G22 `15.0870603°`, MAT1 G20 `41.7370650°` and MAT1 G22 `32.9410427°`.

| Term | One-model held-out p-p bound |
|---|---:|
| direct station time shift, independently ±15 s | 11.191258116 Hz |
| differential troposphere | 0.109631430 Hz |
| RINEX phase quantization | 0.017417907 Hz |
| broadcast-orbit path interval | 161.666414029 Hz |
| higher-order ionosphere | 20.208301754 Hz |
| antenna PCV and phase wind-up | 40.416603507 Hz |
| multipath and signal-specific hardware admission limit | 40.416603507 Hz |
| station displacement, EOP and relativity | 40.416603507 Hz |
| satellite-clock retarded-time remainder | 40.416603507 Hz |

The terms are summed linearly: `354.8594372656104 Hz` for one model. Every
pairwise comparison reserves twice that envelope:
`709.7188745312208 Hz`. No Gaussian independence is assumed.

The frozen prefix-affine separation is `6290.892122536 Hz`. The controlling
G20-versus-G14 separation is `6233.797940337912 Hz`, leaving
`5524.079065806692 Hz` after the pairwise envelope. A primary negative is
therefore interpretable only after measurement and calibration admission.

## Frozen nuisance and nulls

For each hypothesis `H`, fit a constant and slope to `observed - H` using only
the 76 calibration records. Freeze both coefficients and evaluate the same
residual on the 302 held-out records.

The hypotheses are:

- `H_G20`: frozen G20/G22 broadcast geometry;
- `H_AFFINE`: zero orbital curve plus the same prefix-only affine nuisance;
- `H_G14`: frozen G14/G22 broadcast geometry with identical receiver,
  timing, field and scoring transforms.

The score is held-out residual peak-to-peak. No hypothesis receives a free
time phase, different field, different prefix, different transform or
different missing-data rule.

The nominal calibration residual peak-to-peak must not exceed the one-model
`354.8594372656104 Hz` admission envelope. Otherwise the result is
`NOT_DETECTABLE` and held-out comparison is `NOT_EVALUATED`.

A hypothesis is preferred only when its held-out score plus the strict
`709.7188745312208 Hz` pairwise guard is less than every competing score.
Equalities do not pass.

## Frozen outcome semantics

Premeasurement states:

- `ARTIFACT_MATERIALIZATION_FAILED`: exact historical products were not fully
  materialized and hashed; no measurement claim;
- `PRIMARY_EVALUATION_ERROR`: frozen software could not describe or complete
  the run; no epistemic rejection and no physical claim.

Physical terminal outcomes after a valid evaluator run:

- `MEASUREMENT_INVALID`;
- `NOT_DETECTABLE`;
- `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`;
- `PREFIX_AFFINE_NULL_PREFERRED`;
- `WRONG_ORBIT_G14_PREFERRED`;
- `AMBIGUOUS`.

Only the final four evaluate the held-out comparison. Even
`ORBITAL_MODEL_PREDICTIVELY_PREFERRED` authorizes only a model-conditioned
forward result for this coordinate and these two roots. It does not authorize
satellite identity, orbit reconstruction, a claim about all GNSS stations or
repeated-pass consistency.

## Access, persistence and stop rule

Primary access is not authorized by this plan. Before later access, the exact
deterministic evaluator source, dependencies, this plan SHA-256 and the
qualification parser/manifest hashes must be sealed in an executable manifest.

During an authorized run, compressed artifacts may exist only in quarantine.
Decompressed RINEX, selected arrays, observed features and hypothesis arrays
remain in RAM and are overwritten after the single receipt. No raw or derived
GNSS measurement is committed.

After decompression begins: zero retry, zero alternate file, zero new window,
zero station/satellite/signal substitution, zero threshold change and exactly
one terminal receipt. Stop after that outcome.
