# Satellite RF Observatory

An experimental laboratory for testing whether a predicted satellite orbit
leaves an observer-dependent RF structure that survives measurement nuisance
and predicts an independent time interval better than non-orbital alternatives.

The project now follows one satellite-first causal order:

```text
candidate orbit + observer geometry + event time
  -> distributed fractional-Doppler prediction
  -> pass-specific detectability requirement
  -> qualified Internet measurement capability
  -> prospective held-out observation
  -> comparison with frozen non-orbital nulls
```

The orbit determines what an instrument must preserve before an endpoint,
frequency or acquisition window is selected. A connected receiver, a visible
spectral feature or a good fit on calibration data is not by itself evidence
of orbital origin.

This is research software. It is not an operational monitoring platform, a
signal-identification service or evidence that any transmitter has been
identified.

## Current direction

The primary scientific surface is
[`experiments/orbital_discriminability`](experiments/orbital_discriminability/G0_SCOPE.md).
Gate G0 asks offline whether multi-observer orbital geometry is discriminative
at all, before searching for a receiver. Its synthetic map and limits are in
[`G0_IDENTIFIABILITY_REPORT.md`](experiments/orbital_discriminability/G0_IDENTIFIABILITY_REPORT.md).

[`experiments/live_instrument`](experiments/live_instrument/README.md) is a
frozen measurement-integrity layer inherited from Gates B–F2.5. It established
useful controls but no longer chooses the scientific question. Its SatNOGS and
Kiwi branches remain separate historical experiments.

The primitives that survived those branches remain available to the orbital
experiment:

- evaluation by contract clause, not one global health label;
- atomic receipts;
- event time and TTL;
- transform ledger;
- causal lineage;
- separation of physical decisions from descriptive/software errors;
- artifact hashing with zero RF persistence.

They are not promoted to a general framework. Gate G1 must justify each one
against the pass-specific orbital prediction.

## Latest checkpoint

Gate G1 is complete offline. It takes one immutable orbital pass and evaluates
caller-supplied receiver descriptions in two stages: individual observability
qualification, then independent-pair differential detectability. It contains
no discovery or network client and cannot acquire RF.

The reference vertical selects a synthetic Berlin–Eindhoven pair with a
`2807.799 Hz` conservative margin. A fully available local pair is correctly
refused at `-243.201 Hz`; availability therefore cannot masquerade as
falsification power. See
[`G1_ADMISSION_REPORT.md`](experiments/orbital_discriminability/G1_ADMISSION_REPORT.md).

Gate G0 remains the underlying physical result. It samples the existing
stateless orbital kernel for multiple observers, separates fractional geometry
from carrier scaling, fits only station offset and affine drift on a
calibration prefix, and scores the untouched suffix only on jointly visible
station differences. Four non-redundant frozen null families use the same
split, and clock uncertainty is propagated through direct `t ± delta_t`
trajectories rather than a local slope approximation.

The 128-case synthetic sweep contains both detectable and undetectable regions:
81 cases are `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` and 47 are
`ORBITAL_SIGNATURE_BELOW_DETECTABILITY`. This is a mechanism result, not a
claim about a live signal or a satellite identity. G1 now turns that envelope
into an admission procedure, but no current Internet capability has yet been
queried or admitted.

The G1.1–G1.3 inventory/search work is a concluded side investigation, not the
critical path. No global receiver catalog is required.

## Current physical outcome

Several bounded forward routes have now tested the path beyond G1 without
producing an orbital score:

- Berlin–Utrecht OpenWebRX was closed `MEASUREMENT_PATH_INSUFFICIENT` because
  Berlin did not deliver the target profile and Utrecht exposed neither
  server-side frame time nor sample sequence;
- RSP-03 was closed by absolute sample-time provenance;
- MAVEN DSS-45 produced a model-blind development carrier tracker, but only a
  reconstructed date-covering spacecraft SPK is available;
- Cassini produced positive distributed geometry, independent DSN receive
  roots and an X/Ka control at DSS-25, but the tested paths were closed by
  unresolved physical/hardware envelopes or a missing symmetric Ka root;
- the GOLD00USA–NLIB00USA G11/G21 GNSS plan retained a `1420.626 Hz`
  premeasurement physical margin, but its one authorized run stopped
  `MEASUREMENT_INVALID` at `TRUNCATED_REQUIRED_OBSERVATION_RECORD` before any
  calibration or held-out score. A later value-blind forensic repair explained
  the boundary as NLIB G21 `C2W` at `10:06:00 GPS`: header index 5 followed
  only three serialized fields, a RINEX `TRAILING_FIELD_OMITTED` state. The
  historical outcome and closure are unchanged.

No real held-out vertical has therefore reached `MEASUREMENT_VALID` and then
preferred an orbital model over frozen nulls. The GNSS result refuses one exact
measurement path; it is not evidence against G11 or the double-difference
mechanism.

One independent GOLD/NLIB qualification product on DOY 214 was then scanned
structurally without persisting observation values. It failed because NLIB-G21
was absent for the first 27 frozen epochs and reacquired with nonzero LLI; the
longest joint segment contained 358 epochs. A subsequent broadcast-only screen
of DOY 216--220 found no 386-epoch G11/G21 window with the frozen 15-degree
guard and a 30-minute pre-acquisition guard. No new observation artifact or
primary was selected. The unchanged GOLD/NLIB-G11/G21 386-epoch route is now
closed rather than shortened after failure.

