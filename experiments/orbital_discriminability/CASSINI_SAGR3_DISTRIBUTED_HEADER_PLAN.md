# Cassini SAGR3 distributed header-only qualification

Date frozen: 2026-08-21

This bounded spike asks whether the three products admitted by the distributed
geometry screen preserve the control metadata needed for a future held-out
DSS-25 minus DSS-65 frequency comparison. It is not a new gate and produces no
RF, carrier, or orbital claim.

## Frozen products

| Role | Product | Frozen receiver identity |
|---|---|---|
| distributed X left | `s23sags2006_251_1200x14x25rd` | DSS-25 / RSR learned from SFDU / channel A / subchannel 1 |
| same-path Ka witness | `s23sags2006_251_1200x14k25rd` | DSS-25 / RSR learned from SFDU / channel B / subchannel 1 |
| distributed X right | `s23sags2006_251_1200x14x65rd` | DSS-65 / RSR learned from SFDU / channel A / subchannel 1 |

Station and channel A/B come from the exact-hash PDS labels and are checked or
carried with their actual lineage. RSR and subchannel come from the real SFDU
header bytes. The numeric prefix of the source-product suffix is explicitly not
treated as the RSR ID; previous real-header work already disproved that mapping.

## Frozen access boundary

- request only bytes `record_start .. record_start+259` for every record;
- never request or read bytes `260..4259` of any record;
- parse in RAM and overwrite each raw 260-byte buffer immediately;
- persist only strict-JSON aggregate receipts and their ordered hashes;
- never represent samples, IQ, ADC RMS/peak, FGAIN, signal strength, or any
  signal-derived diagnostic;
- stop before detector development or IQ access.

The authorized maximum is 92,400 headers and 24,024,000 SFDU control bytes.
Data CHDO authorization is zero bytes.

## Clauses

1. Every product has its exact label record count and start/stop event times.
2. RSN increments modulo 65,536 and first-sample UTC advances exactly one
   second throughout each complete product.
3. Station, RSR, channel, subchannel, sample resolution/rate, LO, DDC LO,
   override state, frequency/phase polynomial states, filter and decimation are
   explicit and internally stable where identity requires stability.
4. Frequency-polynomial coefficients are finite. Both the raw adjacent-record
   NCO boundary and the physically relevant combined
   `-RF/IF LO - DDC LO + NCO` boundary are reported; DDC recentering is never
   mistaken for a sky-frequency discontinuity.
5. DSS-25 X and Ka are simultaneous distinct channels of the declared receiver
   path; they do not count as two geographic roots.
6. DSS-25 X and DSS-65 X are simultaneous independent receive hardware roots.

## Frozen outcomes

- `CASSINI_SAGR3_HEADER_TOPOLOGY_QUALIFIED`: every clause above is satisfied.
- `NO_ADMISSIBLE_DISTRIBUTED_HEADER_TOPOLOGY`: real control metadata violates
  at least one causal or continuity clause.
- transport, parser, or description failures remain qualification errors and
  do not become physical refusals.

Even the positive outcome leaves `physical_margin_admitted`, detector access,
and IQ access false. Its sole next physical step is a bounded correction
envelope evaluated on the exact real-NCO grids.

Parser manifest SHA-256 before access:
`2ef3b9fed0d104911b5a9059b263bca2a5e9117dd06650e2a6f4359e861d6b9e`.

Parser source SHA-256 before access:
`2583b1813f3f222f2bcf997d8e8f66737b95d741140e26cd93443bc925b75db9`.
