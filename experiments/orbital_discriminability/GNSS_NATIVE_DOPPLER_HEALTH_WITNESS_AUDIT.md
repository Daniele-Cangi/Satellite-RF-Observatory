# GNSS native-Doppler health-witness audit

## Outcome

```text
GNSS_DOPPLER_HEALTH_WITNESS_BOUND_UNAVAILABLE
```

This is a bounded, outcome-independent documentation and receipt audit.  It
does not reopen the destroyed DOY 219 primary, access either reserve, change
the frozen evaluator, rescore the primary or create a new gate.

## Physical question

Can any receiver or RINEX health indicator already present in the frozen
KIRU00SWE--MAT100ITA lineage place a numerical upper bound on native
`D1C/D2W` error, so that a future negative orbital result would remain
interpretable?

The new information is negative but physical: the current RINEX measurement
path proves availability of Doppler values, not their held-out error bound.
The minimum audit was therefore the exact receiver identities, the retained
RINEX semantics, the primary parser boundary and public manufacturer
documentation.  The stop condition is reached because none supplies the
required mapping; no threshold may be synthesized from DOY 219.

## Exact retained measurement path

| Station | Receiver in frozen receipt | RINEX | Retained signal health |
|---|---|---:|---|
| KIRU00SWE | `SEPT POLARX5TR`, firmware `5.6.0` | 4.01 | `S1C`, `S2W` in `DBHZ`; no receiver-native tracking status |
| MAT100ITA | `LEICA GR30`, firmware `4.83/7.900` | 3.04 | `S1C`, `S2W` in `DBHZ`; no receiver-native tracking status |

The value-blind qualification decoded zero LLI values and zero SSI values.
The primary evaluator subsequently parsed only the first 14 characters of
each 16-character observation field.  It retained numeric D/C/S observables,
but not either indicator character.  The complete primary time series was
then destroyed as required.  This audit therefore cannot recover a lock or
status history that is absent from the receipt.

## RINEX semantics

