# Cassini DSS-14 real-NCO header evaluation

Date: 2026-08-21

Outcome: **`CASSINI_DSS14_REAL_NCO_SIGNATURE_RANKED`**

This bounded analysis closes the smallest physical step identified after the
DSS-26 refusal. The two former payload roles were retired before access; they
were evaluated only as `HEADER_CANDIDATE_A/B`. Neither product is now a
primary or reserve, and both RF payloads remain
`UNASSIGNED_AND_PROHIBITED`.

## Access result

The complete header grids were obtained with disjoint HTTP 206 byte ranges.
Only offsets 0–259 of each 4,260-byte SFDU were requested. No data-CHDO byte,
IQ sample, amplitude, RMS, peak, FGAIN or signal diagnostic was requested,
decoded or persisted.

| Candidate | Headers | UTC continuity | RSN continuity | Configuration |
|---|---:|---|---|---|
| 2006 DSS-14 | 10,800 | 0 non-1 s steps | 0 non-unit steps | RSR-5/A/1, 16 bit, 1 ksps, LO 8.1 GHz, DDC 328 MHz |
| 2005 DSS-14 | 4,380 | 0 non-1 s steps | 0 non-unit steps | RSR-3/A/1, 16 bit, 1 ksps, LO 8.1 GHz, DDC 326 MHz |

Frequency override was inactive throughout both products. The maximum
per-second NCO boundary mismatch was approximately `1.00e-8 Hz` for 2006 and
`5.39e-8 Hz` for 2005. The source-product suffix did not encode the RSR ID as
initially assumed; the parser binding was corrected from the authorized
amplitude-blind identity bytes before either signature was compiled. This was
a qualification-description repair and did not alter a scientific parameter.

Successful complete-grid responses contained `3,946,800` whitelisted header
bytes. Two bounded description retries added `26,520` header bytes and zero
data bytes. Raw headers were discarded after parsing; only ordered receipt
hashes remain.

## Frozen comparison

Both candidates used the unchanged plan:

- PREDICT SPK created before the candidate pass;
- DSS-14 station state and historical Earth orientation;
- representative header epoch `+0.5005 s`;
- first 20% calibration prefix;
- only constant USO offset and affine USO aging fitted on that prefix;
- exact header RF-to-IF LO, DDC LO and frequency polynomial;
- no free time phase and no suffix refit;
- controlling null: the two-parameter affine recorded-baseband continuation.

The screening `8.425 GHz` value remains a reference coordinate, not an
asserted Cassini USO carrier. Steering-only and Saturn-center differences were
not used for ranking.

| Rank | Candidate | Calibration / held out | Affine-null p-p | RMS | Versus DSS-26 |
|---:|---|---:|---:|---:|---:|
| 1 | 2006 DSS-14 | 2,160 / 8,640 s | `0.185766145 Hz` | `0.103455627 Hz` | `2.90656×` |
| 2 | 2005 DSS-14 | 876 / 3,504 s | `0.182377370 Hz` | `0.104474279 Hz` | `2.85354×` |
| — | closed DSS-26 reference | 1,931 / 7,720 s | `0.063912643 Hz` | `0.031284968 Hz` | `1×` |

Both real receiver transforms preserve substantially more nonlinear structure
than DSS-26. The 2006 candidate ranks first, but only by
`0.003388776 Hz` (`1.86%`) over the 2005 candidate. The ranking is therefore
valid but narrow; it is not evidence that one RF payload will be better.

## Authorized and unauthorized conclusions

Authorized:

- both exact DSS-14 header/NCO paths preserve more orbital-versus-affine
  structure than the closed DSS-26 path;
- the 2006 product is the first candidate for a pass-specific physical-envelope
  audit because it has the larger controlling separation;
- the 2005 product remains the second header candidate.

Not authorized:

- physical-margin admission;
- detector development;
- access to either IQ payload;
- carrier presence or absence;
- an orbital or satellite-identity claim;
- reuse of DSS-26 correction diagnostics as hard bounds for DSS-14.

All seven physical terms remain unbounded for each candidate: proper/gravity,
relativistic propagation, troposphere, ionosphere, interplanetary plasma,
station hardware, and applicable media calibration. The next smallest
scientific step, if authorized, is a candidate-specific outcome-independent
envelope audit for the rank-1 2006 pass. It must determine whether those terms
leave a usable fraction of `0.185766145 Hz`; it may not begin detector or IQ
work.

## Reproducibility

- plan SHA-256: `4dd7e60f25a7cb00f955346a7c49c42d11ef0990cb5c4eab9b687d9ac827d818`;
- parser manifest SHA-256: `7ffeeb059e091d8e98ebd6cc2ec4f4449b66ffe2ed9baae397c1840b5a1df912`;
- evaluation manifest SHA-256: `d956bbac0e080998e351b72044b37134b6c6e3fc23f36e61f97bc3d0d2d1c3ec`;
- runtime: SpiceyPy `7.0.0`, NumPy `2.3.3`;
- ordered 2006 whitelist receipt SHA-256:
  `54a49099ddd16c37ffcbc13234134ac99f72ea74d7e5f40372bb6f18d217d619`;
- ordered 2005 whitelist receipt SHA-256:
  `9fbf59a1534f1ab7bce6192428fb4b7323e404cdaed93b7b491db2956bf6dd6a`.

The exact label, kernel and source hashes are recorded in the JSON receipt.
