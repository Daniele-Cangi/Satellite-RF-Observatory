# DRAO DOY232 qualification-artifact selection

**DRAO_DOY232_ARTIFACT_SELECTED_PRIMARY_STILL_SEALED**

One metadata-only HEAD request selected the exact qualification artifact
allowed by the frozen contract. No observation header, body byte or value was
opened, and no orbital or measurement claim was produced.

## Selection

| Field | Frozen value |
|---|---|
| station | `DRAO00CAN` |
| role | qualification only; never scored and never primary |
| GPS date | 2026-08-20 / DOY232 |
| product | `DRAO00CAN_R_20262320000_01D_30S_MO.crx.gz` |
| archive | BKG IGS public archive |
| HTTP status | 200 |
| declared content length | 2,904,457 bytes |
| content type | `application/x-gzip` |
| ETag | `"2c5189-6598ad1ef8dbf"` |
| Last-Modified | `Fri, 21 Aug 2026 08:57:02 GMT` |
| Accept-Ranges | `bytes` |

The product name is the deterministic IGS long name implied by the already
frozen station, date, one-day duration, 30-second cadence and mixed-observation
class. Exactly one candidate locator was attempted. No alternate archive,
station, date or signal family was searched.

## What the metadata do not prove

The product name and successful HEAD response do not prove its internal RINEX
version, marker, receiver, antenna, time coverage, signal inventory,
continuity or physical witness quality. Every qualification clause therefore
remains `NOT_EVALUATED`.

The ETag is transport metadata, not a cryptographic checksum. The complete
artifact SHA-256 remains `PENDING_COMPLETE_MATERIALIZATION`; no arbitrary hash
is substituted. `Accept-Ranges: bytes` only supports a possible bounded
pre-hash resume and supplies no integrity evidence.

## Future materialization boundary

A later, separately reviewed action may materialize only this exact locator.
It must:

1. permit at most two transport attempts, both against the same locator;
2. use resume only before a complete-file hash exists;
3. verify the frozen HTTP identity and exact byte count;
4. compute the complete compressed-file SHA-256 before decompression;
5. stop on metadata or identity change without choosing a fallback;
6. keep DOY233 completely unselected and unopened.

Only after the complete hash is recorded may a separately authorized
qualification parse the header or observation records under the frozen
model-blind contract.

## Access accounting

```text
HTTP HEAD requests:                1
qualification body bytes:         0
qualification observation headers: 0
qualification observation values: 0
primary locators/headers/bytes/values: 0
```

The next maximum action is review and complete materialization of this single
qualification artifact. This receipt itself grants no body access.
