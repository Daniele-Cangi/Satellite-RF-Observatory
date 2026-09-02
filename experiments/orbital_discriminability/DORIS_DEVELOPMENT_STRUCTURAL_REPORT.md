# DORIS development structural scan

## Bounded question

**Physical question:** Does the exact development-only Sentinel-3A DORIS
product contain long enough, structurally continuous dual-frequency station
coverage for either frozen geometry pair, with the predeclared same-path code
witness?

**New information:** Real epoch topology, target-station coverage, phase
continuity, code-witness flags and joint segment lengths.

**Why the header could not answer it:** The real header omitted `INTERVAL` and
`TIME OF LAST OBS`; it could not establish cadence, end coverage or flags.

**Minimum experiment:** One full value-blind scan of the already authorised
development artifact. The scanner represented epoch time, station ID,
presence and the two flag characters of L1/L2/C1/C2 only. It never converted
or retained a 14-character observation magnitude.

**Stop condition:** A structural receipt, with no feature, orbital prediction,
null score, detector, candidate-day access or primary selection.

## Terminal outcome

`DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT`

The result is a contract-level structural refusal, not an orbital negative.
One pair has enough core L1/L2 coverage, but neither pair has a continuous
C1/C2 witness admitted by the frozen conservative time-reference-validity
rule.

| Pair | Required | Longest joint core L1/L2 | Longest admitted C1/C2-witnessed coverage | Result |
|---|---:|---:|---:|---|
| TLSB–WEUC | 430 s | 393 s | 0 s | core short by 37 s; witness absent |
| PAUB–RIMC | 480 s | 633 s | 0 s | core passes by 153 s; witness absent |

The smallest positive structural fact is therefore:

```text
PAUB + RIMC
→ independent station records
→ L1/L2 present
→ LLI-continuous station segments
→ maximum station sample gap <= 10 s
→ 633 s joint core coverage
```

This is `CORE_PHASE_STRUCTURE_QUALIFIED` only. It does not admit a measurement
or authorize access to observation values.

## Exact authority and zero-value boundary

- compressed product: `s3arx26242.001.Z`;
- role: `DEVELOPMENT_STRUCTURAL_ONLY_NEVER_PRIMARY`;
- compressed bytes: 1,869,420;
- compressed SHA-256:
  `240d84518beb409dceb5cf1816f02621e9def8c9bf750c9c340cad4f6fbd7add`;
- exact header SHA-256:
  `47311d675dc0130a42676e423827bd63a4ac3b9083664c52741f5f75d185012a`;
- decompressed stream: 7,564,590 bytes, 94,830 lines;
- decompressed SHA-256:
  `9edb37c8a354602c20985a07edb87c594bcd9678d496e6e70ee0b4ee4f20db64`;
- epochs: 16,704;
- station records: 39,024 plus 39,024 continuation lines;
- numerical phase values decoded/persisted: 0 / 0;
- numerical code values decoded/persisted: 0 / 0;
- power, oscillator and meteorological values decoded/persisted: 0 / 0;
- candidate DOY245 access: zero;
- orbital prediction and score: not evaluated.

The terminal scanner is commit
`e2336295eaefd91008636935db7510b974427335` with source SHA-256
`84a0d8171fd780bde03903e6018fb777b99430ad3bca5177aee8911ea7dc16ef`.
Nine synthetic cases passed before the terminal scan. A tenth frozen-receipt
regression was added after the receipt was materialized; this distinction keeps
the pre-outcome test statement exact.

## Description corrections before the terminal scan

The real structure exposed three description errors. None was promoted to a
physical result.

1. DORIS epoch seconds use `F13.9`; a fixed generic-RINEX 36-column prefix
   truncated the station count. The corrected parser consumes exactly nine
   structural tokens and never tokenizes the receiver-clock suffix.
2. Epochs from different stations are interleaved. Absence of a target station
   at another station's epoch cannot break that target's phase chain. Segments
   are built independently by station and their time coverage is intersected
   without interpolation.
3. The real nominal cadence is mainly an alternating 3 s / 7 s pattern, not
   exact 10 s samples. The frozen rule is now positive delta no greater than
   10 s plus continuous LLI; larger gaps break the segment.

The official RINEX DORIS specification also distinguishes the two phase flags:
flag 1 marks a central-frequency measurement and is descriptive; flag 2 is the
LLI/discontinuity flag and breaks continuity. For C1/C2, flag 1 declares
validity for time-reference use and flag 2 is the processing-unit number.

Sources:

- [CNES RINEX DORIS 3.0 specification](https://ids-doris.org/documents/BC/data/RINEX_DORIS.pdf)
- [IDS DORIS RINEX overview](https://ids-doris.org/user-corner/about-doris-rinex-format.html)

## Station-level attribution

| Station | Records | Longest core phase | Nonconforming gaps | Code flag 1 |
|---|---:|---:|---:|---|
| TLSB / D49 | 611 | 703 s | 13 | valid-for-time-reference on all records |
| WEUC / D47 | 328 | 413 s | 7 | not valid-for-time-reference on all records |
| PAUB / D46 | 435 | 683 s | 5 | valid-for-time-reference on all records |
| RIMC / D40 | 484 | 673 s | 5 | not valid-for-time-reference on all records |

The zero witnessed duration is therefore attributed, not guessed: each pair's
second station lacks an admitted time-reference-valid C1/C2 run. This does not
prove that its pseudorange contains no physical information. It proves only
that the current conservative witness clause cannot use it without a new
physical justification.

## What remains open

- numerical DOR-to-TAI/phase-center event-time error bound;
- exact DPOD station coordinates, heights and phase centers;
- the one-way relativistic, ionospheric and tropospheric phase model;
- shared receiver-clock and channel-dependent differential bias;
- whether time-reference validity is actually the correct admission rule for
  a same-path code witness in the intended orbital observable.

The last item is the main SHOCK. The development file shows that dual-frequency
phase can satisfy the duration requirement while the inherited code-witness
clause blocks it. The next work should therefore be an offline
change-of-observable review: determine whether L1/L2 itself supplies the
required dispersive/same-path control, or whether C1/C2 time-reference validity
is causally indispensable. It must not simply delete the clause because the
candidate failed.

No observation value, candidate-day product, primary, detector or orbital
score is authorised by this result.

