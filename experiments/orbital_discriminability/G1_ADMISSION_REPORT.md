# Gate G1 — offline capability-admission report

## Outcome

```text
G1_OFFLINE_MECHANISM: COMPLETE
Internet capability queried: ZERO
receiver connection: ZERO
RF acquisition: ZERO
calibrated probability: ZERO
```

Gate G1 now materializes the boundary between an orbital prediction and a
receiver set. It does not discover receivers and does not claim that any
currently available Internet capability is admitted.

## What is evaluated

One immutable `OrbitalPassPlan` binds:

- element-set content and lineage token;
- pass identifier and complete UTC window;
- carrier and cadence;
- minimum elevation and calibration/holdout split;
- minimum jointly visible holdout support;
- frequency-bin, clock, carrier and orbital uncertainty rules;
- required transform steps and measurement-path witnesses.

Each caller-supplied offer is first evaluated independently. Only offers with
coordinates, one hardware root, TTL valid through pass end, full pass availability, carrier
coverage, bounded time/frequency behavior, sequence continuity, complete
transform affordances and the frozen witnesses may enter a pair.

Pairs then face four separate clauses: independent hardware roots, sufficient
joint calibration visibility, sufficient joint held-out visibility and
positive differential detectability margin. The
selected pair is the admitted pair with the largest margin; input order cannot
change the result.

Event-time uncertainty uses the same direct `t - delta_t` / `t + delta_t`
trajectory envelope as G0. Joint visibility gates both the affine prefix fit
and every held-out score.

## Deterministic reference vertical

The vertical deliberately reuses the historical G0 ISS fixture. Its offers are
synthetic capability descriptions, not observations of real endpoints.

```text
pass:             G1-ISS-2019-FIXTURE
window:           2019-12-09T16:38:29Z to 16:43:29Z
carrier:          145.8 MHz
cadence:          5 s
minimum elevation: 10 degrees
resolution:       5 Hz per offer
clock bound:      1 s per offer
orbit envelope:   1 Hz per station
plan hash:        d239f12380ef09915c309ddd3a8e669fa673b4ba8a2bf6bad9dabf894bf9bd6f
```

All three synthetic offers qualify individually. Pair results are:

| Pair | Joint calibration / held-out samples | Signature | Threshold | Margin | Admission |
|---|---:|---:|---:|---:|---|
| Berlin–Copenhagen | 13 / 37 | 1439.919 Hz | 63.200 Hz | 1376.720 Hz | admitted |
| Berlin–Eindhoven | 13 / 45 | 2885.269 Hz | 77.469 Hz | 2807.799 Hz | selected |
| Copenhagen–Eindhoven | 13 / 37 | 974.390 Hz | 76.696 Hz | 897.694 Hz | admitted |

The synthetic outcome is `CAPABILITY_SET_ADMITTED`, with
Berlin–Eindhoven selected. This says only that the declared capability
envelopes could preserve this fixture’s differential geometry.

## Required negative control

A Copenhagen/local-10-km pair is also described as fully available and
individually qualified, but with 20 Hz resolution and a 5-second clock bound:

```text
differential signature:       24.999 Hz
frequency-bin envelope:       60.000 Hz
event-time envelope:         206.200 Hz
orbital envelope:              2.000 Hz
total threshold:             268.200 Hz
detectability margin:       -243.201 Hz
outcome:              NO_CAPABILITY_ADMITTED
reason:               NO_PAIR_CLEARS_DETECTABILITY
```

Availability therefore cannot rescue insufficient falsification power.

## Descriptive boundary

Every offer receives a deterministic SHA-256 before assessment, including
rejected offers. Strict JSON normalization represents non-finite and NumPy
scalars descriptively; they cannot enter a numerical admission calculation.
No array or RF payload exists in a G1 result.

## Causal limits

The frozen `sample_sequence` and `in_band_frequency_reference` witnesses close
receiver continuity, frequency-axis and transform cuts. They do not prove:

- that a spacecraft emitted at the declared carrier;
- that the emission came from the candidate orbit;
- that propagation did not selectively suppress it;
- that a detected ridge has orbital origin.

Consequently `CAPABILITY_SET_ADMITTED` is not yet a falsifiable observation
plan. Gate G2 must bind an emission hypothesis and target-path positive
controls before an absence can damage the physical hypothesis.

## Authorized claims

G1 authorizes only that:

- capability admission can be derived from a pass-specific orbital feature;
- individual availability and pair-level falsification power are distinct;
- independent hardware roots are required by this distributed geometry claim,
  not by a universal framework rule;
- one conservative negative control remains unadmitted despite complete
  descriptive availability;
- the procedure is deterministic, order-independent and strict-JSON safe.

It does not authorize a claim about a live endpoint, current satellite pass,
received RF feature, transmitter identity or orbital origin.

## Next boundary

G1.1–G1.3 are preserved as a concluded side investigation into capability
discovery; they are not prerequisites for the forward experiment. The next
physical decision is to select one satellite/pass and one explicitly scoped,
predeclared capability set, then apply these clauses without requiring a
global Internet inventory. No observation is authorized by this report.
