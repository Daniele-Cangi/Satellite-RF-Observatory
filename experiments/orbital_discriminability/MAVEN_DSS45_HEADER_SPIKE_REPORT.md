# MAVEN DSS-45 metadata-only RSR header spike

Status: **READY_FOR_DSS45_DEVELOPMENT_IQ**
Scientific scope: **DEVELOPMENT_ONLY_FOR_TWO_WAY_RSR_COMPILER**

Only the DSS-45 development product was accessed. No IQ or signal-derived
value was decoded. DSS-35 primary and DSS-55 reserve remain sealed: their data
products were not requested, ranged, opened or hashed.

## Bounded access receipt

The frozen plan requested 75 headers from record indices 0 through 736 at a
cadence of ten records, plus record 736. Each request had one exact 260-byte
range and was admitted only after HTTP 206, exact Content-Range and
Content-Length 260. A whole-product response would have been refused before
its body was read.

- Authorized bytes read: 19,500.
- Sample/data-CHDO bytes read: 0.
- Raw headers retained: 0.
- First tag: 2016-07-12T12:42:01.000000Z, RSN 1.
- Last tag: 2016-07-12T12:54:17.000000Z, RSN 737.
- Sampled RSN and first-sample-time continuity: complete.
- Whitelist-ledger SHA-256:
  4749dcfe6b94c038db323290ff68c33be1467c9c3632c199f42705e4c922a086.

The 260-byte in-memory buffer was zeroed after parsing. FGAIN, attenuation, ADC
RMS/peak, data-error count, raw header bytes and sample values have no field in
the receipt. Changing those diagnostic bytes leaves the receipt and whitelist
hash unchanged.

## Frozen parser and artifacts

- Parser contract: maven-dss45-rsr-header-whitelist-v1.
- Parser contract SHA-256:
  50de0005bb26317ec94c2816ac8465b48370fbce2db555a28801dffead89317e.
- Parser source SHA-256:
  14d722b70ed43fbd039982185331b8aa9b8f9e9f53c76ae2fc6c80c32dcc1266.
- Spike source SHA-256:
  33e36ce722ffbdced4f559e26851c608e60513e8ed3cf573d9a022bcca9e62eb.
- Standalone manifest SHA-256:
  df90255af923fd87a85da231764887052bf57686d0bc6a1aa72783fd7d3180d8.
- Result JSON SHA-256:
  161417730e00bcf259125655aadf5f1fb941d4d142ea56fb2060c70d5994b147.
- Runtime: Python 3.13.5, SpiceyPy 7.0.0, NumPy 2.5.2.

The documented hexadecimal not-calculable marker becomes an explicit JSON
state with null value. Other NaN or infinity encodings are refused; strict JSON
uses allow_nan false.

## Concrete receiver transform

All 75 headers agree on SPC 40, DSS-45, RSR ID 2 (RSR1B), sub-channel 1,
1,000 complex samples/s, 16-bit samples, RF-to-IF LO 8.100 GHz, DDC LO
346 MHz, override inactive, zero predicts control offsets and finite frequency
and phase polynomials.

DSN 0159-Science states that the VDP FIR receives the 16 Msps DDC stream and
that output bandwidth/sample-rate mode is selected from table 3-1. The 1 ksps
header mode therefore gives a 1 kHz output mode and decimation 16,000. Exact
FIR coefficients are not encoded and remain unknown.

For u=(millisecond+0.5)/1000:

    F_NCO = F1 + F2*u + F3*u^2
    P_NCO = P1 + P2*u + P3*u^2 + P4*u^3
    f_recorded = f_sky - f_RF-to-IF-LO - f_DDC-LO + F_NCO

Override/rate/offset state is retained but not added twice: its active effect is
already embodied in each record NCO polynomial.

## Frozen kernel lineage

