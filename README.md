# Satellite RF Observatory

Reconstruct satellite positions from public RF observations obtained through
the Internet, without supplying the target's orbit to the calculation. Declare
uncertainty before testing an excluded receiver and opening an orbit reference.

The one-event milestone was reached by G14 DOY246. The active objective is now
a [general verification workflow](docs/GENERAL_VERIFICATION_WORKFLOW.md): request
a supported satellite/day, assess available observations, estimate with declared
uncertainty, and return verified evidence or a precise reason for an inconclusive
result. Development starts locally with the historical GPS code profile.
Scientific validation continues as part of that objective. The five-event
archive remains documentation; automatic request execution and public deployment
are not delivered. The first local slice prepares requests and reads sealed
results through `python -m service`; see [the service commands](service/README.md).

The preserved [scientific project](docs/SCIENTIFIC_ROADMAP.md) supplies the research
and validation work for this objective. Its first [S0/S1 report](research/kinematic/results/REPORT.md)
finds a conditional gain from added range-rate observations in an idealized
synthetic model. This is not yet real Doppler integration or new satellite proof.

The next [S2a result](research/kinematic/results/S2_REPORT.md) validates a
receiver-time vacuum model with Earth rotation, clock drift and correlated
noise against an independent inertial generator. The
[remaining S2 requirements](research/kinematic/S2_MODEL.md) precede any real
campaign: RF qualification and the total model-error envelope are still open.

The [S2b reference bridge](research/kinematic/results/S2B_REPORT.md) adds bounded
RINEX import, reference-only clock calibration and an unused-Doppler check.
All six synthetic cases and failure outcomes are retained. Real receiver
qualification and the inverse model-error envelope remain prerequisites for S3.

The subsequent bounded [phase-transform header audit](research/kinematic/S2_PHASE_TRANSFORM_HEADER_AUDIT.md)
closed `PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED` on its final DOY243 artifact.
Five of eight fixed roots supplied an explicit RINEX coordinate ledger; DRAO,
STJO and YELL failed the frozen composite format admission before their
transforms could be qualified. No observation record or value was exposed, and
this is not a receiver-performance or orbital result. S3 remains blocked.

An offline [five-root local-feasibility audit](research/kinematic/S2_FIVE_ROOT_FEASIBILITY.md)
then tested only the five successful root coordinates over a frozen, target-free
synthetic family. Local rank is complete in all 181 jointly visible cases, but
the +60 s conditional envelope ranges from 0.501 km to 83.332 km and is <=10 km
in only 65 cases. Five fit roots also cannot supply the required independent
held-out root. The terminal is `FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE`, not
a measurement or orbital result.

A second offline [code-only held-out audit](research/kinematic/S2_HELDOUT_CODE_TOPOLOGY.md)
finds DRAO to be the strongest sixth-root geometry without using a target orbit:
it is visible in all 181 predecessor cases and retains positive conditional
slack in 180. The median residual physical budget is nevertheless only 12.530 m,
and one case already exceeds the 100 m held-out envelope before unresolved
physics. DRAO was not accessed or admitted by that topology audit.

The subsequent bounded [DRAO code-header qualification](research/kinematic/S2_DRAO_CODE_HEADER_QUALIFICATION.md)
materialized and hash-bound one independent full-day product without opening
any observation record. It stopped `DRAO_CODE_HEADERS_NOT_QUALIFIED` because
the header did not expose the frozen named C1C/C2W format. No legacy label was
reinterpreted post-access. The promising geometry therefore remains unavailable
as a measurement root, and S3 is still blocked.

A further offline [four-fit/one-heldout audit](research/kinematic/S2_FOUR_FIT_ONE_HELDOUT.md)
shows that a sixth root is not topologically mandatory when the temporal
code/interval-phase structure is retained. All five four-root fits have local
rank across the 181 frozen synthetic cases. Reserving GOLD produces 62 cases
that also meet the conditional 10 km fit and 100 m held-out criteria; reserving
PIE1 produces 60. The other three allocations produce none, and no 45,000 or
60,000 km case passes. This result is synthetic and conditional: actual
five-root measurement admission and the physical envelope remain unresolved,
so S3 is not yet authorized.

The first real target-free qualification of that topology then closed
`FIVE_ROOT_STRUCTURE_NOT_QUALIFIED` on DOY242. All five artifacts were available
and hashed, and ALGO/MKEA/PIE1 each supplied a complete 2,880-epoch structural
scan. BOGT and GOLD stopped at an exact-zero L1C phase-shift clause before body
scanning. This does not establish missing measurements: static declared phase
offsets are representable in interval differences, and GOLD is code-only. The
[failure attribution](research/kinematic/S2_FIVE_ROOT_STRUCTURE.md) therefore
keeps common-window and physical-envelope clauses `NOT_EVALUATED`. No
observation number was converted and DOY242 cannot be retried.

