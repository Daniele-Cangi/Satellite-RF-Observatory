# DRAO DOY233 primary-artifact selection

**DRAO_DOY233_PRIMARY_ARTIFACT_SELECTED_UNOPENED**

One metadata-only HTTP HEAD request selected the exact artifact implied by the
already frozen DRAO station, DOY233 date, one-day duration, 30-second cadence
and mixed-observation product class. No directory listing, alternate archive,
fallback, observation header or body was accessed.

## Selected artifact

| Field | Frozen value |
|---|---|
| station | `DRAO00CAN` / DOMES `40105M002` |
| role | one-shot held-out primary |
| GPS date | 2026-08-21 / DOY233 |
| product | `DRAO00CAN_R_20262330000_01D_30S_MO.crx.gz` |
| archive | BKG IGS public archive |
| HTTP status | 200 |
| declared length | 2,886,587 bytes |
| content type | `application/x-gzip` |
| ETag | `"2c0bbb-6599ef1b69d62"` |
| Last-Modified | `Sat, 22 Aug 2026 08:57:35 GMT` |
| Accept-Ranges | `bytes` |

The ETag and length are frozen transport identity, not cryptographic content
integrity. The complete SHA-256 is still unknown and no arbitrary value
replaces it.

## Boundary

This receipt authorizes no GET, decompression, header parse, measurement
admission or score. Every scientific clause and orbital outcome therefore
remains `NOT_EVALUATED`.

A separately reviewed one-use execution may materialize only this locator with
at most two transport attempts before a complete hash exists. Resume is
allowed only in that pre-hash transport phase. The exact byte count and frozen
HTTP identity must match, and the complete compressed SHA-256 must be recorded
before decompression. From that point onward there is zero retry, zero fallback
and no replacement date, station or feature.

The single future action must then either stop `PRIMARY_NOT_EVALUATED` on a
descriptive/transport failure, stop on a typed admission failure without an
orbital score, or proceed through the already frozen opaque score and produce
one terminal outcome.

## Access accounting

```text
HEAD requests:              1
body bytes:                 0
RINEX headers:              0
observation values:         0
orbital scores:             0
```
