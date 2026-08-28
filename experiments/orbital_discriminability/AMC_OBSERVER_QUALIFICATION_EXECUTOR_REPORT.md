# AMC observer structural-qualification executor

## Outcome

`AMC_OBSERVER_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED`

This is an offline freeze. No AMC product, RINEX header, observation record or
value was requested. The seal does not authorize live execution.

## Physical boundary

```text
Physical question:
Can AMC preserve the already frozen G22-minus-G30 phase coordinate and its
same-path witnesses over the complete prospective window?

New information produced by the later one-shot run:
Whether the independently selected AMC measurement root has the exact event
grid, phase/LLI continuity and code-witness structure needed before a held-out
orbital comparison can be made.

Why existing evidence cannot answer it:
PIE proved the coordinate at another station and pass. The AMC site log and
directory listing prove product and hardware descriptions, not RINEX field
occupancy or continuity.

Minimum experiment:
One value-blind structural scan of the predeclared AMC DOY222 product.

Stop condition:
Stop after one structural outcome. Keep AMC DOY221 unopened; qualification
failure authorizes no substitute date, product or window.
```

## Frozen product and transform boundary

- station/product: `AMC400USA` /
  `AMC400USA_R_20262220000_01D_30S_MO.crx.gz`;
- frozen GPS window: `2026-08-10T05:37:30` through `06:46:30`, 139 epochs at
  30 seconds;
- inherited structural split boundary: raw index 79,
  `2026-08-10T06:17:00 GPS`;
- core phase: `L1C`, `L2W` on `G22`, `G30`;
- continuity witnesses: zero/blank LLI and exact epoch grid, with no
  interpolation or gap bridging;
- same-path code witnesses: `C1C`, `C2W`, at least 95 percent per link and
  present at raw indices 0, 78, 79 and 138;
- `S1C` and `S2W`: optional diagnostics, never fatal;
- parser boundary: framing, occupancy and the one-character LLI only. Phase,
  code, SNR, Doppler and all other observation scalars are neither converted
  nor persisted.

The expected header configuration is receiver `SEPT POLARX5TR` serial
`3013929`, firmware `5.6.0`, antenna `TPSCR.G5C NONE` serial `1364-10065` and
marker `AMC4`. Full `TIME OF FIRST OBS` / `TIME OF LAST OBS` coverage is
mandatory.

## Identity, retries and one-shot authority

The prior GSSC directory description fixes 3,455,043 compressed bytes and
modified time `2026-08-11 03:01:26`. Its literal `md5` value `1` is explicitly
not treated as a checksum. A future authorized run must hash the complete file
with SHA-256 before decompression or record scanning.

Only a transport interruption before that complete-file hash may be retried,
with at most two total attempts. Product-description, identity or structural
errors receive no retry. After the hash there is no retry. Before the first
network request the executor must atomically write its authority-consumed
marker; an existing marker or outcome makes another run impossible.

AMC DOY221 remains the prospective primary candidate. Its locator, header,
payload and values are absent from both manifest and executor seal, and all
four access counters remain zero.

## Frozen lineage

| Item | Frozen identity |
| --- | --- |
| source commit | `d8281f2d183b274c5d8f94a7769051440ad95da0` |
| executor source SHA-256 | `6bc2044f78e8afeb2f31a74d47b716ebbbde86350b78503ce135c8bf8f6d3fa6` |
| structural manifest SHA-256 | `5f06900060478f72993a801db5a47ad6aef674b36b847e6aa10ed869abe7cc40` |
| executor seal SHA-256 | `ffd6b009a9e13d05c7b879b5cbb795376d2f9ba1ddeb0ac17bd66ffff3b523ad` |
| metadata report SHA-256 | `e0c8d9496448ead1ac5bfe07cd17a0f25623853c26c70b6f4a1edb32913929fa` |
| geometry receipt SHA-256 | `4982a32459d880a17abab9cf726ee6e8f6383e1d0b570abbf77fd07341d459d5` |

The seal also binds Python `3.13.5`, `hatanaka 2.8.1` and `requests 2.32.4`.

## Verification

- focused pre-seal offline suite: 18 passed;
- exact committed-seal regression: passed;
- Ruff check and formatting: passed;
- complete offline suite on this Windows checkout: 1,197 passed and five
  unrelated byte-exact frozen-artifact tests failed because tracked LF files
  are checked out as CRLF; none of those five artifacts was modified.

The next maximum action is review of exactly one DOY222 structural execution.
It is not AMC primary authority and cannot produce an orbital score.
