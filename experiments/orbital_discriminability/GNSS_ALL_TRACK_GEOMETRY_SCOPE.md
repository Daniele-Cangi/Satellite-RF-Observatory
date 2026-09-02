# Bounded GNSS all-track geometry scope

This scope is frozen before materializing any broadcast-navigation product.
It creates no gate and authorizes no observation-product discovery, header,
payload, measurement value, decoder, primary selection or prospective plan.

## Physical question

Can one predeclared station/date cell produce exactly six continuously visible
GPS orbit tracks whose complete `6!` assignment family and prefix-affine null
remain distinguishable under the conservative historical real-data envelope?

## New orbital information

The preceding synthetic spike proved that an all-track identity-blind scorer
can work.  This screen tests whether the required six-track topology and
decision margin coexist in a real broadcast-orbit geometry before any
measurement is selected.

## Bounded station set

Coordinates and identifiers are reused unchanged from the official-IGS
metadata snapshot already frozen by the independent-pair geometry screen.
Receiver descriptions do not enter this orbit-only calculation.

| Station | Latitude deg | Longitude deg | Height m | DOMES |
|---|---:|---:|---:|---|
| DRAO00CAN | 49.322600 | -119.625000 | 542.0 | 40105M002 |
| ALGO00CAN | 45.955800 | -78.071368 | 200.8294485278988 | 40104M002 |
| WES200USA | 42.613336 | -71.493328 | 85.0 | 40440S020 |

No station may be added or substituted after the screen is run.

## Bounded date and orbit-authority set

The five consecutive GPS days immediately following the earlier DOY224--228
blind-assignment geometry scope are predeclared:

| DOY | GPS date | NOAA broadcast-navigation product |
|---:|---|---|
| 229 | 2026-08-17 | `brdc2290.26n.gz` |
| 230 | 2026-08-18 | `brdc2300.26n.gz` |
| 231 | 2026-08-19 | `brdc2310.26n.gz` |
| 232 | 2026-08-20 | `brdc2320.26n.gz` |
| 233 | 2026-08-21 | `brdc2330.26n.gz` |

Only those five NOAA daily broadcast-navigation products may be materialized.
They must be hashed, parsed in RAM and deleted after compilation.  They are
orbital-model inputs, not receiver observations.

## Frozen geometry and partition

- GPS only;
- 30 s cadence;
- 139 epochs per candidate window;
- prefix indices 0--78;
- held-out indices 79--138;
- minimum elevation 15 deg at direct `t - 15 s`, `t`, and `t + 15 s`
  trajectory evaluations;
- finite broadcast position required for the complete window;
- exactly six satellites must satisfy the complete-window rule;
- the candidate codebook is all six qualifying satellites, without target or
  reference selection;
- any seventh complete track makes the cell ineligible rather than permitting
  a PRN-conditioned subset.

The later structural admission rule, if separately authorized, must accept
all and only tracks that are structurally complete on the frozen grid without
using PRN identity, phase magnitude, residual, SNR or outcome.  A measured
complete-track count other than six is a measurement-admission refusal.

## Frozen hypothesis and nuisance family

- all `6! = 720` orbit-to-track bijections;
- one prefix-affine-only non-orbital null;
- per-epoch ensemble centering, with no privileged reference track;
- one constant and one rate for each centered track, fit on the prefix only;
- no suffix refit, free time phase, time warp, interpolation or
  candidate-dependent complexity.

For an exact orbital fixture the closest wrong assignment is determined by
the smallest prefix-projected pairwise orbit separation.  The affine-null
separation is the largest centered-track residual after the same prefix
projection.  The smaller of those two quantities controls the family.

## Conservative decision envelope

The historical AMC development guard remains
`B = 7339.701234647398 m`.  It is a conservative development envelope, not a
new measurement claim and not a transfer of AMC product validity.

The future scorer requires both an absolute fit no worse than `B` and a
winner-to-runner-up margin greater than `B`.  If the correct track family can
deviate by `B` and a wrong family can improve by `B`, a sufficient orbit-only
condition is therefore:

```text
exact controlling separation > 3 B
robust scorer-margin lower bound = exact separation - 3 B > 0
```

This stricter three-guard condition replaces any informal use of a merely
positive exact separation.

## Deterministic selection and stop

For each station/day retain only its highest robust scorer-margin window.
Rank those daily winners by:

1. largest robust scorer-margin lower bound;
2. largest minimum direct-time-shifted elevation;
3. station identifier;
4. earliest day and window.

Retain at most three geometry candidates.  Stop with exactly one of:

- `ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED` when at least one
  exactly-six window passes the three-guard assignment and affine-null rule;
- `NO_ALL_TRACK_GEOMETRY_DISCRIMINATIVE` when exactly-six windows exist but
  none passes that rule;
- `NO_VALUE_BLIND_TRACK_INCLUSION_RULE` when no window has exactly six
  complete robustly visible satellites.

Even the positive outcome selects no qualification artifact or primary and
does not authorize observation access.
