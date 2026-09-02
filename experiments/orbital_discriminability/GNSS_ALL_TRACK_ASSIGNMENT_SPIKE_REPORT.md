# Identity-blind GNSS all-track assignment spike

## Outcome

`ALL_TRACK_BLIND_ASSIGNMENT_MECHANISM_DISCRIMINATIVE`

This is a synthetic mechanism result. It uses only the closed AMC orbit
prediction bundle and mapping seal as development fixtures. It reopens or
rescores no consumed observation, selects no station/date/product, and makes
zero network, locator, header, payload and observation-value accesses.

## Why DORIS contact topology stops here

The preceding receipt audit left receiver scheduling as the decisive causal
cut. Primary DORIS documentation now resolves that question against the
proposed observable:

- DGXX/DGXX-S has seven Processing Units while more beacons can be physically
  co-visible;
- beacon designation may use received frequency, received power, random
  selection or the DIODE navigator;
- for Sentinel-3, channels 1--5 use DIODE and channels 6--7 use random DAS-T;
- selection modes can be changed during mission life and affect measurement
  count, duration, symmetry and continuity.

Consequently, absence of a station record is not a geometric occultation even
with a complete RINEX presence sequence. Reconstructing historical on-board
designation state would be a new instrument-reconstruction program, not the
minimum route to orbital information. DORIS contact topology is therefore
abandoned rather than repaired.

Primary sources:

- [IDS 2026 beacon designation by DORIS receivers](https://ids-doris.org/documents/report/ids_workshop_2026/IDS26_s1_Bonhoure_BeaconsDesignation.pdf)
- [CNES DORIS system and instrument description](https://cnes.fr/projets/doris/systeme)
- [IDS station policy and free-channel constraint](https://ids-doris.org/resources/technical-documents.html?id=38&view=category)

## Physical question

Can held-out orbital dynamics assign every continuous track in a bounded
observation without selecting a target or reference by PRN before scoring?

The information topology is:

```text
all structurally admitted simultaneous tracks
        -> opaque track identifiers
        -> all orbit-to-track bijections + affine null
        -> common-mode removal
        -> prefix-only nuisance projection
        -> held-out opaque score
        -> score SHA-256

separate receiver code labels
        -> witness SHA-256 before scoring
        -> unavailable to scorer

after score hash
        -> assignment reveal + code-label reveal
        -> CONCORDANT / DISCORDANT / UNRESOLVED
```

The change from the earlier blind experiment is material. G22 and G30 are no
longer selected to construct the coordinate. The scorer receives all six
tracks, six anonymous model curves and every one of the `6! = 720` bijective
assignments, plus one prefix-affine null.

## Frozen scoring semantics

Per-epoch ensemble centering removes the same-clock common mode without
choosing a reference track. Each hypothesis receives the same prefix-only
constant and linear rate per centered track. Because centering removes one
track degree of freedom, this is ten effective parameters rather than twelve.
The closed fixture reconstructs individual curves in a G30-zero mathematical
gauge because its source bundle stored relative predictions; adding any common
curve to all six models leaves ensemble-centered scoring unchanged. G30 is
therefore not a privileged observed track or scorer input.

The untouched 60-epoch suffix is ranked by maximum per-track peak-to-peak
residual, then aggregate RMS, then opaque identifier. A model is preferred
only when both clauses pass:

1. its best absolute held-out residual is no greater than the frozen
   development guard;
2. its improvement over the runner-up is greater than that same guard.

There is no free time phase, suffix refit, target-specific exclusion or
candidate-dependent complexity.

## Synthetic results

The historical `7,339.701235 m` pairwise guard is used only as a conservative
development boundary. The exact correct fixture has a numerical-zero best
residual and an `8,432.443650 m` preference margin.

| Scenario | Score state | Best residual | Preference margin | Post-hash result |
|---|---|---:|---:|---|
| complete correct assignment | `OPAQUE_ASSIGNMENT_PREFERRED` | 0.686779 m | 8,431.916292 m | `ORBIT_CODE_CONCORDANT` |
| same dynamics, swapped code labels | `OPAQUE_ASSIGNMENT_PREFERRED` | 0.686779 m | 8,431.916292 m | `ORBIT_CODE_DISCORDANT` |
| permuted opaque track slots | `OPAQUE_ASSIGNMENT_PREFERRED` | 0.686779 m | 8,431.977388 m | `ORBIT_CODE_CONCORDANT` |
| prefix-affine tracks | `OPAQUE_ASSIGNMENT_PREFERRED` | 0.686779 m | 54,161.484210 m | `NON_ORBITAL_NULL_SUPPORTED` |
| smooth out-of-family curvature | `NO_ADMISSIBLE_OPAQUE_ASSIGNMENT` | 22,515.985404 m | 0 m | `ORBIT_ASSIGNMENT_UNRESOLVED` |
| midpoint of closest assignments | `AMBIGUOUS` | 4,216.221825 m | 0 m | `ORBIT_ASSIGNMENT_UNRESOLVED` |

The absolute-fit clause matters: without it, a badly mismatched family could
still force a winner merely because one wrong model is less wrong than the
others.

## What this does and does not remove

Removed from the experiment-side causal path:

- PRN-conditioned target and reference selection;
- a privileged G22/G30 coordinate;
- post-outcome track orientation choice;
- the requirement that raw IQ be available merely to hide labels from the
  orbital scorer.

Still explicit:

- the receiver performed code correlation before producing RINEX;
- code labels and phase tracks share hardware and tracking loops;
- code-label agreement is an orthogonal same-output witness, not independent
  physical identity evidence;
- a real experiment requires a value-blind all-track inclusion rule;
- the full visible candidate codebook, event time, propagation, phase and
  hardware envelopes must be frozen orbit-first;
- one distinct qualification artifact and one later primary are required.

The maximum future claim is therefore:

> Orbital dynamics assigned all admitted tracks within the frozen candidate
> set, and the post-hash assignment was concordant with the receiver's code
> labels.

It is not unconstrained orbit recovery, code-free identity or independent
hardware confirmation.

## Minimum next physical step

No observation search is authorized by this spike. The next maximum action is
an orbit-only screen over one bounded, predeclared station/date set. It must
find a window in which all predicted candidate tracks are visible, the entire
assignment family retains positive margin after one conservative real-data
envelope, and the inclusion rule can admit all complete tracks without using
their PRN labels.

Valid terminals include:

- `NO_ALL_TRACK_GEOMETRY_DISCRIMINATIVE`;
- `NO_VALUE_BLIND_TRACK_INCLUSION_RULE`;
- `ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED`.

Only the last state could justify a later, separate structural qualification.

## SHOCK

Raw IQ was treated as necessary to remove PRN conditioning. It is necessary
to challenge the receiver's own code correlator, but not to remove the
experiment's target selection. Including every admitted RINEX track turns the
receiver label into an explicit, post-score, non-independent witness while
letting orbital dynamics choose the assignment first.

The strict machine-readable result is
[`GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_RECEIPT.json`](GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_RECEIPT.json).
