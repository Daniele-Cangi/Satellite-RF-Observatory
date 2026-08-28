# AMC observer primary outcome report

## Terminal outcome

`AMC_HELD_OUT_ORBITAL_MODEL_PREFERRED`

Direct receipt claim scope:

`HELD_OUT_STATION_CONFIRMED_FOR_THIS_ORBIT_SIGNAL_WINDOW`

The single prospective AMC400USA DOY221 execution completed on its first and
only transport attempt. The prediction, hypotheses, measurement clauses,
guard, prefix/held-out partition and zero-fit scorer were frozen before any
primary access. The result confirms that the frozen G22-relative-to-G30
orbital prediction preserves the held-out AMC phase structure better than
every frozen alternative.

Together with the earlier PIE held-out result, and only within the scope fixed
by the AMC prospective plan, this supports
`INDEPENDENT_OBSERVER_AND_PASS_REPLICATION_FOR_THIS_ORBIT_SIGNAL_FAMILY`.
AMC and PIE are distinct physical receiver instances, antennas, monuments,
time references, observers and passes, but both use the SEPT POLARX5TR receiver
family. The result therefore does not establish receiver-family independence,
satellite identity, free orbit recovery or a general receiver claim.

## Immutable execution boundary

- executor seal canonical SHA-256: `0b6ffe5af82b15404b7a546e8203df6415a68e0ba373c03500d31d4645f44893`
- authority marker canonical SHA-256: `170d68c0af0f48e29c574b3455252ffeb73accc948add9e773fd4c6395f65706`
- outcome canonical SHA-256: `2cd799c2e070efb6eee3a39a79610bc1d11b34068c26815bdf53aa818eda0c34`
- source commit: `b31a987987578a24fdc0594c44d00abf787f8510`
- source SHA-256: `d87cde21fe8b0ff4e6265e4e460c1c24aaad6a2a590f85d0b8e830fa9975ef63`

The authority marker was persisted before network access and records zero
requests, headers, payload bytes and observation values before authority
consumption. The executor contacted only the frozen GSSC product. No fallback,
replacement endpoint or second window was used.

## Artifact materialization

- product: `AMC400USA_R_20262210000_01D_30S_MO.crx.gz`
- complete compressed bytes: `3,415,979`
- complete-file MD5: `aa4d25b59ec992f4046a13616b2d6c13`
- complete-file SHA-256: `edbe8adfc6bc7ce72c9082f549840576a27a4a949f974a2c7bf1820f82ade425`
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
- maximum geometry-free second differences are `0.005680 m` for G22 and
  `0.002839 m` for G30, both below `0.095147 m`;
- ionosphere-free same-path phase-minus-code variation is `2.856095 m` for
  G22 and `2.134502 m` for G30, both below the frozen `1,250 m` limit.

The receiver serial, antenna serial, firmware, phase-shift records, 30-second
cadence and full-day header coverage match the qualified transform.

## Held-out comparison

Only raw indices `79` through `138` were scored. No constant, rate, time phase
or other nuisance parameter was fitted. Peak-to-peak residual was the primary
ordering statistic, followed by RMS and the frozen hypothesis name.

| Frozen hypothesis | Held-out residual p-p (m) | Held-out RMS (m) |
| --- | ---: | ---: |
| `ORBITAL_G22` | 1.409090 | 6.452538 |
| `FROZEN_AFFINE_NULL` | 162,245.831253 | 52,789.662366 |
| `WRONG_ORBIT_G17` | 162,721.517765 | 53,983.203918 |
| `WRONG_ORBIT_G14` | 220,147.746684 | 351,742.860026 |
| `WRONG_ORBIT_G01` | 498,273.342810 | 534,213.163006 |

The affine null is the runner-up. The orbital model's preference margin is
`162,244.422162 m`, compared with the frozen required guard of
`7,339.701235 m`. The margin therefore passes without changing a threshold,
feature, null, transform or observation window.

## Interpretation and stop

This is prospective evidence that the previously frozen orbital structure
transfers to another observer and another pass. The evidence is especially
discriminating against an affine-in-time explanation: the measured orbital
residual is about five orders of magnitude smaller in peak-to-peak scale than
the closest frozen null.

The primary is consumed. No retry, rescore, alternate endpoint, replacement
window or threshold change is authorized. Any next experiment must ask a new
physical question rather than extend this execution administratively.
