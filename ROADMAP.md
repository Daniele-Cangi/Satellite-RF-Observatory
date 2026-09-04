# Roadmap: satellite-first predictive observation

## North Star

The project has one scientific question:

> Does a candidate orbit predict observer-coupled RF structure in a future,
> held-out interval better than frozen non-orbital explanations?

Work is admitted only if it closes one edge of this chain:

```text
orbit and observer geometry
  -> fractional prediction
  -> pass-specific detectability envelope
  -> capability admission
  -> immutable prospective plan
  -> one distributed observation
  -> held-out orbital-versus-null inference
```

Receiver discovery, protocol work and feature extraction are subordinate to
this chain. They must not generate a new scientific target after the fact.

## Gate discipline

- No live RF activity before a pass-specific prediction clears a conservative
  synthetic detectability envelope.
- Calibration and confirmation windows are disjoint; confirmation never
  changes the model, feature, threshold, station set or null family.
- A valid negative requires continuous event-time coverage and same-path
  witnesses showing that the predicted feature would have been detectable.
- `NOT_DETECTABLE`, `PREDICTION_REJECTED` and `MODEL_NOT_DISCRIMINATIVE` remain
  different outcomes.
- Each gate ends at its declared stop condition. It cannot silently become a
  receiver platform, catalog, general planner or signal-identification system.

## Gate G0 — orbital discriminability: COMPLETE OFFLINE

G0 implements deterministic multi-observer trajectories, fractional and
differential Doppler, joint-visibility-gated nuisance/scoring, direct
time-shift trajectory envelopes, four non-redundant frozen nulls and a
held-out synthetic sweep. The report demonstrates both a non-empty
discriminative region and a non-empty below-detectability region, plus
rejection of a controlled plausible adjacent-orbit mismatch.

G0 authorizes only the mechanism claim: under the declared synthetic geometry
and uncertainty, orbital prediction can beat the nulls. It authorizes no live
RF or identity claim. See
`experiments/orbital_discriminability/G0_IDENTIFIABILITY_REPORT.md`.

## Gate G1 — pass-specific capability admission: COMPLETE OFFLINE

Choose candidate passes from orbital geometry, not from receiver convenience.
For each candidate, compute the predicted differential curvature and admit a
receiver set only if its coordinates, event-time semantics, continuity,
frequency resolution, independent measurement roots and transform ledger
leave a positive conservative margin.

The offline mechanism now evaluates atomic descriptive offers in two stages:
individual observability qualification and independent-pair detectability.
The deterministic vertical admits a high-margin synthetic pair and refuses a
fully available coarse local pair. It performs no discovery, status request or
RF acquisition. Valid terminal outcomes are `NO_CAPABILITY_ADMITTED` and
`CAPABILITY_SET_ADMITTED`.

## G1.1–G1.3 — capability-discovery side investigation: CONCLUDED

The status, inventory and search branches are preserved as historical work.
They are not on the active dependency chain, and repairing search-result
partitioning is not a prerequisite for a physical observation. No successor
inventory/search gate is planned.

GitHub issues #21 and #22 are correspondingly closed as superseded by the
terminal work merged in PR #50; they are not latent roadmap dependencies.
Issue #14 remains maintenance-only and is also outside the scientific critical
path.

## Forward physical attempts — CONCLUDED WITHOUT ORBITAL SCORE

The bounded Berlin–Utrecht OpenWebRX path, RSP-03, MAVEN RSR and the tested
Cassini paths produced useful physical exclusions but no independent held-out
orbital comparison. Their receipts are historical results, not prerequisites
for another receiver search chain.

The subsequent GOLD00USA–NLIB00USA G11/G21 GNSS vertical had a positive
`1420.626 Hz` premeasurement margin after the frozen pairwise physical
envelope. Its single authorized run stopped `MEASUREMENT_INVALID` at
`TRUNCATED_REQUIRED_OBSERVATION_RECORD`; calibration and held-out hypotheses
remained `NOT_EVALUATED`. The receipt cannot attribute the short record to
field absence or an unsupported representation. A bounded value-blind forensic
repair has now located the exact boundary at NLIB G21, `10:06:00 GPS`: `C2W`
was declared at index 5 after only three serialized fields. RINEX variable-line
semantics classify it as `TRAILING_FIELD_OMITTED`, not evidence of file
truncation. The original terminal remains unchanged and the primary remains
closed with zero retry.

## Geometry-guard result — GOLD/NLIB G11/G21 route closed

The DOY 214 independent qualification did not repeat the historical parser
failure. Its complete structural scan found NLIB-G21 absent for the first 27
frozen epochs and nonzero LLI at reacquisition. The maximal joint segment was
358 epochs, so the exact 386-epoch qualification failed without interpolation,
gap bridging or alternate segment selection.

A broadcast-navigation-only audit then screened the predeclared DOY 216--220
set. The physical question was whether another date could supply all 386
epochs after both receiver roots had already seen G11 and G21 above the
15-degree guard for 30 minutes. DOY 217 and 218 contained only 385 guarded
epochs. DOY 216, 219 and 220 contained 386, but their preceding 30-minute
minimum elevations were only 3.405, 3.380 and 3.435 degrees. At 20 degrees the
longest windows were 327--328 epochs.

The modeled prefix-affine separation remained about 2.145 kHz, so geometry was
still discriminative; the missing quantity was acquisition-margined
observability for the frozen duration. No observation product or primary was
selected. The route is closed rather than shortened after its measurement-path
failure. Exact inputs and results are in
`GNSS_GEOMETRY_GUARD_AUDIT_RECEIPT.json`.

Any later GNSS experiment must first justify a different satellite/station
geometry or duration from an orbit-first discriminability comparison. It may
not arise as another retry of this qualification chain.

## Orbit-pair result — one new geometry retained

A bounded broadcast-only comparison has now evaluated every healthy GPS pair
over the unchanged GOLD/NLIB stations, 386-epoch duration and DOY 216--220
date set. Every candidate required 60 preceding epochs plus the full raw
window with all four links at or above 15 degrees. The held-out suffix retained
the same prefix-only affine null and jointly visible wrong-target orbit family.

Twenty pair/date candidates were rankable. The top three were independent-date
instances of G14/G17, all controlled by G22 rather than the affine null. Exactly
one geometry is retained: DOY 220, raw GPS window 05:07:00--08:19:30, guarded
minimum 23.620 degrees and controlling separation 403.375 Hz peak-to-peak.

This is not yet an experiment freeze. No observation product, header or value
was accessed. The next causal question is whether the candidate-specific
pairwise physical envelope leaves a positive margin. If it does not, the
geometry closes before any new qualification artifact is sought. Exact results
are in `GNSS_ORBIT_PAIR_SCREEN_RECEIPT.json` and its report.

That envelope has now been compiled without observation discovery. G22 remains
the controlling null at 403.375 Hz. The one-model conservative bound is
366.877 Hz and the pairwise bound is 733.754 Hz, leaving a -330.379 Hz margin.
The outcome is `GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_DOMINATES`; G14/G17 DOY 220
is closed before plan freeze, and lower-ranked dates are not automatic retries.

The physical lesson is that no single nuisance removal admits the candidate.
Even zeroing the complete broadcast-orbit contribution leaves the aggregate
6.111 Hz above G22. A future step must either justify structured,
outcome-independent orbit/clock uncertainty across multiple causal terms or
select a genuinely stronger geometry. It must not reduce intervals because
this candidate failed.

A bounded documentation and navigation-grid audit has now tested the orbit/
clock branch explicitly. GPS URRE provides useful 95% and 6-sigma design
sensitivities, but no rate-error integrity NTE or published temporal covariance.
Substituting those values still leaves -13.407 Hz and -30.431 Hz margins. The
06:00 and 08:00 ephemeris cutovers affect four feature epochs by only
millihertz; removing them diagnostically leaves the 403.375 Hz separation
unchanged.

The result is `GNSS_ORBIT_CLOCK_STRUCTURE_INSUFFICIENT`. Do not create another
orbit-bound repair: even perfect orbit/clock knowledge cannot admit the closed
candidate under the remaining envelope. The next comparison must change the
causal topology—observer geometry, quotient coordinate or same-path witness—
and rank by remaining physical margin from the start.

That SHOCK comparison is now complete without observation access. Five routes
were compared by the interpretability of a negative result. A third station
alone adds local nuisance families, while a new screen using the same
frequency-rate coordinate changes no causal cut. SatNOGS raster validation is
valuable for a limited positive model-conditioned result, and Delta-DOR is a
stronger but substantially more archive-dependent later route.

The recommended minimum work is an offline continuous-phase quotient spike.
It must keep a multi-frequency geometry-preserving combination, prefix-only
ambiguity/rate nuisance, frozen affine and wrong-orbit nulls, and separate
LLI/geometry-free/code witness clauses. G14/G17 is development-only for this
mechanism and cannot become a primary. If the coordinate survives synthetic
mismatch and a complete physical envelope, a newly predeclared bounded set
may then be ranked by remaining physical margin before any observation product
is discovered. Details are in `POST_G14_G17_SHOCK_REVIEW.md`; no new gate has
been created.

The offline spike has now returned
`PHASE_QUOTIENT_MECHANISM_DISCRIMINATIVE`. On the historical G14/G17 fixture,
the continuous phase coordinate retains 742,458.297 m against G22 after the
same prefix-only nuisance, while the conservative pairwise envelope is
23,037.025 m. The 719,421.272 m remainder is mechanism evidence only: G14/G17
stays closed, no product was discovered and no plan or measurement authority
exists.

The next work may declare one new bounded orbit/station/signal/date set and
rank it directly in the phase coordinate by complete remaining physical
margin. It must exclude G14/G17, keep code/LLI/geometry-free witnesses separate
from the score, and stop before product discovery if no geometry is positive.
No receiver catalog, new gate or change to G0/G1 is required.

That bounded screen has now selected G22/G30 on DOY 220, raw window
04:30:30--07:43:00 GPS. G14 remains the controlling physical wrong-orbit null
at 824,736.025 m despite being excluded from candidate roles. The conservative
pairwise envelope is 19,767.924 m, leaving 804,968.101 m. All five admitted
dates of the single surviving distinct pair were positive; no alternate pair
was manufactured merely to fill a three-row shortlist.

The result is `GNSS_PHASE_GEOMETRY_SELECTED`, not measurement admission. The
next blocker is structural-only qualification of L1C/L2W, LLI,
geometry-free-phase continuity and predeclared C1C/C2W witness cadence on one
independent artifact. The recommended unexecuted roles are DOY 216 for
qualification and DOY 220 for the later primary. No observation product has
yet been discovered or opened.

The value-blind boundary for those roles is now frozen in
`GNSS_PHASE_STRUCTURAL_CONTRACT.md`. DOY 216 uses the exact 04:47:00--07:59:30
GPS raw window; DOY 220 remains sealed at 04:30:30--07:43:00 GPS. Structural
presence, LLI and epoch-grid continuity are separable from geometry-free phase
health, which requires phase scalars and remains `NOT_EVALUATED`. The next
review may authorize at most bounded materialization, hashing, header
admission and a full value-blind scan of the two DOY 216 locators. It may not
touch DOY 220 or produce an orbital score.

That single structural run is now closed as
`GNSS_PHASE_STRUCTURE_REJECTED`. Both exact DOY 216 artifacts and headers were
available, but actual NLIB G22/G30 carrier-phase continuity did not cover the
frozen 386-epoch window; the longest joint segment was 282 epochs and the
same-path code clause also failed. Geometry-free health, measurement admission
and orbital scoring remain `NOT_EVALUATED`; DOY 220 remains sealed. Do not
shift the window or substitute a qualification artifact after this result.

That change-of-abstraction review is now complete without reusing DOY 216 gap
locations. The result is `PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE`. On the
predeclared duration grid, all four unopened DOY 217--220 geometries retain a
positive complete margin at the shortest 60-epoch held-out suffix. The
observation-sized raw interval is 139 epochs (69 minutes elapsed); its worst
margin is 6,473.198 m and its best four-link guard is 39.467 degrees, versus
15.616 degrees at the old 307-epoch suffix. This is model-only physical
availability, not a repaired qualification or a frozen primary.

The roles and proof boundary are now frozen. DOY 217,
05:54:00--07:03:00 GPS is the only qualification date; DOY 220,
05:42:00--06:51:00 GPS remains the sealed primary. The exact 139-epoch
coordinate, 77/60 prefix/holdout partition, geometry-free health limit,
same-path witnesses, prefix-affine null, G01/G14/G17 alternatives and
2,384.234 m decision guard are fixed before product discovery. No reserve is
assigned and qualification failure authorizes no substitution.

