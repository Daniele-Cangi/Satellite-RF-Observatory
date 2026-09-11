# DRAO labelled-forward DOY234 artifact selection

**DRAO_DOY234_ARTIFACT_SELECTED_UNOPENED**

The final unconsumed member of the original pre-observation shortlist was
selected with one metadata-only HTTP `HEAD`. No directory, alternate archive,
fallback, RINEX header or response body was accessed.

| Field | Frozen value |
|---|---|
| station | `DRAO00CAN` / DOMES `40105M002` |
| GPS date | 2026-08-22 / DOY234 |
| product | `DRAO00CAN_R_20262340000_01D_30S_MO.crx.gz` |
| archive | BKG IGS public archive |
| HTTP status | 200 |
| declared length | 2,850,623 bytes |
| content type | `application/x-gzip` |
| ETag | `"2b7f3f-659d4b378b5bb"` |
| Last-Modified | `Tue, 25 Aug 2026 01:05:39 GMT` |
| Accept-Ranges | `bytes` |

The ETag and length are transport metadata, not content integrity. Complete
SHA-256 remains unknown until a one-use runner materializes the complete body
and persists its hash before decompression.

This receipt does not grant body access. It binds the future runner to this
locator and artifact only, with at most two transport attempts before a full
hash exists. After that hash there is no retry, fallback, alternate date,
endpoint, product, PRN, feature, transform, threshold or held-out change.

The access boundary remains one `HEAD`, zero body bytes, zero RINEX headers,
zero observation values and zero orbital scores.
