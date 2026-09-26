# P2 intake: public stationary attack receiver and external GNSS stations

## Result and boundary

The first **real, contemporaneous observation path** now exists. The
[JammerTest 2024 dataset][zenodo] contains a stationary receiver's GPS code
measurements on 11 September 2024. For the selected `2.1.3,2.1.2,2.1.4`
scenario, archived [TRO100NOR][tro] and [KIRU00SWE][kiru] daily RINEX files
provide two physically distinct external stations on the same GPST epochs.
[`pnt_observation_pairing.py`](pnt_observation_pairing.py) pairs **210 structurally
usable GPS satellite/epoch rows** in 32 epochs, across nine satellites, with
at most 0.0041 seconds between the selected local sample and the 30-second grid.
This is an input/coverage result, **not a successful attack detector**.

The [official 2024 test log][official-log] labels its Site 1 Bleik columns
explicitly **local CEST**, resolving the roughly two-hour discrepancy between
the archive's `scenario.json` timestamps and the 07:59–08:59:30 GPST paired
epochs. The [tracked extract](inputs/pnt_jammertest_windows.json) records the
source workbook hash and rows 352–354. On 11 September 2024, CEST minus two
hours plus the 18-second GPST–UTC offset gives these independently published
event windows:

| Test | Transmitted signals in official log | GPST window | Paired GPS rows / epochs by receiver time |
|---|---|---|---:|
| 2.1.3 | Galileo E1 only | 08:01:05–08:16:05 | 0 / 0 |
| 2.1.2 | GPS L1 C/A only | 08:20:28–08:35:28 | 0 / 0 |
| 2.1.4 | GPS L1 and Galileo E1 only | 08:40:35–08:55:35 | 1 / 1 |

An initial version counted 340 pairs, but the flattened source CSV omits empty
measurements in some rows, shifting subsequent fields left. For example, a
carrier phase can land in `pseudorange_L2` while `snr_L1` takes a range-sized
value and `snr_L2` is blank. Numeric range checks alone admitted those rows.
Requiring both terminal SNR fields to be populated and physically plausible
excludes 12,012 ambiguous GPS rows. The revised result has **no usable paired
GPS code in the first two test windows and one pair in the third**. The other
209 pairs fall outside the official windows by receiver time. Neither the
nominal Galileo-only interval nor the GPS L1 interval can be scored from this
CSV. It is not evidence that the attack is undetectable or that its effect is
large; it is a data-format/availability limit.
The CSV timestamp is receiver-derived and may itself jump under attack, so
this is **provisional overlap, not independently timed attack truth**. The
archive's unmodified `scenario.json` entries still say `timestamp_utc` and
“Jamming started/end”; their literal UTC interpretation conflicts with the
official local-time log. The official source governs the schedule used here,
and this inconsistency remains visible in the result.

## Input provenance and admission

| Input | Source | SHA-256 |
|---|---|---|
| Stationary scenario CSV inside `GNSS_DATASET_JAMMING_SPOOFING.tar.gz` | [Zenodo v3][zenodo], `Spoofing/stationary/Medium Power (_1W)/Bands_E1_L1/2.1.3,2.1.2,2.1.4/rinex.csv` | Archive: `73e78934aa00d01dfeebabc45f81b38c9c0aecf972f5fc94d9ff60527065b313` |
| `TRO100NOR_S_20242550000_01D_30S_MO.crx.gz` | [BKG day 255][tro-file] | `45315eca5a5e65c58c419fd9a8ff51c35b93578585475bbe96bab6db29f40c54` |
| `KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz` | [BKG day 255][kiru-file] | `950aa80894752f4bb6312373d69f343cdfc65570a81501c6cc05e1fb076aac1c` |
| Official event workbook | [JammerTest 2024 log][official-log], `Site 1 - Bleik`, rows 352–354 | `4ef5091a4ee6489e8700b3495c51b4e99e9c37c138617c7c9c7f83f2047e60e2` |

The Zenodo-published archive MD5 also matches its listing:
`c7b00c63bb1ee5db80c7692a2b06e169`. The 375 MB archive and original
station files are not copied into Git. The [compact result]
(results/pnt_jammertest_pairing_v1.json) retains the hashes, source member,
unmodified declared attack log, official-window conversion, coverage and
exclusions. This uses public,
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

Of 477,087 local CSV rows, 123,109 are GPS and 47,704 superficially have both
L1 and L2 pseudoranges. The structural SNR check excludes 12,012 of those.
The 0.5-second grid tolerance admits 1,155 raw rows at 32 epochs; repeated
receiver samples reduce these to 231 unique satellite/epoch keys. TRO1 lacks
two of those keys and KIRU lacks 21, leaving 210 present at all three physical
receivers. The report retains non-GPS, single-frequency, ambiguous-column,
off-grid and missing-reference counts. The off-grid fraction may
include ordinary sampling phase as well as attack-induced time behavior; it
is not an attack score. External C1C/C2W were present at the matched keys.

The adapter rejects unqualified RINEX time scales, applied corrections,
nonstandard epochs, duplicate satellites and identical external files counted
twice. It makes no orbit prediction, detector decision or attribution. The
paired numeric rows remain available in memory through `pair(...)` for the
next physical test; they are not published as purported attack evidence.

## Next physical test

Recover signal-qualified raw observations from the archived `240911_075843.ubx`
file, rather than trusting the flattened CSV columns, and check whether the
attacked windows have usable GPS code and receiver-time continuity. If raw
recovery fails, choose another documented receiver recording; do not extract
attack-performance claims from the one usable pair. Once a real contrast is
available, compare fixed-site local, remote-only and combined controls on the
same episodes, keeping pre-event fit and missing rows visible. An independent
time witness remains necessary for absolute-time verification and rigorous
detection timing.

Reproduce pairing after downloading the three files above:

```console
python -m research.exploratory.pnt_observation_pairing ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_E1_L1/2.1.3,2.1.2,2.1.4/rinex.csv" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_OUTPUT.json --windows research/exploratory/inputs/pnt_jammertest_windows.json
python -m pytest research/exploratory/tests/test_pnt_observation_pairing.py -q
```

[zenodo]: https://zenodo.org/records/15911589
[tro]: https://network.igs.org/TRO100NOR
[kiru]: https://network.igs.org/KIRU00SWE
[tro-file]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/TRO100NOR_S_20242550000_01D_30S_MO.crx.gz
[kiru-file]: https://igs.bkg.bund.de/root_ftp/IGS/obs/2024/255/KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz
[official-log]: https://www.jammertest.no/content/files/2026/05/Logg_Jammertest_2024_v1.xlsx
