# Historical raw-IQ timing search

Date: 2026-08-19

This is a bounded, metadata-only search inside the existing forward orbital
work.  It is not a new gate or a receiver catalog.  No IQ file was downloaded,
decoded, ranged, or opened.  In particular, the RSP-03 2026-02-09 primary and
2026-02-13 reserve remain unopened.

## Admission rule

A candidate may enter role selection only when the public record establishes:

1. an ADC-referenced sample-zero UTC and a finite numerical error bound;
2. a disciplined sampling clock or a declared sample-rate accuracy;
3. complex samples before any measurement-derived Doppler correction, or an
   exactly reversible receiver deramp whose complete ledger accompanies every
   sample block;
4. a historical trajectory source independent of the measured ridge;
5. a versioned, hashable artifact and usable data license.

`ADMIT_TO_ROLE_SELECTION` below is not `PLAN_FROZEN` and does not authorize an
IQ download.  The exact two-way predictor, detector, split, nulls, and transform
must still be frozen before a development artifact is materialized.

## Why DSN RSR is materially different

The DSN Radio Science Receiver (RSR) is not merely a file with a civil-time
label.  Its specification says that processing-pipeline delays are compensated,
the first-sample tag denotes when the sample was created by the DIG ADC, later
samples advance by the sample period, and RSR time tags are accurate to
`100 ns`.  The station Frequency and Timing Subsystem distributes references
traceable to UTC and uses hydrogen-maser/cesium standards.

RSR output is complex I/Q in one-second SFDUs.  A predicted-frequency NCO is
part of the receiver downconversion, so these are not fixed-LO, untouched RF
samples.  They are nevertheless pre-residual, pre-ridge samples: every SFDU
contains the RF-to-IF LO, DDC LO, NCO phase/frequency polynomials, sample rate,
and time tag needed to reverse the deramp and recover sky frequency:

```text
sky frequency = RF-to-IF LO + DDC LO - NCO frequency + residual frequency
```

No measured ridge or post-recording Doppler correction is used by that inverse
transform.  Failure of any required SFDU field will be a future measurement
refusal; it cannot be filled from the orbital model.

All three admitted products are MAVEN Level-0 RSR records.  `NORAD 39378` is
only MAVEN's Earth-launch catalog identity; a terrestrial TLE is not used at
Mars.  The historical orbital source is the reconstructed NAV-team SPICE SPK:

- 2016 February: `maven_orb_rec_160101_160401_v1.bsp`;
- 2016 July: `maven_orb_rec_160701_161001_v1.bsp`.

The corresponding DSN station coordinates are taken from the station reference,
not inferred from RF.

## Discriminability screen

The following screen exists only to rank metadata-qualified products.  It is
not the prospective model and is not a detector freeze.

- source: JPL Horizons target `-202` and the documented DSN station location;
- grid: direct trajectories at one-minute cadence;
- nominal downlink scale: `8,445,540,000 Hz`;
- provisional transform: a one-second complex FFT would have `R_f = 1 Hz`;
- split: first 20 percent calibration, remaining 80 percent held out;
- signature: held-out peak-to-peak remainder after extrapolating the
  calibration-prefix affine fit;
- two-way screening proxy: twice the received-path geometric Doppler;
- timing envelope: direct `t-B_t` and `t+B_t` trajectory samples;
- provisional detectability rule: `signature > 3 R_f + 2 E_t`.

The factor-of-two proxy is used only for ordering.  It omits the finite
round-trip light time and time-varying uplink ramp and therefore is not an
authorized primary prediction.  Before any IQ access it must be replaced by a
frozen coherent two-way light-time solution using the archived uplink-frequency
product, the `880/749` turnaround ratio, reconstructed SPICE state, and the
station at transmit and receive times.  Reported maximum timing errors are
honest one-minute direct-trajectory brackets, not interpolated point estimates.

## Candidates after timing admission

### 1. MAVEN / NORAD 39378 — DSS-35, 2016-02-26

