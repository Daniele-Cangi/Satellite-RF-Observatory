# TEXBAT ds7 with two public NOAA witnesses — exposed-data contrast

## Result and boundary

The documented TEXBAT ds7 time-push can be paired, without new equipment or
raw-I/Q processing, to two physically distinct public CORS receivers. On the
2012-09-14 GPST grid, TXAU and SAM2 supply C1 code for 14 matched epochs and
11 common GPS satellites per epoch. The first two epochs are in the published
no-spoofing interval; two are in takeover; ten are in the time-push interval.

| Published ds7 segment (RRT seconds) | Matched epochs / code rows | Median absolute ds7 − cleanStatic code change | Median absolute change in satellite differences |
|---|---:|---:|---:|
| No spoofing, 0–110 | 2 / 22 | 0 m | 0 m |
| Takeover, 110–150 | 2 / 22 | 6.61 m | 0.08 m |
| Time push, 150 onward | 10 / 110 | 168.86 m | 0.53 m |

The [machine-readable result](results/pnt_texbat_noaa_v1.json) includes every
matched epoch, source hash, selection count and exclusion count. During the
time push the per-epoch median local code change reaches 313.17 m, while the
per-epoch median satellite-difference change stays at or below 1.04 m. The
maximum individual satellite-difference change is 3.67 m. These are
descriptive, correlated observations, **not** attack detection rates or a
network advantage. No threshold or false-alarm claim is made. The two benign
epochs cannot establish a representative clean distribution.

For a satellite `s` and reference satellite `r`, the reported contrast is
`[(ds7_s − ds7_r) − (clean_s − clean_r)]`. At the same matched epoch, subtracting
TXAU or SAM2 C1 from both local recordings gives
`[(ds7_s − witness_s) − (clean_s − witness_s)] = ds7_s − clean_s`.
The witnesses establish real simultaneous coverage and constrain the compared
satellite/epoch set; they **do not** supply a detector gain in this particular
counterfactual. A common receiver-wide code offset is exactly removed by the
satellite difference. The outcome demonstrates a blind mode of geometry-only
double differences for this known time-push attack, not signal authenticity,
attribution, fix validation or absolute-time verification.

## Inputs and reproduction

- UT [TEXBAT scenario description](https://radionavlab.ae.utexas.edu/texbat/)
  and [ds7 segment timing](https://rnl-data.ae.utexas.edu/datastore/texbat/texbat_ds7_and_ds8.pdf).
  The public processed-data directory provides
  [cleanStatic/channel.mat](https://rnl-data.ae.utexas.edu/datastore/texbat/processed/cleanStatic/channel.mat)
  and [ds7/channel.mat](https://rnl-data.ae.utexas.edu/datastore/texbat/processed/ds7/channel.mat); its
  [readme](https://rnl-data.ae.utexas.edu/datastore/texbat/processed/readme.txt)
  identifies the GRID/pprx receiver observables and transpose convention.
  [Channel documentation](https://rnl-data.ae.utexas.edu/datastore/satNavCourse/logFileDocumentation/channeldef.txt)
  identifies RRT, ORT, pseudorange, validity and error indicators.
- NOAA's [station list](https://geodesy.noaa.gov/CORS/sort_sites.shtml)
  identifies TXAU (TxDOT Austin RRP2) and SAM2 (SAMINC Austin) as separate
  stations in service in 2012. NOAA-hosted daily observation files are
  [TXAU 2012/258](https://noaa-cors-pds.s3.amazonaws.com/rinex/2012/258/txau/txau2580.12d.gz)
  and [SAM2 2012/258](https://noaa-cors-pds.s3.amazonaws.com/rinex/2012/258/sam2/sam22580.12d.gz).
  Both decode to RINEX 2.11, declare GPST and contain GPS C1 at 30-second epochs.

Download those four files to a local directory and run:

```console
python -m research.exploratory.pnt_texbat_noaa cleanStatic-channel.mat ds7-channel.mat txau2580.12d.gz sam22580.12d.gz report.json
python -m pytest research/exploratory/tests/test_pnt_texbat_noaa.py -q
```

The committed report's four SHA-256 hashes identify the precise inputs.
Raw UT data are not redistributed in this repository. The adapter reads each
source once, hashes those bytes, decodes the two NOAA gzip/Hatanaka files, and
accepts only the declared station, GPST, uncorrected clock and ordinary
observation epochs. The NOAA files also contain 23 comment-only splice events
each; those comments are skipped, while substantive header updates fail.

The TEXBAT ORT gives GPS week 1705, 2012-09-14. For comparison, a fixed
RRT-to-GPST offset is calculated from 3,192 matched, identical code rows in
RRT 20–80 s, safely inside the source's no-spoofing interval. This offset is
**receiver-derived**, not an independent clock. It maps the nearest 5 Hz RRT
sample to each witness's 30-second GPST epoch within 0.11 s; attacked ORT is
never used to retime the comparison. TEXBAT valid GPS L1 code is compared with
NOAA GPS C1 only as an L1-code family. It does not establish identical receiver
tracking, calibration or signal-code conventions. Nonzero GRID error indicators
on otherwise valid code remain included and counted.

Across the full NOAA day, 28,532 rows have C1 at both stations; 28,368 are
outside the much shorter common TEXBAT recording span. Within that span, 164
two-witness rows exist, 10 lack a valid local clean/attack pair and 154 match.
The two external receivers are geographically near Austin but share the GPS
constellation and NOAA archive; neither is an independent non-GNSS time source.
The local capture's independently surveyed coordinates are not established by
these four files. No absolute local–network geometric residual or response
latency is inferred.

## Next physical question

The next software-only experiment should test whether a **reference-only**
network model, with a fixed-site coordinate justified independently of the
attacked ds7 output, exposes a receiver-clock innovation during this time push
that a local-only control misses at comparable benign false alarms. If no
defensible independent coordinate/clock baseline is available, the honest
claim remains incident context and this geometry-only blind mode. Do not turn
this exposed comparison into prospective confirmation or a live blocking rule.
