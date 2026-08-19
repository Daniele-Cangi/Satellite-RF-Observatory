# Gate G1.2 — frozen inventory-mechanism scope

## Question

Gate G1.2 asks one offline question:

```text
what must a current-session inventory receipt prove before its endpoints may
enter status-only capability qualification?
```

It does not ask which receiver to choose. It performs no discovery, status
request, RF acquisition or browser interaction and creates no catalog.

## Unit under evaluation

The unit is one bounded inventory mechanism, not an endpoint and not a
capability offer. Its receipt must bind:

- an operator authority through an HTTPS origin, verified signature or
  authoritative DNSSEC domain;
- an explicit public machine-readable automation intent;
- a non-interactive route requiring no user gesture, browser state, CAPTCHA or
  replayed custom authorization;
- a bounded artifact hashed before parsing;
- a finite positive TTL no greater than 600 seconds and long enough to cover
  the frozen 120-second status-qualification budget;
- a named, versioned schema;
- a declared coverage scope complete for that scope;
- deterministic extraction of at most twenty endpoint identifiers and status
  routes, bound by a canonical endpoint-set hash;
- destruction of the raw inventory artifact after the receipt is formed;
- zero SND, IQ, waterfall, audio, spectrum or other RF activity.

An empty endpoint set can be meaningful only when the mechanism otherwise
proves complete coverage of its declared scope. A non-empty remembered set is
not current-session evidence.

## Frozen comparison

Four causally different forms are compared:

1. the observed interactive Kiwi directory artifact from G1.1;
2. endpoint memory inherited from earlier F2 gates;
3. a non-live contract fixture for an operator-published HTTPS manifest;
4. a non-live contract fixture for authoritative DNS service discovery.

The fixtures test the receipt shape. They do not assert that either route,
operator or endpoint exists on the public Internet.

## Outcome semantics

- `NO_LEGITIMATE_INVENTORY_MECHANISM`: no observed current-session mechanism
  satisfies every inventory clause;
- `INVENTORY_MECHANISM_ADMISSIBLE`: at least one observed current-session
  mechanism may materialize its declared endpoint scope for later status-only
  qualification.

Neither outcome admits a receiver. Capability admission remains
`NOT_EVALUATED`, and no outcome licenses RF activity.

## Frozen limits

```text
plan hash:                    95705011e73704a1ebe522c89e44dbd961d13a8968040e6dd579e53a9496f542
qualification budget:        120 s
maximum inventory TTL:       600 s
maximum endpoints:           20
required endpoint fields:    endpoint_id, status_route
retry:                        ZERO
network activity:             ZERO
RF activity:                  ZERO
persistent inventory:         ZERO
```

Changing the endpoint fields, extending the TTL or budget, increasing the
endpoint count or permitting retries is a new gate rather than a repair.
