# G22/G30 phase-duration sensitivity

The frozen broadcast-only calculation returned:

```text
PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE
```

This is a change-of-abstraction result, not measurement admission. It says
that the continuous-phase coordinate does not inherit the 153.5-minute
held-out suffix required by the earlier differentiated-frequency experiment.
It does not select a new qualification artifact, primary or reserve.

## Result

The shortest predeclared grid point, 60 held-out epochs (30 minutes), has a
strictly positive complete physical margin on all four eligible, unopened
dates. The observation-sized raw interval is 139 epochs, or 69 minutes of
elapsed time, with the 77-epoch calibration prefix unchanged.

| Held-out epochs | Budget | Positive dates | Worst positive margin | Maximum four-link guard |
| ---: | ---: | ---: | ---: | ---: |
| 60 | 30 min | 4/4 | 6,473.198 m | 39.466724 deg |
| 120 | 60 min | 4/4 | 95,553.476 m | 33.549061 deg |
| 180 | 90 min | 4/4 | 319,748.861 m | 27.699384 deg |
| 240 | 120 min | 4/4 | 536,789.235 m | 21.941941 deg |
| 307 | 153.5 min | 4/4 | 800,858.005 m | 15.616483 deg |

The shorter suffix trades absolute separation for a much stronger visibility
guard. At the controlling 30-minute case, the smallest separation is
8,857.432 m against a 2,384.234 m conservative pairwise envelope, leaving
6,473.198 m. This is positive by a factor of about 3.72 in separation over
envelope; it is not a detector SNR claim.

## Diagnostic date ranking

The frozen rule ranks guard first, then remaining physical margin, then date.
Every controlling null at the shortest duration is the real wrong-orbit G01
alternative, not the prefix-affine null.

| Rank | DOY | Raw GPS window | Four-link guard | Separation | Pairwise envelope | Margin |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 220 | 05:42:00--06:51:00 | 39.466724 deg | 8,857.432 m | 2,384.234 m | 6,473.198 m |
| 2 | 219 | 05:46:00--06:55:00 | 39.455847 deg | 8,986.714 m | 2,377.703 m | 6,609.011 m |
| 3 | 218 | 05:50:00--06:59:00 | 39.445654 deg | 9,110.438 m | 2,371.275 m | 6,739.163 m |
| 4 | 217 | 05:54:00--07:03:00 | 39.437345 deg | 9,234.260 m | 2,365.004 m | 6,869.256 m |

These rows are diagnostics only. DOY 220 remains unopened; its first rank does
not silently preserve its former primary role. A later role assignment must
use at least two distinct dates and freeze qualification before any distinct
primary is accessed.

## Causal boundary

- inputs: only the four exact-hash broadcast NAV products for DOY 217--220;
- excluded: DOY 216 as a candidate because its measurement topology was
  already observed;
- imported from the rejected structural run: only its exact terminal outcome
  hash, with no gap positions or coverage summaries used numerically;
- unchanged: G22/G30, GOLD/NLIB, 77-epoch prefix, affine and wrong-orbit nulls,
  direct plus/minus 15-second timing envelope, troposphere, quantization and
  the six conservative path families;
- observation access: zero products discovered or selected, zero headers,
  zero payload bytes and zero values.

The prior rejection therefore remains authoritative for its 386-epoch
topology. This result does not move a window around those observed gaps; it
shows, on four other dates and with a predeclared geometry-only rule, that the
phase observable requires a smaller physical support than the old coordinate.

## Remaining blocker

Before a final GNSS vertical can exist, a review must explicitly assign one
unopened date to independent structural/health qualification and a later
distinct date to primary, then bind the 139-epoch raw topology and same-path
witness rules before product discovery. Product existence, complete
L1C/L2W/LLI continuity, geometry-free health and C1C/C2W witness sufficiency
are still unknown. No primary may be opened until qualification passes.

## Frozen artifacts

- calculation source commit:
  `6da19a8404db1313e10c0bfc3209737d78013cd7`;
- source canonical SHA-256:
  `0fc20ae641ac6ea794667eb1922f5fdd9ad53620a83956b12bdadb5bef82945a`;
- manifest SHA-256:
  `2b14ba846b74bd84d509769b323f180a9d2bff51efda0f46778db5c69e43bf97`;
- receipt: `GNSS_PHASE_DURATION_SENSITIVITY_RECEIPT.json`, 190,211 bytes,
  SHA-256 `a81be2ddfb8d9455915118c74281f93dbf4919da3c140d58e18ebc4ccb4cee49`.
