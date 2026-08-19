# RSP-03 forward orbital test — prospective analysis plan

Status: **`PROSPECTIVE_PLAN_BLOCKED`**

Experiment: `RSP03-65732-20260209-PI9RD-SINGLE-STATION-FORWARD-V1`

Plan hash: `add5c2a3d5121d86978bc5d76ee07d1cc7484f9f533f4f1e04bdda0c8bd79dca`

Scope: one historical, single-station, calibration-prefix/held-out Doppler test.

This is a plan inside the existing G0/G1 scientific path, not a new gate. It
does not continue G1.1–G1.3 and does not modify G0/G1 semantics. No byte from
the primary or replication-reserve IQ files was opened while producing this
plan. Only the primary SigMF sidecar, HTTP headers, SatNOGS metadata and public
implementation documentation were inspected.

The plan is blocked because the available metadata and primary sources do not
give a defensible finite numerical bound from UTC/PPS to the ADC sample clock.
The relative sample clock is usable. A numerical absolute-time bound is not.
No value is substituted for that missing fact.

## Frozen dataset roles

| Role | Recording | Access authority in this plan |
|---|---|---|
| `PRIMARY_HELD_OUT` | RSP-03, 2026-02-09, PI9RD/CAMRAS, sample 0 at `2026-02-09T07:05:50.710039Z` | IQ sealed until the detector and every pre-primary bound are frozen |
| `DEVELOPMENT_FIXTURE` | RSP-03, 2026-02-08, sample 0 at `2026-02-08T11:48:41.560039Z` | may be used only after separate authorization; it is the sole detector-development IQ |
| `SEALED_REPLICATION_RESERVE` | RSP-03, 2026-02-13, sample 0 at `2026-02-13T09:39:30.000039Z` | remains unopened and cannot influence detector or primary analysis |
| `SECOND_STATION_WITNESS` | SatNOGS observation [13352524](https://network.satnogs.org/observations/13352524/), OK2KVL | metadata-only witness for the same pass; never enters the single-station geometric score |

Primary metadata URL:
[`rsp03_2026_02_09_07_05_50...sigmf-meta`](https://data.camras.nl/satellites/raw/rsp03_2026_02_09_07_05_50_436.950MHz_1.00Msps_ci16_le.chan1.sigmf-meta).
Its exact 1,863 response bytes had SHA-256
`0826fd8e6447d25a002697609e520ef152dc57a0cb787607aedbf99f9aa9d48c`
when retrieved on `2026-08-19`.

The primary data URL was queried with HTTP `HEAD`, not `GET`. It reported
`1,869,440,000` bytes, `Last-Modified: Mon, 09 Feb 2026 07:18:10 GMT`, ETag
`"6f6d6400-64a5ef0f9af68"`, and byte-range support. The size implies exactly
`467,360,000` `ci16_le` complex samples at four bytes per sample, or
`467.360000 s` at `1,000,000 samples/s`. These headers are discovery facts, not
the future artifact hash.

The development and reserve IQ and sidecars were not fetched. Their roles and
URLs are frozen in `rsp03_forward_plan.py`; role substitution is forbidden.

## Measurement and Doppler provenance

The primary sidecar states:

- recorder `vrt_to_sigmf`;
- datatype `ci16_le`;
- sample rate `1,000,000 Hz`;
- capture center `436,950,000 Hz`;
- `vrt:reference = external`;
- `vrt:time_source = pps`;
- capture datetime `2026-02-09T07:05:50.710039`;
- no `vrt:time_adjust` and no `vrt:cal_time` field.

CAMRAS operator documentation says the telescope records raw, uncorrected IQ
and that its VRT stream has no Doppler correction. It also says frequency,
sample rate and datatype are carried in VRT metadata. The exact provenance
classification is therefore:

```text
DOPPLER_CORRECTION = PRE_CORRECTION_PATH_SUPPORTED_BY_OPERATOR_DOCUMENTATION
PER_FILE_EXPLICIT_DOPPLER_FLAG = ABSENT
```

This is stronger than `UNKNOWN`, because the operator describes the path, but
weaker than per-file proof: the sidecar has no explicit Doppler-correction
flag. It must not be upgraded. The source is the CAMRAS operator's
[VRT/SatNOGS description](https://community.libre.space/t/proof-of-concept-using-zmq-vrt-instead-of-soapy/10869).

The `vrt-iq-tools` source inspected at commit
[`495e96ae`](https://github.com/tftelkamp/vrt-iq-tools/commit/495e96ae9aacc97a3892bdc17537446c50f9371d)
copies UHD receive metadata time to VRT packet timestamps, marks calibrated
time when PPS is in use, and converts the first packet timestamp to SigMF
`core:datetime`. UHD documents that RX `time_spec` is the time of the first
sample and that PPS latches device time. Those facts establish the timestamp
semantics, but neither source gives an accuracy bound for this particular
CAMRAS recording. See the official UHD
[RX metadata](https://files.ettus.com/manual/structuhd_1_1rx__metadata__t.html)
and [device synchronization](https://files.ettus.com/manual_archive/v4.1.0.0/html/page_sync.html)
documentation.

## Historical orbital elements and provenance

The nominal element set is the exact TLE embedded in SatNOGS observation
[13364515](https://network.satnogs.org/observations/13364515/), the PI9RD job
covering `2026-02-09T07:05:25Z` through `07:13:36Z`. The record identifies
NORAD 65732, observer PI9RD, `437,050,000 Hz`, and `tle_source =
Space-Track.org`.

```text
0 OBJECT XL
1 65732U 98067XL  26039.66236070  .00844645  35986-3  13863-2 0  9991
2 65732  51.6148 196.1853 0007277 299.9440  60.0848 16.02581073 22321
```

Canonical LF-terminated TLE SHA-256:
`1df5f80a1d84d7926e6545e799088db1574a57a65ed42bd37d1990804f9eecd5`.
The raw 2,890-byte API response retrieved at `2026-08-19T18:00:22Z` had
SHA-256
`64c1949a3c3e62c619d900854b73ec77a0d042f5a1e6f49dcaa5d86c9a3c4018`.
The TLE epoch is `2026-02-08T15:53:47.964480Z`, exactly
`54,722.745559 s` before primary sample 0.

This is strong evidence that SatNOGS attached this historical element set to
the scheduled observation. The API does not expose when Space-Track published
it or when the station fetched it; that publication timing remains unknown.
The TLE object label `OBJECT XL` is not independent satellite identity
evidence. No current TLE may replace it.

The TLE embedded in the independent witness observation is frozen as a
**model-sensitivity member only**:

```text
0 OBJECT XL
1 65732U 98067XL  26037.72735522  .00753541  26934-3  14853-2 0  9999
2 65732  51.6170 206.5302 0006539 284.0297  75.9985 15.99425235 22011
```

Its canonical SHA-256 is
`d93d67c004111cb8e81ac2d7f4146e04e6c06d666a00a44df9f76c0db23b38a2`;
the witness API response hash is
`62bc86f16edf0b12ea88d8ba1a025f83a40c4b5db89099a23b93775ad245c071`.
It is not a probability distribution, confidence interval, alternative that
may be chosen after outcome, or age-derived uncertainty. Propagated to PI9RD,
its difference from the nominal trajectory has `390.060 Hz` held-out RMSE
after a calibration-prefix affine removal and reaches `650.283 Hz` absolute.
That is a pre-IQ stress fact showing that element choice can dominate a narrow
detector error budget. The nominal TLE remains the sole hypothesis scored.

## Observer, geometry and exact partition

Observer: PI9RD/CAMRAS, WGS-84 latitude `52.812 deg`, longitude `6.396 deg`,
ellipsoidal altitude `10 m`. Carrier: `437,050,000 Hz`. The values come from
the same historical SatNOGS observation record, not a global inventory.

The existing stateless orbital kernel propagated the nominal TLE at 0.25 s
cadence before any IQ access. Doppler uses `-f_c range_rate/c`.

| Boundary/event | UTC | Elevation | Range rate | Predicted Doppler |
|---|---:|---:|---:|---:|
| sample 0 | `07:05:50.710039Z` | `1.644 deg` | `-6.807835 km/s` | `+9,924.747 Hz` |
| calibration stop / holdout start | `07:07:24.182039Z` | `9.720 deg` | `-6.135235 km/s` | `+8,944.203 Hz` |
| closest range / range-rate zero | about `07:09:29.642Z` | about `25.239 deg` | `0 km/s` | `0 Hz` |
| recording end, exclusive | `07:13:38.070039Z` | `-0.104 deg` | `+6.883210 km/s` | `-10,034.632 Hz` |

The geometric set is `2026-02-09T07:13:36.370519Z`; frames centered after it
are measurement-valid but excluded from orbital scoring. Maximum elevation is
`25.239 deg`; closest slant range is approximately `589.028 km`. Across the
recording the nominal Doppler spans about `19,959.044 Hz`, with slope between
`-132.280` and `-3.054 Hz/s` and sampled curvature between `-1.414` and
`+1.414 Hz/s^2`.

The exact raw-sample split is immutable:

```text
calibration = [0, 93_472_000)
              2026-02-09T07:05:50.710039Z
           to 2026-02-09T07:07:24.182039Z

held-out   = [93_472_000, 467_360_000)
              2026-02-09T07:07:24.182039Z
           to 2026-02-09T07:13:38.070039Z (exclusive)
```

This is exactly 20%/80%. The prefix sees only the early approaching branch
and about `980.545 Hz` of predicted Doppler change. The held-out interval must
extrapolate through maximum elevation, the Doppler zero crossing and almost
the entire receding branch, about `18,978.835 Hz` from its first frame to the
file boundary. This is the planned prediction challenge; it cannot be moved in
response to the ridge.

STFT frames inherit their event time from the center sample. A frame belongs
to calibration only when every sample in the frame lies inside calibration;
a frame belongs to held-out only when every sample lies inside held-out.
Boundary-straddling frames are discarded. Scored frames must also have
geometric elevation at their center at or above `0 deg`.

## Frozen physical hypothesis

For a ridge extracted without access to orbital predictions, the nominal
model is

```text
f_orbit(t) = 437_050_000 Hz
           + Doppler_nominal_TLE(t + delta_t)
           + delta_f0
           + drift * (t - t0)
```

The physical question is whether this exact historical orbital trajectory,
after only the three declared calibration nuisances, predicts the independent
held-out ridge better than every frozen non-orbital family.

Allowed nuisance and only allowed nuisance:

1. one constant carrier/receiver offset `delta_f0`;
2. one affine frequency drift `drift`;
3. one constant absolute-time offset `delta_t` inside a predeclared finite
   interval `[-B_t, +B_t]`.

For each candidate `delta_t`, `delta_f0` and `drift` are least-squares fits on
calibration frames only. The selected `delta_t` minimizes calibration RMSE;
ties are broken by smaller `abs(delta_t)`, then smaller signed `delta_t`.
That triple is applied unchanged to held-out frames. Direct trajectories at
the declared time-bound endpoints provide the timing envelope; local
slope-times-error is forbidden. Dynamic time warp, suffix alignment,
quadratic receiver drift, spline correction, per-frame offsets and holdout
refitting are forbidden.

`B_t` is currently absent. The sidecar proves a PPS-labelled relative sample
clock but not a finite UTC accuracy for this recording. Host time, PPS delay,
timestamp adjustment and ADC latency are not bounded by the preserved
sidecar. Until a same-path record or applicable operator/hardware calibration
establishes `B_t`, the fit domain and direct timing envelope cannot be frozen.
This is `NO_DEFENSIBLE_FINITE_PPS_TO_ADC_UTC_ERROR_BOUND`.

## Frozen null families

Every null is fitted only on the same calibration frames and extrapolated
unchanged over the same held-out frames. Time is normalized once over the full
recording to avoid numerical conditioning differences.

| Null | Shape | Free parameters |
|---|---|---:|
| `N0_CONSTANT` | constant carrier | 1 |
| `N1_AFFINE` | constant plus linear drift | 2 |
| `N2_QUADRATIC` | quadratic polynomial | 3 |
| `N3_BOUNDED_CUBIC` | cubic polynomial constrained to stay in the recorded RF band at all evaluated frame centers | 4 |

Fits use deterministic least squares. If the constrained cubic has tied
calibration minima, the minimum Euclidean coefficient norm is selected. A
null may not consume the nominal trajectory, the primary holdout, the witness
waterfall or the replication reserve during fitting. The historical witness
TLE is a declared mismatch stress case, not `N4` and not a post-outcome rescue.

## Detector-development and transform policy

No detector parameter is selected in this task. One later, separately
authorized pass over the 2026-02-08 development fixture may choose and test:

- deterministic conversion of interleaved `ci16_le` to complex samples;
- fixed channel center, passband, FIR/decimation and group-delay handling;
- STFT window, FFT length, hop and effective native bin spacing;
- generic spectral-contrast, continuity, maximum-slew and gap rules;
- ridge ambiguity and minimum-duration thresholds;
- treatment of clipping, DC/LO artifacts and missing samples.

The detector may use the development fixture's labels and known nominal
carrier, but it may not optimize against the 2026-02-09 or 2026-02-13 IQ. Its
primary ridge selector must be orbital-model blind: it receives IQ, sample
rate, center frequency and frozen detector parameters, but no TLE, predicted
Doppler curve, orbital residual or null score. A ridge closest to the orbit is
not an admissible selection rule. If more than one candidate survives without
a predeclared tie-break, the outcome is `RIDGE_NOT_ADMITTED`.

Before primary access, a strict-JSON detector manifest must bind all of the
above, the exact source commit, numerical thresholds, floating-point/dsp
versions, frame-to-time convention and one effective frequency-resolution
bound `R_f`. The manifest is SHA-256 hashed. After that hash is frozen there is
no parameter, code, channel, threshold or transform change for the primary.
The current `detector_manifest_sha256 = null` is an expected pre-development
blocker, not permission to tune on primary.

Transform ledger for the primary must be exactly:

```text
original SigMF bytes + sidecar
  -> ci16_le complex samples
  -> frozen deterministic channel/filter/decimation
  -> frozen STFT with explicit center-sample UTC and RF-bin coordinates
  -> model-blind ridge admission/extraction
  -> frequency(t) plus resolution/gap mask
  -> calibration-only nuisance/null fits
  -> unchanged held-out predictions and scores
```

Resampling, overlap and interpolation must be recorded. Zero padding may
interpolate a spectrum but cannot be reported as native resolution. Amplitude
normalization may not change the frequency axis. Any discontinuity splits the
stream; gaps are never interpolated across.

## Detectability and held-out scoring

This is a non-probabilistic comparison. Once `R_f` and `B_t` exist, all values
below are computed before primary IQ analysis:

- direct timing envelope `E_t`: maximum nominal-frequency departure over
  trajectories propagated at `t-B_t` and `t+B_t`, evaluated on the frozen
  frame grid;
- single-station orbital signature: held-out peak-to-peak span remaining after
  the calibration-prefix affine projection;
- detectability threshold: `3 * R_f + 2 * E_t`;
- orbital held-out tolerance: `2 * R_f + E_t`;
- required orbital-over-best-null RMSE margin: `R_f`.

No calibrated probability is claimed. The nominal TLE receives zero invented
element-error allowance: this does **not** assert that its error is zero; it
means the tested hypothesis is that exact element set. The predeclared
sensitivity TLE is reported alongside the result to expose model fragility but
does not widen tolerance or replace the nominal model.

Scores are RMSE in hertz on the identical admitted, visible held-out frames.
Calibration residuals are diagnostics only. Held-out samples may not alter a
nuisance, null coefficient, detector threshold, measurement envelope or
visibility rule.

## Exact future artifact procedure

Primary execution, if later authorized and unblocked, performs exactly one
HTTP `GET` of the original `.sigmf-data` into a quarantine file:

1. verify the committed plan and detector-manifest hashes before the request;
2. stream one download while computing SHA-256, but do not invoke any decoder;
3. close the file and emit URL, retrieval UTC, response headers, byte count,
   original SHA-256 and the already frozen sidecar SHA-256;
4. require exactly `1,869,440,000` bytes and a whole number of four-byte
   complex samples; mismatch yields `MEASUREMENT_INVALID`;
5. only after the hash receipt exists may the frozen decoder open that same
   file;
6. after the single outcome, destroy the IQ file and retain only hashes,
   transform receipts and derived non-IQ results.

An interrupted or inconsistent download is not silently retried, repaired by
range requests or replaced with another mirror. It yields
`MEASUREMENT_INVALID`. The reserve is not opened.

## Outcome semantics

Evaluation stops at the first applicable outcome in this order:

1. `MEASUREMENT_INVALID`: byte/hash/format/sample-clock continuity or required
   transform receipt fails. This makes no orbital statement.
2. `ORBITAL_SIGNATURE_NOT_DETECTABLE`: the precomputed nonlinear signature
   does not clear the frozen `3 R_f + 2 E_t` envelope on the usable geometry.
3. `RIDGE_NOT_ADMITTED`: measurement is valid, but the model-blind frozen
   detector does not yield one sufficiently continuous, unambiguous ridge.
4. `ORBITAL_PREDICTION_REJECTED`: an admitted ridge exists, but nominal-orbit
   held-out RMSE exceeds `2 R_f + E_t`.
5. `ORBITAL_MODEL_NOT_DISCRIMINATIVE`: the orbital prediction is within its
   tolerance but fails to beat every frozen null by at least `R_f`.
6. `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`: the signature is detectable, the
   nominal orbital prediction is admissible, and it beats every frozen null by
   at least `R_f`.

`ORBITAL_PREDICTION_REJECTED` rejects the frozen model/element/transform chain;
it does not identify whether elements, transmitter stability, timing or
propagation caused the failure. `PREDICTIVELY_PREFERRED` says that one
predeclared orbital curve predicted one held-out ridge better than the frozen
nulls. It does not prove spacecraft identity, orbit correctness in general,
emitter location, causal independence of SatNOGS, or absence of transmitter
frequency dynamics.

The OK2KVL record is an independent hardware-root presence witness only. Its
API metadata says station 3109, `48.987357 N, 17.178515 E`, observation
`07:07:55Z`–`07:13:31Z`, status `good`, waterfall status `with-signal`, and
`437,050,000 Hz`. SatNOGS products may contain Doppler correction or other
model-conditioned transforms. Without a complete transform ledger and raw
time series, its pixels cannot enter frequency residuals, null scores, timing
calibration or identity inference.

## Stop condition and blockers

The prospective plan is complete and its invariants are tested. Work stops
before detector development and before every IQ access.

Before the development fixture may be touched:

- separate explicit authority for the 2026-02-08 IQ;
- continued prohibition on primary and reserve access.

Before the primary may be touched:

- a defensible finite `B_t`, grounded in same-path metadata/calibration or
  applicable source documentation rather than an assumed PPS number;
- a detector manifest developed only on the 2026-02-08 fixture, hashed and
  committed;
- confirmation that this plan's commit and plan hash are unchanged;
- separate explicit authority for the one primary download.

If the finite timing interval cannot be established, the experiment remains
`PROSPECTIVE_PLAN_BLOCKED`. It must not be converted to an easier claim, a
current-TLE analysis or an adaptively aligned ridge test.
