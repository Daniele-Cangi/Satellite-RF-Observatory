# DORIS observable-topology review

Outcome: **`DORIS_TIME_REFERENCE_PAIR_SELECTED_GEOMETRY_UNEVALUATED`**

This is an offline change-of-abstraction review, not a new gate. It opened no
orbit product, DORIS RINEX artifact, observation value, candidate day, or
network connection. It did not compute an orbital score. The terminal parent
result remains **`DORIS_PHYSICAL_ENVELOPE_BOUND_UNAVAILABLE`**.

## Physical question and stop

**Physical question:** which compound DORIS observable can retain distributed
beacon geometry while eliminating, or independently witnessing, the clock and
receiver-channel terms that blocked PAUB–RIMC?

**New information:** exact symbolic link coefficients show which terms cancel
at a common receive epoch, which cancel at a common transmit epoch, and why
those two operations do not generally commute.

**Why the existing experiment cannot answer it:** PAUB–RIMC supplies one
spaceborne receiver and two standard beacons. Its exact-coepoch quotient
cancels receiver time but leaves two independent transmitter USOs and
receiver-noncommon branches.

**Stop:** select only the minimum topology for a later orbit-only geometry
test. Do not search geometry, open a product, or weaken an uncertainty term.

## Exact event-key rule

For one ionosphere-free link from beacon `b` to satellite `s`, evaluated at
receive event `r` and retarded transmit event `e`, keep the clock part as

```text
+ receiver_clock[s, r] + receiver_proper_time[s, r]
- transmitter_clock[b, e] - transmitter_proper_time[b, e].
```

Hardware identity is insufficient for cancellation: owner **and physical
event** must match. The exact rational L1/L2 combination still cancels the
first-order ionosphere independently on every link.

## Candidate topology comparison

| Rank | Topology | Exact cuts | What survives | Maximum authorized claim |
|---:|---|---|---|---|
| 1 | one satellite + two time-reference beacons at a common receive epoch | first-order ionosphere; shared receiver clock and proper time | two externally referenced transmitter states; two channel branches; atmosphere, antennas and relativity | orbital-versus-frozen-null only after geometry and finite calibration/channel/path envelopes pass |
| 2 | two satellites + same two beacons, common receive epoch at each satellite | first-order ionosphere; each satellite receiver clock and proper time | each beacon clock evaluated at two different retarded emission epochs; four channel branches | cross-satellite consistency or a bounded short-lag USO test, not an USO-free orbital result |
| 3 | same four links aligned to a common transmit epoch per beacon | first-order ionosphere; both beacon clocks and proper times | each satellite receiver at two link-dependent receive epochs; four channel branches | a clock trade, not a clock-free observable |
| 4 | limited C1/C2 time witness on the current single-satellite pair | no new exact cut | standard-beacon USO remains on the same causal link | same-path diagnostic unless a separate multi-beacon time solution is built |

### Why two satellites are not an exact cure

For links `Q(s,b)`, the receive-coepoch double difference is

```text
Q(S1,B1) - Q(S1,B2) - Q(S2,B1) + Q(S2,B2).
```

It cancels each satellite receiver clock. For beacon `B1`, however, the
surviving transmitter term is the difference between `clock_B1(E11)` and
`clock_B1(E21)`. `E11` and `E21` differ because light times to the two
satellites differ. Aligning by common emission epoch makes that beacon term
cancel, but then the two beacon links reach each satellite at different
receive epochs and its receiver clock no longer cancels.

Thus a second satellite changes an unknown USO curve into a finite-lag USO
difference; it does not make it zero. It also doubles the receiver-channel
cuts. This route may become valuable when that short-lag difference has an
independent bound, but no such bound exists in the frozen evidence.

## Why the time-reference pair ranks first

The frozen development header already declares four time-reference stations:

```text
ADHC  HBMB  PAUB  TLSB
```

This creates a bounded set of six possible pairs. No pair has been chosen and
no orbit has been evaluated for them. A same-receive-epoch pair preserves the
useful receiver-clock/proper-time cancellation while replacing the two
uncharacterized standard-beacon USOs with an external time-reference path.
That is not an algebraic cancellation: the header bias and frequency-shift
fields are descriptive until their numerical uncertainty and held-out
applicability are proven.

The topology also does **not** solve receiver-noncommon behavior. A later
physical contract would need fixed processing-unit identity, no unmodelled
switch, and a finite stability envelope for the two simultaneous branches.
An `UNRESOLVED` channel term remains nonzero by construction.

## Why C1/C2 is not the minimum bridge

The exact-coepoch phase quotient already removes the receiver clock that a
limited code-time bridge would target. Code on the same standard-beacon link
does not independently identify that beacon's USO. Promoting C1/C2 into a
complete multi-beacon clock solution would approach the full DORIS time/POD
problem and introduce more assumptions than the first forward orbital test
needs. C1/C2 may remain a same-path witness; it is not the selected causal
repair.

## Remaining admission clauses

Before any observation access, a later time-reference-pair experiment would
still need:

1. positive orbit-only held-out separation for one of the six frozen pairs;
2. finite, outcome-independent time-reference calibration uncertainty over
   the calibration prefix and held-out suffix;
3. exact coepoch L1/L2 phase continuity and a bounded DOR-to-coordinate-time
   bridge;
4. fixed processing-unit identity plus a finite receiver-noncommon bound;
5. finite higher-order ionosphere, troposphere, antenna, wind-up and one-way
   relativistic envelopes on the exact future grid.

No current receipt proves these clauses.

## Decision and next maximum action

The selected abstraction is:

```text
one satellite
+ two header-declared time-reference beacons
+ exact common receive epochs
+ dual-frequency ionosphere-free phase
```

The next maximum action, only after review, is an **orbit-only**
discriminability screen of the six frozen header-declared pairs. It must use
the same affine and geometry-destroying null discipline and access no DORIS
observation product. If no pair has sufficient joint geometry, the topology
closes without searching for a convenient RINEX file.

## SHOCK

Receive-epoch and transmit-epoch clock cancellations do not commute. Adding a
second satellite appears to add independence, but without an independent
short-lag USO bound it preserves the transmitter-clock ambiguity and creates
more channel paths. The smaller single-satellite experiment becomes stronger
only by changing the **quality of the beacon roots** from free-running to
externally referenced, not by multiplying receivers.
