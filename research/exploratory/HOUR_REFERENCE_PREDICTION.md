# One-hour reference contrast prediction — 2026-09-17

## New physical coverage and result

The exposed G14 reference network now covers **03:30–04:30 GPST on September 3,
2026**, at 30-second spacing. All seven fixed stations supply all 121 epochs;
all **847 station/epoch calibrations** pass. The one-hour window, seven stations,
21-reference allowlist, 10-degree mask, chronological split and four models were
fixed before acquisition. Target G14 states and codes are excluded from the
reference calculation. GOLD is not acquired or used.

Out of **8080 admitted reference code paths**, 7731 are evaluated and 349 are
omitted with explicit reasons. This denominator is conditional on the fixed
allowlist and C1C/C2W availability, not all signals broadcast by every satellite.
Station positions are recalculated across the entire hour using the same
regularized/solid-Earth/ocean/pole recipe as PR150, with gridded VMF3 atmosphere.
Overlap with the old eleven epochs reproduces the admitted codes exactly and
station positions within 0.96 micrometres (HARDISP output resolution is 1 micrometre).
The largest observed link endpoint direction change is 32.70 degrees.

Training uses 03:30:00–03:59:30 (60 epochs, **3777 paths**); testing uses
04:00:00–04:30:00 (61 epochs, **3954 paths**). No test residual enters coefficient
estimation. Results of every fixed candidate are retained:

| Model | Predicted test paths | Test RMS, m | Zero-correction RMS on same support, m |
|---|---:|---:|---:|
| Zero correction | 3954/3954 | 0.973703 | 0.973703 |
| Shared satellite offset | 3954/3954 | **0.937967** | 0.973703 |
| Station directional response | 3954/3954 | 0.963278 | 0.973703 |
| Station/satellite offset | 1990/3954 | 0.850606 | 0.897651 |

The shared-satellite candidate improves test RMS by approximately **3.67%**, with
all seven stations improving. The directional candidate worsens DRAO and STJO.
Station/satellite offsets leave **1964 test paths unsupported** as new links
appear; the entire affected station/epoch contrast block is marked unsupported.
Their 0.851 m score is a subset score and must not be compared with the full
0.974 m baseline. The all-test score for that model remains null.

| Station | Test baseline RMS, m | Shared-satellite RMS, m |
|---|---:|---:|
| ALGO | 0.808774 | 0.762822 |
| BOGT | 1.092725 | 1.014986 |
| DRAO | 1.115768 | 1.094479 |
| MKEA | 1.105226 | 1.066761 |
| PIE1 | 0.869217 | 0.852646 |
| STJO | 0.660057 | 0.604915 |
| YELL | 0.999805 | 0.983572 |

Whole-hour reference RMS is 0.942530 m. Descriptive station/satellite mean energy
is 11.06% of residual energy; this does not identify physical covariance or prove
a particular receiver, antenna or satellite error mechanism.

## What is predicted, and what is not

The predicted quantity is the **within-station/epoch residual contrast** after
removing the receiver common clock mode. Reference receiver clocks are still
recalibrated at each test epoch. Test geometry and paired retrospective precise
reference products are supplied; test residual values are excluded from the
candidate coefficient fit. These are conditional contrast predictions, **not
absolute future pseudoranges, future receiver clocks or a target trajectory**.

The shared-satellite result may reflect reference product/bias correlations as
well as persistent RF effects. Its improvement is evidence of some transferable
structure over this hour, not identification of its cause. Upstream precise
products can reuse the same station observations. This is an exposed development
sample, not a statistically independent or unexposed confirmation. No model has
been promoted to production, no uncertainty floor changed and no target fitted.

## Evidence, versions and reproduction

- `65f39d1`: plan and acquisition/station producer frozen before acquisition.
- `5a9cdc0`: complete restricted inputs and v1 analysis frozen before execution.
- `65d41fa`: v1 result preserved; v2 source compatibility fixed before v2 replay.

Original daily observation hashes match the historical BKG receipts. Orbit,
clock and attitude source hashes match the previously acquired paired CODE
products; expanded restricted clock/attitude extracts and reference-only orbit
bytes are retained. Celestial inputs use the pinned DE440s/EOP files and original
HARDISP sources already used by the preceding studies. Source snapshots and
download receipts remain inspectable under `inputs/hour_reference/` and
`inputs/hour_source_bytes/`.

The first provenance test exposed nine existing Python files whose executed
Windows bytes used CRLF while their Git blobs used LF. V1 source and scientific
result are preserved. V2 accepts only either the exact executed bytes or their
explicit LF equivalent for those nine named files. Original executed snapshots,
both hashes and Git ancestry are tested. Any other source edit is rejected;
there is no general whitespace normalization. Scientific outcomes are unchanged.

```powershell
python -m research.exploratory.hour_reference_checked NEW_REPORT.json
python -m pytest research/exploratory/tests/test_hour_reference.py -q
```

The report preserves all calibration diagnostics, residual rays, omitted paths,
coefficients, ranks, prediction support, errors and per-station scores. Tests
cover input/position overlap, target rejection, chronological cohorts, poisoning
test values without changing predictions, failure retention, full replay,
report byte identity and commit/source/input bindings across platforms.

The preparation command additionally needs the pinned full daily raw products,
`skyfield==1.53`, `hatanaka`, DE440s/EOP and `gfortran` on PATH. It writes new
artifacts exclusively; it is not an overwrite/resume command. The ordinary
analysis and tests consume the checked-in restricted artifacts offline.

## Next experiment

Keep the four candidates fixed and test transfer on another arc/day before
adopting shared-satellite offsets. Distinguish a gain on persistent links from
availability on newly rising references. Add absolute clock/time prediction as
a separate objective; this study does not supply it. Physical error covariance,
kinematic target inference, a new confirmatory campaign and product launch remain
open. S2 is still in progress.

## PR review follow-up

The active entry point is `hour_reference_checked.py`, frozen in `bcf674d`
before its replay. It validates fixed bias/antenna receipt and extract hashes
before invoking the unchanged v2 calculation. This closes a real gap: v2 alone
checked those extracts against mutable local receipts, although the recorded
v2 result already includes their exact hashes. The wrapper retains the v2 result
schema and numerical source identity; its own exact source is bound by a Git
ancestry/byte test. The complete CI replay now runs through this entry point.

Frame and loading inputs were already transitively bound before preparation:
`station_frame_epoch.read_frame()` pins root receipt `816ed068...` and its five
files; `ocean_pole_study.read_loading()` pins `16632931...`, the BLQ receipt and
extract, HARDISP sources and products. Their source bytes (including these
constants) are in the hour receipt's frozen source manifest. The station report
is separately pinned by `verified.PINS`. Discarding the returned diagnostic hash
maps did not remove these checks. The new entry point also revalidates those
chains, with mutation tests for both root receipts.

Review observations on `inputs/hour_source_bytes/estimation.py`,
`qualification.py` and `verification.py` concern preserved historical bytes.
They are not imported as code by this experiment and must not be edited to repair
historical evidence. This run performs neither target estimation nor oracle
interpolation; general acquisition hardening is separate from this replay.
Tests reject a simultaneous bias/antenna extract and matching-receipt change
before any calibration. No model, cohort, fitted coefficient or recorded
scientific outcome was changed by this review follow-up.