Any next GNSS proposal must return to orbit-first comparison and justify a
different geometry or duration from physical discriminability before another
qualification artifact is opened. The smallest demonstrated field family
remains `L1C + L2W` phase with their LLI and epoch continuity, plus same-path
`C1C + C2W`; `S1C/S2W` remain optional diagnostics.

That orbit-first comparison is now complete for the unchanged GOLD/NLIB
stations, 386-epoch duration and DOY 216--220 set. Twenty pair/date cases
survived the 30-minute, four-link 15-degree guard and a meaningful wrong-orbit
null. Exactly one geometry is retained: G14/G17 on DOY 220, 05:07:00--08:19:30
GPS. Its controlling held-out separation is `403.375 Hz` against G22 and its
complete guarded minimum elevation is `23.620 degrees`. No observation product
was discovered or opened.

The candidate-specific envelope is now complete and closes this geometry
before plan freeze. The one-model bound is `366.877 Hz`; the frozen pairwise
comparison bound is `733.754 Hz`, leaving `-330.379 Hz` against G22. Even a
zero broadcast-orbit contribution alone would not make the margin positive.
This is `GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_DOMINATES`, not a negative orbital
measurement. No qualification or observation access is authorized.

A bounded structure audit then checked the strongest plausible objection. The
official GPS `0.006 m/s` URRE statistic and `0.02 m/s` 6-sigma design value
would reduce the pairwise total to 416.782 Hz and 433.806 Hz respectively, but
both remain above G22. The two in-window ephemeris cutovers contribute only
millihertz and do not control the separation. The result is
`GNSS_ORBIT_CLOCK_STRUCTURE_INSUFFICIENT`: further orbit-only refinement is not
the next path.

A bounded SHOCK review has now compared five causally distinct routes. Merely
adding a third GNSS station does not shrink station-local worst-case intervals,
and another raw-separation screen risks repeating the same abstraction
failure. The recommended next mechanism is instead a continuous,
multi-frequency carrier-phase double difference with predeclared LLI,
geometry-free phase and same-path code witnesses. It preserves integrated
orbital structure while avoiding premature finite-difference amplification.

This is not a new candidate or authorization. G14/G17 remains closed and may
serve only as a historical development fixture. The next bounded work is an
offline mechanism spike; only after it survives may a new orbit/station/signal
set be declared and ranked by complete remaining physical margin. See
[`POST_G14_G17_SHOCK_REVIEW.md`](experiments/orbital_discriminability/POST_G14_G17_SHOCK_REVIEW.md).

That spike is now complete. On the closed fixture, G22 remains controlling at
742,458.297 m peak-to-peak while the unchanged conservative pairwise physical
envelope is 23,037.025 m, leaving a 719,421.272 m mechanism margin. The result
is `PHASE_QUOTIENT_MECHANISM_DISCRIMINATIVE`. It demonstrates that preserving
continuous phase avoids the former finite-difference loss; it does not reopen
G14/G17 or authorize observations. The next step is a newly predeclared
phase-coordinate geometry set, screened by full remaining margin before any
observation-product discovery. See
[`GNSS_PHASE_QUOTIENT_SPIKE_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_QUOTIENT_SPIKE_REPORT.md).

The bounded phase-coordinate screen is now complete. After excluding G14 and
G17 from candidate roles and the closed G11/G21 pair, all five remaining
pair/date windows are G22/G30 and have positive physical margin. The distinct-
pair rule retains DOY 220, 04:30:30--07:43:00 GPS: G14 is the controlling
wrong-orbit null at 824,736.025 m, the pairwise envelope is 19,767.924 m and
the remaining margin is 804,968.101 m. This is
`GNSS_PHASE_GEOMETRY_SELECTED`, still with zero observation-product
discovery or access. See
[`GNSS_PHASE_GEOMETRY_SCREEN_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_GEOMETRY_SCREEN_REPORT.md).

The following structural-only contract is now frozen before any observation
product discovery. It predeclares G22/G30 DOY 216 as the independent
qualification geometry and keeps the DOY 220 primary candidate sealed. The
contract can test RINEX field topology, LLI and exact epoch continuity without
retaining values, but explicitly refuses to equate those facts with
geometry-free physical phase health. A structural pass can authorize only a
later health review, never measurement admission or an orbital score. See
[`GNSS_PHASE_STRUCTURAL_CONTRACT.md`](experiments/orbital_discriminability/GNSS_PHASE_STRUCTURAL_CONTRACT.md).

