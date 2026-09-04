# GNSS all-track one-clutter mechanism spike

## Outcome

```text
ALL_TRACK_ONE_CLUTTER_MECHANISM_DISCRIMINATIVE
```

This is a bounded offline change-of-abstraction spike, not a new gate. It uses
the already closed synthetic orbital prediction fixture plus two frozen,
model-only orbital curves compiled for another observer and pass. The latter
are adversarial structured clutter only: they assert neither concurrent
visibility nor a relation to an ALGO track. The spike does not reopen or score
ALGO, access an observation product, select a primary or make a real
measurement claim.

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
| six orbits + independent compiled orbital shape | orbital preferred | concordant | 0.733056 m residual; assignment margin 8,431.948803 m; null margin 14,670.872232 m |
| all tracks affine | non-orbital preferred | affine null supported | orbital margin is negative |
| time-reversed geometry | non-orbital preferred | geometry null supported | destroyed event ordering is not called orbital |
| two arbitrary clutter tracks, budget one | no admissible hypothesis | unresolved | excess contamination cannot be hidden |
| one expected orbit removed, two independent compiled orbital shapes added | no admissible hypothesis | unresolved | best orbital residual 26,567.921503 m |
| orbital score preferred, code witness swaps two identities | orbital preferred | discordant | post-hash witness vetoes physical confirmation |
| orbit-like duplicate clutter | ambiguous | unresolved | assignment margin 0 m |
| orbit-like clutter shifted locally by 1.5 s | ambiguous | unresolved | nonzero 1,683.810869 m assignment margin remains below the 7,339.701235 m guard |

The positive controls exceed the guard both against the next orbital
assignment and against the best null. The compiled-curve control shows that
the result is not specific to sinusoidal clutter. The missing-candidate,
duplicate and small time-coordinate perturbation controls show that the
clutter allowance is not a general escape hatch: it cannot manufacture a
complete codebook from two structured nonmembers and cannot force a decision
when two orbital shapes are identical or merely too close at the frozen
resolution. The 1.5 s resampling is a local near-degeneracy stress, not a claim
that it is a separately propagated satellite orbit. Finally, a preferred
anonymous orbital assignment is not promoted to a physical confirmation when
the post-score code witness disagrees.

The structured curves come from
`AMC_OBSERVER_PRIMARY_PREDICTIONS.json`, exact SHA-256
`c9f7236f3cc221cb8485fe82f0a739e720ee3725f9dbf7c7fcc54c4167794155`.
Its own observation-access counters are zero. Only `WRONG_ORBIT_G01` and
`ORBITAL_G22` model coordinates enter these controls; no AMC or ALGO
observation value enters the scorer.

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
| clutter spike | `d61d73a55529a5659b5860481cedf089d4c20f653a53b1bd9aeefa480dd29e45` |

## SHOCK

The extra complete track was not merely an obstacle. It exposed that “exactly
six” mixed a physical orbit family with an accidental receiver topology. A
bounded contamination model is the better abstraction—but only prospectively,
never as a post-hoc rescue of the artifact that revealed the problem.

## Stop

No ALGO score, new artifact, primary selection, geometry search or observation
access is authorized by this result.
