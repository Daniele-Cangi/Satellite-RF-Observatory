# Wet shape versus reference APC geometry and stable IF biases

This is an exploratory extension on the already exposed reference archive.
It asks whether the six station wet coefficients in
[the preceding source study](REFERENCE_SOURCE_GEOMETRY.md) remain distinguishable
when admitted non-target reference geometries and stable link biases compete
for the same observations. It does not admit target products or infer a new
physical raw-error covariance from residuals.

## Declared source model

Four nested models are evaluated without selecting one from held scores:
station wet; wet plus stable IF code bias; wet plus reference RTN displacement
and bias; and wet plus RTN displacement, body-frame IF antenna offset and bias.
All parameters are constant over each fold's training interval. The existing
free epoch receiver/reference clocks, continuous-segment phase ambiguities and
MW float biases remain unpenalized and are profiled before source fitting.
The epoch-wise zero-mean reference-clock datum remains a numerical convention,
not independent timing information.
A stable IF phase level is already contained in those phase ambiguities.

The RTN columns use the admitted reference COM at emission. The radial axis
is `r / |r|`; the normal follows `r cross (v_ECEF + Omega cross r)` and the
transverse axis completes the orthonormal frame. The antenna columns use the
admitted body-to-ECEF attitude at that same emission. Both act as a displacement
of the emitted antenna phase centre (APC), and both rotate by the existing
Sagnac convention to reception ECEF before projection into the ray. The ray
Jacobian includes the VMF3 elevation derivative. Coordinates are metres;
positive coefficients increase the modeled path according to that Jacobian.
Wet columns are the admitted positive wet mapping per station; the stable
bias columns affect retained IF code only. MW remains zero in these source
columns, with its existing free segment levels still profiled. This is a
retained-combination mean model: a constant hardware contribution in MW can
be absorbed by its existing float level. It does not identify the four raw
channel hardware errors separately.

