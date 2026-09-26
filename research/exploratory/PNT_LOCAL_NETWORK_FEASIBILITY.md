# PNT fixed-receiver feasibility: first exposed-data cycle

## Decision

**Continue to a bounded offline P2 prototype, but do not claim spoofing detection
or an improvement over local checks yet.** The current corpus supports a
contemporaneous local/network comparison and exposes a useful diagnostic
distinction between local and shared residuals. It has no recorded local attack,
independent absolute-time witness, or demonstrated equal-false-alarm advantage.
The next decisive input is a fixed receiver's time-tagged per-satellite
observables during a documented attack **and** simultaneous independent
reference stations. Without that pair, additional software analysis of this
clean corpus will not establish the proposed cyber claim.

## P0: data and measurement contract

Use an existing receiver at fixed, independently surveyed coordinates. Record
the local RINEX/receiver observables by satellite and epoch, clock output when
the time claim matters, navigation/configuration changes, and the observation
quality flags. Preserve matching external station observations, coordinates,
station/receiver metadata, products, GPST/UTC conversion and latency. At least
two physically distinct simultaneous external receivers are required for this
first comparison; mirrors of one archive are not extra witnesses. Treat all
shared products and any survey derived from the same RF as dependencies.

The reusable clean development path is the [September 5 reference cohort]
(DAY_REFERENCE_PREDICTION.md): seven archived BKG receivers, 30-second epochs,
10:00–11:00 GPST, GPS C1C/C2W ionosphere-free code and known reference orbits.
For this study ALGO is the local receiver and the six others are candidate
network witnesses. The [excluded-reference report]
(PSEUDOTARGET_REFERENCE.md) provides 61 later epochs for 22 pseudo-target
rotations. Every pseudo-target is excluded from its own clock calibration;
3942 observations evaluate and 5452 grid positions remain unadmitted. Those
stations are geographically dispersed, share CODE products, and are not a
recorded attacked site. Historical geodetic coordinates are usable for this
diagnostic but do not create independent physical truth for every error mode.

Candidate attack data, with no download or RF experiment in this cycle:

| Family | Available evidence | Fit for this fixed-site network claim |
|---|---|---|
| [TEXBAT][texbat] | UT's GPS L1 C/A binary RF recordings include clean and spoofed scenarios, including time-push; research use is permitted but redistribution is discouraged. | Valuable local receiver challenge after an RF-to-observable adapter; the public description does not provide simultaneous independent geodetic witnesses. L1-only is not C1C/C2W. |
| [FGI-JSDR][fgi] | FGI publishes raw I/Q examples for GPS L1 C/A, GPS L5 and Galileo, with several spoofing types. | Useful modern signal stress tests; format conversion, exact epochs/truth, license and concurrent external witnesses need checking for a chosen file. Publication of I/Q alone does not establish network pairing. |
| Documented multi-station geodetic attack | No suitable fixed-receiver attack plus independently observed, time-aligned geodetic network event has been qualified in this cycle. A [three-vehicle dataset][fleet] has synchronized vehicles and spoofed CAR1, but it is a mobile fleet, not this fixed-site topology. | Keep this slot unresolved. Do not substitute an unrelated multi-receiver recording or call clean IGS data an attack. |

The present retained extracts have **no independent non-GNSS time reference**.
An absolute timestamp verdict remains unsupported even if geometry checks pass.

## P1: one physical contrast on the existing report

[`pnt_local_network.py`](pnt_local_network.py) reads the tracked
`results/pseudotarget_v1.json` (SHA-256
`d12c3d1b57520569b39c9faacb1c0089065f229d60ad87fa709806201f50c823`).
For a pseudo-target and identical GPST epoch, `local` is ALGO's held-out code
residual after reference-only clock fitting; `network` is the median residual
of available external receivers; `combined = local - network`. This is a test
of consistency with a **declared known orbit**, not independent orbit recovery.
The detector subtracts each channel's median from 10:30–10:44:30 and chooses
its empirical 99th-percentile absolute threshold there. It evaluates
10:45–11:00 without refitting. At least five earlier observations per
pseudo-target and two simultaneous external witnesses are needed. A pre-event
normal baseline is an assumption; a persistent attack present during training
could be learned away.

| ALGO control | Training alerts / 270 | Clean later alerts / 248 | +10 m on ALGO pseudo-target / 248 | +10 m shared target residual / 248 |
|---|---:|---:|---:|---:|
| Local | 2 | 13 | 248 | 248 |
| Network only | 2 | 3 | 3 | 248 |
| Local − network | 2 | 11 | 248 | 11 |

The 10 m alterations are **additive changes to already calibrated residuals**,
not replayed RF, a spoofing waveform, a trajectory, or a tested receiver
response. The source's known-orbit/model errors remain in the clean baseline.
The same code retains +5 m and +25 m scenarios, unsupported source rows, and
six receiver rotations in the [machine-readable report]
(results/pnt_local_network_v1.json). At +5 m on ALGO, local/combined alert in
232/225 of 248 cases; at +10 m both alert in all 248. These counts are
conditional on this chosen perturbation and thresholds; they are not attack
recall. The 248 epochs/satellite rows are correlated, not 248 independent
incidents. Training thresholds yield **different** realized clean alert rates
(13/248 local versus 11/248 combined); an equal-false-alarm network benefit
has not been shown. Station rotation is mixed: YELL has 10 local versus 14
combined clean alerts, for example.

The mode structure is more informative than the high synthetic alert count:

- Remote-only observations are identical when only the local residual changes.
  They cannot validate the local RF.
- A shared residual perturbation moves both local and remote channels and
  cancels in their difference. That contrast can help distinguish a local
  anomaly from a shared model/product/network effect under its assumptions.
- A receiver-wide common pseudorange offset is absorbed by the fitted
  receiver clock in this idealized differential channel. No separate time
  reference was measured here, so an absolute-time verdict is inconclusive.
- A local hardware fault and local spoofing with the same per-satellite
  residuals are observationally identical to this test. The result is
  `INCONSISTENT_WITH_MODEL` at most, never attribution to an attacker.
- Consistency-preserving attacks, biased coordinates/products, stale or
  compromised witnesses, and an attack already in the training baseline
  remain untested or indistinguishable. Source coverage is conditional on the
  22-satellite allowlist and the original 10-degree elevation mask.

The next P2 iteration should adapt one suitable **documented** attacked fixed
receiver to the existing observation path, pair its exact epochs to archived
external RINEX, and retain local-only, remote-only and combined controls.
Measure false alarms on benign intervals, failure/unsupported fractions and
time to alarm by episode. If no paired attack recording is available, specify
a cooperative acquisition with a separate time witness only if the time claim
is pursued. Do not advance to prospective confirmation or a website verdict
on this hybrid result.

Reproduce the compact analysis with:

```console
python -m research.exploratory.pnt_local_network NEW_OUTPUT.json
python -m pytest research/exploratory/tests/test_pnt_local_network.py -q
```

[texbat]: https://radionavlab.ae.utexas.edu/texbat/
[fgi]: https://www.maanmittauslaitos.fi/en/research/research/gnss-specialists/fgi-gnss-jamming-and-spoofing-dataset-repository-fgi-jsdr
[fleet]: https://doi.org/10.57745/3C63J0
