# MAVEN/DSN RSR prospective plan

Status: **DSN_PROSPECTIVE_PLAN_BLOCKED**
Branch: `experiment/maven-dsn-rsr-prospective`
Scope: metadata and control products only. No RSR `.dat` payload was downloaded, opened, decoded, ranged, or sampled.

This is one scoped audit, not a new gate or archive adapter. The earlier approximate `2 x Doppler` curves are screening evidence only; none of their signatures, margins, windows, or timing limits enters this plan.

## Frozen roles

| Role | PDS LIDVID | Station | Label interval / records | RSR file, bytes, declared MD5 |
|---|---|---|---|---|
| Development | `urn:nasa:pds:maven.rose.raw:data.rsr:mvn_rse_l0_rsr_20160712t124201::1.0` | DSS-45 Canberra; 35.39845768 S, 148.97768563 E, 674.347 m | `2016-07-12T12:42:01Z`--`13:00:00Z`; 1080 | `mvn_rse_l0_rsr_20160712T124201_v01_r00.dat`; 4,600,800; `51ee5e4c95a42d7f477703c94a69b05c` |
| Primary held-out | `urn:nasa:pds:maven.rose.raw:data.rsr:mvn_rse_l0_rsr_20160226t200001::1.0` | DSS-35 Canberra; 35.39579552 S, 148.98145580 E, 694.897 m | `2016-02-26T20:00:01Z`--`20:34:59Z`; 2099 | `mvn_rse_l0_rsr_20160226T200001_v01_r00.dat`; 8,941,740; `3f133379bd322d4660ebc0a3da4d9f3a` |
| Sealed reserve | `urn:nasa:pds:maven.rose.raw:data.rsr:mvn_rse_l0_rsr_20160705t213501::1.0` | DSS-55 Madrid; 40.42429590 N, 4.25263330 W, 819.061 m | `2016-07-05T21:35:01Z`--`22:04:59Z`; 1799 | `mvn_rse_l0_rsr_20160705T213501_v01_r00.dat`; 7,663,740; `2a927244b4829ea7c9e1fdb1f93a5534` |

The product-label SHA-256 values observed in the same order are `a9b37dbc151e83106823d9da6edfa7bd135752caee1e950a3e6c3b551d82c014`, `d808f04228ae523373df9c289d4d10f649f36911129aae2a89253e73db8bff9e`, and `d9c9ccb0cf56d812eeb0167259ca1cb81572cdc31025e9f5aebd6cefcc79dd7b`.

Exact labels: [development](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/07/mvn_rse_l0_rsr_20160712T124201_v01_r00.xml), [primary](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/02/mvn_rse_l0_rsr_20160226T200001_v01_r00.xml), and [reserve](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/2016/07/mvn_rse_l0_rsr_20160705T213501_v01_r00.xml).

The overview proves two-way X/X, same uplink/downlink station, receiver `1B`, subchannel `1`, 1000 complex samples/s, 16 bits, HGA, telemetry off and ingress for all three. Polarization is **unknown**; receiver-name suffixes are not decoded as polarization. Sample rate is not treated as filter bandwidth or spectral resolution.

## Sample-zero and timing admission

The RSR specification directly states that the SFDU time tag denotes creation of the first sample by the DIG ADC, later samples advance by the sample period, DDC/FIR/record-task delays are compensated, and RSR time tags are accurate to 100 ns. This is the RSR-specific ADC link, not the separate DSN-wide inter-station reconstruction figure.

- **Timestamp representation:** integer UTC year/day/second plus sample index; at 1000 samples/s the grid is 1 ms.
- **Station UTC:** traceable to UTC(USNO), but no separate per-pass numerical station-clock allocation is in the sidecar.
- **ADC binding:** explicit in the RSR specification, including pipeline-delay compensation.

The planning bound is conservatively **1 microsecond end-to-end**, conditional on a structurally valid and continuous concrete SFDU header. It relaxes the documented 100 ns device claim and does not assert that station UTC error alone was measured as 1 microsecond. Clock envelopes must evaluate the full predictor at `t - 1 us` and `t + 1 us`, never local slope times error.

