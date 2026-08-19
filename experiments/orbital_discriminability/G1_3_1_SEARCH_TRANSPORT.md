# Gate G1.3.1 — frozen independent-query transport

## Correction boundary

Gate G1.3 failed because one bundled search response erased per-query result
membership and order. Gate G1.3.1 corrects only that descriptive transport:

```text
query 1 -> invocation 1 -> ordered URL list 1 -> hash 1
query 2 -> invocation 2 -> ordered URL list 2 -> hash 2
query 3 -> invocation 3 -> ordered URL list 3 -> hash 3
query 4 -> invocation 4 -> ordered URL list 4 -> hash 4
```

It performs no search. The consumed G1.3 outcome and its receipt remain
unchanged.

## Frozen contract

- the parent G1.3 plan hash is fixed;
- the same four queries execute in the same order;
- each invocation contains exactly one query;
- each invocation has a distinct identity;
- provider order is retained, never reconstructed by relevance;
- at most five unique public HTTP(S) document URLs enter each receipt;
- fragments and credential-bearing URLs are refused;
- a successful empty result receives the canonical empty-list hash;
- a search error carries no stable URL set and cannot support absence;
- raw search responses are not persisted;
- retry, result-page access, `/status` and RF are all zero.

Only after all four independent receipts validate may the unchanged G1.3
round-robin selector determine candidate document URLs.

## Outcome

The offline checkpoint is:

```text
SEARCH_TRANSPORT_FROZEN
```

This means the missing receipt shape has been specified and synthetic responses
can materialize it. It does not claim that a live search provider has produced
valid receipts or that an inventory exists.

```text
parent G1.3 plan:  cb0f8e1cf24b39b4d17a6d85c13c0e3715deb4df0100ecf3c9eeb14c82732d12
G1.3.1 plan hash: 11a1b8dc3ec6863da406d64364f7605b82fd5a806b6e72005e84640a881c279c
```

## Stop

Gate G1.3.1 stops before network activity. A later, explicit authorization may
consume exactly four independent search invocations with zero retry. Any
bundling, query change, additional page access or relevance-based substitution
invalidates that execution.
