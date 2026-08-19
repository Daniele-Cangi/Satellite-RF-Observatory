# Gate G0 — orbital discriminability scope

## Scientific question

After removing only nuisance parameters declared before an observation, does
orbital geometry leave a differential structure between observers that
predicts a held-out time interval better than frozen non-orbital nulls?

The object of study is not an absolute carrier and not a receiver.  It is the
observer-coupled residual

```text
y_i(t) = -range_rate_i(t) / c
delta_y_ij(t) = y_i(t) - y_j(t)
```

and the part of that residual which cannot be reduced to predeclared station
offset and affine drift.

## Frozen causal order

```text
orbital elements + observer geometry + event time
  -> fractional Doppler trajectories
  -> differential trajectory and visibility
  -> carrier scaling
  -> bounded measurement transforms and nuisance
  -> calibration prefix
  -> frozen held-out prediction
  -> comparison with complexity-declared nulls
  -> one G0 outcome
```

The portante is applied after fractional Doppler so geometry and RF scale stay
separate.  Calibration data and held-out data are disjoint.  No parameter may
be learned from the held-out interval.

## Nuisance allowed in G0

- one constant frequency offset per station;
- one affine local drift per station;
- bounded station clock error represented by direct trajectory propagation at
  `t - delta_t` and `t + delta_t`, never by a fitted holdout shift;
- bounded carrier uncertainty;
- bounded orbital-prediction uncertainty;
- declared quantization, noise and missing samples in synthetic observations.

Arbitrary time warps, post-outcome threshold changes, unconstrained splines and
per-sample corrections are forbidden.

## Frozen null families

| Null | Shape | Declared free parameters |
|---|---|---:|
| N0 | independent station constants | one per station |
| N1 | independent station affine drift | two per station |
| N2 | independent station quadratic trajectories | three per station |
| N3 | orbital predictions assigned through one frozen wrong observer permutation | two affine nuisance terms per station |

Every model uses the same calibration prefix and the same held-out interval.
Every fit and score is restricted to the relevant station visibility mask;
pairwise evidence requires joint visibility in both calibration and holdout.
N2 replaces a common smooth term that cancelled identically under differential
scoring. N3 tests whether prediction uses observer geometry rather than merely
a generic pass-shaped curve. Alternative physical orbits are not generic
nulls; controlled adjacent-orbit data are used separately as a model-mismatch
stress case.

## Non-probabilistic decision semantics

G0 uses resolution-derived and uncertainty-derived margins, not calibrated
probabilities:

- `ORBITAL_SIGNATURE_BELOW_DETECTABILITY`: the nonlinear differential
  signature does not clear the conservative measurement envelope;
- `ORBITAL_PREDICTION_REJECTED`: the held-out orbital residual exceeds its
  frozen tolerance;
- `ORBITAL_MODEL_NOT_DISCRIMINATIVE`: the orbital prediction is admissible but
  does not beat every frozen null by the required resolution margin;
- `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`: the signature is detectable, the
  held-out orbital residual is admissible, and it beats all frozen nulls.

`PREDICTIVELY_PREFERRED` is not satellite identity.  G0 contains no live
measurement and authorizes no claim about an observed object.

## Deliverables and stop condition

G0 ends when all of the following exist:

1. deterministic multi-observer orbital trajectories;
2. fractional, differential, slope, curvature and visibility observables;
3. explicit nuisance projection and bounded uncertainty envelope;
4. complexity-declared nulls evaluated on the same holdout;
5. a deterministic synthetic discriminability sweep;
6. a report translating the map into minimum future capability properties;
7. offline tests covering all four outcomes and the no-holdout-leak invariant.

Both a non-empty detectable region and a finding that the considered region is
not discriminative are valid endings.

## Explicit exclusions

Gate G0 performs no network access, receiver discovery, acquisition, SatNOGS
download, Kiwi connection, transmitter identification, catalog ranking,
free-orbit inversion, TDoA, database work, frontend work, generic adapter work
or planner construction.  Frozen F2.5 code and outcomes remain untouched.
