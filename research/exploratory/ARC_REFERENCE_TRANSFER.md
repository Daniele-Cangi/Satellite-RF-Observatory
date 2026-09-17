# Second reference arc and correction transfer — 2026-09-17

The fixed second G14 reference arc is **05:00–06:00 GPST on September 3, 2026**,
with the same seven stations, 21-reference allowlist, 30-second spacing and
10-degree mask. All **847 station/epoch calibrations** qualify. Out of **7913**
admitted paths, **7114** are evaluated and **799** are explicitly below the mask.
This denominator remains conditional on the allowlist and C1C/C2W availability.
Target G14 code and state are excluded. GOLD is not acquired or used.

## Fixed comparisons

The four candidates are unchanged. Local training uses 05:00–05:29:30 (60 epochs,
3668 paths). Transferred training reuses only 03:30–03:59:30 (3777 paths) from the
previous pinned report. Both predict exactly the same **3446 contrasts** at
05:30–06:00 (61 epochs). The transferred coefficients reproduce the previous
coefficients exactly; no observations from the new arc update them.

| Training | Model | Predicted / test paths | RMS on supported paths, m | Zero RMS on same support, m |
|---|---|---:|---:|---:|
| 05:00–05:30 | zero | 3446/3446 | 1.046946 | 1.046946 |
| 05:00–05:30 | shared_satellite | 3446/3446 | 1.003486 | 1.046946 |
| 05:00–05:30 | station_direction | 3446/3446 | 1.029490 | 1.046946 |
| 05:00–05:30 | station_satellite | 2353/3446 | 0.978089 | 1.015405 |
| 03:30–04:00 | zero | 3446/3446 | 1.046946 | 1.046946 |
| 03:30–04:00 | shared_satellite | 3446/3446 | 1.015071 | 1.046946 |
| 03:30–04:00 | station_direction | 3446/3446 | 1.074562 | 1.046946 |
| 03:30–04:00 | station_satellite | 0/3446 | — | — |

Local shared-satellite offsets reduce test RMS **1.046946 → 1.003486 m (4.15%)**,
with all seven stations improving. The earlier arc showed a 3.67% gain; this
second disjoint arc repeats the direction of the effect, not a general accuracy
guarantee. Transferred shared-satellite offsets give **1.015071 m (3.04% gain)**:
five stations improve; DRAO and PIE1 worsen slightly (about 0.08 mm and 1.03 mm RMS).

Local directional fitting improves 1.67%, but transferring the earlier directional
coefficients **worsens RMS by 2.64%**, with all seven stations worse. This provides
a concrete limit on interpreting fitted directional response as a stable station
correction over changing geometry. It does not identify its physical cause.

Local station/satellite offsets leave **1093** paths unsupported. Transferred
station/satellite offsets leave **all 3446** test paths unsupported: every complete
station/epoch contrast block contains at least one unseen training feature. This
does not mean every individual link is new. No fallback, substituted model or
selective subset score fills those failures. The all-test RMS stays null whenever
coverage is incomplete, and both RMS scores are null for the zero-support case.

## Shared-satellite station scores

| Station | Zero RMS, m | Local RMS, m | Transferred RMS, m |
|---|---:|---:|---:|
| ALGO00CAN | 1.021113 | 0.975293 | 0.986863 |
| BOGT00COL | 1.134312 | 1.070383 | 1.059299 |
| DRAO00CAN | 1.433694 | 1.417777 | 1.433771 |
| MKEA00USA | 0.870075 | 0.785997 | 0.784858 |
| PIE100USA | 0.834664 | 0.802420 | 0.835691 |
| STJO00CAN | 0.661942 | 0.610906 | 0.620776 |
| YELL00CAN | 1.089312 | 1.048510 | 1.073192 |

## Scope and interpretation

These are clock-free within-station/epoch contrasts. Receiver clocks are still
recalibrated at test epochs, and retrospective precise reference geometry is
supplied. The study does not predict absolute future RF, target position or
future receiver clocks. Reference products may reuse the same station data.
Both arcs use the **same day and upstream daily products**; this is not an
independent-day test, unexposed confirmation or identification of satellite error.
No covariance qualification, uncertainty-floor change or production promotion.
Whole-hour residual RMS remains 1.045452 m; most residual variation is unexplained.

## Provenance and replay

- `b611bdb`: plan and producer frozen before extracting this arc.
- `08792b9`: restricted input artifacts and analysis frozen before execution.
- Input receipt SHA-256: `03ba35e0b1c17458754654554a360933726b0a43103aef682ff74b918c4583fd`.
- Report SHA-256: `0068da07dbc9d5ed6841d0ebf2a297cfd9879151e03bd83ca60dfed358ed8920`.

The daily raw observations and CODE source files were already downloaded for
previous exposed work. Their historical hashes are checked before extraction;
no fresh observation download is claimed. Only the declared later arc is used.
The same station coordinate/DE440s/HARDISP/2018-pole recipe is recalculated over
the full new hour; the complete VMF3 model stays fixed. The input receipt records
auxiliary bias, antenna, frame and loading provenance explicitly and replay
revalidates it. Only the previously recorded nine CRLF/LF variants are accepted.

```powershell
python -m research.exploratory.arc_reference NEW_REPORT.json
python -m pytest research/exploratory/tests/test_arc_reference.py -q
```

Tests cover fixed cohorts, exclusion of target code/state, no use of future
values in fitting, no use of new training values for transferred coefficients,
failure suppression of both comparisons, Git/source/input provenance and complete
numerical replay. All eight predictions retain the identical test cohort.

## Next step

Keep all four candidates and repeat on a distinct day before adopting a correction.
Retain the failed transfer results; do not generalize the directional fit or
replace missing station/satellite predictions after seeing their score. Separately
check sensitivity to upstream reference products to distinguish product-linked
common residuals from persistent RF behavior. S2 remains open; the website and
new confirmatory campaign remain separate work.
