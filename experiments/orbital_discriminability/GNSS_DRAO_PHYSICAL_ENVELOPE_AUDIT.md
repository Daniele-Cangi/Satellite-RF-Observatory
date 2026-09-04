# DRAO physical-envelope audit

**DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED**

This audit used only the frozen prospective plan and historical model-only bound provenance. No DRAO product was selected or accessed and no orbital score was produced.

## Common-mode topology

For each six-track hypothesis, `c_i = e_i - mean_j(e_j)`. After the same prefix affine projection, `pp(c_i) <= pp(e_i) + mean_j(pp(e_j))`; a uniform per-track p-p bound therefore has gain at most two. A purely epoch-common receiver-clock term cancels exactly, but track-, signal- or channel-dependent implementation terms do not.

## Term attribution

| Term | State | active common-mode bound | Basis or refusal |
|---|---|---:|---|
| EVENT_TIME_DIRECT_TRAJECTORY_ENVELOPE | UNRESOLVED | UNAVAILABLE | THE COMMITTED DRAO RECEIPT RETAINS DIRECT TIME SHIFTED VISIBILITY BUT NOT THE SIX NOMINAL AND T PLUS MINUS 15 S RANGE CURVES AFTER PREFIX AFFINE PROJECTION |
| BROADCAST_ORBIT_AND_CLOCK | UNRESOLVED | UNAVAILABLE | DOY231 SV ACCURACY AND CLOCK REMAINDER FIELDS WERE NOT RETAINED; DOY221 AMC VALUES DO NOT ESTABLISH A DRAO BOUND |
| DIFFERENTIAL_TROPOSPHERE | MODELED_CONSERVATIVE_INTERVAL | 18.125149615 m | ONE OVER SINE THEN SIX TRACK CENTERING |
| IONOSPHERE_FREE_AND_HIGHER_ORDER_REMAINDER | UNRESOLVED | UNAVAILABLE | THE HIGHER ORDER INTERVAL IS TRANSFERABLE ONLY AFTER THE UNSELECTED PRODUCT PROVES EXACT L1C L2W SIGNAL AND SCALE SEMANTICS |
| ANTENNA_PCV_AND_PHASE_WINDUP | UNRESOLVED | UNAVAILABLE | THE STATION LOG IDENTIFIES THE ANTENNA BUT THE FROZEN AUTHORITY DOES NOT BIND A DRAO PCV CALIBRATION OR PHASE WINDUP IMPLEMENTATION |
| MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE | UNRESOLVED | UNAVAILABLE | NINETY FIVE PERCENT CODE COVERAGE PERMITS UNBOUNDED PHASE ERROR AT SIX EPOCHS; NO INTERPOLATION OR GAP BRIDGING IS ALLOWED AND ONE UNBOUNDED EPOCH CAN DOMINATE PEAK TO PEAK |
| RECEIVER_CLOCK_AND_IMPLEMENTATION | PARTIAL_EXACT_CANCELLATION_REMAINDER_UNRESOLVED | UNAVAILABLE | AN ADDITIVE EPOCH COMMON CLOCK TERM CANCELS EXACTLY UNDER ENSEMBLE CENTERING; TRACK SIGNAL OR CHANNEL DEPENDENT IMPLEMENTATION ERROR DOES NOT AND HAS NO FROZEN BOUND |
| RINEX_QUANTIZATION | UNRESOLVED | UNAVAILABLE | NO DRAO ARTIFACT OR SERIALIZATION HAS BEEN SELECTED; THE F14 3 QUANTIZATION MODEL CANNOT BE ASSUMED PRE ARTIFACT |

## Decision

Only the conservative troposphere interval is active numerically (`18.125149615 m`). The aggregate is **UNAVAILABLE**, not zero or infinity encoded as a number. Seven terms remain unresolved, so it cannot be compared defensibly with the frozen `7339.701234647 m` guard.

The geometry remains positive and unchanged. The failure is physical-envelope closure before measurement admission, not a DRAO measurement failure and not evidence against the orbital hypothesis.

The frozen route therefore closes before locator selection. A future proof would need to retain the direct `t ± 15 s` projected range envelopes and require complete same-path witness coverage (or an independent all-epoch track-error bound) before its primary is frozen.

## Access boundary

DRAO locators, headers, payload bytes, observation values and orbital scores: **0**.
