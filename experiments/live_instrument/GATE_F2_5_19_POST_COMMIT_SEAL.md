# Gate F2.5.19 — corrected dual-SND post-commit seal

## Outcome

`EXACT_CORRECTED_QUALIFICATION_READY_FOR_SEPARATE_AUTHORITY`

Gate F2.5.19 performs no receiver connection and grants no live authority. It
binds the exact Gate F2.5.18 implementation to a single boolean-only execution
surface that remains closed until the user separately authorizes its final
commit.

## Reviewed state

- reviewed Gate F2.5.18 commit:
  `0e6fa411800042423e706001aefdcba6fd8c95da`;
- corrected control-plan hash:
  `c1a2d8fc139e6090ee70500f258b28c9160174a3411908d4b347c959cf6909fd`;
- dual execution control-surface hash:
  `c7b12943feb2ea2ba8ef3f9970a6a145d22cad711146d02bdfba3da75cfe1da6`;
- authority-envelope hash:
  `b89c09209e83797b06c9730e001fd85c3a04ae77719412655dd0f9c877bdd80a`;
- causal allowlist: 21 hash-bound files, including the retained setup header
  and manifest;
- numerical environment: Python 3.13.5, NumPy 2.3.3, SciPy 1.17.1 and
  websocket-client 1.8.0;
- pre-freeze retry: zero;
- post-freeze retry: zero;
- RF persistence: zero.

## Exact authority surface

```python
run_reviewed_once(*, live_authorised=False)
```

The caller may change only `live_authorised` from its default refusal. It
cannot supply an endpoint, frequency, candidate order, retry, threshold,
connector, framing module, receipt path, observation window, discovery rule or
intervention.

Guard order is fixed:

1. explicit separate authority;
2. post-commit causal and environment seal;
3. terminal receipt creation;
4. corrected direct dual-SND connectors.

Calling the surface without authority raises before connector or receipt
access. The seal assessment itself is read-only and offline.

## Maximum authorized future scope

The future one-shot may only determine whether one candidate supplies two
simultaneous corrected semantic SND/IQ branches satisfying the frozen topology.
It stops at the first ready pair or candidate exhaustion.

It may not perform:

- local feature discovery;
- retune qualification;
- A1/B/A2;
- model/data reveal;
- scientific observation or interpretation;
- a second window or retry.

If two streams become ready, the qualification stops successfully and the
measurement capability can become input to a separately frozen
observation-plus-data experiment. No such experiment is authorized here.

## Offline verification

Tests prove the full causal and environment seal, default refusal before side
effects, absence of public overrides and the exact corrected candidate loop
through injected rejecting sockets. The synthetic run closes one strict
terminal JSONL receipt with zero RF persistence.

Gate F2.5.19 stops before network activity.
