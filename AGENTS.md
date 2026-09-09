# Satellite-RF-Observatory — Independent Position Verification

## Mission and causal order

Use public RF observations acquired through the Internet to reconstruct a
satellite's position independently of that satellite's orbit products. Declare
uncertainty before revealing an excluded receiver and an external orbit solution.

The scientific question is:
> Can Internet observations determine a new satellite position with defensible
> uncertainty, predict an excluded receiver, and agree with an unopened orbit?

```
predeclared target, stations, selection rule and error model
  -> public RF observations + allowed non-target calibration
  -> independent xyz and emission time, with uncertainty
  -> freeze solution, predictions, inputs and implementation
  -> reveal excluded receiver, then external orbit
  -> report error, uncertainty, all criteria and reproducible evidence
```

This replaces the old forward-orbit-first roadmap. A target orbit is an
evaluation reference after the freeze, not an input to inverse reconstruction.
User instructions continue to take precedence over this file.

## Acquired results: preserve scope and evidence

- DRAO labelled-forward DOY234 reached
  `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`. It is closed. Do not reopen, improve,
  replicate or relabel it during independent-positioning work.
- G08 DOY249 gave 188.705 m orbit-comparison error and 1.849 m held-out GOLD
  residual. Its prospective uncertainty radius was 21,607.660 m; the terminal
  remains `UNCERTAINTY_TOO_LARGE`. It did not pass the 10 km uncertainty limit.
- Preserve G08's frozen implementation, inputs and outcome under
  `experiments/gnss_inverse_positioning/`. Replay is a regression, not new proof.
- G12 DOY250 with seven fit roots closed `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`:
  eighteen consecutive common epochs did not meet its frozen 41-epoch rule.
- A separate G12 DOY248 eleven-epoch attempt reconstructed a new position:
  15.139 m external orbit error, -3.137 m excluded-GOLD residual, but prospective
  uncertainty radius 10,121.469 m. It remains `UNCERTAINTY_TOO_LARGE` and is
  closed. Its 5% margin and uncertainty floors must not be lowered after reveal.
  Preserve its plan, solution, receipts and executed sources under
  `experiments/positioning_g12_doy248/`.
- Historical forward and measurement-integrity experiments are reference
  material. Their gate sequence is not the roadmap for new work.
- G13 DOY247 through the configurable request worker closed
  `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`: zero eligible epochs common to the
  eight fixed stations. No position or target-orbit access. Preserve
  `experiments/positioning_g13_doy247_request/`; do not retry it with a new
  station subset. The local worker is delivered; web job submission is pending.
- G14 DOY246 reached `INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED` for one
  conditional historical event: 31.017 m external 3D error, 5755.157 m prospective
  uncertainty radius and -0.846 m excluded-GOLD residual. All eight calibrations
  passed. Its declared pool selected ALGO, BOGT, DRAO, MKEA, PIE1, STJO and YELL
  at the first qualifying 03:55–04:00 GPST window; AMC4's expected file was absent.
  Preserve `experiments/positioning_g14_doy246_network/` and its original scope.
  Do not rerun, tune or generalize this success into universal accuracy/coverage.

## Current delivery objective

The availability-to-dossier path has now completed a new passing G14 event.
The bounded scientific attempt is closed. The next product milestone is to
connect this controlled worker to web requests; no further search for passing
examples is implied. Broader repeatability needs a separate preregistered design.

The next accepted step is explicit network availability before execution.
The bounded candidate pool, fixed excluded receiver, structural subset/window
rule and terrestrial distribution requirements must be frozen before new data.
An availability report is permission to attempt calibration, not a verified
position. Never reopen G13 with the newly implemented subset rule.

The private three-event web archive is delivered. The user has now authorized
the next milestone: a configurable historical GPS request that can eventually
be launched from the site. First validate the reusable local request-to-dossier
path on one new predeclared event. Then connect a separately controlled job
runner to the web interface; do not execute the estimator inside a page request.
Keep operational completion separate from a scientific pass. Parameterization
alone adds no physical observable and must not be described as reducing uncertainty.

