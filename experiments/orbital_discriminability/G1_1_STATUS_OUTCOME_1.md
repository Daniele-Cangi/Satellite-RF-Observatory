# Gate G1.1 — status-only outcome 1

## Frozen authority

```text
pre-execution commit: 9aaacfb
plan hash:           c8e97a502ebe32cbaf8da30a88cc2240bcd2ec66325a8a64291ddeb5c392327b
evaluated at:        2026-08-19T12:02:40.310794Z
retry:               ZERO
RF requests:         ZERO
```

The sole authorized G1.1 session is consumed. It ended:

```text
CAPABILITY_DISCOVERY_UNAVAILABLE
```

This is not `NO_CAPABILITY_ADMITTED`. No capability descriptions entered the
admission boundary, so the session cannot claim that no suitable Internet
receiver exists.

## Request ledger

Exactly seven bounded descriptive requests were made:

| Phase | Count | Result |
|---|---:|---|
| SatNOGS transmitter metadata | 1 | success; 3,494,829 bytes hashed in RAM |
| CelesTrak OMM | 5 | three success, two HTTP 404 |
| Kiwi public directory entry | 1 | HTTP 200, interaction required |
| Receiver `/status` | 0 | blocked before endpoint materialization |
| SND/IQ/W/F/audio/spectrum | 0 | forbidden |

There was no retry. Response bodies were destroyed after parsing. The strict
scalar receipt is
`session_receipts/g1_1_status_outcome_1.jsonl`, SHA-256:

```text
a91f1a8b7fabf047f8cc70d0bf55732e2b1b0639241f190a73bd56fb29951504
```

## Model side

The frozen HF telemetry/beacon filter produced five transmitter candidates.
Three retained current OMM documents:

| Candidate | Carrier | OMM age at evaluation | Transmitter metadata updated |
|---|---:|---:|---|
| RADIO ROSTO (RS-15), NORAD 23439 | 29.3525 MHz | 35,997.523 s | 2026-02-14 |
| ZACUBE-1, NORAD 39417 | 14.099 MHz | 32,732.295 s | 2022-07-08 |
| OSCAR 7 (AO-7), NORAD 7530 | 29.502 MHz | 41,952.815 s | 2022-03-17 |

NORAD 98272 and 54684 returned HTTP 404 from the frozen CelesTrak route. The
three retained objects are model candidates only. `alive/active` transmitter
metadata, especially old unchanged records, does not prove current emission.

## Capability side

The official entry `http://rx.kiwisdr.com` returned HTTP 200 and redirected to
`http://kiwisdr.com/public/`. Its 2,294-byte page requires a user click and a
custom `x-kiwi-auth` header before materializing the directory.

The frozen plan forbids copying that header from JavaScript, simulating the
gesture or importing endpoints from earlier gates. The runner therefore
recorded `INTERACTION_REQUIRED` and stopped. It made no receiver request.

## Clause attribution

| Clause | State | Evidence |
|---|---|---|
| bounded model metadata route | `SATISFIED` | transmitter response and three fresh OMM hashes |
| non-interactive capability inventory | `UNSATISFIED` | directory page requires interaction/custom authorization |
| endpoint descriptions materialized | `NOT_EVALUATED` | inventory did not expose endpoints |
| individual G1 qualification | `NOT_EVALUATED` | no `/status` response exists |
| pass-specific pair admission | `NOT_EVALUATED` | no capability offer exists |
| prospective RF plan | `NOT_EVALUATED` | admission was never entered |

The interaction requirement is a discovery limitation, not a receiver
rejection and not evidence about RF availability.

## Authorized claims

- The bounded model routes materialized three current orbital candidates with
  HF carrier descriptions.
- The frozen public capability route did not provide a non-interactive
  machine-readable inventory in this session.
- Gate G1.1 respected the interaction boundary and performed zero RF activity.

## Unauthorized claims

- No suitable Internet receiver exists.
- The three transmitter descriptions correspond to current emissions.
- Any listed satellite was visible, transmitting or observed.
- A receiver would fail G1 admission if it could be described through an
  authorized route.

## SHOCK and stop

The model side was easier to materialize than the instrument side. A web page
listing receivers is not itself a capability offer: if obtaining the list
requires an interactive authorization boundary, the system has no legitimate
machine-readable candidate set to score.

G1.1 stops here. It grants no retry and does not authorize a browser-assisted
export. Any successor must begin offline by deciding what constitutes a
legitimate inventory receipt; it may not start from remembered endpoints.
