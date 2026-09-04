# DRAO seven-track/one-clutter prospective plan

## State

```text
DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN_FROZEN
ARTIFACT_UNSELECTED
ZERO_OBSERVATION_ACCESS
```

This is a bounded proof design, not a new gate. It uses only four already
committed receipts and stops before any DRAO observation locator, header,
payload or value is selected or accessed.

## Information-gain test

```text
Physical question:
  Can six predeclared orbital curves be assigned to seven opaque DRAO phase
  tracks with one symmetric clutter allowance, and predict a held-out suffix
  better than frozen affine and time-reversed alternatives?

New information produced:
  A real, previously unopened observer would either preserve or refuse the
  anonymous orbital assignment under one predeclared exclusion.

Why the existing result cannot answer it:
  The hardened one-clutter spike is model-only. ALGO cannot be rescored with a
  model created after its structural outcome without becoming post-hoc.

Minimum experiment:
  One DRAO structural-only qualification date, followed by one distinct
  zero-retry primary if and only if every pre-artifact clause passes.

Stop condition:
  Stop now before artifact selection. Any later primary ends after one
  terminal outcome with zero retry, new window or suffix refit.
```

## Why DRAO

No new geometry or receiver search was performed.

| Existing route | Decision | Reason |
|---|---|---|
| ALGO00CAN | excluded | consumed structural outcome; the one-clutter abstraction was learned from it |
| WES200USA | excluded | existing typed refusal: the known RINEX2 path does not establish explicit L1C/L2W semantics |
| DRAO00CAN | selected | unconsumed root, existing RINEX3-capable metadata and five already frozen positive orbit-only windows |

The selection does not claim receiver-family independence. DRAO metadata
declares a Septentrio POLARX5 5.2.0 and TWIVC6050/SCIS antenna. The exact
historical product still has to prove its own header, signals, timing and
continuity.

## Frozen roles before product selection

| Role | GPS date | Raw window | Held-out boundary | Artifact |
|---|---|---|---|---|
| structural qualification, never scored | DOY230 / 2026-08-18 | 01:27:00--02:36:00 | 02:06:30 | unselected |
| primary geometry | DOY231 / 2026-08-19 | 01:23:00--02:32:00 | 02:02:30 | unselected and unopened |
| reserve | none | — | — | none |

Both dates have the same orbit-derived candidate family:
G07/G08/G09/G21/G27/G30. Labels are unavailable to the scorer until after
the opaque score receipt is hashed.

DOY231 is the strongest non-ALGO DRAO cell already present in the frozen
screen. Its closest wrong assignment swaps G21/G27:

- exact held-out separation: `49,319.268201 m` peak-to-peak;
- three-guard requirement: `22,019.103704 m`;
- robust lower margin: `27,300.164497 m`;
- minimum direct-time-shifted elevation: `22.718488 deg`.

## Frozen seven-track surface

- exactly seven structurally complete opaque tracks must enter;
- every hypothesis evaluates six tracks and excludes exactly one;
- every exclusion is enumerated before reveal;
- 5,040 orbital assignments;
- 5,040 time-reversed-geometry alternatives;
- 7 affine-only alternatives;
- 10,087 total hypotheses;
- identical exclusion freedom for all families;
- no PRN filtering, post-hoc track removal or subset rescue.

The prefix contains 79 epochs and the untouched suffix 60 epochs. The only
continuous nuisance is a prefix-only constant and rate for each of five
independent centered tracks: ten parameters per hypothesis. There is no free
time phase or held-out refit.

## Measurement and witness contract

Core phase is L1C/L2W. A valid track requires the exact 30 s grid, zero LLI on
both fields, no interpolation and no gap bridging. C1C/C2W are same-path code
witnesses with at least 95 percent coverage per track and presence at raw
indices 1, 77, 78 and 137. They cannot correct phase.

All PRN labels remain sealed until after the anonymous score receipt hash. A
preferred orbital assignment whose later receiver-label witness disagrees is
`ORBITAL_INJECTION_DISCORDANT`, never a physical confirmation.

## Pre-artifact physical blocker

The historical `7,339.701235 m` guard is frozen as a ceiling, not assumed to
be a DRAO uncertainty model. Before even selecting a qualification artifact,
an outcome-independent DRAO audit must bound the aggregate effect of:

- event time through direct trajectory evaluation;
- broadcast orbit and clock;
- differential troposphere;
- ionosphere-free and higher-order remainder;
- antenna PCV and phase windup;
- multipath and signal-specific hardware;
- receiver clock and implementation;
- RINEX quantization.

No term becomes zero because it is inconvenient. If the aggregate defensible
effect exceeds the guard or remains unresolved, the path ends
`DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED` without looking for an observation
product.

## Future terminal semantics

Pre-primary terminals include:

```text
DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED
NO_QUALIFICATION_ARTIFACT_AVAILABLE
QUALIFICATION_DESCRIPTION_ERROR
QUALIFICATION_TOPOLOGY_REJECTED
QUALIFICATION_PASSED_PRIMARY_STILL_SEALED
```

Only a separately reviewed primary may later produce:

```text
MEASUREMENT_INVALID
NO_ADMISSIBLE_HYPOTHESIS
AMBIGUOUS
NONORBITAL_NULL_SUPPORTED
ORBITAL_INJECTION_DISCORDANT
ORBITAL_INJECTION_CONCORDANT
```

The maximum positive claim is limited to concordance between anonymous
held-out phase dynamics and a post-hash receiver-label witness inside this one
frozen DRAO six-orbit family. It is not unconstrained orbit recovery,
code-free identity, multi-observer evidence, receiver-family independence or
catalog-wide identity.

## Source binding

| Item | SHA-256 |
|---|---|
| geometry receipt | `09456cae2dcb97550f44a16e45d8cb4b0b5d28a19e0a5b3ef25893c45710089c` |
| root metadata receipt | `24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c` |
| ALGO terminal | `233e34084c0ffe86749919dd3f9b73ff243f9a51f530749328a7456dc7ad828e` |
| WES terminal | `59125fedbe1afbfa40255681f82d575a516589ca0f7d40186f601a23495e88f0` |
| plan source, canonical | `85bf70f8adaf256862f936429586653ea09442b87354cd1f5181ca482e677b71` |
| plan JSON | `a26dcc8e2f2ef00c345d93f2e64132a2536349fcfe0790ba198ae50046e9bb58` |

The plan JSON is 7,729 bytes. All access counters are zero.

## Stop

Do not select a DRAO product, query a locator, inspect a header, build an
executor or open a primary under this commit. The next maximum action is the
offline DRAO physical-envelope audit on the frozen DOY231 grid.
