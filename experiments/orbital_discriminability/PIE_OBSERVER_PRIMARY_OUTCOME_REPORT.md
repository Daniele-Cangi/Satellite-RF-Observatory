# PIE observer primary outcome report

## Terminal outcome

`PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED`

Authorized claim scope:

`HELD_OUT_STATION_CONFIRMED_FOR_THIS_ORBIT_SIGNAL_WINDOW`

The single prospective PIE100USA DOY223 execution completed on its first and
only transport attempt. It confirms that the frozen G22 orbital prediction
preserves the held-out phase structure at this previously unused observer
better than every frozen alternative. It does not establish unconstrained
orbit reconstruction, catalog-wide satellite identity or a general claim
about PIE or other receivers.

## Immutable execution boundary

- executor seal SHA-256: `3b15c0c899756c48c80a6339cb6c6e20a0f493f379f8b439c445caf1bf033e2b`
- authority marker canonical SHA-256: `6f78077bbf374bc463890448ac0b152eb318a77e7f48f4cc03a3d73de977811f`
- outcome canonical SHA-256: `13dc0f6f2dd0d7456bd615599336b4c70354f505821bb694757376f241a1ec9b`
- source commit: `c9334e45025e837a11cc62eec084b1e0495a58e2`
- source SHA-256: `aaa59603eec7dc3139bb4f935faa899e9a8158708c877d8356c459500cf9727a`

The authority marker records zero network requests, headers, payload bytes and
observation values before authority consumption. The executor contacted only
the frozen GSSC product and used no fallback, replacement endpoint or second
window.

## Artifact materialization

- product: `PIE100USA_R_20262230000_01D_30S_MO.crx.gz`
- complete compressed bytes: `3,112,422`
- complete-file MD5: `81d437546a782bbdbc73dbd133aeeb91`
- complete-file SHA-256: `1b3d1190ab2c31591166cddcb42c160f777c05908cadbf83649d10d48a55254d`
- transport attempts before hash: `1`
- hash before decompression, header parsing or record decoding: `true`

The compressed artifact, decoded RINEX and all observation arrays existed only
in RAM and were erased. No compressed or decoded observation artifact and no
observation value was persisted.

## Measurement admission

All predeclared clauses passed:

- all `139` epochs and all `1,112` required structural fields are present;
- L1C/L2W core phase and both LLI fields are valid;
- maximum event-time deviation is `0.0 s` against the frozen `15.0 s` bound;
- maximum geometry-free second differences are `0.004275 m` for G22 and
  `0.003416 m` for G30, both below `0.095147 m`;
- ionosphere-free same-path phase-minus-code variation is `1.538561 m` for
  G22 and `1.735886 m` for G30, both below the frozen `1,250 m` limit.

The receiver serial, antenna serial, firmware, phase-shift records, 30-second
cadence and full-day header coverage match the qualified transform.

## Held-out comparison

Only raw indices `79` through `138` were scored. No constant, rate, time phase
or other nuisance parameter was fitted. Peak-to-peak residual was the primary
ordering statistic, followed by RMS and the frozen hypothesis name.

| Frozen hypothesis | Held-out residual p-p (m) | Held-out RMS (m) |
| --- | ---: | ---: |
| `ORBITAL_G22` | 2.279182 | 7.586689 |
| `FROZEN_AFFINE_NULL` | 190,230.062153 | 61,610.890278 |
| `WRONG_ORBIT_G14` | 190,419.801112 | 298,431.857808 |
| `WRONG_ORBIT_G17` | 300,099.493761 | 266,350.829735 |
| `WRONG_ORBIT_G01` | 580,943.161741 | 677,561.254910 |

The affine null is the runner-up. The orbital model's preference margin is
`190,227.782971 m`, compared with the frozen required guard of
`7,899.820878 m`. The margin therefore passes without changing a threshold,
feature, null, transform or observation window.

## Interpretation and stop

This is real prospective observer-transfer evidence: the model frozen before
PIE observation access predicts the shape seen at an independent station far
better than the frozen non-orbital and wrong-orbit alternatives. It advances
the claim ladder to held-out-station confirmation for this exact G22/G30,
PIE100USA and DOY223 window.

The primary is consumed. No retry, rescore, alternate endpoint, replacement
window or threshold change is authorized. Any next experiment must ask a new
physical question rather than extend this execution administratively.
