# DRAO labelled-forward artifact selection

**DRAO_LABELLED_FORWARD_ARTIFACT_SELECTED_UNOPENED**

One metadata-only HTTP `HEAD` request selected the exact BKG product implied by
the already frozen DRAO station, DOY237 date, one-day duration, 30-second
cadence and mixed-observation class. No directory listing, alternate archive,
fallback, RINEX header or body was accessed.

## Selected artifact

| Field | Frozen value |
|---|---|
| station | `DRAO00CAN` / DOMES `40105M002` |
| GPS date | 2026-08-25 / DOY237 |
| product | `DRAO00CAN_R_20262370000_01D_30S_MO.crx.gz` |
| archive | BKG IGS public archive |
| HTTP status | 200 |
| declared length | 2,849,014 bytes |
| content type | `application/x-gzip` |
| ETag | `"2b78f6-659ef7024f09a"` |
| Last-Modified | `Wed, 26 Aug 2026 08:59:33 GMT` |
| Accept-Ranges | `bytes` |

The ETag and declared length are transport metadata, not content integrity.
The complete SHA-256 remains explicitly unknown until a later authorized
materialization.

## Epistemic boundary

This receipt grants no `GET`, decompression, RINEX parsing, structural
admission, measurement inspection or orbital score. The artifact is not yet a
primary. It is only the single candidate that may undergo the already frozen,
value-blind structural scan; becoming a primary remains conditional on a later
integrated proof freeze.

A later one-use authority may materialize this exact locator with at most two
transport attempts before a complete hash exists. Resume is limited to that
pre-hash phase. After the complete compressed SHA-256 is recorded there is
zero retry, zero fallback and no replacement date, endpoint, artifact or PRN.
No observation value may be persisted.

## Access accounting

```text
HEAD requests:              1
alternate locators:         0
body bytes:                 0
RINEX headers:              0
observation values:         0
orbital scores:             0
```

The next maximum action, after review, is a separately authorized one-use
materialization and value-blind structural scan. It is not measurement or
orbital execution.
