# G12: localizing the rejected phase fit

## Decision

**The reference increments expose a clock-shape mismatch that the single
receiver-clock slope per arc cannot represent.** Correct the clock observation
model before adding orbital forces. This is a supported development direction,
not a diagnosed physical clock fault or an accepted reconstruction.

The [v4 shared fit](G12_DYNAMIC_FIT.md) remains rejected. This study replays its
two rejected phase variants without fitting anything, changing weights or
opening the target orbit/clock products. Its [result](results/g12_phase_diagnostic_v1.json)
retains all eight inherited arcs, eighty training intervals, forty station/arc
contrasts, matched references, missing slots and original failed branches.
The twenty-two historically rejected phase windows and other admission failures
remain in the inherited forty-window selection record. They are not substituted.

Three findings determine the next step:

1. Almost all phase incompatibility is a difference between the two adjacent
   interval residuals, rather than their mean. Independent G12-excluding
   references exhibit the same station-dependent pattern.
2. Subtracting that reference pattern leaves a mostly station-common component.
   It could contain satellite-clock curvature, trajectory/propagation error or
   shared reference-product errors. The decomposition does not distinguish them.
3. Extrapolating the observed reference-clock rate trend worsens the next
   interval: **28/40** cases, RMS **7.880 -> 10.845 mm/s**. Do not replace the
   constant drift by an automatically extrapolated quadratic clock.

## What was compared

The cohort is exactly the eight even-index, historically accepted short phase
arcs inherited by the rejected shared fit. At each of their five receivers,
replay the full geometric light time, Earth rotation, fitted local clocks and
ground coordinates, shared dynamic trajectory and current-geometry VMF3.
The reconstructed joint costs match v4 within 1e-5. Neither code-only fit nor
its different seventeen-arc cohort participates in this comparison.

For two adjacent 30-second phase-rate residuals `r1`, `r2`, define:

```text
u = (r1 + r2)/2                         mean residual rate
q = (r1 - r2)/2                         temporal half-difference
c = (median_reference_rate1 - median_reference_rate2)/2
d = q - c                              reference-subtracted diagnostic
common = mean_over_stations(d)          descriptive projection at each arc
spatial = d - common
```

Constant phase ambiguity and additive linear clock terms have zero second
difference. The complete model still contains clock-dependent receive times,
emission times and propagation; this algebra is not an exact theorem that all
physical clock effects cancel.

The original .02 m iid phase-endpoint weighting implies `Var(u)=sigma²/(2 dt²)`
and `Var(q)=3 sigma²/(2 dt²)`, with zero cross-covariance. The report obtains
those blocks from the original covariance transform, preserving endpoint
correlations. Thus the near-opposite residuals cannot be counted as eighty
independent curvature measurements.

## Numerical localization

All RMS values below are mm/s on the same forty station/arc contrasts.

| Quantity | Central | Central + J2 |
|---|---:|---:|
| Mean residual `u` | 0.00249 | 0.00232 |
| Temporal contrast `q` | 2.426 | 2.422 |
| Reference contrast `c` | 2.373 | 2.373 |
| Remaining `d` | 0.712 | 0.720 |
| Common remaining component | 0.702 | 0.712 |
| Spatial remaining component | 0.115 | 0.106 |
| VMF3 modeled temporal contrast | 0.0225 | 0.0225 |
| Common fraction of remaining squared norm | 97.4% | 97.8% |

Correlation between `q` and `c` is 0.958 / 0.957. This is a descriptive
cohort statistic, not a significance test: intervals, references and upstream
products are correlated, and historical admission is already exposed.
The small modeled VMF3 curvature is not an upper bound on atmospheric error.

The J2 temporal-contrast RMS by receiver is ALGO 3.881, DRAO 0.741,
STJO 0.711, AREQ 0.864, BOGT 1.945 and BRAZ 4.863 mm/s. ALGO contributes
eight contrasts; BRAZ contributes three. The report preserves receiver/time
values rather than turning these unequal denominators into station rankings.

The same-time reference controls retain **371** matched leave-one-reference-out
temporal contrasts and **one unsupported slot**: error RMS 0.171 mm/s, maximum
0.714 mm/s on the matched contrasts. Missing reference endpoints have explicit
unsupported slots rather than subset replacement.
These are relative consistency diagnostics using overlapping medians and
shared orbit/clock/atmosphere products. They do not bound absolute receiver
clock error, a common reference error or G12-specific propagation error.

An exact observation-model ablation changes only the middle receiver-clock
endpoint by `30*c` metres, keeping both outer endpoints, mean drift, shared
state and ground fixed. Its temporal contrast agrees with `q-c` to below
1.1e-8 m/s, including receive-time, light-time and atmospheric changes. This
checks the sign and magnitude of the clock-shape explanation. It is not a
refit, and its residuals receive no new acceptance label or p-value.

All target triad loss-of-lock flags are zero/blank; geometry-free phase second
differences remain in the result (RMS 0.00371 m, maximum 0.01432 m). Neither
observation rules out an unflagged discontinuity or proves a clock-only cause.

## Why a quadratic forecast is not the correction

For each of the same forty station/arcs, form two predictions solely from
reference increments `a1`, `a2`: constant `(a1+a2)/2`, and extrapolated linear
rate `2*a2-a1`. Only then evaluate the third reference increment `a3`.
No target future code, phase or geometry-free value is read by this study.

Both rules have forty evaluable cases. The linear-rate rule worsens 28;
maximum absolute error grows from 24.679 to 40.404 mm/s. These are forecasts
of the retained shared-product reference estimates, not independent clock
truth or a population error bound. They demonstrate that the measured
nonlinearity does not justify smooth quadratic extrapolation on this cohort.

## Concrete follow-up and the missing information

The next estimator change should represent the **measured interval-wise
receiver-clock increments**, rather than compressing two unequal increments
into one slope. Treat them as nuisance observations with a declared joint
covariance, including overlap and shared references. A leave-one-out scatter
alone does not supply that covariance or its common systematic component.
No reduction of the historical floors is justified by this diagnostic.

The station-common residual must also remain free to represent an imperfect
satellite clock; imposing linearity must not force it into the trajectory.
An additional satellite-clock curvature freedom is a modeling hypothesis,
not proof that the remaining signal originates in that clock. Check the
resulting state/bias observability and held-out RF before interpreting any
residual improvement as physical reconstruction. No target state/clock product
should be introduced as an independent-state prior.

What is missing for qualification is a joint error budget for the simultaneous
reference-derived clock increments, including common errors, and enough
independent geometric information to separate the target's common clock/path
component from its motion. Additional contemporaneous, independently timed
receiver observations with different viewing geometry can test those
contrasts; repeating a pooled reference RMS cannot establish that separation.
This study does not prove that such added data would be sufficient.

S2 stays open. The original rejection, 173 residual degrees of freedom,
threshold, formal unqualified covariance, worsening forecasts and failed
branch remain unchanged. No new prospective experiment, S3 claim, production
change or governance layer is introduced.

## Reproduction

```console
python -m research.exploratory.g12_phase_diagnostic NEW_OUTPUT.json
python -m pytest research/exploratory/tests/test_g12_phase_diagnostic.py -q
```

The JSON binds the v4 report, its original input bytes and this analysis source
using the existing hash mechanism. It checks the v4 producer bytes before
replay; later refactors can reproduce this diagnostic from its Git revision.
Tests independently construct nonlinear clock endpoints, verify covariance
contrasts and full-model ablation, poison excluded target future values and
historical corrections, reject target-labeled references before numeric access,
and retain missing reference/forecast slots. Linux/Windows CI discovers them
through its existing exploratory-test suite.
