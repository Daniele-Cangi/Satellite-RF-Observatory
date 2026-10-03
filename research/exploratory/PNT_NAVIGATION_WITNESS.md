# Navigation-message witnesses: a distinct trust boundary

The [reference-transfer exercise](PNT_REFERENCE_TRANSFER.md) does not justify
another mean-residual regression on that topology. This work tests a different
mechanism: the local receiver's own decoded satellite clock/orbit messages can
be part of a coherent but wrong model. External message content can contradict
those inputs even when geometric residuals remain small. That is a candidate
source of additional evidence, not a demonstrated RF detector.

`python -m pnt navigation` compares RINEX 2 GPS NAV records for the same
satellite/toc/continuous week/toe/IODE/IODC. It shares the existing NAV block
normalizer; the propagation parser and its admission rules are unchanged.
The comparison preserves fields and unhealthy records that orbit fitting
omits. Missing issues, incompatible duplicate records and disagreeing
witnesses remain visible. No nearest-issue fallback or majority vote is used.

The [RINEX 2.11 specification, table A4][rinex] defines these clock/orbit
fields and issue identifiers. Transmission time can vary for repeated
messages, and fit duration is optional/derived, so neither participates in
this field-content comparison. The first adapter also omits ionosphere/UTC
header models and spare fields. Integer fields are exact; continuous decimal
values admit only half a unit of the last written digit on each side. This
addresses decimal serialization, not physical uncertainty or cryptographic
authentication. Required fields cannot be silently dropped or shifted.

## Exposed software exercise

The [complete compressed report](results/pnt_navigation_witness_v1.json.gz)
records four fixed variants of the previously used [NOAA daily composite GPS
NAV][noaa-nav] for 2012-09-14. All local NAV inputs are copies or synthetic
modifications of that external archive. They are **not victim-recorded RF**.
The interval selects local NAV `toc` from 12:00 inclusive to 14:00 exclusive
GPST: 31 records, with 444 other source records counted outside the window.

| Fixed case | Retained selected records | Outcome |
|---|---:|---|
| Original archive compared with itself | 31 | Compatible; identical local/external hash explicitly exposed |
| Add a common satellite-clock bias | 31 | Different `af0_s` from the external messages |
| Increment IODE/IODC to an unobserved issue | 31 | Insufficient evidence; no closest-message substitution |
| Original archive plus a contradictory synthetic witness | 31 | External conflict; no automatic preferred source |

The common bias is `2048 * 2**-31` seconds, about 0.954 microseconds. The
derived local file changes only each record's first clock coefficient,
serialized with Python `19.12E`. The second variant increments IODE modulo
256 and IODC modulo 1024. Original archive bytes are preserved externally;
the report binds each generated input by hash and records the transformation.
No threshold, alternative amplitude or time window was searched for a success.

For a physical illustration, the existing [TXAU C1 recording][txau] supplies
the 11 satellite codes at GPST week-second 477930, the first preattack epoch
in the preserved TEXBAT/NOAA clock report. The antenna coordinate comes from
the RINEX header, not an independent survey. Codes, positions and satellite
selection are identical in both fits. Broadcast records use the current
two-hour toc/toe admission rule. No satellite is excluded at this epoch.

| Fit quantity | Original NAV | Synthetic common clock bias in NAV |
|---|---:|---:|
| Receiver-clock estimate (m) | -0.131435 | 285.773442 |
| Largest absolute satellite residual (m) | 5.085518 | 5.085563 |

The receiver-clock estimate changes by **285.904877 m**, while no satellite
residual changes by more than **0.000983 m**. The nuisance receiver-clock
parameter absorbs most of the common change. External decoded fields expose
the message discordance; reducing geometric residuals would not reveal it.
This is a hybrid software counterfactual on real observations, not measured
RF attack detection, absolute-time error, false-alarm performance or an attack
whose every local check was proven plausible. A qualified independent local
clock or other local controls could also expose such a change.

## Actual raw-log intake and next step

The already exposed JammerTest archive contains
`Spoofing/stationary/Medium Power (_1W)/Bands_L1_L2_L5/2.1.1/240911_065707.ubx`.
Its 29,893,716 bytes have SHA-256
`05b41c23ea4ec35951bfc2d96b3638e104781c0c70e82ae23ab3adde626b749d`.
Using the existing UBX packet reader with explicit damage counting finds
**9,387 checksum-valid RXM-SFRBX packets** across GNSS systems and excludes
two bad-checksum packets. This is packet availability, not GPS payload/parity
validation, decoded ephemerides or a navigation contradiction result.

An initial strict inventory of the first stationary jamming member stopped on
a checksum mismatch; no result from that member is admitted. Attempts to get
individual NOAA TXAU/SAM2 NAV files and a BKG NAV URL returned HTTP 404; the
three URLs are retained in the report. No second independent message archive
was silently substituted. The current exercise has one external archive and
no independent local NAV capture. Distinct file hashes or source labels do not
establish independence.

**Next:** decode GPS navigation issues from the recorded SFRBX payloads,
qualify bit/parity/week/issue assembly against known examples, then compare
with the existing contemporaneous external NAV. Retain every malformed,
incomplete, mismatched and unchanged message. This is an ordinary exposed-log
adapter, not a new prospective experiment or an excuse for another gate chain.
Only then can we state which message differences the real episode contains.

## Limits and reproduction

Message agreement cannot authenticate RF origin, ranges or PVT: [relay attacks
can preserve navigation content][relay]. Archive agreement does not establish
freshness or an independent absolute clock. Differences can reflect conversion
errors, receiver faults, legitimate changes or manipulation; they do not
attribute an attacker. This diagnostic provides no general ALLOW/BLOCK token.

Run on decoded local messages and a retained external file:

```console
python -m pnt navigation 2012-09-14 LOCAL.12n.gz --witness NOAA=brdc2580.12n.gz --start 43200 --stop 50400 --output NEW_NAVIGATION.json
```

For the software variants, decode the original gzip to ASCII. In each eight-line
block replace clock characters 22:41 with `float(value) + 2048 * 2**-31`, formatted
`19.12E`; leave other characters unchanged. For the unobserved issue, increment
the first field of orbit row 1 and fourth field of orbit row 6 as above. Write
the resulting lines with LF and a final newline. Each case's `report` is the
corresponding CLI output. The aggregate JSON SHA-256 is
`d9af04fc625b7ab61c545af142ee2072212d81669d08e0bcf4852d0667437053`.
Use the recorded TXAU codes/coordinate and original admitted records to replay
the two clock fits. Original sources remain outside the repository.

Tests cover decimal representation, rebroadcast metadata, changed clock/orbit/
health/L2 fields, missing identities, duplicate conflicts, witness disagreement,
empty coverage, malformed input, the common-clock ambiguity and CLI no-overwrite.
Existing Linux/Windows CI includes these tests; historical report bytes and
source manifests retain their original meaning.

[rinex]: https://files.igs.org/pub/data/format/rinex211.txt
[noaa-nav]: https://noaa-cors-pds.s3.amazonaws.com/rinex/2012/258/brdc2580.12n.gz
[txau]: https://noaa-cors-pds.s3.amazonaws.com/rinex/2012/258/txau/txau2580.12d.gz
[relay]: https://arxiv.org/abs/2204.11641