- **Station:** DSS-35 Canberra, latitude `-35.39579552 deg`, longitude
  `148.98145580 deg`, WGS-84 height `694.897 m`.
- **Artifact UTC / duration:** `2016-02-26T20:00:01Z` through
  `20:34:59Z`, `2,098 s`.  Ranked science interval:
  `20:00:01.25Z`–`20:17:24.75Z`, `1,043.5 s`, ingress.
- **Carrier:** coherent X-band; approximately `8.4 GHz` downlink from a
  `7.2 GHz` uplink multiplied by `880/749`.  `8,445,540,000 Hz` is only the
  metadata-screen scale; exact instantaneous sky frequency is recovered from
  the future SFDU ledger and uplink ramp.
- **Format / sample rate:** DSN RSR SFDU, 16-bit I plus 16-bit Q; selected
  subchannel `1,000 complex samples/s`.
- **Timing architecture / bound:** DSN UTC-traceable atomic Frequency and
  Timing Subsystem; pipeline-compensated DIG-ADC first-sample tag;
  **`|timestamp - ADC event time| <= 100 ns`**.
- **Sample-rate discipline:** station atomic reference; per-SFDU integer sample
  rate and sample period.  No file-local oscillator-health exception is noted
  in the overview.
- **Doppler provenance:** reversible predicts-driven NCO deramp; no
  measurement-derived Doppler/ridge correction in Level 0.
- **Historical elements:** reconstructed NAV-team SPICE
  `maven_orb_rec_160101_160401_v1.bsp` available.
- **Artifact identity:** PDS LIDVID version `1.0`, `8,941,740 bytes`, published
  MD5 `3f133379bd322d4660ebc0a3da4d9f3a`.  A SHA-256 would be computed only on a
  future authorized complete materialization.
- **License:** NASA-led mission data, CC0 unless marked otherwise; no
  restrictive notice was found in the product/bundle metadata.
- **Predicted held-out screen:** `55,136.123 Hz` affine-residual peak-to-peak;
  `26,298.858 Hz` held-out RMS; `46,005.597 Hz` total proxy span.
- **Maximum admissible timing error:** `240 s <= B_t,max < 300 s` on the direct
  one-minute, `R_f=1 Hz` screen.  The documented `100 ns` is over nine orders
  of magnitude smaller than the conservative admitted endpoint.
- **Decision:** **`ADMIT_TO_ROLE_SELECTION`**, rank 1.

### 2. MAVEN / NORAD 39378 — DSS-55, 2016-07-05

- **Station:** DSS-55 Madrid, latitude `40.42429590 deg`, longitude
  `355.74736670 deg` east (`-4.25263330 deg`), WGS-84 height `819.061 m`.
- **Artifact UTC / duration:** `2016-07-05T21:35:01Z` through
  `22:04:59Z`, `1,798 s`.  Ranked science interval:
  `21:42:22.25Z`–`21:56:13.25Z`, `831 s`, ingress.
- **Carrier, format, timing, sample-rate discipline, and reversible NCO
  provenance:** the same RSR mechanism as candidate 1; selected subchannel
  `1,000 complex samples/s`.
- **Historical elements:** reconstructed NAV-team SPICE
  `maven_orb_rec_160701_161001_v1.bsp` available.
- **Artifact identity:** PDS LIDVID version `1.0`, `7,663,740 bytes`, published
  MD5 `2a927244b4829ea7c9e1fdb1f93a5534`; NASA/CC0 rule applies.
- **Predicted held-out screen:** `12,018.286 Hz` affine-residual peak-to-peak;
  `6,172.654 Hz` held-out RMS; `52,017.395 Hz` total proxy span.
- **Maximum admissible timing error:** `60 s <= B_t,max < 120 s` on the direct
  one-minute, `R_f=1 Hz` screen; documented bound `100 ns`.
- **Decision:** **`ADMIT_TO_ROLE_SELECTION`**, rank 2.

### 3. MAVEN / NORAD 39378 — DSS-45, 2016-07-12

