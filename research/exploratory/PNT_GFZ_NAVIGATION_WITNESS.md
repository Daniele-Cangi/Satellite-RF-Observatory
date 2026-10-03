# GFZ transmitted-navigation witness: exposed CTTC intake

On 2026-10-03, the public GFZ NavBit archive supplied a usable binary message
witness for the already-exposed CTTC recording of 2013-04-04. All **10 complete
local cycles, 27 compared fields each**, have `SAME_BROADCAST_FIELDS` under the
unchanged `GPS_LNAV_WRITTEN_INTERVALS_V2` comparator. The five incomplete local
cycles remain incomplete. This resolves the decimal-serialization obstacle
for this case; it is not prospective confirmation or RF authentication.

## Source and provenance

The [GFZ dataset catalog][catalog] identifies the GPS navigation-message
archive, DOI `10.1594/GFZ.ISDC.GNSS/GNSS-GPS-1-NAVBIT`, and CC BY 4.0. Attribution:
Rothacher, Markus; Beyerle, Georg (2008), *GPS C/A Navigation Message Data Bits*, GFZ Data
Services. The [daily download][archive] was accessible anonymously over HTTPS.
The tar contains 32 daily satellite files, 3,246,080 bytes, SHA-256
`431341f496f3128a6faabf03a6d9430b297ba8b17341f3a0f339e0759c5bed58`.

Five unchanged compressed NetCDF members for G01/G11/G17/G20/G32 are retained
in [the fixture directory](../../pnt/tests/fixtures/gfz20130404/provenance.json),
502,782 bytes total. These are all satellites in the existing local replay,
selected without inspecting field agreement. Provenance records download URL,
archive hash, member hashes, decompressed hashes and attribution. The full
archive remains downloadable; replay needs only the retained members and the
existing CTTC inputs. No registration or new runtime dependency is required.

GFZ's [format and processing description][paper] documents transmitted words,
parity filtering, aggregation and multiplicity. The retained files contain
10 unsigned 30-bit words per subframe in 32-bit NetCDF integers, plus time and
multiplicity. Their history records creation on 2013-04-05 by
`navbit2archive_ntrip`. This is **one aggregated provider**, not multiple
independently interrogated station witnesses: per-station identities and the
provider's rejected or disagreeing frames are absent. The published processing
description removes failed parity and resolves disagreements before archival.
Those unavailable upstream failures cannot be recovered from this product.

## Conversion, selection and retained outcomes

The initial naive conversion stripped six parity bits from each word and
failed the existing IODE/IODC consistency check. These are transmitted words;
their data need the preceding word's D30 de-inversion specified in
[IS-GPS-200N 20.3.5.2/table 20-XIV][gps]. The reusable `decode_lnav_words` helper
now performs that transform and checks all six parity bits in each word.
Word 2/10 zero tails are required. It makes no parity repair or polarity search.
Receiver output already de-inverted by u-blox or GNSS-SDR keeps its existing
decoder. This format correction is not a tolerance or a physical finding.

The intake takes SF1/2/3 at **every** local HOW frame start: 368610, 368640 and
368670 seconds of week for all five satellites, including incomplete local
cycles. These correspond to provider start tags 23010–23082 seconds of day;
the HOW/time relation is checked for every selected subframe. GFZ time tags
describe transmitter-message time, not an independent receiver capture clock.
Agreement of these declarations establishes no freshness or absolute time.
Only these 45 selected subframes receive independent parity checking; the
remaining daily words are retained, not claimed as fully decoded/qualified.

| Retained comparison | Outcome |
|---|---|
| Local ordered monitor replay | 15 cycles: 10 complete, 5 incomplete |
| GFZ selected transmitted words | 45 parity-valid subframes, 15 complete cycles |
| Complete local cycles versus GFZ | 10 `SAME_BROADCAST_FIELDS`, all 270 fields uniquely resolved |
| NOAA alone, historical V2 result | 10 `REPRESENTATION_UNQUALIFIED`, unchanged |
| GFZ and NOAA jointly, new result | 10 `EXTERNAL_RECORD_CONFLICT`; no silent source preference |

The selected GFZ multiplicities are 11 for G01/G11/G32, 5 for G17 and 8 for
G20. These are provider-reported counts, not independent votes admitted by our
software. All duplicate issues enter the existing interval intersection.
GFZ and NOAA are reported separately and jointly; their conversion/content
conflicts remain visible. No NOAA precision, L2 metadata, or historical outcome
is repaired to produce agreement. Earlier reports remain byte-identical.

## Reproduction and next physical question

With the existing positioning requirements installed, run offline:

```console
python -m pytest pnt/tests/test_gfz_navigation.py -q
```

The test reconstructs the input selection from all local cycles, verifies
retained member hashes, decodes transmitted words and calls the existing issue
and representation primitives. It compares the complete result with
[the saved machine evidence](results/pnt_gfz_navigation_v1.json.gz).
Uncompressed JSON: 2,132,907 bytes, SHA-256
`3934dc9748e34c386636a065f922cc13d7ae4c7c41d89e9011af9e92d849c2c1`.
Regression checks reject every single-bit change in a real 300-bit subframe,
invalid word representations, truncation and double de-inversion. This adds
one protocol decoder and ordinary tests, not an experiment-specific executor,
seal or authority. NetCDF reading here is fixture intake, not a production
download/stream adapter; the CLI is unchanged.

The witness is suitable for historical **NAV content** comparison on this
exposed case. Source independence, RF origin, pseudorange/PVT authenticity,
freshness, absolute time, attack attribution and P2 detection benefit remain
unassessed. Matching genuine NAV can coexist with manipulated ranges or a replay.
This is also not a matched benign/attack pair. The next useful step is to find
such a documented recording with recoverable local messages/observables and
same-issue external coverage, then assess incremental benefit against local
controls. No hardware purchase, website deployment or new gate sequence is
needed to investigate that question.

[catalog]: https://dataservices.gfz.de/10.1594/gfz.isdc.gnss/gnss-gps-1-navbit/gps-ca-navigation-message-data-bits
[archive]: https://isdc-data.gfz.de/gnss/GNSS-GPS-1-NAVBIT/y2013/GNSS-GPS-1-NAVBIT+2013_094_A.tar
[paper]: https://isdc-data.gfz.de/gnss/GNSS-GPS-1-NAVBIT/documents/BeyerleEtAl-ADataArchiveOfGPSNavigationMessages-2008-corrected.pdf
[gps]: https://prod-01-alb-www-gps.woc.noaa.gov/sites/default/files/2025-07/IS-GPS-200N.pdf
