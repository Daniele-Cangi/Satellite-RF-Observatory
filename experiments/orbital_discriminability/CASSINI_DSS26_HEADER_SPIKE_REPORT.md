# Cassini DSS-26 development header spike

Date: 2026-08-20

Outcome: **`CASSINI_OPEN_TERM_CAN_ABSORB_HELDOUT_SEPARATION`**

This is a bounded repair and development-only header result inside the existing
forward orbital vertical. It is not a new gate. The physical hypothesis and
development/primary/reserve roles did not change. No DSS-14 URL was requested,
and both the primary and reserve remain sealed and unopened.

## Pre-access hardening

Commit `e491bdd` changed the one-way solver to converge on relative geometric
light time, added a floating-point regression, moved the real type-1 PREDICT
SPK regression into a non-optional exact-kernel CI job with SpiceyPy `7.0.0`,
and made SFDU UTC day-boundary/leap-second refusal explicit. The complete
offline suite passed `728` tests; the real exact-hash kernel job passed its
three-epoch regression locally.

The PDS4 label then exposed a pre-header metadata mismatch: its source product
is `...NNNX26RD.1A1`, not the synthetic parser's earlier `2A1`. Commit
`c574936` corrected only that label-derived product identity before the first
SFDU header byte was read. It changed no offsets, transform, hypothesis, role,
or numerical parameter.

## Artifact admission

The complete development product was materialized in quarantine and verified
before parsing:

- LIDVID:
  `urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:s11sags2005_157_1750nnnx26rd::1.0`;
- source product: `CO-S-RSS-1-SAGR1-V1.0:S11SAGS2005157_1750NNNX26RD.1A1`;
- bytes: `41,113,260`;
- published MD5: `ce672e2258ffe8466389db36f9f6668f` (matched);
- complete-file SHA-256:
  `dee30d34255f17c20f6aea7072bfd4b156db0d0e3378720e377f7bcec16ed424`;
- label SHA-256:
  `b02dd0ff1aaa355fbe6faca191b898c91b2d99532864750ac6a50e30d93b70c1`.

Only after those checks did the scanner read the `260` whitelisted bytes per
record. It sought across each `4,000`-byte data CHDO without reading, decoding,
hashing separately, retaining, or representing it. No IQ, amplitude, RMS,
peak, strength, FGAIN, or signal-derived diagnostic entered the runtime or
receipt.

## Complete header continuity

All `9,651` headers parsed successfully. The ordered strict-JSON whitelist
stream has SHA-256
`365b18ec2129524c143ee6ac0c10e38c73b64d96345d45547d49462676091275`,
which commits every exposed control field and polynomial without retaining raw
headers.

- RSN is exactly `0..9650`: `9,651` unique values, zero non-unit steps.
- First-sample UTC is exactly one-second continuous from
  `2005-06-06T17:50:01.000000Z` through
  `2005-06-06T20:30:51.000000Z`; zero non-one-second steps.
- Every record is DSS-26 / RSR 1 / channel A / subchannel 1.
- Sample mode is complex I then Q, MSB 16-bit; every header declares `16` bits
  and `1,000` complex samples/s.
- RF-to-IF LO is always `8,100,000,000 Hz`; DDC LO is always
  `327,000,000 Hz`.
- Frequency override is always false. Predicts time shift, frequency override,
  and frequency rate are `0`; predicts frequency offset is `40 Hz`; subchannel
  offset is `0`.
- NCO polynomial coefficients are finite. The maximum adjacent boundary
  residual is `2.578599378466606e-8 Hz`.
- Phase polynomial coefficients and accumulated phase are finite. The maximum
  adjacent absolute-phase boundary residual is
  `2.384185791015625e-7 cycles`.
- The header implies `16 MHz -> 1 kHz` decimation by `16,000`. FIR
  coefficients are not encoded, so no amplitude-response claim is authorized.

The parser manifest SHA-256 is
`46a4c7ed236911f1ca949b564119d4d2ee3cdec2e04ba454ab620b0c235c3314`.

## Exact recorded-baseband compilation

The frozen spike source is commit `a05cd3d`, source SHA-256
`830e0775da0d6d4ace101339eb934dcb6f3b851e875f6fdb14f32ea85ba1a18b`,
and manifest SHA-256
`77ce25266ca003749e004f639a58588d80706b17a8d43834c63f1108dc9a9903`.
It used the exact four previously frozen, hash-verified kernels and the pre-pass
type-1 PREDICT Cassini SPK.

The causal ledger on every header midpoint (`+0.5005 s`) was:

```text
first-sample UTC
-> LSK UTC/ET conversion
-> historical EOP + DSS-26 station state
-> relative one-way light-time solve
-> pre-pass PREDICT Cassini state
-> exact flat-spacetime kinematic transfer
-> calibration-prefix USO constant offset + affine aging
-> RF/IF LO + DDC LO + exact per-header NCO polynomial
-> recorded-baseband coordinate
```

Only the first `1,931` records (`20%`, rounded upward) fitted the two allowed
USO nuisance terms. The remaining `7,720` records were untouched. There was no
free time phase and no suffix refit.

All alternatives used the same time/header/NCO grid:

1. steering-only: unit kinematic factor;
2. affine baseband: sky frequency is
   `RF_IF_LO + DDC_LO - NCO + (a + b*t)`, so the exact receiver transform
   yields the frozen prefix affine extrapolation;
3. geometry-destroying: Cassini state replaced by the Saturn barycenter from
   the same frozen pre-pass SPK.

Held-out orbital-minus-null separations were:

| Frozen null | Peak-to-peak | RMS | Maximum absolute |
|---|---:|---:|---:|
| steering-only | `1,861.737616 Hz` | `908.224758 Hz` | `1,878.920629 Hz` |
| affine recorded baseband | `0.063912643 Hz` | `0.031284968 Hz` | `0.062385256 Hz` |
| Saturn-barycenter geometry | `265.674356 Hz` | `125.632095 Hz` | `267.792152 Hz` |

The steering-only separation is not independent orbital evidence: the header
NCO was itself generated from DSN frequency predicts. The controlling
non-orbital comparison is therefore the affine recorded-baseband null. The
exact NCO transform reduces the previously screened nonlinear signature to
only `0.063912643 Hz` peak-to-peak.

## Typed refusal

The nonlinear separation is mathematically positive before open terms, but
the following physical terms still have no numerical bound:

- proper-time and gravitational frequency transfer;
- relativistic propagation light time;
- Earth troposphere;
- Earth ionosphere;
- interplanetary plasma;
- station hardware delay/frequency effect;
- applicable archived media calibration.

No arbitrary zero or bound was assigned. Any one unbounded term can absorb a
finite `0.0639 Hz` held-out residual. Consequently this receipt cannot admit a
detector or IQ access, and the exact outcome is:

```text
CASSINI_OPEN_TERM_CAN_ABSORB_HELDOUT_SEPARATION
```

This refusal does not say that the orbital model is false, and it does not say
that no carrier exists. It says only that this metadata-only recorded-baseband
signature is not yet falsifiable against the frozen affine null under the
current correction ledger.

## Public sources

- [DSS-26 PDS4 development label](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/2005/s11sags2005_157_1750nnnx26rd.xml)
- [Cassini SAGR1 archive description](https://pds.nasa.gov/ds-view/pds/viewProfile.jsp?dsid=CO-S-RSS-1-SAGR1-V1.0)
- [Cassini Radio Science User's Guide](https://pds.nasa.gov/data/pds4/misc/document_cassini/Cassini_Radio_Science_Users_Guide_30Sep2018.pdf)
