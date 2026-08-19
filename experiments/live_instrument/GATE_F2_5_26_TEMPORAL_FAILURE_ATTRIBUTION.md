# Gate F2.5.26 — temporal failure attribution

Gate F2.5.26 is exclusively offline. It reads the frozen Gate F2.5.25 receipt
and the pinned KiwiSDR server source already in the repository. It performs no
connection, acquisition, threshold change, decoder change or outcome change.

## Frozen inputs

```text
Gate F2.5.25 receipt SHA-256:
921deca68780b6546d19d4f8be2cb3cbb0ed5c9710d333f5dd24bf5d799b7380

KiwiSDR source commit:
c40ecb471dced33689e335689f8ffd35a54f47fa

server archive SHA-256:
d6a50adfce7f75133020de85635711dc6c2218e6f134d901ac13a450b57de7ea

rx/rx_sound.cpp SHA-256:
b749c91446a5c28e63b37997fa5d0912cf0bdb1a665a053810bf2cfc13547128
```

The outcome remains `QUALIFICATION_INCOMPLETE`. The 30-second maximum remains
the clause that governed that run.

## Failure attribution

The server source computes `last_gps_solution` from the elapsed seconds between
the sample timestamp state and the latest GPS position solution. It caps the
ordinary value at 252 seconds; 253–254 are reserved and 255 represents a
special clock state. The local decoder reads that same header byte. The
recorded 92–103 values are therefore elapsed seconds, not a local sentinel,
quality grade or NumPy conversion artifact.

The two branches show the same structure:

| property | reference | perturbed |
|---|---:|---:|
| server channel | 0 | 1 |
| incoming frames | 295 | 293 |
| SND/IQ frames | 275 | 274 |
| SND sequence | 1–275 | 1–274 |
| sequence gaps | 0 | 0 |
| initial SND without GPS seconds | 1 | 1 |
| later GPS solution age | 92–103 s | 92–103 s |
| readiness roots admitted | 0 | 0 |

Headers, sample decode and IQ mode were satisfied on every SND frame. The
transport delivered hundreds of ordered frames. `TimeoutError` is therefore a
downstream deadline consequence: the opener kept waiting because no frame
satisfied both GPS-seconds presence and the frozen freshness limit. It is not
evidence that the socket or decoder produced no data.

The proximal observed failure is:

```text
REMOTE_GPS_SOLUTION_FRESHNESS_CLAUSE_UNSATISFIED
```

Its physical cause is unknown. The receipt cannot distinguish a GPS antenna,
fix, configuration, clock-state or other server-side cause. Because the age
trajectory is parallel on both DDC branches of one receiver, the unmet
condition belongs to shared upstream server/GPS-clock state, not to two
independent per-channel failures.

## Contract failure versus hypothesis failure

Gate F2.5.25 failed its frozen capability admission. It did not evaluate the
DDC hypothesis. Samples were available; temporally admissible measurement
roots were not. Discovery, retune, plan freeze, A1/B/A2 and every physical
hypothesis remain `NOT_EVALUATED`.

This preserves the useful distinction:

```text
DATA_AVAILABLE = true
MEASUREMENT_ADMISSIBLE = false
DDC_HYPOTHESIS_EVALUATED = false
```

No upstream/downstream, external-RF, detectability or signal-absence claim is
authorized.

## Was absolute fresh GNSS derived from the DDC question?

Not explicitly. A same-Kiwi two-channel DDC intervention allows antenna,
front-end, ADC and sample clock to be shared. Its immediate temporal need is:

- relative simultaneity of reference and perturbed streams;
- continuous per-stream ordering and sample accounting;
- phase boundaries ordered against retune commands;
- bounded relative drift on the shared ADC clock.

Absolute GNSS freshness is indispensable when observations must align to an
external event, model or independent receiver. The Gate F2.5.25 plan inherited
that stronger rule, but its necessity was not derived from the same-clock DDC
claim. This does not make the rule invalid after the fact: it was frozen, so
its failure correctly stopped the run.

The alternative is only a candidate contract for a new prospective trial. It
cannot rescue or reinterpret the frozen session.

## Why the alternative cannot be tested on this receipt

The receipt retained artifact hashes, channel IDs, sequence numbers, clause
states and GPS-solution age. It deliberately destroyed IQ and raw frames. It
did not retain:

- per-frame monotonic arrival times;
- actual GPS seconds or nanoseconds;
- a server sample tick or equivalent shared-clock coordinate;
- decoded sample count per frame;
- retune-command issue times tied to frame boundaries.

Sequence continuity alone proves ordered delivery inside each branch; it does
not prove cross-branch simultaneity, common event-time alignment, sample-clock
drift or an intervention boundary. Consequently the relative-time alternative
is:

```text
NOT_FALSIFIABLE_WITH_THIS_RECEIPT
```

## Minimum conceptual change for a future trial

Do not raise the GPS-age threshold. Derive the temporal clause from the causal
topology before acquisition:

1. Require absolute UTC freshness only if the hypothesis crosses an external
   time root.
2. For a same-ADC DDC cut, predeclare admissible relative simultaneity,
   continuity, drift and command-boundary invariants.
3. Retain only scalar/hash sufficient statistics for those clauses before
   destroying RF: per-frame or anchor arrival time, actual server timestamp or
   sample tick, sample count, sequence, channel and command boundary.
4. Refuse before feature analysis if those invariants fail.

That is a new experiment and a new receipt contract, not a modification of
Gate F2.5.25.

## Authorized and unauthorized conclusions

Authorized:

- two server channels delivered contiguous decodable SND/IQ;
- neither produced an event-time root admitted by the frozen clause;
- the timeout followed repeated temporal-clause failures;
- the DDC hypothesis was not evaluated.

Unauthorized:

- assigning a physical cause to stale GPS state;
- asserting that the samples lacked useful physical structure;
- claiming that relative timing would have admitted the old session;
- changing 30 seconds retroactively;
- supporting or falsifying either DDC-location hypothesis.

## SHOCK

The temporal root must be derived from the intervention boundary, not inherited
from a previous observational topology. Shared ADC and clock are not merely a
loss of independence: for a channel-local intervention they may supply the
cleanest relative-time witness. But that advantage exists only if the receipt
precommits to and preserves the sufficient statistics needed to test it.

Gate F2.5.26 stops here. It adds no live authority and proposes no new
acquisition.
