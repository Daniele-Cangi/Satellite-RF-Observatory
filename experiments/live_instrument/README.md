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
| Same-Kiwi DDC cut | `kiwi_gate_f2_3.py`, `kiwi_gate_f2_4.py`, `kiwi_gate_f2_5.py`, `kiwi_gate_f2_5_1.py`, `kiwi_gate_f2_5_2.py` | topology audit, frozen outcomes and atomic direct-SND qualification |

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
