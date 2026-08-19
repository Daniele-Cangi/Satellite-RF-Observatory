# Gate G0 — orbital discriminability report

## Outcome

```text
G0: COMPLETE_OFFLINE
network activity: ZERO
live measurements: ZERO
calibrated probabilities: ZERO
frozen F2.5 changes: ZERO
```

Gate G0 establishes a deterministic mechanism for asking whether observer-
dependent orbital geometry survives declared nuisance and predicts an
independent time suffix better than frozen non-orbital nulls.  It does not
claim that any live RF signal is orbital.

## Mechanism implemented

The existing stateless SGP4/Skyfield kernel is sampled on a common event-time
grid for two or more observers.  G0 derives, in this order:

```text
range-rate_i(t)
  -> fractional Doppler y_i(t) = -range-rate_i(t) / c
  -> differential y_i(t) - y_j(t)
  -> slope, curvature, visibility and event ordering
  -> carrier scaling in hertz
  -> calibration-prefix nuisance fit
  -> held-out differential score
```

The physical model learns only a station offset and affine drift from the
first 20% of the samples.  The remaining 80% is never used for fitting.  The
score is computed on simultaneous station differences, so an arbitrary common
transmitter drift cancels rather than being mistaken for orbital error.

The same joint-visibility-gated prefix and holdout are used for four frozen,
non-redundant nulls: station constants, station affine drift, independent
station quadratics, and one geometry-destroying observer permutation. The
former common-cubic null was removed because its common component cancelled
identically in the differential score; the two-station duplicate permutation
was also removed. Null complexity and parameter counts are recorded; there is
no post-result model selection or probability calibration.

Clock uncertainty is now propagated directly through the orbital kernel at
each sample's `t - delta_t` and `t + delta_t` endpoints. The differential
envelope combines the two station intervals conservatively. No local
derivative is multiplied by a large clock bound.

An orbital ensemble accepts adjacent element sets or controlled perturbations
and produces per-sample fractional and frequency envelopes.  G0 never converts
TLE age directly into a numeric error.  A controlled ±0.01 degree mean-anomaly
example produces maximum 145.8 MHz deviations of `2.187 Hz` at Berlin and
`2.697 Hz` at Copenhagen over the one-minute test window.  These numbers are
only sensitivity witnesses for that declared ensemble, not empirical TLE
accuracy.

## Frozen synthetic sweep

The discriminability map uses one published ISS element set and one fixed
European pass geometry:

```text
start:                 2019-12-09T16:38:29Z
window:                300 s
cadence:               5 s
calibration / holdout: 13 / 48 samples
carriers:              137.5 MHz, 435 MHz
frequency resolution:  1, 5, 20, 100 Hz
clock-error envelope:  direct trajectories at 0, 1, 5, 30 s
synthetic noise:       0.2 Hz RMS per station
orbit envelope input:  1 Hz per station
detectability rule:    3 frequency bins plus clock/carrier/orbit envelope
preference rule:       orbital RMSE must beat every null by 1 frequency bin
```

Four second-observer geometries are paired with Copenhagen:

| Layout | Baseline | Differential signature at 137.5 MHz | At 435 MHz |
|---|---:|---:|---:|
| local | 10.0 km | 36.745 Hz | 116.248 Hz |
| regional | 80.3 km | 271.450 Hz | 858.769 Hz |
| Berlin | 355.2 km | 1695.565 Hz | 5364.150 Hz |
| Eindhoven | 663.9 km | 1535.381 Hz | 4857.388 Hz |

The signature is the held-out peak-to-peak differential curvature remaining
after an affine prefix extrapolation.  It is not total Doppler span.

Across 128 frozen cases:

```text
ORBITAL_MODEL_PREDICTIVELY_PREFERRED:      81
ORBITAL_SIGNATURE_BELOW_DETECTABILITY:     47
ORBITAL_PREDICTION_REJECTED:                0
ORBITAL_MODEL_NOT_DISCRIMINATIVE:           0
```

The last two counts are expected because this sweep is generated from the
nominal orbit. Independent fixtures verify both outcomes using non-orbital
data and a detectable but weak local geometry. A separate, physically
plausible adjacent-orbit stress changes mean anomaly by `+0.12 deg`, RAAN by
`+0.03 deg`, and mean motion by `-0.0002 rev/day`; it produces
`ORBITAL_PREDICTION_REJECTED` with `88.681 Hz` held-out RMSE against a
`72.469 Hz` frozen tolerance. These offsets are a controlled mismatch, not a
claim about empirical TLE error.

The discrete 128-case outcome region is unchanged by the clock repair, but
the envelope is not numerically equivalent to the previous local-slope
approximation. Across nonzero-clock cases, direct minus local clock allowance
ranges from `-52.838 Hz` to `+0.085 Hz`. No tested case lies close enough to a
boundary for that correction to flip its outcome.

Maximum tested resolution still producing predictive preference:

| Layout / carrier | 0 s clock | 1 s | 5 s | 30 s |
|---|---:|---:|---:|---:|
| local / 137.5 MHz | 5 Hz | none | none | none |
| local / 435 MHz | 20 Hz | none | none | none |
| regional / 137.5 MHz | 20 Hz | 20 Hz | 20 Hz | none |
| regional / 435 MHz | 100 Hz | 100 Hz | 20 Hz | none |
| Berlin / 137.5 MHz | 100 Hz | 100 Hz | 100 Hz | 100 Hz |
| Berlin / 435 MHz | 100 Hz | 100 Hz | 100 Hz | 100 Hz |
| Eindhoven / 137.5 MHz | 100 Hz | 100 Hz | 100 Hz | none |
| Eindhoven / 435 MHz | 100 Hz | 100 Hz | 100 Hz | none |

“None” means no resolution in the tested grid cleared the frozen envelope. It
does not mean no conceivable instrument could do so.

## Reference held-out result

For Copenhagen, Berlin and Eindhoven at 145.8 MHz, 5 Hz resolution and a
1-second clock-error envelope:

```text
outcome:                         ORBITAL_MODEL_PREDICTIVELY_PREFERRED
most discriminating pair:       Berlin–Eindhoven
differential signature:         3138.710 Hz
detectability threshold:          77.469 Hz
orbital held-out RMSE:              0.903 Hz
best-null held-out RMSE:          969.833 Hz
required preference margin:         5.000 Hz
observed preference margin:       968.930 Hz
plan hash: ec6e355f84b745e8646d1cd70bc946c9b50766f4086f02ce14beddd508573f4a
```

The best null remains station affine. The independent quadratic is genuinely
distinct under differential scoring and extrapolates this reference holdout
poorly (`3692.707 Hz` RMSE); it is retained as a smooth station-local
alternative, not selected because it is convenient for this result.

## Discriminability map interpretation

Three conclusions survive this synthetic audit:

1. Baseline distance alone is not a capability requirement.  Berlin remains
   discriminative under the tested 30-second envelope while the more distant
   Eindhoven geometry does not.  Pass geometry and time derivatives matter.
2. Higher carrier frequency scales the same fractional geometric signature,
   but does not automatically guarantee better real instrumentation.  G0 does
   not model band-dependent oscillator quality or propagation.
3. A receiver can provide valid samples while remaining incapable of testing
   the orbital claim.  `NOT_DETECTABLE` is therefore separate from
   `PREDICTION_REJECTED`.

Consequently G1 must not hardcode a universal distance, band or sensor type.
For each candidate orbit, pass and observer set, it must first propagate the
actual geometry and require a positive conservative detectability margin.

## Minimum information required from a future capability

Before any acquisition, G1 must know or conservatively bound:

- observer coordinates and their association with each stream;
- RF band and frequency-bin geometry;
- timestamp semantics, continuity and maximum relative clock error;
- complete candidate observation window and dropout budget;
- carrier value or interval, kept separate from fractional geometry;
- station-local frequency offset and drift policy;
- orbit-element lineage and a declared prediction envelope;
- transform resolution and whether ridge curvature survives it;
- hardware-root independence for the distributed geometric claim.

A capability is admissible only if these bounds leave a positive predicted
differential margin.  Being connected or producing a spectrogram is not
sufficient.

## Authorized and unauthorized claims

G0 authorizes the claims that:

- the existing orbital kernel can deterministically generate synchronized
  observer-specific trajectories;
- fractional and differential Doppler remain separate from carrier scaling;
- station offset, affine drift and common transmitter drift can be prevented
  from consuming held-out geometric evidence;
- geometry permutations provide strong tests that observer identity matters;
- the considered synthetic domain contains both detectable and undetectable
  capability regions.

G0 does not authorize claims that:

- any Internet receiver currently satisfies the envelope;
- SatNOGS, KiwiSDR or WebSDR is suitable for a particular pass;
- the numeric map generalizes to other orbits or passes;
- a real RF track has orbital origin;
- a specific orbit or satellite identity has been confirmed;
- TLE age implies the controlled ensemble used here.

## Limitations carried into G1

- Only one nominal LEO pass geometry is swept.
- The atmosphere, multipath, receiver nonlinearity and non-affine oscillator
  behavior are absent.
- Common transmitter drift is assumed simultaneous at the event-time scale;
  differential residuals from unequal propagation delay are not modeled.
- Clock error is bounded by direct endpoint trajectories. Interior extrema
  between `t - delta_t` and `t + delta_t` are not searched; a future pass with
  a non-monotone interval wider than the local dynamics would require denser
  declared envelope sampling.
- Orbit uncertainty must be supplied by an explicit ensemble; it is not
  inferred from age.
- The frozen null set is strong enough to test this mechanism, not exhaustive
  proof of orbitality.

## Stop condition and next boundary

All G0 exit conditions in `G0_SCOPE.md` are satisfied.  G0 stops here.

The only permitted next question is Gate G1:

> Which currently Internet-accessible, physically independent receiver set
> exposes coordinates, event time, frequency resolution and continuity whose
> pass-specific envelope leaves a positive orbital discriminability margin?

G1 may correctly end without admitting a capability.  It must not acquire a
prospective RF window until that admission has been reviewed and frozen.

## SHOCK

The key resource is not “more receivers” and not even maximum geographic
separation.  It is an observer geometry whose differential curvature survives
the sensor’s time-frequency uncertainty outside calibration.  The orbit can
therefore select the instrument requirement before the project searches the
Internet for a sensor—the reverse of the capability-first drift that F2.5 was
needed to expose.