The maximum next action is bounded discovery and model-blind qualification of
the two DOY 217 station products only. It must stop with the qualification
outcome; DOY 220 remains forbidden until a separate review. If complete
L1C/L2W/LLI structure, geometry-free health or required C1C/C2W witnesses do
not pass, close this role pair rather than move the window.

That single qualification is now complete with
`GNSS_SHORT_WINDOW_QUALIFICATION_PASSED`. Both product hashes were captured
before decoding. The fixed 139-epoch interval is complete on all four phase
links, every relevant structural field is present, all C1C/C2W witnesses have
100% coverage, and the maximum geometry-free second difference is
0.019274 m against the 0.095147 m limit. The qualification used no orbit or
null model and persisted no observation values; DOY 220 remains sealed.

That offline primary decoder/scorer seal is now complete. Source commit
548b7a2 and seal SHA-256 58802ab8...df62b bind the exact DOY 220
broadcast-model curves, runtime dependencies, proof plan and passed
qualification receipts. The exact numerical regressions reproduce the
11,401.473 m prefix-affine and controlling 8,857.432 m G01 separations.
No primary locator was discovered or opened while sealing.

That single DOY 220 execution is complete with
ORBITAL_MODEL_PREDICTIVELY_PREFERRED. Both station products passed exact
hash-before-decode, full-window phase/LLI admission, same-path code witnesses
and geometry-free health. The orbital calibration residual was 0.367 m
peak-to-peak. Its held-out residual was 2.313 m, while runner-up G01 retained
8,858.964 m; the observed 8,856.652 m preference margin exceeds the frozen
2,384.234 m guard.

The result establishes a real prospective held-out orbital-model preference
for this exact station/date/signal/hypothesis set. It does not establish
catalog-wide satellite identity, repeated-pass consistency or a general
receiver claim. The primary is consumed: no retry, reserve or rescore is
authorized. The next work must ask a new physical question rather than extend
this measurement chain administratively.

That next physical question is now frozen, without observation access: does
the preference repeat on a distinct pass? The pre-outcome guard-first ranking
selects unopened DOY 219 after excluding consumed DOY 220 and qualification
DOY 217; DOY 218 remains a sealed non-retry reserve. Exact-hash broadcast NAV
reproduces a controlling 8,986.714 m G01 separation against a 2,377.703 m
pairwise guard, leaving 6,609.011 m of model-only physical margin. Source
commit bed2258 and seal SHA-256 8d4466be...987d bind the unchanged coordinate,
nulls, thresholds and prefix/held-out split. Neither DOY 219 nor DOY 218 has
been discovered or opened. See GNSS_PHASE_REPEATED_PASS_SEAL_REPORT.md.

The experiment-specific DOY 219 executor is now frozen offline as well. It
leaves the consumed DOY 220 source untouched and reuses only its exact-hash
model-blind materialization, decode, coordinate and prefix-fit operations.
Source commit d080bbb and executor seal SHA-256
490f6015...8ed6 bind the DOY 219 grid, thresholds, two locators, prediction and
zero-retry outcome semantics. The seal grants no live authority; both DOY 219
and DOY 218 remain unopened. See
GNSS_PHASE_REPEATED_PASS_EXECUTOR_REPORT.md.

The single authorized DOY 219 execution has now closed positively as
ORBITAL_MODEL_REPEATED_PASS_PREFERRED. All measurement clauses passed. The
orbital held-out residual was 2.269 m peak-to-peak versus 8,988.225 m for the
closest null, leaving an 8,985.956 m preference against the frozen
2,377.703 m guard. This supports repeated-pass consistency for the exact two
GOLD/NLIB G22/G30 passes, not general identity or independence from shared
station-pair systematics. No observation values were persisted, no retry or
fallback occurred and DOY 218 remains sealed. The replication is consumed;
see GNSS_PHASE_REPEATED_PASS_OUTCOME_REPORT.md.

## Independent pair challenge — geometry shortlisted, measurement unopened

Repeated-pass consistency leaves the GOLD/NLIB hardware, geography and
pair-specific systematics shared. Because the phase observable is a four-link
two-station coordinate, adding only one station cannot isolate that causal
cut. The minimum next geometry needs two new sites.

A bounded observation-blind screen fixed six official IGS candidates before
ranking and evaluated all 15 pairs on the unchanged DOY 219 G22/G30 grid,
prefix-affine null, G01/G14/G17 alternatives and complete pairwise physical
envelope. All 15 pairs retain positive margins. The deterministic shortlist
is DRAO00CAN/WES200USA, DRAO00CAN/ALGO00CAN and ALGO00CAN/MDO100USA.

DRAO/WES ranks first with a 96,588.530 m controlling G01 separation and a
3,939.458 m pairwise envelope, leaving 92,649.071 m. Every modeled satellite
remains jointly visible at both sites; the minimum is 19.405 degrees. No
observation product was discovered or opened.

This does not yet prove independent hardware roots. The next maximum work is
a separate value-blind capability qualification establishing the exact
historical receiver/clock lineage, full event-time coverage and the frozen
L1C/L2W/LLI plus C1C/C2W witness family on one distinct artifact. Only after
that review may a DRAO/WES DOY 219 prospective primary be selected and frozen.
See GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_REPORT.md.

Metadata-only admission then rejected DRAO/WES before payload access. WES's
official primary feed is RINEX v2 and cannot prove the explicit L1C/L2W signal
identity required by the frozen coordinate. A post-hoc RINEX2 mapping is not
an admissible repair.

The next bounded role is ALGO00CAN/MDO100USA, already third in the frozen
shortlist. Its 47,828.042 m complete margin remains strongly positive, while
site logs establish distinct DOMES, receiver and antenna serials,
organisations and primary data centers. One DOY217 qualification window is now
frozen model-blind. No observation body has been accessed and no DOY219
product locator exists in the plan. See
GNSS_INDEPENDENT_PAIR_QUALIFICATION_PLAN.md.

The separately authorised execution returned
`GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED`. Both exact artifacts were hashed
before decode and then erased from RAM. Every one of the 3,336 structural rows
is present; all four phase links span the complete 139-epoch window, C1C/C2W
coverage is 100 percent, and the largest geometry-free second difference is
0.022172391 m against the frozen 0.095146836 m limit. This is capability
admission only: no orbit, null or DOY219 product was available to the executor.

## Anti-drift stop

Stop the roadmap if no candidate pass produces a positive detectability margin
with qualified capabilities. Do not return to targetless feature hunting to
manufacture an experiment. The correct result is that the current Internet
measurement substrate cannot test the orbital question.

## Preserved Gates B–F2.5 history

The remainder of this document preserves the measurement-integrity roadmap
that made G0 possible. It is historical context, not the current project
driver.

This earlier roadmap was intentionally narrow. It replaced a former feature
roadmap which assumed a satellite-identification product before measurement
and detectability mechanisms were established.

## Current baseline

- The Gate B through F2.5 history is preserved as immutable plans, receipts,
  outcomes and postmortems.
- The offline live-instrument suite contains deterministic tests with no live
  network activity.
- SatNOGS demonstrated clause-driven continuity/failover semantics.
- Dual-Kiwi work demonstrated the need for in-session nulls and explicit time
  and frequency alignment.
- Gate F2.3 identified a same-Kiwi, two-channel DDC intervention as the cleanest
  causal cut for the current question.
- Gate F2.5 removed W/F and `ext_api` as multichannel truth sources, but its
  first live run stopped before SND because `/status` did not materialize the
  assumed `bandwidth` field.
- Gate F2.5.1 removed that status dependency and its single live run reached
  both SND attempts on every candidate. No pair was admitted: one candidate
  explicitly rejected public SND and the rest remained indeterminate after
  transport/protocol errors.

## Completed gate: F2.5.1, offline only

Goal: remove every precondition that is not necessary to attempt two direct
SND/IQ allocations.

Completed work:

1. Audit the frozen Kiwi client/server protocol evidence for the legal initial
   tuning interval and where bandwidth is actually learned.
2. Replaced `status.bandwidth` with a conservative 0–30 MHz Kiwi-family
   protocol invariant frozen before execution.
3. Ensure status fields and `ext_api` remain descriptive only.
4. Prove offline that missing/malformed status bandwidth cannot block
   `_open_dual()`.
5. Preserve the distinction between:
   - direct second-channel refusal;
   - transport/software failure;
   - two opened but causally inadmissible streams.
6. Prepare a new runtime checkpoint without reinterpreting or amending F2.5
   outcome 1.

Exit criteria:

- tests show the first physical call after optional status/access checks is the
  concurrent SND pair attempt;
- W/F is absent from the call graph;
- no feature, threshold or retune question is evaluated before dual-IQ
  topology admission;
- all RF arrays remain in RAM and outside strict JSON receipts.

The implementation and evidence are in
`experiments/live_instrument/kiwi_gate_f2_5_1.py` and
`experiments/live_instrument/GATE_F2_5_1_OFFLINE.md`. No connection or
acquisition occurred while completing this gate.

## Completed: one separately authorized live execution

After offline review, authorize at most one new session.

Allowed sequence:

```text
frozen candidate order
  -> direct dual-SND attempt
  -> topology receipt
  -> local targetless feature/witness discovery
  -> witness-only retune qualification
  -> immutable plan
  -> one A1/B/A2 confirmation
  -> one outcome and stop
```

Correct terminal outcomes include:

- `QUALIFICATION_INCOMPLETE`;
- `NO_MULTI_CHANNEL_CAPABILITY` only after real second-channel attempts;
- `NO_ADMISSIBLE_CAUSAL_TOPOLOGY`;
- `NO_FALSIFIABLE_INTERVENTION`;
- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`;
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`;
- `AMBIGUOUS`;
- `INTERVENTION_INVALID`;
- `NOT_DETECTABLE`.

The execution terminated as `QUALIFICATION_INCOMPLETE`. It produced no
experiment, and the terminal state is supported by the receipts. No second
session is authorized.

## Completed gate: branch-level receipt audit, offline only

The live outcome exposed that `_open_dual()` collapsed the two concurrent
opening histories when either branch failed. Gate F2.5.2 now:

1. preserves a separate receipt for reference and perturbed opening;
2. distinguishes handshake, channel allocation, GNSS IQ readiness and close;
3. hashes every ephemeral SND frame before decode and separately hashes the
   first valid IQ block before it is used as a readiness witness
   or destroyed;
4. composes the pair decision from the two atomic branch receipts;
5. preserves the frozen candidate set, center policy, retry policy and physical
   question.

The gate remained offline and did not reinterpret F2.5.1 outcome 1.

## Next checkpoint: review before any execution

Review the atomic receipt schema, the readiness hashing boundary and the
composition table in `GATE_F2_5_2_OFFLINE.md`. No new live execution is
authorized by this roadmap. Any future session must be explicitly approved
after the new runtime commit is frozen; it must retain the existing candidates,
centers, retry policy, thresholds and one-outcome stop condition.

The separately authorised F2.5.2 execution has now occurred and is frozen as
`GATE_F2_5_2_OUTCOME_1.md`. It terminated `QUALIFICATION_INCOMPLETE`; no second
session is authorised.

## Next gate: structured control and receipt retention, offline only

The next minimum correction must:

1. derive retry eligibility from atomic `BranchOpenState` and typed branch
   errors, never from aggregate statement text;
2. prove that the unchanged budget of two retries, maximum one per endpoint,
   is materialised exactly for allowed transport/software failures;
3. persist one bounded strict-JSONL session artifact containing only receipts
   and hashes;
4. exclude raw SND frames, IQ arrays, waterfall and STFT from that sink;
5. classify sink/serialization failure descriptively without changing the
   physical branch or pair decision;
6. leave candidates, centers, thresholds, physical question and stop condition
   unchanged.

This gate must remain offline and must not reconstruct the missing Hill receipt
or reinterpret F2.5.2 outcome 1.

Gate F2.5.3 now implements and tests this correction offline. Retry eligibility
comes from atomic state plus a frozen typed-error allowlist; its tests
materialise exactly two total retries and at most one per endpoint. A private
bounded writer retains strict JSONL receipts and hashes while rejecting RF
fields and arrays. Serialization, file and mirror failures remain descriptive
and cannot change the physical decision. See `GATE_F2_5_3_OFFLINE.md`.

No live F2.5.3 execution is authorised by this checkpoint.

The pre-execution review then found that F2.5.3 returned the final artifact
hash and error ledger only in memory, while its CLI discarded that object.
Gate F2.5.3.1 corrects only this closure gap: a reserved terminal JSONL record
commits to every preceding byte and persists retention/error state; the CLI
then exposes the overall closed-file hash. Finalization also occurs on an
unexpected runtime exception. See `GATE_F2_5_3_1_OFFLINE.md`.

No live F2.5.3.1 execution is authorised by this roadmap entry.

