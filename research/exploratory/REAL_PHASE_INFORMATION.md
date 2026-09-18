# Real phase information and interval-inverse transfer

Exploratory development on the already exposed September 3 and September 5,
2026 reference cohorts. Neither original target (G14 / G12 respectively) is
numerically decoded. Closed experiments, their outcomes and uncertainty floors
are unchanged. No new prospective observation is opened.

## Question and implementation

Does phase contain useful information about temporal error, and does this
information survive transfer to position/velocity rather than only reducing a
reference RMS?

`real_phase.py` reuses the existing header parsers and imports only C1C, C2W,
L1C and L2W for the original reference allowlists. Compressed and decoded bytes
must match the original acquisition receipts. Sparse extraction avoids creating
an hour-long dense covariance matrix. RINEX 3.03 is admitted with unit legacy
wavelength factors; scaling is applied before converting full carrier cycles
to metres. See [IGS RINEX 3.03 specification](https://files.igs.org/pub/data/format/rinex303.pdf),
sections 5.4/5.5 and the observation-header/data tables.

The inputs retain rejected fields and reasons. Missing fields, nonzero phase
LLI, nonfinite values and header/event changes are not repaired or interpolated.
This checks declared continuity, not the absence of every unflagged cycle slip.
Absolute phase levels remove a training-only constant on the same uninterrupted
segment; intervals do not cross missing/rejected samples. Common-mode summaries
require at least four references. Alignment shifts constant on a link cancel
in increments, as does the original constant daily code-bias translation.

The reconstruction `phase_IF - code_IF + previous_code_residual` uses the exact
previous reference model and code clock calibration. It is a reference
diagnostic, not target-independent calibration: the old clock fit includes
the reference being examined. Changing an RF observable does not turn those
products into independent truth.

## Measured information

| Cohort | Parsed stations | Available / rejected extracted rows | Paired test intervals |
|---|---:|---:|---:|
| September 3, 03:30–04:30 GPST | 7/7 | 8071 / 147 | 3701 |
| September 5, 10:00–11:00 GPST | 5/7 | 6526 / 105 | 2598 |

The September 5 exclusions are YELL (an event in the scanned prefix) and BOGT
(phase-shift count/column declarations unsupported by the existing parser).
They remain explicit exclusions; no station or day is substituted. Extracted
rows include observations outside the prior elevation mask, so these counts
are not all admitted model rows. The report preserves mask, training and gap
exclusions separately.

| Test interval RMS, m/s | September 3 | September 5 |
|---|---:|---:|
| Code residual increment | 0.036611 | 0.037305 |
| Phase residual increment | 0.014362 | 0.014115 |
| Phase station-common component | 0.014361 | 0.014112 |
| Phase differential component | 0.000189 | 0.000240 |
| Code differential component | 0.036135 | 0.037175 |

Common/differential RMS uses the same interval rows (common values are repeated
once per contributing reference), not independent draws or a population
variance estimate. Common components are not identified receiver hardware
errors: code-clock estimation and shared model errors can contribute too.
Descriptive lag-30s phase correlations range from -0.595 to -0.235 on September
3 and -0.504 to -0.170 on September 5. Differencing/shared endpoint errors are
therefore not interchangeable with independent white interval noise. The JSON
also retains linkwise and matched-reference cross-receiver correlations with
pair counts; these do not establish a causal decomposition.

## Transfer through the existing inverse

`real_phase_inverse.py` calls `interval_fit.fit_intervals` and the existing
`interval_systematics.transport_systematics`; it introduces no new solver,
authority or checked executor. Both estimators receive identical endpoint codes,
receiver geometry and nuisance assumptions. Phase is either absent, used raw,
or corrected by the other available references (selected link excluded, at
least four others). This is a **hybrid sensitivity experiment**: actual receiver
coordinates and measured reference-error sequences are applied to a synthetic
vacuum trajectory. It is not an independent real-satellite reconstruction.

Six consecutive five-minute windows cover each cohort's evaluation half. For
each station/window, the lexicographically first complete reference is selected
by availability, never residual size or solution quality. Any missing station
or insufficient other-reference set rejects the whole window. All outcomes
are retained, including worsening cases and rejected fits.

The declared weighting scenario is 20 m endpoint code, 0.02 m endpoint phase,
2 m receiver-clock offset, 0.01 m/s receiver-clock drift and 0.5 m terrestrial
coordinate standard deviations. These are **conditional assumptions**, not
measured uncertainty or a new bound. Phase endpoint covariance is differenced
with the existing interval operator, preserving adjacent anticorrelation.
The comparison reports rank/conditioning, nonlinear fit status, position,
velocity, position at +60 s and synthetic future code/rate prediction errors.
It does not claim a held-out real receiver/time validation. The code weighting
and all historical scientific floors are unchanged.

All 12 windows were complete. Code-only and other-reference-corrected phase
were conditionally accepted in all 12; raw phase was rejected in all 12.
Acceptance is under the declared weighting scenario, not physical validation.

| Hybrid state errors, min–max | Code only | Code + corrected phase |
|---|---:|---:|
| September 3 position at t0, m | 1.99–21.66 | 11.35–19.95 |
| September 3 velocity, m/s | 0.0846–0.2365 | 0.0272–0.1168 |
| September 3 position at +60 s, m | 5.42–32.62 | 6.51–18.41 |
| September 5 position at t0, m | 6.56–82.42 | 3.02–75.34 |
| September 5 velocity, m/s | 0.0399–0.3229 | 0.0381–0.1306 |
| September 5 position at +60 s, m | 4.71–101.75 | 9.47–70.90 |

Paired worsening cases: **8/12** for position at t0, **3/12** for velocity,
**5/12** for position at +60 s. Thus the smaller differential phase residual
does not imply uniformly better positioning. Neither estimator loses parameter
rank in these geometries (36 parameters with five stations, 46 with seven);
adding phase does not create a missing absolute-bias constraint.

The deterministic response to a hypothetical 1 m constant code bias at one
station remains almost unchanged: maximum t0 position response on September
3 is 33.38 m code-only versus 32.96 m with phase; September 5 is 70.27 versus
69.68 m. These are sensitivities, **not measured bias amplitudes or confidence
radii**. This is the reason to prioritize an independent constraint on absolute
bias instead of further shrinking differential-phase RMS. The phase route is
promising for motion, but it cannot close S2 on its own.

## Error budget and decision boundary

| Mode | What is available | What is still missing |
|---|---|---|
| Code-minus-carrier temporal variation | Measured differences on exposed references | Unique attribution to code, phase or propagation |
| Differential phase increments | Measured, much smaller than code increments | Independently qualified joint covariance and transfer to a real target |
| Station-common phase increments | Measured after the existing code-clock calibration | Separation of receiver drift, calibration error and common model error |
| Constant station-specific range bias | Unit sensitivity propagated into state | Defensible physical amplitude bound; increments annihilate constants |
| Reference orbit/clock and antenna/media terms | Existing conditional reference model | Independent total-error envelope, including phase-specific effects |
| Slips and missing fields | Explicit admission failures and no gap bridging | A bound on unflagged slips; LLI=0 alone does not prove continuity |

The next substantive implementation is a real-target interval adapter with
reference-only clock calibration, the tested satellite excluded from that
calibration, propagation corrections evaluated from the fitted state rather
than its reference orbit, and joint calibration/measurement uncertainty.
The absolute-bias mode must be bounded alongside this work. Do not reduce a
position envelope from the small differential-phase RMS. Do not open another
confirmation until geometry and a credible total error envelope leave useful
margin. Website work remains deferred.

## Reproduction

Inputs: `inputs/real_phase/observations.json`, including original source hashes
and header interpretation. Baselines: unchanged `results/hour_reference_v2.json`
and `results/day_reference_v1.json`; receiver coordinates in the corresponding
`inputs/*_reference/positions.json`. Results: `results/real_phase_information_v1.json`
and `results/real_phase_inverse_v1.json`. Git preserves the implementation;
the reports record active-source/input hashes. No additional freeze is needed
for this exposed-data development.

```powershell
python -m research.exploratory.real_phase --inputs research/exploratory/inputs/real_phase/observations.json --output phase-information-replay.json
python -m research.exploratory.real_phase_inverse --inputs research/exploratory/inputs/real_phase/observations.json --output phase-inverse-replay.json
```

Adding `--cache <directory>` to the first command regenerates the extract from
the original `hour-reference-work` and `day-reference-work` compressed files,
verifying receipt hashes before decompression. Offline tests cover exclusion
of poisoned target records, scaling/unit semantics, loss of lock, event
rejection, gap/ambiguity boundaries and selected-reference exclusion from the
phase common-mode correction. Existing Linux/Windows coverage is preserved.
