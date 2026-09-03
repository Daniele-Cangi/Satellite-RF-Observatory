# GNSS all-track one-clutter mechanism spike

## Outcome

```text
ALL_TRACK_ONE_CLUTTER_MECHANISM_DISCRIMINATIVE
```

This is a bounded offline change-of-abstraction spike, not a new gate. It uses
only the already closed synthetic orbital prediction fixture. It does not
reopen or score ALGO, access an observation product, select a primary or make a
real measurement claim.

## Information-gain test

```text
Physical question:
  Can six orbital curves be identified inside seven anonymous tracks when one
  arbitrary clutter track is allowed before scoring?

New information produced:
  The exact-six count is not mechanically necessary. A symmetric one-clutter
  model can remain discriminative and can still refuse excess or orbit-like
  clutter.

Why the existing experiment cannot answer it:
  The frozen scorer represents a six-to-six bijection only. It correctly
  refused ALGO when seven tracks were complete.

Minimum experiment:
  Seven opaque synthetic tracks; all six-of-seven exclusions; every six-orbit
  assignment; affine-only and time-reversed-geometry nulls with the same
  exclusion allowance; prefix-only nuisance and a held-out suffix.

Stop condition:
  Stop after synthetic controls. Do not apply the post-outcome model to ALGO
  and do not select a new product or primary.
```

## Closed surface

| Property | Frozen value |
|---|---:|
| opaque observed tracks | 7 |
| tracks evaluated per hypothesis | 6 |
| arbitrary clutter allowance | exactly 1 |
| orbital injections | 5,040 = 7 exclusions × 6! assignments |
| time-reversed geometry nulls | 5,040 |
| affine-only nulls | 7 |
| total opaque hypotheses | 10,087 |
| prefix epochs | 79 |
| held-out epochs | 60 |
| free time phase | no |
| held-out refit | no |
| prefix nuisance | constant + rate per centered included track |
| effective continuous parameters | 10 for every hypothesis |
| pairwise/absolute guard | 7,339.701234647398 m |
| persisted observation values | 0 |

Every orbital and time-reversed hypothesis receives the same one-track
exclusion. The affine null enumerates every exclusion but has no meaningless
permutation of six identical zero curves. No observed track is removed before
the exhaustive surface is scored.

The scorer sees model-family names because model comparison requires them. It
does not see PRNs, code identities, reveal mappings or the ALGO result. Model
codes are exposed only after the score receipt is hashed.

Metrics are quantized to six decimal places in receipts. The resulting
micrometre numerical granularity is many orders below the 7.34 km guard and
prevents platform-level floating noise from changing receipt hashes.

## Controls

| Scenario | Score state | Final state | Key result |
|---|---|---|---|
| six orbits + arbitrary clutter | orbital preferred | concordant | assignment margin 8,431.948803 m; null margin 16,577.588442 m |
| permuted track/clutter slots | orbital preferred | concordant | assignment margin 8,432.165039 m; null margin 16,577.551587 m |
| all tracks affine | non-orbital preferred | affine null supported | orbital margin is negative |
| time-reversed geometry | non-orbital preferred | geometry null supported | destroyed event ordering is not called orbital |
| two arbitrary clutter tracks, budget one | no admissible hypothesis | unresolved | excess contamination cannot be hidden |
| orbit-like duplicate clutter | ambiguous | unresolved | assignment margin 0 m |

The positive controls exceed the guard both against the next orbital
assignment and against the best null. The two critical negative controls show
that the clutter allowance is not a general escape hatch: it cannot absorb two
bad tracks and cannot choose between physically indistinguishable duplicate
tracks.

## What changed conceptually

The failed assumption was:

```text
number of structurally complete tracks == number of orbital curves
```

The surviving primitive is narrower:

```text
predeclared contamination budget
+ symmetric enumeration of every exclusion
+ same freedom for orbital and null families
+ held-out assignment and model-family margins
```

This does not retroactively admit ALGO. The one-clutter abstraction was chosen
after learning that ALGO had seven complete tracks, so scoring those data with
it would be outcome-conditioned. ALGO remains a consumed development result.

## Remaining falsification conditions

A future independent experiment would have to freeze before access:

- seven-track admission and exactly one arbitrary clutter allowance;
- all-exclusion enumeration, with no PRN filtering;
- the six-orbit family and the time-reversed/affine null families;
- the same prefix, held-out, nuisance and guard semantics;
- refusal for fewer than six usable tracks, more than one required exclusion,
  non-unique orbital injection or insufficient orbital-versus-null margin.

It would still need real phase continuity, timing, propagation and hardware
envelopes. This spike proves only the selection mechanism.

## Source binding

| Source | Canonical SHA-256 |
|---|---|
| clutter scorer | `ecdf2afffed80f279a23bcaa46a870b5acee3272709e166c8e9c2a97d1205033` |
| clutter spike | `ca98054bc79ff12902a0eba8b5ccd0c489e643ef5a00876aa5f60f40c37ab614` |

## SHOCK

The extra complete track was not merely an obstacle. It exposed that “exactly
six” mixed a physical orbit family with an accidental receiver topology. A
bounded contamination model is the better abstraction—but only prospectively,
never as a post-hoc rescue of the artifact that revealed the problem.

## Stop

No ALGO score, new artifact, primary selection, geometry search or observation
access is authorized by this result.