The authorized DOY 216 value-blind qualification has now returned
`GNSS_PHASE_STRUCTURE_REJECTED`. GOLD preserved the complete G22/G30 phase and
code topology, but NLIB did not: the longest four-link joint segment contains
282 rather than the frozen 386 epochs, and three NLIB code-witness links fail
the predeclared coverage/boundary rule. No phase scalar was parsed and the DOY
220 primary remains sealed. See
[`GNSS_PHASE_STRUCTURE_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_STRUCTURE_REPORT.md).

The subsequent offline change-of-abstraction calculation did not reopen that
artifact. Using only exact-hash broadcast navigation on four other unopened
dates, it found `PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE`: all four dates
retain positive complete phase margin with a 60-epoch (30-minute) held-out
suffix and a 139-epoch raw interval. The worst remaining margin is
6,473.198 m, while the maximum four-link elevation guard rises from 15.616 deg
at the old duration to 39.467 deg. No RINEX product was discovered or opened,
and no new roles were assigned. See
[`GNSS_PHASE_DURATION_SENSITIVITY_REPORT.md`](experiments/orbital_discriminability/GNSS_PHASE_DURATION_SENSITIVITY_REPORT.md).

The distinct roles are now frozen before product discovery. DOY 217,
05:54:00--07:03:00 GPS is the sole qualification date; DOY 220,
05:42:00--06:51:00 GPS is the sealed held-out primary. The 139-epoch plan
keeps the ionosphere-free continuous-phase coordinate, 77/60 prefix/holdout
split, the prefix-affine null and G01/G14/G17 alternative orbits. A
qualification failure authorizes no substitute date, and primary access still
requires a separate review. See
[`GNSS_PHASE_SHORT_WINDOW_PLAN.md`](experiments/orbital_discriminability/GNSS_PHASE_SHORT_WINDOW_PLAN.md).

## Preserved Gate F2.5 experimental history

Gate F2.5 removed server waterfall (`W/F`) and `ext_api` from the causal gate
for same-Kiwi multichannel qualification. Its intended path is:

```text
frozen affordances
  -> direct simultaneous SND reference + perturbed attempt
  -> two IQ streams
  -> local in-memory STFT/PSD
  -> targetless feature + witness
  -> per-channel retune qualification
  -> immutable plan
  -> one prospective A1/B/A2 confirmation
  -> one outcome
```

The first and only live F2.5 execution ended correctly as
`QUALIFICATION_INCOMPLETE`: all six `/status` requests succeeded, but the
frozen center policy expected a `bandwidth` field that the responses did not
contain. No SND channel was attempted, no IQ was acquired and
`NO_MULTI_CHANNEL_CAPABILITY` was therefore forbidden. See
[`GATE_F2_5_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_OUTCOME_1.md).

Gate F2.5.1 now removes that last pre-SND dependency offline. It freezes a
conservative Kiwi-family tuning interval and derives a qualification-only
coordinate without reading `status.bandwidth`; W/F remains absent and
`ext_api` remains a hint. The original outcome is unchanged, and no live
connection was made while preparing that offline checkpoint. See
[`GATE_F2_5_1_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_1_OFFLINE.md).

The single authorised F2.5.1 live session then reached real dual-SND attempts
on every frozen candidate. One endpoint explicitly rejected public SND access;
the others remained indeterminate after WebSocket timeout/closure errors. The
terminal result is `QUALIFICATION_INCOMPLETE`, not a claim that multichannel
capability is absent. No topology, feature, plan or DDC hypothesis was
admitted. See
[`GATE_F2_5_1_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_1_OUTCOME_1.md).

Gate F2.5.2 addresses that outcome strictly offline. It records reference and
perturbed opening as separate atomic receipts, hashes every ephemeral SND
frame before decode, and preserves any single-branch readiness witness even
when the peer fails. It does not change the candidates, tuning policy,
thresholds or DDC question, and no new live connection has been made. See
[`GATE_F2_5_2_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_2_OFFLINE.md).

The single F2.5.2 live session ended as `QUALIFICATION_INCOMPLETE`, but its
atomic boundary exposed a real asymmetric result: one KFS reference branch
reached GNSS IQ readiness with two pre-decode-hashed frames while its perturbed
peer was explicitly rejected. No pair or DDC hypothesis was admitted. The run
also exposed two descriptive-control failures: retry eligibility still
depended on aggregate prose, and stdout-only receipts were not fully retained.
See
[`GATE_F2_5_2_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_2_OUTCOME_1.md).

Gate F2.5.3 corrects those two control failures offline. Retry eligibility now
comes only from atomic branch state and typed transport errors; aggregate prose
cannot enable or disable it. A future session writes one bounded,
exclusive-create, strict-JSONL artifact containing descriptive receipts and
hashes while rejecting RF arrays and raw/derived sample fields. Sink or
serialization failure is descriptive and cannot alter the physical result.
No live connection was made. See
[`GATE_F2_5_3_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_3_OFFLINE.md).

The pre-execution review found that F2.5.3's final artifact hash and emission
errors were returned in memory but discarded by its command-line entry point.
Gate F2.5.3.1 closes that final audit gap offline: the same JSONL ends with a
reserved terminal manifest containing a byte-exact prefix hash and retention
state, while the CLI exposes the closed file's overall hash. Runtime,
serialization and mirror failures remain descriptive. No network activity was
performed. See
[`GATE_F2_5_3_1_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_3_1_OFFLINE.md).

