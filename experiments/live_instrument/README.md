# Live-instrument experiment history

This directory is an evidence trail and a set of disposable vertical probes.
It is not a generic source framework.

## Supported verification

From the repository root:

```bash
python -m pip install -r requirements-live-instrument.txt
python -m pytest experiments/live_instrument/tests -q
```

Tests are offline. Do not add live probes to pytest or CI.

## Mechanism map

| Area | Code | Evidence |
|---|---|---|
| Shared receipts | `models.py` | strict JSON, causal roots, clauses, TTL |
| Orbital geometry | `orbital_kernel.py` | stateless position/range-rate/Doppler tests |
| SatNOGS | `satnogs_probe.py`, `satnogs_failover.py` | Checkpoints 1–3 |
| Targetless dual Kiwi | `kiwi_probe.py` | calibrated session-null comparison |
| Prospective Kiwi | `kiwi_prospective.py` | discovery/model/prediction/confirmation split |
| Detectability | `kiwi_gate_e.py` | Gate E outcomes and E.1 hardening |
| Capability-first synthesis | `kiwi_gate_f2.py`, `kiwi_gate_f2_2.py` | Gate F/F2 outcomes |
| Same-Kiwi DDC cut | `kiwi_gate_f2_3.py` through `kiwi_gate_f2_5_13.py` | topology audit, ordered direct-SND qualification, one-shot execution, failure attribution, semantic receipts and injected ordered integration |

## Reading order

1. [`CHECKPOINT_1.md`](CHECKPOINT_1.md) — first live capability/evidence split.
2. [`CHECKPOINT_2.md`](CHECKPOINT_2.md) — SatNOGS and targetless Kiwi comparison.
3. [`CHECKPOINT_3.md`](CHECKPOINT_3.md) — clause-driven failover and calibrated Kiwi null.
4. [`PROSPECTIVE_OUTCOME_1.md`](PROSPECTIVE_OUTCOME_1.md) — first prospective failure attribution.
5. [`GATE_E_OUTCOME_1.md`](GATE_E_OUTCOME_1.md) and
   [`GATE_E_1_POSTMORTEM.md`](GATE_E_1_POSTMORTEM.md) — detectability and receipt hardening.
6. [`GATE_F_CHECKPOINT_F1.md`](GATE_F_CHECKPOINT_F1.md) — competing capability-generated mechanisms.
7. [`GATE_F2_OUTCOME_1.md`](GATE_F2_OUTCOME_1.md),
   [`GATE_F2_1_POSTMORTEM.md`](GATE_F2_1_POSTMORTEM.md) and
   [`GATE_F2_2_OUTCOME_1.md`](GATE_F2_2_OUTCOME_1.md) — first capability-first executions.
8. [`GATE_F2_3_CAUSAL_TOPOLOGY.md`](GATE_F2_3_CAUSAL_TOPOLOGY.md) — why one multichannel Kiwi is the relevant instrument.
9. [`GATE_F2_4_OUTCOME_1.md`](GATE_F2_4_OUTCOME_1.md) — W/F blocked the desired SND question.
10. [`GATE_F2_5_OFFLINE.md`](GATE_F2_5_OFFLINE.md) and
    [`GATE_F2_5_OUTCOME_1.md`](GATE_F2_5_OUTCOME_1.md) — direct-SND design and the remaining center-policy failure.
