# LuGRE constellation-snapshot discriminability

## Outcome

```text
LUGRE_SNAPSHOT_GEOMETRY_DISCRIMINATIVE
```

This is an observation-blind geometry result. It is not capability admission,
does not freeze a prospective plan and authorizes no LuGRE header, telemetry or
IQ access.

```text
measurement admission = NOT_EVALUATED_OPEN_TERMS
LuGRE payload bytes = 0
orbital scores from measurements = 0
```

## Physical question

Can four simultaneous anonymous GPS L1 carrier frequencies retain orbital
identity after a common receiver frequency offset and a common positive
frequency-axis scale are removed?

This is a different coordinate from the closed 139-epoch anonymous-track
experiment. Its information is across simultaneous satellites, not across a
long temporal curve:

```text
historical broadcast GPS orbits
    + independently archived Blue Ghost observer geometry
    + one exact public snapshot time
        -> one-way light-time and broadcast-clock-rate prediction
        -> four-frequency anonymous shape
        -> common offset/scale projection
        -> wrong-subset and non-orbital null separation
```

The minimum of four signals is frozen because four coordinates retain two
degrees of shape after removing one offset and one scale. No probability is
invented.

## Outcome-independent inputs

The seven operation times and advertised durations come only from the public
Zenodo archive listing. Six exact NOAA RINEX 2.11 daily broadcast-navigation
products provide the GPS transmitter hypotheses. The CLPS PDS archive provides
the observer and reference-frame kernels.

The observer lineage is explicit:

- OP32 and OP37 use the archived **reconstructed** Blue Ghost cruise SPK;
- OP38, OP40, OP73, OP74 and OP76 use the archived actual landing-site SPK;
- neither observer product is a prospective Blue Ghost orbit;
- both are independent of the target LuGRE RF samples and therefore may
  condition observer geometry, but not demonstrate an independent observer
  orbit prediction.

The GPS orbit inputs are the historical broadcast messages, not LuGRE NAV/EPH
telemetry. LuGRE telemetry remains unopened.

Every navigation and SPICE object is bound by byte count and SHA-256 in
[`LUGRE_SNAPSHOT_DISCRIMINABILITY_RECEIPT.json`](LUGRE_SNAPSHOT_DISCRIMINABILITY_RECEIPT.json).
The temporary copies are inputs to the offline compiler and are not repository
artifacts.

## Frozen coordinate and nulls

For every healthy broadcast GPS satellite the compiler:

1. solves one-way transmit time against the Blue Ghost receive epoch;
2. transforms broadcast ECEF geometry to J2000 with archived Earth
   orientation;
3. differentiates light-time range on a fixed one-second stencil;
4. includes the broadcast satellite-clock-rate term;
5. removes Earth-occulted paths;
6. forms every four-satellite anonymous frequency hypothesis.

Every orbital hypothesis and every null receives the same fitted common offset
and positive scale. The null family is:

- nearest wrong four-GPS subset;
- an equally spaced rank-affine shape;
- an Earth-center observer;
- a static observer at the exact Blue Ghost position.

The receiver spectrum sign is not selected by the score. A future exact header
must declare it before scoring.

## Why the first all-satellite result was not used for ranking

Earth line of sight alone leaves 30--31 healthy GPS candidates per operation,
including directions more than 100 degrees off transmit boresight. Treating all
of those directions as equally plausible RF capability made the controlling
codebook separation only `0.008811--0.060388 Hz`. Those directions are valid as
a conservative combinatorial stress test, but not as a physically justified
target family without a transmit antenna/link model.

The observation-blind selector therefore uses exactly one monotonic geometric
proxy:

```text
the four unocculted healthy GPS satellites with minimum transmit off-boresight
```

It uses no antenna gain, received power, LuGRE signal value, code identity or
published post-processed detection. Failure to find all four in a future
authorized artifact would be a pre-score admission failure, not permission to
choose another family.

## Exact operation ranking

The controlling separation is the smallest affine-projected per-track RMS
distance to the nearest wrong subset or frozen null. Half of it is the maximum
aggregate per-track RMS error envelope under the symmetric two-envelope rule.

| rank | operation / UTC | geometry-selected GPS family | off-boresight range | controlling alternative | separation | maximum total RMS envelope |
| ---: | --- | --- | ---: | --- | ---: | ---: |
| 1 | OP76 / 2025-03-15 13:07:27 | G31, G28, G26, G10 | 17.465--34.527 deg | static observer | 11.019310 Hz | 5.509655 Hz |
| 2 | OP37 / 2025-02-27 16:09:37 | G15, G18, G29, G05 | 34.320--43.581 deg | Earth-center observer | 8.713760 Hz | 4.356880 Hz |
| 3 | OP32 / 2025-02-24 12:04:49 | G06, G19, G11, G20 | 21.087--33.300 deg | static observer | 8.055339 Hz | 4.027669 Hz |
| 4 | OP74 / 2025-03-14 12:47:17 | G31, G10, G23, G26 | 16.870--44.901 deg | Earth-center observer | 6.328409 Hz | 3.164205 Hz |
| 5 | OP73 / 2025-03-14 10:09:45 | G24, G18, G12, G05 | 22.933--42.737 deg | wrong GPS subset | 5.033680 Hz | 2.516840 Hz |
| 6 | OP40 / 2025-03-04 07:03:23 | G25, G18, G23, G29 | 17.384--32.345 deg | wrong GPS subset | 4.770605 Hz | 2.385303 Hz |
| 7 | OP38 / 2025-03-03 06:13:00 | G18, G12, G05, G29 | 24.935--40.035 deg | wrong GPS subset | 0.493938 Hz | 0.246969 Hz |