The single authorised F2.5.3.1 session then exercised all six frozen
candidates and exactly the two allowed structured retries. No branch delivered
an IQ frame: explicit branch rejections coexisted with transport closures or a
timeout, so the correct outcome is `QUALIFICATION_INCOMPLETE`, not absence of
multichannel capability. No topology, feature, plan or DDC hypothesis was
evaluated. The 53-line receipt artifact closed `COMPLETE`, with matching prefix
and whole-file hashes and zero RF persistence. See
[`GATE_F2_5_3_1_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_3_1_OUTCOME_1.md).

Gate F2.5.4 audits that frozen outcome without network activity. Four branch
receipts are explicit server-reported rejections, one is a timeout before any
server MSG, and eleven are not causally diagnosable from the retained fields.
In particular, `configuration_sent` records a local action, not remote
acceptance. Because all endpoints share one client implementation root and the
official frozen source revisions are not present locally, the correct exit is
`STOP_PENDING_CONTROL_DISCRIMINATORS`, not a protocol fix or another run. See
[`GATE_F2_5_4_PROTOCOL_AUDIT.md`](experiments/live_instrument/GATE_F2_5_4_PROTOCOL_AUDIT.md).

Gate F2.5.5 now specifies the missing control boundary offline. It keeps an
official-source clause separate from the ordered receipt clause, distinguishes
local command result, remote server field, WebSocket close, TCP loss and first
IQ, and forbids credentials or RF persistence. Because the pinned official
source artifacts and exact kiwiclient control path are not retained locally,
it fails closed as `SOURCE_BASIS_INCOMPLETE`; no implementation or live run is
authorised. See
[`GATE_F2_5_5_OFFLINE.md`](experiments/live_instrument/GATE_F2_5_5_OFFLINE.md).

Gate F2.5.6 then retrieved only the two official repositories at their frozen
commits; it made no Kiwi connection and acquired no RF. The minimal server
source is now retained and verified byte-for-byte. The exact kiwiclient paths
are resolved and hash-audited, but its source is not copied because no license
grant was found at the pinned revision. The correct fail-closed result is
`SOURCE_RETENTION_BLOCKED_BY_LICENSE`: protocol semantics are narrower and
better grounded, while the complete source basis is still not locally
reproducible. See
[`GATE_F2_5_6_SOURCE_REPRODUCTION.md`](experiments/live_instrument/GATE_F2_5_6_SOURCE_REPRODUCTION.md).

Gate F2.5.7 audits whether that client-retention limit actually blocks the
physical question. It does not: server semantics, ordered local sends and a
later hashed IQ witness are sufficient, while the reference client cannot
manufacture a configuration ACK the protocol does not expose. Synthetic
transcripts now distinguish auth, channel allocation, local `mod_iq`, IQ,
clean close and transport loss. The offline result is
`SERVER_WIRE_CONTRACT_SUFFICIENT`; receipt implementation may be prepared in a
separate gate, but no live execution is authorised. See
[`GATE_F2_5_7_SERVER_WIRE_AUDIT.md`](experiments/live_instrument/GATE_F2_5_7_SERVER_WIRE_AUDIT.md).

Gate F2.5.8 now integrates that contract in a new local successor path. It
preserves ordered allowlisted MSG fields, reads the real channel number from
`is_local`, delays `mod_iq` until auth/channel/rate are all witnessed, and
hashes the first qualifying IQ frame before decode. Local send errors,
control timeouts, close frames and transport loss remain distinct. All tests
use synthetic WebSocket frames; no endpoint was contacted. The result is
`ORDERED_WIRE_RECEIPT_IMPLEMENTED`, still with no live authorization. See
[`GATE_F2_5_8_ORDERED_RECEIPT.md`](experiments/live_instrument/GATE_F2_5_8_ORDERED_RECEIPT.md).

Gate F2.5.9 completes the offline pre-live composition review. The disposable
one-shot wrapper now injects only the ordered F2.5.8 opener, maps atomic receipt
states without parsing aggregate exception prose, retains typed pre-freeze
retry and terminal JSONL closure, and preserves the first-outcome stop. Calls
without a separate live authority fail before artifact creation or network
entry. No live execution occurred. See
[`GATE_F2_5_9_PRELIVE_RUNNER.md`](experiments/live_instrument/GATE_F2_5_9_PRELIVE_RUNNER.md).

Gate F2.5.10 freezes the exact execution envelope around that runner. A narrow
authority shim removes caller overrides for plan, receipt path and runtime
commit, verifies the reviewed causal sources and numerical environment, writes
the envelope as the first terminal-artifact receipt, and then invokes only the
F2.5.9 qualifier/retry path. Candidate order, targetless centers, timing, retry
and the first-outcome stop are explicit. The offline exit is
`REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY`; no Kiwi network activity was
performed or authorised. See
[`GATE_F2_5_10_EXECUTION_REVIEW.md`](experiments/live_instrument/GATE_F2_5_10_EXECUTION_REVIEW.md).

The single separately authorised Gate F2.5.10 run has now materialised that
envelope and stopped `QUALIFICATION_INCOMPLETE`. All six candidates received a
simultaneous dual-SND attempt; four branches returned explicit `badp`
rejections and eight reached channel allocation plus local `mod_iq` before an
observed close without a qualifying IQ-readiness event. No retry, discovery,
plan freeze or confirmation occurred. The 46-line terminal artifact is
complete and contains no persisted RF. See
[`GATE_F2_5_10_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_10_OUTCOME_1.md).

## What can be claimed

Receipts may support narrow statements such as:

- a measurement satisfied a named clause before its TTL expired;
- two SND streams were simultaneous and independently sequenced;
- a feature behaved consistently with being upstream of a per-channel DDC;
- an observation was unavailable, unresolved, not detectable or not evaluated.

They do **not** automatically support:

- transmitter or satellite identity;
- external-RF origin;
- common physical cause;
- geolocation or TDoA;
- absence of a phenomenon when detectability was not established;
- multichannel unavailability when a second channel was never attempted.

## Quick start: offline verification

