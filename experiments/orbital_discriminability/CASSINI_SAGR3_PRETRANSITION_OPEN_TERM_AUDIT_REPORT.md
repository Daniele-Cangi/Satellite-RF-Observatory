# Cassini SAGR3 pre-transition physical-envelope audit

Date: 2026-08-21

Outcome: **CASSINI_OPEN_TERM_BOUND_UNAVAILABLE**

The pre-transition distributed geometry remains positive at
**0.07231370056321107 Hz** peak-to-peak, but no physical detector requirement
can yet be admitted. One term now has a quantitative uncertainty family; the
remaining unresolved terms still prevent a combined envelope. This audit used
only exact-hash SPICE kernels and outcome-independent calibration metadata. It
did not access an RSR header, payload, IQ sample, amplitude, or detector output.

## Physical question

After applying the same frozen calibration-prefix affine projection, can every
one of the seven inherited physical terms be bounded tightly enough that a
negative DSS-25 minus DSS-65 X-band result would be interpretable?

The answer is no. The common DSS-14 uplink and coherent Cassini source cancel
from the differential observable at a common transmit epoch. Receiver clock
rate, branch propagation, Earth media, interplanetary plasma, and independent
receiver-chain curvature do not cancel.

## Frozen inputs

- common Cassini transmit grid: 10,651 one-second records;
- calibration prefix: 3,360 records;
- untouched held-out suffix: 7,291 records;
- controlling Saturn-center separation: 0.07231370056321107 Hz;
- two-stream timing envelope: 0.000007482903185973555 Hz;
- no suffix refit;
- PREDICT SPK created before the pass;
- C10 and C60 ION/TRO products hashed before evaluation.

The calibration products are independent of the target RF outcome. This audit
uses three semantic states: `OBSERVABLE` for an independently measured
coordinate, `MODELED` for a frozen central model plus a quantitative uncertainty
family, and `UNRESOLVED` when neither is available. `UNRESOLVED` is never
silently replaced by zero. A one-sigma accuracy or a product FITSIG is not by
itself a temporal covariance model or a deterministic residual bound.

## Seven-term result

All metrics below are evaluated after the same prefix-only affine projection.

| Term | Epistemic class | Provenance | Central non-affine p-p | RMS | Uncertainty state |
|---|---|---|---:|---:|---|
| proper-time and gravitational frequency | MODELED | independent model/specification | 0.0005846983 Hz | 0.0003103464 Hz | bounded family: 0.0003046679 Hz p-p |
| relativistic propagation light time | UNRESOLVED | independent central model | 0.0000944727 Hz | 0.0000525132 Hz | UNAVAILABLE |
| Earth troposphere | UNRESOLVED | independent correction-only partial model | 0.0075399281 Hz | 0.0046749723 Hz | UNAVAILABLE |
| Earth ionosphere | UNRESOLVED | independent complete central model | 0.0003817801 Hz | 0.0002016459 Hz | UNAVAILABLE |
| interplanetary plasma | UNRESOLVED | unknown | — | — | UNAVAILABLE |
| station hardware delay/frequency curvature | UNRESOLVED | unknown | — | — | UNAVAILABLE |
| available media calibration | control only | independent, non-additive partial control | 0.0079217083 Hz | 0.0048746428 Hz | not an additive bound |

### Scientific correction: proper time and gravity

The previous `0.1927967948 Hz` diagnostic double-counted endpoint kinetic time
dilation. The one-way relativistic transfer already contains the exact
special-relativistic gamma ratio; adding another
`(v_station² - v_spacecraft²)/(2c²)` endpoint term was incorrect. The corrected
central term is therefore potential-only after the exact gamma transfer and is
`0.0005846983090055662 Hz` peak-to-peak (`0.00031034635243532395 Hz` RMS).

The central value is not its uncertainty. For the receiver proper-time model
scope, the IERS omission bound of `1e-15` fractional frequency per receiver was
combined conservatively to `2e-15` differential and propagated through the
exact frozen prefix-affine operator. Its worst-case gain is
`9.040589085582225`, producing an admitted `0.000304667852184121 Hz`
peak-to-peak family. This does not cover receiver hardware or branch
propagation; those remain separate terms.

### Troposphere remains unresolved

The TRO archive contains simultaneous C10 and C60 normalized-polynomial
corrections. The DSN Services Catalog gives a candidate `1 cm` one-sigma zenith
wet-plus-dry delay accuracy, but that scalar does not specify the temporal
covariance or delay-rate structure needed to bound a frequency residual after
the frozen affine projection. Historical applicability to both paths, mapping
uncertainty, and a complete DSS-65 central model also remain unproved. No
arbitrary conversion from delay sigma to hertz was made.

The ION models cover both receive grids, but their FITSIG values and statistical
accuracy are not hard residual bounds. No applicable independent finite family
was found for the differential interplanetary-plasma gradient or the nonlinear
difference between the DSS-25 and DSS-65 receiver chains.

## Conservative combination

One scoped term was admitted numerically, but the combination remains open:

- admitted proper-time/gravity uncertainty: 0.000304667852184121 Hz p-p;
- combined envelope state: **UNAVAILABLE**;
- remaining physical margin: **unknown**;
- maximum detector resolution: **not defined**;
- optimistic ceiling if every unresolved term were zero:
  0.024000516602613656 Hz, explicitly not an admission requirement.

Consequently, neither a detector nor IQ access is authorized. Treating an
unknown term as zero would convert a negative result into
**NOT_FALSIFIABLE_WITH_THIS_RECEIPT**.

## Exact blockers and change of abstraction

The remaining blockers are:

1. a relativistic-propagation uncertainty family;
2. a temporal tropospheric error model applicable to DSS-25 and DSS-65;
3. a DSS-65 dispersive-path observable or uncertainty family;
4. a finite differential interplanetary-plasma family;
5. a finite differential DSS-25/DSS-65 receiver-chain curvature family.

This bounded pass stops before the X/Ka witness review because the
non-dispersive tropospheric frequency family is still unresolved. The already
predeclared simultaneous DSS-25 X/Ka witness may later turn part of the plasma
term into an observable, but it cannot cancel proper-time/gravity or
troposphere. That review is not implemented here and authorizes no IQ access.

No new gate was created.

## Official sources

- [Cassini Radio Science User’s Guide](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/logs/Cassini%20Radio%20Science%20Users%20Guide%20-%2030%20Sep%202018.pdf)
- [IERS Conventions 2010, chapter 10](https://iers-conventions.obspm.fr/content/chapter10/tn36_c10.pdf)
- [DSN media-calibration interface](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/cors_0103/document/trk_2_23_000531.txt)
- [DSN Services Catalog, Rev. H](https://deepspace.jpl.nasa.gov/files/820-100-H.pdf)
- [SAGR3 ION product](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/sagr3_ancillary/ion/s23sagf2006_244_2006_273.ion)
- [SAGR3 TRO product](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/sagr3_ancillary/tro/s23sagf2006_244_2006_262.tro)
