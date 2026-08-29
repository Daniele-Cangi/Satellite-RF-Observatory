# Bounded raw-RF time/orbit metadata audit

## Outcome

```text
NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL
```

No IQ sample, spectrum, waterfall or signal feature was used to reach this
outcome. The five-family boundary in
`RAW_RF_TIME_ORBIT_CANDIDATE_SCOPE.md` was not expanded and no prospective
experiment was synthesized.

The result is capability admission, not an orbital measurement. It says only
that none of the five predeclared public families simultaneously proves:

- raw complex samples before measurement-derived Doppler extraction;
- a finite numerical ADC-sample-zero to UTC bound;
- a disciplined frequency/sample-rate reference;
- a hashable pre-pass orbit authority independent of the target RF;
- enough immutable product identity to freeze later development, primary and
  reserve roles.

Missing quantities remain `UNKNOWN`. No held-out orbital-versus-null curve was
computed after a candidate failed an upstream admission clause.

## Physical question and information value

```text
Physical question:
Can one public raw-RF family test observer-coupled orbital frequency dynamics
without the GNSS PRN/RINEX measurement pipeline?

New information produced:
Within this bounded set, raw-IQ availability is not sufficient. The
controlling missing edge is product-specific event-time and orbit provenance,
not detector implementation.

Why existing experiments cannot answer it:
PIE/AMC operate on PRN-labelled GNSS phase; RSP-03 lacks absolute time; MAVEN
has only reconstructed orbit authority; and the Cassini paths are closed by
their frozen physical-envelope results.

Minimum experiment:
Metadata-only clause audit of exactly five frozen public families.

Stop condition:
Stop before samples when no family clears both time and independent-orbit
admission.
```

## Clause semantics

The audit distinguishes three different claims that are often collapsed:

1. **timestamp representation** — a file can encode fractional seconds;
2. **station time accuracy** — a maser, GPS PPS or White Rabbit link can be
   close to UTC;
3. **ADC binding** — the recorded time must identify sample zero through the
   complete receiver and packetization path with a finite numerical bound.

Only the third can bound an orbital trajectory at the recorded sample grid.
Likewise, a filename containing `OEM` or a date before the observation is not
an immutable orbit authority unless the exact bytes, lineage and uncertainty
can be frozen.

## Candidate results

### 1. Breakthrough Listen Voyager 1 / GBT SigMF

Concrete metadata product:
`blc07_guppi_57650_67573_Voyager1_pol1.sigmf-meta`.

- station: Green Bank Telescope; official NAD83 latitude
  `38 deg 25 min 59.236 sec N`, longitude
  `79 deg 50 min 23.406 sec W`; phase-center ellipsoid height is documented
  separately as approximately `824.55 m`;
- recording sidecar time: `Mon Sep 19 14:46:57 2016`, with no timezone token;
- carrier coordinate: `8,419,921,875 Hz` center, descending frequency order;
- format: SigMF `ci8_be`, one polarization per file;
- sample rate magnitude: `2,929,687.5 complex samples/s`;
- data object: `1,318,060,032 bytes`, corresponding to
  `224.948912128 s` for one `ci8` complex stream;
- raw-IQ state: `PRESENT_PRE_DOPPLER`; the published instrument applies an
  8-times-overlapped 512-channel PFB and complex requantization but does not
  Doppler-track the local oscillators;
- frequency architecture: ADC/FPGA clocks derive from a Valon synthesizer
  locked to the site 10 MHz hydrogen maser;
- time architecture: GPS-derived PPS arms the ROACH2 boards. The instrument
  paper explicitly retains cable delay and a stable `+/- 8` ADC-sample
  demultiplexing ambiguity. The GBT timing memo says SiteTime is kept within
  “a few microseconds” of UTC and documents backend cable delays, but does not
  state a numeric worst-case bound for this 2016 converted SigMF product;
- time semantics blocker: the timezone-free sidecar time is not sufficient to
  bind UTC. The filename convention also carries an MJD/seconds field whose
  relationship to the extracted SigMF sample zero is not declared in the
  sidecar;
- orbit authority: NAIF published
  `Voyager_1.a54206u_V0.2_merged.bsp` on 2015-01-21, before this recording, and
  it covers Voyager 1 through 2031. NAIF states that the post-flyby trajectory
  is a run-out of solutions made using earlier actual tracking data and warns
  that Voyager SPICE data require extreme caution. It is independent of this
  later GBT target RF, but no applicable numerical trajectory uncertainty was
  found;
- artifact identity: the SigMF metadata is SHA-256 bound, while the data
  object exposes length, last-modified and a non-cryptographic HTTP ETag. No
  published cryptographic checksum or data-specific license was found;
