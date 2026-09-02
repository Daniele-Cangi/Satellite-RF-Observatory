# DORIS compound-observable causal audit

## Outcome

```text
DORIS_DUAL_PHASE_DIFFERENTIAL_REQUIRES_COEPOCH_REQUALIFICATION
```

This is an offline change-of-observable result. It does not admit a
measurement, score an orbit or authorize access to either the destroyed
development artifact or candidate DOY245. The prior terminal result remains
immutable:

```text
DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT
```

The frozen structural receipt SHA-256 is
`cf564053c1a866849475c46a33037a27a738e77f514958a89e69f4b802e188d8`.

## Physical question

Can synchronous dual-frequency phase close the dispersive and shared-receiver
cuts for an inter-beacon orbital observable without requiring each target
beacon's C1/C2 fields to be valid for time-reference use?

The answer is conditional. L1/L2 phase is not a generally complete DORIS
measurement family. It can be sufficient for the narrower inter-beacon
differential only when both beacon observations have the same receiver epoch,
the absolute DOR-to-coordinate-time bridge is independently bounded, and the
remaining propagation and hardware terms are bounded before scoring.

## Outcome-independent basis

The [RINEX DORIS 3.0 specification](https://ids-doris.org/documents/BC/data/RINEX_DORIS.pdf)
defines synchronous L1/L2 observations, phase flag 2 as the loss-of-lock /
discontinuity indicator, and C1/C2 flag 1 specifically as validity for
time-reference use. C1/C2 flag 1 is therefore not a generic field-presence or
signal-validity bit.

The [DORIS models and solutions reference](https://ids-doris.org/documents/BC/data/DORIS_models%26solutions_v1.0.pdf)
models phase as propagation/geometry plus receiver and transmitter clock and
proper-time terms and pass biases. It uses ionosphere-free phase and code
combinations in a complete single-station solution. That complete-solution
requirement must not be confused with the narrower exact-coepoch
inter-beacon quotient considered here.

## Frozen algebra

For range-equivalent phase, with nominal DORIS frequencies
`f1 = 2,036,250,000 Hz` and `f2 = 401,250,000 Hz`, freeze

```text
Q_IF = alpha * (lambda1 * L1) + beta * (lambda2 * L2)

alpha =  294849 / 283400 =  1.040398729710656316
beta  =  -11449 / 283400 = -0.040398729710656316
```

The implementation verifies with exact rational arithmetic that
`alpha + beta = 1` and `alpha/f1^2 + beta/f2^2 = 0`. Thus the nondispersive
coordinate is retained and the first-order ionosphere cancels.

For two beacons observed at one identical receiver epoch, left-minus-right
phase differencing also gives exact zero symbolic coefficients for the shared
receiver clock and shared receiver proper-time terms. If the epochs differ,
the corresponding coefficients are `+1` and `-1`; temporal overlap alone does
not cancel them.

## Causal topology comparison

| Topology | Receiver clock / proper time | C1/C2 role | Maximum current claim |
| --- | --- | --- | --- |
| Single station | Remains in the observable | An ionosphere-free code time solution or another bounded clock model is required | Not admitted by the current receipt |
| Two overlapping, non-coepoch beacon streams | Difference between two receiver epochs remains | A bounded time bridge remains required | Not admitted |
| Exact-coepoch inter-beacon L1/L2 difference | Shared receiver terms cancel symbolically | Per-target time-reference-valid code is not required for that cancellation; an absolute event-time bridge is still required | Conditionally plausible, not structurally qualified |

Common epoch-tag error is only a first-order common-mode reduction. It is not
listed among exact cancellations and does not remove the need to bound event
time against the orbital trajectory.

## Consequence for the frozen development pairs

- TLSB–WEUC retains 393 s of joint core overlap against 430 s required and has
  frequency-shift factors `K = (0, 18)`. It remains insufficient.
- PAUB–RIMC retains 633 s of joint core overlap against 480 s required and has
  `K = (0, 0)`. It is the preferred conditional pair because it avoids the
  shifted-frequency correction.

The existing receipt deliberately describes both pair products as
intersections of independent station grids with no interpolation. It does not
prove a contiguous exact-coepoch L1/L2 chain. Therefore the positive 633 s
overlap cannot be reinterpreted as measurement admission.

## Revised clause semantics

The old rule "time-reference-valid C1/C2 on every target epoch" is not a
universal measurement requirement. It attached a global witness to a causal
cut that an exact-coepoch difference can remove algebraically.

The replacement is claim-scoped:

1. exact common receiver epoch for the two phase observations;
2. continuous L1/L2 with zero phase-discontinuity flags;
3. a bounded absolute DOR-to-coordinate-time bridge for orbital evaluation;
4. predeclared bounds or models for every surviving term.

C1/C2 remains necessary for a complete receiver-time/clock solution and may
remain a useful same-path diagnostic. It is not silently discarded.

## Terms that survive the quotient

The following remain explicit and cannot become zero by convention:

- absolute event-time error against the orbit;
- higher-order ionosphere;
- differential troposphere;
- beacon coordinates, antenna phase centers and antenna maps;
- phase wind-up;
- Shapiro and one-way relativistic terms;
- non-affine differential ground-oscillator behavior;
- channel switching or receiver-noncommon bias.

Calibration-prefix constant and affine differential oscillator terms and
constant inter-frequency/pass biases are only nuisance candidates. Their
admission and projection remain prospective work.

## Stop and next minimum action

Current measurement admission, orbital prediction and null scoring are all
`NOT_EVALUATED`. No DORIS observation magnitude was accessed.

The next minimum physical step, only under separate authority, is one
value-blind structural requalification of the same development artifact. It
would retain exact epoch tags, station identities, L1/L2 presence and flags
only, and determine whether PAUB–RIMC contains a contiguous exact-coepoch chain
covering the frozen 480 s requirement. It must not access candidate DOY245 or
decode phase/code magnitudes.

If that topology is absent, the dual-phase-only route stops. If it is present,
the remaining physical terms and absolute event-time bridge still have to be
bounded before any measurement or orbital score.

