# Reconstructing real reference satellites without their own products

## Result and decision

**The current interval-clock model now has an absolute-state diagnostic on
real RF, rather than RF residuals alone. S2 remains open.** The corrected
[v2 result](results/reference_state_validation_v2.json) produces trajectories
for four of the 22 original reference candidates. Their discrepancies against
CODE's modeled IF antenna-center trajectories are 66–210 m RMS in position and
.013–.028 m/s RMS in velocity. Conditional formal uncertainties remain much
wider, branch searches remain incomplete, and the reference products share
upstream observations. This is not independent truth or prospective accuracy
qualification.

The [older pseudo-target study](PSEUDOTARGET_REFERENCE.md) evaluated differential
RF using known target states. This study instead excludes each candidate's
products from its own calibration, initialization and fit, and evaluates the
resulting position and motion afterward. The G12 trajectory is never opened.

## Data and exclusion boundary

Use the existing September 5, 10:00–11:00 GPST archive, all 22 declared GPS
references and seven station identities. The reference-only phase extract has
six supported stations; unsupported YELL remains in the input provenance.
Every candidate retains twenty even chronological 60 s windows, with a separate
+30 s RF endpoint. Initial coverage uses only available three-endpoint RF
records and requires at least five receivers. No orbit-derived target mask,
historical fitted state, radius constraint or preferred satellite is used.

In each fold, remove its candidate as text before numeric orbit, clock, bias,
antenna or attitude parsing. Remove its RF before reference-code translation
and clock calibration. Recompute receiver offsets using the existing residual,
subset, ground-coordinate and rank checks, and phase increments using the
G12-excluding reference median with the candidate also excluded. Minimum four
remaining references and existing thresholds are retained.

Reference geometric admission at 10 degrees precedes weather evaluation.
Three training code snapshots use the existing solver and reference offsets;
they require a unique exterior-Earth branch for this preparation rule. Retain
their branch records and keep receivers above 10 degrees at all three epochs.
No residual-based trimming or station replacement is used. The full shared fit
retains its own branches and failures. Snapshot ambiguity is a **pipeline support
limit**, not proof that the full dynamic RF problem is physically unresolvable.

Fit the unchanged central+J2 dynamics, free constant station-code contrasts,
interval receiver clocks and free satellite-clock curvature. Use the previously
declared `shared_endpoints_added` conditional covariance, historical floors,
10-degree mask and p=.01 criterion. No covariance rescaling, new force tuning
or target-product correction is introduced.

All candidates' fits and RF predictions are fixed before dedicated state-scoring
oracles and RF scores are evaluated. Exclusion is **per fold**: a satellite is
an allowed reference in another fold, so its products can already have been
decoded there. This exposed archive is not a process-wide value-blind opening.
The claim is numerical exclusion from its own selection/calibration/fit.

## Coverage and retained failures

All 440 candidate/window slots remain visible:

| Preparation outcome | Windows |
|---|---:|
| Fewer than five RF receivers | 336 |
| Ambiguous RF snapshot geometry | 23 |
| Fewer than five receivers after the RF-derived mask | 18 |
| Prepared | 63 |

Seventeen candidates have insufficient prepared arcs, including G06 and G13,
whose RF snapshot branches remain ambiguous. G11 has nine prepared arcs but
both initialization branches fail: one trial is at **9.996 degrees at AREQ**,
the other is inside Earth. No iterations or residual rejection occurred.
This is a numerical/domain failure, not evidence that its real trajectory
violates the model. Do not substitute its earlier partial-cohort fit or lower
the 10-degree mask to conceal that failure.

Four trajectories use the remaining 54 prepared arcs. Each retains one fitted
candidate plus an interior-Earth initialization failure, hence
`BRANCH_SEARCH_INCOMPLETE`. None receives a global uniqueness or physical
qualification claim.

## State and RF evaluation