Python 3.11 or 3.12 is recommended.

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r requirements-live-instrument.txt
python -m pytest experiments/live_instrument/tests -q
```

The test suite is offline. It uses deterministic fixtures and synthetic IQ;
it does not contact SatNOGS, KiwiSDR or any other remote service.

## Live execution policy

Live runners are disposable experiment materializations, not daemons.

- Never run them as part of installation, import, tests or CI.
- Freeze candidates, order, transforms, thresholds, retry budget and stop
  condition before network access.
- Use only public capabilities and respect receiver-owner access limits.
- Retry only pre-freeze software/transport failures allowed by the frozen plan.
- After plan freeze: zero retry, endpoint change, frequency change, threshold
  change or second confirmation window.
- Hash ephemeral RF artifacts before analysis and destruction; persist only
  strict JSON receipts and hashes.

Every new live session requires explicit authorization. The repository's
documented outcomes must remain unchanged after the fact; fixes belong to a
new gate and a new commit.

The latest offline materialization is Gate F2.5.14: two injected semantic SND
branches are composed concurrently, evaluated by explicit topology clauses and
fed through the frozen candidate order to one terminal receipt. Its envelope
still requires post-commit causal-source review; it is not live authority.

Gate F2.5.15 now supplies that offline post-commit seal and a boolean-only
authority surface. It is ready to be reviewed for a separate exact live
authorization, but importing, assessing, testing or committing it performs no
network activity.

The single F2.5.15 authority has since been consumed. Its frozen outcome is
`QUALIFICATION_INCOMPLETE`: all candidates were attempted without retry, four
branches were explicitly rejected, eight closed after allocation without any
SND frame, and no dual-IQ pair was admitted. No cause is assigned to the empty
peer closes.

Gate F2.5.16 attributes that outcome offline. Ordered command hashes show that
all eight allocated branches emitted 15 or 16 keepalives before `AR OK`; the
pinned server source increments that count and contains an incomplete-setup
removal predicate above four. This falsifies the local assumption that
keepalive was neutral during setup, but it does not identify the live peer's
close cause: remote revision, command receipt, setup mask and close reason were
not observed. Physical dual-SND capability remains `NOT_EVALUATED`.

Gate F2.5.17 closes the missing source definition and repairs only that local
control defect. The pinned `CMD_SND_ALL` mask requires frequency, mode,
passband, AGC and `AR OK`. The successor waits for every required metadata
field, emits the complete setup exactly once, and permits a time-paced
keepalive only afterwards. Its receipt distinguishes local emission from the
still-unobservable remote setup state. The implementation is synthetic-only,
has no live connector and grants no acquisition authority.

Gate F2.5.18 composes two corrected branches concurrently, preserves the
same-Kiwi channel/connection/sequence/event-time topology clauses and runs the
unchanged candidate order into one terminal receipt. Both retry budgets remain
zero; status and waterfall remain outside the direct-SND admission path. The
module still requires injected connectors and post-commit review, so it cannot
contact a receiver or claim live authority.

Gate F2.5.19 seals the resulting commit, 21-file causal allowlist, numerical
environment and exact dual execution surface. Its only public control is
`run_reviewed_once(live_authorised=False)`; default refusal occurs before
receipt or connector access. The maximum future scope is one corrected
dual-SND qualification, stopping before discovery, retune or observation. The
seal is ready for a separate commit-specific authority but does not imply one.

That separate authority has now been consumed exactly once. The first frozen
candidate supplied two simultaneous semantic SND/IQ streams on distinct server
channels with distinct receipts and overlapping GNSS event time, yielding
`DUAL_SEMANTIC_PAIR_READY`. The run stopped immediately, persisted no RF and
did not perform feature discovery, retune or A1/B/A2. This qualifies the
same-Kiwi multichannel topology only; it does not yet support a physical-signal
or upstream/downstream claim. See
[`GATE_F2_5_19_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_19_OUTCOME_1.md).

Gate F2.5.20 now composes that exact qualified endpoint with the already tested
prospective vertical, still entirely offline. The old readiness frames select
the capability but cannot satisfy future admission: corrected dual SND must be
requalified in the same session, followed by a new ephemeral discovery,
witness-only retune qualification, immutable freeze and exactly one independent
A1/B/A2. Thresholds are unchanged, both retry budgets are zero and the module
has no live surface pending a separate post-commit seal. See
[`GATE_F2_5_20_PROSPECTIVE_VERTICAL.md`](experiments/live_instrument/GATE_F2_5_20_PROSPECTIVE_VERTICAL.md).

Gate F2.5.21 supplies the required post-commit seal. It binds the reviewed
F2.5.20 commit, 22 causal files including the retained protocol artifacts, the
numerical environment, prospective control surface and live-wrapper source.
The sole control was `run_reviewed_once(live_authorised=False)` and its default
refusal occurred before receipt or connector access. See
[`GATE_F2_5_21_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_21_POST_COMMIT_SEAL.md).

That authority has now been consumed exactly once. Same-session direct SND
again admitted two simultaneous IQ channels, but the independent four-second
local discovery produced fewer than two distinct stable structures. The
terminal outcome is `NO_FALSIFIABLE_INTERVENTION`: no retune occurred, no plan
was frozen, no A1/B/A2 was run and neither DDC-boundary hypothesis was
evaluated. The strict receipt is complete with zero RF persistence. This is a
valid refusal to synthesize an experiment, not evidence that the passband
contained no signal. See
[`GATE_F2_5_21_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_21_OUTCOME_1.md).

