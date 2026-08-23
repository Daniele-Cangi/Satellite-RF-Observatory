# GNSS native-Doppler primary postmortem

## Frozen outcome

The exact DOY 219 run remains `NOT_DETECTABLE`.  This audit is offline and
does not alter the plan, evaluator, receipt, threshold, primary decision or
claim scope.  The observation quarantine was destroyed before this audit and
no observation or navigation product was reopened.

The outcome receipt SHA-256 is
`e2c15a9939ac3fcef9fd28d0f46d5906bde629cb852197cf062876c15135d5c7`.

## BLOCK

The evaluator admitted both artifacts, all 380 epochs, all four links and all
selected D/C/S scalars.  The prefix orbital residual was `0.560609157 Hz`,
below the frozen `1.702713980 Hz` limit.  Prefix and held-out dispersive
peak-to-peak values were `0.025483333 Hz` and `0.033600000 Hz`, both below the
frozen `0.271716667 Hz` limit.

The only failed predicate was:

```text
for every station/satellite/SNR stream:
    heldout minimum >= calibration-prefix minimum
```

Consequently no orbital or affine held-out score was computed.  This is not a
negative result for the orbital hypothesis.

## Exact scalar evidence

| Stream | Prefix minimum | Held-out minimum | Change | Frozen predicate |
|---|---:|---:|---:|---|
| KIRU G15 S1C | 46.25 | 35.25 | -11.00 | fail |
| KIRU G15 S2W | 44.75 | 22.00 | -22.75 | fail |
| KIRU G22 S1C | 42.75 | 44.75 | +2.00 | pass |
| KIRU G22 S2W | 28.75 | 32.50 | +3.75 | pass |
| MAT1 G15 S1C | 42.70 | 47.85 | +5.15 | pass |
| MAT1 G15 S2W | 42.75 | 47.60 | +4.85 | pass |
| MAT1 G22 S1C | 50.95 | 39.85 | -11.10 | fail |
| MAT1 G22 S2W | 49.90 | 37.15 | -12.75 | fail |

The units are the RINEX S-observable units represented by the receipt.  No
independent absolute tracking threshold was frozen, so these magnitudes do not
by themselves establish either adequate or inadequate Doppler accuracy.

## Why the predicate is not a continuity test

The prefix has 76 samples and the held-out suffix has 304.  For exchangeable
continuous samples from one unchanged distribution, the condition

```text
minimum(heldout 304) >= minimum(prefix 76)
```

passes exactly when the minimum of all 380 samples happens to fall in the
prefix.  Its pass probability is therefore `76/380 = 0.20` for one stream,
even when the stream has not degraded.  This is an order-statistic consequence,
not a probability calibrated from this experiment.

If eight streams were independent, the illustrative probability that all
eight pass would be `0.20^8 = 0.00000256`.  They are not known to be independent,
so that number is not an admitted joint false-rejection probability.  The
single-stream asymmetry alone is sufficient to show that the rule depends on
window length and cannot establish continuity.

The predicate also silently requires amplitude non-degradation across changing
satellite elevation, antenna gain and propagation.  Those effects may change
SNR while a receiver continues to deliver valid Doppler.  Conversely, a finite
SNR value does not prove a bounded Doppler error.  No outcome-independent model
linked the selected minimum statistic to the accuracy required by the orbital
comparison.

## Failure attribution

| Layer | Attribution | Evidence |
|---|---|---|
| Orbital model | not tested on held-out | no score exists; prefix compatibility passed |
| Model to prediction | not shown to fail | exact navigation compiled and prefix residual passed |
| Measurement availability | available | complete 30 s grid, four links, finite positive D/C/S |
| Doppler feature extraction | completed but unscored | measurement admission passed; no series was persisted |
| Same-path health feature | insufficiently causal | scalar SNR minimum has no frozen mapping to Doppler error |
| Decision contract | controlling failure | unequal-window minimum comparison can reject an unchanged stream |
| Physical orbital hypothesis | `NOT_EVALUATED` | held-out comparison was correctly blocked by the frozen evaluator |

The raw receipt labels `prefix_detectability` as `UNSATISFIED` because the
implementation uses one aggregate detectability flag for prefix and held-out
health.  The prefix-specific numerical clauses themselves passed.  This is a
descriptive granularity defect; it does not change the terminal physical
decision.

## What the receipt can and cannot establish

It establishes that the measurement products and selected observables were
available continuously on the frozen grid, that the prefix was compatible
with the orbital model, that the dispersive witness remained within its frozen
envelope, and that four SNR minima failed the predeclared relative rule.

It cannot establish why an SNR minimum changed, whether a receiver lost lock,
whether Doppler uncertainty exceeded the decision envelope, what the held-out
orbital and affine residuals were, or which physical hypothesis would have won.
The destroyed time series cannot be reconstructed from the scalar receipt.

The correct scientific classification is therefore:

```text
FROZEN_RUNTIME_OUTCOME: NOT_DETECTABLE
SENSOR_DEGRADATION_ATTRIBUTION: INCONCLUSIVE
ORBITAL_HYPOTHESIS_RESULT: NOT_EVALUATED
FALSIFIABILITY_WITH_PRESERVED_RECEIPT: NOT_FALSIFIABLE_WITH_THIS_RECEIPT
```

## Minimum conceptual repair for a future independent experiment

A health witness must preserve a causal distinction required by the Doppler
claim.  For a future reserve, before access, require either:

1. a documented outcome-independent mapping from receiver tracking state or
   SNR to a maximum Doppler error; or
2. direct integrity indicators and continuity rules whose failure is known to
   invalidate Doppler, while treating uncalibrated SNR magnitude as descriptive.

Exact cadence, finite D/C/S, receiver-reset or lock indicators, prefix Doppler
residual and the dispersive witness may remain separate clauses.  An SNR rule
based on extrema from unequal windows must not be reused.  Replacing it with a
quantile, equal-size comparison or trend test would still require independent
development and a predeclared error interpretation; it cannot be selected from
the observed DOY 219 failures.

The DOY 219 primary must not be rescored.  Any future reserve plan must be
frozen from outcome-independent documentation or separate development, then
run once on an unopened product.

## SHOCK

The surviving abstraction is not “every available witness gates the claim.”
It is clause-specific causal sufficiency: a witness may gate an observable only
when its failure is connected to the error that matters.  SNR was on the same
measurement path but was not, in this experiment, a calibrated witness of
native-Doppler accuracy.
