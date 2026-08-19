# Gate G1.3.2 — independent inventory search outcome 1

## Frozen authority

```text
search transport parent: 691bc73
document transport:       b6d13aa
G1.3 plan hash:           cb0f8e1cf24b39b4d17a6d85c13c0e3715deb4df0100ecf3c9eeb14c82732d12
G1.3.1 plan hash:         11a1b8dc3ec6863da406d64364f7605b82fd5a806b6e72005e84640a881c279c
G1.3.2 document hash:     9a5f1d93ee0fd066b68b805e7b292cae410437942a37fe172c9571eadf2f78dc
evaluated at:             2026-08-19T13:43:01.465334Z
search retry:             ZERO
document retry:           ZERO
receiver status:          ZERO
RF requests:              ZERO
```

The authorized execution ended:

```text
NO_LEGITIMATE_INVENTORY_FOUND
```

This result is limited to the frozen four-query surface and six round-robin
candidates. It is not evidence that no suitable inventory or receiver exists
elsewhere.

## Independent search receipts

Each query ran in a separate provider invocation, once, in frozen order. The
ordered result lists were retained only as URLs plus their canonical hashes:

| Query | Invocation | Results | Ordered-set SHA-256 |
|---|---:|---:|---|
| public SDR receiver directory API machine readable | `turn48` | 5 | `02cc0fba7e6423aedcf567a8dc2d13ccd1850dbfdea5232e226c69902d3277f4` |
| KiwiSDR public receiver directory API official | `turn49` | 5 | `79930dacddff0e89e27952b4d2693b9d7f0617f001d51e1b3e2144e3881f988d` |
| OpenWebRX receiver directory API official | `turn50` | 5 | `4185fa537d211688ee145612474eb1cbfa8fd1b3ad49a4ff9959967ea7e547ad` |
| WebSDR server list machine readable API official | `turn51` | 5 | `3def9c98653ffccbca9ef652e8a91e915cc104292a4fd4bda3d7957881b0d310` |

All four receipts are `SUCCESS`. No merged-result reconstruction or relevance
reranking was used.

## Frozen candidate audit

The unchanged round-robin selected the following six documents. Each was read
once with a 15-second timeout and 1 MiB bound. Complete bytes were hashed
before descriptor extraction and then destroyed.

| Rank | Candidate | Bytes | Artifact SHA-256 | Audit |
|---:|---|---:|---|---|
| 1 | `https://database.radioid.net/api/` | 39,017 | `04f982ccd25187f3f68d6550ffeee41bc69fba80e5df450cf02a118cfdbcb4eb` | API landing page, not a current live-SDR endpoint-set artifact |
| 2 | `https://github.com/jks-prv/KiwiSDR` | 449,743 | `15c4be6d698fd35273280dc6e4820929ebd5b580bb1d185212695ce488a01632` | software repository; map link is not an inventory receipt |
| 3 | `https://github.com/jketterl/openwebrx` | 293,885 | `9422fb7f2d0b6b628f95fc7765f23dca1c00af9e7bd0b3854c90a69feefb9b49` | software repository; `bands.json` is configuration, not a receiver inventory |
| 4 | `https://docs.wsdr.io/webdev/websdr/websdr.html` | 23,154 | `2d37031b458b6c7162f18c75a35d7dbf903476c7ff44bac48fb3bb2cbad23ab4` | software documentation; no current endpoint set |
| 5 | `https://home.recnet.com/index.php/api` | 91,034 | `f9fb62e417fe8b1952bcc5e3131af4230c156900801f43e6bb76a497beb00cdc` | radio-data API, not a complete live Internet SDR scope |
| 6 | `https://www.areg.org.au/remote-hf-rx` | 77,526 | `6096a4f123b4db734dfa158e45c3cacc3570f9a17f3bb76e13e212441a230c7d` | descriptive receiver page without inventory schema, TTL or complete endpoint binding |

Every fetch returned `SUCCESS`; therefore no descriptive error was converted
into a mechanism rejection. No arbitrary second link was followed. None of
the first documents designated a machine-readable current inventory artifact
that could enter the second-document allowance without a new post-hoc choice.

## Clause attribution

All six candidates satisfied only the clauses demonstrated directly by the
bounded fetch:

- current-session artifact basis;
- non-interactive document retrieval;
- bounded artifact integrity and hash-before-parse;
- ephemeral handling;
- descriptive-only activity with zero receiver status and zero RF.

All six failed admission because the frozen receipt could not establish all
of the remaining requirements:

- operator authority binding was not inferred from search rank or hostname;
- no documented automation permission for a current receiver inventory was
  materialized;
- no positive TTL at most 600 seconds covered the 120-second qualification
  budget (`max-age=0` for GitHub, `1800` for WSDR, `900` for REC, absent for
  RadioID and AREG);
- no named, versioned endpoint schema was materialized;
- no complete declared selection scope was materialized;
- no deterministic set of `endpoint_id` plus `status_route` entries was
  materialized.

The WSDR and REC cache lifetimes are descriptive HTTP cache values, not proof
of inventory freshness; in any case they exceed the frozen 600-second bound.

## Authorized claims

- The independent-query transport fixed the earlier loss of query membership.
- The six candidates selected prospectively were all fetched and evaluated.
- No candidate supplied an admissible Gate G1.2 inventory receipt on this
  frozen search surface.
- Capability admission remains `NOT_EVALUATED`.
- No receiver status or RF path was contacted and no raw document persisted.

## Unauthorized claims

- No legitimate RF inventory exists on the Internet.
- Any linked map, API, repository or receiver is unavailable or illegitimate.
- Any receiver would fail Gate G1 observability or pair detectability.
- Any satellite is emitting, observable or absent.

## SHOCK

Search relevance is not inventory authority. The search successfully found
pages rich in the words *API*, *receiver* and *directory*, yet those pages
mostly described software or adjacent radio databases. Even an official
receiver page did not expose the temporal and set-completeness semantics needed
to interpret selection neutrally.

The missing object is not another endpoint. It is an operator-bound, expiring,
machine-readable statement of the endpoint population from which status
qualification may select. Until such an object is observed, moving directly
from search results to remembered Kiwi endpoints would reinstate the hidden
selection that Gate G1.2 removed.

## Receipt and stop

The strict JSON Lines receipt is
`session_receipts/g1_3_2_search_outcome_1.jsonl`, SHA-256:

```text
0725da4aef18baab5f155904b282d9236112a8bc0a4198c338180d28e5295295
```

It contains search URL lists, clause receipts and artifact hashes, but no
response bodies, receiver status or RF data.

Gate G1.3.2 stops here. Gate G2 remains blocked because no inventory mechanism
was admitted.
