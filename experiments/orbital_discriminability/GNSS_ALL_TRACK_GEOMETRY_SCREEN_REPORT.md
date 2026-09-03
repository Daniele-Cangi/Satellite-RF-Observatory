# Bounded GNSS all-track geometry screen

## Outcome

```text
ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED
```

One real broadcast-orbit geometry instantiates the six-track blind-assignment
mechanism with positive conservative margin.  This is an orbit-only result.
It selects no observation product, qualification artifact or primary, freezes
no prospective plan and authorizes no measurement or identity claim.

## Frozen scope

The scope was committed before any navigation access:

- stations: DRAO00CAN, ALGO00CAN and WES200USA;
- GPS DOY229--233 / 2026-08-17--21;
- 139 epochs at 30 s, with 79 prefix and 60 held-out epochs;
- direct `t - 15 s`, `t`, `t + 15 s` trajectory visibility;
- minimum elevation 15 deg on the complete window;
- exactly six complete GPS tracks;
- all 720 bijections and one prefix-affine null;
- ensemble common-mode removal and the same prefix-only constant/rate nuisance.

The complete candidate codebook is created by the geometry.  No target,
reference or PRN subset is chosen.  A seventh complete track makes a future
measurement ineligible rather than allowing the experiment to remove an
unhelpful identity.

## Why three guards are required

The historical AMC development guard is
`B = 7,339.701234647398 m`.  It is not a new ALGO measurement bound.  It is
used here as the one conservative real-data envelope requested by the
mechanism spike.

The future scorer accepts a best absolute residual no greater than `B` and
requires its advantage over the runner-up to exceed `B`.  In the conservative
case, the correct model residual can grow by `B` while the wrong-model
residual shrinks by `B`.  The orbit-only sufficient condition is therefore:

```text
exact separation > 3 B = 22,019.103703942194 m
robust scorer-margin lower bound = exact separation - 3 B
```

This closes a subtle weakness in a two-guard interpretation: two guards would
only keep the observed winner ahead of the runner-up, but would not guarantee
the scorer's additional one-guard preference clause.

## Complete sweep result

All 15 frozen station/day cells were evaluated.  Across their overlapping
30 s starts:

- `13,465` windows had exactly six robustly complete GPS orbit tracks;
- `3,403` also passed both the closest-assignment and affine-null three-guard
  requirements;
- every station and every day contributed at least one robust window;
- complete-track counts over the scope ranged from three to nine.

Thus the value-blind six-track topology is not an isolated numerical point,
although any concrete measurement must still prove that its structural track
count is exactly six.

## Ranked shortlist

The deterministic ranking retains each station/day's best window and ranks by
robust scorer margin, minimum shifted elevation, station and time.

| Rank | Station | DOY | Raw GPS window | Held-out start | Codebook | Exact controlling separation m p-p | Robust lower margin m | Minimum shifted elevation deg |
|---:|---|---:|---|---|---|---:|---:|---:|
| 1 | ALGO00CAN | 230 | 12:45:30--13:54:30 | 13:25:00 | G05/G15/G18/G20/G21/G29 | 71,119.527421 | 49,100.423718 | 15.555979 |
| 2 | ALGO00CAN | 229 | 12:49:30--13:58:30 | 13:29:00 | G05/G15/G18/G20/G21/G29 | 70,958.929479 | 48,939.825775 | 15.499855 |
| 3 | ALGO00CAN | 231 | 12:41:30--13:50:30 | 13:21:00 | G05/G15/G18/G20/G21/G29 | 70,767.805037 | 48,748.701334 | 15.612240 |

The same six-satellite family repeats about four minutes earlier each day,
as expected for GPS geometry.  That repetition is useful for a possible later
qualification/primary/reserve separation, but no role is assigned by this
screen.

The controlling runner is never the affine null:

- DOY230 and DOY231 are controlled by the G20/G29 swap;
- DOY229 is controlled by the G15/G21 swap;
- the affine-null maximum is about 203 km peak-to-peak and is substantially
  farther away.

The closest nonidentity result is not an approximation.  With the same six
model curves, ensemble centering is invariant to permutation.  Every wrong
bijection moves at least two tracks, and swapping the closest prefix-projected
pair attains the minimum possible maximum per-track residual.  A regression
enumerates all 719 wrong bijections and verifies this equality.

## Cross-station context

ALGO dominates on assignment margin, but its shortlist windows sit close to
the elevation floor.  The best DRAO cell has a smaller but still positive
three-guard margin of about `27.300 km` and a stronger minimum shifted
elevation of about `22.718 deg`.  The best WES2 cell has about `25.397 km`
margin and `21.161 deg` minimum elevation.  These alternatives remain in the
receipt; the top-three policy does not silently promote them over the frozen
ranking.

## Measurement boundary and residual blocker

The five NOAA RINEX 2.11 broadcast-navigation files were hashed, parsed in
RAM and deleted.  Their complete compressed and uncompressed hashes remain in
the receipt.  No GNSS observation locator, product, header, payload byte,
value or decoder was accessed.

The remaining blocker is structural and physical, not geometric.  Before a
prospective experiment can be frozen, one separately authorized qualification
artifact would have to prove on a distinct date:

1. all structurally complete GPS tracks enter without PRN or value selection;
2. exactly six complete L1C/L2W phase tracks survive the frozen window and
   segment rules;
3. event time, sample continuity, LLI, same-path code witnesses and receiver
   configuration are valid;
4. the ALGO-specific propagation, antenna and receiver-error family fits
   inside a predeclared bound no larger than the decision envelope;
5. receiver PRN labels remain sealed from the scorer until after the opaque
   score receipt is hashed.

A seventh complete measured track, a missing member, or an unbounded physical
term must stop admission.  The geometry result cannot be used to relax the
rule or select a convenient subset.

## Claim boundary

If a later held-out measurement passes, the maximum claim remains:

> Within one frozen six-orbit candidate set, held-out orbital dynamics assigned
> every admitted opaque track and the post-hash assignment was or was not
> concordant with the receiver's code labels.

This would not establish unconstrained orbit recovery, code-free RF identity
or hardware-independent confirmation.  The receiver's upstream code
correlator remains a non-independent witness.

## Reproducibility

- scope commit: `33dba523f8c7c599b36b487e943486ad276926e0`;
- compiler commit: `91eb9ac134a3388612f81929dce73f25bdce96ae`;
- compiler canonical SHA-256:
  `6c27a9d07032abc257a9d951b568c3a422f4e7d331c149dfbb7ef1941f2b4062`;
- manifest SHA-256:
  `345d5425bc05e13f9842d9b758f45f392155bedad05c6c8018bf7dface9121d3`;
- receipt bytes: `72,125`;
- receipt SHA-256:
  `09456cae2dcb97550f44a16e45d8cb4b0b5d28a19e0a5b3ef25893c45710089c`.

The strict result is
[`GNSS_ALL_TRACK_GEOMETRY_SCREEN_RECEIPT.json`](GNSS_ALL_TRACK_GEOMETRY_SCREEN_RECEIPT.json).