The user accepted continuing product work despite G12 DOY248 exceeding the
uncertainty criterion by 121.469 m (about 1.21%). This authorizes a first usable
web archive of the closed results. The 10 km scientific criterion is not a
blocking release gate for that archive. Preserve the original failed outcomes;
do not relabel them or equate 15 m observed error with 15 m prospective accuracy.

The web slice must let users select a documented event, see its inferred
position, observed error, prospective uncertainty and excluded-receiver check,
and download its evidence dossier. Missing positions stay missing. Consume
frozen receipts through a deterministic export with provenance checks; never
run the estimator or read a target oracle from an interactive page request.
Keep this archive visibly historical and experimental. A private review edition
precedes any separately authorized public launch.

## Scientific objective and information value

The first one-event milestone was reached by preregistered G14 DOY246: BOTH
prospective uncertainty radius <=10 km and subsequent 3D error <=10 km, plus
the excluded-receiver test. Preserve the conditional claim. A new event is
needed for additional physical evidence, and a validation design is needed
before claiming repeatability or population uncertainty coverage.

For scientific runs, consolidate the software required to execute and reproduce
the declared event. The current read-only web archive is separate product work.
Packaging G08 alone is insufficient scientific progress. Complete the bounded
event through its declared terminal; failure does not authorize indefinite
search for a passing example.

Before substantial work, state the new physical information it can produce.
Fix ordinary parser/runtime problems as engineering repairs, not new numbered
gates. When a physical route fails, identify the failed assumption, what was
learned, alternative physical mechanisms and the smallest worthwhile new test.
Infrastructure is not the default answer to poor geometry or missing observables.

## Target-state exclusion

The target's TLE, OMM, SP3, broadcast orbit/clock, orbit-derived corrections,
catalogue state, propagated previous solution, radius constraint or trajectory
must not inform event selection, preprocessing, calibration, initialization,
regularization, optimization or uncertainty tuning.

Allowed: terrestrial coordinates, declared physical constants and states/clocks
of explicitly identified NON-target reference satellites. Record this boundary.
Target-state independence does not mean absence of all reference ephemerides.

Discard target blocks from mixed navigation downloads as text BEFORE numerical
parsing; hash and retain the admitted reference-only input. Reject target
records again at the numerical calibration boundary. Removing or poisoning
excluded target blocks must leave admitted inputs unchanged.

Run estimation offline with only admitted inputs. Put held-out target and
oracle evaluation in a separate stage that verifies the solution freeze first.
Hashes and process separation support the audit; neither alone proves physical
independence or provides a trusted public timestamp.

## Selection, blinding and stopping

Before target measurement values are read, fix target/date, bounded station set,
excluded receiver, observable, structural window-selection rule, calibration,
transformations, nuisance model, uncertainty assumptions, thresholds, oracle
product rule, frame/time conventions, stopping rules and outcome labels.

Ground-coordinate-only or explicitly synthetic geometry design is allowed.
Do not use the real target orbit to choose the network or interval.
If selection uses fit-side numerical data, preregister the exact rule, account
for selection in the claim and keep confirmation independent. Prefer a simple
structure-only chronological rule for the next event.

Implementation defects may be repaired before confirmation if changes/accesses
are recorded and selection/outcome rules remain fixed. After confirmation, do
not tune thresholds, swap stations/targets, shift time, refit offsets or silently
rerun. A defect affecting a revealed result invalidates that attempt; a new proof
requires new unexposed confirmation evidence.

## Physical and numerical obligations

- Solve at least xyz and relevant emission-time/clock nuisance. A snapshot is
  not velocity, an orbit or independently discovered satellite identity.
- Check rank after nuisance removal, alternative branches, far-field degeneracy
  and geometric amplification. Receiver count alone is not observability.
- Common reception epochs and common emitted events differ. Interpolation must
  bracket the event; do not silently extrapolate.
- Make GPST/UTC, week rollover, date boundaries and frame epoch explicit. Use
  integer/base epochs plus small local floating-point offsets for fine time.
