# Post-AMC review: change the information, not the station count

## Scope and decision

This is a bounded offline change-of-information review. It creates no gate,
opens no observation product, searches no receiver inventory, selects no
station or date and does not reopen or rescore PIE, AMC or either consumed
ALGO/MDO primary.

```text
Physical question:
Which single next experiment can remove the strongest remaining causal
ambiguity in the PIE/AMC result while preserving a prospectively interpretable
orbital-versus-null outcome?

New information produced:
Whether the G22-relative-to-G30 orbital preference transfers across a declared
receiver implementation family, rather than only across physical instances,
observers and passes of SEPT POLARX5TR.

Why existing experiments cannot answer it:
PIE and AMC are distinct receiver serials, antennas, monuments, clocks,
firmware versions, observers and passes, but both receivers are POLARX5TR.
ALGO/MDO would have changed receiver family, but both one-shot primaries were
consumed before measurement admission and produced no orbital comparison.

Minimum experiment:
One bounded non-POLARX5TR observer, one value-blind qualification artifact and
one later distinct held-out primary. Preserve the G22/G30 continuous-phase
mechanism and frozen null discipline; change the receiver implementation
family and observer geometry, not the scientific question.

Stop condition:
Stop without a primary if no bounded candidate has documented cross-family
provenance, positive orbit-only margin, a date-separated qualification path
and a complete interpretable measurement contract. Stop the traditional GNSS
replication ladder after one terminal primary outcome, positive or negative.
```

The recommended next route is therefore one final
`CROSS_RECEIVER_FAMILY_OBSERVER_TRANSFER`. This name describes the causal cut;
it is not a gate or reusable framework.

## Authoritative boundary after AMC

The two terminal held-out results are:

| observer/pass | orbital residual p-p | affine residual p-p | frozen guard | result |
| --- | ---: | ---: | ---: | --- |
| PIE100USA / DOY223 | `2.279182 m` | `190,230.062153 m` | `7,899.820878 m` | `PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED` |
| AMC400USA / DOY221 | `1.409090 m` | `162,245.831253 m` | `7,339.701235 m` | `AMC_HELD_OUT_ORBITAL_MODEL_PREFERRED` |

AMC's exact affine-to-orbital peak-to-peak residual ratio is
`115,142.266363`. This is a descriptive ratio between residuals under one
shared frozen metric. It is not a likelihood ratio, Bayes factor, confidence
level or orbit-accuracy estimate.

Both primaries passed their predeclared event-time, core phase/LLI,
geometry-free continuity and same-path code witness clauses. Those clauses
exclude gross measurement-path failures. They do not prove the absence of
firmware-dependent tracking behavior, receiver-family bias, antenna/multipath
effects, phase wind-up or every other non-affine systematic.

The current maximum claim remains:

```text
INDEPENDENT_OBSERVER_AND_PASS_REPLICATION_FOR_THIS_ORBIT_SIGNAL_FAMILY
```

It is not satellite identity, free orbit recovery or receiver-family-
independent replication.

## Causal topology

PIE and AMC already separate:

- physical receiver serial and firmware version;
- antenna serial and monument;
- local time reference;
- observer coordinates;
- atmosphere and local multipath environment;
- date, pass and observer-specific predicted curve.

They still share:

- SEPT POLARX5TR receiver architecture and tracking implementation family;
- GNSS spreading-code identification upstream of the stored RINEX fields;
- RINEX observable semantics;
- the broadcast-navigation model family;
- the same analysis operator, anchor, metric and null definitions.

A receiver from a genuinely different declared family cuts the first shared
branch. It does not cut the remaining four. The next claim must therefore be
"replicated across the two declared receiver families", not "independent of
all receiver hardware".

Hardware diversity requires documented manufacturer/model lineage and a
different tracking implementation family. A different serial, firmware
version, antenna or station attached to another POLARX5TR is insufficient.
Conversely, manufacturer name alone is not enough if the relevant receiver or
tracking pipeline is shared or unknown.

## Route A — cross-receiver-family observer transfer

### Physical question

Does the predeclared G22-relative-to-G30 orbital trajectory remain preferred
to the same affine and wrong-orbit alternatives at an observer whose receiver
implementation family is not SEPT POLARX5TR?

### New causal cut

This route changes receiver correlator/tracking implementation together with
observer geometry and pass, while retaining the already successful physical
coordinate. A positive result would make a POLARX5TR-family explanation of
the two earlier outcomes substantially less plausible.

### Minimum proof shape

```text
frozen G22/G30 mechanism and null discipline
    -> bounded hardware-family-diverse capability set
    -> orbit-only observer/date discriminability
    -> one distinct-date value-blind qualification
    -> exact plan and prediction freeze
    -> one later primary
    -> one terminal held-out outcome
```

The coordinate remains an anchored target-minus-reference ionosphere-free
L1C/L2W carrier-phase coordinate. Every hypothesis receives the identical
anchor, grid, timing treatment and peak-to-peak/RMS ordering. No suffix fit,
free time phase, candidate-dependent transform or post-outcome threshold is
allowed.

The numerical measurement thresholds need not be copied blindly from
POLARX5TR. They must be justified and frozen before the primary from
outcome-independent specifications or the separate qualification artifact.
They may not be relaxed because a candidate or primary fails.

### Maximum claim

```text
CROSS_RECEIVER_FAMILY_OBSERVER_AND_PASS_REPLICATION_FOR_THIS_ORBIT_SIGNAL_FAMILY
```

This means replication across the receiver families explicitly present in the
experiment. It is not universal hardware independence or blind identity.

### Main risks

- another long capability search could become infrastructure drift;
- receiver family may be documented only after values are exposed;
- configuration may change between qualification and primary;
- a seemingly new vendor may share an unknown tracking implementation;
- archive or decode failure may again prevent physical admission;
- the very large G22-versus-null separation may make the result physically
  valid but add less orbital information than a harder identity test.

