# Historical raw-IQ timing search

Date: 2026-08-19

Cassini one-way RSR pivot updated: 2026-08-20

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

## Historical MAVEN role structure and closure

The first bounded search found time-qualified MAVEN data and froze this
historical structure:

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

The DSS-45 development artifact was subsequently materialized and a model-blind
detector was frozen.  The available MAVEN trajectory was then confirmed to be a
post-pass reconstructed SPK.  It can support receiver/compiler development but
not an independent orbital prediction.  MAVEN is therefore closed as
`DEVELOPMENT_ONLY_FOR_TWO_WAY_RSR_COMPILER`.  DSS-35 primary and DSS-55 reserve
remain sealed and unchanged.

## Post-MAVEN independent-orbit pivot: Cassini one-way RSR

This second search was bounded to a single mechanism after the MAVEN closure.
Only three PDS4 XML labels, two NAIF SPK labels, and two predicted SPK files were
materialized.  No Cassini `.dat` payload was downloaded, ranged, decoded, or
opened.

The selected records are Saturn Gravity Science Experiment RSR products with
`NNN` uplink and X-band downlink.  They are therefore one-way Cassini-USO
observations rather than coherent two-way links.  This removes the uplink ramp
and turnaround-ratio compiler from the prospective causal path.  The RSR NCO
still applies a precomputed predicts-driven deramp; the per-SFDU frequency and
phase polynomials remain mandatory for exact inversion.

The Cassini Radio Science User's Guide states that this steering frequency was
precomputed from the predicted ephemeris supplied by navigation.  More
importantly, the concrete NAIF labels independently mark the candidate kernels
as `PRODUCT_VERSION_TYPE = "PREDICT"` and place their creation before the
recordings:

- `050426AP_SCPSE_05116_05216.bsp`: created
  `2005-04-26T11:10:12`, coverage `2005-04-26T11:04:46` through
  `2005-08-04T00:00:00`, SHA-256
  `065258e6982b10488604d97f02f9b5110d6b1e4760ff340211b50973ab8228f5`;
- `060901AP_SCPSE_06244_06255.bsp`: created
  `2006-09-01T09:44:12`, coverage `2006-09-01T09:37:45` through
  `2006-09-12T08:16:51`, SHA-256
  `0b7cc35d94b956602593106ed8aa62ce5f33cb178b8544036a841c5e53fc81dd`.

Both kernels include Cassini, Earth and the planetary context needed by a
future one-way light-time predictor.  Their predicted status is not inferred
from filename syntax.  It is explicit in the producer labels.  No
reconstructed Cassini SPK may replace either kernel after a prospective plan is
frozen.

### Shared measurement admission

- Product class is raw DSN RSR complex I/Q in one-second SFDUs.
- Each selected product contains exactly `1,000` I/Q pairs per record and one
  record per second, hence `1,000 complex samples/s` for the selected
  subchannel.
- The container exposes 16-bit I and Q words.  Actual sample resolution is a
  per-SFDU header field and remains **unknown before header access**.
- Pipeline-compensated first-sample UTC is bound to DIG-ADC sample creation;
  the RSR timing specification gives `100 ns` accuracy.
- Downlink is one-way X-band, RCP.  The mission band table gives approximately
  `8,425 MHz`; the exact received sky-frequency coordinate remains a function
  of the unopened RF-to-IF, DDC-LO and NCO header fields.
- No measurement-derived Doppler correction is present.  The predicts-driven
  NCO is a known receiver transform, reversible only if the complete header
  ledger is admitted.
- PDS4 version is `1.0`; each label states that the PDS3 data bytes were not
  changed during migration.  Published artifact MD5 values provide immutable
  remote identity; a future authorized materialization must add full-file
  SHA-256 before decoding.

### Role-selection discriminability screen

JPL Horizons current geometry was used only to rank the already admitted
records.  It is reconstructed/operational screening output and is prohibited
from the prospective predictor.  The screen used:

- one-way topocentric range-rate at a provisional `8.4 GHz` scale;
- one-minute geometry points and the documented DSN station coordinates;
- first 20 percent as an affine calibration prefix and the remaining 80
  percent as held out;
- peak-to-peak held-out residual after extrapolating that frozen affine;
- provisional `R_f = 1 Hz` solely for admission screening;
- direct `t-B_t` and `t+B_t` trajectory envelopes, never local
  slope-times-error;
- `signature > 3 R_f + 2 E_t` as the conservative screen.

The resulting physical rank is:

| Rank | Product / station | Held-out residual p-p | Held-out RMS | Total Doppler span | Direct timing bracket |
|---:|---|---:|---:|---:|---:|
| 1 | `s23sags2006_251_1200nnnx14rd` / DSS-14 | `2,046.336 Hz` | `1,001.084 Hz` | `7,419.467 Hz` | `1,140 s <= B_t,max < 1,200 s` |
| 2 | `s11sags2005_157_1750nnnx26rd` / DSS-26 | `1,851.173 Hz` | `909.095 Hz` | `10,104.246 Hz` | `720 s <= B_t,max < 780 s` |
| 3 | `s10sags2005_122_1955nnnx14rd` / DSS-14 | `1,294.885 Hz` | `639.576 Hz` | `30,305.974 Hz` | `60 s <= B_t,max < 120 s` |