The separately authorised first F2.5.3.1 execution is now complete and frozen
as `GATE_F2_5_3_1_OUTCOME_1.md`. It materialised exactly two structured
pre-freeze retries, retained a complete terminal-manifest JSONL artifact, and
ended `QUALIFICATION_INCOMPLETE`: no branch delivered IQ readiness, so no
topology, feature, plan or DDC hypothesis entered evaluation. No second session
is authorised.

Gate F2.5.4 then audits only that frozen code and artifact. It classifies four
atomic receipts as explicit server-reported rejection, one as a transport
timeout before any retained MSG, and eleven post-configuration closures as
`NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT`. The local command shape is consistent
with the prior single-channel path, but official source conformance is not
reproducible from this repository. The resulting exit is
`STOP_PENDING_CONTROL_DISCRIMINATORS`: no new endpoint, rerun or client fix is
authorised by this audit.

Gate F2.5.5 materialises those discriminators as an offline contract while
keeping official-source provenance as an independent clause. Command results,
allowlisted server fields, WebSocket close, TCP loss and IQ witness are ordered
without retaining credentials or RF. The source artifacts and the exact
kiwiclient control path are not present locally, so the gate terminates
`SOURCE_BASIS_INCOMPLETE`. Implementation and live execution remain
unauthorised until a separately reviewed source-reproduction step succeeds.

Gate F2.5.6 completed that separately authorised source retrieval without any
Kiwi or RF access. The exact server subset is retained with license notices and
verified hashes. The kiwiclient control path is resolved and hash-audited, but
its source is excluded because no license grant was found at the frozen commit.
The gate therefore stops at `SOURCE_RETENTION_BLOCKED_BY_LICENSE`: the ordered
receipt is still not authorised for integration and no live run is authorised.

Gate F2.5.7 then asks whether the missing client retention is epistemically
necessary. Synthetic ordered transcripts show that it is not: the server
archive defines auth, allocation and per-channel tuning semantics; local send
results describe client actions; only later IQ can witness a usable branch.
The result is `SERVER_WIRE_CONTRACT_SUFFICIENT`. A following offline gate may
integrate the ordered receipt into the local path, but no connection or RF
acquisition is authorised until that implementation receives a separate
review.

Gate F2.5.8 has now implemented that successor path offline. It hashes every
incoming control/IQ frame before analysis, preserves ordered allowlisted
fields, extracts channel identity from `is_local`, and sends `mod_iq` only
after auth, channel and rate witnesses exist. Synthetic tests also separate
local send error, control timeout, close frame and transport loss. The exit is
`ORDERED_WIRE_RECEIPT_IMPLEMENTED`; a separate pre-live review is still
required and no session is authorised by this roadmap entry.

Gate F2.5.9 completes that review by replacing the single stale dependency in
the future one-shot path. The new wrapper reaches only the ordered opener,
derives retry from ordered branch state and typed errors, retains terminal
receipt closure, and stops at the first outcome. It also refuses before file
or network I/O unless a later caller supplies separate live authority. The
offline exit is `ORDERED_ONE_SHOT_RUNNER_MATERIALIZED`; no live session is
authorised or executed by this roadmap entry.

Gate F2.5.10 then closes the remaining authority ambiguity: the reviewed live
entry point accepts no plan, receipt-path, commit or retry overrides. Before
entering the F2.5.9 qualifier/retry path it checks causal sources, numerical
environment, repository root and the exact candidate/timing envelope, then
writes that envelope as the first receipt. Its offline exit is
`REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY`. A later live run still needs
separate human authority and any mismatch must terminate before network entry.

That single authority has now been consumed. The exact run attempted both SND
branches once on all six candidates, used no retry, admitted no IQ-readiness
root and stopped `QUALIFICATION_INCOMPLETE` before discovery or plan freeze.
Four atomic branches contain explicit `badp` rejection; eight contain ordered
allocation and local `mod_iq` followed by a close before the qualifying IQ
witness. The receipt is terminally complete with zero RF persistence. No rerun
is authorised by this roadmap entry.

Gate F2.5.11 attributes that frozen failure boundary without network activity.
All eight close artifact hashes equal the recorder's exact empty-payload
encoding, so their displayed `1005` values were local no-status sentinels, not
peer-supplied status codes. The receipt nevertheless omits the per-hash frame
tag and the clause result for discarded SND frames; it cannot distinguish no
SND from SND excluded by the GNSS/readiness predicate. The offline exit is
`FROZEN_FAILURE_BOUNDARY_ATTRIBUTED_CAUSE_UNRESOLVED`. A future receipt would
need hash-bound categorical clause transitions, not retained RF. No runner is
changed and no new session is authorised.

Gate F2.5.12 implements that narrow future receipt offline. Each transient
frame hash is now bound to MSG/SND/CLOSE class and separate header, IQ mode,
sample decode, GPS-seconds, GPS-age and readiness states. Empty close payloads
carry `EMPTY_NO_STATUS` and no invented `1005`; descriptive transform errors
leave readiness `NOT_EVALUATED` and cannot become physical rejection. Samples
remain ephemeral, strict JSON contains no RF surface, and the 30-second GPS
limit has no caller override. The exit is
`HASH_BOUND_SEMANTIC_RECEIPT_IMPLEMENTED`. Integration into an ordered opener,
pre-live review and any network authority remain separate future gates.

Gate F2.5.13 performs the first of those steps with synthetic sockets only. The
F2.5.10 causal-source guards correctly rejected an attempted additive hook in
the frozen opener, so F2.5.8 remains byte-identical and a successor binds each
ordered wire hash to its F2.5.12 semantic transition. Its wrapper requires an
injected connector and framing module and exposes no live entry point. The
sanitized receipt omits the legacy locally synthesized close code, requires
exact cross-layer hash order and keeps explicit control rejection separate
from typed qualification errors. The exit is
`SEMANTIC_ORDERED_OPENER_INTEGRATED_OFFLINE`; dual composition, terminal
receipt, exact execution envelope and network authority are still absent.

Gate F2.5.14 performs the next composition step, still with synthetic sockets
only. It starts reference and perturbed semantic SND openers concurrently on
one candidate, admits the pair only with distinct connections and server
channel IDs plus overlapping IQ event time, and preserves clause-level reasons
for every failed branch. The frozen candidate loop makes exactly one two-branch
attempt per endpoint, stops at the first ready pair or exhaustion, and closes a
terminal strict-JSON receipt without RF persistence. Its immutable envelope
keeps status, `ext_api` and waterfall outside the pre-SND causal path and sets
both retry budgets to zero. The exit is
`DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE`. A post-commit review must still
bind this new causal source and envelope before a specific live authority can
exist; no prior generic authorization is consumed.

Gate F2.5.15 performs that post-commit review without network activity. It
seals the F2.5.14 commit, a complete 17-file causal allowlist with canonical-LF
SHA-256, the exact numerical environment and the F2.5.14 control-surface hash.
The sole public execution surface is
`run_reviewed_once(live_authorised=False)`: it exposes no endpoint, frequency,
threshold, retry, receipt-path or connector override, and guard order places
explicit authority and the seal before receipt creation and connector access.
The exit is `EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY`; no live
authority is implied or consumed. A later authorization must name the commit
that freezes F2.5.15 and permits only the one dual-SND qualification outcome,
not discovery, retune or A1/B/A2.

That exact authority has now been consumed once. All six candidates received
one concurrent reference/perturbed attempt and no retry occurred. Four atomic
branches contain explicit `badp` rejection. The other eight observed channel
allocation and local `mod=iq`, then an empty close with no peer status. The
semantic layer records exactly zero SND frames across all twelve branches, so
the old ambiguity between no SND and a discarded stale/malformed SND is closed;
the unobserved cause of the empty closes is not inferred. No candidate produced
two IQ readiness roots, therefore the terminal outcome is
`QUALIFICATION_INCOMPLETE`, not `NO_MULTI_CHANNEL_CAPABILITY`. The terminal
receipt is complete with zero RF persistence. This authority cannot be reused.

Gate F2.5.16 audits the frozen control sequence and pinned server source without
network activity. Every allocated branch locally emitted 15 or 16 keepalives
before `AR OK`. The pinned server model increments that counter and has an
incomplete-setup removal path after more than four, so the plan's neutral
keepalive assumption is locally falsified. Because the live server revision,
remote command receipt, `cmd_recv` state and close reason were not witnessed,
the remote causal attribution remains `INCONCLUSIVE` and physical dual-SND
capability remains `NOT_EVALUATED`. No rerun is authorized.

Gate F2.5.17 retrieves only the missing licensed header from the same pinned
server commit and materialises a corrected branch opener offline. The exact
setup mask is now known: frequency, mode, passband, AGC and `AR OK`. All
required metadata must be observed before the setup is emitted once; keepalive
is absent from setup and becomes time-paced only after local completion. The
receipt never promotes local sends to a remote acknowledgement. Synthetic
tests prove the frozen failed sequence exposes the retained guard while the
corrected sequence does not. Dual composition and post-commit sealing remain
required before a separately authorised qualification; no live authority is
present.

Gate F2.5.18 performs the dual composition offline. Exactly two corrected SND
branches start concurrently per candidate and must still demonstrate distinct
connections, server channels and sequences plus overlapping GNSS event time.
The frozen candidate order, data-independent centers, zero retry and terminal
receipt are preserved. Status and waterfall remain outside admission. The
result is an injected, synthetic-only qualification envelope; a post-commit
seal is still mandatory and no live authority is present.

Gate F2.5.19 supplies that post-commit seal. It binds the F2.5.18 commit, 21
causal source hashes, numerical environment and control-envelope hash to a
boolean-only public surface. Default refusal precedes receipt creation and
connector access; no endpoint, frequency, retry, connector or path override is
exposed. A future explicit authority may consume exactly one corrected
dual-SND qualification and must stop before feature discovery or observation.
The seal itself remains offline and does not grant or consume that authority.

The separately authorised Gate F2.5.19 outcome has now consumed that surface
once. The first candidate produced two corrected semantic SND/IQ readiness
roots on distinct channels with 24.835 ms of event-time overlap, so the
terminal outcome is `DUAL_SEMANTIC_PAIR_READY`. The stop condition prevented
all later candidates and no retry occurred. This removes multichannel
availability as the immediate blocker, but retune independence, local feature
discovery and the physical A1/B/A2 intervention remain completely unevaluated.
A future gate must freeze those as a new prospective experiment; it may not
extend or rerun the consumed qualification.

Gate F2.5.20 performs that next composition offline. It binds the frozen
F2.5.19 outcome artifact and its sole winning endpoint, but requires fresh
same-session corrected dual-SND admission before using any new sample. The
prospective order is fixed: new local-IQ discovery, witness-only retune
qualification, plan freeze and one independent A1/B/A2. Existing thresholds
and geometric negative controls are retained unchanged, both retry budgets are
zero, and no connector default or live authority exists. The next admissible
step is a post-commit causal/environment seal, not an observation.

Gate F2.5.21 now supplies that seal. Besides the reviewed causal files and
numerical environment, it hashes the authority-facing function sources so the
wrapper itself cannot drift outside the review. Default refusal precedes all
receipt and connector access.

The separate authority was consumed once. Current-session requalification
proved the dual-SND topology again, while the independent local-IQ discovery
found fewer than two distinct stable structures. It therefore terminated
`NO_FALSIFIABLE_INTERVENTION` before retune qualification, plan freeze or
A1/B/A2. This closes the authority without a physical-signal outcome: it
supports multichannel availability only and does not permit an upstream,
downstream or external-RF claim. Any next step must begin offline from this
observed detectability limit and cannot retry or reinterpret the consumed
window.

Gate F2.5.22 performs the required offline discoverability attribution. The
frozen error is localised but not causally attributable because its discovery
receipt retained only an error-description hash and no input hashes, stage
counts or margins. A future successor must preserve those scalar sufficient
statistics before destroying IQ. The audit also separates the causal need for
an orthogonal witness from its old representation as a second narrowband peak.
A target-excluded distributed spectral fingerprint can, in deterministic
fixtures, witness a unique perturbed translation while the reference remains
fixed and A2 returns. This alternative is not live-qualified, changes no frozen
threshold and grants no authority. The next admissible step is offline
integration plus a new seal; it is not another observation.

Gate F2.5.23 now materialises the pre-freeze successor offline. The real
phase-aware control boundary is exercised with injected sockets, then a
one-target descriptive discovery and a target-excluded distributed witness
produce an immutable plan in deterministic fixtures. Altering the target in
every tested lag leaves witness state and scores invariant. Missing target and
channel-fixed witness fixtures stop with downstream phases `NOT_EVALUATED`.
The plan freezes one independent future confirmation and the existing physical
outcome set.