At matching GPST epochs, compare the fitted ECEF point with CODE's interpolated
COM plus the declared IF antenna offset rotated with CODE attitude. Retain COM
position discrepancies separately. COM velocity uses the existing nine-node
orbit polynomial derivative; only the metre-scale antenna displacement is
differenced at ±.5 s. No candidate clock or bias is needed for this state oracle.
Propagate the fit's marginal six-state covariance with its state transition
matrix, without residual scaling.

| Candidate | Fit arcs | State epochs | Position RMS, m | Velocity RMS, m/s | Largest formal position 1-sigma axis at fit epoch, km | Excluded code RMS, m |
|---|---:|---:|---:|---:|---:|---:|
| G05 | 20 | 40 | 156.13 | .01254 | .754 | .554 |
| G19 | 8 | 16 | 146.01 | .02811 | 6.857 | 1.303 |
| G20 | 10 | 20 | 66.20 | .02221 | 3.718 | .764 |
| G21 | 16 | 32 | 210.30 | .01927 | 1.253 | .738 |

There are 108 evaluated state epochs from **four fitted trajectories**, not
108 independent trials. Only one state epoch per candidate and twenty RF
receiver predictions in total lie beyond all that candidate's training times.
At those four future epochs, position discrepancies are 152.41, 141.70, 77.02
and 214.72 m respectively. The other epochs/predictions are within the shared
training span. All 292 RF receiver/endpoints are scored; phase-rate RMS ranges
from 7.78 to 10.60 mm/s. No result is selected by its oracle error.

All 108 state errors lie within the broad formal 95% position and joint-state
ellipsoids. That count does not establish coverage: epochs share fitted states,
folds share references/products, and the error-budget assumptions remain
unqualified. Largest formal position 95% axes at the initial epochs range from
2.11 to 19.17 km. Small training costs and p-values numerically 1.0 do not make
those uncertainties physically calibrated or the positions universally accurate.

## Initial execution and engineering correction

[v1](results/reference_state_validation_v1.json), produced at `6e4042d`, remains
byte-identical with its original source in Git. It had 33 atmosphere-domain
preparation failures and ten calibration rejections. Its code evaluated VMF3
before excluding some below-mask references. The corrected order masks the
reference geometry first; the mask, weather domain, floors and estimator are
unchanged. v2 is a new exposed-data execution, not a retroactive relabeling.

More valid input does not guarantee smaller errors. On matched evaluation
epochs, position RMS changes as follows:

| Candidate | Matched epochs | v1 RMS, m | v2 RMS, m |
|---|---:|---:|---:|
| G05 | 22 | 141.37 | 156.22 |
| G19 | 10 | 109.28 | 146.79 |
| G20 | 12 | 126.79 | 69.59 |
| G21 | 16 | 207.83 | 210.13 |

G11's earlier smaller-cohort trajectory is retained in v1; the corrected
expanded-cohort initialization fails in v2. These worsening cases are part of
the result. No previous outcome, target G12 result or production floor changes.

## Next useful work

The diagnostic distinguishes achieved trajectory discrepancies from uncertainty
and support limits. Improve RF-only initialization and ambiguous-branch
preparation while preserving final admission criteria, rather than interpreting
those failures as a need for new hardware. Separately qualify the joint
clock/bias/propagation error budget and test a fixed method on different,
appropriately unexposed data before claiming S3 or population coverage.
The current comparison cannot establish an independently certified error bound.

## Reproduction

```console
python -m research.exploratory.reference_state_validation NEW_OUTPUT.json
python -m pytest research/exploratory/tests/test_reference_state_validation.py -q
```

Existing input/source hashes and Git history bind both versions. Tests poison
the candidate's products and RF before its reference calibration, poison its
future values, check geometric masking before weather/phase numeric access,
retain ambiguous branches and missing evaluations, verify matching-time state
and covariance scoring, and ensure scoring oracles follow all fits. CI replays
the retained RF/state scores and provenance without regenerating all folds.
Existing Linux/Windows workflows are unchanged. Codex provides substantive PR
review; SonarQube is not part of the current workflow.
