# Gate G1.2 — inventory-mechanism audit

## Result

The offline comparison ends:

```text
NO_LEGITIMATE_INVENTORY_MECHANISM
```

No observed mechanism in the frozen evidence can produce a legitimate
current-session endpoint set. The result is not `NO_CAPABILITY_ADMITTED`:
receiver status, pass-specific qualification and RF remain `NOT_EVALUATED`.

## Comparison

| Mechanism | Basis | Result | Decisive reason | Maximum claim |
|---|---|---|---|---|
| G1.1 Kiwi directory page | observed artifact | refused | interaction/custom authorization, no documented automation intent, no TTL/schema/complete endpoint binding | the frozen route did not materialize a legitimate inventory in G1.1 |
| remembered F2 endpoints | remembered state | refused | no current artifact, authority, TTL or declared complete scope | earlier endpoint memory cannot support current selection or absence |
| operator HTTPS manifest | contract fixture | admissible in principle | all frozen receipt clauses represented | this receipt form could bind an operator-scoped inventory if actually materialized |
| authoritative DNS service discovery | contract fixture | admissible in principle | all frozen receipt clauses represented | this receipt form could bind a DNS-authoritative inventory if actually materialized |

The manifest and DNS fixtures are deliberately not ranked. They close the
same epistemic boundary through different authority mechanisms and neither is
a discovered public source.

## Clause attribution for the observed G1.1 artifact

| Clause | State | Evidence |
|---|---|---|
| current artifact basis | `SATISFIED` | frozen G1.1 response receipt |
| authority binding | `UNSATISFIED` | no HTTPS/signature/DNSSEC binding retained |
| automation intent | `UNSATISFIED` | no public machine-readable permission retained |
| non-interactive route | `UNSATISFIED` | user gesture and custom `x-kiwi-auth` required |
| artifact integrity | `SATISFIED` | 2,294 bytes hashed before parsing; SHA-256 `f59bd5d1…7b14` |
| temporal validity | `UNSATISFIED` | no inventory TTL retained |
| machine-readable schema | `UNSATISFIED` | interactive HTML is not a bounded endpoint schema |
| declared coverage | `UNSATISFIED` | scope and completeness were not materialized |
| deterministic endpoint binding | `UNSATISFIED` | zero endpoints because discovery stopped before the list |
| ephemeral artifact | `SATISFIED` | only receipt/hash retained |
| descriptive only | `SATISFIED` | zero receiver and RF requests |

The failure is at the inventory mechanism. It is neither a receiver rejection
nor evidence that a receiver was unavailable.

## Why HTTPS alone is insufficient

Transport identity cannot rescue an interactive selection boundary. An HTTPS
page that requires browser state or a custom token copied from page logic
still cannot establish unattended automation intent, a complete declared
scope or deterministic endpoint extraction. Conversely, authoritative DNS is
not sufficient without a documented service schema and automation policy.

## Receipt boundary

The receipt retains scalar descriptions, the source-artifact hash and a
canonical endpoint-set hash. It does not retain the source artifact or build a
persistent endpoint list. A later status request would need to bind its
endpoint identity to the ephemeral set before the latter is destroyed.

This is the smallest useful bridge:

```text
operator authority
  -> bounded current inventory artifact
  -> hash before parse + TTL + declared coverage
  -> ephemeral endpoint set and canonical set hash
  -> later status-only qualification
```

The bridge stops before capability or pass admission.

## Authorized claims

- The G1.1 directory response has artifact integrity but does not satisfy the
  frozen inventory-mechanism contract.
- Remembered endpoints cannot provide a current, selection-neutral inventory.
- An operator manifest and authoritative DNS represent two distinct receipt
  forms capable of satisfying the contract if they are actually materialized.
- Gate G1.2 performed no network, status or RF activity and created no catalog.

## Unauthorized claims

- Either contract-fixture route exists publicly.
- Any remembered endpoint remains live.
- No suitable Internet RF receiver exists.
- A receiver or pair satisfies Gate G1.
- Any candidate satellite is currently emitting or observable.

## SHOCK

Capability discovery is itself a measurement with lineage, selection scope
and expiry. Treating it as plumbing hides selection bias: a stale hand-picked
endpoint can make capability qualification look objective even though the
candidate set was never legitimately materialized.

The surviving primitive is not a source adapter or catalog. It is the narrow
requirement that the mechanism producing candidates must be receipted before
the candidates can be scored.

## Stop

Gate G1.2 stops offline. Gate G2 remains blocked. A later, separately reviewed
Gate G1.3 may search only for an actually operator-authorized machine-readable
inventory matching this receipt. It must be allowed to terminate
`NO_LEGITIMATE_INVENTORY_FOUND` and may not fall back to remembered endpoints,
browser-token replay or RF probing.
