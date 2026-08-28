# PIE DOY223 held-out observer prospective plan

## Frozen status

```text
PIE_OBSERVER_PRIMARY_PLAN_FROZEN
PRIMARY_DOY223_UNOPENED
```

This is a prospective proof design, not an executor or measurement authority.
It creates no new gate. It binds the already selected PIE100USA geometry and
the independently qualified DOY221 signal family to exactly one still-sealed
DOY223 logical product.

## Physical question and information gain

Can the frozen broadcast-orbit prediction for G22 relative to G30 predict a
continuous ionosphere-free carrier-phase coordinate at PIE, an observer not
used by the GOLD/NLIB development and replication results, better than one
prediction-frozen affine null and three wrong-orbit alternatives?

A positive held-out preference would test transfer to new hardware and
geography. A valid negative could damage the orbital model because the sensor
structure, time bound, transform and nuisance envelope are frozen first.

The geometry screen alone cannot answer this because it contains no
measurement. The DOY221 qualification cannot answer it because it parsed no
numerical observation value and had no orbit, null or score surface.

## Frozen observer, product and window

| Property | Value |
|---|---|
| observer | PIE100USA, 34.301506 deg, -108.118927 deg, 2347.711 m |
| receiver | SEPT POLARX5TR `4100427`, firmware `5.7.0` |
| antenna | ASH701945E_M NONE `CR520022114` |
| logical product | `PIE100USA_R_20262230000_01D_30S_MO.crx.gz` |
| date/time system | 2026-08-11 / GPS DOY223 |
| raw window | 05:42:00--06:51:00 GPS, inclusive |
| cadence/count | 30 s / 139 epochs |
| witness prefix | raw indices 0--78, 79 epochs |
| held-out suffix | raw indices 79--138, 60 epochs; starts 06:21:30 GPS |
| ambiguity anchor | raw index 0 only |

The preexisting CDDIS HEAD described 3,112,422 bytes, ETag
`"2f7de6-658ce9f13e195"` and last modification 2026-08-12 00:25:15 GMT.
Those fields are descriptive, not artifact identity. A future authorized
materialization must compute the complete SHA-256 before any header or record
decode. GSSC is the sole predeclared body transport; it may attempt the same
logical product at most twice for timeout or interrupted transport before a
complete hash exists. There is no retry after hashing or decoding and no
fallback product, station, date or window.

## Frozen coordinate

For each satellite `s`, convert L1C/L2W cycles to the ionosphere-free phase
range:

```text
P_s(t) = alpha * lambda_L1 * L1C_s(t)
       + beta  * lambda_L2 * L2W_s(t)

alpha =  2.5457277801631601
beta  = -1.5457277801631601

Q(t) = P_G22(t) - P_G30(t)
Z(t) = Q(t) - Q(t_0)
```

The same grid, target-minus-reference order and sample-zero anchor apply to
the orbital model and every null. The anchor removes one constant ambiguity.
There is no fitted constant, receiver rate, free time phase, time warp,
interpolation, gap bridging, prefix fit or suffix refit.

## Measurement and detectability admission

The future primary may be scored only if all structural clauses pass:

- the exact 139-epoch grid is present and every event flag is normal;
- actual event-time deviation is no more than 15 s from the frozen grid;
- L1C, L2W, C1C and C2W are present for G22 and G30 at every epoch;
- both phase LLIs are blank or zero throughout;
- the receiver/antenna/header identity and TIME OF LAST OBS cover the window;
- no unsupported scale, time or frequency transform is present;
- every value needed by the declared transforms is finite.

Numerical cycle continuity is model-blind. For each satellite, all 137 second
differences of

```text
lambda_L1 * L1C - lambda_L2 * L2W
```

must have magnitude no greater than `0.09514683639918244 m`, half the shorter
used carrier wavelength. A structural failure, nonzero LLI, abnormal epoch or
geometry-free violation is `MEASUREMENT_INVALID`.

The same-path hardware/multipath witness is also frozen. For each satellite:

```text
H_s(t) = anchor(IF_phase_s(t) - IF_code_s(t))
```

using L1C/L2W phase and C1C/C2W code with the same ionosphere-free weights.
Its full-window peak-to-peak must not exceed `1,250 m`. This deliberately wide
limit exceeds one 1.023 Mcps code-chip range after ionosphere-free weighting;
it is not learned from DOY223 and cannot alter a score. Missing witness values
make the measurement invalid. A complete finite witness over the fixed limit
is `NOT_DETECTABLE`, not an orbital result.

## Frozen hypotheses and envelope

The hypotheses are:

1. broadcast G22 relative to the fixed G30 reference;
2. a zero-intercept affine null with rate `-343.3209190383492 m/s`, derived
   only from the target prediction before observation;
3. wrong-orbit G01, G14 and G17, each replacing G22 while G30 stays fixed.

The prior geometry envelope contained an unwitnessed 4 m hardware term. This
plan does not inherit it. The fixed 1,250 m per-satellite code-phase rule gives
a conservative 2,500 m one-model target-minus-reference term and 5,000 m
pairwise contribution.

| Quantity | Frozen value m p-p |
|---|---:|
| affine controlling separation | 190,232.341335 |
| revised one-model physical envelope | 3,949.910439 |
| revised pairwise decision guard | 7,899.820878 |
| remaining physical margin | 182,332.520457 |

Every other event-time, broadcast-orbit, antenna, satellite-clock,
station/EOP/relativity, higher-order-ionosphere, troposphere and RINEX
quantization term remains exactly as in the geometry receipt. Event-time is
propagated with direct `t +/- 15 s` trajectories, not a local slope.

## Scoring and outcomes

Only the 60 held-out epochs are scored. For each frozen hypothesis, compute
the peak-to-peak and RMS of `Z_observed - Z_model`; no nuisance parameter is
fit. Ordering is peak-to-peak, then RMS, then frozen hypothesis name. A model
is preferred only when the runner-up minus best peak-to-peak residual is
strictly greater than `7,899.8208783974924 m`. Otherwise the result is
`AMBIGUOUS`.

Allowed terminal outcomes are:

```text
PRIMARY_ARTIFACT_MATERIALIZATION_FAILED
PRIMARY_DESCRIPTION_ERROR
MEASUREMENT_INVALID
NOT_DETECTABLE
PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED
FROZEN_AFFINE_NULL_PREFERRED
WRONG_ORBIT_G01_PREFERRED
WRONG_ORBIT_G14_PREFERRED
WRONG_ORBIT_G17_PREFERRED
AMBIGUOUS
```

The maximum positive claim is held-out-station confirmation for this exact
orbit, signal family, observer and window. It is not independent satellite
identity, orbit recovery or a claim about other stations or dates.

## Access and stop boundary

This plan issued zero network requests, opened zero DOY223 headers and payload
bytes, accessed zero primary values and produced zero orbital scores. It does
not include an executor.

The next maximum work, after review, is an offline exact-hash prediction seal
using the already frozen DOY223 broadcast-navigation authority. The primary
must remain unopened. Detector/executor construction and observation access
require later, separate review.
