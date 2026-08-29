# Post-blind-orbit review: separate dynamics from code identity

## Scope

This is a bounded offline scientific review of the consumed AMC DOY226
outcome. It does not reopen or rescore the primary, query an observation
locator, search a receiver inventory, select a new station or create a gate.

```text
Physical question:
What remaining causal dependency prevents the positive blind-orbit result
from becoming independent satellite-identity evidence?

New information produced:
Which measurement topology can make orbital dynamics and signal identity two
separately frozen witnesses instead of allowing the receiver's PRN assignment
to choose the coordinate before orbital scoring.

Why the existing experiment cannot answer it:
The executor selected the G22 and G30 RINEX fields before it constructed the
anonymous coordinate. The scorer was identity-blind, but the measurement path
was already PRN-conditioned.

Minimum next experiment:
First prove offline that anonymous simultaneous GNSS tracks can preserve a
candidate-pair orbital distinction while a separately sealed code-identity
receipt remains unavailable to the orbit scorer.

Stop condition:
Stop before capability discovery if anonymous tracking, timing, propagation
or oscillator envelopes can absorb the orbit-versus-null distinction, or if
the code-to-PRN mapping must enter the orbital scorer.
```

## Authoritative result

The consumed primary remains:

```text
BOUNDED_TRUE_ORBIT_PREFERRED
```

The following ordering is a receipt-only join with the mapping that was sealed
before primary access. No model was rerun and no score was changed.

| Revealed hypothesis | Held-out residual p-p |
| --- | ---: |
| G22 relative to G30 | `6.104475 m` |
| prefix-affine null | `18,768.100639 m` |
| G06 relative to G30 | `26,490.063488 m` |
| G14 relative to G30 | `49,348.823240 m` |
| G17 relative to G30 | `54,729.304010 m` |
| G19 relative to G30 | `94,424.941279 m` |

The correct candidate beat the controlling affine null by `18,761.996164 m`,
above the frozen `7,339.701235 m` pairwise guard. This is strong evidence that
the held-out dynamics match the predeclared G22-relative-to-G30 trajectory
within the frozen family.

## Claim-ladder audit

| Claim level | State | Reason |
| --- | --- | --- |
| `MEASUREMENT_VALID` | supported | All frozen structural, timing, continuity and same-path clauses passed. |
| `ORBITAL_SIGNATURE_DETECTABLE` | supported | The controlling separation exceeded the frozen physical guard. |
| `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` | supported | The prefix-fitted model retained the smallest untouched-suffix residual. |
| `SPECIFIC_ORBIT_PREFERRED` | bounded support | G22 beat four predeclared wrong-orbit alternatives and the affine null. |
| `HELD_OUT_STATION_CONFIRMED` | not established by this experiment | AMC is the only observer in this blind assignment. Prior PIE/AMC work is forward, PRN-conditioned evidence. |
| `REPEATED_PASS_CONSISTENCY` | not established for blind assignment | The blind candidate-ranking mechanism has one consumed pass. |
| `IDENTITY_CANDIDATE_SUPPORTED` | not authorized | The receiver correlated the GNSS code and emitted PRN-labelled RINEX before blinding. |

The result is not weakened by this boundary. It answers a narrower question
very strongly: given a real coordinate already associated upstream with two
GNSS tracking channels, which frozen orbital dynamics explain its future
shape? It does not show that orbital dynamics independently discovered the
signal identity.

## Current causal topology

```text
physical GNSS RF
    -> receiver code correlation and tracking
    -> PRN-labelled G22/G30 RINEX fields
    -> executor selects G22 minus G30
    -> anonymous coordinate
    -> identity-blind orbital scorer
    -> hashed score receipt
    -> mapping reveal
```

The blind boundary protects the final model comparison from PRN labels. It
does not cross the earlier selection boundary. A second RINEX observer would
change station geometry and hardware instance, but it would preserve this
same information topology.

## Competing next routes

### Route A — another PRN-labelled RINEX observer

This would test whether the bounded blind preference repeats at another
observer. Its negative could be interpretable after qualification, but its new
information is small: GOLD/NLIB, PIE and AMC already show observer/pass
transfer for the same orbit-signal family, while the cross-receiver-family
screen terminated without an admissible new root. It would not remove PRN
conditioning.

Disposition: **do not make this the automatic next experiment**.

### Route B — anonymous raw-GNSS tracks with a sealed code witness

Use one immutable, time-qualified raw GNSS IF/IQ artifact to create two
information branches:

