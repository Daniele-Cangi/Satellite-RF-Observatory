# GNSS orbit/clock structure audit

## Purpose

This bounded audit asks whether the closed DOY-220 G14/G17 geometry could be
made prospectively falsifiable by replacing only the sample-wise broadcast-
orbit interval with an outcome-independent, temporally structured GPS
orbit/clock family.

It does not reopen the candidate, change its nulls, inspect a lower-ranked
date, select an observation product or create another gate.

## Information-gain test

Physical question:

> Is the negative physical margin mainly an artifact of treating broadcast
> orbit/clock error as an arbitrary per-epoch path perturbation?

New information produced: whether an official GPS range-rate error family can
reverse the already frozen `-330.378588 Hz` margin, and whether navigation-data
cutovers materially generate the G14-versus-G22 separation.

Minimum experiment: documentation plus exact-header-grid navigation metadata
and trajectory calculations. No GNSS observation artifact is involved.

Stop condition: if the margin remains non-positive even with zero broadcast-
orbit contribution, do not implement a new uncertainty compiler for this
candidate.

## Outcome-independent authorities

The audit used only two official specifications, inspected on 2026-08-24:

- [IS-GPS-200N](https://archive.gps.gov/technical/icwg/IS-GPS-200N.pdf),
  section 6.2.1: URA is a conservative RMS URE estimate for a specific signal
  and satellite. A scaled URA provides probabilistic instantaneous-URE
  integrity over the applicable transmission interval and worst footprint
  location. It does not publish an orbit/clock decomposition or temporal
  covariance.
- [GPS SPS Performance Standard, 5th edition](https://www.gps.gov/sites/default/files/2025-07/2020-SPS-performance-standard.pdf),
  sections 3.4.2, 3.4.3, 3.5.2 and 3.5.3: URRE is at most `0.006 m/s` as a 95%
  global statistic over any three-second interval. A `0.02 m/s` instantaneous
  URRE value is described as a high-probability 6-sigma design bound, but there
  is explicitly no URRE integrity NTE. The analogous URAE figures are
  `0.002 m/s^2` at 95% global and `0.007 m/s^2` as a high-probability design
  value. Perceived rate/acceleration errors caused by NAV dataset cutovers are
  excluded from those normal-operation figures.

Consequently:

- `URA` is an admitted statistical amplitude description, not a state
  covariance from which a unique smooth trajectory family can be derived;
- `0.006 m/s` is a global performance statistic, not a per-pass integrity
  bound;
- `0.02 m/s` is a useful design sensitivity, but not a formal NTE;
- adjacent broadcast solutions provide self-consistency evidence, not an
  upper bound on error relative to truth;
- post-pass precise products cannot reduce the envelope because they may
  assimilate tracking from the target interval.

## Frozen-window cutovers

All three relevant satellites change LNAV ephemeris at both 06:00 and 08:00
GPS inside the held-out interval.

| GPS epoch | Satellite | IODE | Position discontinuity | Station-differenced range jump |
|---|---|---|---:|---:|
| 06:00 | G14 | 220 → 221 | 0.235358 m | -0.022909 m |
| 06:00 | G17 | 33 → 35 | 0.198592 m | -0.020360 m |
| 06:00 | G22 | 52 → 53 | 0.246988 m | +0.023988 m |
| 08:00 | G14 | 221 → 222 | 0.316763 m | -0.010936 m |
| 08:00 | G17 | 35 → 51 | 0.885382 m | +0.075713 m |
| 08:00 | G22 | 53 → 54 | 0.256157 m | +0.014806 m |

After the common G17 reference cancels from the G14-minus-G22 model
comparison, the station-double-differenced jump is `-0.046897 m` at 06:00 and
`-0.025742 m` at 08:00. Through the frozen 60-second central derivative these
correspond to only `0.004107 Hz` and `0.002255 Hz`.

Exactly four feature epochs straddle a cutover: 05:59:30, 06:00:00, 07:59:30
and 08:00:00 GPS. Removing those points diagnostically, without refitting the
77-feature prefix, leaves the held-out peak-to-peak separation unchanged at
`403.37545402996614 Hz`. The selected distinction is therefore not a cutover
spike artifact. This diagnostic does not authorize retroactive masking in a
future measurement.

## Structured-rate sensitivity

The existing affine projection gain is `28.924759451075236`. The table below
replaces only the old `324.268025 Hz` pairwise broadcast-orbit contribution;
every other frozen physical term is unchanged.

| Orbit/clock treatment | Replacement pairwise contribution | Total pairwise envelope | Margin against G22 |
|---|---:|---:|---:|
| Original 4 m sample-wise path interval | 324.268025 Hz | 733.754042 Hz | -330.378588 Hz |
| Official 95% global URRE, 0.006 m/s | 7.296031 Hz | 416.782047 Hz | -13.406593 Hz |
| Official 6-sigma design URRE, 0.02 m/s | 24.320102 Hz | 433.806118 Hz | -30.430664 Hz |
| Perfect orbit/clock, zero contribution | 0.000000 Hz | 409.486016 Hz | -6.110562 Hz |

The two URRE substitutions are sensitivities, not admitted integrity
envelopes. More importantly, even the physically impossible zero-error case
does not admit the candidate. Refining orbit/clock alone cannot change the
decision.

## Result

```text
GNSS_ORBIT_CLOCK_STRUCTURE_INSUFFICIENT
```

The prior terminal outcome remains authoritative:

```text
GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_DOMINATES
```

No threshold, null, partition, candidate or physical term was changed. No
observation product was discovered or opened.

## Change of abstraction

### Block

The residual non-orbit envelope is already larger than the complete G22
separation. Orbit/clock refinement cannot rescue this geometry.

### Information value

The project has learned that the failure is not caused solely by an overly
adversarial broadcast-orbit bound and is not caused by broadcast ephemeris
cutovers. The remaining limit is the joint causal topology of antenna/wind-up,
signal-specific hardware, station/EOP/relativity, satellite-clock remainder,
event time and higher-order ionosphere.

### Best physical path

Do not create another orbit-bound successor. Return to SHOCK and compare
physically distinct observables or observer geometries in which several of
those terms cancel structurally or are measured by same-path witnesses. The
physical envelope must be part of selection, not applied only after choosing
the largest geometric separation.

Candidate examples for a later comparison are:

1. an additional independent GNSS station producing an overdetermined spatial
   quotient;
2. a multi-frequency/phase-continuous coordinate that observes rather than
   worst-case-bounds more signal-specific terms;
3. a different station geometry selected by remaining physical margin rather
   than raw orbital separation;
4. a physically distinct satellite RF route whose detector uncertainty is
   already below its predicted orbital-versus-null structure.

No alternative is implemented or selected in this audit.