Even the weakest direct bracket exceeds the documented RSR time error by more
than eight orders of magnitude.  These numbers do not authorize a claim about
the predicted SPKs; they only show that exact predicted-SPK compilation is
worth doing.

### Exact candidate records

#### Development — DSS-26, 2005-06-06

- LIDVID:
  `urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:s11sags2005_157_1750nnnx26rd::1.0`;
- UTC: `2005-06-06T17:50:01Z` through `20:30:51Z`;
- station: DSS-26 Goldstone, latitude `35.33568922 deg`, longitude
  `243.12698351 deg` east, height `968.686 m`;
- file: `41,113,260 bytes`, `9,651` one-second records, published MD5
  `ce672e2258ffe8466389db36f9f6668f`;
- XML-label SHA-256:
  `b02dd0ff1aaa355fbe6faca191b898c91b2d99532864750ac6a50e30d93b70c1`;
- predicted orbit: `050426AP_SCPSE_05116_05216.bsp`.

This is the development role because it is a non-occultation one-way SAGR
track, has a large timing/discriminability margin, and uses a different
hardware root from the strongest primary candidate.

#### Primary held out — DSS-14, 2006-09-08

- LIDVID:
  `urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:s23sags2006_251_1200nnnx14rd::1.0`;
- UTC: `2006-09-08T12:00:01Z` through `15:00:00Z`;
- station: DSS-14 Goldstone, latitude `35.42590087 deg`, longitude
  `243.11046179 deg` east, height `1,001.390 m`;
- file: `46,008,000 bytes`, `10,800` one-second records, published MD5
  `378f601ddbc057ebdc822cdb5fac4197`;
- XML-label SHA-256:
  `185d43fe474484d1ef29957c603a63feaab9ac5426043d588fe33716e871ca58`;
- predicted orbit: `060901AP_SCPSE_06244_06255.bsp`.

It is the primary recommendation because it ranks first on held-out curvature
and on direct timing margin, while remaining independent of development in
date, station hardware, and predicted-orbit delivery.

#### Sealed reserve — DSS-14, 2005-05-02

- LIDVID:
  `urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:s10sags2005_122_1955nnnx14rd::1.0`;
- UTC: `2005-05-02T19:55:01Z` through `21:08:00Z`;
- station coordinates: the same DSS-14 values above;
- file: `18,658,800 bytes`, `4,380` one-second records, published MD5
  `9b8b89c1e3a15ad742c828b51224b85f`;
- XML-label SHA-256:
  `b17cf1f4470630894988b9694284fcda7bad115d59018a29a40fe496ede3c6c9`;
- predicted orbit: `050426AP_SCPSE_05116_05216.bsp`.

The reserve is a time-separated model replication, not a new station root: it
shares DSS-14 with the primary.  That limitation is explicit and may not be
promoted to independent-hardware corroboration.

### Offline one-way compiler and synthetic DSS-26 parser

The bounded offline implementation was completed without opening a real RSR
header, data record, or sample payload and without making any network request.
It produces no RF or orbital outcome. Its status is
**`OFFLINE_COMPILER_AND_SYNTHETIC_PARSER_READY`**.

The product-bound one-way compiler:

- requires SpiceyPy/CSPICE and has no Horizons, Skyfield, or reconstructed-SPK
  fallback;
- admits only the frozen LSK, historical Earth-orientation BPC, DSS station
  SPK, and pre-pass `050426AP_SCPSE_05116_05216.bsp` PREDICT kernel after exact
  byte-count and SHA-256 verification;
- converts RSR receive UTC to ET/TDB, solves the geometric one-way transmit
  epoch, obtains Cassini and DSS-26 SSB/J2000 states through CSPICE, and applies
  the exact flat-spacetime special-relativistic kinematic frequency factor;
- keeps the declared USO rest frequency, constant calibration offset, and
  aging rate in the emitter rest frame;
- emits a steering-only sky-frequency null with the same carrier, calibration,
  correction, timing, and receiver-control inputs as the orbital path.

The first implementation deliberately leaves the following as explicit
`OPEN_TERM` values rather than silently assigning zero: spacecraft/station
proper-time and gravitational frequency effects, relativistic propagation
delay, Earth troposphere, Earth ionosphere, interplanetary plasma, station
hardware delay, available media calibration, and any undeclared USO offset or
aging. Closing all sky-frequency terms is necessary but still insufficient
for a primary claim: a concrete header-derived RF/IF/NCO transform, detector
manifest, and detectability result are separately required. Consequently the
compiler's `primary_prediction_authorized` field is always false.

