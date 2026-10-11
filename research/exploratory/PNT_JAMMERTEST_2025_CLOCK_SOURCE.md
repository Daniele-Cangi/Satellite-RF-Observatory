# FGI 2025: does the original SBF provide independent time?

Exploratory source qualification, 11 October 2026, following the exposed
[2.3.5 geometry comparison](PNT_JAMMERTEST_2025_COHERENT.md). No new detector,
threshold, attack execution or prospective confirmation. That comparison and
its retained results are unchanged.

**This recording does not qualify an independent UTC acquisition boundary.**
All 901 receiver-status records have `EXT_FREQ=0`, `EXT_TIME=1`, and all 901
measurement epochs indicate clock steering. There is evidence of a detected
PPS input, but its source, UTC epoch association and uncertainty are unknown.
Neither that pulse nor a receiver-generated PPS qualifies as an independent
UTC witness on the available evidence.
This closes the documentary lead for this file; it does not establish that no
independent clock existed at the site.

## Input and coverage

The source is `/Static/Spoofing/MF/2.3.5/JT25_2.3.5_S_MF.sbf` in the
[FGI archive][dataset], Metax file `01a06b85-406c-7c73-a876-9fe0f33594e9`.
The 21,355,148 bytes matched the published SHA-256 **before decoding**:
`92780cfcd8ae6a0f8434a9a899da538edf6d1b4519b6aeb61ef62ac6f9f2c3b4`.
Attribution: Emma Mannfors, Muwahida Liaquat, Zahidul Bhuiyan, Mika Saajasto
and Toni Hammarberg; Finnish Geospatial Research Institute, National Land
Survey of Finland; CC BY 4.0. Original bytes remain outside Git.

The existing third-party [pysbf2 library][parser], pinned to 1.0.6, was used
without adding a production dependency or another repository parser. All
**138,447 SBF frames / 32 ID-revision pairs** cover the source bytes exactly:
zero skipped/trailing bytes and zero CRC failures. Framing, CRC and selected
clock-field decoding are distinct checks. A separate all-block library pass
raised no parse errors; this is not semantic qualification of every payload
(the library has nominal/unimplemented layouts, including `Meas3Ranges`).

`ReceiverStatus` revision 1, `ReceiverTime` revision 0, `xPPSOffset` revision 0,
`MeasEpoch` revision 1 and `PVTGeodetic` revision 2 each have 901 records.
Their week/TOW sequences agree exactly: week 2384, TOW 308,298,000 through
309,198,000 ms, in 1,000-ms increments. These correspond to **13:38:18 through
13:53:18 GPST**, or the receiver's reported 13:38:00 through 13:53:00 UTC,
17 September 2025. They are receiver tags, not independently measured arrival
times. The RINEX comparison began two seconds later and used 899 native
epochs; no missing SBF clock record is silently substituted or interpolated.

The [retained inspection](results/pnt_jammertest_2025_clock_source_v1.json.gz)
contains the complete block inventory and every selected timing record with
source offset, raw status words and the fields used here. The receiver-status
prefix and bit masks were also checked directly against the vendor layout,
independently of the library's field labels.

## What the fields establish

Field meanings come from Septentrio's **PolaRx5 firmware 5.5.0 Reference Guide**,
19 August 2022: time management pp. 58-60; measurement flags p. 292; time/PPS
blocks pp. 412-413; status pp. 437-439. The publisher's URL returned HTTP 403;
the [manufacturer-authored PDF mirrored here][guide] was read instead, SHA-256
`d72d24826072d22a2d18686f8744daac8493bee58d7aabdfc505da64b120ce9e`.
No `ReceiverSetup` block identifies the recording's actual firmware version;
the interpretation uses the documented layouts for the recorded revisions.

| Field | Observed denominator | Meaning and limit |
|---|---:|---|
| `ReceiverStatus.EXT_FREQ` (RxState bit 2) | 0 in 901/901 | No detected external 10-MHz reference is reported; the guide associates zero with the internal clock. This does not corroborate the site's `EXTERNAL CESIUM` declaration for this recording. |
| `ReceiverStatus.EXT_TIME` (bit 3) | 1 in 901/901 | A PPS IN pulse was detected. This flag contains no source identity, epoch label, phase measurement or uncertainty. |
| `MeasEpoch.ClockSteering` (CommonFlags bit 3) | 1 in 901/901 | Receiver-time steering is enabled. The guide describes steering toward GNSS time, not independent UTC. |
| `ReceiverTime.SyncLevel` / `DeltaLS` | 7 / 18 in 901/901 | GNSS synchronization flags and a receiver UTC conversion; not an external clock comparison. |
| `xPPSOffset.TimeScale` / `SyncAge` | GPS (1) in 901/901; age 0 in 856, 1-31 s in 45 | Offset of the receiver's **output** pulse, in ns; not PPS IN phase or capture time. No independent timing budget is inferred. |
| `ReceiverStatus.REFOUT_LOCKED` (bit 11) | 0 in 27; 1 in 874 | Output frequency reports GNSS lock from TOW 308,325,000 ms onward; not a cesium/UTC qualification. |