```text
raw simultaneous GNSS samples
    -> frozen acquisition/tracking process
       -> anonymous continuous tracks A and B
       -> orbit-only candidate scorer
       -> hashed orbital receipt

    -> separately sealed code-correlation identity receipt
       -> unavailable to the orbital scorer

after both receipts are immutable
    -> reveal code identity
    -> concordance or discordance with orbital assignment
```

The acquisition process may need spreading-code templates to make the
below-noise GNSS carriers observable. That means this is not code-free RF and
the two branches are not independent hardware roots. The causal improvement is
more precise: code identity becomes an explicit same-sample orthogonal witness
rather than an unexamined input to the orbit scorer. A transparent raw-sample
path also cuts dependence on proprietary RINEX tracking output.

Before any real artifact is sought, an offline mechanism spike must show that
the anonymous track coordinate remains discriminative under conservative:

- sample-zero event-time and sample-rate error;
- common and differential oscillator terms;
- single- or dual-frequency propagation uncertainty;
- cycle slips, gaps and phase ambiguity;
- code/acquisition uncertainty and track permutation;
- frozen affine, wrong-orbit and geometry-destroying alternatives.

If dual-frequency civilian tracking is required, band and signal availability
must be demonstrated rather than inferred from the current L1C/L2W RINEX
fields. No current primary value may be used as development data.

Disposition: **recommended minimum next mechanism**.

### Route C — non-GNSS independently timed raw RF

A narrowband satellite carrier with ADC-bound UTC, disciplined frequency,
pre-pass orbital lineage and a prospectively frozen tracker would remove the
GNSS code/RINEX path completely. This has the highest modality independence.
The prior bounded audit admitted no such dataset, however, and repeating
metadata search would be infrastructure drift.

Disposition: retain as the higher-ceiling route only when a concrete
time-qualified capability becomes available independently of a new search
program.

### Route D — rescore the consumed primary with harder candidates

This would use outcome knowledge to alter the candidate family and would
violate the one-shot plan. It would not add an independent measurement.

Disposition: **forbidden**.

## Comparison by physical information gain

| Rank | Route | New causal distinction | Negative interpretability | Current feasibility | Decision |
| ---: | --- | --- | --- | --- | --- |
| 1 | Anonymous raw-GNSS tracks + sealed code witness | Separates orbital assignment from revealed code identity and proprietary RINEX output | Potentially high after an offline envelope | Unknown until mechanism spike | proceed offline only |
| 2 | Non-GNSS time-qualified raw RF | Removes the complete GNSS tracking and code path | Potentially highest | No admitted capability in bounded audit | wait for a concrete capability |
| 3 | Another RINEX observer | Adds observer/pass replication | High | Technically familiar | insufficient new information |
| 4 | Primary rescore | None | Invalid | Available only post hoc | forbidden |

The ranking is by the ambiguity removed, not implementation convenience.

## Recommended next vertical, still offline

The next work should be one small synthetic mechanism spike, not a data search
or runtime:

1. Treat the consumed G22/G30 geometry and candidate family as a closed
   development fixture only.
2. Generate anonymous simultaneous track coordinates from orbital geometry;
   do not use AMC observation values.
3. Keep every code/PRN mapping outside the scoring process and reveal it only
   after a synthetic score receipt is fixed.
4. Include a track-permutation null, prefix-affine null and the existing
   wrong-orbit family under the same timing and propagation envelope.
5. Test at least one correct-model case, one wrong-orbit case, one code/orbit
   discordance and one below-detectability case.
6. Stop without capability discovery unless a non-empty discriminative region
   survives.

Only after that proof may one bounded, explicitly predeclared raw-GNSS
capability set be considered. `NO_CAPABILITY_AVAILABLE` and
`NO_FALSIFIABLE_RAW_TRACK_EXPERIMENT` must remain valid terminals; the project
is not required to manufacture an observation.

## SHOCK

The PRN correlation is not merely a contaminant to remove. If its result is
sealed separately, it can become the orthogonal physical witness that the
current experiment lacks:

```text
orbit dynamics says which candidate fits
code structure says which signal was tracked
agreement is checked only after both claims are immutable
```

That topology asks a stronger question than either another station or a more
difficult post-hoc candidate list. It also makes the remaining dependence
honest: the two witnesses share the same RF samples and front-end, so agreement
supports a bounded identity candidate but does not claim independent hardware
confirmation.

## Stop boundary

No observation, capability search, product selection, detector freeze or live
authority follows from this review. Do not reopen AMC DOY226, continue the
traditional GNSS station ladder, or generalize the proposed separation into a
framework. The next permissible implementation is only the offline mechanism
spike described above.