The new SFDU parser is intentionally separate from the MAVEN parser and is
bound only to the DSS-26 development identity ending in `2A1`. Before any
future header authorization it is tested only against specification-derived
synthetic 260-byte headers. It exposes first-sample UTC, station/RSR/channel/
subchannel, sample rate and actual sample resolution, RF-to-IF and DDC LO,
override state, frequency and phase polynomials, and filter/decimation state.
It rejects a complete 4,260-byte record and has no representation for ADC RMS,
ADC peak, signal strength, FGAIN, samples, or signal-derived diagnostics.
Unknown FIR coefficients remain unknown; no amplitude-response claim is made.

Frozen implementation identities:

- compiler source SHA-256:
  `f397ef8d35431793ef8151e460fd5f4914ee812221288d1152d952d98ff61b7b`;
- compiler manifest SHA-256:
  `c9cb25a632a10d8f52a3a8f624f962fdd61c412c1ba5b146e6d750525680792b`;
- parser source SHA-256:
  `0ac072250ce681555a23737821302588daa89ee92e53c8216073e24de04a6830`;
- parser manifest SHA-256:
  `d77a9f96cd0290a8f22c97e12441d6d324be1944492ef180f90347e8d569eb83`.

The initial focused synthetic suite passed `18` tests, and the complete orbital
suite passed `113`. An isolated SpiceyPy `7.0.0` runtime subsequently loaded
the four frozen kernels after all byte counts and SHA-256 values matched. With
a unit rest-frame carrier, zero declared calibration offset and aging, and all
physical media/hardware terms still open, the kernel-bound regression is:

| Receive UTC | Geometric light time | Kinematic frequency factor |
|---|---:|---:|
| `2005-06-06T17:50:01Z` | `4,907.510879427195 s` | `0.9999299036421737` |
| `2005-06-06T19:10:26Z` | `4,907.850356847048 s` | `0.9999293648478778` |
| `2005-06-06T20:30:51Z` | `4,908.192765682936 s` | `0.9999286935663851` |

The factor changes by approximately `-1.2100757886e-6`; scaling that only for
comparison by the provisional `8.425 GHz` screening carrier gives about
`-10.195 kHz`. This is diagnostic, not an asserted Cassini USO frequency. An
opt-in test re-verifies all kernel identities and reproduces the three points.
With that exact kernel set present, the complete orbital suite passes `114`
tests.
The remaining blocker is the concrete USO calibration and header-derived
RF/IF/NCO ledger, followed by bounds or claim-scope exclusions for every open
term. Development IQ, primary, and reserve remain unopened.

### Decision and remaining blocker

Outcome: **`TIME_AND_ORBIT_QUALIFIED_DATASET_FOUND`**.

The recommended structure is:

```text
DEVELOPMENT       Cassini SAGR 2005-06-06 DSS-26
PRIMARY_HELD_OUT  Cassini SAGR 2006-09-08 DSS-14
SEALED_RESERVE    Cassini SAGR 2005-05-02 DSS-14
```

This is not access authority and no role is yet sealed by a prospective plan.
The next minimum step is offline: compile the exact one-way received-sky and
recorded-baseband curves from the two pre-pass predicted SPKs, Earth
orientation/station kernels and the RSR inverse-NCO header contract; then
freeze detector inputs, split and nulls before materializing development.

The immediate software blocker is narrow and physical: the installed Skyfield
reader does not support the type-1 Cassini spacecraft segment.  A future
compiler must use a validated SPICE implementation that supports that segment;
it may not substitute Horizons or a reconstructed trajectory.  Exact sample
resolution, NCO override state and frequency-polynomial continuity also remain
unknown until a separately authorized, amplitude-blind development-header
spike.  Primary and reserve must remain unopened throughout both steps.

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
- [Cassini Radio Science User's Guide](https://pds.nasa.gov/data/pds4/misc/document_cassini/Cassini_Radio_Science_Users_Guide_30Sep2018.pdf)
- [Cassini SAGR bundle](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/inst-rss_curr.html)
- [Cassini operational SPK directory](https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/)
- [DSS-26 development label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2005/s11sags2005_157_1750nnnx26rd.xml)
- [DSS-14 primary label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2006/s23sags2006_251_1200nnnx14rd.xml)
- [DSS-14 reserve label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2005/s10sags2005_122_1955nnnx14rd.xml)
- [2005 predicted-SPK label](https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/050426AP_SCPSE_05116_05216.bsp.lbl)
- [2006 predicted-SPK label](https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/060901AP_SCPSE_06244_06255.bsp.lbl)
- [GPS L1 Zenodo record](https://zenodo.org/records/6394603)
- [GPS sample-zero timing analysis](https://destevez.net/2022/03/timing-sdr-recordings-with-gps/)
- [CAMRAS satellite IQ catalog](https://data.camras.nl/satellites/raw/)
- [CAMRAS DSCOVR sidecar](https://data.camras.nl/satellites/raw/camras-2022_09_29_13_02_25_2215.000MHz_1.0Msps_ci16_le.sigmf-meta)
- [CAMRAS White Rabbit characterization](https://link.springer.com/article/10.1007/s10686-025-10038-4)