- Include Earth rotation over light time, reference clock conventions and
  relevant propagation/receiver terms. Never correct the fit with target oracle.
- Propagate correlations from code tags, reference clocks and ground coordinates
  through the complete estimation chain.
- Justify uncertainty floors/envelopes or explicitly label them conditional
  design assumptions before reveal. Do not lower them after an accurate result.
- Finite branch searches, axis profiles, Monte Carlo and box corners are
  diagnostics, not certified global bounds or proofs of 95% coverage. Report
  numerical search limits and model assumptions.
- Small residuals are not position accuracy. Oracle error is not prospective
  uncertainty. Report both without substituting one for the other.

## Quantitative evaluation and claims

For the current milestone require all of:
1. Qualified measurements/calibration with no target-state contamination.
2. Numerically identifiable finite solution with branches investigated.
3. Declared total prospective 95% uncertainty radius <=10,000 m.
4. Excluded receiver absolute range-equivalent residual <=100 m AND within its
   predeclared predictive band, without holdout-fitted offsets.
5. Subsequent 3D orbit error <=10,000 m and consistency with frozen uncertainty,
   under the declared oracle error treatment.

Reserve `INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED` for all required criteria
passing within the explicitly limited, conditional claim. Distinguish missing
or invalid data, calibration failure, non-identifiability, excessive uncertainty,
holdout rejection, oracle rejection and contamination. Report every attempt.

An independently produced orbit may reuse the same ground measurements. Do not
claim statistically disjoint oracle evidence without establishing it. Repeated
events support repeatability; coverage claims need an appropriate validation
design and sample size.

## Engineering for the next physical result

Keep a small active positioning package separate from frozen experiments.
Make target/date/stations/window explicit inputs, without machine paths or
hidden date constants. Prefer portable stage commands and bounded files over
a framework, database, service mesh or global receiver inventory.

Maintain reproducible dependencies and meaningful tests for units/signs,
emitted-event alignment, independent receiver-clock gauge shifts, target
exclusion, rollover, branches/degeneracy and data-to-result replay. Run active
tests in CI. Automated tests do not replace a new real event.

Preserve frozen outputs before improving active code. Never overwrite an event
to make a regression green. Historical experiments stay immutable except for
separately identified user-authorized maintenance.

## Experimental website

Build a public archive/service of reproducible verifications for supported
satellites and epochs with qualified Internet measurements. Every result must
show event time, stations, inferred position, uncertainty, withheld checks,
oracle error, versions and downloadable evidence. Show failed/inconclusive
outcomes plainly.

A verified historical position is not a live position. Propagation is a labelled
prediction. GPS support is not support for all satellites. Worldwide uniqueness
is an unproven product claim.

The web layer consumes sealed results and must not substitute an oracle-derived
position or hide uncertainty. The thin archive is the current product milestone.
On-demand positioning, monitoring and a public launch remain separate work;
they are not implied by publishing historical verification dossiers privately.

## Working agreement

The user authorized this change of direction and immediate implementation of
the next bounded inverse experiment. Proceed with necessary local edits, tests
and public-data acquisition without repeated confirmation. Honor the freeze/
reveal order and the experiment's stopping rules.

Do not message other people or publish/deploy externally without authorization.
The user has authorized ordinary Git commits and pushes when needed for this
work. Review the exact outgoing changes and push without forcing history.
This does not authorize deployment or merging protected/default branches.

### GitHub CLI on Windows

- GitHub CLI is authenticated as `Daniele-Cangi` through the Windows keyring.
- Always run `gh` commands requiring network or authentication outside the
  Windows sandbox. Verify authentication with `gh auth status` outside it.
- Socket, DNS and `api.github.com` access errors inside the sandbox are network
  failures, not evidence of expired credentials. Never run or request
  `gh auth login` based only on an error from inside the sandbox.
- Prefer `gh` over the browser or GitHub connector for forks and pull requests.

Do not spawn sub-agents merely because this file is named AGENTS.md; use them
only when separately requested or instructed.

Communicate concrete physical findings and remaining uncertainty. Finish with
what changed, what was measured, what passed/failed and where evidence is stored.
