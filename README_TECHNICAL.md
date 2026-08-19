# Technical model: orbital prediction over a bounded measurement substrate

This document describes an experimental mechanism, not a permanent platform
architecture.

## 0. Scientific layer and measurement layer

The repository now has two deliberately ordered layers:

```text
experiments/orbital_discriminability
  orbit -> observer-specific prediction -> detectability -> held-out null test
                              |
                              v
experiments/live_instrument
  event-time measurement -> transform ledger -> atomic evidence -> receipt
```

`orbital_discriminability` owns the scientific prediction. It uses the
stateless orbital kernel, derives fractional Doppler before applying a carrier,
forms simultaneous station differences, fits bounded nuisance only on a
calibration prefix and evaluates an untouched suffix against frozen nulls.

`live_instrument` is the frozen measurement-integrity substrate established by
Gates B–F2.5. It does not select an endpoint, frequency, feature or target for
the orbital experiment. A future capability enters only when a propagated
pass shows that the capability can preserve a discriminative orbital feature.

The current Gate G0 is entirely offline. Its scope and numerical limits are in
`experiments/orbital_discriminability/G0_SCOPE.md` and
`experiments/orbital_discriminability/G0_IDENTIFIABILITY_REPORT.md`.

Gate G1 adds a narrow admission boundary. An `OrbitalPassPlan` is propagated
before any offer is considered. Each descriptive offer must first satisfy its
own time, band, continuity, transform and witness clauses; only then may a pair
be tested for distinct hardware roots, joint visibility and positive
differential margin. The synthetic result is not a live capability claim. See
`experiments/orbital_discriminability/G1_ADMISSION_REPORT.md`.

Gate G1.1 tested the descriptive boundary once. Model metadata materialized,
but the capability inventory required interactive authorization. The correct
state is `CAPABILITY_DISCOVERY_UNAVAILABLE`: downstream endpoint,
qualification, pair and RF clauses remain `NOT_EVALUATED`. An interactive web
listing is not treated as a machine-readable capability offer.

Gate G1.2 makes the upstream selection boundary explicit. An inventory
mechanism must have operator-bound authority, documented automation intent, a
non-interactive bounded schema, hash-before-parse integrity, finite TTL,
declared complete scope and a deterministic endpoint-set hash. Only hashes and
scalar receipts persist. The mechanism may expose an ephemeral candidate set
to later `/status` qualification; it cannot itself admit a receiver.

The frozen G1.1 artifact and remembered endpoints fail this boundary. HTTPS
manifest and authoritative-DNS fixtures pass only as contract forms, not as
live sources. No adapter, registry or persistent capability catalog is added.

The sections below preserve the live-instrument mechanism because its controls
remain candidate primitives for G1. They are not automatically a framework.

## 1. The unit of work

The current experiment begins with an orbital prediction, not a source
adapter or an opportunistic RF feature:

```text
determine whether one candidate orbit predicts observer-coupled RF structure
that a qualified Internet measurement set can falsifiably test
```

A capability is useful only when the propagated pass predicts a signal margin
that its event time, frequency geometry, continuity and transforms can
preserve. Information gain or receiver availability alone is insufficient.

```text
candidate orbit
  -> observer-relative range rate
  -> fractional and differential Doppler
  -> sensor capability
  -> conditioning transforms
  -> held-out orbital-versus-null outcome
```

Before freeze, unknown quantities may be bounded, learned or cause admission
to fail. After freeze, feature definitions, transforms, controls and decision
regions cannot change.

## 2. State is clause-local

One global `OBSERVABLE/DEGRADED` label was rejected because it conflated
available measurements with support for a causal hypothesis.

The experiments instead distinguish:

