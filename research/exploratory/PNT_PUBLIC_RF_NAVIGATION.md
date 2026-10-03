# Public RF decoding and NAV conversion limits

Executed 3 October 2026. Exploratory development on public, already exposed
reference data. Two receiver runs are retained: native RINEX export, then
navigation-bit monitoring to investigate discrepancies. No prospective
confirmation, matched attack case or new false-alarm qualification.

## Result and next physical test

The software-only path works: raw RF samples -> GNSS-SDR acquisition/tracking
and LNAV decoding -> local GPS NAV -> same-issue Internet comparison. No new
receiver, antenna, Docker service or proprietary sensor was needed. The
native receiver completed with exit code 0 and reported 11.52 seconds of
processing time for 99.95 seconds of the 100-second recording. This is one
local runtime measurement, not a throughput guarantee.

The existing 27-field comparator reports **5/5 DIFFERENT_FROM_EXTERNAL** for
the native RINEX export. Those outcomes remain unchanged. The raw-bit cross
check exposes conversion problems that prevent treating these discrepancies
as RF attack detections. No threshold was relaxed, field dropped or missing
issue replaced to obtain a match.

The next necessary step is a reusable comparison of decoded LNAV fields with
qualified archive representations, including their precision and metadata
semantics. Test genuine one-bit changes and ambiguous representations, and
retain conversion failures separately from evidence of manipulation. Then
apply it to an adequate benign/attack pair. More clock-bias variants on the
old synthetic cases do not resolve this conversion problem. **P2 stays open.**

## Inputs and receiver