Gate F2.5.22 audits that failure without new data. The frozen discovery receipt
contains only the error-description hash, not the two ephemeral input hashes,
candidate counts or threshold margins, so the underlying reason for “fewer
than two structures” is not attributable. The audit also finds that legacy
peak widths can be inflated by the admission mask sentinel. A synthetic-only
alternative keeps the orthogonal-witness requirement but removes the needless
assumption that it must be a second narrowband peak: a target-excluded
distributed spectral fingerprint, fixed reference branch, unique perturbed
translation and A2 return can qualify the DDC coordinate transform. No live
capability or target physics is thereby qualified. See
[`GATE_F2_5_22_DISCOVERABILITY_AUDIT.md`](experiments/live_instrument/GATE_F2_5_22_DISCOVERABILITY_AUDIT.md).

Gate F2.5.23 integrates that result into an offline successor. Injected
phase-aware sockets establish the dual-channel topology; one stable target is
then sufficient because a target-excluded distributed fingerprint separately
qualifies the retune. Deterministic tests prove that changing the target at all
predeclared control positions cannot change witness state, orientation or
scores. The successor freezes distinct upstream/channel-fixed predictions,
negative controls, one future confirmation and zero retry. It still has no
connector or authority. See
[`GATE_F2_5_23_ONE_TARGET_SUCCESSOR.md`](experiments/live_instrument/GATE_F2_5_23_ONE_TARGET_SUCCESSOR.md).

Gate F2.5.24 now implements the missing confirmation evaluator offline. Before
examining the target it requires six distinct post-freeze artifacts, an exact
channel/tune ledger, continuous event-time streams and a uniquely translating
target-excluded distributed witness. Deterministic fixtures reach all five
frozen outcomes without changing the plan and prove that invalid intervention
clauses block target evaluation, while lost target detectability remains a
separate `NOT_DETECTABLE` result. The evaluator has no connector, live runner
or execution authority and persists no RF. See
[`GATE_F2_5_24_CONFIRMATION_EVALUATOR.md`](experiments/live_instrument/GATE_F2_5_24_CONFIRMATION_EVALUATOR.md).

Gate F2.5.25 supplies the post-commit seal and the only authority-facing
composition. It binds F2.5.24, all causal source hashes, the numerical
environment and the complete live surface. The composition keeps the same two
SND channels open from requalification through the only confirmation, closes
the diagnostic command ledger before confirmation, and always attempts channel
closure afterward. Its sole public argument is a default-false authority bit.
The seal was built and tested offline; it grants and consumes no live
authority. See
[`GATE_F2_5_25_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_25_POST_COMMIT_SEAL.md).

That authority has now been consumed once. The endpoint allocated two channels
and delivered hundreds of decodable IQ/SND frames, but none supplied an
admissible event-time witness: GPS solution age was 92–103 seconds against the
frozen 30-second maximum. The terminal outcome is
`QUALIFICATION_INCOMPLETE`; discovery, retune, plan freeze and confirmation are
all `NOT_EVALUATED`. This is not evidence that no signal or multichannel
capability existed. It demonstrates that data availability and measurement
admissibility are separate clauses. See
[`GATE_F2_5_25_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_25_OUTCOME_1.md).

Gate F2.5.26 attributes that failure offline. The pinned server source confirms
that the recorded field is elapsed seconds since the latest GPS position
solution, while the receipt proves both transports and decoders remained
active. The timeout was a consequence of the frozen temporal clause, not the
absence of SND/IQ. Absolute fresh GNSS was not explicitly derived from the
same-ADC DDC hypothesis, but the receipt lacks the arrival, sample-clock and
command-boundary statistics needed to test a relative-time alternative. The
old outcome therefore remains unchanged and the alternative is
`NOT_FALSIFIABLE_WITH_THIS_RECEIPT`. See
[`GATE_F2_5_26_TEMPORAL_FAILURE_ATTRIBUTION.md`](experiments/live_instrument/GATE_F2_5_26_TEMPORAL_FAILURE_ATTRIBUTION.md).

Gate F2.5.27 now materialises that new temporal contract offline. It does not
relax the consumed run: the new causal cut requires actual server timestamps,
sample counts and monotonic arrivals that the old receipt did not preserve.
For a future same-ADC trial, timestamp steps must close against sample geometry
within one sample, channel sequences must remain contiguous, reserved server
clock states are refused, and the two streams must overlap for at least two
existing STFT windows. Absolute GNSS freshness is explicitly `NOT_REQUIRED`
for this cut, while command boundaries receive independent scalar witnesses.
No connector or authority has been added. See
[`GATE_F2_5_27_RELATIVE_TIME_ADMISSION.md`](experiments/live_instrument/GATE_F2_5_27_RELATIVE_TIME_ADMISSION.md).

Gate F2.5.28 integrates that contract into an injected one-shot path. Every SND
artifact is hashed before decode, the temporal receipt controls whether
read-only in-RAM IQ can reach discovery, discovery controls retune access, and
retune qualification requires both A1→B and B→A2 boundary witnesses. All IQ
arrays are overwritten and verified in `finally`; the returned result contains
only strict scalar/hash receipts. Tests measure zero downstream callback calls
on temporal failure. The exact parser, one-shot surfaces, parent sources and
numerical environment are sealed, but no connector or live authority is
present. See
[`GATE_F2_5_28_INJECTED_ONE_SHOT.md`](experiments/live_instrument/GATE_F2_5_28_INJECTED_ONE_SHOT.md).

