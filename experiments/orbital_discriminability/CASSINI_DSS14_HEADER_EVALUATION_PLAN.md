# Cassini DSS-14 bounded header evaluation plan

Date frozen: 2026-08-21

This is a bounded continuation of the Cassini physical route, not a new gate.
It can reveal whether either remaining recorded receiver transform preserves
more nonlinear one-way orbital structure than the closed DSS-26 path. It
cannot observe a carrier or authorize an orbital claim.

## Role reassignment

The authoritative DSS-26 outcome remains
`CASSINI_OPEN_TERM_BOUND_UNAVAILABLE`; DSS-26 is closed and is not read again.

The former payload roles are retired before any DSS-14 header access:

| Header role | Product | RF payload role |
|---|---|---|
| `HEADER_CANDIDATE_A` | `s23sags2006_251_1200nnnx14rd` | `UNASSIGNED_AND_PROHIBITED` |
| `HEADER_CANDIDATE_B` | `s10sags2005_122_1955nnnx14rd` | `UNASSIGNED_AND_PROHIBITED` |

No DSS-14 product is a primary or reserve under this plan. A later payload
role would require a new prospective decision after this evaluation.

## Frozen access boundary

Allowed:

- the two PDS product labels and published checksum metadata;
- the applicable pre-pass PREDICT SPK and the already selected time,
  historical Earth-orientation and station kernels;
- exactly bytes `record_index * 4260` through
  `record_index * 4260 + 259`, inclusive, for every declared SFDU record;
- a server response only when it proves the requested byte range and returns
  exactly 260 bytes.

Prohibited:

- any byte in a data CHDO (offsets 260 through 4259 of every record);
- complete RSR materialization, IQ decoding, amplitude, RMS, peak, signal
  strength, FGAIN, samples or any signal-derived diagnostic;
- detector work, feature inspection, free time phase, held-out refit or a new
  gate/framework.

A server that ignores a Range request causes a typed header-path refusal; its
response body must not be read. Header bytes are parsed into the frozen
whitelist receipt and then discarded. Raw header bytes are not persisted.

## Frozen scientific comparison

- representative point in each one-second SFDU: `0.5005 s`;
- calibration prefix: first `20%` of records, rounded upward;
- permitted emitted-frequency nuisance: one constant USO offset and one
  affine USO aging term fitted on the prefix only;
- confirmation suffix: all remaining records, with no refit;
- screening rest frequency: `8,425,000,000 Hz`, reference-only;
- exact per-header RF-to-IF, DDC LO and frequency polynomial are applied;
- spacecraft state: the product's pre-pass PREDICT SPK;
- station state: DSS-14 with the frozen station/Earth-orientation kernels;
- controlling null: two-parameter affine recorded-baseband continuation
  fitted on the same prefix;
- metric: held-out orbital-minus-affine peak-to-peak and RMS in hertz.

Steering-only and Saturn-center comparisons are not controlling and cannot be
used to promote a candidate. Candidate-specific physical correction bounds
are not inferred from DSS-26. Header evaluation can rank preserved structure,
but cannot by itself yield `CASSINI_BASEBAND_PHYSICAL_MARGIN_ADMITTED`.

## Stop outcomes

- `CASSINI_DSS14_HEADER_PATH_INCOMPLETE`: a label, exact header grid or frozen
  PREDICT trajectory cannot be established without RF-payload access;
- `CASSINI_DSS14_NO_SIGNATURE_IMPROVEMENT`: neither exact receiver transform
  preserves more affine-null separation than DSS-26's frozen
  `0.06391264328448062 Hz`;
- `CASSINI_DSS14_REAL_NCO_SIGNATURE_RANKED`: at least one product preserves a
  larger exact-header affine-null separation; this only selects the next
  candidate for a separate physical-envelope audit.

Every outcome stops before detector or IQ access.
