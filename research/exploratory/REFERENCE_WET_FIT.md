# Shared wet-delay response through calibration and dynamic reconstruction

## Physical question and intervention

The [v3 state diagnostic](REFERENCE_STATE_VALIDATION.md) leaves five RF-only
trajectories among 22 candidates. Its small training residuals coexist with
large conditional state axes. This increment asks how a persistent propagation
error trades against the interval receiver clocks, station-code contrasts and
shared dynamic state. It does not select a correction by its CODE discrepancy.

The intervention removes the exact-VMF3 wet-delay restriction in a separately
versioned development variant. Estimate one **signed zenith wet residual per
station**, constant across its training hour and +30 s forecasts, without a wet
prior. Reuse the existing shared central+J2 fit, satellite clock curvature,
free constant code contrasts, RF selection, floors and branch search. Every new
fit starts from the RF endpoint initializer; no previous fitted state is a seed.
The existing fixed-VMF3 behavior remains the default API.

The spatial/elevation shape comes from the already admitted VMF3 grid and wet
mapping, not from a candidate product. A constant residual over an hour is a
restricted sensitivity model, not a measured meteorological error process.
There is no asserted finite wet error sigma or total uncertainty budget.

## What constrains the state

The candidate codes constrain ranges only after receiver clocks and station
contrasts are considered. Constant differential code biases are free; their
common level is a clock gauge. Phase increments constrain changes of path, not
the constant code biases. The receiver increments are measured from other
satellites. Arc-common path curvature can trade with the free satellite clock
curvature. A single J2 trajectory ties the receiver-differential path changes
across arcs; it supplies the current local rank, rather than an orbit prior.

The new raw-observation response profiles the local clocks and ground terms in
the same whitened design used by the solver. Its covariance reconstructs the
unscaled formal global covariance. In the fixed-VMF3 model, mean interval-clock
observations contribute about 81% of the variance along G05's weakest position
axis, and about 90–97% for the other four trajectories. These fractions describe
the **assumed observation covariance**; they are not measured physical error
fractions. Code is the next material family. The existing phase, clock offset,
clock contrast and ground components are smaller in this particular metric.

The report retains a compensated local mode for a one-metre displacement along
the weak position axis, including velocity, station-code contrasts and wet
parameters, and its delta chi-square. This concretely exhibits the trade, not
an exact null or a second physical orbit. Full local rank under a restricted
model does not establish global uniqueness. The interior-Earth initialization
failure remains a numerical/domain terminal, not a competing physical solution.

## The shared source must traverse both paths

At station s, let z_s be the wet correction and M_s(t) its candidate wet mapping.
The candidate path receives `M_s(t) z_s`. Recompute the candidate-excluding
reference calibration at z=±.01 m to obtain the clock-coefficient response R:

```text
c_cal(z) = c_cal(0) + R z             first-order reference recalibration
c_cal(0) observes c_receiver - R z
candidate path = nominal path + M z
```

The .01 m is a numerical differentiation step, not an uncertainty. The reference
code mean and phase median are both recomputed, including the original residual,
subset, rank, ground-coordinate and elevation checks. This uses the original
reference observations and products, excluding the candidate as text before
numeric parsing. Reference future endpoints and all candidate products are
absent from the derivative. A half-step test checks the response on real RF.

The same z appears at every epoch and every arc of its station, simultaneously
in offset, mean increment and increment contrast. Its covariance with state and
bias is marginalized in the shared global solve. Perturbing only the final
candidate delay would omit the reference-calibration response and would answer
a different physical question. Full recalibration at each fitted station z is
retained afterward to check the local expansion, without feeding it back or
retuning weights. Median changes need not be globally linear.

## Which uncertainty is supported, and which remains conditional

| Component | Information actually present | Treatment / remaining gap |
|---|---|---|
| Code and phase | Archived IF code and carrier increments; shared middle phase endpoint | Historical 20 m code and .02 m endpoint floors remain; not measured population noise laws |
| Receiver offsets and increments | Other-satellite code means and phase medians with existing admission checks | 2 m offset, .01 m/s mean and sqrt(3)*.01 m/s contrast scales remain assumptions; overlapping reference sets do not supply independent repeat measurements |
| Wet propagation | VMF3 dry/wet values and mapping at admitted coordinates, benchmarked implementation | New station residual is free and shared through calibration and target path; its constancy is an assumption, its amplitude is not externally qualified |
| Station-code biases | RF data, shared state and constant contrast parametrization | No candidate-dependent bias prior; stability across the hour is still assumed |
| Terrestrial coordinates | Admitted coordinates, displacement corrections and .5 m conditional floor | The current per-arc ground observations are treated as independent even at the same monument; persistent coordinate/frame errors and their calibration response are not bounded here |
| Reference orbit/clock/bias/attitude | Candidate-excluding paired CODE product chain | Correlated product errors and absolute datum remain unqualified; CODE scoring shares upstream observations and is not independent truth |
| Dynamics | Central+J2 propagation and variational equations | No stochastic force budget or physical force-error bound is supplied; local state covariance is conditional on this force model |