The label start is retained as metadata, not silently promoted into a verified sample-zero value; the concrete first SFDU header remains sealed.

## Occultation and media scope

PDS overview science intervals are ingress: development `12:42:01.25Z`--`12:54:17.25Z` (736.0 s), primary `20:00:01.25Z`--`20:17:24.75Z` (1043.5 s), and reserve `21:42:22.25Z`--`21:56:13.25Z` (831.0 s), on their respective dates. They are not yet a scoring window. A vacuum orbital prediction does not explain neutral-atmosphere or plasma refraction near ingress.

Applicable lineage exists for PDS troposphere, ionosphere, and weather:

- February TRO `...:mvn_rse_l3_tro_20160201t030000::1.0` MD5 `c19000b38edfeae71ed8c30fa8c026cd`; ION `...:mvn_rse_l3_ion_20160201t014700::1.0` MD5 `9235c6bf35fdf5f0c55e2a3b461d9643`.
- July TRO `...:mvn_rse_l3_tro_20160701t030000::1.0` MD5 `8917b004a0472a71d1c5d45e8f147d38`; ION `...:mvn_rse_l3_ion_20160701t000100::1.0` MD5 `2d873a92357385726a56ae2b5a279768`.
- DSCC weather W40 for DSS-35/45, MD5 `f4328a384bf1890f3a7476b4f53595d4`; W60 for DSS-55, MD5 `6366a72b2c5a4735c6dd7edf192a1249`.

No media value enters the current predictor. An admitted run would need a pre-occultation vacuum interval or a separately frozen media-corrected scope.

## Exact control and tracking products

Each FUP table is a piecewise-linear Earth-transmit ramp with `ETT` UTC, `DFUPDT` in Hz/s and `FUP` in Hz. Each label says that the values were extracted from the Tracking and Navigation File (TNF). The exact ramp is frozen by LIDVID and content hash:

| Role | FUP LIDVID | Coverage / records | Table MD5 | Table SHA-256 |
|---|---|---|---|---|
| Development | `urn:nasa:pds:maven.rose.calibrated:calibration.fup:mvn_rse_l2_fup_20160712t082035::1.1` | `08:20:35Z`--`16:16:57Z`; 112 | `49c2d890e67aab83336544e4ba58c573` | `f06d91a4c88c54e72eaec8caebe705c1c15aacace3fe3df107531b9f4b589286` |
| Primary | `urn:nasa:pds:maven.rose.calibrated:calibration.fup:mvn_rse_l2_fup_20160226t161513::1.1` | `16:15:13Z`--`2016-02-27T00:45:47Z`; 138 | `73d5f997f0b888a7bd5477fffadbcfcb` | `7eecad1c21dd58a8cd3b45d43ab62c65fd1afc05795c1d6adb24077ccdc261e4` |
| Reserve | `urn:nasa:pds:maven.rose.calibrated:calibration.fup:mvn_rse_l2_fup_20160705t155112::1.1` | `15:51:12Z`--`2016-07-06T00:35:23Z`; 125 | `2298f909c583bb9014035f144e953fd1` | `dfe891790f1d8ec955ae5ba2796c15bf450473bf8f3e50738c7b342645b59d6` |

Within a row's validity interval the immutable rule is `f_up(t) = FUP + DFUPDT * (t - ETT)`. No nominal carrier replaces these ramps.

Source TNF products:

| Role | TNF LIDVID | Coverage | MD5 |
|---|---|---|---|
| Development | `urn:nasa:pds:maven.rose.raw:data.tnf:mvn_rse_l0_tnf_20160712t082027::1.0` | `08:20:27Z`--`16:20:01Z` | `74468bf69628e38244eeabb57bab6f47` |
| Primary | `urn:nasa:pds:maven.rose.raw:data.tnf:mvn_rse_l0_tnf_20160226t161511::1.0` | `16:15:11Z`--`2016-02-27T00:55:01Z` | `4655a2f6588d96768729241a12c362e6` |
| Reserve | `urn:nasa:pds:maven.rose.raw:data.tnf:mvn_rse_l0_tnf_20160705t155104::1.0` | `15:51:04Z`--`2016-07-06T00:45:00Z` | `134d546ae4a1b793c14d069774ded25f` |

