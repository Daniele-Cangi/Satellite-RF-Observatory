# Bounded blind-orbit assignment: orbit-only scope

## Scientific boundary

This is not a new gate. It is one bounded, observation-blind orbit screen
after the traditional GNSS replication route and the bounded raw-RF metadata
route both terminated.

```text
Physical question:
Can the already demonstrated G22-relative-to-G30 phase dynamics distinguish
G22 from four deliberately close GPS orbital alternatives when the PRN-to-
hypothesis mapping is hidden from the future scoring stage?

New information produced:
Whether a genuinely difficult, prospectively frozen bounded orbit-assignment
problem exists before any new observation product is selected or opened.

Why existing experiments cannot answer it:
PIE and AMC compared G22 with three convenient wrong-orbit alternatives whose
held-out separations were very large. They established forward prediction,
not orbit specificity inside a close candidate family. The cross-family and
raw-RF routes subsequently stopped before another physical outcome.

Minimum experiment:
Five exact predeclared broadcast-navigation days, one already characterized
observer geometry, one fixed target/reference mechanism, four model-selected
close orbital alternatives, one affine null and no observation input.

Stop condition:
Stop before observation-product discovery unless one 139-epoch window admits
four jointly visible alternatives whose prefix-calibrated held-out distinction
remains positive after the complete frozen pairwise physical guard.
```

The maximum result of this screen is geometry selection. It cannot establish
satellite identity, measurement validity or an orbital preference.

## Frozen causal inputs

- observer geometry: `AMC400USA`, latitude `38.803125 deg`, longitude
  `-104.524597 deg`, ellipsoidal height `1911.3941 m`;
- target orbit used only by the orbit-only screen: `G22`;
- fixed reference orbit: `G30`;
- population: healthy GPS broadcast ephemerides `G01`--`G32`, excluding
  `G30`; no observation availability or signal values may filter it;
- orbital family size: exactly five hypotheses, `G22` plus four alternatives;
- grid: `30 s`, `139` epochs, indices `0--78` calibration prefix and
  `79--138` held-out suffix;
- visibility: every family member and `G30` must remain at or above `15 deg`
  on the nominal and direct common `t +/- 15 s` grids for the complete window;
- coordinate: anchored one-station target-minus-`G30` geometric range in
  metres, with the same L1C/L2W ionosphere-free measurement interpretation
  already demonstrated by PIE and AMC;
- future measurement guard: the unchanged AMC pairwise decision guard
  `7339.701234647398 m` peak-to-peak. This screen may not reduce it.

The five frozen navigation authorities are:

| GPS date | DOY | Exact NOAA locator |
| --- | ---: | --- |
| 2026-08-12 | 224 | `https://geodesy.noaa.gov/corsdata/rinex/2026/224/brdc2240.26n.gz` |
| 2026-08-13 | 225 | `https://geodesy.noaa.gov/corsdata/rinex/2026/225/brdc2250.26n.gz` |
| 2026-08-14 | 226 | `https://geodesy.noaa.gov/corsdata/rinex/2026/226/brdc2260.26n.gz` |
| 2026-08-15 | 227 | `https://geodesy.noaa.gov/corsdata/rinex/2026/227/brdc2270.26n.gz` |
| 2026-08-16 | 228 | `https://geodesy.noaa.gov/corsdata/rinex/2026/228/brdc2280.26n.gz` |

Compressed and uncompressed byte counts and SHA-256 values are descriptive
outputs of the later orbit-only materialization. Navigation bytes may exist
only ephemerally and must be destroyed after compilation.

## Frozen difficulty and ranking rule

For every complete candidate window and every alternative orbit `s`:

1. form the anchored range curves `G22 - G30` and `s - G30` on the identical
   observer/time grid;
2. fit one constant plus one linear rate to their difference using only the
   79-epoch prefix;
3. propagate that fixed prefix affine correction into the 60-epoch held-out
   suffix;
4. compute held-out peak-to-peak and RMS separation;
5. apply the unchanged pairwise physical guard.

The affine nuisance has exactly two parameters for every orbital hypothesis,
is calibrated only on the prefix and receives no suffix refit, free time
phase, time warp, spline or candidate-dependent complexity.

For each window, retain the four alternatives with the smallest strictly
positive remaining margin. A window is robustly admissible only when all four
remaining margins are at least one additional full decision guard; equivalently
each held-out separation must be at least twice the guard. The same condition
must hold against the prefix-frozen affine-only null.

Rank admissible windows by:

1. smallest maximum held-out orbital-alternative separation, so the selected
   family is difficult rather than merely convenient;
2. largest minimum remaining margin;
3. largest minimum time-shifted elevation;
4. earliest date and start epoch.

No ranking input may depend on an observation product, signal value, archive
availability or decoder behavior.

## Blindness and future claim scope

The screen may name G22 because it compiles the prospective challenge. A
future scorer must receive opaque hypothesis identifiers and a model-blind
measurement coordinate; the PRN-to-hypothesis mapping must be sealed outside
the scoring surface. This hides the association only from the evaluator. It
does not undo the receiver's upstream GNSS code correlation and therefore can
authorize at most:

```text
BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET
```

It cannot authorize targetless RF identity or free orbit recovery.

## Forbidden in this screen

- reopening, rescoring or using observation values from PIE, AMC, GOLD/NLIB,
  ALGO/MDO or any other consumed experiment;
- discovering or opening a new observation locator, header or payload;
- selecting a receiver, qualification artifact or primary product;
- changing G0/G1, the physical guard, the prefix/held-out split or event-time
  bound;
- choosing alternatives after seeing RF/GNSS observations;
- a sixth navigation date, global inventory, generic framework or detector.

Allowed outcomes are exactly:

```text
BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED
NO_DIFFICULT_FAMILY_WITH_POSITIVE_MARGIN
```

