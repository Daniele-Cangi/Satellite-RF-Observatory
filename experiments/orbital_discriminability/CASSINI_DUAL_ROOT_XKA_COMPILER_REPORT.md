# Cassini 2005 dual-root X/Ka exact compiler outcome

## Outcome

`CASSINI_DUAL_ROOT_PHYSICAL_ENVELOPE_UNAVAILABLE`

The exact four-stream metadata coordinate is valid and the geometric
Cassini-versus-frozen-null separation remains positive. The physical envelope
is not closed, so this outcome does **not** authorize IQ access, a detector,
a plasma measurement, or an orbital RF claim.

## Frozen authority

- pre-access compiler commit:
  `a7ddd39062e8ebe79e47eed607d53b4fe94c644a`
- compiler manifest SHA-256:
  `b4c103d40e9a43d5704f4a63e1e59b78c6e3117886fec8ae92c87ece1c4f3823`
- canonical compiler source SHA-256:
  `ea3f3ee640a579c85a70dc9c9388ada34d6f9f1ee1f08569e8d6c3ec3c021508`
- outcome receipt SHA-256:
  `942549a05d37d0926af9a5d65b7891c4c998134a9eb2254c28406982134ec1f8`

The frozen parents and all four SPICE kernels were hash-verified. SpiceyPy
7.0.0 was used. No parameter, null, time phase, product, or window changed
after the compiler freeze.

## Access boundary

The single authorized re-read requested 21,120 disjoint 260-byte control
headers: 5,491,200 bytes total.

- data CHDO requested/read: `0 / 0 bytes`
- IQ accessed: `0 bytes`
- amplitude or signal diagnostics represented: `false`
- raw headers persisted: `false`
- derived per-record coordinates persisted: `false`

Only hashes and aggregate metrics survive. Each transient header buffer was
zeroed after whitelist parsing.

## Exact common coordinate

The four native streams contain 5,280 continuous one-second control records
each. Mapping both roots onto one common Cassini transmit coordinate produces:

| field | value |
|---|---:|
| common records | 5,279 |
| calibration prefix | 1,056 |
| held-out suffix | 4,223 |
| first transmit UTC | 2005-06-08T17:54:57.678910Z |
| last transmit UTC | 2005-06-08T19:22:55.678912Z |
| joint visibility | true |

The frozen future transform is:

```text
model-blind baseband ridge
+ RF-to-IF + DDC - exact per-record NCO
-> sky-frequency coordinate
-> common Cassini transmit epoch
-> fractional X/Ka composite independently at DSS-25 and DSS-55
-> DSS-25 minus DSS-55, scaled by 8.425 GHz
-> one prefix-only affine projection
-> untouched held-out comparison
```

NCO is receiver steering. It is not evidence that a physical carrier occupied
that coordinate.

## Receiver-coordinate result

| stream | tuning minimum | tuning maximum | derived artifact SHA-256 |
|---|---:|---:|---|
| DSS-25 X | 8,426,636,501.428985 Hz | 8,426,667,574.009580 Hz | `e2fe6cbc03432dbafe8726692aa503a116f78b7ef443ff07a66edb132ad3e1eb` |
| DSS-25 Ka | 32,021,218,713.460598 Hz | 32,021,336,789.248554 Hz | `819ea1d55a1d687ab2f1830842c560603fd45901ffb6714e4183629d4ee51d3c` |
| DSS-55 X | 8,426,620,734.465706 Hz | 8,426,653,989.083331 Hz | `d556d164637c862ab276f838da942753c26c7514fd98b386c51b2cda3e4aaa8b` |
| DSS-55 Ka | 32,021,158,798.974907 Hz | 32,021,285,166.523605 Hz | `1bec7069d3eee69dca619f2209923f87febe45b785d1a9e3e04a2c7dc792ee8a` |

The weights are stable but are not probabilities:

| branch | weight range |
|---|---:|
| DSS-25 X | -0.0744047618650323 to -0.0744047618642167 |
| DSS-25 Ka | 1.0744047618642167 to 1.0744047618650323 |
| DSS-55 X | -0.0744047618650850 to -0.0744047618642438 |
| DSS-55 Ka | 1.0744047618642438 to 1.0744047618650850 |