No ODF is linked by the RSR or FUP labels. TNF is the demonstrated tracking input. Matching DLF predicted-frequency products are lineage/cross-checks, never the independent orbital model: development `urn:nasa:pds:maven.rose.raw:calibration.dlf:mvn_rse_l2_dlf_20160712t033242::1.0` MD5 `9c8e0f5537e2000cca4c20e96c784737`; primary `urn:nasa:pds:maven.rose.raw:calibration.dlf:mvn_rse_l2_dlf_20160226t125711::1.0` MD5 `f5f9c727dad8c85b0d43c70f711713b5`; reserve `urn:nasa:pds:maven.rose.raw:calibration.dlf:mvn_rse_l2_dlf_20160705t163511::1.0` MD5 `a9804e14bdff57783461a55c99179fd2`.

## Receiver channel and NCO transform

The RSR architecture is shared analog IF and 256 Msps DIG ADC, a DDC producing a nominal 16 MHz complex channel, and a VDP FIR subchannel. Concrete FIR bandwidth/coefficients and exact decimation are **unknown**.

The PDS label proves that every SFDU contains these fields, but not their concrete values:

- DDC LO and RF-to-IF LO;
- predicts time shift, override flag/value, frequency rate and frequency offset;
- subchannel frequency offset;
- RF points 1--3 and subchannel frequency points 1--3;
- frequency coefficients `F1`--`F3`, accumulated phase and phase coefficients `P1`--`P4`.

For millisecond `m=0..999`, `F_NCO(m) = F1 + F2*((m+0.5)/1000) + F3*((m+0.5)/1000)^2`. The recorded frequency follows the inverse documented RSR relation: `f_baseband = f_sky - RF_to_IF_LO - DDC_LO + F_NCO`.

Override/rate/offset controls are not added again because their effect is already embodied in the SFDU NCO coefficients. Phase polynomials are required for a later phase-continuity audit, not for the frequency-only kernel.

**Frequency-transform admission: BLOCKED.** All concrete LO, NCO, override, filter and decimation values are inside unopened RSR SFDU headers; none is in the sidecar. A nominal X-band LO or assumed decimation would be invented data.

## SPICE set and independence classification

Archived 2016 meta-kernels identify the date-covering lineage:

- Primary: `maven_2016_v01.tm` (created 2016-05-14), with `naif0011.tls`, `pck00010.tpc`, `maven_v09.tf`, `maven_ant_v10.ti`, `mvn_sclkscet_00027.tsc`, `de430s.bsp`, `mar097s.bsp`, `maven_struct_v00.bsp`, `maven_orb_rec_160101_160401_v1.bsp`, and reconstructed spacecraft/APP CKs covering 2016-02-26.
- Development/reserve: `maven_2016_v03.tm` (created 2016-11-11), with `naif0012.tls`, the same planetary/frame/structure family, `mvn_sclkscet_00034.tsc`, `maven_orb_rec_160701_161001_v1.bsp`, and reconstructed CKs covering each July date.

The February SPK LIDVID is `urn:nasa:pds:maven.spice:spice_kernels:spk_maven_orb_rec_160101_160401_v1.bsp::1.0` (MD5 `b18e714a7902edf78ec23abbbd407ca4`); the July SPK is `...:spk_maven_orb_rec_160701_161001_v1.bsp::1.0` (MD5 `d89d705e3304b8cb9c1169be0f2ecbab`). Their labels say NAIF merged weekly **reconstructed** SPKs produced by the MAVEN NAV team.

The archive documents a predicted-SPK naming family, but its present collection contains no predicted SPK covering these 2016 dates. The date-covering spacecraft SPKs are reconstructed and were published after the observations. No source establishes that their orbit solutions excluded the target pass's DSN tracking. Classification:

`RECONSTRUCTED; TARGET_PASS_ASSIMILATION_NOT_EXCLUDED; NOT_AN_INDEPENDENT_PROSPECTIVE_ORBIT`.

