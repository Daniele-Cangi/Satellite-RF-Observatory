# Cassini SAGR3 pre-transition physical-envelope audit

Date: 2026-08-21

Outcome: **CASSINI_OPEN_TERM_BOUND_UNAVAILABLE**

The pre-transition distributed geometry remains positive at
**0.07231370056321107 Hz** peak-to-peak, but no physical detector requirement
can be admitted. This audit used only exact-hash SPICE kernels and
outcome-independent calibration metadata. It did not access an RSR header,
payload, IQ sample, amplitude, or detector output.

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

The calibration products are independent of the target RF outcome. The DSN
service documentation describes their accuracy statistically, including
one-sigma values. A one-sigma accuracy or a product FITSIG is not a
deterministic worst-case residual bound and was not promoted into one.

## Seven-term result

All metrics below are evaluated after the same prefix-only affine projection.

| Term | Provenance | Non-affine peak-to-peak | RMS | Bound state |
|---|---|---:|---:|---|
| proper-time and gravitational frequency | independent central model | 0.1927967948 Hz | 0.1025986202 Hz | UNAVAILABLE |
| relativistic propagation light time | independent central model | 0.0000944727 Hz | 0.0000525132 Hz | UNAVAILABLE |
| Earth troposphere | independent correction-only partial model | 0.0075399281 Hz | 0.0046749723 Hz | UNAVAILABLE |
| Earth ionosphere | independent complete central model | 0.0003817801 Hz | 0.0002016459 Hz | UNAVAILABLE |
| interplanetary plasma | unknown | — | — | UNAVAILABLE |
| station hardware delay/frequency curvature | unknown | — | — | UNAVAILABLE |
| available media calibration | independent, non-additive partial control | 0.0079217083 Hz | 0.0048746428 Hz | UNAVAILABLE |

The 0.1927967948 Hz proper-time/gravitational value is a central-model
contribution, not an error envelope. It is larger than the 0.0723137006 Hz
orbital-versus-null separation and therefore demonstrates that the physical
coordinate cannot be treated as a negligible correction. It does not prove
that the residual after a complete correction would dominate.

The TRO archive contains simultaneous C10 and C60 normalized-polynomial
corrections. The inspected frozen sources do not contain a complete public
DSCC60 seasonal baseline, a hard elevation-mapping error, or a deterministic
residual bound. The reported TRO number is therefore explicitly partial and
cannot reduce the envelope.

The ION models cover both receive grids. Their FITSIG values and the DSN
one-sigma calibration accuracy remain statistical descriptions, not hard
bounds. No applicable independent finite bound was found for the differential
interplanetary-plasma gradient or the nonlinear difference between the DSS-25
and DSS-65 receiver chains.

## Conservative combination

No term was admitted numerically:

- admitted open-term envelope: 0 Hz from zero admitted terms;
- combined envelope state: **UNAVAILABLE**;
- remaining physical margin: **unknown**;
- maximum detector resolution: **not defined**;
- optimistic zero-open-term ceiling: 0.024102072553341698 Hz, explicitly not
  an admission requirement.

Consequently, neither a detector nor IQ access is authorized. Treating an
unknown term as zero would convert a negative result into
**NOT_FALSIFIABLE_WITH_THIS_RECEIPT**.

## Exact blockers and change of abstraction

The remaining blockers are:

1. a finite differential interplanetary-plasma bound;
2. a finite differential DSS-25/DSS-65 receiver-chain curvature bound;
3. a complete tropospheric model with a hard residual bound.

Repeating another absolute-link documentation search is unlikely to change the
physical result. The smallest next physical review is whether the already
predeclared simultaneous DSS-25 X/Ka witness can change the observable so that
dispersive plasma becomes measured rather than assumed, while keeping
band-specific hardware explicit. That review is not implemented here and
authorizes no IQ access.

No new gate was created.

## Official sources

- [Cassini Radio Science User’s Guide](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/logs/Cassini%20Radio%20Science%20Users%20Guide%20-%2030%20Sep%202018.pdf)
- [DSN media-calibration interface](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/cors_0103/document/trk_2_23_000531.txt)
- [DSN service calibration accuracies](https://deepspace.jpl.nasa.gov/files/820-100-F1.pdf)
- [SAGR3 ION product](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/sagr3_ancillary/ion/s23sagf2006_244_2006_273.ion)
- [SAGR3 TRO product](https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/sagr3_ancillary/tro/s23sagf2006_244_2006_262.tro)
