# DORIS development header qualification

## Frozen question and authority

**Physical question:** Does one real Sentinel-3A DORIS product declare the
dual-beacon time, phase and receiver transforms needed to turn the positive
orbit-only geometry into a prospective measurement path?

**New information produced:** The development header can establish product and
spacecraft identity, receiver type, declared observables, station membership,
station frequency-shift factors and DORIS time semantics before any observation
record is exposed.

**Why the geometry spike cannot answer it:** The geometry calculation assumed a
nominal carrier, simultaneous phase availability and an event-time coordinate.
Those assumptions were not yet bound to the actual RINEX product.

**Minimum experiment:** Materialize and hash only `s3arx26242.001.Z`; run a
specification-derived, frozen whitelist parser through the first
`END OF HEADER` newline; terminate the decompressor there.

**Stop condition:** Stop on header qualification or typed refusal. Read no
epoch, flag or observation record; perform no detector fit and no orbital score.

## Outcome

`DORIS_DEVELOPMENT_HEADER_REJECTED`

This is not a negative RF or orbital outcome. The parser reached the exact
header boundary and found a physically useful DORIS product, but the frozen
header-only admission requires three records that are absent:

- `INTERVAL`;
- `TIME OF LAST OBS`;
- `MARKER TYPE`.

The absence of `INTERVAL` and `TIME OF LAST OBS` means that this authorized
surface cannot demonstrate actual cadence or full-day/window coverage. The
absent `MARKER TYPE` also violates the predeclared whitelist admission, even
though the separate `SATELLITE NAME`, COSPAR number and DORIS system fields are
consistent with a spaceborne Sentinel-3A receiver. The rule was not weakened
after seeing the header.

Measurement admission and orbital scoring remain `NOT_EVALUATED`.

## Artifact and parser boundary

The official IGN product listing declared 1,869,420 bytes and a remote
modification time of 2026-08-31 22:20:14 UTC. No published adjacent checksum
was available. The complete local artifact was therefore bound by a newly
computed SHA-256 before decompression:

- product: `s3arx26242.001.Z`;
- role: `DEVELOPMENT_HEADER_ONLY_NEVER_PRIMARY`;
- bytes: `1,869,420`;
- SHA-256: `240d84518beb409dceb5cf1816f02621e9def8c9bf750c9c340cad4f6fbd7add`.

The parser was frozen first in commit `0da158e` and validated on synthetic
Unix-compress fixtures derived from the RINEX DORIS 3.0 field definitions. Its
source hash is
`c1c081aebd57fb3e843d816e0e221c525e70c562529363fa8a787b8c127ef0d0`.

The real boundary receipt is:

- 78 complete header lines;
- 6,318 decompressed header bytes exposed;
- header SHA-256
  `47311d675dc0130a42676e423827bd63a4ac3b9083664c52741f5f75d185012a`;
- first `END OF HEADER` newline used as the boundary;
- zero post-header bytes read from the pipe;
- decompressor terminated at that boundary;
- zero epoch, phase, pseudorange, power, oscillator, meteorology or flag
  records read or represented.

The compressed artifact was destroyed after the receipt was verified. No
decompressed file was ever created.

## What the real header establishes

| Property | Header result | Epistemic role |
|---|---|---|
| Product identity | Sentinel-3A / COSPAR 2016-011A | `OBSERVED_METADATA` |
| Receiver | CHAIN1 / DGXX-S / 1.00 | `OBSERVED_METADATA` |
| Antenna | DORIS / STAREC | `OBSERVED_METADATA` |
| RINEX | 3.00, file type `O`, system `D` | `OBSERVED_METADATA` |
| Phase | L1 and L2 declared | `CORE_DECLARED_NOT_SAMPLED` |
| Same-path code | C1 and C2 declared, scale factor 100 | `WITNESS_DECLARED_NOT_SAMPLED` |
| Power | W1 and W2 declared | `OPTIONAL_DIAGNOSTIC_NOT_SAMPLED` |
| Receiver oscillator | F declared | `CLOCK_COORDINATE_NOT_SAMPLED` |
| Meteorology | P/T/H declared | `MEDIA_INPUTS_NOT_SAMPLED` |
| L2/L1 event offset | -0.1 microsecond | `OBSERVED_METADATA` |
| First observation tag | 2026-08-30 00:00:18.853332 DOR | `OBSERVED_METADATA` |
| Cadence | `INTERVAL` absent | `UNRESOLVED` |
| End coverage | `TIME OF LAST OBS` absent | `UNRESOLVED` |
| Structural continuity | body unopened | `NOT_EVALUATED` |
| Numerical event-time error | not supplied by header | `UNRESOLVED` |

The DOR time tag is receiver proper time monitored with respect to TAI. That is
a semantic relationship, not yet a numerical bound between a phase-center
event and true TAI/UTC. The four declared time-reference stations and their
bias/shift metadata do not by themselves supply that end-to-end error bound.

## Shortlist intersection

The development header declares 56 ground stations. Two of the three orbit-only
shortlist pairs are present as station references:

| Pair | Development-header state | Frequency-shift factors `K` |
|---|---|---|
| KRWB–LAPB | unavailable: KRWB absent, LAPB present | unknown / 0 |
| TLSB–WEUC | declared | 0 / +18 |
| PAUB–RIMC | declared | 0 / 0 |

This proves only membership and the header transform parameter. It does not
prove that both beacons were observed simultaneously in either geometric
window or that their phases were continuous.

## Causal ledger after the header

```text
pre-observation Sentinel-3A orbit                     OBSERVED / FROZEN
  -> beacon station identity and K                    OBSERVED IN HEADER
  -> dual S/U-band phase and code schema              DECLARED IN HEADER
  -> DOR receiver-time semantics                      DOCUMENTED + DECLARED
  -> actual epoch cadence and final coverage          UNRESOLVED
  -> simultaneous pair presence and phase flags       NOT_EVALUATED
  -> DOR-to-TAI numerical event-time bound             UNRESOLVED
  -> one-way relativistic/media correction            UNRESOLVED
  -> ionosphere-free differential phase coordinate    NOT_COMPILED
  -> prefix calibration and held-out null comparison  NOT_EVALUATED
```

## Change-of-abstraction review

**BLOCK:** Header-only access cannot establish the required observation
interval, end coverage, simultaneous pair epochs or phase discontinuity flags.

**INFORMATION VALUE:** The route is not a generic RINEX hope: a real
Sentinel-3A DGXX-S product declares dual-frequency phase/code, the actual `K`
values and two usable shortlist station pairs.

**CURRENT ABSTRACTION:** Requiring those facts specifically from optional
header records is not physically necessary. Requiring the facts themselves is
necessary.

**ALTERNATIVES:**

A. Stop DORIS now and lose a geometry route with a very large preliminary
margin.

B. Search for richer DORIS headers, which risks another metadata inventory and
does not guarantee different optional records.

C. Perform one bounded **value-blind structural epoch scan** of this same
development artifact, exposing only epoch time, station identifier and
phase/code flag presence while discarding all numerical observations.

D. Admit the missing fields as zero/default, which would make a future negative
uninterpretable and is refused.

**BEST PHYSICAL PATH:** C. It directly tests whether the real product contains
the simultaneous, continuous coordinate required by the already shortlisted
orbit geometry. It is not a new gate or a generic parser.

**ACTION:** Stop here. A structural epoch scan requires separate explicit
authority because the current authorization ended at `END OF HEADER`.

The candidate-day observation product was not accessed. No primary role is
frozen by this result.
