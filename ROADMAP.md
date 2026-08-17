# Roadmap: the next falsifiable vertical experiment

This roadmap is intentionally narrow. It replaces the former feature roadmap,
which assumed a satellite-identification product before the measurement and
detectability mechanisms were established.

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

- Run the offline live-instrument suite on pushes and pull requests.
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
