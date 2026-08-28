# AMC DOY221 observer-replication prospective plan

## Frozen status

```text
AMC_OBSERVER_PRIMARY_PLAN_FROZEN
PRIMARY_DOY221_UNOPENED
```

This is a prospective proof design, not an executor or measurement authority.
It creates no new gate. It binds the already shortlisted AMC400USA geometry,
the value-blind AMC DOY222 structural qualification and exactly one still-sealed
DOY221 logical product.

## Physical question and information gain

Can the frozen broadcast-orbit prediction for G22 relative to G30 predict a
continuous ionosphere-free carrier-phase coordinate at AMC better than one
prediction-frozen affine null and three wrong-orbit alternatives?

This is an observer-and-pass replication of the positive PIE result. AMC has a
distinct receiver serial, antenna, monument, clock, firmware and observing
pass. AMC and PIE nevertheless use the same SEPT POLARX5TR receiver family;
therefore a positive result tests transfer across observer geometry and physical
instances, not full receiver-design diversity.

The geometry screen alone contains no measurement. The AMC DOY222 qualification
parsed no numerical observation value and produced no orbit, null or score.

## Frozen observer, product and window

| Property | Value |
|---|---|
| observer | AMC400USA, 38.803125 deg, -104.524597 deg, 1911.3941 m |
| receiver | SEPT POLARX5TR `3013929`, firmware `5.6.0` |
| antenna | TPSCR.G5C NONE `1364-10065` |
| logical product | `AMC400USA_R_20262210000_01D_30S_MO.crx.gz` |
| date/time system | 2026-08-09 / GPS DOY221 |
| raw window | 05:41:30--06:50:30 GPS, inclusive |
| cadence/count | 30 s / 139 epochs |
| witness prefix | raw indices 0--78, 79 epochs |
| held-out suffix | raw indices 79--138, 60 epochs; starts 06:21:00 GPS |
| ambiguity anchor | raw index 0 only |

The preaccess GSSC directory described 3,415,979 bytes and modification time
2026-08-10 03:01:38. Its captured directory response has SHA-256
`1f30600686f3ae8e466bcc796e3538bcdf601d2d7e2d676f839357c320d600b5`.
The literal directory MD5 field `1` is not a checksum, and none of these fields
is artifact identity. A future authorized materialization must compute the
complete SHA-256 before any header or record decode. GSSC is the sole
predeclared body transport; it may attempt the same logical product at most
twice for timeout or interrupted transport before a complete hash exists.
There is no retry after hashing or decoding and no fallback product, station,
date or window.

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

The same grid, AMC G22-minus-G30 order and raw-index-zero anchor apply to the
orbital model and every null. The anchor removes one constant ambiguity. There
is no fitted constant, receiver rate, free time phase, time warp, interpolation,
gap bridging, prefix fit or suffix refit.

## Measurement and detectability admission

The future primary may be scored only if all structural clauses pass:

- the exact 139-epoch grid is present and every event flag is normal;
- actual event-time deviation is no more than 15 s from the frozen grid;
- L1C, L2W, C1C and C2W are present for G22 and G30 at every epoch;
- both phase LLIs are blank or zero throughout;
- receiver, antenna, header identity and TIME OF LAST OBS cover the window;
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
it is not learned from DOY221 and cannot alter a score. Missing witness values
make the measurement invalid. A complete finite witness over the fixed limit
is `NOT_DETECTABLE`, not an orbital result.

## Frozen hypotheses and envelope

The hypotheses are:

1. broadcast G22 relative to the fixed G30 reference;
2. a zero-intercept affine null with rate `-410.277100928825 m/s`, derived only
   from the target prediction before observation;
3. wrong-orbit G01, G14 and G17, each replacing G22 while G30 stays fixed.

The prior geometry envelope contained an unwitnessed 4 m hardware term. This
plan does not inherit it. The fixed 1,250 m per-satellite code-phase rule gives
a conservative 2,500 m one-model target-minus-reference term and 5,000 m
pairwise contribution.

| Quantity | Frozen value m p-p |
|---|---:|
| affine controlling separation | 162,247.192926 |
| revised one-model physical envelope | 3,669.850617 |
| revised pairwise decision guard | 7,339.701235 |
| remaining physical margin | 154,907.491692 |

Every other event-time, broadcast-orbit, antenna, satellite-clock,
station/EOP/relativity, higher-order-ionosphere, troposphere and RINEX
quantization term remains exactly as in the geometry receipt. Event time is
propagated with direct `t +/- 15 s` trajectories, not a local slope.

## Scoring and outcomes

Only the 60 held-out epochs are scored. For each frozen hypothesis, compute
the peak-to-peak and RMS of `Z_observed - Z_model`; no nuisance parameter is
fit. Ordering is peak-to-peak, then RMS, then frozen hypothesis name. A model
is preferred only when the runner-up minus best peak-to-peak residual is
strictly greater than `7,339.701234647398 m`. Otherwise the result is
`AMBIGUOUS`.

Allowed terminal outcomes are:

```text
PRIMARY_ARTIFACT_MATERIALIZATION_FAILED
PRIMARY_DESCRIPTION_ERROR
MEASUREMENT_INVALID
NOT_DETECTABLE
AMC_HELD_OUT_ORBITAL_MODEL_PREFERRED
FROZEN_AFFINE_NULL_PREFERRED
WRONG_ORBIT_G01_PREFERRED
WRONG_ORBIT_G14_PREFERRED
WRONG_ORBIT_G17_PREFERRED
AMBIGUOUS
```

The maximum positive claim is independent-observer-and-pass replication for
this orbit signal family. It is not independent satellite identity, orbit
recovery, full receiver-family independence or a claim about other stations or
dates.

## Access and stop boundary

This plan issued zero network requests, opened zero DOY221 headers and payload
bytes, accessed zero primary values and produced zero orbital scores. It does
not include an executor.

The next maximum work, after review, is an offline exact-hash prediction seal
using the already frozen DOY221 broadcast-navigation authority. The primary
must remain unopened. Executor construction and observation access require
later, separate review.
