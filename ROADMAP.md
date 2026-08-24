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

## Current satellite-first forward route: GNSS quotient observable

The Cassini 2005 dual-root route is closed because unresolved absolute-
frequency terms can absorb its controlling held-out separation. The next
physical route is not another receiver search and not a continuation of the
F2.5 gate sequence.

The historical G11/G21 primary and independent qualification are closed. Their
physical mechanism survives, but neither artifact may be reused or rescored.

The current route is the newly selected G14/G17 geometry on DOY 220. It was
chosen from five exact-hash broadcast-navigation days without discovering or
opening any observation product. G22 is the frozen closest wrong-target orbit;
the controlling held-out separation is 403.375 Hz.

The candidate-specific physical envelope has returned a non-positive margin:
-330.379 Hz. The geometry is therefore closed without structural qualification
or observation access. The smallest remaining model-first question is whether
the dominant metre-scale orbit/clock/path intervals can be replaced by
predeclared smooth physical uncertainty families using only outcome-independent
information. Orbit/clock alone has now been shown insufficient even under a
zero-error sensitivity. The next work must compare causally different
observables or observer geometries; until then, no GNSS primary should be
selected.
