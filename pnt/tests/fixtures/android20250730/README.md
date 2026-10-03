# Public Android Raw intake fixture

Source: [S7AM1NA/GNSS-Spoofing-Dataset]
(https://github.com/S7AM1NA/GNSS-Spoofing-Dataset), MIT; original LICENSE retained.
Retrieved 2026-10-03 from
`https://raw.githubusercontent.com/S7AM1NA/GNSS-Spoofing-Dataset/main/sample/gnss_log_2025_07_30_10_15_12.txt`.
No author/library parser code is copied.

`pixel6_first_epoch.txt` contains the original header and every Raw row of the
first epoch, without rewriting bytes. Extraction stops at the first change in
the `utcTimeMillis` field; no measurement-value selection is performed. It has
49 Raw rows, including eight GPS measurements (C1C/C5Q); other constellations
remain in the source and are counted. The extracted byte stream is 18,665 bytes,
SHA-256 `ce7af0eca97f72ffbf1370fe937faac890429a4cf43af4c8cc86743cb47408ed`.

The full public sample is 23,678,435 bytes, SHA-256
`424c74f2b5962b5935c49fa021bb1e2b83a3553b8e23fe07d0127c5a300f9cef`.
Running `python -m pnt android-raw` on that sample retained 11,482 GPS rows:
11,406 normalized, 76 unresolved GPS transmit times. The 54,178 non-GPS rows
were counted as unsupported, out of 65,660 Raw rows total. No replacement,
resampling, smoothing or data repair was attempted. The full sample can be
obtained from the source; it is not duplicated in this small parser fixture.

This is an exposed parser regression input, not a benign/challenge experiment.
The device-reported UTC range is 2025-07-30 02:15:04.999–02:37:24.000, after the
last attack interval in the author's README (ending 02:10:36). Device UTC is
not independently authenticated; absence of an overlap does not certify a
benign receiver. No surveyed position or external reference is supplied here.
The README advertises a 115 MB release, but GitHub's releases endpoint returned
an empty list on retrieval. No attack/false-alarm or external-network benefit
claim is made from the accessible sample.