Gate F2.5.24 now supplies the post-freeze evaluator offline. Admission is
strictly ordered: event-time/artifact identity, command and tuning ledger,
stream integrity, then the target-excluded distributed witness. Target
predictions are inaccessible until those clauses pass. Adversarial fixtures
reach every frozen outcome, including the distinct cuts
`INTERVENTION_INVALID`, `NOT_DETECTABLE` and `AMBIGUOUS`, without changing the
plan. No connector, acquisition or live authority was added.

Gate F2.5.25 now seals that evaluator and the exact same-session execution
surface. The audit found that the F2.5.23 offline materializer closes its
channels before a future caller could confirm; the sealed composition therefore
uses the reviewed primitives directly, keeps the two channels only through one
confirmation, clears qualification command history at the freeze boundary and
closes afterward. Commit, causal files, environment and control-source hashes
all match. Default refusal precedes receipt and connector access. The gate is
ready only for a separate, explicit, one-use live authority; none is implied by
the seal itself.

That authority has now been consumed. Both allocated channels delivered
decodable SND/IQ, but their GPS solution age remained 92–103 seconds while the
prospective contract required at most 30 seconds. No readiness root was
admitted, so the run terminated `QUALIFICATION_INCOMPLETE` before discovery;
retune, freeze and confirmation are `NOT_EVALUATED`. No retry is authorized.
The next work must be an offline failure attribution of temporal capability,
not a threshold change or another acquisition.

Gate F2.5.26 now completes that attribution offline. Pinned server source and
the frozen receipt agree that the age byte is seconds since the latest GPS
position solution. Both channel transports were active, decoded IQ and had
gap-free local sequences; the terminal timeout followed the absence of any
frame satisfying the frozen 30-second event-time clause. The physical cause of
the stale server GPS state remains unknown, and every DDC hypothesis remains
`NOT_EVALUATED`.

The audit also exposes a contract-topology mismatch without changing the old
result. A same-ADC per-channel DDC intervention needs relative simultaneity,
continuity, command-boundary ordering and drift; absolute fresh GNSS was not
explicitly derived from that claim. The frozen receipt does not retain actual
server timestamps, monotonic arrivals, sample counts or command boundary times,
so this alternative is `NOT_FALSIFIABLE_WITH_THIS_RECEIPT`. Any successor must
first derive and freeze a new topology-specific temporal clause and its scalar
sufficient statistics. It must not raise the old threshold or reuse the
consumed authority.

Gate F2.5.27 now freezes the new temporal admission offline. A future SND frame
must be hashed before analysis and expose only endpoint/channel, sequence,
actual server seconds/nanoseconds, GPS-age byte, sample count, sample rate and
monotonic arrival in its retained receipt. Adjacent server timestamps must
agree with sample counts within one sample period; both branches must be
continuous, same-rate and overlap for at least two 1024-point STFT windows.
Absolute freshness is `NOT_REQUIRED` only for this same-ADC cut, while reserved
server clock states 253–255 remain explicit refusals.

The A1/B/A2 command boundaries are also predeclared as scalar witnesses across
both streams. This admits only the timing topology; it cannot prove that a
retune occurred or decide feature location. The next admissible work is an
offline post-commit integration/seal audit. It must show that the one-use path
captures these scalars before RF destruction and blocks every downstream phase
on temporal failure. No live authority or new observation exists yet.

Gate F2.5.28 now integrates the scalar contract into an injected one-shot
control path. Raw SND input is hashed before decode; decoded IQ remains in
private RAM and is exposed only through read-only callback views after temporal
admission. Frame or clock failure produces zero discovery and retune calls.
Discovery failure produces zero retune calls. Retune qualification additionally
requires both `A1_TO_B` and `B_TO_A2` boundary receipts. Every array is
zeroized and checked in `finally`, and only strict scalar/hash receipts return.

The parent sources, environment and exact parser/one-shot surfaces are sealed.
This is still synthetic integration: there is no connector, endpoint call,
plan freeze, confirmation or live authority. The next admissible work is an
offline live-facing wrapper audit with injected WebSocket frames, followed by
a separate post-commit seal. It must expose no caller-controlled endpoint,
frequency, timing, threshold, callback or receipt path.

Gate F2.5.29 completes that offline wrapper audit. Two already-open injected
SND branches run concurrently through the exact F2.5.17 auth, remote metadata,
single setup and SND transfer phases. Explicit rejection, description error
and inadmissible channel topology remain separate. The wrapper releases each
transport-frame lease, clears every bounded transient SND input after the
one-shot, and delegates IQ zeroization to F2.5.28. Absolute GPS-age freshness
does not re-enter the same-ADC relative-time contract.

There is still no connector, live runner, plan freeze or confirmation. The
next admissible work is a separate offline post-commit seal of a
default-refusing live-facing surface. It may expose only one authority bit and
must provide no caller-controlled endpoint, frequency, timing, threshold,
callback or receipt path. No network activity belongs in that seal audit.

Gate F2.5.30 attempted that seal audit and correctly refused to synthesize the
authority surface. F2.5.29 closes each branch socket in the collector `finally`
before the outer wrapper invokes discovery or retune. A deterministic test
observes both sockets closed inside both callbacks. Because the callback sees
only read-only IQ and no control handle, a live A1→B→A2 intervention cannot be
issued or witnessed by this surface. The sealed outcome is
`LIVE_SURFACE_NOT_SEALABLE`; it is not evidence against the Kiwi capability.

The next admissible work is an offline open-handle successor. It should retain
the two exact channel roots from initial temporal admission through discovery
and both command boundaries, expose retune only to an internal frozen command
executor, and close everything in one outer `finally`. It must first pass
injected socket lifetime and command-witness tests. Only its later post-commit
seal may add one default-refusing authority bit. No network belongs in either
offline step.

Gate F2.5.31 now materializes that open-handle successor offline. The two
injected branches remain open through A1 discovery and both commands; the
reference branch receives zero retunes, both F2.5.27 scalar boundaries are
witnessed, and all settling frames contribute to a full sequence/sample-clock
continuity receipt. One outer `finally` zeroizes every decoded frame and closes
both handles.

This repairs the lifecycle cut but does not yet justify a live seal. The
current positive outcome proves command/time topology only; it does not test
whether RF structure moved in the perturbed baseband or stayed channel-fixed.
The next admissible work is offline integration of the existing distributed,
target-excluded RF witness over these exact A1/B/A2 arrays. Thresholds and
control geometry must remain unchanged. `INTERVENTION_INVALID`,
`NOT_DETECTABLE` and physical hypothesis outcomes must remain distinct. Only a
later post-commit audit may expose a default-refusing authority bit.

Gate F2.5.32 now completes that RF-response integration offline. After both
scalar boundaries and full-session continuity pass, the reviewed distributed
witness excludes the target at every predeclared control position and tests a
fixed reference, unique perturbed translation, A2 return and even/odd
consistency. Target B/A2 data is not matched until a plan containing both
hypotheses and all negative controls has been immutably hashed.

Synthetic tests now keep `INTERVENTION_INVALID`, `NOT_DETECTABLE`,
`UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`,
`DOWNSTREAM_CHANNEL_FIXED_SUPPORTED` and `AMBIGUOUS` distinct while preserving
zero RF persistence. This is evaluator/lifecycle evidence, not a live physical
outcome. The next admissible work is a separate offline post-commit seal of
this exact surface. It may add only a default-refusing authority bit; it must
not add endpoint, frequency, timing, threshold, callback or retry controls, and
must perform no network activity.

Gate F2.5.33 now completes that post-commit seal offline. Commit, F2.5.32
source, immutable plan, private integration surface, live-facing adapter and
numerical environment are exact. The sole public execution signature exposes
only `live_authorised=False`; refusal precedes assessment, receipt creation and
network access. Mutable WebSocket payload ownership is transferred into the
reviewed lease boundary, while partial dual-connector failure closes the peer
and terminalizes the receipt.

No authority was consumed. The next action requires a new explicit decision:
either retain the sealed runner unused or authorize one live execution. If
authorized, that run has zero retry, no changed endpoint/frequency/thresholds,
and must stop after the first terminal outcome. No further implementation is
needed before that decision.

The one Gate F2.5.33 authority was consumed on 19 August 2026 and produced
`NO_FALSIFIABLE_INTERVENTION`. Both SND handles opened with distinct channel
IDs, identical sample rates and admissible relative timing. The unchanged A1
discovery admitted no common feature, so the runtime emitted zero retune
commands and left every physical hypothesis `NOT_EVALUATED`.

The outcome is frozen in `GATE_F2_5_33_OUTCOME_1.md` and its strict receipt.
No retry or second window is authorized. Because the negative discovery
receipt contains no candidate-stage counts or threshold margins, future work
must begin with an offline attribution of what this receipt can and cannot
distinguish. It must not lower thresholds, reinterpret the result as an empty
passband or acquire new data.

Gate F2.5.34 completes that receipt-only attribution. The committed artifact
proves that both SND branches, relative timing and the normal discovery
transform were operational, and that no candidate survived the complete
frozen admission rule. It does not reveal whether the first lost predicate was
joint contrast, patch validity, cross-branch correlation or half-window
stability. That internal cause is `INCONCLUSIVE`; the DDC-location hypothesis
is `NOT_FALSIFIABLE_WITH_THIS_RECEIPT` because no plan was frozen and no
intervention occurred.

The minimum future repair is descriptive, not observational: attach scalar
stage counts and finite threshold margins to the same pre-analysis hashes,
without allowing that sibling receipt to change selection and without
retaining RF. Gate F2.5.22 already demonstrates the required shape, so a new
framework is unnecessary. Any such repair belongs to a future separately
reviewed experiment; Gate F2.5.34 adds no authority, runtime change or window.

Gate F2.5.35 now materializes that repair as an offline successor. The
authoritative selector decision is constructed first; a sibling scalar audit
then records closed stage counts and best finite margins to the unchanged
contrast, correlation and half-stability thresholds. Both receipts bind the
same 16 A1 frame hashes. A description failure retains only its type and hash
and is structurally unable to alter selection or downstream physical control
flow.

Deterministic negative and positive tests preserve the exact frozen discovery
receipt, phase semantics and F2.5.32 physical evaluator outcomes. No connector
or authority surface exists and no RF-derived array persists. The next
admissible work is a separate offline post-commit seal of this exact successor;
only later review may grant one new single-use live authority.

Gate F2.5.36 now seals the exact F2.5.35 commit offline. Source, inherited
plan, decision/audit boundary, full injected integration, reviewed F2.5.33
connector, numerical environment, endpoint, receipt shape and live call graph
are hash-bound. The public surface has one keyword-only default-false
authority bit; refusal occurs before assessment, artifact creation or network
access.

The single authority has now been consumed with zero retry. The run admitted
two same-clock SND branches and one common A1 feature, and witnessed both local
retune boundaries, before ending `INTERVENTION_INVALID`. Both physical
hypotheses remain `NOT_EVALUATED`. The exact one-per-branch continuity failure
is reproducible from the leading-zero timestamp that initial admission counted
and excluded but the full-session evaluator compared against the first valid
timestamp. This is an offline-attributed `QUALIFICATION_ERROR`, not evidence
of a remote clock jump.

Gate F2.5.37 now completes that offline repair without editing the frozen
F2.5.31–36 sources. The full-session evaluator reuses the exact F2.5.27
leading-zero/GPS-week normalization already used at initial admission. Tests
reproduce both live residuals, prove that only leading zeros are excluded,
preserve interior-zero refusal and GPS rollover, and carry the existing
synthetic vertical beyond the former false continuity block with unchanged RF
decisions and cleanup.

No connector, public authority, retry, threshold or experiment dimension is
added by F2.5.37.

Gate F2.5.38 now completes the post-commit seal offline. It binds the F2.5.37
commit, source, plan, continuity evaluator, temporary installation scope,
corrected integration, reviewed connector, numerical environment, receipt
shape and complete live surface. Default refusal occurs before assessment,
artifact creation and connector access; injected tests exercise only synthetic
sockets and strict receipts.

The single later authority has now been consumed with zero retry. The run
admitted two simultaneous branches and the corrected relative-time topology,
then stopped `NO_FALSIFIABLE_INTERVENTION` before retune. The scalar sibling
audit localizes the failure without changing it: all five patches were
complete, four passed correlation, and none reached the inherited `3.0 dB`
minimum in both temporal halves; the best such minimum was
`2.0756149291992188 dB`.

The measurement path was available, but no A1 feature satisfied the complete
frozen proposition needed to authorize an intervention. Both DDC hypotheses
therefore remain `NOT_EVALUATED`. This outcome must not be converted into a
claim that no signal or physical phenomenon existed, and it grants no retry.
Any successor begins with offline interpretation of this frozen receipt, not
with another acquisition or threshold change.

## Only after one valid prospective outcome

Review which abstractions were actually necessary. Candidates for deletion or
demotion include:

