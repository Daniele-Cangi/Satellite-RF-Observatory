# DRAO labelled-forward DOY238 artifact selection

**DRAO_DOY238_ARTIFACT_SELECTED_UNOPENED**

One metadata-only HTTP `HEAD` request selected the exact BKG product implied by
the already frozen station, DOY238 date, one-day duration, 30-second cadence
and mixed-observation class. No directory listing, alternate archive, fallback,
RINEX header or body was accessed.

## Selected artifact

| Field | Frozen value |
|---|---|
| station | `DRAO00CAN` / DOMES `40105M002` |
| GPS date | 2026-08-26 / DOY238 |
| product | `DRAO00CAN_R_20262380000_01D_30S_MO.crx.gz` |
| archive | BKG IGS public archive |
| HTTP status | 200 |
| declared length | 2,852,212 bytes |
| content type | `application/x-gzip` |
| ETag | `"2b8574-659fd671597b7"` |
| Last-Modified | `Thu, 27 Aug 2026 01:39:11 GMT` |
| Accept-Ranges | `bytes` |

The ETag and length are transport metadata, not content integrity. Complete
SHA-256 remains unknown until the one-use runner has materialized the complete
body and persisted its hash before decompression.

## Boundary

This receipt does not itself grant body access. It binds a future one-use
runner to this locator only, with at most two complete transport attempts before
a full hash exists. After that hash there is zero retry, fallback, alternate
date, endpoint, artifact, PRN, feature, transform, threshold or held-out change.

Access at selection is one `HEAD`, zero body bytes, zero RINEX headers, zero
observation values and zero orbital scores.
