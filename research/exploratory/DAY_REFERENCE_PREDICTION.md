# Distinct-day reference prediction — 2026-09-17

## Fixed sample and result

The September 5, 2026 reference experiment covers **10:00–11:00 GPST**, with
121 epochs at 30-second spacing. All **847 station/epoch calibrations** qualify.
The fixed historical G12 reference network comprises ALGO, DRAO, STJO, YELL,
BOGT, BRAZ and AREQ; its 22-reference allowlist excludes G12. GOLD is not used.
Five stations overlap the September 3 network; BRAZ/AREQ replace MKEA/PIE1.
Target code and states are excluded from the reference calculation.

Of **9009 admitted paths**, **8074** are evaluated and **935** are explicitly
below the 10-degree elevation mask. Counts are conditional on the fixed reference
allowlist and C1C/C2W availability, not all satellite signals. No replacement
stations, shifted interval or after-result candidate changes were used.

Training uses **10:00–10:29:30** (60 epochs, **4132 paths**); testing uses
**10:30–11:00** (61 epochs, **3942 contrasts**). The four candidate definitions
and chronological split procedure are unchanged. All coefficients are estimated
locally on this day; no September 3 coefficients or observations enter fitting.

| Model | Predicted / test paths | Supported RMS, m | Zero RMS on same support, m |
|---|---:|---:|---:|
| zero | 3942/3942 | 1.009796 | 1.009796 |
| shared_satellite | 3942/3942 | 0.931068 | 1.009796 |
| station_direction | 3942/3942 | 0.978263 | 1.009796 |
| station_satellite | 2801/3942 | 1.038395 | 1.078423 |

Shared-satellite offsets improve full test RMS **1.009796 → 0.931068 m (7.80%)**,
with all seven stations improving. This repeats the sign of the 3.67% and 4.15%
local-training gains on the two September 3 arcs. The magnitudes are descriptive
comparisons across different samples, not a pooled population accuracy estimate.

The directional candidate improves 3.12% locally, also at all seven stations.
This does not undo its failed temporal transfer on September 3. Station/satellite
offsets leave **1141 paths unsupported**; affected complete station/epoch blocks
are retained as failures. Their 1.038395 m supported RMS must be compared only
with 1.078423 m on the same support, not the full 1.009796 m baseline. The all-test
score remains null; STJO worsens on the supported subset.

## Shared-satellite station scores

| Station | Zero RMS, m | Corrected RMS, m |
|---|---:|---:|
| ALGO00CAN | 1.137849 | 1.064980 |
| AREQ00PER | 0.652944 | 0.586716 |
| BOGT00COL | 1.121803 | 1.005948 |
| BRAZ00BRA | 0.601222 | 0.357561 |
| DRAO00CAN | 1.469168 | 1.442810 |
| STJO00CAN | 0.827138 | 0.763785 |
| YELL00CAN | 1.046075 | 0.966776 |

For the **five stations common to September 3**, all 2695 test paths are
predicted: **1.144879 → 1.078797 m (5.77% gain)**. This is an evaluation
subset of the full-network fit, fixed by the plan; the model is not refitted on
only those five stations. It does not isolate the effect of network composition.

## What this establishes and what remains open

The shared-satellite candidate improves held-out-time contrast RMS on three
arcs across two days. The second day changes the time, two stations, excluded
target, reference allowlist and daily products. This is therefore replication
of the method on another exposed sample, **not an isolated causal day effect**
or cross-day transfer of frozen coefficients. The eleven previously exposed
10:30–10:35 epochs are part of the new test interval; this is not new unexposed
confirmation or a statistically disjoint validation campaign.

Receiver clocks are recalibrated at every test epoch; retrospective precise
reference products provide geometry. Predicted quantities remain clock-free
within-station/epoch contrasts, not absolute future RF or target positions.
Products may reuse station observations. A shared residual does not identify
satellite physics rather than upstream orbit/clock/bias processing. No production
correction, uncertainty-floor change or physical covariance qualification.

## Provenance and reproduction

- `736b536`: plan, authoritative input chain and producer frozen before acquisition.
- `6237b99`: restricted input artifacts and analysis frozen before execution.
- Input receipt SHA-256: `42b8c63c6799fe24428a0a0dfd492ac9d30a3a562e80fb35b8eada62819eaaf5`.
- Report SHA-256: `ff4caa87d4963524252437184ab67128b9a75beaf704b664dff1951350b33600`.

All seven daily observation files were downloaded again from their archived BKG
URLs. Compressed and decoded hashes agree with the pinned admission manifest.
Untrusted sidecars are not the authority. Timed, attitude, bias and antenna
receipts/extracts are validated against the frozen prior report before use;
copied orbit bytes are checked before a new receipt is written. Frame, loading
and station-report provenance is recorded and revalidated during replay.

The observation day is derived from the fixed plan. Station coordinates, solid
Earth tides, HARDISP CMC:NO and the 2018 pole model are recalculated for the hour.
VMF3 MJD is derived from the same date (61288); EOP interpolation must bracket
each epoch. Old eleven-epoch code observations match exactly and station
positions match within 2 micrometres. Only the nine previously recorded CRLF/LF
source variants are accepted. Frozen historical evidence is unchanged.

```powershell
python -m research.exploratory.day_reference NEW_REPORT.json
python -m pytest research/exploratory/tests/test_day_reference.py -q
```

Preparation uses `research.exploratory.prepare_day_reference` with work, raw
product cache, celestial input directory and a new output directory. It requires
original pinned daily files, Skyfield 1.53, Hatanaka and gfortran; analysis and CI
replay use the checked-in restricted inputs offline. It is a fixed experiment,
not a general multi-day CLI. Tests include authoritative input mutation, date/
cohort binding, target exclusion, failure retention, Git ancestry, identical
four-model test cohorts and complete numerical replay with weather-date guards.

## Next experiment

Before promotion, hold the admitted RF sample and candidate definitions fixed
and compare a separately sourced, convention-compatible reference product set.
This can test whether the shared correction follows the reference products or
persists across processing choices. Different providers do not automatically
mean statistically independent data. Keep failed products and unsupported paths;
do not claim physical covariance from residual RMS alone. S2 remains open.
