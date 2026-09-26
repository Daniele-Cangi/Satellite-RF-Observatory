# Real G12 phase in the interval inverse: result and stopping point

This is exploratory work on the **previously exposed** G12 day (2026-09-05).
It uses actual C1C/C2W code and L1C/L2W carrier observations, reference-only
clock calibration and the existing `interval_fit` inverse. No G12 orbit or clock
product enters the fits. The original G12 outcome (`UNCERTAINTY_TOO_LARGE`)
and its 20 m code floor are unchanged. Neither this study nor its redesign is
prospective confirmation.

## Selection, access and failures

The [first access record](real_target_phase_access.json) fixed seven source
stations, five pre-supported phase stations, and twenty disjoint 90 s arcs in
the second half of the hour. Each arc fits the first three 30 s endpoints and
withholds the fourth. Raw and decoded RINEX files were SHA-256 checked against
the original acquisition receipt. The target-only parser reads just G12's
four required fields. The original reference parser and historical reports
were not altered.

The first five-station attempt has **zero admissible complete arcs**. STJO
phase disappears after the first three arcs; in those three, RF-only geometry
places G12 at 7.17°, 6.71° and 6.25°, below the 10° model mask. All 20 outcomes
are retained in `results/real_target_interval_v1.json`: three low-elevation,
seventeen incomplete. A code-only provisional fit is preserved for each of
the first three; it does not rescue their admission.

The [separate v2 access record](real_target_phase_access_v2.json) acknowledges
the prior target exposure and selects BOGT instead of STJO. Before BOGT target
values were decoded, its receipt-verified header showed complete GPS L1C/L2W
phase-shift declarations; the existing strict parser failed on unused
non-GPS declarations. `real_target_phase_v2.py` removes only non-GPS
`SYS / PHASE SHIFT` records in the adapter, keeping the GPS declarations,
other headers and observation body unchanged. The strict GPS parser still
rejects missing signals, bad scaling/wavelengths, loss-of-lock flags and
events. BOGT has 121 available G12 samples; YELL remains unsupported.
Reference-only BOGT calibration adds 497 held-out reference comparisons,
RMS 0.000284 m/s and maximum 0.002072 m/s with the median estimator. This
is relative performance, not a clock uncertainty bound.

## Paired real-RF inverse

All twenty v2 arcs have the five preselected receiver paths. Both fits use
identical code, RF-derived geometry and propagation corrections. A preliminary
code-only fit supplies target geometry for VMF3; no target orbit or clock is
consulted. The conditional weighting scenario retains 20 m code, 0.02 m
carrier endpoint, 2 m reference-clock offset, 0.01 m/s clock drift and 0.5 m
station-coordinate standard deviations. It does **not** propagate the full
correlation from the preliminary geometry and shared products; the model
chi-square is therefore a diagnostic under assumptions, not a physical
confidence test.

| Result on 20 arcs | Code only | Code + phase increments |
|---|---:|---:|
| Conditional model accepted | 20 | 5 |
| Model rejected | 0 | 15 |

On the **same five accepted phase arcs**, the 25 withheld receiver paths have
code residual RMS 3.557 m for code-only and 0.757 m for code+phase (20 paths
improve, five worsen). Withheld carrier-rate residual RMS changes from
0.1034 to 0.00831 m/s (22 improve, three worsen). These are target-RF checks
at one future endpoint, not an accuracy or population-coverage bound. The
other fifteen phase fits fail the existing conditional model test and are
not promoted because their state happened to look promising afterward.

The RF predictions were serialized and committed before the historical SP3
was read. `real_target_oracle_v2.py` verified the original rapid-SP3 receipt
hash and compared fitted ECEF position at each arc's final GPST tag, without
adjusting the states or selecting windows by the orbit. Its report records the
frozen RF report SHA-256
`33f7f3d34e66fe239f2fa71036b4fea73f76f6f90e5f496c3f1c8560c0393ba2`.
Nine-node interpolation is checked against eight nodes; the largest difference
in these comparisons is under 0.014 m. The SP3 is a historical IGS rapid
combination and may share upstream GNSS data with the reference products.

| Oracle position error, m | Count | RMS | Median | Maximum |
|---|---:|---:|---:|---:|
| Code only, all arcs | 20 | 48.62 | 29.75 | 96.02 |
| Code only, paired five arcs | 5 | 49.88 | 28.31 | 87.99 |
| Phase, conditionally accepted five | 5 | 55.41 | 14.66 | 120.68 |
| Phase, rejected fits (diagnostic only) | 15 | 108.48 | 64.42 | 256.81 |

The phase improves oracle position in **3/5** accepted paired arcs and worsens
it in **2/5**. The better withheld RF residual does not guarantee a better
position; the one 120.68 m phase error makes paired RMS worse. Oracle errors
are retrospective observations, **not** the prospective uncertainty radius.
No new accuracy promise, velocity validation, S3 admission or site claim
follows from these twenty highly correlated windows on one exposed target.

## S2 error-mode decision

| Error mode | What this work establishes | Remaining status |
|---|---|---|
| Reference phase increments | Measured leave-one-reference-out; median limits one-link influence | Unflagged BRAZ/G13 0.85 m/30 s discontinuity remains visible; no global slip bound |
| Target phase increments | Five conditional accepts; fifteen rejections; RF prediction improves on accepted subset | Target-specific propagation/clock/model correlations and continuity not qualified |
| Code endpoint errors | 20 real fits and withheld errors measured; original 20 m floor retained | Absolute station-specific bias and its covariance not bounded |
| Constant station code bias | Phase differences annihilate it; earlier transfer showed up to ~70 m position response per hypothetical 1 m at one station | **Unidentified amplitude; no credible total position envelope** |
| Reference orbit/clock, media, antennas | Fixed products and VMF3 used reproducibly | Conditional/shared products; target antenna effects and full correlations unresolved |

The decisive missing constraint is **absolute range bias**, not another small
reference RMS improvement. The next scientific change must measure or bound
that mode independently, or change the observable/geometric design so that
it becomes identifiable. Until then S2 cannot close with a useful physical
position envelope and a new prospective S3 attempt would lack a justified
margin. The general verification workflow may still report explicit failure;
it must not advertise these conditional errors as guaranteed accuracy.

## Replay

From repository root, with the original receipt-verified cached RINEX files:

```powershell
python -m research.exploratory.real_target_phase --cache <cache>/day-reference-work --output research/exploratory/inputs/real_phase/g12_target_phase.json
python -m research.exploratory.real_target_interval research/exploratory/results/real_target_interval_v1.json
python -m research.exploratory.real_target_phase_v2 --cache <cache>/day-reference-work --target-output research/exploratory/inputs/real_phase/g12_target_phase_v2.json --reference-output research/exploratory/inputs/real_phase/observations_gps_only_v2.json
python -m research.exploratory.reference_phase_clock research/exploratory/results/reference_phase_clock_gps_only_v2.json --phase-input research/exploratory/inputs/real_phase/observations_gps_only_v2.json
python -m research.exploratory.real_target_interval_v2 research/exploratory/results/real_target_interval_v2.json
python -m research.exploratory.real_target_oracle_v2 --oracle <receipt-verified-SP3.gz> --output research/exploratory/results/real_target_oracle_v2.json
```

Outputs and source hashes are retained in the linked JSON artifacts. Replay
historical v1 with the Git source version recorded in its report; v2 uses the
same interval fit routine rather than a separate solver.
