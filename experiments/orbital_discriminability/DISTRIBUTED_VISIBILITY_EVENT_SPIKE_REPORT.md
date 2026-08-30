# Distributed visibility-event spike

## Result

```text
DISTRIBUTED_VISIBILITY_MECHANISM_DISCRIMINATIVE
SPECIFIC_ORBIT_NOT_DISCRIMINATIVE_AT_THIS_BOUND
```

This is one bounded offline geometry spike. It is not a new gate, does not
select a receiver, and does not authorize an observation.

```text
network connections          0
RF bytes accessed            0
observation values accessed  0
```

## Physical question

Can a frozen candidate orbit predict a station-bound sequence of presence and
Earth-occulted absence that a common transmitter schedule, co-located geometry,
or observer permutation cannot reproduce?

## New information

Yes. A frequency ridge is not the only useful distributed orbital coordinate.
The fixed G0 LEO fixture produces a conservative three-state topology for a
bounded observer lattice:

```text
one observer visible / the other geometrically occulted
                       ↓
                 both visible
                       ↓
the other observer visible / the first geometrically occulted
```

This topology survives a finite event-time allowance without requiring a
sub-hertz frequency coordinate. It does not, at the tested timing bound,
distinguish the nominal orbit from a nearby plausible orbit.

## Why the existing experiments did not answer it

The successful GNSS experiments measured orbital dynamics in upstream
PRN-labelled observables. The anonymous-track spike removed that identity
label synthetically, but no real time-qualified raw-track capability was
admitted. The RSP-03, MAVEN, Cassini and LuGRE paths each stopped on a
different causal cut involving absolute time, orbit independence, physical
envelopes or receiver transforms. None tested a binary, geographically
distributed visibility topology with a witnessed absence.

## Competing physical routes

| Route | New causal cut | Negative result | Main uncontrolled assumptions | Decision |
|---|---|---|---|---|
| anonymous real raw-GNSS tracks | removes upstream PRN identity | strong if ADC time and blind acquisition are qualified | no admitted real capability after the bounded TEX-CUP/LuGRE review | retain as later inverse route, do not resume inventory search |
| time-qualified raw-IQ Doppler | direct carrier dynamics | interpretable only after timing, detector and propagation envelopes close | prior datasets failed absolute time, orbit independence or open-term bounds | do not start another metadata search now |
| SatNOGS/public raster Doppler | independent public RF roots | weak when raster absence lacks a same-path witness | lossy time/frequency raster, feature selection, target-conditioned identity | possible supporting route, not the minimum negative test |
| distributed visibility/occultation | observer-coupled event ordering and physical Earth blockage | interpretable if emission-on and receiver-path witnesses are simultaneous | emission continuity, directional horizon mask, local interference and receive-path health | selected for the offline spike |

The selection is based on the negative result: a target present at one root
while it is predicted to be Earth-occulted at a witnessed second root is more
interpretable than failure to extract a fine Doppler ridge.

## Frozen offline spike

The fixture is the existing fixed G0 ISS element set. The following city names
refer only to WGS-84 geometry; they do **not** assert that a receiver or suitable
capability exists there.

```text
grid cadence                         5 s
conservatively visible               elevation >= +5 deg
geometrically occulted               elevation <= -2 deg
excluded transition band             (-2, +5) deg
provisional per-root event-time bound 5 s
minimum robust state dwell            30 s
required confirmation frames          3
```

The observer lattice contains Dublin, Madrid, Rome and Warsaw. It was chosen
only to test whether the mechanism exists across scientifically distinct
baselines; it is not a capability inventory.

## Geometry result

| Pair | Ordered topology | left-only | both visible | right-only | controlling duration after timing | dwell margin | admitted |
|---|---|---:|---:|---:|---:|---:|---|
| Dublin–Rome | left → both → right | 145 s | 240 s | 155 s | 135 s | +105 s | yes |
| Dublin–Warsaw | left → both → right | 165 s | 205 s | 85 s | 75 s | +45 s | yes |
| Madrid–Rome | left → both → right | 20 s | 300 s | 80 s | 10 s | -20 s | no |
| remaining three pairs | incomplete or too short | — | — | — | 0 s | -30 s | no |

For Dublin–Rome, three confirmation frames fit if frame cadence is no worse
than 45 s. This is a derived maximum requirement, not a claimed property of
any instrument.

The complete strict plan hash is:

```text
1d6dc9875c4ed996b70ebf89f5110c761d62fbbe460e71d879589351cd887d09
```

## Null and alternative-orbit interpretation

- `COMMON_TRANSMITTER_SCHEDULE` predicts the same target-presence state at
  both healthy roots. It cannot produce a witnessed one-present/one-occulted
  state.
- `COLOCATED_OBSERVER_GEOMETRY` destroys the ordered exclusive intervals.
- `OBSERVER_PERMUTATION` reverses the station-bound transition order and is
  rejected only if station identity and event time are immutable.
- `PLAUSIBLE_ADJACENT_ORBIT` is a physical alternative, not a generic null.
  Its maximum relative AOS/LOS/duration change is 5 s. The comparison bound is
  15 s (two 5 s station bounds plus one 5 s grid interval), so this spike does
  not prefer the specific nominal orbit.

The authorized claim therefore stops at:

> Observer-coupled orbital visibility can be discriminative against frozen
> geometry-destroying alternatives.

It does not authorize satellite identity, a receiver measurement, or even the
claim that a suitable real pair currently exists.

## Witnesses and causal cuts

A real absence is usable only if all of the following are frozen before the
test:

1. two geographically independent hardware roots;
2. event-time binding no worse than the pass-specific derived bound;
3. a target-present root that witnesses transmitter activity during the
   predicted absence at the other root;
4. a same-path witness at the occulted root covering tuning, antenna path,
   receiver continuity, transform continuity and local interference;
5. a predeclared directional horizon/antenna mask;
6. a target whose emission continuity is either physically scheduled or
   witnessed continuously by the positive root;
7. immutable station identity, target feature, state classifier and missing-
   data rule.

A connected receiver or a noise-floor trace alone is insufficient. The
same-path witness must show that the target feature would have survived the
local measurement path had it been present.

## False-negative boundary

The following remain capable of turning a physical presence into a measured
absence and are not silently zeroed:

- directional antenna null or uncharacterized local horizon;
- polarization or link-margin failure;
- target emission interruption;
- local interference covering the target feature;
- receiver scheduling, dropout or timestamp discontinuity;
- target-conditioned feature selection that fails differently at the roots;
- atmospheric or propagation effects near the horizon.

If any one remains unresolved in the eventual capability receipt, the state
is `NOT_DETECTABLE` or `MEASUREMENT_INVALID`, not an orbital negative.

## Stop condition and next physical step

The spike stops here, before capability discovery and before RF access.

The smallest next physical step is **not** another raw-IQ dataset search. It is
an orbit-first, metadata-only pass selection for one current satellite whose
emission can be witnessed continuously, followed by evaluation of one bounded
pair near a geometry with two robust exclusive intervals. Actual station
coordinates must replace the city lattice and the provisional 5 s timing
bound must be recomputed, not inherited.

If no predeclared pair can provide the emission-on witness, same-path absence
witness and directional mask, this route must stop as
`NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE` without observing RF.
