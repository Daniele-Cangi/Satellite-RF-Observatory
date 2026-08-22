# Cassini 2005 dual-root X/Ka header qualification

## Physical question

Does the frozen DSS-25/DSS-55 X/Ka measurement path preserve the time and
receiver-frequency coordinates needed to test the pre-pass Cassini geometry?

The answer is yes at the control-path level:

`CASSINI_DUAL_ROOT_HEADER_PATH_QUALIFIED`

This is not yet physical-envelope admission and authorizes no IQ access.

## Frozen authority

The five-candidate pass selection was frozen in commit
`8c18f82f8c26d09f1545eb98838617aa55b1e6e2`. The product-specific parser,
window offsets and admission invariant were frozen before header access in
commit `89c59334fa70a7dde9b8f2db49651f01d620d896`.

- selection manifest:
  `9f0f409e2067820578ad8c586213ee8fee1288465c99065f2453c1742053ce69`;
- parser manifest:
  `c7d1922cfaf69906399c6a0e3f8a6bb5a9078296fbba002bc152764e39481f52`;
- canonical parser source:
  `151b275bed8a5583163c31207c7e0b0220cdd524e07c48683d47866e588b225d`.

No threshold, candidate, endpoint, product, window, channel assignment or
transition rule changed after access began.

## Access boundary

Only exact HTTP byte ranges covering bytes 0–259 of each authorized SFDU
record were requested. A response had to prove status 206, exact
`Content-Range`, total product size and 260-byte payload before the body
could be assimilated. A server response with status 200 would have been
closed without reading its body.

The four products were each read once, sequentially, without retry:

- 5,280 headers per product;
- 21,120 headers total;
- 5,491,200 authorized SFDU control bytes;
- 0 Data CHDO bytes requested or read;
- 0 sample, amplitude, RMS, peak or signal-diagnostic values represented;
- raw header buffers zeroed immediately after receipt generation;
- no raw headers or RF persisted.

## Observed control topology

All four streams cover exactly
`2005-06-08T19:17:00.000000Z` through
`2005-06-08T20:44:59.000000Z`, with one header per second and no UTC or
RSN gap.

| Stream | Center | RSR/channel | RF→IF LO | DDC LO | Mode | Discrete changes |
|---|---:|---|---:|---:|---|---:|
| DSS25-X | 10 | 1/A/1 | 8.1 GHz | 327 MHz | 1 ksps, 16 bit | 0 |
| DSS25-Ka | 10 | 2/B/1 | 31.7 GHz | 321 MHz | 1 ksps, 16 bit | 0 |
| DSS55-X | 60 | 1/A/1 | 8.1 GHz | 326 MHz | 1 ksps, 16 bit | 0 |
| DSS55-Ka | 60 | 2/B/1 | 31.7 GHz | 321 MHz | 1 ksps, 16 bit | 0 |

The X and Ka witnesses at each station are therefore real distinct receiver
branches, while DSS-25 and DSS-55 are independent receive roots. X/Ka channels
do not count as extra geographic roots.

All Predicts override/time-shift/rate/offset fields are finite zero and the
override state is false throughout. RF→IF LO, DDC LO and override state have
zero transitions in the frozen window.

Maximum adjacent receiver-transform boundary residual:

- DSS25-X: `9.5367431640625e-7 Hz`;
- DSS25-Ka: `3.814697265625e-6 Hz`;
- DSS55-X: `9.5367431640625e-7 Hz`;
- DSS55-Ka: `3.814697265625e-6 Hz`.

These values are descriptive numerical continuity, not detector resolution.
The configured 1 ksps rate and 1 kHz output bandwidth must not be called
spectral resolution.

## Transform ledger

For every record the metadata supply the reversible coordinate

`recorded_baseband = sky - RF_TO_IF_LO - DDC_LO + NCO(t)`.

The full ordered whitelist receipt stream is committed by a SHA-256 for each
product. The persisted receipt contains the coefficient envelopes, timing
endpoints, RSN endpoints, mode, identity and transform boundary metrics. It
does not retain raw headers.

Filter topology is modeled as 16 Msps input decimated by 16,000 to 1 ksps.
The FIR coefficients are not encoded in the SFDU and remain unresolved.
Consequently no amplitude-response, group-delay ripple or detectability claim
is authorized.

## Causal-state update

The non-probabilistic state envelope has narrowed:

### Observed control state

- four complete and simultaneous one-second header grids;
- two independent DSN processing/station roots;
- X and Ka on distinct channels at both roots;
- finite LO/DDC/NCO transform for every record;
- no discrete control transition in calibration or holdout.

### Modeled but not yet uncertainty-bounded

- 16 MHz to 1 kHz decimation topology;
- common-transmit-time orbital mapping;
- outcome-independent EOP, station and solar-system geometry.

### Still unresolved

- FIR coefficients and their phase/group-delay response;
- a product-specific numerical ADC-to-UTC error bound;
- differential troposphere;
- receiver proper-time/gravity uncertainty;
- higher-order plasma and scintillation;
- X/Ka differential hardware delay and frequency reference errors;
- Cassini USO aging and retarded-time coupling;
- PREDICT-SPK orbit error without a frozen covariance.

An especially important remaining condition is simultaneity semantics:
equal receive UTC at X and Ka does not by itself mean equal spacecraft
transmit epoch. Dispersive propagation gives the bands different group delay,
and DSS-25/DSS-55 also receive a common spacecraft epoch at different station
times. The composite must therefore be built on one frozen retarded-time
coordinate, not by subtracting rows merely because their UTC strings match.

Similarly, sharing the station frequency reference can reduce differential
noise while creating correlated errors. Those errors cannot be combined by
root-sum-square unless their independence is documented.

## Authorized and unauthorized claims

Authorized:

- the frozen four-stream control path is continuous;
- DSS-25 and DSS-55 provide two independent receive roots;
- both roots have simultaneous, distinct X/Ka control paths;
- first-order plasma is observable in principle at both roots;
- the central 0.2991723488 Hz geometry screen may proceed to an exact
  baseband/physical-envelope calculation.

Not authorized:

- plasma-corrected RF measurement;
- detector resolution or carrier detectability;
- closure of the non-dispersive physical envelope;
- preference for the Cassini orbit over a null;
- detector development or IQ access.

## Next physical step

The minimum next step is not another inventory or parser. It is one
metadata-only streaming compiler on the same four frozen products:

1. map all four NCO/LO polynomials onto a common Cassini transmit-time grid;
2. construct a predeclared first-order X/Ka plasma coordinate at each root;
3. form the DSS-25 minus DSS-55 non-dispersive composite;
4. apply the same calibration-prefix affine projection to the orbital model
   and every frozen null;
5. propagate correlated envelopes for proper-time/gravity, troposphere,
   higher-order plasma, hardware, timing, FIR/group delay and PREDICT-SPK
   error;
6. compare the combined envelope with the controlling
   `0.2991723488431748 Hz` held-out separation.

The compiler must terminate without IQ if an unresolved term can absorb the
separation. Per-record transforms were deliberately not persisted, so any
future read requires a separate explicit authorization; it must compile in
RAM during that single read rather than create a metadata database.
