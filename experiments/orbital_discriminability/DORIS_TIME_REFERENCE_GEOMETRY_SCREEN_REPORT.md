# DORIS time-reference pair geometry screen

Outcome: **`DORIS_TIME_REFERENCE_TOPOLOGY_NO_JOINT_VISIBILITY`**

This is the bounded orbit-only screen authorized by the preceding observable-
topology review. It is not a new gate. It opened the three already frozen,
exact-hash SP3 forecasts and no DORIS RINEX product, observation value, phase,
code, power, receiver diagnostic or candidate measurement artifact.

## Physical question and stop

**Physical question:** can any of the six frozen pairs of header-declared
time-reference beacons observe Sentinel-3A simultaneously long enough to
support the existing calibration-prefix and held-out orbital-versus-null test?

**New information:** all six pairs are continuously outside the common
visibility geometry at the frozen 10 degree elevation cutoff, even under a
conservative orbit-radius and station-normal bound.

**Why the earlier result could not answer it:** the topology review proved
which clock terms the coordinate could remove, but deliberately did not open
an orbit product or propagate the four time-reference sites.

**Stop condition:** close this topology without evaluating null scores and
without measurement access if no pair has a 360 s common visibility interval.

## Frozen scope

- candidate: Sentinel-3A / NORAD 41335;
- candidate day: 2026-09-02 UTC;
- stations: ADHC, HBMB, PAUB and TLSB;
- pairs: all six unordered pairs from those four stations;
- grid: 10 s;
- minimum elevation: 10 degrees at each station;
- minimum joint interval: 360 s;
- calibration/held-out rules and null families: unchanged;
- station coordinates: the public [IDS current station table](https://ids-doris.org/network-stations/sites.html), last updated 2026-06-03, at its published one-arcminute resolution;
- station height: unresolved and set to zero only for screening.

The current Sentinel-3A forecast reaches an exact-grid maximum geocentric
radius of **7,188,967.934 m**. For each station the proof computes the WGS84
geodetic-normal versus geocentric-radius offset and subtracts it from the
elevation cutoff. This expands, rather than shrinks, the admissible continuous
visibility cap. A positive separation excess is therefore an impossibility
certificate under the frozen geometry, not a grid-resolution artifact.

## Results

| Diagnostic rank | Pair | Station separation | Conservative joint cap | Excess beyond cap | Best 10 s-grid minimum elevation | Joint samples | Longest joint interval |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | ADHC-PAUB | 66.242946 degrees | 38.702100 degrees | **27.540847 degrees** | -5.235425 degrees | 0 | 0 s |
| 2 | HBMB-TLSB | 73.170909 degrees | 38.672868 degrees | **34.498042 degrees** | -8.563820 degrees | 0 | 0 s |
| 3 | ADHC-HBMB | 74.806402 degrees | 38.763884 degrees | **36.042518 degrees** | -8.857619 degrees | 0 | 0 s |
| 4 | HBMB-PAUB | 136.714919 degrees | 38.484960 degrees | **98.229960 degrees** | -29.068938 degrees | 0 | 0 s |
| 5 | PAUB-TLSB | 144.410249 degrees | 38.611083 degrees | **105.799166 degrees** | -31.489502 degrees | 0 | 0 s |
| 6 | ADHC-TLSB | 147.854660 degrees | 38.890008 degrees | **108.964652 degrees** | -32.443178 degrees | 0 | 0 s |

The ranking is diagnostic only. Even ADHC-PAUB, the least impossible pair,
misses the conservative continuous cap by 27.54 degrees. There is no shortlist.

## Why the nulls are not scored

The affine, +/-60 s along-track, Sentinel-3B wrong-orbit and prior-forecast
families remain frozen. Their state is
`NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW`, not failed and not passed. Every
comparison requires a calibration prefix and independent held-out suffix
inside a jointly visible interval. Scoring a nonexistent interval would turn a
capability failure into a false orbital statement.

This result therefore authorizes only:

```text
the frozen Sentinel-3A + two declared time-reference-beacon topology
cannot instantiate its required simultaneous coordinate on this day
```

It does **not** authorize a negative RF claim, a null preference, a statement
about DORIS generally, or a conclusion about Sentinel-3A's orbit.

## Artifacts and retention

| Role | File | Bytes | SHA-256 |
|---|---|---:|---|
| current S3A pre-observation forecast | `exts3a30.b26243.e26246.D__.sp3.001.Z` | 278,021 | `1f8662c0d77b4fbc08dc35121108eb18a70cf22a94185944da652b06dfd97376` |
| prior S3A forecast envelope, frozen but not scored | `exts3a30.b26242.e26245.D__.sp3.001.Z` | 280,545 | `17cd7dfa11016f7e389237572190cd02530966764ebce36cbd2c12d0d00ebf7a` |
| S3B wrong-orbit null, frozen but not scored | `exts3b30.b26243.e26246.D__.sp3.001.Z` | 279,938 | `5c80e1374b9d2185b476c70ff51d8f46e2def0fba84ff7bef6f31b24ed4870e1` |

After hashing and analysis, all three compressed orbit artifacts were
destroyed. Repository retention is zero. The strict machine-readable receipt
is [`DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_RECEIPT.json`](DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_RECEIPT.json).

## Decision

The time-reference-pair topology is **closed for the frozen Sentinel-3A
candidate geometry**. Do not search for a convenient DORIS observation and do
not weaken visibility. The next work must be a change-of-abstraction review,
not another product or beacon search. Plausible alternatives to compare are:

1. one time-reference beacon plus one standard beacon whose USO evolution is
   independently bounded over the short interval;
2. a multi-satellite, short-lag coordinate only if the beacon-USO derivative
   and receiver-channel terms have outcome-independent bounds;
3. a different satellite observable or sensor family that preserves an
   orbital held-out coordinate without requiring simultaneous visibility of
   these widely separated time-reference roots.

No alternative is selected by this screen.

## SHOCK

The best clock roots are the worst geometric roots for this shared LEO
receiver: in the frozen DORIS scope, time-reference quality and joint
visibility are anti-correlated. The topology was algebraically cleaner yet
physically unrealizable. Causal cancellation is useful only after the geometry
proves that all required links can coexist.