The bounded role-specific repair then used distinct DOY241 and reached
`FIVE_ROOT_ROLE_STRUCTURE_QUALIFIED`. All five roots supplied complete gap-free
days and 2,834 eleven-epoch windows met the unchanged structural rule. BOGT's
declared per-satellite phase overrides were all static zero-cycle metadata;
GOLD was evaluated only on its C1C/C2W held-out path. This validates structural
capacity only: numerical measurements and the total physical envelope remain
unevaluated, no target was selected and DOY241 cannot become the primary.

A distinct DOY240 reference-only run then reached
`FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_QUALIFIED` on the first frozen five-minute
window. The controlling fit-root phase residual was 0.018670 m/s maximum at
ALGO; GOLD's code-only maximum was 7.561 m. The corresponding two-times
conditional envelopes are 0.037339 m/s and 15.121 m. G14 measurements and
navigation were removed before numeric parsing. This admits the real reference
path, not a future target or total physical envelope; directional and transfer
terms remain unresolved.

An [offline causal transfer audit](research/kinematic/S2_REFERENCE_TARGET_TRANSFER_AUDIT.md)
then tested whether that aggregate receipt can close the future-target envelope.
It cannot: all six directional, continuity, propagation, reference-state and
cross-covariance terms are `NOT_IDENTIFIABLE_FROM_RECEIPT`. The reference-path
bounds remain valid in their original coordinates, but were not combined or
silently transferred to a target. The terminal is
`FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT`; this is an
evidence-sufficiency limit, not a new measurement failure.
The original v1 audit receipt remains historical: a review completed after its
merge found four execution-integrity defects. The repaired, whole-plan-bound v2
receipt reproduced the outcome but was subsequently superseded.
The completed review of that v2 found a remaining hash/parse race and
commit-provenance test defects. V3 closes them, reproduces the same outcome and
is now authoritative; v1 and v2 remain immutable superseded receipts.

## Current evidence

| Experiment | What was measured | Frozen outcome |
|---|---|---|
| DRAO labelled-forward DOY234 | A known orbit predicts held-out RF dynamics better than the frozen alternatives | `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`; closed |
| G08 DOY249 inverse | 188.705 m orbit error; 1.849 m excluded-GOLD residual; 21.608 km prospective uncertainty radius | `UNCERTAINTY_TOO_LARGE`; closed |
| G12 DOY250, seven fit roots | Eight sources individually contain G12, but only 18 consecutive common epochs against a required 41 | `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`; closed before fit/oracle |
| G12 DOY248, eleven-epoch support | 15.139 m orbit error; -3.137 m excluded-GOLD residual; 10.121 km prospective uncertainty radius | `UNCERTAINTY_TOO_LARGE`; new position, primary criterion failed |
| G13 DOY247, configured request | Zero eligible epochs common to the fixed network | `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`; closed before fit/oracle |
| G14 DOY246, candidate network | 31.017 m orbit error; -0.846 m excluded-GOLD residual; 5.755 km prospective uncertainty radius | `INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED`; one conditional event |

The small observed G08 and G12 DOY248 errors did not override their prospective
uncertainty failures. After DOY250's structural failure, a separate plan used
the eleven samples actually needed by the estimator on an unexamined day.
It yielded a new position and passed the excluded-receiver and orbit tests,
but exceeded the unchanged 10 km uncertainty threshold by 121.469 m.
No closed result has been reopened or improved after confirmation.

- [Active mission and operating rules](AGENTS.md)
- [Active positioning implementation](positioning/README.md)
- [Closed G08 experiment](experiments/gnss_inverse_positioning/README.md)
- [G12 plan](experiments/positioning_g12_doy250/plan.json)
- [G12 outcome and physical interpretation](experiments/positioning_g12_doy250/OUTCOME.md)
- [New G12 position and frozen outcome](experiments/positioning_g12_doy248/OUTCOME.md)
- [Eleven-epoch support justification](experiments/positioning_g12_doy248/SUPPORT.md)

## Calculation before comparison

```
frozen experiment plan
  -> Internet RF measurements and non-target clock references
  -> offline xyz + emission time + uncertainty
  -> frozen solution, input hashes and excluded-receiver prediction
  -> excluded receiver, then external orbit comparison
  -> complete result and downloadable evidence
```

Terrestrial coordinates and explicitly non-target satellite ephemerides are
allowed calibration inputs. Target navigation blocks are removed before
numerical parsing. The estimator does not receive target orbit/clock products
or the excluded receiver's target values. The verification stage checks the
freeze and never fits the position.

This is target-state independence, not absence of all reference ephemerides.
Receiver labels do not independently establish satellite identity. The IGS
oracle may share underlying station observations; statistical disjointness is
not claimed. Numerical uncertainty remains conditional on its declared model.

## Run and test

Python 3.13, from this checkout:

