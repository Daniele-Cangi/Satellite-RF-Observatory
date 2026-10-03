# WegenerNet short-baseline inputs, 2024-09-11

These are the first three station names from the public day-255 index: W181,
W182 and W183. The original `.sbx.gz` members cover 00:00–01:00 (availability
and earlier coordinate metadata), then 08:00–11:00 for the unchanged A/B
transfer windows. No station or window was selected for its numerical score.

Attribution: Kirchengast, G.; Ramatschi, M.; Bradke, M.; Kvas, A.;
Fuchsberger, J.; Scheidl, D.; Galovic, R.; Bichler, C. (2025):
*WegenerNet 3D Open-Air Laboratory GNSS StarNet (WSN) Level 0 Data*.
Wegener Center for Climate and Global Change, University of Graz, Austria.
[DOI 10.25364/WEGC/WPS3D-L0-WSN](https://doi.org/10.25364/WEGC/WPS3D-L0-WSN).
The provider's unchanged [README](SOURCE_README.md) states **CC BY 4.0** and
that Level 0 is unchecked raw data. This license applies to the source and
derived measurement data, separately from the repository's software license.

`*_fixed.obs.gz` is a derived RINEX 3.04 conversion of the three concatenated
08:00, 09:00 and 10:00 members. RTKLIB EX CONVBIN 2.5.1 supplied the measurement
conversion. Only the coordinate header is replaced with the earlier midnight
ReceiverSetup declaration; comments identify that change. The observation
body is unchanged. The converter omits 10:59:30; it is not filled or repaired.
These declared coordinates are not an independent survey or an accuracy bound.

[provenance.json](provenance.json) records original and derived hashes, source
URLs, converter versions, conversion checks, coordinate declarations and errors.
Preliminary and unsuccessful `-hp` override headers are retained there as hex;
concatenating each with the primary observation body reconstructs its exact
original input bytes, checked against its saved plain SHA-256. This avoids
retaining three identical observation bodies for each receiver. Both attempts'
complete/partial numerical results remain in the aggregate report.

Compressed conversion logs/traces retain the non-GPS NAV errors. The shared
NOAA navigation input is reused at `../gfz20240911/brdc2550.24n.gz`, with its
original header and attribution intact; no duplicate navigation product is
created. Modeling uses that GPS NAV, not the converter's navigation output.

The optional external cross-check used `gnss-js@2.6.0` (AGPL-3.0-only or
commercial license) to decode the same original logs. It is not a new runtime
dependency, and its code/binary is not distributed here. Both Meas3 decoders
share RTKLIB lineage: agreement checks implementation/rounding, not independent
physical truth. Converter binaries stay external; retained RINEX lets CI replay
the scientific calculation on Linux and Windows without installing either tool.

See [the report](../../../../research/exploratory/PNT_CLOSE_REFERENCE_TRANSFER.md)
for methods, all outcomes, exact reproduction and limits.
