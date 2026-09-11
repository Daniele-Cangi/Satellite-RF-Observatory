# Eleven-epoch support for a separately declared G12 event

The closed DOY250 attempt required 41 consecutive 30-second observations but
passed only the central eleven to estimation. The outer thirty contributed no
values to receiver calibration, target interpolation or uncertainty. They were
a structural lead-in/out condition, not an estimated elevation or noise bound.

The next attempt uses eleven consecutive observations, spanning 300 seconds,
and their central event. The cubic estimator uses the four nearest emitted-code
tags and the quintic control uses six. Seven samples are the smallest odd array
that can contain both centered stencils for small interreceiver tag differences;
eleven retain two additional epochs at each edge. This is a support argument,
not a proof that all real observations will qualify.

Calibration estimates the non-target reference clock independently at each
epoch. It does not average over the discarded outer ten minutes or require a
long-term target orbit/clock model. Using the same eleven observations leaves
the numerical calibration and uncertainty calculations unchanged.

`support_design.py` checks eighteen invented range curves with different
speeds, curvatures and sinusoidal terms. For the same central event, seven,
eleven and forty-one samples give cubic values equal within 1 micrometre.
The synthetic curves are noiseless and are not GPS ephemerides. Their small
interpolation errors do not justify reducing the real-data noise/bias floors,
prove a worst-case interpolation bound or establish position accuracy.

Real admission still requires monotonically bracketing emitted tags; both
interpolation stencils must bracket, and their difference must be <=2 m.
Independent reference calibration must pass its existing checks at all eleven
epochs. The inferred target must meet the existing 5-degree elevation and
identifiability checks. All uncertainty and confirmation limits are unchanged.

Target G12 and the same seven fit stations plus excluded GOLD are retained.
2026-09-05 (DOY248) is the most recent completed GPST calendar day not yet
examined in this inverse series: DOY249 and DOY250 were already used, while
DOY251 is still ongoing at planning time. No DOY248 observation or G12 orbit was
examined to choose this day. This is one new bounded attempt, not a reopening
of DOY250 or a search through multiple windows until one passes.

The plan and implementation are committed and pushed before acquisition.
Each executed stage retains its source bytes in addition to hashes. Failure
closes this target/day/network attempt without substitution.