- a central planner;
- target identity;
- `BeliefSnapshot`;
- a generic instrument object;
- universal multi-sensor requirements;
- permanent source adapters;
- calibrated probabilities.

Do not generalize the surviving primitives until a second genuinely different
experiment needs them.

## Engineering integration

- Run both offline experiment suites on pushes and pull requests.
- Keep live network activity out of CI.
- Maintain strict JSON and zero-RF-persistence tests.
- Keep frozen outcome documents append-only.
- Describe every live runner as disposable experiment code, not product
  architecture.

## Explicitly deferred

- database and RF storage;
- frontend and dashboards;
- microservices and schedulers;
- source marketplace or persistent capability registry;
- generic adapter SDK or experiment DSL;
- ML/LLM selection of phenomena;
- TDoA and geolocation;
- new SatNOGS source expansion;
- transmitter identification;
- production deployment.

The project advances by closing one causal ambiguity at a time, not by adding
features around an unverified inference.

## Current satellite-first forward route: independent GNSS station pair

The continuous-phase G22/G30 mechanism has passed one held-out GOLD/NLIB
primary and one distinct-pass replication. The authorized claim remains
repeated-pass consistency for that exact pair; shared station systematics are
still open.

The current route therefore preserves the same orbital coordinate and changes
the observer roots. DRAO/WES had the strongest geometry but failed metadata
admission because WES provides RINEX v2 rather than explicit L1C/L2W signal
identity. No payload was opened.

ALGO00CAN + MDO100USA has now passed its sole model-blind DOY217 qualification.
The pair retains 47,828.042 m of complete modeled margin and has demonstrated
the required 139-epoch L1C/L2W/LLI path plus C1C/C2W witnesses on physically
distinct hardware, antenna, organisation and ingest roots.

The distinct DOY219 primary is now selected and prediction-frozen without
opening either observation. Two exact ALGO/MDO locators returned descriptive
HEAD metadata, while artifact hashes remain intentionally unknown until a
future single materialization before any header decode. The exact-hash
broadcast NAV compilation reproduces the G14-controlling 51,370.299 m
separation, 3,542.257 m pairwise guard and 47,828.042 m remaining margin. The
seal grants no observation authority. The immediate blocker is review of this
one-shot proof boundary, not further selection or infrastructure. See
[`GNSS_INDEPENDENT_PAIR_PRIMARY_PLAN.md`](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_PRIMARY_PLAN.md).

That one authorized DOY219 execution is now closed as
`PRIMARY_ARTIFACT_MATERIALIZATION_FAILED`. ALGO timed out before a complete
artifact existed, MDO was not attempted, and no header, observation value or
orbital score entered the result. DOY219 cannot be retried, reopened or
substituted.

A new bounded orbit-only screen has therefore selected DOY223 without opening
any observation product. Over the fixed DOY221--223 candidate set, all three
dates retained positive ALGO/MDO G22/G30 geometry; DOY223 ranks first at
2026-08-11 05:24:00--06:33:00 GPS. The controlling wrong-orbit G14 separation
is 54,990.702 m peak-to-peak against a 3,142.164 m pairwise envelope, leaving
51,848.538 m. This is geometry selection only, not a prospective plan or
measurement. The next maximum work is to freeze one DOY223 primary contract
before discovering or materializing its two observation artifacts. See
[`GNSS_INDEPENDENT_PAIR_NEXT_PRIMARY_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_NEXT_PRIMARY_SCREEN_REPORT.md).

The corresponding DOY223 primary contract is now observation-blind and frozen.
It binds the two logical ALGO/MDO products, a closed ordered mirror set, the
139-epoch window, witnesses, physical envelope and nulls. Transport may retry
or resume only during bounded pre-hash materialization; after complete hashes
or any decode begins there is no retry, substitution or second window. At
freeze, all observation access counters remain zero. The next maximum work is
an exact-hash offline prediction seal, not an observation request. See
[`GNSS_INDEPENDENT_PAIR_DOY223_PRIMARY_PLAN.md`](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_PRIMARY_PLAN.md).

That offline prediction seal is now complete. It binds source commit,
dependencies, plan manifest, the exact NOAA DOY223 broadcast NAV hashes and the
five immutable 137-epoch curves. The compiled regression retains the
54,990.702 m G14-controlling separation and 51,848.538 m physical margin, with
all observation access counters still zero. The next maximum step is review of
the already defined bounded primary materialization; the seal itself does not
authorize it. See
[`GNSS_INDEPENDENT_PAIR_DOY223_PREDICTION_REPORT.md`](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_PREDICTION_REPORT.md).

The corresponding disposable executor is now source- and manifest-sealed. It
implements only the two frozen products, bounded retry/resume before complete
hashes, both hashes before decode, the qualified L1C/L2W plus witness path and
the frozen held-out scorer. No observation request or outcome exists, and the
executor seal grants no live authority. The next maximum step is therefore one
explicit execution review, not more implementation or selection. See
[`GNSS_INDEPENDENT_PAIR_DOY223_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_EXECUTOR_REPORT.md).

That one authorized DOY223 execution is now closed as `MEASUREMENT_INVALID` at
`HATANAKA_DECODE_FAILED:ALGO00CAN`. Both frozen byte streams reached complete
SHA-256 receipts before the first decode; ALGO then failed the frozen Hatanaka
decoder, MDO was not decoded, and admission and held-out scoring remained
`NOT_EVALUATED`. The receipt does not identify the underlying response-body or
encoding cause, so none is inferred. No observation value or RF artifact was
persisted, and the primary cannot be retried, repaired in place or moved to a
second window. See
[`GNSS_INDEPENDENT_PAIR_DOY223_OUTCOME_REPORT.md`](experiments/orbital_discriminability/GNSS_INDEPENDENT_PAIR_DOY223_OUTCOME_REPORT.md).

The post-outcome change-of-abstraction review does not continue that transport
chain. It compares a wholly disjoint pair, a held-out observer, a one-new-root
cross baseline, SatNOGS and fixed public SDR roots. The recommended minimum
next work is an offline observer-transfer spike: freeze a candidate family on
development observers A/B, then test whether a one-anchor continuous-phase
coordinate at unseen observer C can retain positive orbital-versus-null margin
without a free rate or suffix fit. No station, date, locator or artifact is yet
selected. See
[`POST_DOY223_INDEPENDENT_OBSERVER_REVIEW.md`](experiments/orbital_discriminability/POST_DOY223_INDEPENDENT_OBSERVER_REVIEW.md).

The recommended offline spike is now frozen as
`OBSERVER_TRANSFER_MECHANISM_DISCRIMINATIVE`. On its deterministic synthetic
high-elevation geometry, the one-anchor observer-C coordinate retains
1,703.225 m peak-to-peak separation from the prediction-frozen affine null,
against a 286.883 m pairwise physical envelope. Common receiver clock cancels;
signal-specific hardware remains a mandatory C-prefix admission bound. A
wrong-orbit truth stress selects the wrong orbit, so the target is not favored
by construction. This advances only the mechanism: no real observer, date,
product or primary has been selected, and no measurement is authorized. The
next maximum work after review is bounded orbit-only observer ranking before
artifact discovery. See
[`GNSS_OBSERVER_TRANSFER_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_OBSERVER_TRANSFER_SPIKE_REPORT.md).

The bounded real-geometry successor is now frozen without creating a new gate
or opening observations. Four unused observers times three frozen post-A/B
NAV days yield 12/12 positive cases. The distinct-observer shortlist is
PIE100USA/DOY223, WES200USA/DOY223 and AMC400USA/DOY221; PIE leaves
187,324.520 m after the complete 2,907.821 m pairwise envelope. WES remains
historically capability-rejected because its RINEX v2 feed does not establish
L1C/L2W identity, so this geometry result does not reinstate it. The next
maximum work is bounded PIE-only capability characterization before selecting
any qualification artifact or primary. See
[`GNSS_OBSERVER_TRANSFER_GEOMETRY_REPORT.md`](experiments/orbital_discriminability/GNSS_OBSERVER_TRANSFER_GEOMETRY_REPORT.md).

The bounded PIE-only metadata check has confirmed exact CDDIS RINEX 3 compact
products for DOY221 and DOY223 plus one continuous documented receiver,
antenna and H-maser/10 MHz/PPS configuration across both dates. No observation
body was requested and DOY223 remains unopened. Product naming cannot prove
L1C/L2W, LLI, C1C/C2W, actual epoch coverage or continuity, so the state is
`PIE_METADATA_PATH_AVAILABLE`, not capability admission. The next maximum
action, after explicit review, is one DOY221-only structural qualification;
DOY223 access remains forbidden. See
[`PIE_OBSERVER_CAPABILITY_METADATA_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_CAPABILITY_METADATA_REPORT.md).

That one DOY221-only structural qualification is now complete as
`PIE_OBSERVER_QUALIFICATION_PASSED`. The full artifact was hashed before
decode; the complete 139-epoch G22/G30 window, L1C/L2W plus LLI structure and
C1C/C2W same-path witnesses all passed. The qualifier parsed and persisted
zero observation values, produced zero orbital scores and left DOY223 wholly
unopened. Geometry-free numerical phase health remains `NOT_EVALUATED`, so the
next maximum work is review and freezing of one prospective PIE/DOY223
contract with an explicit measurement-admission rule. It is not authority to
open the primary. See
[`PIE_OBSERVER_QUALIFICATION_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_QUALIFICATION_REPORT.md).

The prospective PIE/DOY223 proof contract is now frozen with zero additional
network or observation access. It preserves the exact 139-epoch geometry and
replaces the inherited unwitnessed 4 m hardware assumption with a fixed
full-window ionosphere-free code-phase witness of 1,250 m p-p per satellite.
No constant, rate, time phase or suffix nuisance may be fitted. The revised
pairwise guard is 7,899.821 m and the affine-controlling margin remains
182,332.520 m. The state is `PIE_OBSERVER_PRIMARY_PLAN_FROZEN`; DOY223 is still
unopened and no executor exists. The next maximum work, after review, is an
offline exact-hash prediction seal from the already frozen broadcast NAV
authority. See
[`PIE_OBSERVER_PRIMARY_PLAN.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_PLAN.md).

The reviewed offline prediction seal is now frozen without primary access.
Exact-hash NOAA DOY223 broadcast navigation binds all five nominal curves and
the eight direct `t +/- 15 s` orbital envelope curves. The affine null remains
controlling at 190,232.341 m, the direct timing envelope is 1,418.146 m, joint
visibility remains complete and the revised physical margin remains
182,332.520 m. This is `PIE_OBSERVER_PRIMARY_PREDICTION_FROZEN`, not a
measurement or executor authority. The next maximum work is review of a
minimal one-shot executor; until then the PIE DOY223 product remains unopened.
See
[`PIE_OBSERVER_PRIMARY_PREDICTION_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_PREDICTION_REPORT.md).

The minimal PIE executor is now frozen offline as
`PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED`. Source commit `c9334e4` and
executor seal SHA-256 `3b15c0c8...33e2b` bind the sole DOY223 product, exact
prediction and plan, qualified transform, one-shot transport boundary,
measurement admission and no-fit held-out scoring. All primary access counters
remain zero. The seal grants no live authority; the next maximum work is a
separate decision on one exact execution. See
[`PIE_OBSERVER_PRIMARY_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_EXECUTOR_REPORT.md).

The one authorized PIE execution is now closed as
`PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED`. The exact product was completely
SHA-256 hashed on the first transport attempt before decode; the complete
139-epoch measurement contract and all witnesses passed. With no fitted
nuisance parameters, G22 leaves `2.279 m` p-p on the frozen held-out suffix,
versus `190,230.062 m` for the affine runner-up. The `190,227.783 m` preference
margin is well above the fixed `7,899.821 m` guard. The result authorizes only
`HELD_OUT_STATION_CONFIRMED_FOR_THIS_ORBIT_SIGNAL_WINDOW`. No observation value
or product bytes persist, and the consumed primary may not be retried or
rescored. See
[`PIE_OBSERVER_PRIMARY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/PIE_OBSERVER_PRIMARY_OUTCOME_REPORT.md).

The bounded next-replication review selects AMC400USA/DOY221 from the already
frozen observer shortlist, without a new geometry search or observation
access. It combines a new station and new pass with `159,899.492 m` remaining
modeled margin and a `25.726 deg` minimum shifted elevation. Official metadata
establishes a physical receiver, antenna, monument and H-maser root distinct
from PIE, while the shared POLARX5TR family remains a declared limitation.
GSSC directory descriptions contain one exact AMC file for DOY222
qualification and one for the still-unopened DOY221 primary candidate. This is
`AMC_REPLICATION_METADATA_PATH_AVAILABLE`, not qualification or a prospective
plan.

The corresponding one-shot value-blind DOY222 execution is now consumed as
`AMC_OBSERVER_QUALIFICATION_PASSED`. The exact 3,455,043-byte artifact was
SHA-256 hashed before decode on the first attempt. All 1,668 structural rows
are present, G22/G30 span the complete 139-epoch core phase/LLI window, and all
four C1C/C2W witness links have 100 percent coverage. Zero observation values
and zero product bytes persisted; quantitative measurement admission and
orbital scoring remain `NOT_EVALUATED`.

The prospective AMC/DOY221 contract is now frozen offline as
`AMC_OBSERVER_PRIMARY_PLAN_FROZEN`; DOY221 remains unopened. It binds the exact
139-epoch window, sample-zero anchor, fixed prefix/held-out split, zero fitted
nuisance parameters and the affine/G01/G14/G17 alternatives. Replacing the
unwitnessed 4 m hardware term with the predeclared full-window code-phase rule
raises the pairwise guard to `7,339.701 m`, still leaving `154,907.492 m`
against the controlling affine separation. The distinct physical instance and
pass test observer transfer, while the common POLARX5TR family remains a claim
limitation. This is a frozen plan, not primary access or an orbital outcome.
See
[`AMC_OBSERVER_REPLICATION_METADATA_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_REPLICATION_METADATA_REPORT.md)
and
[`AMC_OBSERVER_QUALIFICATION_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_QUALIFICATION_EXECUTOR_REPORT.md).
The consumed qualification is documented in
[`AMC_OBSERVER_QUALIFICATION_OUTCOME_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_QUALIFICATION_OUTCOME_REPORT.md),
and the frozen proof design is
[`AMC_OBSERVER_PRIMARY_PLAN.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_PLAN.md).

That exact-hash prediction seal is now complete as
`AMC_OBSERVER_PRIMARY_PREDICTION_FROZEN`. The NOAA DOY221 broadcast NAV exactly
reproduces `162,247.193 m` separation from the affine controller, the direct
clock envelope is `1,138.625 m`, minimum shifted elevation is `25.726 deg`, and
the frozen decision guard leaves `154,907.492 m`. The seal accessed zero AMC
locator, header, payload or value data and produced zero orbital scores. It
authorizes neither executor nor primary access. See
[`AMC_OBSERVER_PRIMARY_PREDICTION_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_PREDICTION_REPORT.md).

The minimal experiment-specific executor is now frozen as
`AMC_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED`. It binds the sole DOY221
logical product, the exact plan and prediction seals, the AMC-qualified header
transform, full-window measurement admission, the same-path witness and the
zero-fit held-out comparison. Source commit `b31a987` and executor seal
`0b6ffe5a...f44893` retain zero primary access and grant no live authority. The
next maximum work is a separate decision on exactly one execution, not further
executor or infrastructure work. See
[`AMC_OBSERVER_PRIMARY_EXECUTOR_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_EXECUTOR_REPORT.md).

The reviewed one-shot execution is now consumed and terminal as
`AMC_HELD_OUT_ORBITAL_MODEL_PREFERRED`. The exact 3,415,979-byte product was
hashed before decode on the first transport attempt; all 139 epochs, event
time, core phase/LLI, geometry-free continuity and same-path code witnesses
passed. With no fitted nuisance parameters, G22 leaves `1.409 m` p-p on the
held-out suffix against `162,245.831 m` for the affine runner-up. The resulting
`162,244.422 m` preference margin passes the fixed `7,339.701 m` guard. This
closes the planned observer/pass replication positively, without claiming
satellite identity, orbit recovery or independence from the POLARX5TR receiver
family shared with PIE. No retry or rescore is permitted. See
[`AMC_OBSERVER_PRIMARY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/AMC_OBSERVER_PRIMARY_OUTCOME_REPORT.md).

The post-AMC review does not create a new gate or continue station accumulation.
It ranks one bounded cross-receiver-family observer transfer ahead of blind
orbit assignment and independently timed RF for the immediate next action.
The route changes the POLARX5TR tracking implementation while retaining the
successful G22/G30 physical coordinate and null discipline. At most five
hardware-diverse roots may be declared before observation access; geometry is
ranked orbit-only, qualification and primary dates are distinct, and one
terminal primary ends the traditional GNSS replication ladder. Failure to
find documented family diversity, positive complete margin or a stable
qualification/primary path must stop synthesis rather than expand inventory.
See
[`POST_AMC_NEXT_INFORMATION_REVIEW.md`](experiments/orbital_discriminability/POST_AMC_NEXT_INFORMATION_REVIEW.md).

## Terminal cross-family and raw-RF route decisions

The one permitted traditional-GNSS cross-family screen is complete as
`NO_CROSS_FAMILY_GEOMETRY_SHORTLISTED`. Its bounded set produced no root that
simultaneously cut the POLARX5 family, retained explicit signal semantics and
covered the unchanged 139-epoch G22/G30/null geometry. No qualification or
primary was selected. The roadmap therefore retains
`STOP_TRADITIONAL_GNSS_REPLICATION` and forbids another station-search
successor. See
[`GNSS_CROSS_FAMILY_BOUNDED_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_CROSS_FAMILY_BOUNDED_SCREEN_REPORT.md).

The bounded independently timed raw-RF audit is also terminal for its exact
five predeclared families. It accessed metadata only and stopped
`NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL`: two families lack open-loop
complex samples, SLIM declares internal time, and the otherwise promising
Voyager/GBT and Artemis I products do not provide a product-applicable finite
ADC-sample-zero UTC bound together with complete immutable orbit/artifact
lineage. Unknown bounds remain unknown; detector work and held-out scoring are
not authorized. See
[`RAW_RF_TIME_ORBIT_METADATA_AUDIT_REPORT.md`](experiments/orbital_discriminability/RAW_RF_TIME_ORBIT_METADATA_AUDIT_REPORT.md).

The next physical question was therefore changed to bounded blind orbit
assignment. Its first observation-blind screen is now complete as
`BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED`. Five exact NOAA broadcast-navigation
days and the already characterized AMC geometry selected DOY226,
06:14:30--07:23:30 GPS, with the family G22/G06/G14/G17/G19. The controlling
prefix-frozen affine separation is 18,763.717 m peak-to-peak; after the
unchanged 7,339.701 m guard, 11,424.015 m remains. No observation product,
header or value was discovered or opened, and no prospective plan or primary
is frozen. See
[`GNSS_BLIND_ORBIT_ASSIGNMENT_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_BLIND_ORBIT_ASSIGNMENT_SCREEN_REPORT.md).

The opaque-hypothesis prospective-plan audit for this one geometry is now
complete as `BLIND_ORBIT_ASSIGNMENT_PLAN_FROZEN`. It binds only
`AMC400USA_R_20262260000_01D_30S_MO.crx.gz`, whose existence remains
`UNKNOWN_UNQUERIED`; no fallback station, date, cadence, window or archive is
allowed. Six preaccess opaque identifiers cover the five frozen orbital
candidates and the affine null. The scorer must handle every hypothesis in
one identical loop with exactly a prefix constant and rate, and it may not
receive the PRN mapping, product metadata, navigation parser or observation
decoder. The mapping is reviewable in the repository, so the claimed
blindness is an enforced interface boundary, not cryptographic secrecy. No
product locator, header, payload byte, value or score was accessed.

The offline exact-hash prediction bundle and scorer seal are now complete as
`BLIND_ORBIT_PREDICTION_AND_SCORER_SEALED`. The exact NOAA DOY226 navigation
product reproduced the frozen orbital regressions, then its temporary copy was
destroyed. The scorer-facing bundle exposes only six opaque arrays, grid and
scoring constants. The scorer cannot import the mapping, any named orbit,
navigation compiler or observation decoder; it applies one identical
constant/rate prefix fit and hashes an opaque, value-free receipt before any
identity reveal. Synthetic tests cover a positive opaque preference and an
exactly ambiguous controlling midpoint. Primary access and measurement scores
remain zero.

The reviewed one-shot executor was then seal-bound without primary access and
the separate authority was consumed exactly once. The exact 3,456,560-byte AMC
DOY226 product was hashed before decoding; all 139 epochs and frozen physical
witnesses passed. The opaque scorer preferred `H_72E7F21DC8244653` with a
`6.104475 m` held-out peak-to-peak residual, while the runner-up retained
`18,768.100639 m`. The `18,761.996164 m` preference margin exceeds the frozen
`7,339.701235 m` guard. Only after the score receipt hash was persisted did the
mapping reveal the best identifier as `G22_RELATIVE_TO_G30`.

The terminal is `BOUNDED_TRUE_ORBIT_PREFERRED`, authorizing only
`BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET`. Compressed
and decoded observations and observation values persisted zero bytes. The
primary is consumed: no retry, rescore, alternate product or hypothesis change
is permitted. No automatic gate follows. Any next work must first compare
physically independent ways to test transfer of this blind preference, rather
than resume traditional GNSS station inventory. See
[`GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_OUTCOME_REPORT.md).

That comparison is now complete offline. The blind scorer never received PRN
identity, but the executor had already selected the G22/G30 RINEX channels;
the experiment therefore supports bounded specific-orbit preference, not
independent signal identity. Another RINEX observer preserves this causal
topology and is not the next route. The recommended minimum is an offline
anonymous-track mechanism spike: derive synthetic simultaneous tracks without
AMC values, keep the code/PRN identity receipt outside the orbital scorer,
freeze orbit and code receipts separately, and reveal their concordance only
after both exist. No capability search or acquisition is authorized until
this topology retains a non-empty discriminative region under timing,
oscillator, propagation, ambiguity and track-permutation envelopes. See
[`POST_BLIND_ORBIT_INFORMATION_REVIEW.md`](experiments/orbital_discriminability/POST_BLIND_ORBIT_INFORMATION_REVIEW.md).

The mechanism spike now returns
`ANONYMOUS_TRACK_SEALED_WITNESS_MECHANISM_DISCRIMINATIVE`. Its pure scorer
receives only two anonymous same-clock tracks, eleven opaque curves and one
guard. A wrong-orbit truth selects G06, a deliberately contradictory code
witness remains discordant, reversed track order selects the frozen reversed
orientation, and the G22/affine midpoint remains ambiguous. The exact fixture
margin is `18,763.716565 m`; after the historical development guard,
`11,424.015330 m` remains.

This is not capability admission. Sample-zero timing/rate, differential
non-affine oscillator behavior and propagation remain `OPEN_TERM`; cycle slips
and gaps are pre-score invalidity, while track permutation is an explicit
hypothesis family. No observation access occurred. After review, the maximum
next action is one bounded raw-GNSS capability consideration with valid
`NO_CAPABILITY_AVAILABLE` and `NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT` terminals,
not a catalog or another RINEX station. See
[`GNSS_ANONYMOUS_TRACK_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_ANONYMOUS_TRACK_SPIKE_REPORT.md).

The single bounded raw-GNSS consideration is complete as
`NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT`. It did not create a catalog. TEX-CUP
May 9/12 has the needed continuous L1/L2 raw-IF topology, but the official data
surface currently exposes no products and exact former payload URLs return
HTTP 404. LuGRE Zenodo `16411687` is reachable, immutable and exposes seven
same-operation L1/L5 IQ snapshot pairs, but each is only `0.3--2.0 s` and the
inspected documentation does not supply product-applicable finite ADC-time or
sample-rate-accuracy bounds. Zero sample bytes were accessed.

Do not respond by searching more receiver inventories or by adapting the
139-epoch runtime to snippets. The next maximum work is an offline LuGRE
constellation-snapshot discriminability calculation: determine whether a
simultaneous anonymous multi-satellite frequency pattern survives
common-clock, timing, permutation, propagation and non-orbital nulls before
any IQ access. A non-positive margin must close the route. See
[`RAW_GNSS_CAPABILITY_CONSIDERATION_REPORT.md`](experiments/orbital_discriminability/RAW_GNSS_CAPABILITY_CONSIDERATION_REPORT.md).

The bounded offline LuGRE calculation has now returned
`LUGRE_SNAPSHOT_GEOMETRY_DISCRIMINATIVE`. It used six exact-hash NOAA
broadcast-navigation days and archived CLPS observer geometry, with zero LuGRE
payload access. Four simultaneous L1 coordinates are projected against the
same common offset and positive scale for the orbital family and all nulls.
The observation-blind family selector is the four unocculted healthy GPS
satellites with minimum transmit off-boresight; it uses no gain, received
power, code identity or signal result.

OP76 ranks first with G31/G28/G26/G10, `17.465--34.527 deg` off-boresight and
an `11.019310 Hz` controlling static-observer separation. The symmetric total
per-track RMS envelope ceiling is `5.509655 Hz`. The full 30--31-satellite
population remains a conservative codebook stress surface whose controlling
separation is only `0.008811--0.060388 Hz`; it is not the physical target
selector. Discrete OP76 timing stresses preserve the selected identity at
`+/-10 s` but not `+/-60 s`, without converting that observation into an ADC
timing bound.