This is the recommended next experiment because it closes one already-declared
ambiguity with the smallest change to a mechanism that has produced two real
held-out outcomes.

## Route B — bounded blind orbit assignment

### Physical question

Can a frozen evaluator rank the correct orbit from a deliberately difficult,
predeclared candidate family when the PRN association is hidden from the
scoring stage?

### New causal cut

This changes the inference problem from forward validation to bounded orbit
identification. It tests orbit specificity more deeply than another receiver
replication and can use closer physical alternatives than G01/G14/G17.

It does not, however, create fully targetless identity evidence. The GNSS
receiver has already correlated the spreading code and separated measurements
into PRN-labelled fields upstream. Hiding that label from the scorer tests the
orbital evaluator, not the independence of the original signal association.

### Maximum claim

```text
BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET
```

### Main risks

- candidate-set difficulty could be selected post hoc;
- hiding labels may be mistaken for raw-signal identity;
- a new null and scoring design changes more than one causal variable at once;
- orbit candidates could be trivially separated rather than genuinely close.

This route has the higher scientific ceiling, but it should follow the single
cross-family closure rather than be mixed into it.

## Route C — independently timed RF observation

### Physical question

Does independently timestamped, frequency-calibrated RF preserve the
observer-specific orbital Doppler structure without relying on a geodetic
receiver's PRN-labelled tracking output?

### New causal cut

This changes measurement modality and cuts the common GNSS tracking/RINEX
pipeline. It is the most direct return to Internet RF observatory evidence.

### Maximum claim

```text
INDEPENDENT_RF_ORBITAL_DYNAMICS_CONSISTENT_WITH_FROZEN_MODEL
```

### Main risks

- absolute event time and ADC binding may be unavailable;
- frequency calibration and oscillator drift may absorb the signature;
- raw-IQ or ridge transformations may not preserve the required distinction;
- negative detectability may lack same-path witnesses;
- capability qualification can again dominate the satellite question.

This route offers the greatest modality independence but currently carries the
largest risk of an uninterpretable negative. It remains the preferred route
after the GNSS replication ladder closes.

## Comparison by new physical information

| Rank now | Route | New information | Negative interpretability | New assumptions | Infrastructure risk |
| ---: | --- | --- | --- | --- | --- |
| 1 | Cross-receiver-family observer transfer | Whether PIE/AMC preference survives a different tracking implementation | High after qualification | Low-medium | Low-medium if the set remains bounded |
| 2 | Bounded blind orbit assignment | Whether dynamics identify one orbit among close frozen candidates | High with a genuine candidate holdout | Medium-high | Medium |
| 3 | Independently timed RF | Whether raw RF reproduces the observer-coupled dynamics | Potentially highest | High until timing/calibration admission | High |

The ranking is for the immediate next action. It does not claim that Route A
has the highest eventual scientific ceiling. It is first because it isolates
one remaining ambiguity without simultaneously changing the observable,
candidate problem and measurement modality.

## Frozen boundary for the next bounded review

The next work may perform metadata and orbit-only analysis, but no observation
value access. It must satisfy all of the following:

1. Retain G22 as target, G30 as reference and the continuous ionosphere-free
   phase observer-transfer mechanism.
2. Retain an affine non-orbital alternative and frozen wrong-orbit families;
   every candidate receives the same operator and grid.
3. Declare at most five candidate receiver roots before any target-window
   observation access. No global inventory is required.
4. Exclude POLARX5TR and the consumed ALGO/MDO primary paths. A historical
   station may be considered only as a new, non-consumed experiment after the
   bounded set is declared; no old artifact or date may be reopened.
5. Require outcome-independent receiver-family, station, antenna, time-source
   and configuration provenance.
6. Rank observer/date candidates by complete orbital-versus-null margin, joint
   visibility and timing envelope before discovering target-window values.
7. Admit only RINEX phase/code/LLI semantics sufficient for the existing
   physical clauses. Optional signal strength remains non-fatal without a
   quantitative rule.
8. Use one structurally and physically independent qualification date and one
   later distinct primary date under the same documented configuration.
9. Freeze the decoder and transform path. Hatanaka is not forbidden as a
   format, but primary decode failure is terminal and authorizes no fallback.
10. Permit one primary, one window and one outcome. No replacement station,
    date, signal pair, null, threshold or decoder after plan freeze.

Stop without synthesizing an experiment if:

- receiver-family provenance is unknown;
- fewer than two genuinely distinct declared families remain across the
  evidence chain;
- no candidate geometry has positive complete margin;
- qualification and primary cannot be separated under stable configuration;
- any required non-affine term remains unresolved and can absorb the held-out
  distinction;
- progress would require a receiver catalog, decoder repair program or source
  inventory rather than one physical observation.

## Terminal policy

One cross-family primary is the final traditional GNSS replication, whatever
its outcome.

- A model preference may advance the bounded claim across the declared
  receiver families.
- An admitted null preference or ambiguity is a physical result and closes the
  route without retuning.
- A capability or measurement failure closes that exact path; it does not
  authorize repeated station substitution.
- If no experiment can be synthesized, move to Route B or Route C rather than
  expanding infrastructure.

## SHOCK

PIE and AMC show that the limiting uncertainty is no longer whether a frozen
orbital curve can survive a new observer and pass. It can. The next question is
which upstream interpretation produced that information: physical RF dynamics
that transfer across receiver implementations, or structure already stabilized
by one tracking family and labelled measurement pipeline.

Changing receiver family once is therefore useful, but repeating GNSS stations
after that would avoid the harder question. The project must then change the
information type: bounded orbit assignment or independently timed RF.