11. [`GATE_F2_5_1_OFFLINE.md`](GATE_F2_5_1_OFFLINE.md) — status-independent bootstrap prepared without a new live session.
12. [`GATE_F2_5_1_OUTCOME_1.md`](GATE_F2_5_1_OUTCOME_1.md) — direct SND reached, but branch-level readiness remained indeterminate.
13. [`GATE_F2_5_2_OFFLINE.md`](GATE_F2_5_2_OFFLINE.md) — atomic branch receipts and pre-decode readiness hashing, with no new live run.
14. [`GATE_F2_5_2_OUTCOME_1.md`](GATE_F2_5_2_OUTCOME_1.md) — one ready branch preserved, peer rejection, and the remaining structured-control failures.
15. [`GATE_F2_5_3_OFFLINE.md`](GATE_F2_5_3_OFFLINE.md) — typed retry control and bounded receipt-only JSONL retention, prepared without network activity.
16. [`GATE_F2_5_3_1_OFFLINE.md`](GATE_F2_5_3_1_OFFLINE.md) — terminal manifest, prefix hash and guaranteed receipt closure, prepared without network activity.
17. [`GATE_F2_5_3_1_OUTCOME_1.md`](GATE_F2_5_3_1_OUTCOME_1.md) — one live run materialised the exact retry budget and ended `QUALIFICATION_INCOMPLETE` before any IQ readiness or DDC experiment.
18. [`GATE_F2_5_4_PROTOCOL_AUDIT.md`](GATE_F2_5_4_PROTOCOL_AUDIT.md) — offline control-boundary attribution: four explicit rejections, one pre-handshake timeout and eleven failures not diagnosable by the frozen receipt.
19. [`GATE_F2_5_5_OFFLINE.md`](GATE_F2_5_5_OFFLINE.md) — fail-closed official-source clause plus an ordered, redacted control-receipt contract; no runtime or network activity.
20. [`GATE_F2_5_6_SOURCE_REPRODUCTION.md`](GATE_F2_5_6_SOURCE_REPRODUCTION.md) — exact server source archive, hash-only client audit and the explicit license-retention boundary; no Kiwi or RF activity.
21. [`GATE_F2_5_7_SERVER_WIRE_AUDIT.md`](GATE_F2_5_7_SERVER_WIRE_AUDIT.md) — why the server-defined ordered receipt is sufficient for the DDC question without retaining the official client source; offline only.
22. [`GATE_F2_5_8_ORDERED_RECEIPT.md`](GATE_F2_5_8_ORDERED_RECEIPT.md) — integration of the ordered auth/channel/rate/command/IQ receipt with synthetic frames and zero RF persistence; no live execution.
23. [`GATE_F2_5_9_PRELIVE_RUNNER.md`](GATE_F2_5_9_PRELIVE_RUNNER.md) — pre-live call-graph review and one-shot materialisation using only the ordered opener; execution remains separately gated.
24. [`GATE_F2_5_10_EXECUTION_REVIEW.md`](GATE_F2_5_10_EXECUTION_REVIEW.md) — exact candidate, timing, source, environment and authority envelope; no caller overrides and no live execution.
25. [`GATE_F2_5_10_OUTCOME_1.md`](GATE_F2_5_10_OUTCOME_1.md) — the single authorised run ended `QUALIFICATION_INCOMPLETE`: six dual attempts, zero readiness witnesses, zero retry and a complete terminal receipt.
26. [`GATE_F2_5_11_FAILURE_ATTRIBUTION.md`](GATE_F2_5_11_FAILURE_ATTRIBUTION.md) — offline attribution proves the recorded `1005` values were local sentinels for empty close payloads, while SND presence and the failure cause remain unresolved by the frozen receipt.
27. [`GATE_F2_5_12_SEMANTIC_RECEIPT.md`](GATE_F2_5_12_SEMANTIC_RECEIPT.md) — a future frame receipt now binds its pre-analysis hash to MSG/SND/CLOSE class and clause-by-clause readiness transitions, without retaining RF or changing a live runner.
28. [`GATE_F2_5_13_ORDERED_INTEGRATION.md`](GATE_F2_5_13_ORDERED_INTEGRATION.md) — the semantic receipt is integrated into the real ordered opener through a mandatory injected connector, verified only with synthetic sockets and still stopped before dual composition or live authority.
29. [`GATE_F2_5_15_OUTCOME_1.md`](GATE_F2_5_15_OUTCOME_1.md) — the exact sealed authority was consumed once: eight allocated branches produced zero semantic SND frames and physical capability remained unevaluated.
30. [`GATE_F2_5_16_CONTROL_SEQUENCE_POSTMORTEM.md`](GATE_F2_5_16_CONTROL_SEQUENCE_POSTMORTEM.md) — offline command-hash/source attribution falsifies neutral keepalive semantics while keeping the remote close cause explicitly inconclusive.
31. [`GATE_F2_5_17_PHASE_AWARE_CONTROL.md`](GATE_F2_5_17_PHASE_AWARE_CONTROL.md) — the exact pinned setup mask closes the source gap and a synthetic-only successor emits setup once before permitting time-paced liveness.
32. [`GATE_F2_5_18_DUAL_PHASE_AWARE.md`](GATE_F2_5_18_DUAL_PHASE_AWARE.md) — two corrected branches are composed concurrently under the frozen topology, candidate order, zero-retry and terminal-receipt boundary.
33. [`GATE_F2_5_19_POST_COMMIT_SEAL.md`](GATE_F2_5_19_POST_COMMIT_SEAL.md) — the corrected dual qualification is bound to its reviewed commit, causal hashes and environment behind one default-refusing authority bit.
34. [`GATE_F2_5_19_OUTCOME_1.md`](GATE_F2_5_19_OUTCOME_1.md) — the single authority produced two simultaneous semantic SND/IQ branches on one Kiwi at the first candidate, then stopped before discovery or retune.
35. [`GATE_F2_5_20_PROSPECTIVE_VERTICAL.md`](GATE_F2_5_20_PROSPECTIVE_VERTICAL.md) — the qualified endpoint is composed offline with a new ephemeral discovery, witness-only retune qualification, immutable plan and one post-freeze A1/B/A2.
36. [`GATE_F2_5_21_POST_COMMIT_SEAL.md`](GATE_F2_5_21_POST_COMMIT_SEAL.md) — commit, causal sources, numerical environment and the live wrapper itself are sealed behind one default-refusing authority bit.
37. [`GATE_F2_5_21_OUTCOME_1.md`](GATE_F2_5_21_OUTCOME_1.md) — the single authority admitted two live SND/IQ channels, but local discovery found fewer than two distinct stable structures and stopped before retune, freeze or confirmation.
38. [`GATE_F2_5_22_DISCOVERABILITY_AUDIT.md`](GATE_F2_5_22_DISCOVERABILITY_AUDIT.md) — offline attribution shows the frozen failure lacks input hashes and candidate margins, corrects a masked-width defect descriptively, and proves that an orthogonal witness need not be a second narrowband peak.
39. [`GATE_F2_5_23_ONE_TARGET_SUCCESSOR.md`](GATE_F2_5_23_ONE_TARGET_SUCCESSOR.md) — injected synthetic sockets, one-target discovery and a target-excluded distributed witness now materialize an immutable pre-freeze plan.
40. [`GATE_F2_5_24_CONFIRMATION_EVALUATOR.md`](GATE_F2_5_24_CONFIRMATION_EVALUATOR.md) — the post-freeze evaluator is integrated offline with target-independent intervention admission, all five frozen outcomes and strict zero-RF receipts; no observation or authority is added.
41. [`GATE_F2_5_25_POST_COMMIT_SEAL.md`](GATE_F2_5_25_POST_COMMIT_SEAL.md) — commit, causal sources, environment and the same-session one-target execution surface are sealed behind one default-refusing authority bit; no live authority is granted or consumed.
42. [`GATE_F2_5_25_OUTCOME_1.md`](GATE_F2_5_25_OUTCOME_1.md) — the single authority received two SND/IQ streams but no temporally admissible readiness roots: GPS solution age was 92–103 seconds against the frozen 30-second limit, so every physical phase remained `NOT_EVALUATED`.
43. [`GATE_F2_5_26_TEMPORAL_FAILURE_ATTRIBUTION.md`](GATE_F2_5_26_TEMPORAL_FAILURE_ATTRIBUTION.md) — the offline attribution verifies the server-defined age semantics, separates active data transport from failed measurement admission, and shows that a topology-derived relative-time alternative cannot be evaluated from the frozen receipt.
44. [`GATE_F2_5_27_RELATIVE_TIME_ADMISSION.md`](GATE_F2_5_27_RELATIVE_TIME_ADMISSION.md) — a new offline plan derives temporal admission from the same-ADC causal cut: sample-count closure, reserved clock-state refusal, common overlap and command-boundary witnesses, with actual server timestamps retained only as scalar receipts.
45. [`GATE_F2_5_28_INJECTED_ONE_SHOT.md`](GATE_F2_5_28_INJECTED_ONE_SHOT.md) — the relative-time plan is integrated into a sealed injected path: hash-before-decode, hard downstream call gates, two mandatory retune boundaries and unconditional RAM zeroization; no connector or live authority exists.
46. [`GATE_F2_5_29_PHASE_AWARE_INJECTED_BRIDGE.md`](GATE_F2_5_29_PHASE_AWARE_INJECTED_BRIDGE.md) — two injected SND branches now obey the exact phase-aware auth/metadata/setup order, release transport bytes explicitly, enter the same-ADC relative gate without absolute-freshness leakage and retain no RF; no public execution surface exists.
47. [`GATE_F2_5_30_SEALABILITY_AUDIT.md`](GATE_F2_5_30_SEALABILITY_AUDIT.md) — the exact post-commit audit refuses a nominal authority bit because both channel handles close before discovery and retune; relative-time admission survives, while live A1/B/A2 remains unsealable until an open-handle successor exists.
48. [`GATE_F2_5_31_OPEN_HANDLE_SUCCESSOR.md`](GATE_F2_5_31_OPEN_HANDLE_SUCCESSOR.md) — one injected outer owner now spans A1 discovery and both scalar command boundaries, permits retune only on the private perturbed handle, audits every settling frame and closes everything in the outer `finally`; RF response remains deliberately unevaluated.
49. [`GATE_F2_5_32_RF_RESPONSE_INTEGRATION.md`](GATE_F2_5_32_RF_RESPONSE_INTEGRATION.md) — the same open-handle A1/B/A2 arrays now pass first through the existing target-excluded distributed RF witness, then an immutable target plan and only then target matching; all five physical outcome semantics are exercised offline with unchanged thresholds and zero RF persistence.
50. [`GATE_F2_5_33_POST_COMMIT_SEAL.md`](GATE_F2_5_33_POST_COMMIT_SEAL.md) — the reviewed F2.5.32 commit, source, plan, integration surface, numerical environment and minimal WebSocket ownership adapter are sealed behind one default-false authority bit; assessment is offline and no authority is consumed.
51. [`GATE_F2_5_33_OUTCOME_1.md`](GATE_F2_5_33_OUTCOME_1.md) — the single authority admitted two simultaneous same-clock SND/IQ channels and relative timing, then stopped `NO_FALSIFIABLE_INTERVENTION` because unchanged discovery admitted no common A1 feature; no retune or physical hypothesis evaluation occurred.
52. [`GATE_F2_5_34_DISCOVERY_FAILURE_ATTRIBUTION.md`](GATE_F2_5_34_DISCOVERY_FAILURE_ATTRIBUTION.md) — receipt-only attribution proves the sensor and transform path were operational and the composite feature rule failed, but the missing stage counts and margins make the specific rejection cut inconclusive; the DDC hypothesis remains not falsifiable from this receipt.
53. [`GATE_F2_5_35_SCALAR_AUDIT_INTEGRATION.md`](GATE_F2_5_35_SCALAR_AUDIT_INTEGRATION.md) — an offline successor emits an authoritative discovery decision and a decision-independent scalar stage audit from the same ephemeral arrays; description failure cannot change the selector, downstream phases or physical outcome.
54. [`GATE_F2_5_36_POST_COMMIT_SEAL.md`](GATE_F2_5_36_POST_COMMIT_SEAL.md) — the committed audited vertical, decision/audit boundary, inherited plan, connector, environment and strict receipt are sealed behind one default-false authority bit; no network activity or authority consumption occurs.
55. [`GATE_F2_5_36_OUTCOME_1.md`](GATE_F2_5_36_OUTCOME_1.md) — one feature passed the unchanged live discovery and both retune boundaries were witnessed, but the run stopped `INTERVENTION_INVALID`; offline reconstruction proves the final continuity evaluator counted each branch's excluded leading-zero timestamp, so the physical hypotheses remain `NOT_EVALUATED` and the block is attributed to software qualification.

## Frozen-outcome rule

An outcome document describes exactly one execution from exactly one runtime
commit. Never edit a frozen plan or outcome to make a later interpretation
look successful. Corrections belong to a postmortem or a new gate.

## Live safety and scope

- Require explicit authorization for every live execution.
- Use only the frozen public endpoints and responsible, short-lived access.
- Persist no RF, waterfall or sample arrays.
- Stop at the first outcome.
- Do not infer satellite identity, transmitter identity, external-RF origin,
  geolocation or common cause unless a future experiment closes those exact
  causal cuts.