| State | Meaning |
|---|---|
| `SATISFIED` | the receipt supports this clause under its frozen transform and TTL |
| `UNSATISFIED` | the clause was evaluated and its condition failed |
| `UNRESOLVED` | measurements exist, but they do not distinguish the causal alternatives |
| `UNOBSERVABLE` | the required measurement is unavailable or expired |
| `NOT_EVALUATED` | an upstream admission/precondition blocked evaluation |
| `QUALIFICATION_ERROR` | software, transport or description failed; no physical rejection follows |
| `CAPABILITY_REJECTED` | an explicit access or physical admission condition failed |

`MODEL_AVAILABLE` is separate. A propagable orbit does not satisfy an
observation clause.

## 3. Atomic receipts and TTL

One receipt represents one evidence-producing artifact or one explicit phase
decision. It records:

- event start and end, not merely client arrival;
- measurement and model roots;
- artifact hashes;
- transforms and their completeness;
- constraints and uncertainty;
- authorized and unauthorized claims.

Evidence satisfies a clause only while:

```text
evaluation_time <= event_end + clause_TTL
```

Fresh arrival cannot rescue stale event-time evidence. Model roots never count
as independent measurement roots.

## 4. Strict descriptive boundary

Receipt JSON uses `allow_nan=False`. Non-finite values are represented by an
explicit numeric state, not replaced with arbitrary numbers. NumPy scalars are
normalized; NumPy arrays are rejected.

Raw IQ, waterfall data and STFT arrays remain ephemeral:

```text
bytes arrive
  -> incremental SHA-256
  -> in-memory transform
  -> receipt/hash emission
  -> destruction
```

A serialization failure may change the descriptive receipt state, never the
underlying physical decision.

## 5. SatNOGS branch: model-conditioned measurements

`satnogs_probe.py` acquires published observation artifacts and keeps their
measurement roots distinct from shared catalog/orbit roots.

`satnogs_failover.py` defines separate contracts:

- continuity: at least one valid measurement root;
- corroboration: at least two independent measurement roots.

Revoking a source removes only its atomic evidence. Replacement candidates are
ranked by the lost clause they restore, event-time freshness, new lineage,
transform completeness and cost. A replacement is successful only if it
actually restores the clause; it is not a hardcoded station fallback.

When every measurement expires the observation is `UNOBSERVABLE`, even if an
orbital model remains `MODEL_AVAILABLE`.

## 6. Kiwi branch: targetless RF

### 6.1 Dual-receiver comparison

`kiwi_probe.py` uses two independent public Kiwi receivers. Equal frequency is
not called coincidence. A shared-change claim requires:

- GNSS event-time overlap and continuous sequences;
- an explicit common time/frequency grid;
- a jointly salient time-frequency region;
- time-shift and frequency-shift max-statistic nulls from the same session;
- even/odd self-consistency;
- bounded clock and frequency drift;
- separate station scores and causal lineage.

HF propagation leaves important ambiguity: fading, different paths, local
interference, ionospheric delay and common Kiwi software can imitate or erase
structure. The maximum claim is compatibility with one shared live RF change,
not transmitter identity or common cause.

### 6.2 Prospective separation

`kiwi_prospective.py` separates:

1. discovery;
2. model reveal;
3. immutable prediction;
4. independent confirmation.

The separation prevents selection of a band, feature or threshold after the
confirmation outcome is visible.

### 6.3 Same-Kiwi DDC intervention

Gate F2.3 established that two independent hardware roots are not universally
required. To test a per-channel NCO/DDC boundary, a cleaner topology is:

```text
shared antenna/front-end/ADC/clock
                   |
           per-channel split
              /           \
     fixed reference     perturbed branch
       no retune          A1 -> B -> A2
```

Shared hardware removes propagation and inter-receiver clock differences, but
leaves common-mode ADC overload, intermodulation, clock spurs and upstream FPGA
artifacts. Therefore `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED` is not a synonym for
external RF.

The required topology is hypothesis-specific:

- one server instance;
- two simultaneous SND/IQ allocations;
- distinct channel identities and sequence receipts;
- one command-free reference branch;
- one controllably retuned branch;
- a witness that moves only where the retune predicts;
- no geographic-location requirement.

## 7. Gate F2.5 causal path