- role separation: two polarizations are the same observation and hardware
  root. Distinct development/primary/reserve observations were not established
  inside the frozen SigMF release.

Decision:

```text
REFUSED_ABSOLUTE_TIME_AND_ORBIT_UNCERTAINTY_BOUND_UNAVAILABLE
```

The orbit-only held-out signature is `NOT_EVALUATED_AFTER_TIME_REFUSAL`.

### 2. CAMRAS DSLWP-B public release v1.0

Concrete product: Zenodo record `10.5281/zenodo.3571330`, version `v1.0`.

- satellite: DSLWP-B, lunar-orbit amateur payload;
- product: decoded/raw telemetry frames (`raw_frame.csv`), image frames and
  JT4G messages;
- immutable identity: one `8.1 MB` zip with published MD5
  `ec30e1603dfc3f01735b46eb2625890e`;
- license: CC BY 4.0;
- raw-IQ state: `ABSENT`.

Decision:

```text
REFUSED_RAW_COMPLEX_SAMPLES_ABSENT
```

Timing, orbit and discriminability clauses are `NOT_EVALUATED` after the
physical observable required by this experiment is absent.

### 3. CAMRAS SLIM / LEV-1 landing SigMF

Concrete metadata product:
`slim_2024-01-19_16_25_47_437.200MHz_1.00Msps_ci16_le.chan0.sigmf-meta`.

- station: Dwingeloo Telescope at longitude `6.3961694 deg`, latitude
  `52.8120194 deg`, metadata altitude `60 m`;
- capture time representation: `2024-01-19T16:25:47.000`;
- carrier coordinate: `437,200,000 Hz`;
- format/rate: SigMF `ci16_le`, `1,000,000 complex samples/s`;
- data object: `2,347,200,000 bytes`, or `586.8 s` at four bytes per complex
  sample;
- raw-IQ state: `PRESENT_PRE_DOPPLER`;
- frequency reference: sidecar value `external`;
- time source: sidecar value **`internal`**;
- orbit provenance: the sidecar records J2000 pointing state but names no
  immutable trajectory solution or uncertainty family;
- artifact identity: metadata SHA-256 and HTTP object length/ETag exist, but
  no published complete-IQ cryptographic checksum was found.

Decision:

```text
REFUSED_INTERNAL_TIME_SOURCE_AND_ORBIT_AUTHORITY_UNKNOWN
```

The timestamp has millisecond representation but no finite ADC-to-UTC accuracy
bound. Its precision must not be treated as accuracy. Discriminability is
`NOT_EVALUATED_AFTER_TIME_REFUSAL`.

### 4. CAMRAS Artemis I tracking SigMF

Concrete metadata product:
`camras-2022_11_30_19_18_07_2216.500MHz_5.0Msps_ci16_le.sigmf-meta`.

- station: the same Dwingeloo coordinate above;
- capture time representation: `2022-11-30T19:18:07.000008`;
- carrier coordinate: `2,216,500,000 Hz`;
- format/rate: SigMF `ci16_le`, `5,000,000 complex samples/s`;
- data object: `1,200,000,000 bytes`, exactly `60 s` at four bytes per complex
  sample;
- raw-IQ state: `PRESENT_PRE_DOPPLER`;
- frequency/time declarations: `difi:reference=external` and
  `difi:time_source=pps`;
- protocol semantics: DIFI signal-data timestamps identify the first sample
  and include integer and fractional seconds; this proves coordinate meaning,
  not timestamp accuracy;
- station architecture: CAMRAS documents an Ettus USRP B210 with a hydrogen-
  maser reference distributed through White Rabbit. No product-applicable
  numerical bound from PPS through B210/DIFI to the ADC sample was found;
- orbit authority: the sidecar names the pre-pass tracking argument
  `Orion_OEM_20221117_1600_V0.1`, thirteen days before the recording. The OEM
  bytes, checksum, producer lineage and uncertainty were not present in the
  inspected public directory, so chronological naming cannot complete orbit
  admission;
- artifact identity: metadata SHA-256, HTTP object length/ETag and CC BY 4.0
  are available; no published complete-IQ cryptographic checksum was found.

Decision:

```text
REFUSED_NO_RECORDING_APPLICABLE_PPS_TO_ADC_BOUND_AND_ORBIT_BYTES_UNAVAILABLE
```

The 60-second orbit-only signature is
`NOT_EVALUATED_AFTER_TIME_REFUSAL`. No signal-derived Artemis frequency or
power series enters this decision.

### 5. Rosetta RSI solar-conjunction archive

Concrete family:
`RO-X-RSI-1/2/3-CR2-0040-V1.0`, volume `RORSI_0040`.

- mission interval: 2006-04-23 solar-conjunction radio science;
- receiving system in the concrete volume: `CLOSED_LOOP/IFMS` only at levels
  1A, 1B and 2;
