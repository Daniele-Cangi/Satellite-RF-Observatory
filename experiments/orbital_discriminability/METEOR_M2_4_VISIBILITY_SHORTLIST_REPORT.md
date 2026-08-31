# METEOR-M N2-4 visibility shortlist

## Terminal result

```text
METEOR_M2_4_VISIBILITY_GEOMETRY_SHORTLISTED
NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE
```

The two statements are deliberately separate. The orbit admits useful
observer-coupled visibility events, but the bounded capability set does not
yet contain two admitted measurement roots. No RF connection, sample,
waterfall, spectrum frame or observation value was accessed.

## Physical question

Can one current satellite and a predeclared small set of real public stations
replace the synthetic city lattice while retaining the sequence

```text
one root visible / other root Earth-occulted
                    ↓
               both visible
                    ↓
other root visible / first root Earth-occulted
```

with enough time margin that a negative could later be distinguished from an
unobservable event?

## Candidate and orbit provenance

The selected orbit-first candidate is **METEOR-M N2-4**, NORAD `59051`, object
`2024-039A`. WMO OSCAR classifies it operational and describes real-time LRPT
availability. The SatNOGS transmitter record supplies the reviewed
`137.900 MHz` LRPT candidate. A current public Doncaster station describes
automated raw-IQ capture and SatDump decode, but that station report is not
operator evidence and does not by itself close emission continuity.

The descriptive OMM epoch is `2026-08-29T06:26:44.437632`; its strict hash is:

```text
f88a0042c01e7a750cac71ea7e1bb4e247a58cc5b989853357424f52b215f85a
```

Propagation uses the newer public mirrored TLE at epoch
`2026-08-29T21:38:22.077Z`. Two adjacent public element sets are frozen as a
bounded sensitivity ensemble. They are not a covariance and do not authorize
a probability statement.

## Bounded capability set

| Root | Descriptive result | Frequency coverage | Admission |
|---|---|---|---|
| YO3BN Bucharest | HTTP `status.json` returned exact GPS coordinates `44.5227901918 N, 26.2576461447 E`, 80 m, OpenWebRX+ profile centered at `137.000 MHz`, sample rate/span `2.400 MHz` | covers `137.900 MHz` | discovered, not admitted: event-time binding, sequence continuity, directional mask and same-path absence witness are unknown |
| AwareSignal Doncaster | station says online; dedicated V-pole + SAWbird+ NOAA; automated 137 MHz raw-IQ capture and SatDump decode | documented 137 MHz product | discovered, not admitted: exact station coordinates, public immutable IQ path, first-sample time and continuity are unknown |
| YO8TNB Dorohoi | published `47.957 N, 26.403 E`, 180 m, RSP1A and 137 MHz weather-satellite coverage | documented | discovered, not admitted: direct status endpoint was unreachable in the bounded check |

`sample_rate` is retained only as the delivered profile width. It is not
promoted to spectral resolution, frame cadence or event-time accuracy.

AwareSignal publishes only Doncaster and `53.5 N`. For geometry feasibility,
the audit therefore propagates a deliberately broad analysis-only box:

```text
latitude   53.2 .. 53.8 deg
longitude  -1.5 .. -0.7 deg
altitude   0 .. 250 m
```

This box is not an inferred station coordinate. Its survival can establish
robust geometry; it cannot satisfy capability admission.

## Frozen geometry rules

```text
discovery interval              2026-08-30 00:00 to 2026-09-01 00:00 UTC
coarse cadence                  30 s
refined cadence                 5 s
conservatively visible         elevation >= +5 deg
geometrically occulted         elevation <= -2 deg
excluded transition band       (-2, +5) deg
minimum state dwell            30 s
confirmation frames            3
coordinate members             9
orbit members                  3
RF access                      forbidden
```

The strict plan hash is:

```text
938d6e90a93814848c86f4640d674ed565b04ee3882cf2383ba0b47e794f10e1
```

## Ranked pass geometry

For the table, `right` is YO3BN Bucharest and `left` is the Doncaster geometry
member. Every retained event runs Bucharest-only → both → Doncaster-only.

| Rank | Refined UTC interval | Robust controlling state | Dwell margin | Coupled timing/cadence requirement | Classification |
|---|---|---:|---:|---|---|
| 1 | 2026-08-30 12:54:15–13:14:05 | 90 s | +60 s | `2 Δt + 3 C <= 90 s` | positive |
| 2 | 2026-08-31 12:32:25–12:52:25 | 80 s | +50 s | `2 Δt + 3 C <= 80 s` | positive |
| 3 | 2026-08-30 11:15:00–11:33:45 | 30 s | 0 s | `2 Δt + 3 C <= 30 s` | boundary; not admitted |

Here `Δt` is the defensible per-root event-time error and `C` is delivered
frame cadence. The two maxima in a row cannot be taken simultaneously outside
the stated frontier. For example, with `C = 10 s`, rank 1 permits `Δt <= 30 s`
and rank 2 permits `Δt <= 25 s`. Rank 3 has no positive timing slack and is
therefore not a prospective candidate.

The exact Bucharest–Dorohoi pair produces no complete three-state sequence in
the same interval. Its short baseline is geometrically unsuitable for this
particular visibility observable even before the current offline status is
considered.

## Witnesses and causal cuts still required

A future measurement path would need all of the following before freeze:

1. one root with target structure present during the other root's predicted
   occultation, establishing that the transmitter remained on;
2. immutable root identity and actual station coordinates;
3. a bound satisfying the selected `Δt/C` frontier;
4. uninterrupted sequence accounting through the complete window;
5. a predeclared local horizon and antenna-direction/polarization envelope;
6. an in-band same-path witness proving tuning, antenna/front-end, stream and
   transform survival at the root where absence is predicted;
7. a predeclared interference and missing-data rule;
8. a target feature fixed before the confirmation window.

A page loading successfully, a receiver clock shown in the browser, a
sample-rate field, or a generic noise floor does not close those causal cuts.

## Authorized and unauthorized claims

Authorized:

> Across the frozen adjacent-orbit and Doncaster-position ensemble, two
> METEOR-M N2-4 pass geometries retain positive observer-coupled visibility
> margins relative to YO3BN.

Not authorized:

- that the Doncaster geometry is the AwareSignal antenna coordinate;
- that either public product has ADC- or server-bound event time;
- that an RF absence would currently be interpretable;
- that the LRPT signal is continuously emitted from operator evidence;
- that the specific orbit is identified by these event times;
- that a forward experiment has been frozen.

## Stop and next maximum action

The terminal result remains:

```text
NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE
```

The exact blocker is `NO_PAIR_OF_MEASUREMENT_CAPABILITIES_ADMITTED`.
Geometry is no longer the controlling uncertainty. The minimum next action,
only after review, is one short non-target-specific measurement-path
characterization of YO3BN and one explicitly named independent western root.
It must stop without RF observation if the pair cannot supply event-time,
continuity and same-path absence witnesses. It must not become a receiver
inventory.

The main SHOCK is that a coarse visibility coordinate relaxes the sub-hertz
detector problem, but makes **absence provenance** the instrument. A public
receiver that covers the frequency is not yet a capability to measure an
occultation.
