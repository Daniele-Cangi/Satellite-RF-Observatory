# GPS wide-lane DD calibration and validation with known integers

Exploratory reference-only study, 12 November 2026. The [previous
study](../wide-lane-uncertainty-2026-11-12/RESULTS.md) showed that a free
constant bias and the wide-lane integer cannot be separated from MW alone.
This study measures one physical contribution separately and exercises the
absolute calibration procedure on generated data with known integers.

## Real code contribution at zero baseline

[Borio, Susi and Węzka](https://doi.org/10.5281/zenodo.15118153) recorded two
Septentrio PolaRx5S receivers using one antenna through a splitter on
2024-03-08. Use WUT000POL minus WUT100POL, then the lower minus the higher GPS
PRN. The code term is the signed C1C/C2W contribution to the MW combination
in wide-lane cycles. Form receiver differences on matched GPST epochs before
applying the two code weights, then difference the satellites. This removes
common range, propagation and separable receiver delay in the common-antenna
model. The remaining code term includes differential receiver/signal effects,
measurement noise and any residual timing mismatch. No phase values, phase
lock flags or fitted integers enter this statistic.

Use the first five minutes at 00:00 and 12:00 GPST. The public hourly members
are large, so only their prefixes were transferred via byte ranges before
analysis. The first five minutes at each hour were selected before looking at
the code values. Archive-wide checksums were not verified for the partial
transfers. The retained window hashes identify the bytes that were processed.
Use the 30 s grid of the previous study and all 465 distinct pairs of eligible
GPS PRNs (G01–G32 excluding G12) at each window, with lower PRN first.
Each reported mean requires all ten epochs and both code fields at all four
endpoints. No partial block is scored and every missing pair is counted.

| Start GPST | Complete | Partial | Missing | Median / 95th percentile / max of absolute block means (cycles) | Above 0.10 cycles |
|---|---:|---:|---:|---:|---:|
| 00:00 | 36 | 9 | 420 | 0.049 / 0.132 / 0.158 | 4 |
| 12:00 | 45 | 0 | 420 | 0.239 / 0.559 / 0.618 | 38 |

The largest absolute code term, 0.618 cycles (0.533 m in the MW combination),
was G11–G26 at 12:00. Six pairs have a full block in both windows. Their
absolute between-window changes have median 0.284 and maximum 0.568 cycles.
These are descriptive counts with shared receivers, epochs and satellites.
The common-antenna configuration does not measure field multipath or the
carrier contribution. The measured code term can be compensated or reinforced
by phase effects. It therefore supplies neither a lower nor an upper bound on
the total absolute bias, and it cannot be transferred to the #245 network.

## Independent calibration and validation of the integer decision

For an admitted calibration arc with independently known DD integer N,
a mean z and simultaneous error halfwidth h imply b in
[z − N − h, z − N + h]. Intersect these intervals only for anchors sharing a
constant bias and jointly valid error bounds. Apply that interval to a
separate arc only with an independently justified bound on how much b may
change. A missing anchor, contradictory calibration, or unknown transfer
leaves the decision unbounded. Fix only when the resulting interval supports
one integer. Retain empty sets, multiple sets and every wrong fix.

The forward exercise generates C1C/C2W code and L1C/L2W phase from range,
dispersive ionosphere and independent, signed per-link integer counts. A
nonseparable delay on one endpoint creates a known DD bias. Calibration and
validation use disjoint generated arcs and random streams. Truth comes from
the generator's integer counts. The scorer receives held truth after the
prediction file is written. Noise halfwidths and transfer bounds are design
inputs in this exercise. No orbit or target data is read.

| Scenario | Calibrated result (64 cases each) | Wrong fixes if bias is set to zero |
|---|---|---:|
| Stable, true bias moves from 0.95 to 0.98 cycles | 64 correct | 63 |
| Broad transfer envelope | 64 multiple | 63 |
| Unknown transfer | 64 unbounded | 63 |
| Drift outside the declared envelope | 64 wrong | 62 |
| Contradictory anchors | 64 unbounded | 61 |
| No anchor | 64 unbounded | 61 |

The stable calibration interval was [0.9323, 0.9658] cycles. The deliberately
misspecified drift shifts the held bias to 1.98 cycles and gives plausible but
wrong singletons. These scenarios validate the implementation and expose the
transfer failure mode. Their counts do not estimate a real-world error rate.

## Physical input still required

The zero-baseline archive provides RINEX and navigation records. It does not
publish independent per-arc integer labels in the receiver convention.
A real anchor requires either independently logged integers from a
phase-coherent calibrated setup that preserves the receiver's phase origin,
or an equivalent external code-and-phase calibration with traceable bounds
in the same observable convention. A surveyed baseline or a simulated RF
position alone cannot label the receiver's initial carrier-cycle count.
[RINEX source documentation](https://doi.org/10.5281/zenodo.15118153)
[Carrier tracking and phase initialization](https://gnss-sdr.org/docs/sp-blocks/observables/)

The minimum next dataset is labelled C1C/C2W/L1C/L2W calibration and held
sessions on the same signal chain with independent arc labels, matched epoch
and DD sign conventions, plus a justified bound on transfer between sessions.
Qualifying another receiver/site geometry or the #245 network requires
evidence for that domain. Until then the real total DD bias, real wrong-fix
rate and narrow-lane ambiguity remain open. The orbit solver stays float.

## Reproduction

    python -m research.exploratory.known_wide_lane --output data/known-wide-lane-synthetic
    python -m research.exploratory.zero_baseline_dd_code --cache data/known-wide-lane-wut --output data/known-wide-lane-wut-results.json

The zero-baseline command accepts the two original receiver ZIPs from the
DOI (WUT000POL and WUT100POL) or their RINEX prefixes ending before the
respective 05:00 minute boundary within each hour. The [real
extract](zero-baseline-code.json.gz) records each prefix SHA-256, receiver
header identity, admitted code fields, per-pair results and missing totals.
To replay the statistic without fetching the original archives, reconstruct
each receiver index as {(sv, t): [p1, p2]} from its code_m rows and call
summarize with the recorded hour and the ordered indices.

[Predictions](synthetic-predictions.json.gz) and
[scores](synthetic-scores.json.gz) retain the controlled trials. For a new
source, pass --measurements and --truth as separate JSON files. Measurements
is a list of groups with id, transfer_bound_cycles (null if unqualified),
anchors and validation. Rows use id, mean_cycles and halfwidth_cycles.
Anchors additionally supply integer. Truth maps validation row IDs to
independent integer labels. Use unique observation IDs and keep source
provenance, phase-origin conventions and transfer justification with the
inputs. The CLI records the input digests and cannot establish their
scientific independence from filenames or IDs.
