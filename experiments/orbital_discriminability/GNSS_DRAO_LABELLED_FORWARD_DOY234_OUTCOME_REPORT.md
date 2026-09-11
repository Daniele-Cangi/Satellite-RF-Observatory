# DRAO labelled-forward DOY234 outcome

**ORBITAL_MODEL_PREDICTIVELY_PREFERRED**

The final unconsumed geometry in the original DRAO shortlist has produced one
real, terminal held-out event. No parameter, PRN, window, transform, nuisance,
null or decision bound changed after observation access, and the consumed
primary cannot be retried or rescored.

## Immutable materialization

The exact BKG product
`DRAO00CAN_R_20262340000_01D_30S_MO.crx.gz` was materialized on the first
transport attempt. Its complete size is 2,850,623 bytes and its SHA-256 is
`5eb4c7f8b2fa3a0b2f3b4fe40de1f69a85a9150bd5eafd61667fc84bcf9e5335`.
The complete hash receipt was written before decompression. The compressed
product, decoded RINEX, observation values and derived series were not
persisted.

## Measurement admission

The frozen 2026-08-22 05:05:00--06:14:00 GPS window contains all 139 normal
epochs for G14/G15/G17/G20/G24/G30. All 3,336 required structural cells are
`PRESENT`. Event times land exactly on the frozen 30 s grid.

Both required `SYS / PHASE SHIFT` records are valid reference-signal blank-
correction states. Scale-factor absence is the specification-defined unity
state, and the receiver-clock transform is accounted for exactly once.

The largest geometry-free second difference is `0.040297855 m`, below the
frozen `0.095146836 m` limit. The largest held-out same-path phase/code witness
is `8.514774204 m`, below the frozen `1,250 m` limit. The measurement therefore
entered the score without the prediction bundle having been available during
admission.

## Frozen held-out comparison

| Family | Controlling prefix p-p | Controlling held-out p-p |
|---|---:|---:|
| orbital | 0.644549 m | **1.651111 m** |
| time-reversed geometry | 36,208.045878 m | 36,208.777701 m |
| prefix-affine only | 27,445.220832 m | 103,857.524914 m |

The closest alternative is the time-reversed geometry family. The orbital
preference margin is `36,207.126590 m`, or `9.134 B`, where the prospectively
frozen one-model guard is `B = 3,964.157667 m`. The orbital held-out residual
is also below the absolute positive bound. No held-out refit or free time phase
was used.

## Claim boundary

This event authorizes the narrow claim that, for this labelled DRAO station,
date, six-PRN codebook and held-out interval, the frozen orbital geometry
predicts the admitted continuous-phase coordinate better than both frozen
non-orbital/geometry-destroying alternatives.

It does not independently establish satellite identity: the PRN labels and
broadcast navigation products condition the model. It is a single receiver
root, not distributed confirmation, and it is not orbit determination, anomaly
detection or a general statement about GNSS receivers.

The requested stopping condition has been reached: one physical DRAO
labelled-forward event occurred and produced one immutable outcome.
