# Post-DRAO DOY233 change-of-abstraction review

## Decision

```text
DOY233_CONSUMED_CLOSED_NO_RETRY
EXACT_TRACK_CARDINALITY_REMOVED_FROM_FORWARD_MEASUREMENT_VALIDITY
ALL_TRACK_INVERSE_ROUTE_DEMOTED
FORWARD_MODEL_CONDITIONED_VERTICAL_RECOMMENDED
```

This is an offline review of committed plans, source and terminal receipts. It
does not reopen DRAO DOY233, select another artifact, score an observation or
create a new gate.

## BLOCK

The complete DOY233 product reached the frozen structural cardinality check.
Eight opaque tracks satisfied the frozen complete-track predicate across the
full grid; the plan admitted exactly seven. The one-clutter hypothesis surface
therefore had no representation for the observation and correctly did not
score it.

No receiver-integrity failure was established. The stopped path had already
required, for every counted track:

- L1C, L2W, C1C and C2W at every frozen epoch;
- zero or blank LLI on both phase fields;
- valid epoch flags and the exact grid.

Geometry-free continuity, same-path phase/code witnesses and orbital-versus-
null scoring remained `NOT_EVALUATED`.

## INFORMATION VALUE

The outcome discovered a category error in the contract:

```text
measurement validity
!=
membership in one fixed inverse hypothesis surface
```

The eighth complete track is evidence that the bounded receiver product had a
richer structural surface than assumed. It is not evidence of physical
clutter, corruption or orbital disagreement.

## CURRENT ABSTRACTION

Exactly seven tracks was necessary only for this question:

```text
Can six anonymous orbital curves be recovered from exactly seven tracks while
excluding exactly one unknown track?
```

It was not required to test whether six predeclared orbital geometries predict
six predeclared receiver-labelled phase tracks in a held-out interval. The
cardinality rule protected a targetless identity claim, not phase timing,
continuity, propagation or the orbital-versus-null comparison itself.

The frozen DOY233 outcome remains `MEASUREMENT_INVALID` under its own contract.
It must not be rewritten. Future contracts must not reuse that label when only
the available hypothesis surface is too small; the attributable state would
be `HYPOTHESIS_SURFACE_UNSUPPORTED`, with measurement validity still
unevaluated or separately evaluated.

## ALTERNATIVES

### A. Change seven to eight and allow two exclusions

For eight tracks and six orbital curves, exhaustive symmetry would require
all 28 six-track subsets, all 720 assignments for orbital and time-reversed
families and one affine null per subset: 40,348 hypotheses.

This cannot rescue DOY233: the data are consumed, the rule would be chosen
after observing `8`, and the values were destroyed. Repeating this expansion
after every new multiplicity is the rejected gate treadmill.

### B. Freeze a K-conditional all-track inverse scorer

A future scorer could predeclare an allowed K range, enumerate every six-of-K
subset and apply the same subset freedom to every family. It would also need a
K-conditional false-selection/multiplicity control and witnesses for every
admitted subset. This is conceptually possible, but it preserves the hardest
identity problem and adds no shorter route to the first orbital result.

### C. Predeclare receiver-labelled tracks for a forward test

Select the orbital codebook from geometry before artifact access, then require
only those labelled tracks. Extra complete tracks are retained as descriptive
structure but neither invalidate the measurement nor enter selection. Missing
or invalid required tracks still fail admission.

This route is model-conditioned and cannot establish satellite identity. It
can directly test whether the frozen orbital dynamics predict a held-out phase
coordinate better than affine and geometry-destroying nulls. This is the
recommended route.

### D. Return immediately to two independent receiver roots

A distributed pair would produce stronger observer-coupled evidence and should
remain the later target. It currently costs more capability qualification than
the single-root forward repair and is not needed to diagnose the cardinality
failure.

## BEST PHYSICAL PATH

```text
orbit-only station/date screen
  -> predeclared station, window and PRN codebook
  -> one distinct unopened artifact
  -> required-track structural and physical admission
  -> prefix-only nuisance calibration
  -> held-out orbital versus frozen affine/time-destroying nulls
  -> one outcome
```

The observation receiver's PRN labels are part of the model-conditioned
coordinate and must be declared before access. They are not independent
identity evidence. The maximum positive claim stops at
`ORBITAL_MODEL_PREDICTIVELY_PREFERRED` for the predeclared labelled coordinate.

The following primitives survive:

- exact event-time grid and held-out suffix;
- core dual-frequency phase, zero LLI and no interpolation;
- geometry-free continuity and same-path code witnesses;
- common-mode removal and prefix-only constant-plus-rate nuisance;
- orbital, affine and geometry-destroying families with identical observation
  intervals and transforms;
- one immutable outcome and zero observation-value persistence.

The following abstractions are removed from the first forward path:

- exact total track cardinality;
- a fixed clutter budget;
- all-track anonymous subset search;
- post-score PRN identity reveal;
- identity-candidate language.

## ACTION

Do not repair or rerun DOY233. Do not build a generic K-track scorer now.

The next maximum action is one bounded, orbit-only screen over an explicitly
limited station/date set. It may compute visibility and discriminability but
must not query, select or open an observation artifact. It stops with either a
single labelled forward geometry worth freezing or
`NO_FORWARD_LABELLED_GEOMETRY_ADMITTED`.

Before that future work begins, its information-gain statement is:

```text
Physical question:
  Do predeclared orbital curves predict held-out receiver-labelled phase
  dynamics better than frozen non-orbital alternatives?

New information produced:
  A real orbital-versus-null result without claiming targetless identity.

Why the existing experiment cannot answer it:
  DOY233 is consumed and its exactly-seven inverse surface refused before
  score.

Minimum experiment:
  One orbit-only selected geometry and one later distinct, unopened artifact;
  fixed labelled tracks, prefix calibration, held-out suffix and frozen nulls.

Stop condition:
  One terminal outcome; no replacement artifact, retry, track substitution or
  held-out refit.
```

## SHOCK

The eighth track is not a request for a larger clutter model. It reveals that
the project had silently promoted targetless identity recovery above the more
basic claim ladder. The physically cheaper experiment is allowed to know which
receiver-labelled tracks it intends to test, provided it stops claiming that
the orbital model independently discovered their identities.
