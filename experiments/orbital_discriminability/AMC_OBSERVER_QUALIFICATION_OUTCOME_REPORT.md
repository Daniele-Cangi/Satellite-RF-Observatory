# AMC observer structural-qualification outcome

## Outcome

`AMC_OBSERVER_QUALIFICATION_PASSED`

The one authorized, value-blind AMC DOY222 qualification is consumed. It is a
measurement-path result, not a measurement admission or orbital score.

AMC DOY221 remains unopened:

```text
locator requests: 0
headers:          0
payload bytes:    0
values:           0
```

## Materialization and identity

The exact frozen product was obtained on the first transport attempt:

- product: `AMC400USA_R_20262220000_01D_30S_MO.crx.gz`;
- complete compressed bytes: `3,455,043`;
- complete-file SHA-256:
  `1b2257350a6cadb5713c5db9316b87bc1cd61dc49e71533189741e3b1a45cea8`;
- computed MD5: `9973b2e2db0fbbf52750ed55c9886e14`;
- GSSC directory modified time: `2026-08-11 03:01:26`;
- response type: `application/x-gzip`.

The complete-file SHA-256 was computed before decompression, header parsing or
record scanning. The GSSC directory's literal `md5` value `1` was not treated
as a checksum.

## Structural result

The RINEX 3.04 header confirms the frozen AMC chain:

- marker/station: `AMC4` / `AMC400USA`;
- receiver: `SEPT POLARX5TR`, serial `3013929`, firmware `5.6.0`;
- antenna: `TPSCR.G5C NONE`, serial `1364-10065`;
- declared interval: 30 seconds;
- `TIME OF FIRST OBS`: `2026-08-10T00:00:00 GPS`;
- `TIME OF LAST OBS`: `2026-08-10T23:59:30 GPS`;
- receiver clock offset applied: `0`.

The frozen window `05:37:30--06:46:30 GPS` contains all 139 expected epochs.
Across G22/G30 and the six retained observables, all 1,668 structural rows are
`PRESENT`; there are no parser issues, gaps or nonzero LLI states. The joint
core segment therefore spans all 139 epochs (4,140 seconds elapsed).

Every C1C/C2W link is present at all 139 epochs, so the predeclared same-path
code-witness clause is satisfied. S1C/S2W remain optional diagnostics.

## Epistemic boundary

The executor inspected only RINEX framing, field occupancy and one-character
LLI flags. It converted and persisted no phase, code, SNR, Doppler or other
observation scalar. The compressed and decoded products existed only in RAM
and were zeroized; no observation artifact was persisted.

Consequently:

- structural capability for the frozen G22/G30 field family is established;
- geometry-free phase health remains `NOT_EVALUATED_BY_VALUE_BLIND_AUTHORITY`;
- quantitative measurement admission remains `NOT_EVALUATED`;
- the AMC DOY221 held-out comparison remains `NOT_EVALUATED`;
- no orbital score or identity claim is authorized.

The shared POLARX5TR receiver family with PIE remains a declared common-mode
limitation even though receiver serial, antenna, monument and clock roots are
distinct.

## Frozen receipts

| Receipt | Canonical SHA-256 |
| --- | --- |
| authority consumed | `7379ed30f51d06f6a3b2cffdf2e5b22d4ce0425ae99383f8e3c589558caa4310` |
| outcome | `8c543bbd5d00128c70feab66574df4b878983f036daab932ba7cb6714ee829c4` |
| structural summary | `3e1be4ca9ef741690af99d6206ff94719fbae32b97fe6792034ac87ac9efca69` |
| structural coverage | `bfaccd2ca742f329fe56d6df5e88774c73790040eca2bee5eb3c6ca907718077` |

## Next maximum action

The next work is offline review and freezing of one prospective AMC DOY221
plan and its exact model/null predictions. It may use the now-proven structural
field family, but it may not treat structural presence as quantitative
measurement validity. DOY221 access still requires a later, separately
reviewed one-shot executor and authority.
