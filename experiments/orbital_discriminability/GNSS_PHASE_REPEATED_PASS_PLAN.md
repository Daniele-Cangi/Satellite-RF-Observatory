# G22/G30 distinct-pass replication

Status: FROZEN BEFORE OBSERVATION PRODUCT DISCOVERY.

This is a new physical experiment, not a gate and not a second score of the
consumed DOY 220 measurement.

## Scientific boundary

Physical question:

Can the frozen broadcast G22-relative-G30 prediction be preferred again on a
distinct, still-unopened pass measured by the same two independent hardware
roots?

New information produced:

Repeated-pass consistency across a new date, pass geometry and observation
artifact.

Why the completed primary cannot answer it:

DOY 220 contains only one pass realization. Its positive outcome cannot
establish repeatability and it will not be reopened or rescored.

Minimum experiment:

One one-shot GOLD/NLIB observation on DOY 219, using the same continuous
ionosphere-free carrier-phase coordinate, prefix-only nuisance, null families,
measurement clauses and no-retry semantics. DOY 218 remains sealed and is not
a retry.

Stop condition:

Stop after this plan and the DOY 219 model prediction are sealed. A separate
review is required before even discovering an observation product.

## Alternatives considered

| Route | New independence | Important shared cause | Decision |
| --- | --- | --- | --- |
| same roots, distinct pass | date, pass geometry, artifact | station pair, receiver families, scorer | selected: direct repeatability with the fewest new assumptions |
| new station pair | hardware and geography | GNSS signal family and scorer | deferred: stronger later generalization but requires new discovery and qualification |
| new target/reference pair | spacecraft pair and orbital signature | station pair and scorer | deferred: changes the physical hypothesis before repeatability is tested |

The selected route cannot establish independence from a GOLD/NLIB-specific
systematic. That limitation is part of the claim scope.

## Outcome-blind role selection

The pre-outcome diagnostic ranking was DOY 220, 219, 218, 217, ordered by
joint four-link elevation guard, then remaining physical margin, then date.
DOY 220 is consumed by the primary and DOY 217 by qualification. The first
eligible unopened date is therefore DOY 219. This rule uses neither product
availability nor observation information.

| Role | Date | Raw GPS window | Held-out start | Access |
| --- | --- | --- | --- | --- |
| distinct-pass replication | DOY 219 / 2026-08-07 | 05:46:00--06:55:00 | 06:25:00 | sealed, undiscovered, unauthorized |
| sealed reserve | DOY 218 / 2026-08-06 | 05:50:00--06:59:00 | 06:29:00 | sealed, not a retry |

## Frozen physical coordinate

- stations: GOLD00USA and NLIB00USA;
- target/reference: G22/G30;
- core fields: L1C and L2W;
- ionosphere-free coefficients: 2.5457277801631601 and
  -1.5457277801631601;
- signed order: (GOLD G22 - GOLD G30) - (NLIB G22 - NLIB G30);
- 139 raw epochs at 30 seconds;
- 137 feature epochs;
- 77-epoch calibration prefix;
- 60-epoch held-out suffix;
- no derivative, interpolation, gap bridging, free time phase or suffix refit.

## Frozen model and nulls

Every hypothesis receives the same coordinate and constant-plus-rate nuisance
fit on the 77-epoch prefix only:

- broadcast G22 relative to G30;
- zero-geometry prefix-affine null;
- G01, G14 and G17 relative to G30.

For DOY 219, the frozen model-only bounds are:

| Quantity | Value |
| --- | ---: |
| one-model calibration envelope | 1,188.851495144414 m |
| pairwise decision guard | 2,377.702990288828 m |
| controlling G01 separation | 8,986.714337965008 m |
| remaining physical margin | 6,609.011347676180 m |

The larger DOY 218 margin does not override the pre-outcome guard-first
selection rule.

## Measurement admission

The later one-shot observation must satisfy the same clauses as the first
primary:

- all 139 epochs at both stations on the exact 30-second grid;
- L1C and L2W on all four links;
- zero LLI on both phase fields;
- TIME OF LAST OBS covering the frozen window;
- receiver and antenna configuration matching the qualified path;
- geometry-free second-difference no greater than
  0.09514683639918244 m;
- C1C and C2W present on at least 95 percent of each link and at raw indices
  1, 77, 78 and 137.

S1C and S2W remain optional. Code witnesses cannot correct the phase score.

## Outcome and claim semantics

A positive result is ORBITAL MODEL REPEATED PASS PREFERRED. It authorizes only
the claim that the frozen orbital preference occurred on two distinct
GOLD/NLIB G22/G30 passes.

Other admissible outcomes are MEASUREMENT INVALID, NOT DETECTABLE,
PREFIX AFFINE NULL PREFERRED, one of the three named wrong-orbit preferences,
or AMBIGUOUS.

No outcome authorizes general GNSS identity, catalog-wide identification,
unconstrained orbit determination or independence from station-pair
systematics.

## Access and retry boundary

At freeze: zero observation products discovered, zero headers, zero payload
bytes and zero values. The future execution, if separately authorized, permits
one attempt per predeclared DOY 219 locator, with no endpoint or date
substitution. DOY 218 cannot be opened as a consequence of a DOY 219 failure.