Gate F2.5.29 now supplies the missing phase-aware transport boundary, still
entirely offline. Two injected SND branches execute the exact
auth → metadata → one-shot setup → SND order concurrently. Each transport
frame transfers through an explicit byte lease, its artifact is hashed, and
the lease is released before analysis; bounded SND copies are cleared after
the F2.5.28 call while decoded IQ is zeroized by that parent gate. The wrapper
does not reuse the obsolete absolute-age rejection: distinct channels,
same-clock continuity and relative overlap decide access. No connector, public
runtime override or live authority exists. See
[`GATE_F2_5_29_PHASE_AWARE_INJECTED_BRIDGE.md`](experiments/live_instrument/GATE_F2_5_29_PHASE_AWARE_INJECTED_BRIDGE.md).

Gate F2.5.30 audits whether that bridge can honestly receive a live authority
bit. It cannot yet: both collectors close their channel sockets before the
F2.5.28 discovery and retune callbacks run, and those callbacks receive no
control handle. Commit, source and envelope seals all pass, so the terminal
result is `LIVE_SURFACE_NOT_SEALABLE`, not a qualification or capability
failure. The relative-time work remains reusable, but no nominal live runner
was created. See
[`GATE_F2_5_30_SEALABILITY_AUDIT.md`](experiments/live_instrument/GATE_F2_5_30_SEALABILITY_AUDIT.md).

Gate F2.5.31 repairs that lifetime exclusively with injected sockets. One
outer owner keeps the two admitted handles open through local A1 discovery and
both A1→B→A2 command boundaries; only a private executor can tune the
perturbed branch. Settling frames remain in the full sequence-continuity
ledger, while all IQ and both handles are released in the outer `finally`.
The result still leaves RF response and DDC-location hypotheses
`NOT_EVALUATED`: command topology is now valid, but it is not a substitute for
the distributed RF-structure witness. See
[`GATE_F2_5_31_OPEN_HANDLE_SUCCESSOR.md`](experiments/live_instrument/GATE_F2_5_31_OPEN_HANDLE_SUCCESSOR.md).

Gate F2.5.32 closes the remaining offline RF-response integration cut. The
existing distributed witness first excludes every target/control position and
must show a fixed reference, one unique perturbed translation and an A2 return.
Only then are target predictions hashed and B/A2 target matching allowed. The
synthetic suite distinguishes `INTERVENTION_INVALID`, `NOT_DETECTABLE`, both
directional DDC hypotheses and `AMBIGUOUS` without changing thresholds. All IQ
is still ephemeral and no live authority exists. See
[`GATE_F2_5_32_RF_RESPONSE_INTEGRATION.md`](experiments/live_instrument/GATE_F2_5_32_RF_RESPONSE_INTEGRATION.md).

Gate F2.5.33 now seals that exact commit and execution surface. The only
live-capable signature contains one keyword-only `live_authorised=False` bit;
default refusal occurs before assessment, receipt creation or connector
access. The endpoint, dual-channel topology, control geometry, thresholds,
receipt path, zero-retry rule and one-outcome stop are not caller parameters.
The assessment is offline and no authority has been consumed. See
[`GATE_F2_5_33_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_33_POST_COMMIT_SEAL.md).

The single Gate F2.5.33 authority has now been consumed. Two simultaneous
same-clock SND/IQ channels and relative temporal admission succeeded, but the
unchanged A1 discovery admitted no common feature. The run therefore stopped
`NO_FALSIFIABLE_INTERVENTION` before retune, plan freeze or physical-hypothesis
evaluation. This is not evidence that the passband contained no signals. See
[`GATE_F2_5_33_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_33_OUTCOME_1.md).

Gate F2.5.34 attributes that negative using only the committed receipt and
source seals. The dual-channel measurement and spectral transform were
operational, and the complete frozen feature rule was unsatisfied. The
receipt does not retain peak counts, per-stage rejection counts or threshold
margins, so contrast, patch validity, correlation and half-window stability
remain indistinguishable. The physical DDC hypothesis is still
`NOT_FALSIFIABLE_WITH_THIS_RECEIPT`. A prior scalar audit already contains the
needed descriptive shape, so no new framework or selector change is proposed.
See
[`GATE_F2_5_34_DISCOVERY_FAILURE_ATTRIBUTION.md`](experiments/live_instrument/GATE_F2_5_34_DISCOVERY_FAILURE_ATTRIBUTION.md).

Gate F2.5.35 integrates the minimum future repair offline without touching the
frozen runtime. The unchanged one-feature selector first emits its
authoritative `DiscoveryReceipt`; a sibling scalar audit then records stage
counts and finite threshold margins against the same 16 pre-analysis frame
hashes. Audit construction failure becomes `DESCRIPTION_ERROR` and cannot
change selection, retune control flow or physical outcome. Synthetic negative
and positive full-vertical tests preserve the F2.5.32 decisions, while no IQ,
STFT, spectrum or candidate patch persists. See
[`GATE_F2_5_35_SCALAR_AUDIT_INTEGRATION.md`](experiments/live_instrument/GATE_F2_5_35_SCALAR_AUDIT_INTEGRATION.md).