- **Station:** historical DSS-45 Canberra, latitude `-35.39845768 deg`,
  longitude `148.97768563 deg`, WGS-84 height `674.347 m`.
- **Artifact UTC / duration:** `2016-07-12T12:42:01Z` through
  `13:00:00Z`, `1,079 s`.  Ranked science interval:
  `12:42:01.25Z`–`12:54:17.25Z`, `736 s`, ingress.
- **Carrier, format, timing, sample-rate discipline, and reversible NCO
  provenance:** the same RSR mechanism as candidate 1; selected subchannel
  `1,000 complex samples/s`.
- **Historical elements:** reconstructed NAV-team SPICE
  `maven_orb_rec_160701_161001_v1.bsp` available.
- **Artifact identity:** PDS LIDVID version `1.0`, `4,600,800 bytes`, published
  MD5 `51ee5e4c95a42d7f477703c94a69b05c`; NASA/CC0 rule applies.
- **Predicted held-out screen:** `9,941.527 Hz` affine-residual peak-to-peak;
  `5,218.338 Hz` held-out RMS; `42,253.762 Hz` total proxy span.
- **Maximum admissible timing error:** `60 s <= B_t,max < 120 s` on the direct
  one-minute, `R_f=1 Hz` screen; documented bound `100 ns`.
- **Decision:** **`ADMIT_TO_ROLE_SELECTION`**, rank 3.

## Timing refusals retained as controls

### 4. GPS G12 / NORAD 29601 — EA4GPZ, 2022-03-27

- **Station:** antenna ECEF `(4,840,402, -312,932, 4,128,949) m`.
- **UTC / duration:** sample zero
  `2022-03-27T11:32:04.2147593125Z`; `15 s`.
- **Carrier / format / rate:** GPS L1 `1,575.42 MHz`, SigMF `ci16`,
  `4 Msps`, raw IQ.
- **Timing architecture:** USRP B205mini latched a GPSDO PPS; PC/NTP supplied
  the integer second.  GPS code/nav post-analysis estimated sample-zero GPS
  time and observed an `8.41 us` UHD-minus-GPS discrepancy.
- **Numerical bound:** **none**.  `8.41 us` is one observed discrepancy, not an
  upper bound.  The author also documents a free-running frequency reference,
  several microseconds of drift in ten seconds, unmodelled `50–100 ns`
  ionosphere, and extrapolation of the code solution back to sample zero.
- **Doppler correction:** none; raw pre-Doppler IQ.
- **Historical elements:** broadcast navigation file `hour0860.22n` was used.
- **Artifact / license:** Zenodo DOI `10.5281/zenodo.6394603`,
  `240,000,000 bytes`, MD5 `6b7f4676dacc0a39752dd6b4be9779d0`, CC-BY-4.0.
- **Predicted held-out signature / maximum admissible timing error:**
  `NOT_COMPUTED_AFTER_TIMING_REFUSAL`; the 15-second record also offers little
  suffix after a calibration prefix.
- **Decision:** **`REFUSED_NO_FINITE_ADC_UTC_BOUND_AND_UNDISCIPLINED_SAMPLE_CLOCK`**.

### 5. DSCOVR / NORAD 40390 — Dwingeloo, 2022-09-29

- **Station:** Dwingeloo 25 m, latitude `52.8120194 deg`, longitude
  `6.3961694 deg`, metadata altitude `60 m`.
- **UTC / duration:** sample zero `2022-09-29T13:02:36.102439Z`; `20 s`.
- **Carrier / format / rate:** `2,215 MHz`, SigMF `ci16_le`, `1 Msps`, raw IQ.
- **Timing architecture:** USRP B210, external reference and external time,
  `--pps`; metadata description `DSCOVR, White Rabbit`.  CAMRAS separately
  documents a White-Rabbit-distributed hydrogen-maser reference at Dwingeloo.
