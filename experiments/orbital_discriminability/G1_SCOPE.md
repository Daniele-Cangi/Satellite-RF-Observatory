# Gate G1 — pass-specific capability admission

## Question

Given one frozen orbit, pass window and carrier, does a set of descriptive
receiver offers contain at least one physically independent pair capable of
preserving the predicted differential orbital curvature with a positive
conservative detectability margin?

G1 does not ask which receiver is generally best. It does not infer a target
from receiver data. The propagated pass creates the requirement; offers are
tested against it.

## Frozen order

```text
orbit + event-time window + carrier
  -> observer-specific fractional trajectories
  -> jointly visible held-out differential curvature
  -> offer-local qualification
  -> hardware-root topology
  -> conservative time/frequency/orbit envelope
  -> deterministic pair admission or refusal
```

Individual qualification and pair admission are separate. A connected or
fresh capability may be individually qualified while every possible pair
remains below detectability.

## Individual clauses

Each offer must expose, before admission:

- WGS-84 observer coordinates;
- one named hardware measurement root;
- a fresh description whose TTL covers the complete pass window;
- full availability over the frozen pass window;
- carrier-band coverage and a finite positive frequency resolution;
- event-time semantics with a finite error bound;
- sequence continuity and a bounded maximum gap;
- the exact required transform steps;
- preservation of the RF frequency axis and ridge shape;
- the predeclared same-path health witnesses.

Missing descriptive information is an unsatisfied qualification clause, not a
physical rejection and not evidence that the signal is absent.

## Pair clauses

A pair is admitted only when:

1. both individual offers are qualified;
2. their hardware roots are distinct;
3. enough held-out samples are jointly above the frozen elevation mask;
4. differential curvature after calibration-prefix affine removal exceeds:

```text
minimum bins × coarser frequency resolution
  + station-specific event-time error envelope
  + carrier interval envelope
  + declared orbital prediction envelope
```

No calibrated probability is introduced. TLE age is never converted into a
numeric orbital uncertainty; that bound must be supplied by the frozen plan.

## Outcomes

- `NO_CAPABILITY_ADMITTED`: no pair satisfies every clause. A more precise
  terminal reason remains in the receipt.
- `CAPABILITY_SET_ADMITTED`: one deterministic pair has positive
  pass-specific falsification power and may be proposed to Gate G2.

Admission is not evidence of a received signal and does not authorize an
acquisition.

## Stop condition

G1 stops after the offline mechanism, deterministic synthetic vertical and
tests exist. No Internet status request, receiver connection, catalog query,
TLE download or RF acquisition occurs. A later status-only qualification must
be separately reviewed and must consume this exact admission logic without
changing its clauses.
