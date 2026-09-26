# P2 raw observation recovery: JammerTest 2024

The [flattened CSV intake](PNT_JAMMERTEST_PAIRING.md) exposed shifted columns
and left almost no usable GPS code inside the three scheduled tests. The
published archive also contains the original `240911_075843.ubx` recording.
[`pnt_rawx_recovery.py`](pnt_rawx_recovery.py) reads its checksum-verified
UBX-RXM-RAWX packets, uses the receiver's GPS signal identifiers and
`prValid` bit, and pairs actual L1 C/A plus L2 CL code with the same archived
TRO1 and KIRU reference epochs. This recovers **318 three-receiver pairs in
82 epochs**, including 108 pairs in the scheduled tests. The [compact result]
(results/pnt_jammertest_rawx_recovery_v1.json) retains counts, source hashes,
time discontinuities and missing-reference counts; the 43 MB raw member and
375 MB archive stay outside Git.

| Official test | Raw dual-GPS samples at 5 Hz | Three-receiver pairs / epochs at 30 s |
|---|---:|---:|
| 2.1.3, Galileo E1 only | 4,863 | 40 / 23 |
| 2.1.2, GPS L1 C/A only | 6,793 | 64 / 26 |
| 2.1.4, GPS L1 and Galileo E1 | 337 | 4 / 1 |
| Outside the three windows | 35,700 | 210 pairs |

The reader verified 60,023 UBX packets, of which 18,355 are RAWX and 3,671
are NAV-PVT, a five-to-one count consistent with the observed 5 Hz cadence.
The first receiver time is 07:58:42.799 GPST; at 5 Hz, the
last packet's inferred capture time is 08:59:53.599, just 0.002 seconds from
the final receiver time after recovery. This supports using packet order as a
**provisional monotonic acquisition clock**. It does not provide an independent
timestamp or guarantee that no internal gaps occurred. The official CEST
schedule and conversion are recorded in the [tracked log extract]
(inputs/pnt_jammertest_windows.json); edge timing and detection latency are
not established by this reconstruction.

The RAWX receiver time has six jumps greater than one second. In test 2.1.2
it moves backward about 73,228 seconds twice and returns, with the second
return aligned near the published stop. In test 2.1.4 it moves backward about
74,435 seconds and returns near the published stop. The full before/after
receiver values and inferred capture indices are in the result. The nominal
Galileo-only test has no such jump. These are **observed local receiver-time
discontinuities in an exposed attack recording**; their existence does not
prove that an independent site clock was falsified. They are locally visible
even without the Internet witnesses, so they do not establish network benefit.

The raw payload identifies GPS L1 C/A (`gnssId=0`, `sigId=0`) and L2 CL
(`sigId=3`) under the [u-blox RAWX format][ublox]. External RINEX offers C1C
and C2W. C1C is the corresponding GPS L1 C/A code; **C2W is not L2 CL**.
Unqualified cross-receiver subtraction of the two L2 observables would include
signal-specific biases. The reader rejects invalid code flags and nonpositive
or nonfinite values even when `prValid` is set. Of 226,660 GPS L1/L2 records,
45,509 meet that latter exclusion; all failure counts remain visible. It does
not infer a detector threshold, spoofing source, authenticated RF origin,
absolute-time truth or false-alarm rate.

Next, compare a local-only GPS L1 control, a remote-only control and a joint
consistency measure on the **same recovered epochs**. Use the 30-second paired
set and explicitly account for satellite geometry and fixed-site coordinates;
the published recording's receiver time cannot serve as the event clock during
the jumps. The limited mixed-test coverage and all code exclusions must stay
in the denominators. A positive contrast would still be exploratory and
specific to this recorded attack, pending benign controls and held-out work.

Reproduce after downloading the archive and two reference files listed in the
[CSV intake](PNT_JAMMERTEST_PAIRING.md):

```console
python -m research.exploratory.pnt_rawx_recovery ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_E1_L1/2.1.3,2.1.2,2.1.4/240911_075843.ubx" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_OUTPUT.json --windows research/exploratory/inputs/pnt_jammertest_windows.json
python -m pytest research/exploratory/tests/test_pnt_rawx_recovery.py -q
```

[ublox]: https://content.u-blox.com/sites/default/files/documents/u-blox-F9-HPG-1.32_InterfaceDescription_UBX-22008968.pdf