- **Numerical bound:** **none applicable to this capture**.  Neither the
  sidecar nor the cited White Rabbit work supplies a recording-specific bound
  from UTC/PPS through the B210 timestamp to the ADC sample.  A stable frequency
  reference cannot substitute for this absolute-time bound.
- **Doppler correction:** no per-file correction flag; raw IQ, with Horizons
  used for antenna pointing only.
- **Historical elements:** sidecar names Horizons solution
  `DSCO-2015-02-11-Nominal_withMCC.V0.1`, but supplies no immutable solution
  hash.
- **Artifact / license:** stable public URL, catalog size `76.3 MB`, CC-BY-4.0;
  no published complete-IQ checksum was found.
- **Predicted held-out signature / maximum admissible timing error:**
  `NOT_COMPUTED_AFTER_TIMING_REFUSAL`.
- **Decision:** **`REFUSED_NO_RECORDING_APPLICABLE_PPS_TO_ADC_BOUND`**.

## Recommended role structure

The bounded search did find time-qualified data.  The recommended structure is:

```text
DEVELOPMENT
  MAVEN 2016-07-12 DSS-45
  smallest artifact; still strongly discriminating

PRIMARY_HELD_OUT
  MAVEN 2016-02-26 DSS-35
  largest affine-resistant geometric screen and widest timing margin

SEALED_REPLICATION_RESERVE
  MAVEN 2016-07-05 DSS-55
  independent date, station and reconstructed pass; second-ranked screen
```

This is a role recommendation, not access authority.  Before any artifact is
opened, the minimum remaining work is entirely prospective and orbital:

1. replace the factor-of-two screen with one frozen coherent two-way
   light-time/ramp predictor and hash its SPICE, Earth-orientation, station and
   uplink-frequency inputs;
2. freeze the exact subchannel, science interval, calibration/holdout split,
   SFDU inverse-NCO transform, frequency resolution and existing null family;
3. require complete-file materialization and SHA-256 before decoding;
4. materialize **development only**, freeze a model-blind detector, then keep
   primary and reserve sealed until their separate authorities exist.

No free time phase is allowed.  The candidate-specific absolute-time nuisance
can be bounded by the documented `100 ns`; it may not be expanded after seeing
any ridge.

## Public sources

- [MAVEN ROSE archive SIS](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/document/maven_sis_ROSE-1.7.pdf)
- [DSN RSR science interface specification](https://pds-ppi.igpp.ucla.edu/data/mess-rs-raw/document-rs/dsn_0159_science_sis.pdf)
- [DSN Frequency and Timing](https://deepspace.jpl.nasa.gov/dsndocs/810-005/304/304C.pdf)
- [DSN station coordinates](https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301O.pdf)
- [MAVEN reconstructed SPK index](https://naif.jpl.nasa.gov/pub/naif/MAVEN/kernels/spk/)
- [MAVEN SPICE archive description](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/document/spiceds_v012.html)
- [MAVEN ROSE overview index](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/document/mvn_rse_ovw_v01_r29.csv)
- [2016-02-26 PDS label](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/02/mvn_rse_l0_rsr_20160226T200001_v01_r00.xml)
- [2016-07-05 PDS label](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/07/mvn_rse_l0_rsr_20160705T213501_v01_r00.xml)
- [2016-07-12 PDS label](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/07/mvn_rse_l0_rsr_20160712T124201_v01_r00.xml)
- [NASA science-data licensing](https://science.data.nasa.gov/about/license)
- [JPL Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html)
- [GPS L1 Zenodo record](https://zenodo.org/records/6394603)
- [GPS sample-zero timing analysis](https://destevez.net/2022/03/timing-sdr-recordings-with-gps/)
- [CAMRAS satellite IQ catalog](https://data.camras.nl/satellites/raw/)
- [CAMRAS DSCOVR sidecar](https://data.camras.nl/satellites/raw/camras-2022_09_29_13_02_25_2215.000MHz_1.0Msps_ci16_le.sigmf-meta)
- [CAMRAS White Rabbit characterization](https://link.springer.com/article/10.1007/s10686-025-10038-4)