The historical within-arc clock scenario adds one station-common endpoint
process; station-common paths are largely absorbed by satellite clock freedom.
It omits offset/increment and cross-arc correlations from the common underlying
calibration sources. The new station wet mode handles **one** such source
coherently. It does not qualify all remaining correlations or make product
errors independent. Five trajectories and their repeated evaluation epochs do
not become a coverage sample.

## Execution and outcomes

Results are retained in `results/reference_wet_fit_v1.json`. All 22 candidates,
440 nominal preparation windows and both variants remain visible. The support
comparison is paired on the same prepared arcs; this increment does not expand
snapshot preparation. Seventeen candidates still lack sufficient arcs. Numerical snapshot roots vary
across LAPACK/platform builds: 15 snapshot root counts differ from the v3
artifact, while all 440 window outcomes and selected station sets agree. Every
new branch is retained; historical artifacts are unchanged. The freshly refitted
fixed-VMF3 states agree with v3 within .04 mm.

Both variants retain five `BRANCH_SEARCH_INCOMPLETE` algebraic fits, each with
one interior-Earth initialization failure. They use the same 63 arcs and 126
state evaluation epochs; five epochs are genuinely future. **All five free-wet
fits imply negative total zenith wet delay at one or more stations.** They are
signed sensitivity fits, not accepted physical wet-only corrections.

| Candidate | CODE position RMS fixed -> free, m | Velocity RMS fixed -> free, m/s | Largest conditional position 1-sigma fixed -> free, km | Future position discrepancy fixed -> free, m |
|---|---:|---:|---:|---:|
| G05 | 156.13 -> 142.90 | .01254 -> .01072 | .754 -> .860 | 152.41 -> 139.21 |
| G11 | 88.51 -> 90.54 | .01302 -> .01334 | 4.123 -> 4.738 | 83.06 -> 86.34 |
| G19 | 146.01 -> 67.52 | .02811 -> .00515 | 6.857 -> 7.612 | 141.70 -> 70.96 |
| G20 | 66.20 -> 148.29 | .02221 -> .03107 | 3.718 -> 4.804 | 77.02 -> 158.76 |
| G21 | 210.30 -> 203.02 | .01927 -> .01794 | 1.253 -> 1.441 | 214.72 -> 207.10 |

G11 and G20 worsen in both position and velocity. The largest formal velocity
axes also grow in every case: .1305–1.2019 -> .1486–1.3621 m/s across the five
fits. CODE discrepancies are shared-product diagnostics, not independently
measured physical accuracy. Neither improved G19 error nor lower training cost
selects a preferred correction or weight.

| RF evaluation | Pairs | Code RMS fixed -> free, m | Phase-rate RMS fixed -> free, mm/s | Pairs worsened code / phase |
|---|---:|---:|---:|---:|
| All excluded endpoints | 339 evaluated, 1 unavailable | .76870 -> .76814 | 8.48537 -> 8.48424 | 160 / 154 |
| Beyond all respective training | 26 evaluated | .84029 -> .83093 | 6.97953 -> 7.01152 | 10 / 13 |

The small pooled RF changes coexist with tens of metres of state displacement
and a 82 m worsening of G20's position RMS. Future phase worsens overall. The
26 future receiver predictions come from five trajectories, not 26 independent
orbit trials. There is no availability increase or hidden support replacement.

Full reference recalibration evaluates all 340 station/arc coefficients without
rejection. Its maximum exact-minus-linear discrepancy is 1.16e-7 m in offset,
.414 mm/s in mean rate and .354 mm/s in contrast. The nonlinear median response
is therefore visible, rather than assumed globally linear. These are expansion
discrepancies, not measured receiver-clock errors. The smallest inferred total
wet delay is -.970 m; nine station/fold minima are negative. This rules out
interpreting these fitted corrections as a successful physical wet-only model.
Conditional wet standard deviations are 3.89–26.06 m, far too weak to infer a
useful absolute wet residual from this model and these assumed weights.

