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