| Kernel | Role | Bytes | SHA-256 | Independence |
|---|---:|---:|---|---|
| naif0012.tls | UTC to TDB | 5,257 | 678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b | time control |
| pck00010.tpc | body constants | 126,143 | 59468328349aa730d18bf1f8d7e86efe6e40b75dfb921908f99321b3a7a701d2 | model control |
| de430s.bsp | Earth/solar system | 4,364,288 | 488970e63ddc0537964431da007336005be0a79ad36b041471b8a043f6457787 | planetary ephemeris |
| mar097s.bsp | Mars system | 93,998,080 | cbe84c5d6830e2fa1086b8f71d51b811a94be9345d22a5cc94167489cfe65f38 | Mars ephemeris |
| maven_orb_rec_160701_161001_v1.bsp | MAVEN | 41,503,744 | 773c52db6b95a4af9f1ea1f9999d49f66da28d67fb8189ef64e11bce57256223 | reconstructed post-pass |
| earthstns_itrf93_050714.bsp | DSS-45 | 38,912 | 371fb58d19dd757de7b31cac80b5e61d5eaa26dc3437a009eece1c47792cee5c | station model created 2005 |
| earth_1962_260806_2126_combined.bpc | Earth orientation | 31,318,016 | cc87ad1a495cf598800ba403763d350f087ac0b97da9fec603278a3864c6a53e | reconstructed historical EOP |

Binary kernels were temporary and were removed after compilation. Immutable
URLs and hashes remain in the result JSON.

## Exact metadata-driven causal ledger

    SFDU first-sample UTC
      -> LSK UTC-to-TDB conversion
      -> DSS-45 ITRF93 station state and historical Earth orientation
      -> reconstructed MAVEN, Earth and Mars J2000 states
      -> solved uplink light time
      -> exact FUP at Earth-transmit epoch
      -> uplink geometric frequency factor
      -> coherent MAVEN 880/749 turnaround
      -> downlink geometric frequency factor
      -> received sky frequency
      -> per-SFDU RF/IF LO plus DDC LO minus NCO
      -> predicted recorded baseband
      -> VDP FIR 16 Msps to 1 ksps, decimation 16000

The exact development FUP has 6,272 bytes and SHA-256
f06d91a4c88c54e72eaec8caebe705c1c15aacace3fe3df107531b9f4b589286;
its PDS provenance is the development TNF.

## Compiled baseband curve

At the frozen 0.5005 s intra-record epoch:

| UTC record | Uplink Hz | Received sky Hz | NCO Hz | Baseband Hz |
|---|---:|---:|---:|---:|
| 12:42:01 | 7,188,705,956.260 | 8,445,512,904.773 | 487,122.626 | 27.398 |
| 12:48:11 | 7,188,698,123.569 | 8,445,522,205.606 | 477,832.369 | 37.975 |
| 12:54:17 | 7,188,687,447.553 | 8,445,534,654.666 | 465,396.143 | 50.809 |

Across all 75 metadata points, predicted baseband is 27.398273561 Hz to
50.808883286 Hz. The complete curve and same-transform ramp/NCO-only and
Mars-center null curves are in MAVEN_DSS45_METADATA_RESULT.json. They are
compiler-development products, not held-out evidence.

Open terms remain explicit: solar gravitational light time, neutral atmosphere,
ionosphere, interplanetary plasma, Mars occultation media, station hardware
delay, transponder delay and the unencoded FIR coefficient shape.

## Orbit-provenance result

One bounded official PDS/NAIF search found the predicted-SPK naming family but
no predicted or demonstrably pre-pass MAVEN trajectory covering 2016-07-12.
The date-covering product is reconstructed and was published after the pass.
No source excludes assimilation of target-pass tracking.

    SPK_INDEPENDENCE =
      RECONSTRUCTED_POST_PASS
      TARGET_PASS_ASSIMILATION_NOT_EXCLUDED
      NOT_AN_INDEPENDENT_ORBITAL_PREDICTION

    MAVEN_CLASSIFICATION =
      DEVELOPMENT_ONLY_FOR_TWO_WAY_RSR_COMPILER

The header path, RSR transform, station geometry and metadata compiler are
operational. This authorizes only a later, separately authorized DSS-45
development-IQ access. It does not authorize primary/reserve access and does
not turn the reconstructed curve into an independent orbital result.

**READY_FOR_DSS45_DEVELOPMENT_IQ**