For OP76 specifically:

- nearest wrong-subset separation: `11.585111 Hz`;
- static-observer separation: `11.019310 Hz`;
- Earth-center separation: `12.097682 Hz`;
- rank-affine separation: `1366.836390 Hz`.

The static observer, not the assignment alternative, controls. The prospective
question would therefore test motion-dependent geometry, not merely whether
four tones have unequal spacing.

## Timing stress

The exact public operation second is not silently treated as ADC truth. For the
OP76 family, direct recomputation at `-10`, `-1`, `-0.1`, `+0.1`, `+1` and
`+10 s` still ranks the frozen family first. At both `-60 s` and `+60 s`, a
wrong subset becomes preferable. This is a discrete sensitivity audit, not a
proof that every intermediate offset is safe and not a product-applicable
ADC-time bound.

Consequently a future header/receipt must provide a finite sample-zero binding
well inside a separately frozen safe interval. `UNKNOWN` cannot be replaced by
the filename's one-second precision.

## What this result authorizes

It authorizes only this statement:

> Before inspecting LuGRE signal content, at least one exact public operation
> has a four-satellite, motion-dependent GPS Doppler shape that is separated
> from the frozen wrong-subset and non-orbital nulls after common offset and
> scale projection.

It does **not** authorize any statement that:

- G31/G28/G26/G10 are present in OP76;
- any listed satellite is detectable at its off-boresight angle;
- the IQ header binds sample zero to GPST tightly enough;
- a two-second weak-signal estimator meets a `5.509655 Hz` aggregate envelope;
- differential media, satellite-clock residuals and non-affine receiver clock
  behavior fit inside the remaining margin;
- LuGRE independently predicts the Blue Ghost observer trajectory;
- an orbital measurement has occurred.

## Residual blockers before a prospective plan

The geometry has removed the previous “snapshot is too short by definition”
blocker. The exact residual blockers are now measurement clauses:

1. product-applicable first-sample GPST/ADC semantics and finite error;
2. exact sample rate, rate accuracy, center/IF coordinates and spectrum sign;
3. deterministic model-blind four-carrier estimator and its error envelope;
4. predeclared admission of all four frozen family members without replacement;
5. transmitter-clock residual, differential media and receiver non-affine
   oscillator envelopes below the controlling margin;
6. an L5 same-satellite branch, if available, used only as a dispersive witness
   under a rule frozen before primary access.

The public generic `50 ns` Qascom timing figure remains insufficient unless a
product specification binds it to these IQS first samples.

## Candidate next vertical, not yet frozen

If the blockers can be closed from non-signal metadata, the smallest clean role
split would be:

- development candidate: OP73, 2.0 s, `5.033680 Hz` controlling separation;
- held-out primary candidate: OP76, 2.0 s, `11.019310 Hz` controlling
  separation;
- sealed reserve candidate: OP74, 0.5 s, `6.328409 Hz` controlling separation.

This is a recommendation only. No role, detector, threshold or access authority
is frozen by this report.

## SHOCK

The LuGRE snapshots are not merely truncated versions of a long GNSS track.
Their potentially useful observable is the simultaneous constellation shape.
But the complete anonymous GPS population is too combinatorially dense at the
millihertz level. Physical information appears only after an outcome-blind
geometric family is selected before RF access. In this regime, “targetless”
cannot mean “all physically imaginable transmitters are equally admissible.”

## Evidence boundary and reproduction

- LuGRE ZIP, IQS headers, IQ, NAV/EPH telemetry and signal diagnostics:
  `0 bytes accessed`;
- no LuGRE URL was requested by the compiler;
- no signal value, code identity, C/N0, acquisition result or published
  post-processing result entered the score;
- temporary orbit files are not committed;
- strict JSON forbids non-finite values;
- receipt canonical SHA-256:
  `bbe20a00fb7f11b9979a70d352f8faff9d571749256716f10c752ef0d936f2de`;
- frozen compiler commit:
  `f8aa957ea0310f07ac0976e247c00308efc82314`;
- compiler canonical SHA-256:
  `c30f38b365ca55bf4d29cceb55adee8b002d05dc78f44dc34d6c9e4e0b39d089`.

Public authorities:

- LuGRE archive metadata: <https://zenodo.org/records/16411687>
- LuGRE mission result and receiver architecture: <https://doi.org/10.33012/NAVI.756>
- CLPS SPICE archive description: <https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/document/spiceds_v003.html>
- NOAA historical broadcast navigation root: <https://geodesy.noaa.gov/corsdata/rinex/2025/>