The [PolaRx5 User Manual][manual], Appendix B.3-B.4, separately documents REF
IN as a 10-MHz frequency input. A frequency standard does not supply the
absolute epoch association required by the project's time test.

`UpTime` increases from 26,169 to 27,069 s without a reset; `CmdCount` stays 1.
Those observations do not reconstruct configuration before this excerpt.
No `ReceiverSetup`, `Commands`, `ASCIIIn`, `Comment`, `RxMessage`, `ExtEvent`
or external-event PVT blocks are present. No source/calibration record for
the input pulse appears in the selected SBF or the previously read site log
and sidecar. This absence is scoped to those files, not the whole campaign.

Failures remain visible: `RxError=8` (the latched software warning/error bit)
appears in all 901 status records. Its cause and time are unspecified; it is
not evidence that the spoofing caused a software fault. PVT status is 0 in
856 records, 4 in 32 and 6 in 13; the latter 45 have `TimeSystem=255`.
The output PPS synchronization age is also nonzero in 45 records; the two
sets are retained separately and do not coincide exactly. Derived clock
solutions are not promoted to timing truth. `CumClkJumps=0`
in all 901 measurement records also does not bound absolute timing error.

## Reproduce the retained inspection

Download the original SBF using the Etsin procedure in the geometry report;
verify the size and SHA-256 above. Use a separate environment with
`pysbf2==1.0.6 pynmeagps==1.1.7 pyrtcm==1.2.0`. The library is independent of
Septentrio. Its default log-and-continue error policy is not used here.
From the repository root, with the original file in `INPUTS`, this reproduces
the result's `inspection` object using existing library/standard primitives:

```python
from pathlib import Path
from collections import Counter, defaultdict
from binascii import crc_hqx
from hashlib import sha256
from struct import unpack_from
from pysbf2 import SBFReader
from pysbf2.sbftypes_core import SBF_MSGIDS

path = Path('INPUTS/JT25_2.3.5_S_MF.sbf')
source = path.read_bytes()
assert len(source) == 21355148
assert sha256(source).hexdigest() == (
    '92780cfcd8ae6a0f8434a9a899da538edf6d1b4519b6aeb61ef62ac6f9f2c3b4')
fields = {
    4014: ('CPULoad', 'UpTime', 'CmdCount'),
    5914: ('UTCYear', 'UTCMonth', 'UTCDay', 'UTCHour', 'UTCMin',
           'UTCSec', 'DeltaLS', 'SyncLevel'),
    5911: ('SyncAge', 'TimeScale', 'Offset'),
    4027: ('N1', 'ClockSteering', 'CumClkJumps'),
    4007: ('Error', 'TimeSystem'),
}
counts, records, cursor = Counter(), defaultdict(list), 0
with path.open('rb') as stream:
    reader = SBFReader(stream, protfilter=2, quitonerror=2, parsing=False)
    for raw, _ in reader:
        offset = stream.tell() - len(raw)
        assert offset == cursor
        assert raw[:2] == b'$@' and len(raw) >= 14 and len(raw) % 4 == 0
        assert int.from_bytes(raw[6:8], 'little') == len(raw)
        assert crc_hqx(raw[4:], 0) == int.from_bytes(raw[2:4], 'little')
        cursor = stream.tell()
        idrev = int.from_bytes(raw[4:6], 'little')
        mid, rev = idrev & 8191, idrev >> 13
        counts[mid, rev] += 1
        if mid not in fields:
            continue
        msg = SBFReader.parse(raw, validate=1, parsebitfield=1)
        values = {key: getattr(msg, key) for key in
                  ('TOW', 'WNc') + fields[mid]}
        if mid == 4014:
            values['ExtError'] = raw[15]
            values['RxState'], values['RxError'] = unpack_from('<II', raw, 20)
        records[msg.identity].append(
            {'offset': offset, 'length': len(raw), 'fields': values})
    assert cursor == stream.tell() == len(source)
inspection = {
    'framed_bytes': cursor, 'frame_count': sum(counts.values()),
    'skipped_bytes': 0, 'crc_failures': 0,
    'blocks': [{'id': mid, 'revision': rev, 'name': SBF_MSGIDS[mid][0],
                'count': count} for (mid, rev), count in sorted(counts.items())],
    'records': dict(records),
}
```

## Development decision

Do not give this dataset an absolute-time budget or infer PPS IN identity from
the antenna log. The remaining requirement is **a documented association
between an independently timed acquisition and the attacked measurements**,
with source and uncertainty. A software capture with the Android collector's
independent Internet-time channel is a possible development route; its
software challenges are already exposed evidence and do not replace a
physical attacked recording. A different public recording must contain that
association explicitly before it is used for a timing claim. More thresholds
or equivalent sessions on this file would not supply it. P2 physical
qualification and P3 remain open; the website follows that demonstration.

[dataset]: https://etsin.fairdata.fi/dataset/095782a8-4e31-456e-8719-7021b4c96362
[parser]: https://github.com/semuconsulting/pysbf2
[guide]: https://www.gnss-imu.com/down/upload/20220923/1663940448.pdf
[manual]: https://www.septentrio.com/system/files/support/polarx5_user_manual_v2.7.pdf
