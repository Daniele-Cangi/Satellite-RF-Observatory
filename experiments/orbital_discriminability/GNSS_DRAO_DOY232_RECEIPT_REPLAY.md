# DRAO DOY232 content-blind receipt replay

## Outcome

```text
DRAO_DOY232_RECEIPT_REPLAY_MATERIALIZED
physical decision = NOT_EVALUATED
```

The one authorized replay accessed only the exact frozen compressed
qualification artifact:

```text
DRAO00CAN_R_20262320000_01D_30S_MO.crx.gz
actual bytes = 2,904,457
SHA-256 = fca688310e9bd48a70452e0f9409a24d4b036add44ee31024ca1d76e130fe8d3
```

The actual byte count equals the frozen expected length. GET `Content-Length`,
ETag and Last-Modified were present and matched the selected metadata. These
transport descriptors are not promoted to cryptographic evidence; the
full-file SHA-256 is the content identity.

The two-phase receipt persisted the digest and byte count before cleanup. The
exact payload was then unlinked and its quarantine directory removed. The
receipt SHA-256 is
`10e6c002333080087c5d87787d74a7882175ae72f875f55162ee53653d3341b0`.

## Boundaries preserved

- decompression attempts: `0`;
- RINEX headers parsed: `0`;
- observation values accessed: `0`;
- primary locators selected: `0`;
- primary payload bytes: `0`;
- physical claims authorized: none;
- qualification clauses evaluated: none.

This result repairs artifact identity provenance only. It does not qualify the
DRAO measurement path and produces no orbital score. The next maximum action,
after separate review, is one model-blind DOY232 structural qualification using
the frozen contract and this exact artifact hash.
