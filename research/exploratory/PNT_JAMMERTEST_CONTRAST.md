# P2 exploratory contrast: local GPS code versus external stations

The [raw UBX recovery](PNT_JAMMERTEST_RAWX.md) gives 317 valid three-receiver
GPS satellite/epoch pairs across 81 epochs in a public JammerTest 2024
recording. [`pnt_rawx_contrast.py`](pnt_rawx_contrast.py) compares **the same
pairs** three ways: local L1 C/A minus L2 CL, the median of two external
C1C-minus-C2W changes, and local change minus external change. Each
satellite/station series is centred on its median outside the three official
test windows. The [versioned result]
(results/pnt_jammertest_rawx_contrast_v1.json) contains hashes, exclusions,
support, per-window counts and unrounded statistics.

The later [reference-agreement result]
(results/pnt_jammertest_rawx_contrast_v3.json) retains those outcomes and also
reports each external station separately. Its median absolute between-station
disagreement is 0.43 m outside the scheduled tests, 0.25 m in 2.1.3,
0.41 m in 2.1.2, and 0.85 m on the four 2.1.4 pairs. The 2.1.4 support is too
small to establish stability. A near-zero network median could otherwise hide
opposite changes at the two stations; the v3 test explicitly exercises that
failure mode. Agreement here concerns only separately centred GPS
frequency-difference changes on matched rows, not every possible shared error.

| Window | Paired rows / epochs | Median absolute local change | External change | Combined change |
|---|---:|---:|---:|---:|
| Outside scheduled tests | 209 / 31 | 0.40 m | 0.41 m | 0.35 m |
| 2.1.3, nominal Galileo E1 only | 40 / 23 | 89 m | 0.48 m | 89 m |
| 2.1.2, GPS L1 C/A only | 64 / 26 | 232 m | 0.24 m | 232 m |
| 2.1.4, GPS L1 and Galileo E1 | 4 / 1 | 750 km | 0.37 m | 750 km |

The 90th-percentile absolute changes are 1.95/1.82/0.93 m
(local/external/combined) outside scheduled tests, 299/2.09/299 m in 2.1.3,
618/1.19/616 m in 2.1.2, and 2,698 km/0.47 m/2,698 km in the one-epoch
mixed interval. The last interval is too sparse for a performance estimate.
Even the nominal Galileo-only window is **not a clean GPS control** in this
receiver: its local GPS L1–L2 observable changes by tens to hundreds of metres.
This could involve receiver behavior, signal coupling or other effects; the
comparison does not identify a cause.

The external **frequency-difference observables** remain comparatively stable
on the matched epochs. That gives context for a change in the victim observable
which the same diagnostic does not show at the two references; it does not
exclude an anomaly shared in another, untested measurement mode.
The local-only change is already large in all three windows, and subtracting
the network control leaves nearly the same median. **This case has not shown
an added attack-detection advantage over the local observable.** The smaller
combined spread outside the tests is descriptive and in-sample, since those
same exposed rows set the baselines. It is not a measured false-alarm rate or
population precision. The network-only channel cannot verify the local RF.

This is a geometry-free temporal diagnostic, not an absolute position or
time check. L1 C/A corresponds to external C1C, but local L2 CL and external
C2W are different tracking codes. Per-series centring removes a static offset,
not time-varying hardware or tracking bias. Event time uses the RAWX packet
order anchored before the tests; receiver time itself jumps during 2.1.2 and
2.1.4, and there is no independent clock. The official event log describes
transmitted signals, not a verified cause of every receiver measurement.
All code and pairing exclusions remain in the result. No threshold, attack
attribution, signal authenticity or prospective confirmation is claimed.

The next P2 question is specific: find a case where a network witness changes
a decision that reasonable local controls alone would make, or narrow the
product claim to independent **incident context** rather than detection gain.
That requires a benign control and a paired attack whose local evidence is
not already decisive; adding more formal workflow around this easy case will
not answer it.

Reproduce using the archive and station files listed in the
[intake](PNT_JAMMERTEST_PAIRING.md):

```console
python -m research.exploratory.pnt_rawx_contrast ARCHIVE.tar.gz "Spoofing/stationary/Medium Power (_1W)/Bands_E1_L1/2.1.3,2.1.2,2.1.4/240911_075843.ubx" 2024-09-11 TRO100NOR_S_20242550000_01D_30S_MO.crx.gz KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz NEW_OUTPUT.json --windows research/exploratory/inputs/pnt_jammertest_windows.json
python -m pytest research/exploratory/tests/test_pnt_rawx_contrast.py -q
```

The current command writes the v3 schema; the original v1 file remains as
historical evidence.
