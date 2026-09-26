# P2 intake: public stationary attack receiver and external GNSS stations

## Result and boundary

The first **real, contemporaneous observation path** now exists. The
[JammerTest 2024 dataset][zenodo] contains a stationary receiver's GPS code
measurements on 11 September 2024. For the selected `2.1.3,2.1.2,2.1.4`
scenario, archived [TRO100NOR][tro] and [KIRU00SWE][kiru] daily RINEX files
provide two physically distinct external stations on the same GPST epochs.
[`pnt_observation_pairing.py`](pnt_observation_pairing.py) pairs 340 GPS
satellite/epoch rows in 85 epochs, across nine satellites, with at most
0.439 seconds between the selected local sample and the 30-second grid.
This is an input/coverage result, **not a successful attack detector**.

The chosen scenario is publicly described as stationary spoofing with large
position/time jumps. Its `scenario.json` labels attacks at 10:00–10:55 UTC,
while the corresponding local observation CSV covers 07:58–08:59 in its
receiver-derived time and the paired external epochs run 07:59–08:59:30 GPST.
Those intervals do not overlap if the labels are interpreted literally as
UTC. Several other stationary scenarios show a roughly two-hour displacement;
local civil time is a plausible explanation, **not a verified correction**.
The selected log also names events “Jamming started/end” although the scenario
is classified as spoofing. Other scenario logs have mismatched sub-scenario
identifiers. None of these log entries is silently converted or used as an
attack truth label. A test of detection probability, false alarms during
attack-free intervals or time to alarm must wait for a qualified timeline.

## Input provenance and admission

| Input | Source | SHA-256 |
|---|---|---|
| Stationary scenario CSV inside `GNSS_DATASET_JAMMING_SPOOFING.tar.gz` | [Zenodo v3][zenodo], `Spoofing/stationary/Medium Power (_1W)/Bands_E1_L1/2.1.3,2.1.2,2.1.4/rinex.csv` | Archive: `73e78934aa00d01dfeebabc45f81b38c9c0aecf972f5fc94d9ff60527065b313` |
| `TRO100NOR_S_20242550000_01D_30S_MO.crx.gz` | [BKG day 255][tro-file] | `45315eca5a5e65c58c419fd9a8ff51c35b93578585475bbe96bab6db29f40c54` |
| `KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz` | [BKG day 255][kiru-file] | `950aa80894752f4bb6312373d69f343cdfc65570a81501c6cc05e1fb076aac1c` |

The Zenodo-published archive MD5 also matches its listing:
`c7b00c63bb1ee5db80c7692a2b06e169`. The 375 MB archive and original
station files are not copied into Git. The [compact result]
(results/pnt_jammertest_pairing_v1.json) retains the hashes, source member,
unmodified declared attack log, coverage and exclusions. This uses public,
already exposed recordings. No one-shot confirmation has begun.

The source's `rinex.csv` is a flattened CSV, not a RINEX observation file.
Its fields say `pseudorange_L1` and `pseudorange_L2` without identifying GPS
tracking codes. The external RINEX files declare **C1C/C2W**. We cannot yet
equate those signal pairs or subtract them as identical observables without
checking the local receiver/UBX signal IDs and hardware biases. The local
timestamp is provisionally treated as GPST because it agrees with the dataset's
receiver `iTOW` at the start, but both derive from the attacked receiver and
cannot serve as independent time evidence. No surveyed victim coordinate or
independent clock is established by this intake.

Of 477,087 local CSV rows, 123,109 are GPS and 47,704 have both L1 and L2
pseudoranges. The 0.5-second grid tolerance admits 1,617 raw rows at 85 epochs;
repeated receiver samples reduce these to 369 unique satellite/epoch keys.
TRO1 lacks three of those keys and KIRU lacks 29, leaving 340 present at all
three physical receivers. The report retains the remaining non-GPS, single-
frequency, off-grid and missing-reference counts. The off-grid fraction may
include ordinary sampling phase as well as attack-induced time behavior; it
is not an attack score. External C1C/C2W were present at the matched keys.

The adapter rejects unqualified RINEX time scales, applied corrections,
nonstandard epochs, duplicate satellites and identical external files counted
twice. It makes no orbit prediction, detector decision or attribution. The
paired numeric rows remain available in memory through `pair(...)` for the
next physical test; they are not published as purported attack evidence.

## Next physical test

Resolve the scenario timeline and local signal IDs from an independent
recording/catalogue or a better documented subset before scoring this attack.
Then compare a fixed-site local baseline, a remote-only control and their
combination on the **same** episodes. Keep pre-event fit separate, report
nonmatches/clock jumps and use a declared orbit/propagation hypothesis if
absolute geometric residuals are calculated. If the labels cannot be
qualified, retain this dataset for adapter and stress testing only, and choose
another documented attack for performance claims. An independent time witness
is still needed for absolute-time verification.

Reproduce pairing after downloading the three files above:

```console
python -m research.exploratory.pnt_observation_pairing ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_E1_L1/2.1.3,2.1.2,2.1.4/rinex.csv" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_OUTPUT.json
python -m pytest research/exploratory/tests/test_pnt_observation_pairing.py -q
```

[zenodo]: https://zenodo.org/records/15911589
[tro]: https://network.igs.org/TRO100NOR
[kiru]: https://network.igs.org/KIRU00SWE
[tro-file]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/TRO100NOR_S_20242550000_01D_30S_MO.crx.gz
[kiru-file]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz
