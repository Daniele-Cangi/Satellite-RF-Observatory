# P2 intake decision: matched recording needed

P2 asks whether external GNSS observations improve an incident decision over
reasonable local receiver controls. The two earlier JammerTest episodes did not
show that advantage. This check examined a qualitatively different public
stationary recording: a simulated drive using broadcast ephemerides, first on
Galileo (2.3.8), then on GPS (2.3.5). The source is the
[JammerTest archive](https://zenodo.org/records/15911589); the
[official event workbook](https://www.jammertest.no/content/files/2026/05/Logg_Jammertest_2024_v1.xlsx),
sheet *Site 1 - Bleik*, rows 375–376, supplies the CEST windows. The exact
extract is [versioned](inputs/pnt_jammertest_235_windows.json).

The existing CSV/RINEX intake paired the stationary receiver's GPS L1/L2
columns with simultaneous C1C/C2W observations from TRO1 and KIRU. The
[machine-readable result](results/pnt_jammertest_235_pairing_v2.json) retains
source hashes, exclusions, the two named stations and every segment's
support. Its interval counts use the receiver-derived time provisionally;
the recording has no independent event clock.

| Interval | Local dual-code rows / epochs | Three-receiver pairs / epochs |
|---|---:|---:|
| Before 2.3.8 | 24 / 3 | 20 / 3 |
| Galileo 2.3.8 | 1 / 1 | 1 / 1 |
| Between the logged transmissions | 56 / 8 | 49 / 8 |
| GPS 2.3.5 | 33 / 16 | 33 / 16 |
| After 2.3.5 | 21 / 3 | 21 / 3 |

The GPS window lasts about ten minutes, yet the 33 paired rows come from only
six satellites, with G07 contributing 13. Just one pair survives the earlier
Galileo window. The CSV is a flattened export with unqualified L1/L2 code
identities and frequent missing fields (47,254 of 64,613 GPS rows lack a dual
code; another 1,393 have ambiguous columns). The source `scenario.json`
describes these two sub-scenarios as spoofing without jamming, but its
`attack_log` lists jamming events under **different** sub-scenario IDs. The
official workbook governs the chosen windows; the conflicting sidecar is kept
as a provenance discrepancy, not silently harmonized.

**Decision:** this is an exposed-source qualification, not an attack-detection
test. The between-event gap follows a transmitted scenario and is not a
certified benign baseline. There is no independent fixed-site truth or
acquisition-time witness here. Sparse and changing dual-code support, uncertain
CSV signal identity and inconsistent event metadata would make an incremental
network-benefit claim fragile. Do not tune a new threshold or publish a
positive/negative attack score from these rows. The current P2 result remains
independent incident context, with detection gain open.

## Minimum useful next recording

Collect or obtain one **fixed-site** receiver recording with independently
surveyed antenna coordinates, a documented benign interval and a controlled,
independently logged challenge designed to leave basic local quality and
continuity checks plausible. Keep the original receiver data: per-satellite
code, carrier phase, Doppler, C/N0 and validity/lock flags with explicit signal
IDs; receiver PVT and clock state; configuration and antenna metadata. A
lossless UBX stream or identified RINEX observations are suitable inputs.
Retain packet order and host capture timestamps from a monotonic clock with a
documented non-victim time anchor. Absolute-time claims require an independent
clock witness and its uncertainty; a GNSS-derived receiver timestamp cannot
serve as its own truth.

Obtain at least two physically separate reference stations with overlapping
epochs, the same identified signal modes where a direct code comparison is
claimed, station coordinates/antenna metadata and source provenance. Record
the event schedule and its time zone independently of the victim receiver.
Include benign periods on the same setup before and after the challenge, and
document plausible benign disturbances rather than declaring every unscheduled
gap clean. Preserve missing packets, signal loss, station outages and all
failed attempts in the denominator. Compare local-only, network-only and
combined rules on the **same** admitted epochs, including false alarms and
inconclusive time. A recording that cannot supply these observations may still
inform incident context, but cannot settle the stronger P2 question.

This is an acquisition specification, not a new approval mechanism or a plan
to transmit RF. Use an authorized, shielded or externally controlled test; no
RF transmission or prospective confirmation was started here.

Reproduce the qualification with the archived files identified in the earlier
[JammerTest intake](PNT_JAMMERTEST_PAIRING.md):

```console
python -m research.exploratory.pnt_observation_pairing ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_E1_E5_L1_L2_L5/2.3.5,2.3.8/rinex.csv" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_OUTPUT.json --windows research/exploratory/inputs/pnt_jammertest_235_windows.json
```
