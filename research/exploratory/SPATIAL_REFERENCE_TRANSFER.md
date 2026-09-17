# Reference corrections transferred to excluded receivers

Shared-satellite corrections improve pooled later-time contrasts at receivers
excluded from local correction training, but **not every receiver improves**.
This is exposed-data development, not independent confirmation or a position
accuracy result.

| Fixed product family | Zero test RMS (m) | Excluded-receiver corrected RMS (m) | Improvement | Stations improving |
|---|---:|---:|---:|---:|
| CODE rapid | 1.009796 | 0.952836 | 5.64% | 6 / 7 |
| CODE final | 0.987925 | 0.952889 | 3.55% | 5 / 7 |

Each product scores all **3942 test paths**, exactly once across seven folds.
All shared-satellite fits have rank 21 for 22 reference columns: the one common
offset is removed by the station/epoch clock gauge. Every observed test
contrast is identifiable from the respective six-station training design.
No unseen-reference or rowspace failures occurred in this fixed sample; tests
verify that such failures would retain the entire block and a null full score.

## Receiver results

Positive percentages mean lower RMS than the same product's zero model.
Negative values are retained degradations, not grounds for excluding a station.

| Excluded station | Test paths | Rapid corrected RMS (m) | Rapid gain | Final corrected RMS (m) | Final gain |
|---|---:|---:|---:|---:|---:|
| ALGO00CAN | 518 | 1.074235 | 5.59% | 1.074450 | 4.12% |
| DRAO00CAN | 576 | 1.462006 | 0.49% | 1.462018 | −0.30% |
| STJO00CAN | 529 | 0.796276 | 3.73% | 0.796329 | 1.61% |
| YELL00CAN | 563 | 0.987511 | 5.60% | 0.987510 | 3.92% |
| BOGT00COL | 509 | 1.014379 | 9.58% | 1.014342 | 7.07% |
| BRAZ00BRA | 686 | 0.383555 | 36.20% | 0.383984 | 30.05% |
| AREQ00PER | 561 | 0.655278 | −0.36% | 0.655150 | −4.91% |

The earlier all-seven-station local training gave approximately 0.931 m with
either family; receiver exclusion gives approximately 0.953 m. Spatial
transfer costs performance while retaining a pooled improvement. This does
not establish a universal correction, and the aggregate gain must not hide
AREQ's degradation or the much weaker DRAO result.

## Frozen comparison

Commit `a3283d9` froze `spatial_reference_plan.json`, the analysis and checked
entry point before execution. It declares only the zero and shared-satellite
models, with no parameter tuning or selection by test score.

The two exact input reports are:

- `results/day_reference_v1.json`, SHA-256
  `ff4caa87d4963524252437184ab67128b9a75beaf704b664dff1951350b33600`.
- `results/final_reference_v1.json`, SHA-256
  `51faab82e28ac2a82d1bf4814bfb9f15cb1c6712fb51e3bf555d67ea29f7aaf3`.

Both retain the same September 5 10:00–11:00 GPST, seven-station, 22-reference
cohort with G12 excluded. This experiment reads only those frozen reference
residual reports: no new acquisition, raw target products or target fit.
Input checks reject mismatched cohorts, duplicate paths, target contamination,
nonfinite residuals and incomplete station/epoch blocks.

For each station, the training set contains **only the other six stations at
10:00–10:29:30**. Neither any historical row of the excluded station nor any
station's test-half rows enter its fit. Testing contains only the excluded
station at **10:30–11:00**, with the original fixed links. The existing SVD,
whole-block support and rowspace rules are unchanged. Pooled scores concatenate
the seven disjoint test-station sets; the folds share training measurements
and are not seven independent experiments.

Output: `results/spatial_reference_v1.json`, SHA-256
`376b4283c6451b5e3ce0f8927647f835db20d035a0d08012cf8bf6cf8106f035`.

Replay into a new file:

```text
python -m research.exploratory.spatial_reference_checked NEW_REPORT.json
```

The checked launcher pins the analysis, numerical helper and JSON/hash helper
before execution. Tests independently bind the launcher, plan and executed
sources to the pre-execution Git commit, as well as replaying the full report.

## What this establishes, and what remains

There is a transferable component in this conditional local residual model;
its benefit is not confined to receivers that trained the correction. However,
upstream CODE orbit/clock products may contain observations from the locally
excluded receiver. The clock at each test epoch was also calibrated in the
input study. Thus this is a test of clock-free residual contrasts, not
absolute future RF, fully independent receivers or physical covariance.

The next stage should connect error assumptions to **position and motion
uncertainty**, rather than repeatedly optimizing residual RMS. Map the current
estimator's sensitivity to independent, station-common and time-correlated
errors, explicitly retaining modes that centered contrasts cannot measure.
Keep zero and shared-correction alternatives, the degraded stations and the
original uncertainty floors. A separate exploratory propagation diagnostic
must not rewrite closed target events or promote these pooled gains to a
qualified uncertainty radius. New-data confirmation and the website remain
downstream of this scientific step.