Gate F2.5 makes W/F optional and treats `ext_api` only as a descriptive hint.
The operational truth must come from a direct simultaneous SND reference and
perturbed attempt.

Topology qualification, local feature discovery and retune qualification are
separate phases. `NO_MULTI_CHANNEL_CAPABILITY` is legal only after a real
second-channel attempt. Timeout or software failure produces
`QUALIFICATION_INCOMPLETE`.

The first live F2.5 outcome exposed one remaining precondition: center
selection expected `bandwidth` in `/status`, so direct SND was never attempted.
This is a policy/transform failure. It says nothing about multichannel
availability.

Gate F2.5.1 removes only that dependency. A frozen 0–30 MHz Kiwi-family
interval supplies a deterministic interior coordinate for qualification; the
coordinate is independent of status, is not a target or discovered feature,
and cannot itself prove that tuning or IQ delivery succeeded. Those facts must
come from the direct SND streams. The older runtime and outcome remain
reproducible and immutable.

Its first live outcome reached both SND attempts for all frozen candidates but
admitted no pair. One candidate produced an explicit access rejection; the
remaining candidates produced transport/protocol errors, so the terminal
state is `QUALIFICATION_INCOMPLETE`. The run also exposed a narrower receipt
problem: if either concurrent branch fails, `_open_dual()` collapses both
branch histories into one exception. A possible ready branch and its first
GNSS IQ block are therefore not independently receipted or hashed. This blocks
topology inference even though it does not imply zero RF persistence.

Gate F2.5.2 moves that boundary one step earlier. Each SND branch now emits an
atomic `BranchOpenReceipt`; every raw SND frame is hashed before decode with a
length-delimited stream digest, and the GNSS readiness frame has its own hash.
The pair is composed only after both branch states exist. A ready sibling may
be closed after peer failure without erasing its channel/readiness evidence,
while any qualification error keeps aggregate availability indeterminate.
These receipts remain local to this vertical probe rather than becoming a
generic capability framework.

The first F2.5.2 live outcome validated the new boundary: one reference branch
was `READY` with a hashed GNSS IQ witness while its perturbed peer was
`CAPABILITY_REJECTED`. It also showed that structured evidence was not yet
driving all control. The legacy retry selector searched aggregate statement
text, so replacing that prose with an atomic summary silently disabled the
declared retries. Receipt JSONL was also stdout-only and one console segment
was not retained. Future correction must use structured branch error types for
retry eligibility and a bounded strict-JSON receipt sink; neither change
requires RF persistence.

## 8. Prospective freeze and outcomes

Before plan freeze, a declared retry budget may cover only timeout, transport,
description, serialization or software transform failure. It cannot change the
physical question, feature, threshold, candidate order or window.

After freeze:

- zero retry;
- zero new window;
- zero endpoint or frequency change;
- zero threshold or transform change;
- exactly one outcome.

Possible DDC outcomes include:

- `UPSTREAM_OF_CHANNEL_DDC_SUPPORTED`;
- `DOWNSTREAM_CHANNEL_FIXED_SUPPORTED`;
- `AMBIGUOUS`;
- `INTERVENTION_INVALID`;
- `NOT_DETECTABLE`.

Pre-freeze terminal states include `QUALIFICATION_INCOMPLETE`,
`NO_MULTI_CHANNEL_CAPABILITY`, `NO_ADMISSIBLE_CAUSAL_TOPOLOGY` and
`NO_FALSIFIABLE_INTERVENTION`.

## 9. Module map

