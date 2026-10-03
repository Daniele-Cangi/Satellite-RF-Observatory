# Recorded GPS navigation witnesses: JammerTest 2.1.1

The [software mechanism exercise](PNT_NAVIGATION_WITNESS.md) is now extended
to the already exposed [JammerTest 2.1.1 recording](PNT_JAMMERTEST_211.md).
This is an offline content diagnostic, not prospective confirmation or a
qualified spoofing detector. The [complete compressed report]
(results/pnt_navigation_jammertest_211_v1.json.gz) retains raw GPS payloads,
every cycle, source hashes, the strict-reader failure and the explicit recovery.

## Input and decoding

The [public archive][dataset] SHA-256 is
`73e78934aa00d01dfeebabc45f81b38c9c0aecf972f5fc94d9ff60527065b313`.
Its member
`Spoofing/stationary/Medium Power (_1W)/Bands_L1_L2_L5/2.1.1/240911_065707.ubx`
contains 29,893,716 bytes, SHA-256
`05b41c23ea4ec35951bfc2d96b3638e104781c0c70e82ae23ab3adde626b749d`.
The same-day [NOAA composite GPS NAV][nav] SHA-256 is
`ef484bb751743dcb37601112c2a6c0b81c7e738b4cb9f2faf4bfb1fa446aace3`.
NOAA is one external archive; neither its name nor different input bytes
qualifies independent receiver/provider provenance.

The existing UBX reader rejects the recording by default because two packets
have bad transport checksums. Explicit `--recover-corrupt` excludes and counts
them, accepting 39,503 checksum-valid UBX packets. Of 9,387 SFRBX packets,
424 are GPS L1 C/A and 8,963 use unsupported signals/GNSS. Of those 424,
247 contain clock/ephemeris subframes 1/2/3; 177 are subframes 4/5, retained
without interpreting their almanac/ionosphere content.

The [u-blox interface][interface] defines the version-2 header/signal IDs.
Its [receiver documentation][ublox] describes already de-inverted GPS words,
with padding ignored and parity processed by the receiver. The adapter checks
UBX transport checksum and structure; it does **not independently verify
radio parity or RF origin**. [IS-GPS-200N][gps], figures 20-1 and tables
20-I/III, supplies field layouts and scales. Binary values are decoded exactly;
semicircles use decimal pi with a numerical bound of 1e-58 rad or rad/s.
URA uses nominal metres; an unavailable accuracy/TGD or invalid reference
time yields an explicit unusable issue rather than a replacement value.

Only complete subframes 1/2/3 from the same satellite and HOW 30-second cycle,
with matching IODE and low IODC bits, are compared. A return to an old cycle
after another cycle starts cannot reuse its fragments. Repeated/conflicting
frames stay visible. This conservative rule leaves **204 incomplete cycles**
and only **three complete cycles**. It does not establish receiver-output
coverage or continuity during the attack, and no cross-cycle reconstruction
is used to increase the denominator.

## Result

| Complete cycle | Local decoded toc (GPST) | Week / toe / IODE / IODC | Same-day NOAA witness |
|---|---|---|---|
| G17, cycle 17 | 2024-09-11 08:00:00 | 2331 / 288000 / 57 / 57 | All 27 fields compatible |
| G21, cycle 140 | 2024-09-11 07:59:44 | 2331 / 287984 / 27 / 27 | All 27 fields compatible |
| G14, cycle 161 | 2024-10-01 14:00:00 | 2334 / 223200 / 2 / 2 | Issue missing; insufficient evidence |

The supplied day resolves only the 1024-week era; HOW/toc/week and the
satellite identity remain untrusted message declarations. G14's declared date
is retained as evidence, not accepted as capture-time truth. An initial
development check inherited RINEX's toc-day selection and omitted G14.
UBX mode now retains **all decoded issues in the capture**, with a null
selection window and an explicit count outside the declared day. RINEX mode
and the previous v1 report retain their original toc-window contract.

The third issue has no corroboration in the supplied same-day file. This
is not a matched-issue field contradiction or proof that this satellite's
RF originated at a spoofer. The case had [large local clock discontinuities]
(PNT_JAMMERTEST_211.md) already; no incremental detection benefit, independent
time error, false-alarm rate or attack-window attribution is measured here.
Even the two matches do not authenticate pseudoranges, PVT or freshness.
The archive writes zero `af2` with a coarse decimal exponent: the existing
representation interval cannot resolve the full LNAV `af2` range. That
limitation is covered by a regression and is not treated as authentication.

## Reproduction and next evidence

Extract the named member into `jammertest-211.ubx`, retain its bytes and use
the identified NAV file. The strict command rejects the damaged recording;
the retained comparison uses explicit recovery:

```console
python -m pnt navigation 2024-09-11 jammertest-211.ubx --local-format ubx --recover-corrupt --witness NOAA=brdc2550.24n.gz --output NEW_NAVIGATION.json
```

The CLI JSON equals the stored aggregate's `report`. The aggregate also
records acquisition provenance, implementation hashes, the strict attempt
and interpretation. Its uncompressed JSON SHA-256 is
`1da95d2da54afff067c45785bf19981c7faa8f85634e0f007f6d6b9cf5ad3e4f`.
The compact captured fixture exercises nine original subframes and a G17
NAV record from the separate NOAA file. Linux/Windows CI tests all 27 fields,
signed/split values, week rollovers, incomplete/conflicting cycles, malformed
messages, transport damage and retention of the out-of-day issue.

This delivers the raw-log adapter, with limited support rather than a passing
P2 detection claim. The next useful evidence is a matched benign/altered
message case in which the external witness can add information beyond local
controls. The existing synthetic clock-message case illustrates that physical
mechanism; this recording does not establish its real attack performance.
Stop repeating residual/clock variants of this locally obvious episode.

[dataset]: https://zenodo.org/records/15911589
[nav]: https://noaa-cors-pds.s3.amazonaws.com/rinex/2024/255/brdc2550.24n.gz
[interface]: https://content.u-blox.com/sites/default/files/documents/u-blox-F9-HPG-1.32_InterfaceDescription_UBX-22008968.pdf
[ublox]: https://content.u-blox.com/sites/default/files/products/documents/u-blox8-M8_ReceiverDescrProtSpec_UBX-13003221.pdf
[gps]: https://archive.gps.gov/technical/icwg/IS-GPS-200N.pdf
