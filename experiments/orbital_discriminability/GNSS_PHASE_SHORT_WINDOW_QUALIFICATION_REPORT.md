# G22/G30 DOY 217 short-window qualification outcome

The single authorized qualification returned:

```text
GNSS_SHORT_WINDOW_QUALIFICATION_PASSED
```

This is measurement-capability evidence only. No orbit prediction, null curve
or orbital score entered the qualification, and the DOY 220 primary remained
completely sealed.

## Artifact admission

Both predeclared daily artifacts were materialized once, completely hashed in
RAM before any decode, and destroyed after analysis.

| Station | Complete bytes | SHA-256 | Attempts |
| --- | ---: | --- | ---: |
| GOLD00USA | 2,170,051 | `ef2c80b96c5bbe7fbb83fb90abaa6203a9ff8d557a9aa3a39db5930188487573` | 1 |
| NLIB00USA | 2,500,618 | `582199ddeccd57fdde76f30aed9bb4e9489f4248563f3b7f217714fdd4dde473` | 1 |

The headers cover the full day in GPS time at 30-second cadence. GOLD reports
`JAVAD TRE_G3TH DELTA 4.2.03 / AOAD/M_T NONE`; NLIB reports
`SEPT POLARX5TR 5.7.0 / JAVRINGANT_DM SCIS`, exactly matching the frozen
configuration.

## Structural result

The fixed 05:54:00--07:03:00 GPS interval contains one complete joint segment:

```text
139 / 139 epochs
4 / 4 station-satellite phase links
3336 / 3336 relevant fields PRESENT
0 nonzero or invalid LLI
0 gaps, omitted fields or blank relevant fields
```

C1C and C2W have 100% coverage on every link, including raw indices
1, 77, 78 and 137. S1C/S2W were present but remained descriptive and no
signal-strength scalar was parsed.

## Model-blind phase health

The frozen geometry-free second-difference limit is
`0.09514683639918244 m`. All 137 second differences on every link were
evaluated without an orbital model:

| Station | Satellite | Maximum absolute second difference | Violations |
| --- | --- | ---: | ---: |
| GOLD00USA | G22 | 0.019273575 m | 0 |
| GOLD00USA | G30 | 0.010488357 m | 0 |
| NLIB00USA | G22 | 0.012220029 m | 0 |
| NLIB00USA | G30 | 0.010022134 m | 0 |

The worst observed aggregate is about 20.3% of the frozen limit. This is a
continuity result, not evidence that G22 is the correct orbit.

## Access and persistence boundary

- qualification phase scalars parsed in RAM: 1,112;
- phase scalars persisted: zero;
- code or SNR scalars parsed: zero;
- compressed or decoded RINEX persisted: zero bytes;
- orbital prediction accesses and scores: zero;
- DOY 220 products discovered, headers opened, payload bytes and values: zero.

Only structural JSON Lines and aggregate health receipts remain. Qualification
success authorizes a primary seal review, not primary access by itself.

## Frozen receipts

| Receipt | Bytes | SHA-256 |
| --- | ---: | --- |
| `GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_COVERAGE.jsonl` | 1,159,538 | `a1bcf2b0117caaa08694631bcacc6f3a4ea044f7319f7e1b90b79784ce8e3a5e` |
| `GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_SUMMARY.json` | 8,451 | `64a453b2117ad4a156024f9297d5e6457da530d5b2fe6001d232988776bf748b` |
| `GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_OUTCOME.json` | 2,866 | `c592ae34c665322d1bc209d6d868d1ab5aedae10934d3a79a524231dab765322` |

The execution is bound to source commit
`d22695e513734c41ebb909b45c3846b37069940a`, source SHA-256
`f7ccffa52b1a2497ac6f4a073b00d7966f2ee4e4bec38ff2164629b138a727e8`
and proof-plan manifest SHA-256
`0068385ef4aaf1014f0211efaa47da52da8c5fb18cf51377f4812434fd2b5f3c`.

## Remaining boundary

The next work may freeze the exact primary decoder/scorer against the already
fixed DOY 220 window and hypotheses. It must be committed before primary
access. The primary remains zero-retry, and no qualification-derived
threshold, window, nuisance or null may be changed.
