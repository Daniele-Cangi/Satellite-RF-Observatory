# Cassini DSS-14 rank-1 physical-envelope audit

## Outcome

```text
CASSINI_OPEN_TERM_BOUND_UNAVAILABLE
```

This is a metadata-only closure of the rank-1 2006 DSS-14 candidate. No RSR
artifact, IQ, sample, amplitude diagnostic, or detector was opened or
implemented. The candidate payload remains unassigned and prohibited.

The controlling comparison remains the real-NCO orbital prediction against the
calibration-prefix affine recorded-baseband null. Its held-out peak-to-peak
separation is **0.18576614507706193 Hz**. Neither the larger steering-only
separation nor the Saturn-center null controls this claim.

## Frozen grid and projection

- representative sample grid: `2006-09-08T12:00:01.500500Z` through
  `2006-09-08T15:00:00.500500Z`;
- 10,800 one-second records;
- first 2,160 records are the immutable calibration prefix;
- last 8,640 records are the held-out suffix;
- every physical curve is projected through the same prefix-only affine fit;
- suffix refit is prohibited;
- trajectory: type-1 PREDICT SPK
  `060901AP_SCPSE_06244_06255.bsp`, created before the pass and verified by
  exact SHA-256.

The direct `t - 100 ns`, `t`, `t + 100 ns` trajectory calculation gives a
maximum one-sided timing contribution of `3.7414515929867775e-06 Hz`, or
`7.482903185973555e-06 Hz` two-sided.

## Seven-term ledger

The numbers below are central-model diagnostics after the frozen prefix-affine
projection. They are **not error bounds** and therefore do not reduce the
conservative envelope.

| Term | Provenance | held-out p-p | held-out RMS | Bound state | Reason |
|---|---|---:|---:|---|---|
| Proper time and gravitational frequency | `INDEPENDENT_OF_TARGET_RF` | 0.0176885898 Hz | 0.0082981680 Hz | `UNAVAILABLE` | The outcome-independent IERS central model has no pass-specific hard truncation bound. |
| Relativistic propagation light time | `INDEPENDENT_OF_TARGET_RF` | 0.0000319951 Hz | 0.0000120236 Hz | `UNAVAILABLE` | The static central diagnostic omits unbounded moving-body and higher-order terms. |
| Earth troposphere | `INDEPENDENT_OF_TARGET_RF` | 0.3914154889 Hz | 0.2299763534 Hz | `UNAVAILABLE` | Applicable TSAC TRO exists, but `FITSIG` and the approximate elevation map are not deterministic residual-frequency bounds. |
| Earth ionosphere | `INDEPENDENT_OF_TARGET_RF` | 0.0003162154 Hz | 0.0001530216 Hz | `UNAVAILABLE` | Applicable TSAC ION exists, but `FITSIG` is not a deterministic residual-frequency bound. |
| Interplanetary plasma | `UNKNOWN` | — | — | `UNAVAILABLE` | No applicable outcome-independent finite ray-path bound was found. |
| Station hardware delay | `UNKNOWN` | — | — | `UNAVAILABLE` | No pass-specific DSS-14 end-to-end receiver-delay/frequency hard bound was found. |
| Available media calibration | `INDEPENDENT_OF_TARGET_RF` | 0.3910993797 Hz | 0.2298262698 Hz | `UNAVAILABLE` | Coverage is complete, but residual uncertainty is unbounded; this is a non-additive control and is not double-counted. |

The large central TRO diagnostic is dominated by the documented TSAC
correction-segment transition at the final header. It must not be interpreted
as either a hard error bound or an observed RF effect. The corresponding PDS
TRO label also says 2005 while its filename, archive volume, and content say
2006; the inconsistency is retained descriptively rather than repaired
silently.

## Decision

No term was admitted into a finite error envelope. Consequently:

- combined open-term envelope: `UNAVAILABLE`;
- remaining physical margin: `null`;
- maximum admissible detector resolution: `null`;
- IQ access: not authorized;
- detector implementation: not authorized.

If every unavailable term were counterfactually zero, the optimistic
three-bin ceiling would be `0.06191955405795865 Hz`. This is explicitly **not**
an admission requirement because the missing bounds are the point of the
refusal.

## Change-of-abstraction review

Another single-frequency envelope audit is not the shortest path to a physical
result:

- phase-continuous analysis can improve measurement sensitivity but cannot
  bound plasma or receiver-system nuisance;
- a fixed-NCO product can enlarge the orbital-versus-steering separation but
  does not close those physical terms;
- both remaining DSS-14 header candidates have already been evaluated and
  ranked.

The next smallest physical mechanism to evaluate is therefore a predeclared
**multi-frequency differencing** experiment. A simultaneous frequency pair can
cancel non-dispersive terms and turn dispersive plasma from an unconstrained
nuisance into an observable coordinate. This report does not search for,
design, or execute that experiment.

## Reproducibility and sources

- audit manifest SHA-256:
  `2b50108d5f3e8b8e62d25814fd7eab05ac34285655b8c15f024298d435bde3a4`;
- exact machine-readable result:
  `CASSINI_DSS14_RANK1_OPEN_TERM_AUDIT_RECEIPT.json`;
- official ION product:
  <https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/sagr3_ancillary/ion/s23sagf2006_244_2006_273.ion>;
- official TRO product:
  <https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/sagr3_ancillary/tro/s23sagf2006_244_2006_262.tro>;
- calibration inventory:
  <https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/calib/calinfo.txt>.

All downloaded metadata and exact-hash SPICE kernels were kept in temporary
quarantine for the computation and removed afterwards. No RF data were
persisted.