The next maximum work, only after review, is a metadata-first prospective
freeze that tries to close exact IQS timing/receiver transforms and physical
error envelopes for a possible OP73-development / OP76-primary / OP74-reserve
split. Failure to establish all four frozen signals or a complete envelope
must terminate before measurement scoring. Do not open LuGRE IQ, NAV/EPH
telemetry or post-processed identity results merely because geometry is
positive. See
[`LUGRE_SNAPSHOT_DISCRIMINABILITY_REPORT.md`](experiments/orbital_discriminability/LUGRE_SNAPSHOT_DISCRIMINABILITY_REPORT.md).

That metadata-first audit is complete and stops
`LUGRE_PROSPECTIVE_PLAN_BLOCKED_BY_ADC_TIME_PROVENANCE`. The six exact SDRX
companions materially improve the instrument picture: OP73/OP74/OP76 have
simultaneous L1/L5 capture timestamps, `8/24 MHz` rates, 4-bit complex IQ,
zero translated frequency and no inversion. Same-file affine offset and scale
remain projected by the frozen score. However, `rxTime`/`SC_Start` semantics do
not provide a numerical ADC-to-true-GPST accuracy bound; the repeated one-
millisecond SDRX/OPTABLE difference is resolution/convention evidence only, and
the generic public `50 ns` receiver figure is not product-applicable. The
DEFLATE IQS members also prevent header-only access without sample bytes, so
the exact binary headers remain unopened. No role, detector or prospective plan
is frozen. The route may continue only if outcome-independent timing provenance
closes this clause; otherwise LuGRE closes without RF access. See
[`LUGRE_PROSPECTIVE_METADATA_AUDIT_REPORT.md`](experiments/orbital_discriminability/LUGRE_PROSPECTIVE_METADATA_AUDIT_REPORT.md).

The final bounded timing-provenance audit closes this branch as
`LUGRE_ROUTE_CLOSED_BY_ABSOLUTE_TIME_PROVENANCE`. Public preflight mission
architecture documents the receiver-time state machine, but no inspected
outcome-independent source supplies all numerical edges from ADC sample zero
through IQS tagging and receiver synchronization to true GPST/UTC. Timestamp
resolution, generic QN400-S performance and VCTCXO Allan deviation remain
distinct from that bound. OP73/OP76/OP74 are closed without IQ or telemetry
access; the positive geometry is preserved. There is no automatic successor.
Any future route must select a different orbit-first raw-IQ family whose
sample-zero time accuracy is documented before plan freeze. See
[`LUGRE_ADC_TIME_PROVENANCE_CLOSURE_REPORT.md`](experiments/orbital_discriminability/LUGRE_ADC_TIME_PROVENANCE_CLOSURE_REPORT.md).

## Post-LuGRE change of observable

The project does not automatically resume raw-IQ metadata search. A bounded
offline spike has established
`DISTRIBUTED_VISIBILITY_MECHANISM_DISCRIMINATIVE` on the existing G0 LEO
fixture. Dublin–Rome geometry retains a three-state
left-only → both-visible → right-only topology with a 105 s dwell margin after
the provisional timing allowance. The coordinate needs no sub-hertz ridge,
but its negative is usable only with a simultaneous transmitter-on root, a
same-path witness at the occulted root, immutable station identity and a
predeclared directional mask.

The spike does not establish specific orbit identity: the plausible adjacent
orbit changes relative event timing by at most 5 s against the 15 s comparison
bound. It also asserts no receiver near either city. The next maximum work,
only after review, is a metadata-only orbit/pass calculation for one current
candidate with independently witnessable emission and one bounded pair of
actual station coordinates. If the witnesses or timing cannot be qualified,
the route stops `NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE` without RF
access. See
[`DISTRIBUTED_VISIBILITY_EVENT_SPIKE_REPORT.md`](experiments/orbital_discriminability/DISTRIBUTED_VISIBILITY_EVENT_SPIKE_REPORT.md).

The current-candidate geometry audit is also complete. METEOR-M N2-4 / NORAD
59051 produces two positive Doncaster-envelope/YO3BN visibility margins (90 s
and 80 s) under the frozen adjacent-orbit and position ensemble. A third event
has zero positive timing slack, while the exact Bucharest–Dorohoi baseline
does not produce the complete three-state topology. This result does not
promote the Doncaster proxy to a station coordinate. None of the three bounded
public station descriptions closes event time, sequence continuity and a
same-path absence witness as a pair, so the branch stops
`NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE` with zero RF access. The next
maximum action is a reviewed, non-target-specific measurement-path check of
one explicitly named pair, not a catalog or a new geometry search. See
[`METEOR_M2_4_VISIBILITY_SHORTLIST_REPORT.md`](experiments/orbital_discriminability/METEOR_M2_4_VISIBILITY_SHORTLIST_REPORT.md).

The bounded OpenWebRX path and its SatNOGS alternative are now both concluded.
The SatNOGS development-only receipt found a common 160 kHz / 1,024-bin native
configuration, but not a common native row event-time sequence and not the
concrete model-driven Doppler control applied upstream of each waterfall.
Thus the actual terminal is `SATNOGS_DEVELOPMENT_METADATA_PATH_BLOCKED`, not a
negative orbital outcome. No detector was built and all four primary
artifacts remain sealed. A next vertical must preserve raw pre-control samples
or a reversible receiver-control ledger with bounded event time; repairing
SatNOGS raster transport is not on the active roadmap. See
[`METEOR_SATNOGS_DEVELOPMENT_METADATA_REPORT.md`](experiments/orbital_discriminability/METEOR_SATNOGS_DEVELOPMENT_METADATA_REPORT.md).

## Post-METEOR DORIS geometry route

The next abstraction is not another public-SDR transport. DORIS provides a
different physical topology: independent ground beacon transmitters,
beacon-specific propagation, and a shared spaceborne dual-frequency receiver.
The bounded orbit-only calculation stops
`DORIS_FORWARD_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED` with zero DORIS
RINEX access.

The current bounded scope is Sentinel-3A / NORAD 41335 on 2026-09-02 and four
predeclared current-beacon pairs. KRWB–LAPB, TLSB–WEUC and PAUB–RIMC are the
ranked geometry shortlist. Their preliminary held-out margins are 34,855.565,
21,465.993 and 18,144.799 Hz respectively after the same prefix-affine
projection and a current-versus-prior forecast envelope. These are orbit-only
screening margins, not measurement or detector margins.

No observation role is frozen. The route may advance only through a separate
development-only structural/metadata qualification that establishes:

- exact DPOD beacon coordinates, heights and antenna phase centers;
- actual station frequency-shift factors and dual-frequency observable map;
- DORIS-time, receiver-clock, time-reference and event-time semantics;
- continuous simultaneous L1/L2 phase with declared flags and C1/C2 witnesses;
- one-way light time, relativistic, atmospheric and antenna corrections;
- explicit treatment of shared receiver-clock and channel-dependent bias;
- complete coverage of a later frozen candidate window.

The tentative published development filename `s3arx26242.001.Z` and the
convention-derived future filename `s3arx26245.001.Z` are not authority to
download, decompress or inspect either product. The latter was not present and
is not a frozen primary. If the development metadata cannot close the causal
ledger without observation-value access, this route stops before a detector or
primary. See
[`DORIS_FORWARD_GEOMETRY_SPIKE_REPORT.md`](experiments/orbital_discriminability/DORIS_FORWARD_GEOMETRY_SPIKE_REPORT.md).

The authorised development header spike is also complete. It stops
`DORIS_DEVELOPMENT_HEADER_REJECTED`, without a measurement decision, because
`INTERVAL`, `TIME OF LAST OBS` and `MARKER TYPE` are absent. The same header
does materially confirm Sentinel-3A / DGXX-S, the complete dual-frequency
observable schema, `K` values and the TLSB–WEUC and PAUB–RIMC shortlist pairs.

Do not search for a more convenient header and do not weaken the missing-field
rules after the result. If separately authorised, the next maximum action is
one value-blind structural scan of this exact development product. It may
retain only epoch time, station identifier, record presence/continuation and
phase/code flags needed to determine cadence, simultaneous pair coverage and
segment breaks. Numerical phase, pseudorange, power, oscillator and
meteorological observations remain forbidden. See
[`DORIS_DEVELOPMENT_HEADER_REPORT.md`](experiments/orbital_discriminability/DORIS_DEVELOPMENT_HEADER_REPORT.md).

The authorised value-blind structural scan has now consumed that exact
development artifact and terminates
`DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT`. The scanner retained only epoch
time, station identity, presence and L1/L2/C1/C2 flags; all numerical
observation magnitudes remained unrepresented and unpersisted. PAUB–RIMC
provides a positive 633 s core L1/L2 overlap for a 480 s requirement, while
TLSB–WEUC provides 393 s for 430 s. Both full contracts fail because the
second station has no time-reference-valid C1/C2 witnessed segment.

Do not access candidate DOY245 and do not weaken the witness after observing
this result. The next maximum action is an offline physical-role audit of the
compound DORIS observable: establish whether dual-frequency L1/L2 phase itself
closes the dispersive/same-path cut, or whether the C1/C2 time-reference flag
is causally necessary for the intended claim. Only a predeclared answer may
change the minimum signal family. See
[`DORIS_DEVELOPMENT_STRUCTURAL_REPORT.md`](experiments/orbital_discriminability/DORIS_DEVELOPMENT_STRUCTURAL_REPORT.md).

The offline compound-observable audit is complete as
`DORIS_DUAL_PHASE_DIFFERENTIAL_REQUIRES_COEPOCH_REQUALIFICATION`. It shows that
L1/L2 ionosphere-free phase plus an exact common receiver epoch can cancel the
first-order ionosphere and shared receiver clock/proper-time terms without a
time-reference-valid C1/C2 field on every target record. It does not show that
the frozen development pair actually has that topology: the previous receipt
proved only overlapping independent station grids. PAUB–RIMC is the preferred
conditional pair because its 633 s core overlap exceeds the 480 s geometry
requirement and both frequency-shift factors are zero.

No primary, candidate-day product or observation magnitude may be accessed on
this result. The maximum next action, under separate authority, is a
value-blind requalification of the same development artifact for one
contiguous exact-coepoch PAUB–RIMC L1/L2 chain. Even a positive topology result
would leave absolute event time, higher-order ionosphere, differential
troposphere, phase centers, phase wind-up, relativity, non-affine ground-clock
behavior and receiver-noncommon bias explicit. See
[`DORIS_OBSERVABLE_ROLE_AUDIT_REPORT.md`](experiments/orbital_discriminability/DORIS_OBSERVABLE_ROLE_AUDIT_REPORT.md).

The one authorised value-blind requalification is complete as
`DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED`. The exact development stream contains
a PAUB–RIMC segment of 128 valid simultaneous L1/L2 epochs over 633 s, exceeding
the frozen 480 s requirement. Pairing uses identical DOR epoch tags, no
interpolation and a maximum 10 s pair gap. This proves that the shared
spaceborne receiver clock and proper-time terms can enter the predeclared
common-mode quotient topology.

The result does not admit observation magnitudes or the candidate day. The
next maximum action is an offline physical-envelope audit on this fixed 633 s
topology: absolute DOR-to-coordinate time, higher-order ionosphere,
differential troposphere, phase centers, wind-up, relativistic terms,
non-affine beacon oscillators and receiver-noncommon bias must leave a positive
orbital-versus-null margin. If they cannot, the DORIS vertical closes before
observation values. See
[`DORIS_EXACT_COEPOCH_REQUALIFICATION_REPORT.md`](experiments/orbital_discriminability/DORIS_EXACT_COEPOCH_REQUALIFICATION_REPORT.md).

That audit is now complete as `DORIS_PHYSICAL_ENVELOPE_BOUND_UNAVAILABLE`.
Three terms cancel exactly in the qualified coordinate—first-order
ionosphere, shared receiver clock and shared receiver proper time—but all
eight surviving term families still lack an applicable finite
outcome-independent uncertainty bound. Descriptive scales such as around
10 microseconds synchronization, a few millimetres phase noise and 0.3 mm/s
system performance are retained as diagnostics only, never converted into
hard bounds.

The audit also closes an implicit cross-date shortcut: the 633 s exact-coepoch
chain is a 2026-08-30 development capability proof, whereas the 18,144.799 Hz
preliminary geometry margin belongs to the unopened 2026-09-02 candidate.
There is no shared exact grid and therefore no combined measurement margin.
Do not access candidate phase or build a detector. A next physical proposal
must either close the eight families on a predeclared prospective grid or
change the observable topology so the independent beacon-USO and
receiver-noncommon curvature are observed/cancelled before discriminability is
recomputed. Do not search for a more convenient RINEX file as a substitute.
See
[`DORIS_PHYSICAL_ENVELOPE_AUDIT_REPORT.md`](experiments/orbital_discriminability/DORIS_PHYSICAL_ENVELOPE_AUDIT_REPORT.md).

