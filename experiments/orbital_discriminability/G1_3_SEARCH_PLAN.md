# Gate G1.3 — frozen bounded inventory search

## Question and authority

Gate G1.3 may perform one bounded Internet search for an actually
operator-authorized, machine-readable inventory mechanism satisfying Gate
G1.2. It searches for inventory routes, not receivers. It may read search
results, operator documentation and at most one inventory artifact per
candidate. It may not request `/status`, SND, IQ, waterfall, audio or RF.

## Frozen query surface

Exactly four search queries are issued once, in this order:

1. `public SDR receiver directory API machine readable`
2. `KiwiSDR public receiver directory API official`
3. `OpenWebRX receiver directory API official`
4. `WebSDR server list machine readable API official`

At most five ordered result URLs are retained per query. Their canonical list
hash persists; the search response body does not. The complete four-query
surface must materialize before a negative result is allowed.

## Candidate selection

At most six distinct candidate mechanisms may be audited. Selection is fixed
before page inspection: take result rank one from each query in frozen query
order, then rank two from each query, continuing round-robin until six unique
URLs are retained or results are exhausted. Candidate identifiers are derived
from those URLs. Every selected URL must receive an audit; it cannot be
substituted after inspection. Earlier F2 endpoints, browser history and the
interactive Kiwi token path are forbidden.

For each candidate, at most two documents and 1 MiB per document may be read:

- one operator/automation/schema document;
- one inventory artifact linked by that document.

The timeout is 15 seconds and retry is zero. Raw documents are hashed before
analysis and destroyed. Candidate qualification uses the unchanged G1.2
clauses: authority, documented automation intent, non-interactivity,
hash-before-parse, TTL through the 120-second qualification budget, schema,
complete declared scope, deterministic endpoint-set binding, zero persistence
and zero RF.

## Error and stop semantics

- `LEGITIMATE_INVENTORY_FOUND`: at least one observed current-session
  mechanism satisfies every G1.2 clause. This still does not admit a receiver.
- `NO_LEGITIMATE_INVENTORY_FOUND`: every frozen query completed and every
  retained candidate was evaluable but refused. The claim is limited to this
  search surface.
- `INVENTORY_SEARCH_INCOMPLETE`: a search or candidate qualification error
  prevents the bounded negative claim.

No candidate is promoted because it is convenient, large or familiar. Search
or description errors never become physical or capability rejection.

## Frozen budgets

```text
queries:                       4
results per query:             5
candidate mechanisms:          6
documents per candidate:       2
maximum document size:         1 MiB
document timeout:              15 s
retry:                         ZERO
receiver /status requests:     ZERO
RF requests:                   ZERO
persistent inventory catalog:  ZERO
```

The frozen plan hash is:

```text
cb0f8e1cf24b39b4d17a6d85c13c0e3715deb4df0100ecf3c9eeb14c82732d12
```

Any query, limit, selection rule or retry change creates a new gate.
