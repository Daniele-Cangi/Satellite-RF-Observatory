# Post-DRAO change of abstraction

## Block

The closed DRAO result is not a geometry or measurement failure. The proof
required a complete physical envelope before selecting a qualification
product, while four of its clauses depend on product-level signal, format,
calibration or witness properties. The previous 95 percent code witness could
also leave six phase epochs without any bound.

## Information value

The six-track common-mode operator is now understood: a uniform per-track
peak-to-peak bound has gain at most two; a purely epoch-common receiver clock
cancels exactly; track-, signal- and channel-dependent errors remain. The
DOY231 orbital geometry remains positive and no observation was tested.

## Alternatives

1. Reopen DOY230/DOY231 or search another DRAO artifact for the same proof:
   rejected because the route is terminal and the causal order is unchanged.
2. Return immediately to public raw RF: rejected for now because the bounded
   set remains blocked by sample-zero UTC and independent-orbit provenance.
3. Change to phase second differences: physically interesting, but it changes
   the observable and requires a new noise/multipath detectability model before
   it can interpret a negative.
4. Stage DRAO admission: first retain the exact model-side envelope, then use
   one independent qualification to resolve product-dependent clauses, and
   freeze a distinct primary only afterward.
5. Stop independent transfer: valid, but leaves the existing real blind-orbit
   preference without a new observer/topology test.

## Selected physical path

Alternative 4 is the shortest path to new orbital information. It uses no new
station or inventory, does not reopen the failed roles and does not treat
qualification as a primary. The already frozen five-day orbit-only scope
leaves DOY232 followed by DOY233 as the only chronological unused pair.

```text
exact-hash DOY233 navigation
    -> retained nominal and t +/- 15 s six-track curves
    -> model-side common-mode envelope
    -> conditional complete-witness reserve
    -> if positive, review one DOY232 qualification only
    -> close product-dependent envelope
    -> only then consider freezing one DOY233 primary
```

This repairs the causal order, not the old plan. It creates no gate and makes
no claim that DRAO data exist or are adequate.