The required change-of-abstraction review is complete as
`DORIS_TIME_REFERENCE_PAIR_SELECTED_GEOMETRY_UNEVALUATED`. It compares the
single-satellite time-reference pair, two distinct four-link/two-satellite
epoch alignments, and a limited C1/C2 clock bridge with exact symbolic event
keys. A receive-coepoch four-link difference leaves short-lag beacon-clock
differences; a transmit-coepoch alignment instead leaves receiver-clock
differences. Two satellites therefore do not create a generally clock-free
observable and add four receiver-channel terms.

The minimum forward candidate is one satellite and two header-declared
time-reference beacons, retaining the existing exact receiver-clock and
first-order-ionosphere cancellations. Its six-pair scope is frozen from ADHC,
HBMB, PAUB and TLSB, but no pair geometry or calibration uncertainty is yet
admitted. The next maximum physical action is one orbit-only discriminability
screen of those six pairs. It must close with no observation access if none has
positive geometry after frozen nulls; it must not become a new beacon catalog
or a search for a convenient product. See
[`DORIS_OBSERVABLE_TOPOLOGY_REVIEW_REPORT.md`](experiments/orbital_discriminability/DORIS_OBSERVABLE_TOPOLOGY_REVIEW_REPORT.md).

That bounded screen now closes
`DORIS_TIME_REFERENCE_TOPOLOGY_NO_JOINT_VISIBILITY`. On the unchanged 2026-09-02
Sentinel-3A trajectory, none of the six pairs has even one simultaneous sample
above 10 degrees, and a conservative continuous-cap proof excludes missed
between-grid visibility. ADHC-PAUB is geometrically closest but remains 27.541
degrees beyond the joint cap; no 360 s interval, calibration prefix or held-out
suffix exists. The affine, along-track, wrong-orbit and forecast-envelope nulls
remain frozen and `NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW`, rather than being
scored on an impossible coordinate.

The single-satellite/two-time-reference-beacon topology is therefore closed
for this candidate geometry. Do not search for a convenient observation or
weaken elevation/duration. Before further DORIS access, compare a bounded-USO
mixed beacon coordinate, a rigorously bounded short-lag multi-satellite
coordinate, and a physically distinct satellite observable. Advance only a
route that can instantiate its full causal graph and increase held-out orbital
information. See
[`DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_REPORT.md`](experiments/orbital_discriminability/DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_REPORT.md).

The bounded contact-topology spike is also closed as
`DORIS_STRUCTURAL_VISIBILITY_NOT_FALSIFIABLE_FROM_RETAINED_RECEIPT`. It tests
the abstraction change offline: use ordered beacon-contact intervals as the
orbital observable rather than requiring simultaneous dual-beacon phase. The
mechanism is physically plausible, but the existing receipt retained only
four of 56 station streams and the five longest phase-continuity segments for
each. It did not retain the complete station/epoch presence sequence, and its
segment boundaries are not acquisition or geometric rise/set events.

The decisive cut is absence semantics. Without a predeclared receiver
scheduling/channel-allocation policy, acquisition/dropout envelope and
telemetry-retention rule, a missing station record cannot mean that the beacon
was not visible. DOR-to-orbit event-time error and the matching development
orbit grid are also unbound. Time-shift, wrong-orbit, station-permutation and
schedule-only nulls therefore remain
`NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY`. No retrospective score, primary
selection or new data access is allowed. Continue this DORIS route only if an
independent structural qualification can make absences causally interpretable;
otherwise change sensor family rather than extending receipt infrastructure.
See
[`DORIS_CONTACT_TOPOLOGY_SPIKE_REPORT.md`](experiments/orbital_discriminability/DORIS_CONTACT_TOPOLOGY_SPIKE_REPORT.md).

Primary IDS/CNES documentation now makes the DORIS stop terminal. The
DGXX/DGXX-S seven-channel receiver does not preserve a one-to-one map from
physical visibility to station records: Sentinel-3 mixes DIODE designation
and random DAS-T selection, and modes can change in flight. Missing records
therefore cannot become occultation events without reconstructing historical
on-board designation state. Do not extend the DORIS scanner or search another
RINEX product for this observable.

The next change of information is instead proven offline as
`ALL_TRACK_BLIND_ASSIGNMENT_MECHANISM_DISCRIMINATIVE`. It removes the
experiment's upstream target/reference choice without claiming that RINEX is
code-blind. Six opaque tracks are scored against every one of 720 candidate
bijections and one affine null after common-mode ensemble centering and the
same prefix-only nuisance. Correct, permutation, code-discordance, affine,
out-of-family and midpoint controls all terminate as designed.

No station, date, product or primary is selected. The next maximum action is
one orbit-only screen of a bounded predeclared station/date set. Admission
requires complete predicted visibility for the full candidate codebook, a
positive all-assignment margin after one conservative envelope, and a
value-blind rule that includes every structurally complete track. If those
conditions do not coexist, close this mechanism before product discovery.
See
[`GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_REPORT.md).

That bounded screen now returns
`ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED`. Its station/date
scope was committed before navigation access: DRAO00CAN, ALGO00CAN and
WES200USA over GPS DOY229--233. The geometry itself defines the full six-orbit
codebook; no target or reference is selected, and any seventh complete track
makes a future measurement ineligible.

The screen corrects the conservative decision accounting from an informal
two-guard separation to three guards. The best true residual may grow by one
guard, the wrong residual may shrink by one, and the scorer still requires a
one-guard preference. On this rule, 3,403 of 13,465 exactly-six windows remain
positive. The top three are ALGO00CAN DOY230/229/231 with the same
G05/G15/G18/G20/G21/G29 family and robust lower margins of
49,100.424, 48,939.826 and 48,748.701 m. The closest wrong bijection, not the
affine null, controls each.

No observation locator, product, header, payload or value was accessed, and
the five exact-hash broadcast-navigation payloads were destroyed. The next
maximum work, only after review, is selecting one independent structural
qualification artifact rather than a primary. It must prove that all and only
six structurally complete L1C/L2W tracks enter under a PRN- and value-blind
rule and that ALGO-specific physical terms fit the frozen decision envelope.
Failure closes this fixed-six vertical without subset selection. See
[`GNSS_ALL_TRACK_GEOMETRY_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_GEOMETRY_SCREEN_REPORT.md).

The independent qualification artifact is now selected, but still unopened:
ALGO00CAN DOY229,
`ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz`. The official BKG index and a HEAD
request confirm its exact name and a 4,317,738-byte content-length hint; these
descriptive fields are not substituted for a future full-file SHA-256. The
frozen scanner contract includes every GPS track, persists no observation
magnitude, requires full-window L1C/L2W with zero LLI breaks and passes only
with exactly six complete opaque tracks. It does not read Doppler or signal
strength fields. DOY230 and DOY231 remain geometry-only candidates with no
primary/reserve role.

The next maximum action requires separate authority to materialize this exact
qualification artifact, verify its complete-file hash before decompression and
run one structural-only scan. A pass permits review of one distinct primary;
a valid structural failure closes the fixed-six path. Materialization or
description errors remain separate from physical topology. See
[`GNSS_ALL_TRACK_QUALIFICATION_PLAN.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_PLAN.md).

The single authorized ALGO DOY229 attempt is now closed as
`QUALIFICATION_DESCRIPTION_ERROR / ANTENNA_TYPE_CHANGED`. It materialized and
hashed the exact `4,317,738`-byte product at
`88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24`
before decompression, then stopped during header admission. No observation
value or artifact byte was persisted, no primary was selected, and neither
the exact-six-track clause nor any orbital score was evaluated.

The failure is attributable to a software description boundary: the common
header helper shaped `ANT # / TYPE` like the receiver's `3A20` record, while
RINEX 3.04 defines the antenna record as `2A20` and carries model plus radome
inside its second field. The failed receipt did not retain the encountered
antenna text, so it cannot assert a real hardware mismatch. The next maximum
action is an offline specification-derived `2A20` parser repair, not another
artifact, primary or gate. A second access to DOY229 would require new explicit
authority after that repair is reviewed. See
[`GNSS_ALL_TRACK_QUALIFICATION_DESCRIPTION_ERROR.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_DESCRIPTION_ERROR.md).

The ordinary parser repair is now frozen offline. `ANT # / TYPE` is read as
RINEX `2A20`, with the IGS antenna type partitioned into A16 model plus A4
radome; receiver `3A20` semantics and historical receipts remain unchanged.
Specification-derived tests cover the two formats and require future mismatch
receipts to retain observed and expected normalized descriptions. The old
outcome remains the execution guard, so the repaired code cannot contact ALGO
or overwrite the terminal receipt. The next maximum action is review of a
distinct non-overwriting retry contract; only separate explicit authority may
permit one new materialization of the same qualification product.

The bounded retry contract is now implemented and frozen offline without a
new gate. It changes only the RINEX antenna-description parser and preserves
the same ALGO DOY229 artifact, exact SHA-256, 139-epoch window, field roles,
LLI rules, opaque membership and exactly-six clause. The first description
error remains an immutable predecessor; the retry has four distinct output
names and cannot overwrite it. The executor verifies its seal before any
network operation and stops after one structural terminal with measurement
admission, orbital scoring and primary selection still `NOT_EVALUATED`.

The next maximum action is review and merge of this offline contract. Only a
later explicit authority can permit the single materialization. A structural
pass would permit review of a distinct primary; it would not select one
automatically. See
[`GNSS_ALL_TRACK_QUALIFICATION_RETRY_PLAN.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_RETRY_PLAN.md).

The authorized retry has now produced a valid structural refusal:
`GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED`. The exact artifact identity,
header and 139-epoch grid were satisfied, but 7 opaque tracks were complete
where the frozen contract required exactly 6. Only after the count failed did
the reveal show the complete set as G05/G11/G15/G18/G20/G21/G29: the intended
six-code family plus G11. No subset may be selected after reveal, and no
measurement or orbital score was evaluated.

This closes the ALGO DOY229 exact-six measurement path. Do not retry it or
search for a convenient count. The next possible information-bearing work is
an offline change-of-abstraction test: determine whether a six-orbit injection
can be discriminated inside an `N >= 6` opaque all-track set with explicit
clutter and equal combinatorial freedom for every null. That alternative is
not yet authorized. See
[`GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME_REPORT.md).

The minimum offline change-of-abstraction test is now positive:
`ALL_TRACK_ONE_CLUTTER_MECHANISM_DISCRIMINATIVE`. Seven anonymous tracks enter;
every possible one-track exclusion and every six-orbit assignment are scored.
Time-reversed geometry receives the same 5,040-hypothesis freedom, and the
affine family receives every exclusion. Positive controls clear the frozen
guard, including a clutter track constructed from an independently frozen
orbital prediction rather than a sinusoid. Removing an expected member while
adding two structured nonmembers is inadmissible. A preferred anonymous score
whose post-hash code witness disagrees is discordant, not confirmed. Exact and
non-identical near-degenerate orbit-like clutter terminate ambiguous.

This proves a synthetic selection mechanism, not a real measurement. The
model was motivated by the consumed seven-track ALGO outcome and therefore
cannot be applied retroactively to it. The next maximum action, only after
review, is to decide whether one independent prospective experiment should
freeze the seven-track/one-clutter topology, code witness, all-exclusion
surface and refusal rules before selecting or accessing a distinct
qualification artifact. No parser work, new geometry search, inventory or
search chain is implied by the spike. See
[`GNSS_ALL_TRACK_CLUTTER_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_ALL_TRACK_CLUTTER_SPIKE_REPORT.md).

The separately reviewed prospective proof now selects DRAO00CAN from the
existing orbit-only scope without any new geometry or receiver search. ALGO is
excluded as consumed and outcome-conditioned; WES retains its signal-product
semantics refusal. DRAO DOY230 is the structural-only qualification geometry
and DOY231 the distinct held-out primary geometry, but both observation
artifacts remain unselected and unopened.

The proof freezes exactly seven opaque tracks, one symmetric exclusion, all
5,040 orbital assignments, 5,040 time-reversed alternatives and seven affine
alternatives. The primary's closest-assignment separation is `49,319.268 m`
and its three-guard lower margin `27,300.164 m`. This does not yet establish a
DRAO physical envelope: the next maximum action is an offline,
outcome-independent bound of the declared timing, propagation, orbit/clock,
antenna and receiver terms on that exact grid. If their aggregate cannot fit
inside `7,339.701 m`, terminate `DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED` before
selecting any product. See
[`GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.md`](experiments/orbital_discriminability/GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.md).
