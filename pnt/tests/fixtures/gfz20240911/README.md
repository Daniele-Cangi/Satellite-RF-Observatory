# GFZ NavBit and retained capture association, 2024-09-11

The three `.nc.gz` files are unchanged daily G14/G17/G21 members from GFZ's
day-255 archive. They are all satellites with complete local CEI cycles in
the exposed JammerTest 2.1.1 capture. Entire members are retained, not just
matching windows. Original/decompressed hashes and URLs are in
[provenance.json](provenance.json); the tar itself stays external.

Attribution: Rothacher, Markus; Beyerle, Georg (2008): *GPS C/A Navigation
Message Data Bits*. GFZ Data Services,
[DOI 10.1594/GFZ.ISDC.GNSS/GNSS-GPS-1-NAVBIT](https://doi.org/10.1594/GFZ.ISDC.GNSS/GNSS-GPS-1-NAVBIT).
The [current catalog](https://dataservices.gfz.de/10.1594/gfz.isdc.gnss/gnss-gps-1-navbit/gps-ca-navigation-message-data-bits)
licenses the external GFZ data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
independently of the software license. Extraction and analysis are described
in the report; the NetCDF members have not been altered.

`brdc2550.24n.gz` is the unchanged NOAA public same-day composite from the
earlier diagnostic, with its original attribution/header retained.
`capture_association.json` is our provisional association of nine original
SFRBX packets with preceding RAWX payloads and inferred capture ticks. The
packet excerpts come from the [public JammerTest dataset](https://zenodo.org/records/15911589),
Sayyaf, M. I.; Ortiz, M.; Renaudin, V. (2025). Its source metadata specifies
`GPL-3.0-or-later`; the original license text is in
[JAMMERTEST_LICENSE.txt](JAMMERTEST_LICENSE.txt). Captured payload excerpts
retain the dataset's license; the original software license is unchanged.
This association is not a provider receipt or an independent
clock certificate. The full UBX file stays external and is needed to replay
its entire packet-order timeline.

See [the test report](../../../../research/exploratory/PNT_GFZ_RECORDED_ATTACK.md)
for input boundaries, all source failures, replay scope and physical limits.