Gate F2.5.36 seals that exact committed successor offline. The F2.5.35 source,
inherited plan, decision/audit and full integration surfaces, reviewed dual-SND
connector, numerical environment, endpoint, zero-retry policy and strict
receipt shape are hash-bound. The sole public execution signature exposes
only `live_authorised=False`, and default refusal precedes assessment, receipt
creation and connector access. No authority is granted or consumed. See
[`GATE_F2_5_36_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_36_POST_COMMIT_SEAL.md).

The single Gate F2.5.36 authority has now been consumed. Two simultaneous SND
channels passed relative-time admission and the unchanged selector admitted a
common feature with positive contrast, correlation and half-stability margins.
Both retune boundaries were witnessed, but the final session-continuity check
stopped `INTERVENTION_INVALID`, leaving both physical hypotheses
`NOT_EVALUATED`. Receipt-only reconstruction exactly attributes its one
violation per branch to a software evaluator that included the already counted
leading-zero timestamp. The frozen live outcome is not evidence of a remote
clock jump or of either DDC-location hypothesis. See
[`GATE_F2_5_36_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_36_OUTCOME_1.md).

Gate F2.5.37 repairs only that duplicated timestamp semantics offline. The
full-session evaluator reuses the existing F2.5.27 leading-zero and GPS-week
normalization, retains every prior sequence/tolerance/receipt rule and leaves
the frozen F2.5.31–36 sources untouched. Deterministic tests reproduce the
exact live residual, reject interior zeros, preserve rollover and show the
corrected synthetic vertical passing beyond the former false block. No live
claim, connector or authority is added. See
[`GATE_F2_5_37_CONTINUITY_NORMALIZATION.md`](experiments/live_instrument/GATE_F2_5_37_CONTINUITY_NORMALIZATION.md).

Gate F2.5.38 now seals that corrected vertical offline. The F2.5.37 commit,
source, plan, continuity evaluator, temporary installation scope, integration,
reviewed dual-SND connector, numerical environment, strict receipt and full
live surface are hash-bound. The sole public execution signature contains only
`live_authorised=False`, and its default refusal precedes every side effect.
No network activity or authority consumption occurs. See
[`GATE_F2_5_38_POST_COMMIT_SEAL.md`](experiments/live_instrument/GATE_F2_5_38_POST_COMMIT_SEAL.md).

The separately authorised Gate F2.5.38 execution has now consumed that surface
once, with zero retry. Two simultaneous SND/IQ channels and the corrected
relative-time clauses passed. Local discovery then stopped
`NO_FALSIFIABLE_INTERVENTION`: five complete candidates were evaluated, four
passed the frozen correlation threshold, and none passed the unchanged
minimum contrast in both temporal halves. No retune was emitted and both DDC
hypotheses remain `NOT_EVALUATED`. The receipt contains scalar decisions and
hashes only; RF persistence is zero. See
[`GATE_F2_5_38_OUTCOME_1.md`](experiments/live_instrument/GATE_F2_5_38_OUTCOME_1.md).

## Repository map

```text
experiments/orbital_discriminability/
  trajectory.py             synchronized orbital observables and envelopes
  nuisance.py               calibration-only nuisance projection
  null_models.py            frozen non-orbital and geometry-breaking nulls
  heldout.py                immutable plan and outcome semantics
  synthetic.py              deterministic discriminability sweep
  g1_admission.py            pass-specific receiver-pair admission
  g1_synthetic.py            offline admission/refusal verticals
  G0_*.md, G1_*.md           scope, evidence, limits and next boundaries
  tests/                    offline orbital-mechanism test suite

experiments/live_instrument/
  models.py                 strict receipts, clause and JSON boundary
  orbital_kernel.py         stateless Skyfield geometry/Doppler kernel
  satnogs_probe.py          model-conditioned published artifacts
  satnogs_failover.py       clause-driven continuity/corroboration failover
  kiwi_probe.py             targetless dual-Kiwi capture and in-session nulls
  kiwi_prospective.py       discovery/prediction/confirmation separation
  kiwi_gate_e.py            detectability and qualification experiments
  kiwi_gate_f2*.py          capability-first and same-Kiwi DDC interventions
  tests/                     offline deterministic test suite
  CHECKPOINT_*.md            checkpoint evidence
  GATE_*.md                  frozen plans, outcomes and postmortems

analysis/, collectors/, processors/, trackers/
  original offline satellite prototype, retained for reference

api/, workers/, core/, receivers/
  legacy architecture retained for reference; not the supported path
```

For mechanisms and state semantics, read
[`README_TECHNICAL.md`](README_TECHNICAL.md). For the next bounded work, read
[`ROADMAP.md`](ROADMAP.md).

## Original proof of concept

![Early map-based interface proof of concept](docs/images/sis-proof-of-concept.webp)

The image records the original product exploration. Its labels, confidence,
locations and events are demonstration output, not validated telemetry or
satellite identifications. No supported frontend is currently included.

## Legacy offline prototype

The original SDR-to-disk and satellite-candidate code remains available through
`gray_system_main.py`. It is exploratory and is not the validated output of
the live-instrument gates. In particular:

- encryption and secure export are not implemented;
- metadata-scrubbed captures are incompatible with the current reader;
- Doppler proximity is candidate ranking, not identification;
- old API, Redis, PostgreSQL and frontend documents are historical.

## Legal and ethical use

Use this repository only for lawful education, amateur-radio experimentation,
spectrum research and signals you are authorized to receive and process. It
does not transmit, jam, decrypt or bypass access controls. Public receiver
availability is not a blanket license to record or redistribute content.
Operators are responsible for applicable radio, privacy and data-retention law.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
