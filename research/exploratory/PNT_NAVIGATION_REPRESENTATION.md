# LNAV representation qualification

Executed 3 October 2026 on the already exposed CTTC inputs from
[the public RF exercise](PNT_PUBLIC_RF_NAVIGATION.md). This is software
development and representation qualification, not a new RF recording,
prospective confirmation or measured detector performance.

## Result

The existing navigation CLI can now distinguish a uniquely recoverable
broadcast value from an ambiguous or unsupported archive representation:

```console
python -m pnt navigation 2013-04-04 pnt/tests/fixtures/cttc20130404/GSDR276o10.26N --witness NOAA=pnt/tests/fixtures/cttc20130404/brdc0940.13n.gz --qualify-lnav --output NEW.json
```

It retains the original written-decimal comparison and adds
`lnav_representation` under schema `pnt-navigation-witness-v3`. Without the
flag, previous v1/v2 reports remain unchanged. The same option works with the
existing UBX GPS L1 C/A adapter; it introduces no receiver dependency or
experiment-specific executor.

For each field, count the encodable values inside the existing written
interval, using [IS-GPS-200N tables 20-I/III][gps] for binary scales and widths.
Signed fields retain their two's-complement range; angles retain the
decoder's semicircle conversion. Integer metadata is exact. URA uses
[RINEX 3.05 table A6][rinex]'s nominal-metre mapping, rather than interpreting
a receiver-exported index as metres. Invalid L2-code metadata and unavailable
URA/TGD stay unqualified. The continuous week retains its declared era.

One candidate permits a conditional encoded-value comparison. Zero candidates
means the stated interval cannot represent a broadcast value. Multiple
candidates remain ambiguous. Closed boundaries retain ties. No nearest-value
repair, inferred effective digits, physical tolerance or automatic exporter
correction is admitted. Profile `GPS_LNAV_WRITTEN_INTERVALS_V2` uses exact
rational candidate bounds and the interval between the decoder's truncated pi
and its next decimal unit. The conversion uncertainty scales with each encoded
value; zero remains exactly zero. It never enlarges the written interval by a
fixed tolerance or models archive error. This qualifies the representation under these
assumptions, not a provider's truth, source independence, freshness or RF origin.

Conflicting duplicates and contradictory witnesses retain the existing exact
issue boundary and interval intersection. No majority or nearest-issue fallback.
Every field remains visible, including uniquely different fields when another
field is unqualified. `SAME_BROADCAST_FIELDS` requires all 27 fields to resolve
uniquely; it still does not authenticate pseudoranges or receiver PVT.

UBX qualification also retains complete cycles with unavailable URA/TGD.
Their field-level diagnostics remain unqualified; the original comparison
still rejects them as `UNUSABLE_ISSUE`, with its original reason and counts.
`representation_record_index` orders these diagnostics, `sfrbx_cycle_index`
binds the raw cycle, and `local_record_index` links the original comparison
record or is null for a rejected issue. Structural/IODE/reference-time failures
remain rejected, including when unavailable metadata is also present.

## Exposed RF result and retained limitations

The five native exports remain **5/5 DIFFERENT_FROM_EXTERNAL** under the
previous comparator. Their added qualification is **5/5
REPRESENTATION_UNQUALIFIED**; the incorrect URA export and other conversion
limitations are not reclassified as attacks or repaired to obtain agreement.

Independent replay of all 65 ordered monitored messages retains ten complete
cycles and five incomplete cycles. All 270 decoded local field occurrences
resolve uniquely. The same-issue NOAA representations give:

| External field result | Occurrences across ten complete cycles |
|---|---:|
| Unique encodable value | 118 |
| No encodable value in the written interval | 136 |
| Ambiguous representation | 10 |
| Invalid L2-code metadata | 6 |

These are repeated field occurrences, not independent observations or benign
receiver-hours. Each cycle remains unqualified. The ten ambiguities are the
coarsely serialized zero `af2`: its interval contains all 256 possible
coefficients, so even a one-bit change cannot be excluded from that archive.
G32's square-root semimajor axis remains outside NOAA's written interval;
the earlier nearest-integer investigation does not authorize broadening it.
URA and the L2 P flag agree when compared from decoded bits rather than the
faulty native export. NOAA's invalid L2-code value remains explicit for three
satellites. No source is silently preferred.

## Reproduction and decision

The [corrected machine result](results/pnt_navigation_representation_v2.json.gz)
contains exact input hashes, the entire native report and every raw-bit
qualification. Its uncompressed JSON is 1,248,047 bytes with SHA-256
`bdc5ea137f09b9e6e6022fb206587f99e5e18eaee0cd4e2339de4db6c3002fbf`.
The native command above reproduces `native_report`. The existing RF test's
ordered-message replay supplies decoded rows to `qualify_navigation_records`
for `raw_bits_representation`; regression tests compare both with the saved
artifact. Existing Git history and replay protect this development result.

The [initial v1 result](results/pnt_navigation_representation_v1.json.gz) remains
byte-identical (uncompressed SHA-256
`52d420564c8cef1dcfe7d5c043fbede053b77ea993208e61869f6c20be25d243`), with its
implementation retained in commit `d8ee5401d99b13e857159207b495f1f8c009f506`.
Review identified an unsound fixed angular enlargement near zero and missing
UBX unavailable-metadata diagnostics. V2 records the correction separately;
the exposed CTTC field counts and all legacy comparison outcomes are unchanged.
V1's angular candidate logic is superseded and must not be used for new claims.

Tests include one-bit changes in all 20 continuous clock/orbit/delay fields,
exact integer metadata, signed ranges, ties, coarse zeros, missing issues,
conflicting sources, unavailable metadata, CLI retention and previous reports.
Tiny positive/negative RINEX angles, exact zero, nonzero pi boundaries and UBX
sentinels alone/together are explicit regressions; retaining sentinels cannot
bypass other issue checks.
These are receiver-decoded software mutations, not valid RF transmissions.

The next physical prerequisite is an Internet witness that preserves the
broadcast values, or documented conversion bounds that independently justify
its representation. This source does not pass that qualification. After that,
apply the existing paired comparison to adequate benign/altered recordings.
P2 detection benefit, false-alarm performance and absolute-time verification
remain open. Do not tune archive precision on this exposed case to make it pass.

[gps]: https://archive.gps.gov/technical/icwg/IS-GPS-200N.pdf
[rinex]: https://files.igs.org/pub/data/format/rinex305.pdf
