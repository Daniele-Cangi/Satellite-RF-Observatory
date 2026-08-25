# G22/G30 short-window qualification and held-out primary plan

Status: `FROZEN_BEFORE_OBSERVATION_PRODUCT_DISCOVERY`.

The machine-readable experiment-specific manifest is implemented by
`gnss_phase_short_window_plan.py`; its canonical SHA-256 is
`0068385ef4aaf1014f0211efaa47da52da8c5fb18cf51377f4812434fd2b5f3c`.
It is bound to duration receipt SHA-256
`a81be2ddfb8d9455915118c74281f93dbf4919da3c140d58e18ebc4ccb4cee49`.

This is the proof boundary for the 30-minute held-out continuous-phase route.
It is not a new gate and does not reopen or repair the rejected DOY 216
artifact.

```text
Physical question:
Can a qualified 69-minute G22/G30 continuous-phase measurement prefer the
frozen orbital prediction on a distinct, still-unopened primary date?

New information produced by the future vertical:
Whether the actual GOLD/NLIB phase coordinate is measurement-valid and whether
its held-out suffix prefers G22 over a prefix-affine null and the frozen
jointly-visible alternative orbits.

Why the existing experiment cannot answer it:
The duration sweep proves model-only physical availability. It contains no
observation and assigned no qualification or primary roles.

Minimum experiment:
One independent qualification date and one later primary date, fixed
GOLD/NLIB and G22/G30, 139 raw epochs, unchanged physical envelope, one
model-blind health qualification, then one zero-retry held-out comparison.

Stop condition:
Stop after qualification. Primary access requires a separate review and is
forbidden if any qualification clause fails.
```

## Frozen role selection

| Role | Date | Raw GPS window | Reason | Access |
| --- | --- | --- | --- | --- |
| qualification | DOY 217 / 2026-08-05 | 05:54:00--07:03:00 | largest remaining margin at the shortest frozen duration | not discovered; next review may authorize only this date |
| primary | DOY 220 / 2026-08-08 | 05:42:00--06:51:00 | largest four-link elevation guard at the shortest frozen duration | sealed, undiscovered and unauthorized |

The selection used only broadcast geometry and the exact duration-sensitivity
receipt. It did not use product availability, headers, observation values or
the DOY 216 gap locations. No reserve is assigned: a qualification failure
does not authorize trying another date.

The predeclared locator names are the GOLD00USA and NLIB00USA daily 30-second
mixed-observation products for each date. A locator is not an artifact
identity. Byte count and SHA-256 remain unknown until a separately authorized
complete-file materialization.

## Frozen partition

- cadence: 30 seconds;
- raw interval: 139 epochs, 69 minutes elapsed;
- continuous phase feature: raw indices 1--137, 137 epochs;
- calibration prefix: raw indices 1--77, 77 epochs;
- held-out confirmation: raw indices 78--137, 60 epochs / 30-minute budget;
- no interpolation, gap bridging or suffix refit;
- no free time phase.

The qualification and primary windows are distinct. Qualification can test
measurement capability, but it cannot fit, change or select a primary
threshold, nuisance family, null or window.

## Measurement and witness clauses

The coordinate is ionosphere-free continuous carrier phase in meters:

```text
IF = 2.5457277801631601 * L1C_m
   - 1.5457277801631601 * L2W_m

Y = (GOLD_G22 - GOLD_G30) - (NLIB_G22 - NLIB_G30)
```

No time derivative is taken. Qualification requires all 139 epochs on both
stations, L1C/L2W on all four links, zero LLI, an exact 30-second grid and
header coverage through the frozen stop. Receiver and antenna declarations
must match the already frozen GOLD/NLIB configuration.

Geometry-free phase health is evaluated without an orbital prediction, using
the already frozen maximum absolute second-difference limit of
`0.09514683639918244 m`. C1C/C2W remain same-path code witnesses: each link
must reach 95% presence and must be present at raw indices 1, 77, 78 and 137.
They may not correct the phase score. S1C/S2W remain optional diagnostics.

Qualification success authorizes only a later primary-plan seal review.
Qualification failure closes this role pair. It does not select a substitute
date or permit primary access.

## Frozen hypotheses and decision rule

Every hypothesis receives the same samples, ionosphere-free transform,
station/satellite differencing, prefix and held-out interval.

- orbital hypothesis: broadcast G22 relative to G30;
- non-orbital null: zero geometric curve plus the same prefix-only affine fit;
- alternative-orbit hypotheses: G01, G14 and G17 relative to G30.

For each hypothesis, only a constant and rate are fit on the 77-epoch prefix.
Held-out peak-to-peak and RMS residuals are then calculated with no refit. The
primary orbital calibration residual must not exceed the frozen one-model
envelope `1192.1168692918313 m`; otherwise the outcome is `NOT_DETECTABLE` and
the held-out comparison is not evaluated.

A hypothesis is preferred only when its held-out peak-to-peak residual beats
every alternative by more than the frozen pairwise decision guard
`2384.2337385836627 m`. The controlling predicted separation is
`8857.431880665245 m` against G01, leaving the previously frozen physical
margin `6473.198142081582 m`.

Allowed future primary outcomes are:

```text
MEASUREMENT_INVALID
NOT_DETECTABLE
ORBITAL_MODEL_PREDICTIVELY_PREFERRED
PREFIX_AFFINE_NULL_PREFERRED
WRONG_ORBIT_G01_PREFERRED
WRONG_ORBIT_G14_PREFERRED
WRONG_ORBIT_G17_PREFERRED
AMBIGUOUS
```

Only `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` may authorize the corresponding
claim, and that claim remains below satellite identity on the project claim
ladder.

## Access boundary

At this freeze point:

- observation products discovered: zero;
- observation headers opened: zero;
- observation payload bytes accessed: zero;
- observation values accessed: zero;
- primary access: forbidden.

The maximum next action, not authorized by this plan itself, is bounded
discovery and complete-file hashing of only the DOY 217 qualification pair,
followed by structural and model-blind phase-health qualification with zero
persisted observation values. The primary requires a later, separate review.
