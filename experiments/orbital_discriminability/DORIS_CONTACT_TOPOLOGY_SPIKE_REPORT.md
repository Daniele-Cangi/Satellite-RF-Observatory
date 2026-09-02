# DORIS contact-topology sufficiency spike

## Terminal outcome

`DORIS_STRUCTURAL_VISIBILITY_NOT_FALSIFIABLE_FROM_RETAINED_RECEIPT`

This is an offline change-of-observable spike, not a new gate and not an
orbital result. It opened only four frozen JSON receipts and the repository
scanner source. Network, orbit artifacts, RINEX artifacts, observation values
and new measurements remained at zero.

## Physical question

Can the order and duration of DORIS beacon contacts form a held-out orbital
observable without requiring two beacons to be visible simultaneously?

The proposed causal chain is:

```text
candidate orbit + beacon geometry
        -> predicted visibility intervals
        -> receiver acquisition and retention
        -> station-record presence sequence
        -> held-out contact order and duration
        -> orbital model versus frozen nulls
```

If the complete chain were admitted, it would avoid phase magnitude, carrier
frequency, beacon-USO phase, receiver-clock phase, ionospheric phase correction
and amplitude calibration. Its claim ceiling would nevertheless be only
orbital visibility topology within a predeclared receiver-acquisition model,
not RF-phase agreement or satellite identity.

## What the frozen evidence actually retains

The development header declares 56 beacon stations. The structural scanner
read all 39,024 station records without decoding a numerical observation
value, but constructed state only for four preselected station IDs: D40, D46,
D47 and D49. For each it retained only the five longest phase-continuous
segments. Those segment boundaries mean LLI/discontinuity or a station sample
gap; they do not mean geometric acquisition, rise or set.

The executed scanner remains attributed to frozen commit `e2336295...` and
source SHA-256 `84a0d817...`. The current source audited for this spike has
SHA-256 `9042f81f...`; its later epoch-parser hardening did not change the
preselected-station or top-five retention rules. The receipt records both
identities rather than relabeling the historical execution.

| Required fact | Frozen evidence | State |
|---|---|---|
| a station record existed at a tagged DOR epoch | retained for the selected summaries | `PARTIALLY_SUPPORTED` |
| complete 56-station presence sequence | four stations summarized; no epoch sequence retained | `NOT_RETAINED` |
| all contact intervals rather than top-k summaries | five longest segments per selected station | `NOT_RETAINED` |
| geometric rise/set boundary | phase/LLI/gap boundaries only | `NOT_RETAINED` |
| finite DOR-to-orbit event-time error | DOR tags exist; numerical bound was never admitted | `UNRESOLVED` |
| receiver scheduling/acquisition/dropout policy | absent | `UNRESOLVED` |
| exact development-day orbit grid | not bound by the descriptive receipts | `NOT_RETAINED` |

The exact-coepoch receipt adds a positive PAUB-RIMC subset—196 epochs with
both stations present, 186 phase-valid—but remains a preselected pair summary.
It is not a network contact-event sequence.

## Why a negative contact is not evidence of nonvisibility

A positive record proves that the receiver produced a station record at that
DOR epoch. It does not identify the first geometrically possible acquisition.
An absent record has several causally live explanations:

- the station was below the physical visibility boundary;
- no receiver tracking channel was allocated to it;
- acquisition or link margin was insufficient;
- the tracking loop dropped the beacon;
- telemetry selection or ground editing removed the record;
- a phase discontinuity split a retained segment even though RF visibility
  continued.

Because the retained evidence cannot distinguish these cuts, `NOT DETECTED`
cannot be converted into `NOT VISIBLE`. This is the controlling failure, not
the number of stations or the missing orbit file by itself.

## Null discipline

The candidate nulls are a time-shifted orbit, a wrong orbit, station-identity
permutation and schedule/coverage-only structure. All remain
`NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY`. Comparing any of them to the top
five phase-continuity summaries would create a retrospective score from an
observable that was never retained.

No threshold was changed. No primary was selected. No measurement access or
retrospective orbital score is authorized.

## BLOCK

The receipts do not contain a complete, causally interpretable sequence of
contact events. In particular, absence is not bound to physical nonvisibility.

## INFORMATION VALUE

The contact-topology observable is physically meaningful and may bypass the
simultaneous-beacon geometry failure. The present result also establishes
that the historical structural receipts cannot test it. This is information
about the admissibility of an orbital observable, not merely about a parser.

## CURRENT ABSTRACTION

The simultaneous dual-beacon phase coordinate is not universally necessary.
Contact topology could replace it, but only when receiver acquisition and
retention are part of the measurement model. Reusing phase-continuity
summaries as contact intervals is not valid.

## ALTERNATIVES

A. On an independently authorized development artifact, retain every
station/epoch structural presence state and all intervals while retaining no
observation magnitude. Admit the receiver scheduling and acquisition policy
before any later primary.

B. Find an existing product whose contact/acquisition states and coverage
policy are already explicit and immutable; freeze orbit, event-time and nulls
before evaluating a distinct primary.

C. Use only positive event ordering if a separate instrument log identifies
physical acquisition events. The current records do not supply that witness.

D. Leave DORIS and select a sensor family that directly exposes an
observer-coupled held-out coordinate with interpretable missingness.

## BEST PHYSICAL PATH

Do not reopen the destroyed development artifact or access a candidate-day
product. DORIS contact topology should continue only if an outcome-independent
receiver scheduling/acquisition specification can make absences interpretable
and one independent structural qualification artifact is explicitly
authorized. Otherwise route D reaches a real orbital observation faster.

## Minimum future contract—not executed

A future qualification would have to freeze and retain:

- every station ID at every receiver epoch, including presence, absence and
  continuation state;
- all contact intervals, not a top-k list;
- exact product start, end and gaps;
- predeclared tracking-channel and scheduling policy;
- outcome-independent acquisition/dropout envelope;
- finite DOR-to-orbit event-time bound;
- orbit and station geometry before a distinct primary.

Observation magnitudes, post-outcome contact selection and unmodeled-absence
claims remain forbidden.

## SHOCK

Structure discarded as “not the measurement” for the phase question becomes
the measurement for contact topology. Evidence retention is therefore
hypothesis-dependent: a receipt can be sufficient for the experiment that
created it and still be incapable of answering a later, physically better
question.

The strict machine-readable result is
[`DORIS_CONTACT_TOPOLOGY_SPIKE_RECEIPT.json`](DORIS_CONTACT_TOPOLOGY_SPIKE_RECEIPT.json).
