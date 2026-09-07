# DRAO labelled-forward geometry scope

This scope is frozen before materializing its five broadcast-navigation
inputs. It creates no gate and authorizes no observation-product query,
selection, header, payload, value, decoder or score.

## Physical question

Does one orbit-only selected DRAO window contain six predeclared GPS orbital
curves whose held-out ensemble-centred dynamics remain distinguishable from a
prefix-affine null and time-reversed geometry under the conservative historical
DRAO screening guard?

## New information

The screen can identify one real orbital geometry for a later
model-conditioned forward measurement. Unlike the closed inverse route, it
does not require the receiver product to contain exactly six or seven total
tracks.

## Bounded observer and dates

The only observer is the already documented station:

```text
DRAO00CAN / DOMES 40105M002
latitude 49.322600 deg
longitude -119.625000 deg
height 542.0 m
```

The only model-input dates are the five consecutive GPS days immediately
after the closed DOY233 primary:

| DOY | GPS date | NOAA broadcast-navigation input |
|---:|---|---|
| 234 | 2026-08-22 | `brdc2340.26n.gz` |
| 235 | 2026-08-23 | `brdc2350.26n.gz` |
| 236 | 2026-08-24 | `brdc2360.26n.gz` |
| 237 | 2026-08-25 | `brdc2370.26n.gz` |
| 238 | 2026-08-26 | `brdc2380.26n.gz` |

No station or date may be substituted after execution. Navigation files are
ephemeris inputs, not receiver observations; they are hashed, parsed in RAM
and destroyed after compilation.

## Geometry and partition

- GPS broadcast orbit only;
- 30 s grid;
- 139 epochs per window;
- prefix indices 0--78;
- held-out indices 79--138;
- candidate starts sampled every ten epochs (five minutes), beginning at GPS
  midnight;
- complete-window elevation at least 15 deg under direct trajectory
  evaluation at `t - 15 s`, `t` and `t + 15 s`;
- finite broadcast position at every epoch;
- at least six jointly visible healthy satellites;
- every six-satellite combination is evaluated from orbit geometry only;
- one highest-margin codebook is retained per day, then at most three daily
  winners are ranked globally.

The winning PRNs are frozen before any later observation-product access.
Additional receiver tracks will be descriptive and cannot invalidate or enter
the forward score. A missing or invalid required PRN remains fatal.

## Coordinate, nulls and nuisance

For each six-PRN codebook, station ranges are ensemble-centred at every epoch.
Every family then receives the same prefix-only constant and rate per centred
track. There is no suffix refit, free time phase, interpolation or time warp.

The orbit-only separations are:

1. frozen labelled broadcast-orbit geometry versus prefix-affine-only;
2. frozen labelled broadcast-orbit geometry versus the same curves with event
   ordering reversed inside the complete window.

The smaller held-out maximum per-track peak-to-peak separation controls. This
tests orbital temporal structure, not independent PRN identity.

## Conservative screening envelope

The historical DRAO guard remains `B = 7339.701234647398 m`. It is a screening
ceiling, not measurement admission for a new date. Direct `+/-15 s` trajectory
perturbations must each fit inside `B` after the same prefix projection.

A sufficient screening condition is:

```text
controlling exact null separation > 3 B
robust lower margin = controlling exact null separation - 3 B > 0
```

The three guards allow the correct model to worsen by `B`, the null to improve
by `B`, and still require a preference greater than `B`. A selected cell still
needs a separate date/codebook-specific physical-envelope audit before any
prospective measurement plan.

## Outcome and stop

The only outcomes are:

```text
DRAO_LABELLED_FORWARD_GEOMETRY_SHORTLISTED
NO_FORWARD_LABELLED_GEOMETRY_ADMITTED
```

Even a positive screen selects no RINEX observation product and freezes no
primary. Stop after the orbit-only shortlist. Do not query whether a matching
observation artifact exists.

The maximum future positive claim is
`ORBITAL_MODEL_PREDICTIVELY_PREFERRED` inside the predeclared labelled
coordinate. Satellite identity is model-conditioned and not independently
established.