All estimates, conditional covariances and +30 s RF forecasts precede RF and
CODE state scoring. This is ordering on previously exposed data, not a new
blind experiment. Only one evaluation epoch per fitted trajectory is beyond
all of that trajectory's training times; the other excluded endpoints are
internal temporal holdouts. The G12 orbit is never opened.

Signed corrections can imply negative total wet delay. Such an algebraic fit
is outside the physical wet-only interpretation. The artifact records minimum
total zenith wet delay, affected stations, full recalibration failures and the
exact-minus-linear clock discrepancy. No such result is promoted by its small
training cost or by a wide formal ellipsoid.

## What additional information would constrain the trade

The artifact calculates information requirements from the fitted design, before
state scoring. It shows hypothetical independent measurements of all station
code-bias contrasts at .01/.1/1/10 m sigma, and all station wet residuals at
.001/.01/.1/1 m sigma. These are prospective precision requirements under this
geometry, **not priors admitted to either fit**. A measurement of just the common
clock or common code-bias level cannot replace receiver-differential information.
The bias contrasts would require an independently characterized receiver/signal
path or other justified calibration transfer; the reference OSB product alone
does not establish that transfer for the candidate signal.

| Candidate | Largest position sigma with hypothetical 1 mm wet measurements, m | With hypothetical .01 m code-bias contrast measurements only, m |
|---|---:|---:|
| G05 | 754.40 | 592.15 |
| G11 | 4123.31 | 577.83 |
| G19 | 6857.10 | 2303.36 |
| G20 | 3717.57 | 2211.08 |
| G21 | 1252.93 | 785.03 |

Even millimetre wet measurements alone recover essentially the original broad
state axes. Wet delay is material to nuisance/state coupling, but is not the
sole bottleneck. Even centimetre bias-contrast measurements alone do not supply
a 100 m local position scale here while wet parameters remain free. No such
external measurement is actually present, and no floor is reduced. The
calculation adds independent measurement information using
`C_new = C - C[:,I] (C[I,I] + sigma^2 I)^-1 C[I,:]`, at the fitted geometry.
Correlated external measurements need their actual joint covariance instead.

For example, in the free-wet G19 design a compensated 100 m local position
shift changes velocity by .01775 m/s, station bias contrasts by up to 3.97 m,
and station wet residuals by up to .0512 m, with delta chi-square .000173 after
profiling local clocks and ground terms. This is a local trade around a signed
sensitivity fit, whose physical wet domain already fails; it is not a claim of
two physical orbits. The retained fixed-VMF3 modes separately expose state/bias
trade-offs without any wet correction. Distinguishing these trades requires
receiver-differential information across the arcs, not an added common clock
level or another nominal wet correction.

The concrete next step is joint reference-only code/phase clock calibration
that can support its temporal and station-differential error model, together
with justified stable code-bias information or geometry that constrains those
contrasts. The approximately .01 m/s interval-rate scales currently dominate
the conditional weak state direction. Replacing them from overlapping LOO
scatter, small target residuals or a second product supplier would not qualify
them. New information must establish its own dependence on the same reference
products; the current archive does not supply an independent absolute datum.

The next S2 obstruction remains a physically supported receiver-differential
clock/bias/propagation budget. The new engine can expose this shared source and
its compensated state modes; it cannot manufacture the absent accuracy of an
absolute reference datum, certify global uniqueness, or justify population
coverage. No S3 campaign, historical outcome, uncertainty floor or G12 state
scoring is introduced.

## Reproduction and verification

```console
python -m research.exploratory.reference_wet_fit NEW_RESULT.json
python -m pytest research/kinematic/tests/test_shared_wet.py research/exploratory/tests/test_reference_wet_fit.py -q
```

The runner refuses an existing destination and binds the original input,
weather receipt and implementation bytes. Historical v3 sources now replay from
`ac902e5` through the existing Git mechanism; historical report bytes and hashes
are unchanged. Tests cover synthetic joint state/motion/bias/wet recovery,
wet and calibration signs, covariance reconstruction, coherent cross-arc error
versus independent appearances, poisoned products/observations, step convergence,
scoring chronology and retained support/forecasts. Existing Linux/Windows CI
workflows discover them. Codex review is requested on the delivery PR.