```powershell
python -m pip install -r requirements-positioning.txt
python -m positioning acquire experiments/positioning_g12_doy250/plan.json work/g12_reproduction
python -m positioning estimate work/g12_reproduction
python -m positioning verify work/g12_reproduction
python -m pytest positioning/tests experiments/gnss_inverse_positioning/tests -q
```

These commands reproduce the closed G12 qualification failure. They do not
silently switch to another event. A new scientific attempt requires its own
predeclared plan and unexposed confirmation evidence. On a sandbox restricting
the system temporary directory, add `--basetemp work/pytest-positioning-local`
to the test command with a dedicated workspace directory.

The dedicated CI workflow tests the active package and frozen G08 regression on
Windows and Linux. Local test results and remote CI execution are distinct.

## Next physical work

Read-only diagnosis of G12 and G14 finds a weak approximately radial direction.
The S1 synthetic study supports investigating the information added by range
rate, while rejecting concentrated-network ambiguities and inappropriate motion
models. S2a validates receiver-time vacuum geometry, drift nuisance and
correlated fitting; S2b connects RINEX reference files to clock fitting and
unused Doppler. Next qualify receiver conventions and complete propagation
and inverse model-error bounds before any real v2 confirmation.
The [local inverse uncertainty study](research/kinematic/S2_INVERSE_UNCERTAINTY.md)
now propagates shared errors, uncertain station coordinates and excluded clocks,
and tests how constant jerk distorts the fit and future predictions. Its local
Gaussian and affine bounds do not establish total nonlinear coverage.
The subsequent [joint fit](research/kinematic/S2_JOINT_FIT.md) uses one fixed
covariance across RF, reference clocks and terrestrial coordinates for both
optimization and the local residual test. Its paired synthetic study measures
test calibration effects; it does not establish real-data accuracy or coverage.
The [physical-source audit](research/kinematic/S2_PHYSICAL_SOURCES.md) identifies
missing Doppler declarations in the historical network and adds a separate
reference-only phase-increment diagnostic. Mean phase rates require their own
time model, continuity checks and covariance before inverse integration.
The [phase-reference bridge](research/kinematic/S2_PHASE_REFERENCE_BRIDGE.md)
now performs full RINEX code/phase import and checks unused phase increments
against code-fitted reference clocks. Its synthetic slip detection does not
establish universal continuity or real receiver qualification.
The first [real reference-only qualification attempt](research/kinematic/S2_REAL_REFERENCE_QUALIFICATION.md)
stopped before measurement parsing because an undeclared descriptive header
condition was inherited by the runner. It is an invalid execution, not evidence
against the receiver or phase observable; DOY252 will not be retried.
The repaired, distinct DOY253 qualification retained its receipts and verified
full-day ALGO/BOGT structure, but the exact eight-root set closed
`PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED` when DRAO exposed an unmodelled legacy
phase wavelength-factor transform. No phase residual, target fit or S3 claim
was produced.
The later header-only audit qualified five phase-coordinate roots. Their offline
target-free geometry is locally identifiable, but not uniformly below 10 km at
high synthetic shells; those five roots also leave no independent held-out root
and still lack a total physical error envelope. A next physical design must
address all three facts without using a target orbit to choose a favorable case.
Removing the 5% margin or reducing a floor to pass the revealed event is not an
acceptable continuation. An accurate single event does not establish coverage.

Software work must serve that next physical result. Date, GPS week, target,
station roles and time window are explicit inputs. Frozen experiments stay
separate from the active implementation. Product interfaces, monitoring and
infrastructure follow supported scientific claims.

## Historical work

The forward-orbit and measurement-integrity experiments remain available under
`experiments/orbital_discriminability/` and `experiments/live_instrument/`.
Their former roadmap is archived in
[the previous project README](docs/history/README_forward.md). It does not
override the current independent-position mission in `AGENTS.md`.

Licensed under [Apache 2.0](LICENSE).

## Experimental web archive

The user accepted moving ahead with the archive despite the 1.21% excess over
the scientific uncertainty threshold. The first read-only interface is under
[web/](web/README.md): five selectable historical events, inferred coordinates,
observed errors, prospective uncertainty, excluded-receiver checks and JSON
evidence downloads. Missing positions remain unavailable and failed criteria
are never relabelled. The scientific 10 km milestone is distinct from delivering
this experimental archive.

Further website/service/hosting work is paused under the scientific project
approved on 2026-09-10.

Its data are exported deterministically from closed receipts by
`scripts/export_positioning_archive.py`. CI checks their provenance and builds
the site. No position solver or target-orbit request runs in the web interface.
## Synthetic interval inverse model

The [interval study](research/kinematic/results/S2_INTERVAL_REPORT.md) now
compares code-only and code/phase inverse estimates with full covariance.
These local synthetic diagnostics do not establish real satellite accuracy.
