# Raw integer feasibility: wide-lane structure, no admitted fixing

The retained data show useful wide-lane structure, but do not yet support an
admitted integer constraint for an orbital solution. This is not a failed
orbit reconstruction or evidence that the raw observations are useless.

One execution, producer `91582d5b6c926f3ff4f9ef40a582b755fc7dc11b`, through the
existing `real_phase` CLI. All training float/integer hypotheses precede held
RF scoring. No target orbit/clock/product, target OSB, prior state or new data
was read. G12's already-exposed raw observations were used explicitly; no
G12 state was estimated. Input/source hashes and every configuration are retained.

## Availability and complete denominators

Six receivers have supported raw C1C/C2W/L1C/L2W observations. All their declared
phase shifts are zero and their ambiguity wavelength factors are unit. YELL
remains unsupported because of the original event/header change. Blank/zero
LLI permits this conditional test; it does not prove full-cycle continuity.
The two input hashes are unchanged from the retained extracts.

| Role | All DD configurations | No prefix ending at cut | Prefix but no contiguous held data | Held scored |
|---|---:|---:|---:|---:|
| G12/reference | 462 | 400 | 0 | 62 |
| Reference/reference controls | 4851 | 4572 | 28 | 251 |

The 5,313 configurations are correlated transformations sharing raw endpoints,
not 5,313 independent experiments. They retain every receiver pair and satellite
pair without selecting successful residuals. These are raw-signal diagnostics;
no target-dependent geometric/elevation admission or orbital uncertainty is
claimed. The two scalar models compare frozen constant means on the same held
sequence; neither is a prediction of full carrier range or an orbital state.

## Actual held comparison

| Descriptive quantity | G12/reference, 62 scored | Reference controls, 251 scored |
|---|---:|---:|
| Held mean nearest integer agrees with the TRAINING integer | 62/62 | 220/251 |
| Integer hypothesis has smaller held RMS than float mean | 34/62 | 135/251 |
| Median absolute training distance to nearest integer, cycles | .064702 | .080060 |
| Median training scatter RMS, cycles | .373431 | .383270 |
| Median held integer RMS, cycles | .459061 | .502696 |
| Median absolute held-minus-training mean, cycles | .093617 | .124719 |

The held-mean rounding is computed only after scoring as a descriptive stability
check, never to select or refit an integer. G12 support uses five receivers;
BRAZ has no target prefix before the fixed 10:30 cut. The 62 correlated agreements
are therefore an encouraging limited observation, not independent successes or
proof that those are the physically correct integers. The 31 control disagreements
remain visible, including departures up to 2.239 cycles from the frozen integer.
They may combine changes/slips, bias, multipath and short-prefix error; no cause
is attributed or repaired in this run. The maximum G12 held-mean departure is
.476897 cycles, close to a half-cycle decision boundary in the worst case.

## Why no integer is admitted

The wide-lane wavelength is .8619184003 m. The inherited four-channel weights
imply an individual DD MW sigma of 11.103225 cycles. These weights preserve the
historical IF 20 m code/20 mm phase scales; they are NOT measured raw-noise laws.
Even the longest prefix has conditional IID mean sigma 1.433420 cycles.

Under that fixed weighting scenario, the scalar delta-Q <= 4 set includes
**5-22 integers for every scored G12 configuration** and 5-32 for the reference
controls. No scored configuration has a unique integer in that scalar diagnostic set.
This is not a global correlated integer least-squares network solution and
does not exclude improvements from such a joint formulation.
This does not prove that the real data contain insufficient precision: the
observed scatter is much smaller than the assumed endpoint scale. Scatter
alone does not calibrate the constant link bias or temporal error of a mean.
No weights were lowered using these held results.

There are also two exact structural qualifications:

1. DD removes receiver/satellite-SEPARABLE fractional bias. If a remaining link
   bias is arbitrary, `MW_DD=N_W+b_DD+noise` has the exact invariance
   `(N_W+k,b_DD-k)`. All integers can then fit equally. A near-integer MW mean
   does not independently establish the required bias decomposition.
2. MW determines only `N1-N2`. The simultaneous integer shift `(N1+k,N2+k)`
   leaves it unchanged while shifting IF phase by **k*.1069533781 m**. Even a
   perfectly known wide-lane integer does not by itself fix the remaining phase
   level or remove the orbit bias-position ambiguity.

Synthetic tests recover a known wide-lane integer with separable fractional
terms, expose the free-bias invariance, and verify the remaining equal-integer
shift. Held-value poisoning preserves every frozen hypothesis and support rule.
A GF-null unflagged 77/60 slip remains a scored failure, not a repaired integer.

## Consequence

This route is worth continuing, but a full integer orbital fit is premature.
The next useful software work is a reference-only qualification of raw MW bias
and temporal stability, including the 31 disagreeing controls and long-baseline
receiver/satellite coupling. Its purpose is to establish an error model that can
discriminate wrong integer branches, rather than inherit the old IF weighting
as a raw-noise measurement or shrink it against G12's revealed outcome.

If that succeeds, test the remaining narrow-lane ambiguity jointly with RF
geometry/dynamics and excluded observations, without a target orbit prior.
Do not apply the current rounded hypotheses to production or label them a
physical integer fix. S2 and independent confirmation remain open. No historical
result, prospective boundary, mask or uncertainty floor has changed.

See [method and reproduction](README.md), [frozen predictions](predictions-before-scoring.json.gz)
and [held scores](scores.json.gz).