The meta-kernels also do not freeze a historical DSN station SPK/Earth-orientation set for DSS-35/45/55. Coordinates above are from DSN 810-005 module 301, not an admitted historical station kernel.

## Two-way causal ledger

The only implemented numerical path is [`maven_dsn_two_way.py`](./maven_dsn_two_way.py):

1. Evaluate the exact FUP ramp at Earth transmit time.
2. Solve uplink light time directly from station and MAVEN states.
3. Apply the one-way relativistic kinematic frequency ratio.
4. Apply the coherent MAVEN X-band turnaround ratio `880/749`.
5. Solve downlink light time and its frequency ratio to the receiving station.
6. Produce received sky frequency.
7. Apply concrete per-SFDU RF-to-IF LO, DDC LO and millisecond NCO to produce predicted recorded baseband.

The kernel does not hide UTC/TDB conversion, gravitational light-time terms, Earth orientation, neutral atmosphere, ionosphere, interplanetary plasma, Mars refraction, station hardware delay, or transponder delay. They remain explicit open ledger entries rather than zeros in an admitted run.

## Frozen null families

Both nulls receive the identical event-time grid, FUP artifact, turnaround ratio, timing bound, per-SFDU LO/NCO/override state, FIR/decimation ledger and baseband transform:

1. **`N_RAMP_NCO_ONLY`** retains the nominal solved transmit epoch but sets both geometric frequency-transfer factors to one. It asks whether ramp plus receiver tracking alone explains the ridge.
2. **`N_MARS_CENTER_GEOMETRY`** replaces MAVEN's Mars-relative orbital state with a frozen Mars-center state while retaining Earth--Mars light time, station rotation, the same ramp and receiver transform. It destroys spacecraft orbital geometry without replacing controls.

No null may be refit after RSR access. The exact geometry-destroying state source cannot yet be selected because the nominal independent SPICE source is not admitted.

## Detectability and stop result

The conservative timing bound is admitted at 1 microsecond, but no exact recorded-baseband signature, null divergence, filter response, detectability margin, or maximum admissible timing error is reported. Each requires sealed SFDU transforms and an outcome-independent historical trajectory. Reusing preliminary screening curves would violate the plan.

Exact blockers:

1. `NO_OUTCOME_INDEPENDENT_2016_MAVEN_TRAJECTORY`: reconstructed SPKs do not exclude assimilation of target-pass tracking.
2. `RSR_PER_SFDU_FREQUENCY_TRANSFORM_SEALED`: exact LO/NCO/control fields required for recorded baseband are only in unopened payload headers.
3. `RSR_FILTER_DECIMATION_UNKNOWN`: concrete response and decimation required for detectability are absent from the sidecar.
4. `HISTORICAL_DSN_STATION_GEOMETRY_NOT_FROZEN`: coordinates are documented, but exact historical Earth-orientation/station-kernel lineage is not admitted.

Development access is not authorized by this plan; primary and reserve remain sealed.

**DSN_PROSPECTIVE_PLAN_BLOCKED**

## Authoritative sources

- [MAVEN ROSE archive SIS](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/document/maven_sis_ROSE-1.7.pdf)
- [DSN RSR 0159 science SIS](https://pds-ppi.igpp.ucla.edu/data/mess-rs-raw/document-rs/dsn_0159_science_sis.pdf)
- [MAVEN RSR collection](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/rsr/)
- [MAVEN FUP collection](https://pds-ppi.igpp.ucla.edu/data/maven-rose-calibrated/calibration/fup/)
- [MAVEN TNF collection](https://pds-ppi.igpp.ucla.edu/data/maven-rose-raw/data/tnf/)
- [MAVEN SPICE archive description](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/document/spiceds_v012.html)
- [MAVEN SPICE SPK collection](https://naif.jpl.nasa.gov/pub/naif/pds/pds4/maven/maven_spice/spice_kernels/spk/)
- [DSN station locations, 810-005 module 301](https://deepspace.jpl.nasa.gov/dsndocs/810-005/301/301O.pdf)
