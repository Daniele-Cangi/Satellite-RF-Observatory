# ALGO/MDO distinct-root primary plan

## Status

`PRIMARY_PLAN_AND_PREDICTION_FROZEN`

The plan and exact broadcast-orbit curves are frozen. The primary observation
is still sealed and requires separate review. This is not a new gate.

## Physical question

Does the frozen broadcast G22-relative-G30 geometry predict the held-out
continuous-phase coordinate

```text
(ALGO_G22 - ALGO_G30) - (MDO1_G22 - MDO1_G30)
```

better than the same-prefix affine null and the three frozen wrong-orbit
alternatives G01, G14 and G17?

The new information would be generalization beyond the already successful
GOLD/NLIB roots. The DOY217 ALGO/MDO result established only a model-blind
measurement path; it produced no orbital score.

## Frozen primary

- date: 2026-08-07 / GPS DOY219;
- raw window: 05:46:00 through 06:55:00 GPS, inclusive;
- cadence: 30 s;
- raw epochs: 139;
- feature epochs: 137;
- calibration prefix: feature indices 0--76;
- held-out suffix: feature indices 77--136;
- core phase: L1C and L2W;
- same-path code witnesses: C1C and C2W;
- optional diagnostics: S1C and S2W;
- interpolation and gap bridging: forbidden.

The two predeclared products are:

| Station | Product | HEAD length | ETag | Last-Modified |
| --- | --- | ---: | --- | --- |
| ALGO00CAN | `ALGO00CAN_R_20262190000_01D_30S_MO.crx.gz` | 4,320,264 | `"41ec08-658934a2a4a08"` | Sun, 09 Aug 2026 01:38:07 GMT |
| MDO100USA | `MDO100USA_R_20262190000_01D_30S_MO.crx.gz` | 3,559,665 | `"3650f1-658855380e7c4"` | Sat, 08 Aug 2026 08:58:35 GMT |

These are one-request `HEAD` descriptions only. They prove locator
availability, not immutable artifact identity. Full byte count and SHA-256
must be recorded after one future materialization and before any header or
sample decode. There is no fallback product, date or station pair.

## Frozen orbital prediction

The exact-hash broadcast navigation authority is
`BRDM00DLR_S_20262190000_01D_MN.rnx`:

- gzip: 1,391,036 bytes,
  SHA-256 `12246e0e614f0a16c9bd7329ddd637fb541d478160d944131023aa9faeffcc3d`;
- raw: 8,383,950 bytes,
  SHA-256 `8d5126ae5a7a8ad1e718c11a1c575c0961de1c57845ca15da4081e65e5709b5d`.

The prediction compiler was committed before it received that navigation
artifact. It has no observation transport or decoder and reproduced the
frozen geometry-screen regressions exactly:

| Alternative | Held-out non-affine peak-to-peak |
| --- | ---: |
| prefix affine | 148,023.979107 m |
| wrong orbit G01 | 62,887.714392 m |
| wrong orbit G14 | 51,370.298992 m |
| wrong orbit G17 | 192,076.638322 m |

The controlling null remains `WRONG_ORBIT_G14`. The conservative pairwise
physical guard is 3,542.257067 m, leaving 47,828.041924 m of modeled margin.

Bindings:

- plan manifest SHA-256:
  `4bae4d9aa655579263de00e84b6d374a8263b8196122ef024bd39ccfdd804756`;
- compiler source commit:
  `24dd303dcb5395bf158f4e8fed025e4b54ff4609`;
- compiler source SHA-256:
  `922a974a8670812a949b61d2bd4573d93ba5ba003733948e23edd4ae367bef12`;
- compiler manifest SHA-256:
  `ace14f2c6809a11dccc843398a3d4e9a96be67dae0b779a68146cef2739db17c`;
- curve-set SHA-256:
  `cdccb4fcef936c9256b11893b4f9af9b9c5c95400d70cfb4649e576ffe9a5ce1`;
- prediction artifact SHA-256:
  `f88b7a9185203fea00a4587335b2018172c5a894409bb5cb13d481d3e9996c0c`;
- seal SHA-256:
  `f8585632bc5f5ea6f3f94441fae35d58b53ab181bcbeeda32c3daf8747e07793`.

## Admission and outcomes

The future observation is admitted only if both headers cover the exact grid,
match the DOY217-qualified receiver and antenna configuration, expose all
four L1C/L2W links with zero LLI, preserve the same-path code rule and remain
below the frozen geometry-free second-difference limit. Failure is
`MEASUREMENT_INVALID`, not an orbital result.

If the realized measurement envelope cannot preserve the predeclared
distinctions, the outcome is `NOT_DETECTABLE`. Otherwise the only score
outcomes are orbital preferred, one named frozen null preferred, or
`AMBIGUOUS`. Constant and rate are fit on the calibration prefix only; there
is no free time phase, suffix refit or threshold change.

## Access boundary and next step

At seal time:

- descriptive HEAD requests: 2;
- observation headers opened: 0;
- observation payload bytes: 0;
- observation values: 0.

The smallest next step is review of this seal. Only a later explicit authority
may create the disposable one-shot executor. That executor must materialize
each exact predeclared locator once, hash the complete files before header
access, run the frozen admission and comparison in RAM, persist no observation
values, emit one outcome and stop. The seal itself grants no such authority.