| Module | Responsibility |
|---|---|
| `models.py` | clause, receipt, causal graph and strict JSON primitives |
| `orbital_kernel.py` | stateless position, range-rate and Doppler calculation |
| `satnogs_probe.py` | atomic published-observation acquisition |
| `satnogs_failover.py` | clause-driven replacement and TTL semantics |
| `kiwi_probe.py` | dual-Kiwi capture, temporal audit and session nulls |
| `kiwi_prospective.py` | prospective discovery/prediction/confirmation |
| `kiwi_gate_e.py` | detectability and qualification boundary experiments |
| `kiwi_gate_f2.py` | capability-first falsification experiment synthesis |
| `kiwi_gate_f2_2.py` | frozen multipath bootstrap and one-shot policy |
| `kiwi_gate_f2_3.py` | causal topology audit |
| `kiwi_gate_f2_4.py` | first same-Kiwi two-channel runtime |
| `kiwi_gate_f2_5.py` | direct-SND-first causal path |
| `kiwi_gate_f2_5_1.py` | status-independent SND bootstrap policy |
| `kiwi_gate_f2_5_2.py` | atomic per-branch opening and readiness hashes |
| `kiwi_gate_f2_5_3.py` | typed retry selection and bounded receipt-only JSONL sink |
| `kiwi_gate_f2_5_3_1.py` | in-band terminal manifest and closed-artifact receipt |
| `kiwi_gate_f2_5_4.py` | pure offline attribution of the SND control boundary and exit semantics |
| `kiwi_gate_f2_5_5.py` | fail-closed source basis and ordered SND control-receipt contract |
| `kiwi_gate_f2_5_6.py` | strict offline verification of the pinned server archive and hash-only client source audit |
| `kiwi_gate_f2_5_7.py` | gate-specific server-wire transcript and official-client necessity audit |
| `kiwi_gate_f2_5_8.py` | ordered auth/channel/rate/command/IQ receipt integration tested with synthetic frames |

## 9.1 Pinned protocol source boundary

Gate F2.5.6 resolves the exact server and client control paths without touching
a Kiwi endpoint. The retained server subset proves that `badp=0` is auth
success, `badp=5` is the no-multiple-connections policy, `too_busy` is a
capacity response, and `SET mod` addresses `conn->rx_channel`. These facts do
not imply that a frozen session reached IQ readiness.

The server archive is verified by whole-archive and per-member SHA-256, exact
membership, byte counts and line counts. The client checkout was inspected
ephemerally; only commit, blob IDs, paths, spans, hashes and sizes are retained
because no license grant was found. Therefore the exit remains
`SOURCE_RETENTION_BLOCKED_BY_LICENSE`, implementation stays unauthorized and
the eleven historical closures remain causally unresolved.

## 9.2 Server wire versus reference client

Gate F2.5.7 removes the retained official client from the physical evidence
requirements. The minimum causal chain is server-defined auth/channel/rate,
an observed local `mod_iq` send and a later pre-decode-hashed IQ frame. Client
source cannot substitute for the last witness and is therefore not a required
root.

The synthetic contract requires `badp=0`, the channel number carried by
`is_local`, and `sample_rate` before `mod_iq`; an IQ frame must follow it. It
also keeps clean WebSocket close separate from typed transport loss. The
current runtime has not yet been changed to emit this sequence. The result
`SERVER_WIRE_CONTRACT_SUFFICIENT` authorises only an offline receipt-integration
gate, not a live run.

## 9.3 Ordered receipt integration

Gate F2.5.8 implements a successor branch opener without rewriting the frozen
F2.5.2 outcome. Incoming MSG, SND and close frames are hashed before analysis;
only allowlisted fields and artifact hashes enter the receipt. Configuration
waits for `badp=0`, the channel number inside `is_local`, and `sample_rate`.
The first valid IQ then witnesses a usable ordered branch.

The integration also distinguishes local send error and control timeout from
WebSocket close and transport loss. Dual composition requires two complete
transcripts with different server channel numbers. This implementation is
offline-tested only and has no automatic runner or live authorization.

## 10. Non-goals

The current direction does not require a database, frontend, microservice,
source marketplace, adapter SDK, experiment DSL, universal planner, ML model,
LLM orchestrator, persistent capability catalog, RF storage, TDoA or new
SatNOGS expansion.

Those components should not be introduced until a vertical experiment proves
that the missing abstraction is necessary.
