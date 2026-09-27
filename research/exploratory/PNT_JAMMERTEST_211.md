# P2 exploratory check: second stationary JammerTest episode

The public [JammerTest archive](https://zenodo.org/records/15911589) contains a
second stationary recording, scenario 2.1.1, labelled as power-ramped spoofing.
The official event workbook, *Site 1 - Bleik*, rows 341–351, places the ramp
from 09:00:41 to 09:36:49 CEST on 11 September 2024 (07:00:59–07:37:07 GPST).
Those eleven contiguous rows are represented by the [window extract]
(inputs/pnt_jammertest_211_windows.json). Its broad `scenario.json` log instead
uses the wording “Jamming started/end”; the official workbook and raw recording
do not establish the cause of every anomalous measurement.

The [recovery result](results/pnt_jammertest_211_rawx_recovery_v2.json) retains
source hashes, all packet and code exclusions, a provisional 5 Hz capture
timeline, and window support. Two UBX frames have invalid checksums and are
**skipped and counted**; one missing RAWX interval is inferred from a short
integral receiver-time gap. The remaining 12,518 checksum-valid RAWX packets
align at the endpoint to 0.002 s under this assumption. This does not supply an
independent acquisition clock. The recovered receiver time jumps by −68,466.798
s during the logged ramp and +68,467.239 s just after it. These are local
continuity failures, not independently measured absolute time errors. There are
also 16,059 positive but implausibly large GPS code records and 1,983
nonpositive/nonfinite records despite their valid flags; all are excluded and
counted.

The same-day TRO1 and KIRU RINEX observations yield 231 simultaneous
three-receiver GPS pairs across 50 epochs: 49 pairs/7 epochs before the logged
ramp, 166/39 during it and 16/4 after. Requiring at least three pre-event pairs
per satellite leaves 154 pairs/27 epochs during the ramp. The [contrast result]
(results/pnt_jammertest_211_rawx_contrast_v2.json) compares the **same pairs**
as local L1 C/A-minus-L2 CL change, median external C1C-minus-C2W change,
and local-minus-external change. Each satellite/station series is centred on
its pre-event median. These exposed pre-event observations are a scheduled
control, not an independently certified benign population.

| Interval | Paired rows / epochs used | Median absolute local | External | Combined |
|---|---:|---:|---:|---:|
| Pre-event | 49 / 7 | 0.27 m | 0.20 m | 0.37 m |
| Official 2.1.1 ramp | 154 / 27 | 0.71 m | 0.36 m | 0.78 m |
| Post-event | 16 / 4 | 0.59 m | 1.02 m | 0.61 m |

During the ramp, the 90th-percentile absolute changes are 4.03 m local,
1.23 m external and 3.56 m combined. The largest local and combined changes
are both about 462 m. The network is comparatively steady in this particular
frequency-difference channel, but subtracting it does not create a clear
incremental signal over the local diagnostic. This is a descriptive comparison,
not a calibrated detection/false-alarm experiment. Only 39 of roughly 72
possible 30-second ramp epochs have a three-receiver pair, and only 27 retain
pre-event satellite support. Missing observations and local clock jumps are
themselves important local controls; they cannot be hidden by selecting the
surviving pairs.

As in the [first episode](PNT_JAMMERTEST_CONTRAST.md), local L2 CL and external
C2W are different tracking codes. Temporal centring removes a static offset,
not dynamic receiver biases. No fixed-site ground truth, independent clock,
absolute position/time verification, RF authenticity or attack attribution is
obtained here. The scheduled ramp is too long and the paired data too sparse
to infer a useful alarm lead time. Two examples from this archive still do not
show the **added** detection value required by the [PNT plan]
(../../docs/PNT_SECURITY_PLAN.md). We should stop multiplying variants of
these locally obvious or poorly observed episodes. The next P2 evidence needs
a matched benign condition and an attack whose local controls remain plausible,
or the product claim should be narrowed to independent incident context.

Reproduce with the archive and same-day station files identified in the
[intake](PNT_JAMMERTEST_PAIRING.md):

```console
python -m research.exploratory.pnt_rawx_recovery ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_L1_L2_L5/2.1.1/240911_065707.ubx" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_RECOVERY.json --windows research/exploratory/inputs/pnt_jammertest_211_windows.json --recover-corrupt
python -m research.exploratory.pnt_rawx_contrast ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_L1_L2_L5/2.1.1/240911_065707.ubx" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_CONTRAST.json --windows research/exploratory/inputs/pnt_jammertest_211_windows.json --recover-corrupt --baseline pre-event
```
