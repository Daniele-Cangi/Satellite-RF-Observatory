# GFZ GPS NavBit, 2013-04-04

These five `.nc.gz` files are unchanged members of the public daily archive
linked in [provenance.json](provenance.json). They retain the complete day for
every satellite in the exposed CTTC local replay; only 45 selected subframes
are decoded by the source-intake test. Original and decompressed SHA-256 hashes
are in the provenance file. That JSON is our intake metadata, not a GFZ receipt
or a cryptographic certification of the source.

Attribution: Rothacher, Markus; Beyerle, Georg (2008): *GPS C/A Navigation
Message Data Bits*. GFZ Data Services. DOI:
[10.1594/GFZ.ISDC.GNSS/GNSS-GPS-1-NAVBIT](https://doi.org/10.1594/GFZ.ISDC.GNSS/GNSS-GPS-1-NAVBIT).
The [current GFZ catalog](https://dataservices.gfz.de/10.1594/gfz.isdc.gnss/gnss-gps-1-navbit/gps-ca-navigation-message-data-bits)
lists the data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
verified on 2026-10-03. These external data retain that license independently
of the repository's software license. Files have not been altered; extraction
of five members and selection of subframes are described in the report.

See [the intake report](../../../../research/exploratory/PNT_GFZ_NAVIGATION_WITNESS.md)
for processing, retained failures, replay and claim limits. This is one
provider's aggregated message archive, not independently available station
votes or an independent acquisition clock.