- index identity: `INDEX.TAB`, `28,440 bytes`, SHA-256
  `c82f99b2cf3c2dda219a2733389629fd8cc473b7810e9243549088188bb52d5b`;
- product semantics: level-1A `.RAW` names closed-loop IFMS telemetry products;
  the index exposes no open-loop complex-voltage product;
- raw-IQ state for the frozen family: `ABSENT`.

Decision:

```text
REFUSED_OPEN_LOOP_RAW_COMPLEX_SAMPLES_ABSENT_FROM_CONCRETE_VOLUME
```

Generic RSI documentation that describes possible DSN RSR products cannot be
used to manufacture an open-loop product in this volume. Timing, orbit and
discriminability are `NOT_EVALUATED`.

## Why no physical ranking is authorized

The requested scientific ranking is by held-out orbital discriminability
**after** timing admission. No candidate reaches that boundary, so assigning a
numeric rank would compare curves whose event-time coordinate is not admitted.

Descriptively, Voyager and Artemis are the nearest mechanisms: both provide
raw complex samples and disciplined clocks, Voyager has a genuinely pre-pass
public SPK, and Artemis has first-sample DIFI semantics plus a named pre-pass
OEM. This is not a rank and grants no sample access. Their blockers are
upstream of detector design.

## Procedural deviation and isolation

During Artemis provenance inspection, an ancillary file named
`horizons_log.txt` was fetched in memory because its name suggested trajectory
provenance. It actually contained signal-derived columns. The complete
`3,776,740`-byte response was destroyed without filesystem persistence; no
value, row, statistic or feature from it was used in any clause or decision.

The receipt classifies this as `DESCRIPTION_ERROR`, not a physical capability
rejection. The Artemis refusal is independently supported by its SigMF
sidecar, public directory, DIFI semantics and station documentation. This
error therefore cannot alter the outcome, but it is retained rather than
silently reported as zero access.

## Terminal interpretation

This bounded set supplies no development/primary/reserve structure. The
correct terminal state is:

```text
NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL
```

The result does not justify a sixth dataset search, a receiver catalog, a
generic parser or a detector. Repeating metadata reconnaissance would now be
infrastructure drift. Per the frozen post-AMC change-of-information review and
the terminal cross-family screen, the next smallest physical route is bounded
blind orbit assignment within a predeclared difficult candidate family. That
route changes the inference question; it must not be disguised as continuation
of this raw-RF audit.

The strict JSON receipt is `14,936` bytes with SHA-256
`8143bc4a5d4e1e773b59122978f716f4b9bb0182a66f55c33efd918405697b11`.
It binds the predeclared scope at commit
`b446637c2a30c2d5b81609c526fdd30ada89ef26` and scope-file SHA-256
`be38a7e3ed7a822106b52781b0948078cfb1a13ded093615615158bcda342cb4`.

## Public authorities

- [Breakthrough Listen Voyager SigMF release](http://blpd0.ssl.berkeley.edu/SigMF_data/)
- [Breakthrough Listen GBT instrumentation](https://seti.berkeley.edu/assets/files/breakthrough-listen-search.pdf)
- [GBT coordinates](https://greenbankobservatory.org/portal/gbt/instruments/)
- [GBT clock and backend delays](https://www.greenbankobservatory.org/~fghigo/timer/clockdelays.html)
- [NAIF Voyager kernel status](https://naif.jpl.nasa.gov/pub/naif/VOYAGER/kernels/aareadme.txt)
- [NAIF Voyager SPK index and coverage](https://naif.jpl.nasa.gov/pub/naif/VOYAGER/kernels/spk/)
- [DSLWP-B release v1.0](https://zenodo.org/records/3571330)
- [CAMRAS SLIM IQ directory](https://data.camras.nl/slim/iq/)
- [CAMRAS Artemis IQ directory](https://data.camras.nl/artemis/)
- [DIFI first-sample timestamp semantics](https://github.com/DIFI-Consortium/DIFI-Certification/blob/main/DIFI_101_Tutorial.md)
- [CAMRAS Artemis receiver and clock description](https://www.camras.nl/en/blog/2022/first-results-artemis-i-lunar-mission-from-dwingeloo/)
- [Rosetta RSI CR2-0040 dataset](https://pds.nasa.gov/ds-view/pds/viewDataset.jsp?dsid=RO-X-RSI-1%2F2%2F3-CR2-0040-V1.0)
- [Rosetta RSI CR2-0040 volume](https://archives.esac.esa.int/psa/ftp/INTERNATIONAL-ROSETTA-MISSION/RSI/RO-X-RSI-1-2-3-CR2-0040-V1.0/)
