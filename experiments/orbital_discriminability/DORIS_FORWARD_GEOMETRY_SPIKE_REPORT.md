# DORIS forward geometry spike

## Decision before work

**Physical question:** Can a pre-observation Sentinel-3A orbit predict a
beacon-dependent, simultaneous DORIS phase coordinate that separates from an
affine continuation and frozen geometry-destroying alternatives on an untouched
suffix?

**New information produced:** A bounded, orbit-only calculation determines
whether the ground-beacon-to-spacecraft topology contains a positive geometric
held-out separation before any observation product is opened.

**Why the existing experiment cannot answer it:** The GNSS verticals share the
POLARX5 receiver family across ground roots. The METEOR OpenWebRX path did not
admit event time, and the SatNOGS raster path did not preserve a reversible
Doppler coordinate. DORIS reverses the measurement direction: independent
ground transmitters are observed simultaneously by one spaceborne receiver and
reported as dual-frequency raw phase and pseudorange.

**Minimum experiment:** Three exact pre-observation extrapolated SP3 products,
four predeclared beacon pairs, a 10 s interpolated grid, joint visibility,
prefix-only affine calibration, an adjacent-orbit-time family and one distinct
spacecraft alternative. No RINEX observation is needed.

**Stop condition:** Stop before all DORIS RINEX access unless a later review
admits the event-time semantics, phase continuity, receiver clock, actual beacon
frequency, media combination, exact station coordinates and candidate-window
coverage. A positive geometry result is not measurement admission.

## Outcome

`DORIS_FORWARD_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED`

The spike found ten Sentinel-3A joint-visibility intervals on 2026-09-02 UTC
within the four-pair scope. Three have large positive *preliminary geometry*
margins after an affine prefix fit and a prior-forecast disagreement envelope.
No DORIS RINEX file, header, phase, pseudorange, power value or oscillator value
was accessed. No observation role has been frozen.

This outcome authorizes only a shortlist for later measurement-path review. It
does not establish DORIS detectability, satellite identity or an orbital RF
observation.

## Why DORIS is a different measurement topology

The IDS describes DORIS RINEX as the telemetry-derived exchange format for raw
DGXX phase and pseudorange. The RINEX specification defines instrument proper
time linked to TAI, station identity and frequency-shift factor `K`, dual phase
and pseudorange observables, time-reference fields, receiver oscillator offset
and a fixed L2/L1 measurement-time offset. It also says that receiver channels
tracking the same station are combined to extend phase continuity. These are
promising semantics, but their presence and numerical validity in the candidate
product remain untested.

The causal path under review is:

```text
independent DORIS beacon oscillators and transmit chains
  -> beacon-specific S/U-band emission
  -> beacon-specific atmosphere and line of sight
  -> shared Sentinel-3A antenna and DGXX receiver
  -> shared receiver clock plus channel-specific transforms
  -> L1/L2 phase, C1/C2 pseudorange, flags and RINEX construction
```

The independent roots are therefore the *transmitters*, not two receive
systems. Shared antenna, receiver, clock and RINEX generation are allowed only
for a claim about beacon-dependent distributed geometry. They cannot authorize
independent-receiver confirmation.

Primary documentation:

- [IDS overview of DORIS RINEX](https://ids-doris.org/user-corner/about-doris-rinex-format.html)
- [CNES RINEX DORIS 3.0 specification](https://ids-doris.org/documents/BC/data/RINEX_DORIS.pdf)
- [DORIS models and solutions](https://ids-doris.org/documents/BC/data/DORIS_models%26solutions_v1.0.pdf)
- [IDS current station table](https://ids-doris.org/network-stations/sites.html)
- [IDS extrapolated-orbit announcement](https://ids-doris.org/ids-news.html)

## Frozen orbit-only inputs

All three products are CNES `ORBIT ITRF EXT` SP3 files in TAI, with position and
velocity records at 60 s cadence. They were decompressed only in RAM. The
2026-09-02 calculation uses a fixed 37 s TAI-minus-UTC conversion and cubic
Hermite interpolation to 10 s. After the receipt was reproduced exactly and
the full-file hashes were rechecked, the three compressed orbit artifacts were
destroyed; repository retention is zero.

| Role | Product | Bytes | SHA-256 |
|---|---|---:|---|
| Current Sentinel-3A forecast | `exts3a30.b26243.e26246.D__.sp3.001.Z` | 278,021 | `1f8662c0d77b4fbc08dc35121108eb18a70cf22a94185944da652b06dfd97376` |
| Prior Sentinel-3A forecast | `exts3a30.b26242.e26245.D__.sp3.001.Z` | 280,545 | `17cd7dfa11016f7e389237572190cd02530966764ebce36cbd2c12d0d00ebf7a` |
| Sentinel-3B physical alternative | `exts3b30.b26243.e26246.D__.sp3.001.Z` | 279,938 | `5c80e1374b9d2185b476c70ff51d8f46e2def0fba84ff7bef6f31b24ed4870e1` |

The current/prior Sentinel-3A disagreement is an outcome-independent forecast
comparison, not a complete orbit-error distribution. Sentinel-3B is retained
as a physically distinct wrong-orbit diagnostic. It is not the controlling
null because its visibility is not guaranteed on every Sentinel-3A interval.

## Frozen screening calculation

- candidate: Sentinel-3A / COSPAR 2016-011A / NORAD 41335;
- candidate day: 2026-09-02 UTC (DOY 245);
- nominal S-band carrier used only for geometry scaling: 2.03625 GHz;
- station scope: TLSB–GR4B, TLSB–WEUC, PAUB–RIMC and KRWB–LAPB;
- station coordinates: public IDS table rounded to one arcminute, with height
  deliberately unresolved;
- joint elevation: at least 10 degrees at both beacons;
- joint interval: at least 360 s;
- calibration: first 25%, at least 120 s;
- untouched suffix: at least 240 s;
- frozen nulls: prefix-fitted station-affine continuation and same-trajectory
  along-track alternatives at -60 s and +60 s;
- physical diagnostic: Sentinel-3B on the same time grid;
- forecast envelope: current minus prior Sentinel-3A forecast after the same
  prefix affine projection.

The instantaneous range-rate coordinate is a geometry screen. A later physical
model must use the DORIS phase convention, one-way propagation and the actual
header frequency factor; it must not silently equate `sample_rate`, phase-count
cadence and Doppler resolution.

## Ranked shortlist

| Rank | Beacon pair | Joint UTC interval | Cal / held-out | Controlling separation | Forecast envelope p-p | Preliminary geometry margin |
|---:|---|---|---|---:|---:|---:|
| 1 | KRWB–LAPB | 01:52:30–01:59:30 | 120 s / 300 s | 34,858.049 Hz | 2.484 Hz | 34,855.565 Hz |
| 2 | TLSB–WEUC | 10:51:10–10:58:20 | 120 s / 310 s | 21,467.817 Hz | 1.824 Hz | 21,465.993 Hz |
| 3 | PAUB–RIMC | 19:35:50–19:43:50 | 120 s / 360 s | 18,147.766 Hz | 2.967 Hz | 18,144.799 Hz |

For KRWB–LAPB and TLSB–WEUC the closest controlling alternative is the +60 s
along-track shift. For PAUB–RIMC it is the affine continuation. The large
numbers mean that the *geometric coordinate* is not the bottleneck; they do not
measure the residual after atmosphere, clocks, receiver transforms or actual
phase extraction.

## Open terms and exact blocker

| Clause | State | Why it blocks measurement admission |
|---|---|---|
| Exact DPOD beacon coordinates, heights and phase centers | `UNRESOLVED` | Minute-resolution public positions are only suitable for screening. |
| One-way light time, Earth rotation/Sagnac, Shapiro and proper-time terms | `UNRESOLVED` | The range-rate screen is not yet the physical phase equation. |
| Troposphere, ionosphere and antenna maps | `UNRESOLVED` | Dual-frequency phase may constrain dispersive media, but no combination or bound is frozen. |
| Station frequency-shift factor `K` | `UNRESOLVED` | It must come from the actual RINEX station-reference header. |
| DORIS time, receiver-clock and time-reference flags | `UNRESOLVED` | Format semantics exist, but the candidate product and event-time error are unopened. |
| L1/L2 phase continuity and C1/C2 same-path witnesses | `UNRESOLVED` | Presence, flags, gaps and joint coverage have not been structurally qualified. |
| Shared receiver and channel-dependent biases | `UNRESOLVED` | Common-mode cancellation is plausible, not yet demonstrated or bounded. |
| Candidate-day product existence and interval coverage | `UNRESOLVED` | No 2026-09-02 observation product was present or accessed during the spike. |

The exact residual blocker is therefore not geometry. It is the lack of an
admitted transformation from DORIS phase/time/header fields to a bounded,
dual-beacon held-out coordinate. `UNRESOLVED` does not become zero merely
because the preliminary margin is large.

## Next maximum action after review

The smallest next step would be a **development-only, value-blind structural
and metadata qualification** using one distinct already published Sentinel-3A
DORIS day, tentatively `s3arx26242.001.Z`. It would test only header identity,
time semantics, station mapping and `K`, observable schema, flags, complete
window coverage and simultaneous L1/L2/C1/C2 availability. It must not read or
score a future primary and must not fit a detector.

The future candidate `s3arx26245.001.Z` is named only by the documented archive
convention. It was not present, opened, downloaded or frozen as a primary.
Development access is not authorized by this report.

## SHOCK

Two independent receive roots are not universally the cleanest topology. For
this physical question, independent ground transmitters observed by one
simultaneous dual-frequency spaceborne receiver may make common receiver-clock
effects more cancellable while preserving beacon-dependent geometry. The same
sharing also creates the unexpected risk that one downstream receiver or RINEX
transformation can imprint correlated channel structure on both beacons. Root
independence must therefore be derived from the claim, not inherited as a
global requirement.