They sum to one at each root and cancel the ideal first-order `p/f^2` term.
The maximum numerical coefficient residual is
`3.76158192263132e-37 Hz^-2`. This proves algebra and conditioning only.
First-order plasma remains `NOT_EVALUATED_WITHOUT_IQ`.

## Exact discriminability

| same prefix affine | held-out p-p | held-out RMS |
|---|---:|---:|
| orbital versus affine | 894.288354116472 Hz | 429.832309442975 Hz |
| orbital versus Saturn-center null | 0.299592373563 Hz | 0.145497570140 Hz |

The Saturn-center null remains controlling. Relative to the earlier
five-second screen (`0.299172348843 Hz`), the exact value increases by
`0.000420024720 Hz` (`0.1404%`). The discriminating region survives the exact
coordinate; it was not a five-second-grid artifact.

The conservative four-stream timing envelope is
`0.0000204165223073 Hz`, derived from direct trajectories at
`t +/- 1 microsecond` and absolute X/Ka weights. No unproved same-station
clock-error cancellation was assumed.

## Physical-envelope attribution

The state is a non-probabilistic causal envelope. Bounded families would
combine by conservative correlated interval/Minkowski sum. No root-sum-square,
invented likelihood, or probability amplitude is used.

| existing term | state | why it still blocks |
|---|---|---|
| receiver proper-time/gravity differential | `MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED` | X/Ka does not cancel receiver-rate differential; central value is not uncertainty |
| relativistic propagation remainder | `MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED` | moving-body and higher-order residual family is not frozen |
| differential troposphere | `PARTIAL_MODEL_UNRESOLVED` | applicable C10/C60 TRO has no complete slant model plus deterministic residual bound |
| Earth ionosphere | `FIRST_ORDER_NOT_EVALUATED_WITHOUT_IQ_HIGHER_ORDER_UNRESOLVED` | the coordinate can cancel first order later; higher order remains |
| interplanetary plasma | `FIRST_ORDER_NOT_EVALUATED_WITHOUT_IQ_HIGHER_ORDER_UNRESOLVED` | the coordinate can cancel first order later; scintillation/higher order remains |
| station/receiver hardware | `UNRESOLVED` | cross-band/root reference, cable, FIR and group-delay curvature is unbounded |
| available media calibration | `PARTIAL_CALIBRATION_UNRESOLVED` | coverage exists, but FITSIG is not a deterministic bound |

The official ION product `s11sroc2005_152_2005_181` and TRO product
`s11sroc2005_152_2005_184` cover the window. Their presence upgrades missing
calibration to applicable partial calibration; it does not close uncertainty.

Separate inherited controls remain open: PREDICT-SPK orbit uncertainty, X/Ka
group-delay alignment on a common retarded-time coordinate, frequency-reference
stability, and future detector resolution/SNR. They are not silently folded
into the seven-term sum.

## Interpretation and stop

New physical information was produced:

1. both hardware roots support the same exact X/Ka algebra;
2. the first-order dispersive coordinate is numerically well conditioned;
3. controlling orbital-versus-null curvature survives the exact grid;
4. timing is negligible relative to geometry under the frozen bound.

No RF observable was produced. Steering cannot witness carrier, plasma or
orbit. Because all seven terms lack an admitted hard envelope, `UNRESOLVED`
remains distinct from zero and detector resolution remains undefined.

Stop before IQ and detector development. The smallest useful continuation is
outcome-independent closure of nondispersive and cross-band/cross-root
uncertainty families, retaining this coordinate and these nulls. If they cannot
be bounded below `0.299592373563 Hz p-p`, close this 2005 vertical without IQ.

## Official sources

- [Cassini Radio Science User's Guide](https://pds.nasa.gov/data/pds4/misc/document_cassini/Cassini_Radio_Science_Users_Guide_30Sep2018.pdf)
- [Cassini RSS current PDS archive](https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/inst-rss_curr.html)
- [SROC archive catalog](https://atmos.nmsu.edu/data_and_services/atmospheres_data/catalog.htm)