The [GNSS-SDR first-fix example](https://gnss-sdr.org/my-first-fix/) provides
the CTTC Spain recording of 4 April 2013: GPS L1 C/A, 4 MSps, interleaved
signed 16-bit I/Q. The archive contains 1,600,000,000 raw bytes, representing
100 seconds. It is a documented reference recording with no attack applied
here; it does not establish independently labeled benign receiver-hours.

| Input | Bytes | SHA-256 |
|---|---:|---|
| [RF archive](https://downloads.sourceforge.net/project/gnss-sdr/data/2013_04_04_GNSS_SIGNAL_at_CTTC_SPAIN.tar.gz) | 1,150,716,878 | `d5b926aefe7462ca4211bcae2129591a810fa4960a214f35d056a883aa2af3ff` |
| `2013_04_04_GNSS_SIGNAL_at_CTTC_SPAIN.dat` member | 1,600,000,000 | `6489a6630784478f144f20bf872848410dee3b54a20fd8d1bdd9258afccf2976` |
| [NOAA day 094 GPS NAV](https://noaa-cors-pds.s3.amazonaws.com/rinex/2013/094/brdc0940.13n.gz) | 60,466 | `e8405767901fd0d9c55bfcfbe0efdfb8c30640e962b87bb7a7a07941aaa1b864` |
| Native `GSDR276o10.26N` | 4,050 | `5d7ab0f85f8663a0e260e035b6d1d146741dfde59cd83cb3862deed54cc88a95` |
| Monitored `navdata.json` | 72,717 | `666ec0bbd9e3a1f11614aec4c8364895b061526c0580b9b825e3f93ac3661322` |

Receiver: GNSS-SDR 0.0.21, conda-forge Linux package
`gnss-sdr-0.0.21-hb52da05_5`, running in existing Ubuntu 24.04 WSL 1. It was
installed in an isolated environment; the system package manager had unmet
dependencies and was not repaired. RF data and the runtime remain outside
Git. The receiver is an optional development tool, not a production Python
dependency or a CI prerequisite.

Settings follow the public first-fix example, with RTCM serving disabled and
only RINEX file output enabled. The portable configuration changes only the
input pathname from the executed configuration. The tutorial's
`pre_2009_file=true` setting is retained: in this receiver version it chooses
the 1999 GPS-week era, which also resolves the recording's week 1734. The
comparison does not derive capture time from the computer clock.

The export filename and header date reflect the **2026 processing date**;
the message `toc` values are **2013-04-04 08:00:00 GPST**. UTC/ionosphere
header fields are zero/unqualified and outside the comparator. Receiver PVT
and timestamps are not surveyed position or independently verified time.
Only L1 observations are present: the C1C/C2W fixed-site diagnostic cannot be
applied by inventing a second frequency.

## Native comparison and raw-bit investigation

Each native message finds one same-issue NOAA record. The IODE/IODC values
are respectively G01 11/11, G11 23/23, G17 51/51, G20 27/27 and G32 35/35.
All share continuous week 1734 and `toe=374400`.

| Satellite | Differing native export fields |
|---|---|
| G01 | `codes_l2`, `l2_p_flag`, `sv_accuracy_m` |
| G11 | `cic_rad`, `codes_l2`, `l2_p_flag`, `sv_accuracy_m` |
| G17 | `omega_dot_rad_s`, `idot_rad_s`, `l2_p_flag`, `sv_accuracy_m` |
| G20 | `l2_p_flag`, `sv_accuracy_m` |
| G32 | `sqrt_a_m_sqrt`, `codes_l2`, `l2_p_flag`, `sv_accuracy_m` |

The second run enabled GNSS-SDR's [navigation data monitor]
(https://gnss-sdr.org/docs/sp-blocks/telemetry-decoder/#retrieving-decoded-navigation-messages),
sent only to localhost. Its protobuf datagrams and all 300-bit strings are
retained, in arrival order. There are 65 GPS L1 messages: 15 uninterrupted
same-HOW cycles, of which 10 contain subframes 1/2/3 and five are incomplete.
No invalid TLM/HOW or conflicting subframe body was found. The complete
cycles repeat the same five issues at frame starts 368640 and 368670 GPST
seconds of week. Reuse of `pnt.sfrbx.decode_issue` needs no fabricated UBX
envelope: strip each de-inverted word's six parity bits and supply its 240
data bits to the existing decoder.

Two exporter defects are directly visible in
[GNSS-SDR v0.0.21 source](https://github.com/gnss-sdr/gnss-sdr/blob/v0.0.21/src/algorithms/PVT/libs/rinex_printer.cc#L2618-L2626):

- The RINEX L2 P flag is populated from `code_on_L2`, ignoring the separately
  decoded flag. All five RF flags are 0, whereas the native export writes 1.
- The exporter writes `SV_accuracy`, which the
  [LNAV decoder](https://github.com/gnss-sdr/gnss-sdr/blob/v0.0.21/src/core/system_parameters/gps_navigation_message.cc#L125-L134)
  stores as a URA index, into the RINEX accuracy-in-metres field. Here index 0
  is exported as 0 metres; the existing ICD nominal mapping and NOAA use 2.

The numerical disagreements also include archive representation precision.
For example, G32's exact broadcast square-root semimajor axis is
`5153.7204875946044921875`; the native export writes `5153.72048759`, NOAA
writes `5153.720487600`. The latter's trailing zero gives a narrower written
decimal interval than the underlying exact value warrants. This does not
justify changing the previous comparator's rounding rule or silently
declaring the archive a lossless copy of the RF payload.

A separately labeled conversion diagnostic divides each continuous field by
its ICD binary scale (including pi for semicircles) and records the nearest
integer and distance from that integer. The largest archive distance is
0.0028288 LSB. For all ten complete cycles, these nearest integers agree
with the RF clock/orbit values. This is **not** a replacement comparison
profile, a calibrated tolerance or a security verdict. Raw `codes_l2=1`
still disagrees with NOAA's 0 for G01/G11/G32; no source is silently preferred.
G17/G20 have no remaining field difference under this exploratory lattice
diagnostic. The archive's L2-code disagreement requires source qualification.

GNSS-SDR admits the monitored subframes after its parity checks. This study
does not independently reconstruct the radio parity chain or establish RF
origin. The raw bit strings preserve the receiver's de-inversion and parity
decision, not unprocessed antenna samples. Repeated issues and distinct
file hashes do not qualify independent truth, freshness or attack attribution.

## Reproduction and retained evidence

Small exact outputs, the full NOAA file and portable receiver configurations
are in [`pnt/tests/fixtures/cttc20130404/`](../../pnt/tests/fixtures/cttc20130404).
The large public RF input stays external. Install GNSS-SDR 0.0.21 in an
isolated Linux environment, extract only the documented `.dat` member, verify
the hashes above, and replace the configuration's absolute input pathname.
Run in a new output directory:

```console
gnss-sdr --config_file=/absolute/path/cttc-gps-l1.conf --log_dir=/absolute/path/logs
python -m pnt navigation 2013-04-04 GSDR276o10.26N --witness NOAA=brdc0940.13n.gz --output NEW-native-navigation.json
```

For the preserved outputs, run the same Python command with the fixture
paths. The filename after a new receiver run will depend on processing time;
use its actual GPS NAV output. Exact whole-file hashes can differ because of
that header and receiver scheduling; they are hashes of the retained runs,
not promises about every future demodulation.

The bit-monitor configuration uses localhost port 39237. A listener must be
bound before starting the receiver. Deserialize the official
[`nav_message.proto` v0.0.21](https://github.com/gnss-sdr/gnss-sdr/blob/v0.0.21/docs/protobuf/nav_message.proto)
with Protocol Buffers. `navdata.json` retains both datagram hex and the five
decoded fields; no public listener service or new scientific executor is
introduced. The report retains every cycle's packet indices, missing
subframes, exact decoded fields and archive lattice coordinates so the
conversion diagnostic can be replayed from those datagrams.

Machine result: [`pnt_public_rf_navigation_v1.json.gz`](results/pnt_public_rf_navigation_v1.json.gz),
114,268 uncompressed bytes, SHA-256
`ea103533728774b6abbf28262da5508cc027587441bc198f344d758264709f8b`.
The native report is reproduced by the existing CLI; offline regressions
also check the raw-bit cross check and preserve prior RINEX/UBX results.