The use of an emitted APC and a body-frame offset follows the measurement
and antenna conventions described by ESA Navipedia:
[GNSS observables](https://gssc.esa.int/navipedia/index.php/GNSS_Basic_Observables)
and [satellite APC](https://gssc.esa.int/navipedia/index.php/Satellite_Antenna_Phase_Centre).
This implementation deliberately tests **fixed-emission APC displacement
shapes**. It does not perturb a complete ephemeris, recompute relativistic
clock corrections or emission time under an orbit perturbation, model antenna
PCV, or supply a stochastic orbit/antenna error law. Source-shape attribution
under this restricted law is narrower than identifying real product errors.

## Joint rank, prediction and state transfer

Let `A` contain epoch clocks, `B` the global phase/MW floats, `G` the declared
source columns and `W` the existing historical whitening metric. Profiling
`A` and `B` gives `J = (I - U_B U_B^T) W (I - A K) G`. The SVD resolves singular
values against `1e-10` times the original weighted source scale, before the
clock/bias projection. No external anchor, ridge, residual rescaling or
positivity clipping completes a source null direction. All source coordinates
are metres; the Euclidean coordinate metric is declared, not a physical prior.

The retained minimum-norm coefficient vector represents only the fitted
projection. Its null coordinates are unassigned. Wet coefficients and fixed-weight
parameter precision are reported separately only when the wet design remains
full rank after projecting the competing source columns. Negative total wet
values remain domain failures rather than being clipped or used as corrections.

Held links use the unchanged hash selection and last-third exclusion. Their
IF/GF values are removed before new segmentation and every clock, float and
source fit. Upstream timing, masks and nominal geometry still condition the
analysis, and contemporaneous RF from other links remains available.
For a held observation, the complete source response `H` includes its direct
source path **and the compensating refits of clocks and prefix phase floats**.
A code/phase pair is issued only when both rows annihilate the source null
space to relative `1e-8`. This joint output also requires a training-prefix
phase level; a missing phase prefix is not relabeled as a missing code clock. Unseen source coordinates, missing clocks, missing
prefix phase levels and ambiguous predictions remain separate terminals.
The scalar SVD representative alone is never sufficient to issue a prediction.

Fresh cold-start nominal RF trajectories supply local state derivatives.
A positive source model correction changes the candidate state through
`T_ref = -L_clock K_reference G` and through `T_candidate = -L G_candidate`.
The latter has nonzero columns only for the station wet field shared by both
paths. Reference-product displacement and reference-link biases are declared
reference-specific; no unknown target product is imported as a prior.
The null image `(T_ref + T_candidate) N` tests whether source descriptions unresolved at that declared numerical tolerance nevertheless produce different local candidate states.
A retained null probe has **1 cm total Euclidean source-coordinate norm**;
it is neither per-link RMS nor source sigma. Its reference check refits the
fixed-geometry linear network; it does not claim full observation-time or
trajectory relinearization. No representative source correction is applied
to a candidate trajectory. All source/nominal RF predictions precede dedicated
reference and RF/MW scoring. There is no new CODE state score.

## Execution and retained results

The numerical producer is `3e31526237c8047982e6630852fd457e299c0673`,
created after 68 focused tests passed (112.12 s), including historical receipts
and checkout provenance. The unchanged runner command is:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ../py313/bin/python -m research.exploratory.reference_network_clocks --separate research/exploratory/results/reference_source_separation_v1.json.gz
```

There was one full execution, with unchanged numerical code through its
completion. The retained gzip is
[`results/reference_source_separation_v1.json.gz`](results/reference_source_separation_v1.json.gz),
15,345,824 bytes, SHA256
`a8caee27bbb751090ce4af25d384bc23bad8111e2d94fe76754834f937821467`.
Its input/source hashes, fitted source spaces, every prediction terminal,
local state maps and fixed-geometry reference checks are retained. The receipt
replays full-source profiles, null projectors, state maps, prediction support
and held scores against producer bytes in Git: 1 test passed in 56.82 s.
Together with the producer regression, 69 focused tests are verified.

All 22 original candidates, 440 windows and 63 prepared arcs remain. There
are 17 `INSUFFICIENT_PREPARED_ARCS` and five `BRANCH_SEARCH_INCOMPLETE` RF
trajectories (G05/G11/G19/G20/G21), with their failed interior initializations
preserved. No failed root is relabeled as a second physical orbit or a global
uniqueness result. The five folds share many reference observations and are
not independent replications. Their reference rows total 25,117 occurrences.
There are no source-preparation failures in the five supported folds.

## Separation loses precision even though wet rank stays six

Every model in every supported fold retains wet conditional rank 6/6 at
the stated numerical resolution. The resulting **fixed-weight marginal
parameter standard deviations**, in millimetres of zenith delay, are:

| Fold | Wet only | + stable IF bias | + RTN and bias | + RTN, antenna and bias |
| --- | ---: | ---: | ---: | ---: |
| G05 | 1.694–4.653 | 1.862–5.000 | 7.770–37.984 | 15.227–150.033 |
| G11 | 1.635–4.695 | 1.783–5.130 | 7.593–34.148 | 14.493–165.770 |
| G19 | 5.289–19.050 | 5.954–21.104 | 63.466–491.994 | 318.841–3268.903 |
| G20 | 1.853–4.735 | 2.400–5.245 | 8.245–37.575 | 14.244–140.150 |
| G21 | 1.958–6.359 | 2.379–6.812 | 11.408–81.586 | 25.273–309.074 |

The greatest station-wise inflation relative to wet-only is 32.245, 35.306,
227.330, 29.598 and 62.818 respectively. This is parameter precision under the
historical independent raw-link/epoch weighting scenario. Temporal/shared
noise and systematic model errors remain unqualified. It is not weather
process covariance, measured source accuracy or a total orbit uncertainty.

The full conditional wet estimates, in station order
ALGO/AREQ/BOGT/BRAZ/DRAO/STJO, are:

| Fold | Conditional zenith residuals (mm) | Minimum sampled total wet (m) |
| --- | --- | ---: |
| G05 | −28.420, −15.936, 221.167, 3.691, 35.784, −24.998 | .072511 |
| G11 | −32.794, −5.817, 194.750, 42.171, −24.669, −17.481 | .082630 |
| G19 | 42.583, −81.966, −1601.507, 577.118, −16.746, −182.657 | **−1.486787** |
| G20 | −32.849, −16.232, −11.854, −1.342, 9.830, −24.712 | .072215 |
| G21 | −8.668, 85.438, 461.399, 51.330, 4.236, −11.744 | .113663 |

G19 fails the nonnegative-total-wet domain in both the full training profile
and the excluded-link training profile (minimum −.884517 m in the latter).
The other four full and excluded-link training profiles retain positive
sampled totals. That does not make their source attribution physical.
Negative residual corrections alone are allowed; the domain failure is a
negative **total** delay. No negative value is clipped or applied to a candidate.

There is a second, more severe qualification failure. Minimum-norm algebraic
representatives exploit extremely weak source combinations and require huge
nonwet coefficients:

| Fold | Largest stable bias in wet+bias (m) | Largest full RTN coordinate (m) | Largest full antenna coordinate (m) | Largest full bias (m) |
| --- | ---: | ---: | ---: | ---: |
| G05 | 251298 | 1964246 | 1925798 | 1201345 |
| G11 | 183759 | 2132467 | 2085478 | 218041 |
| G19 | 347961 | 507032 | 246258 | 121107 |
| G20 | 387669 | 2089112 | 2043019 | 785856 |
| G21 | 159562 | 528992 | 647542 | 516627 |

These are **not estimated physical orbit/antenna errors or hardware delays**.
They are representatives of a linear fitted projection, far outside the
small-displacement interpretation of the admitted APC Jacobian. Even the
bias-only extension exposes tiny observation-time clock derivatives as
insufficient practical absolute bias information. The full model's smallest
retained singular values are only 2.889e-7–6.209e-7 per metre against original
weighted scales 2834–4769 per metre. The declared cutoff is numerical, not a
physical amplitude prior. Neither a complete wet rank nor a finite SVD inverse
qualifies this unconstrained model for physical correction.

Training weighted costs decrease in every fold as columns are added:

| Fold | Wet | Wet+bias | Wet+RTN+bias | Full |
| --- | ---: | ---: | ---: | ---: |
| G05 | 662.813 | 637.426 | 440.929 | 400.665 |
| G11 | 693.291 | 676.443 | 445.854 | 406.132 |
| G19 | 168.642 | 162.523 | 114.013 | 106.105 |
| G20 | 754.382 | 707.613 | 463.384 | 425.225 |
| G21 | 506.293 | 480.874 | 324.187 | 289.873 |

These nested-model cost reductions do not establish transfer or causal source
identification. No weight, source scale, cutoff, sign, correction or floor was
selected from the reductions or the excluded scores.

## Null directions and matching candidate coupling

The full source dimensions/ranks are 197/129, 197/128, 182/110, 198/130 and
193/123: respectively 68, 69, 72, 68 and 70 numerically unresolved source
directions. Wet+bias already has 16, 16, 18, 16 and 16 such directions;
wet+RTN+bias has 34, 34, 36, 34 and 34. Individual RTN, antenna and stable
bias coordinates therefore cannot be read as unique source measurements.

At the declared resolution these source aliases largely cancel in the
complete calibration/candidate state map. The largest full-model position
response in their null space is 1.72e-5–7.90e-5 m per metre of total source
coordinate norm. For the retained **.01 m total-norm** probes:

| Fold | Linear position change (m) | Linear velocity change (mm/s) |
| --- | ---: | ---: |
| G05 | 7.900e-7 | 9.107e-8 |
| G11 | 1.718e-7 | 1.874e-8 |
| G19 | 5.503e-7 | 9.397e-8 |
| G20 | 2.116e-7 | 2.928e-8 |
| G21 | 5.676e-7 | 2.993e-8 |

The fixed-geometry reference refit agrees with its linear clock prediction:
maximum discrepancy 4.86e-11 m in offsets and 1.67e-12 m/s in interval rates.
This validates the nuisance compensation at that scale. It does not validate
a full perturbed ephemeris, a nonlinear trajectory response, or a physical
source amplitude distribution. The numerical unresolved directions are not
claimed to be exact mathematical nulls at unlimited amplitude.

This small null image is useful: filling arbitrary aliases is not the way to
recover a physical wet estimate. The serious loss of wet information and the
huge fitted nonwet representatives occur in the **very weak retained
combinations**. Small null probes cannot bound those combinations or a total
state error. No representative source-state correction is published or added
to the nominal trajectory, and no new physical covariance is assembled.

## Excluded-reference transfer worsens

The same 61 held link occurrences contain 1494 rows. For each of wet,
wet+bias and wet+RTN+bias, there are 1298 paired code/phase predictions,
178 `UNOBSERVED_NETWORK_CLOCK` and 18 `UNOBSERVED_PREFIX_PHASE` terminals.
The latter are 9 G05 and 9 G20 rows; their missing phase prefix does not imply
that the code clock is unobserved. The full model issues 1292 pairs and retains
six additional `UNIDENTIFIABLE_SOURCE_PREDICTION` terminals, all in G19.
No minimum-norm value is silently issued for those six.

The first three models yield 1254/879 increment pairs at 30/300 s; the full
model yields 1248/874. All comparisons below use the intersection across all
four models, including the same 1292 levels, 1248 short increments and 874
long increments. Thus the six missing full-model predictions cannot improve
the apparent comparison merely by changing its denominator.

| Model | Code level RMS (m) | Phase level RMS (mm) | 30 s code increment RMS (m) | 30 s phase increment RMS (mm) | 300 s code increment RMS (m) | 300 s phase increment RMS (mm) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Wet | .970620 | 16.596 | 1.283933 | 9.310 | 1.333436 | 14.567 |
| Wet+bias | .959597 | 18.716 | 1.283948 | 9.322 | 1.333446 | 14.865 |
| Wet+RTN+bias | .960062 | 27.418 | 1.283846 | 9.368 | 1.333656 | 17.673 |
| Full | .968310 | 153.522 | 1.284080 | 16.081 | 1.346861 | 113.850 |

The full model worsens phase RMS in **all five folds**, for levels and both
lags. Its 300 s phase RMS by fold is 100.987, 87.865, 93.400, 49.524 and
187.264 mm, versus wet-only 15.852, 13.043, 16.761, 14.692 and 13.825 mm
on the same support. The full 300 s code RMS also worsens in all five folds.
The small pooled code-level improvement is accompanied by code-level
worsening in G19 and G21. A better code-level mean fit does not rescue phase
transfer or physical source attribution.

Every adverse-count denominator is retained below. Each entry is
`worse absolute code / worse absolute phase` compared with wet-only on the
common support:

| Model | Levels /1292 | 30 s increments /1248 | 300 s increments /874 |
| --- | ---: | ---: | ---: |
| Wet+bias | 608 / 804 | 628 / 622 | 421 / 472 |
| Wet+RTN+bias | 609 / 771 | 626 / 619 | 431 / 477 |
| Full | 568 / 822 | 633 / 716 | 436 / 589 |

Fold-wise code/phase RMS worsening counts, always out of five:

| Model | Levels | 30 s increments | 300 s increments |
| --- | ---: | ---: | ---: |
| Wet+bias | 1 / 4 | 3 / 2 | 3 / 5 |
| Wet+RTN+bias | 1 / 5 | 0 / 4 | 4 / 5 |
| Full | 2 / 5 | 4 / 5 | 5 / 5 |

All algebraic forecast outcomes, including the negative-wet G19 model and
the huge representative coordinates, are retained as diagnostics. They do
not qualify a physical weather/product-error correction. Overlapping folds,
links and lags also preclude treating these counts as independent trials.

The fresh nominal candidate RF fits retain 339 evaluated station-window
pairs and one unavailable pair: 313 interleaved holdouts and 26 genuinely
beyond all training, from five trajectories. These are nominal predictions;
no data-estimated source correction is used. There is no new CODE state
score, target-product prior, G12 state reveal, noise-floor change or S3 run.

## Consequence and next obstruction

The wet-only millimetre precision cannot be promoted to source attribution.
The admitted geometry separates six wet coordinates only conditionally, and
competing source shapes expose weak information, out-of-domain amplitudes
and worse excluded phase transfer. This execution provides fitted competing
models, null-safe held predictions and the matching state map, rather than
another residual-closure label or an assumed independent supplier.

The next useful increment must resolve the **weak retained combinations**:
test finite physical validity of their geometry and add independently justified
wet/APC/bias or interval-timing information, or enough new geometrical leverage
to distinguish their time evolution. Any amplitude constraint must have an
independent measurement/model basis; clipping negative wet or penalizing large
coordinates after seeing these scores would not establish physical separation.
An arbitrary null anchor or another correlated product alone cannot supply
that information. S2 remains open.