The authoritative [RINEX 4.01
specification](https://files.igs.org/pub/data/format/rinex_4.01.pdf) states that
the loss-of-lock indicator is for phase observations only.  Blank or zero
also means either OK *or not known*.  LLI is consequently neither a
standardized `D1C/D2W` validity flag nor a quantitative Doppler-error bound.

The same specification defines SSI as a coarse signal-strength indicator and
prefers explicit `Sna` signal-strength observations.  It does not map SSI or
`Sna` to Doppler accuracy.  The older [RINEX 3.04
specification](https://files.igs.org/pub/data/format/rinex304.pdf) labels the
30--35 dB-Hz SSI bin as a general threshold for good tracking.  That label is
not an error ceiling for a single native Doppler observable, is not retained
as such by RINEX 4.01, and cannot be promoted into a common KIRU/MAT1 Doppler
threshold.

## Receiver-documentation audit

### KIRU / PolaRx5TR

The official [PolaRx5TR product
description](https://www.septentrio.com/en/products/gnss-receivers/gnss-reference-receivers/polarx-5tr)
claims high-precision, low-noise measurements and supports interference and
tracking monitoring.  Those are qualitative capabilities, not a numerical
native-Doppler guarantee.

The official [PolaRx5TR user manual
v2.7](https://www.septentrio.com/system/files/support/polarx5tr_user_manual_v2.7.pdf)
is applicable to firmware 5.5.0, while the receipt identifies 5.6.0.  It
documents external 10 MHz/PPS operation and internal measurement-latching
calibration, but it gives no raw Doppler accuracy as a function of C/N0, lock
time or receiver status.  The RINEX header also does not prove whether the
station was using the documented external-reference configuration.

Septentrio's official [RxTools
manual](https://www.septentrio.com/system/files/support/rxtools_v25.0.0_user_manual.pdf)
shows that receiver-native SBF material can expose Doppler, lock time and C/N0
as distinct fields.  Their existence in a different native product does not
put them in the historical RINEX artifacts or establish a numerical
lock/C/N0-to-Doppler-error transfer function.

### MAT1 / Leica GR30

The official [Leica GR30/GR50 data
sheet](https://leica-geosystems.com/-/media/files/leicageosystems/products/datasheets/gr30-gr50-new/leica%20gr30%20gr50%20ds%20846250%200426%20en%20lr.pdf)
publishes carrier-phase measurement noise and solution-level velocity
performance under stated operating assumptions.  Carrier-phase RMS and a
multi-satellite PVT/VADASE velocity solution are different estimands from the
single-epoch raw `D1C/D2W` values used here.  Converting those product-level
figures into a Doppler bound would silently assume receiver algorithms,
covariance and signal conditions that the receipt does not retain.

The bounded public-document search found no GR30 mapping from RINEX SNR,
LLI/SSI or a tracking flag to a maximum per-observation Doppler error for the
identified firmware/export path.

This is not a claim that no private or unpublished receiver calibration can
exist.  It is a claim about what the frozen receipts plus the audited public
documentation can support.

## Candidate witnesses

| Candidate | What it establishes | Doppler-error bound | Admission |
|---|---|---:|---|
| Complete finite `D1C/D2W` grid | measurement values were delivered | none | `MEASUREMENT_AVAILABLE` |
| Code observations `C1C/C2W` | same signal family was represented | none | descriptive only |
| Explicit `S1C/S2W` dB-Hz | received signal-strength estimate | none | descriptive only |
| RINEX LLI | phase lock/cycle-slip state, when present | not defined for D observations | not applicable |
| RINEX SSI | coarse signal strength, when present | none | not admitted |
| PolaRx5TR native SBF status | potentially richer receiver state | absent from artifact and receipt | not available |
| Leica phase/PVT specifications | phase or solved-position/velocity performance | not transferable to raw D | not admitted |
| `0.560609157 Hz` prefix residual | exact path was calibration-compatible in the prefix | prefix only | `PREFIX_COMPATIBLE` |
| dispersive L1/L2 witness | ionospheric combination stayed inside its envelope | does not bound receiver Doppler error | orthogonal witness only |
| `1.702713980 Hz` development envelope | historical exact-path performance on DOY 214 | no retained health transfer into a later suffix | development evidence only |

## Why the primary remains unrescorable

The old SNR-extrema clause remains the frozen cause of
`NOT_DETECTABLE`; this audit does not reinterpret it.  The receipt contains no
held-out orbital/null scores and no retained series from which a different
health test could be computed.  A 30 dB-Hz cutoff, Leica velocity figure,
LLI rule, quantile or roughness threshold selected now would be post-outcome.

The correct distinctions are:

```text
MEASUREMENT_AVAILABILITY: SATISFIED
PREFIX_MODEL_COMPATIBILITY: SATISFIED
HELDOUT_DOPPLER_ERROR_BOUND: UNRESOLVED
DOY_219_ORBITAL_HYPOTHESIS: NOT_EVALUATED
RESERVE_ACCESS: NOT_AUTHORIZED
```

## Minimum future requirement

A reserve can support an interpretable negative only after one of these is
frozen from evidence independent of that reserve:

1. receiver-native per-observation integrity metadata plus a documented
   configuration-specific numerical mapping to maximum native-Doppler error;
   or
2. a separate development record on the same receiver/export path that
   calibrates a predeclared, causally direct Doppler-error witness and its
   transfer envelope.

Field presence, positivity, SNR magnitude, a lock label or solution-level
velocity accuracy alone is insufficient.  Until such a bound exists, the GNSS
reserve is `BLOCKED_BY_DOPPLER_HEALTH_PROVENANCE`.  This block does not by
itself justify a new gate or additional observation access.

## SHOCK

The experiment already had a direct calibration witness--the prefix Doppler
residual--but treated an uncalibrated amplitude statistic as the controlling
held-out health witness.  More metadata is not automatically better.  The
needed witness is the smallest one whose failure can absorb the orbital
decision margin, and the current RINEX products do not preserve such a bound.
