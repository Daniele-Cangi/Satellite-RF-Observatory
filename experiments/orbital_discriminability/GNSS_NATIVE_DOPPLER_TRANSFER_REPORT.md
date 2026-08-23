# GNSS native-Doppler transfer and model-bound audit

## Outcome

`NATIVE_DOPPLER_TRANSFER_RULE_FROZEN_MODEL_BOUND_REQUIRED`

No observation header, artifact or numeric value was opened. This is a normal
offline hardening step inside the existing GNSS vertical, not a new gate.

## Physical question

Can the frozen DOY 214 measurement-path envelope and conservative path-delay
terms leave positive room for an independently justified G15/G22 broadcast
orbit error before a DOY 219 primary is opened?

New information produced: the exact same-path admission rule and the maximum
per-link broadcast-orbit path error that each shortlisted geometry can tolerate.
The earlier geometry receipt could not answer this because it preceded numeric
measurement development; the development receipt could not answer it because
G20/G22 residuals are not an independent G15/G22 model-error bound.

## Conservative physical transfer

Every per-link path interval is mapped into the native-Doppler coordinate with
four signed links and the two endpoints of the 60 s central difference. The
algebraic no-cancellation bound is doubled once for safety and then receives the
exact frozen prefix-affine peak-to-peak gain. The resulting coefficient is
`40.63775321596158 Hz` of held-out bound per metre of per-link path interval.

The fixed non-orbit terms include:

- troposphere: 3.5 m zenith divided by sine of the frozen minimum elevation;
- higher-order ionosphere: 0.5 m per link;
- antenna PCV and phase windup: 1 m;
- multipath and signal-specific hardware: 1 m calibration admission limit;
- station displacement, EOP and relativity remainder: 1 m;
- satellite-clock retarded-time remainder: 1 m.

The DOY 214 development-path envelope remains a separate `1.7027139799721753
Hz`; it is not relabelled as pure instrument precision.

| Role | DOY | Fixed non-orbit path | Maximum admissible broadcast-orbit path | Illustrative margin if 4 m were independently admitted |
|---|---:|---:|---:|---:|
| Primary candidate | 219 | 17.979250 m | 64.950176 m/link | 4953.756446 Hz |
| Reserve 1 | 220 | 17.986573 m | 64.939129 m/link | 4952.858565 Hz |
| Reserve 2 | 221 | 17.993410 m | 64.926217 m/link | 4951.809117 Hz |

The illustrative 4 m case is deliberately **not admitted**. The parent
navigation receipt retained complete product hashes but not the selected
G15/G22 `sv_accuracy_m` values or another outcome-independent per-link orbit
error bound. `UNRESOLVED` therefore does not become zero.

## Frozen same-path admission

Before held-out scoring, the future evaluator must require all 380 epochs and
all four links, finite `D1C/D2W/C1C/S1C/C2W/S2W`, positive code/SNR witnesses,
a prefix model-residual peak-to-peak no larger than `1.7027139799721753 Hz`, and
a prefix dispersive-network peak-to-peak no larger than
`0.2717166666666344 Hz`.

During held-out confirmation, the health witnesses may gate detectability but
may not fit either hypothesis. Every selected scalar must remain finite, there
may be no cadence gap, each link's SNR may not fall below its own calibration-
prefix minimum, and the dispersive-network witness must remain below the frozen
development value.

There is no invented absolute dB-Hz threshold. In particular, the observed
development minimum of 2.25 dB-Hz was not promoted to a threshold.

## Stop condition

The primary plan and observation authority remain false. The next smallest
physical step is a metadata/navigation-only proof that the exact G15/G22
broadcast orbit path bound is below the reported approximately 64.93--64.95 m
limit on the frozen header grid. If no outcome-independent bound is available,
this GNSS primary must remain blocked. No observation may be opened to estimate
that term.
