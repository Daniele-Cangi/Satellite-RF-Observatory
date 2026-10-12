# G12: does dynamical coupling help the differential bias mode?

## Result and decision

**Yes, under the declared local model, but it does not complete S2.** A shared
six-parameter trajectory strengthens differential station-code-bias information
relative to independent short-arc position/motion models. With phase and constant
biases, the weakest formal coefficient scale changes from **1,992.6 to 217.3 m**.
Both profiles already have full local bias rank; the improvement is conditioning,
not newly demonstrated position accuracy. This is information evaluated at a
propagated RF-derived geometry, **not a fitted common orbit or a physical bound**.

The force approximation matters. Central gravity and central-plus-J2 propagation
from exactly the same RF state separate by **318.4 m** at the final endpoint,
3,510 s later. Their vacuum-code predictions differ by up to **295.9 m**, and
their interval-mean phase-rate predictions by up to **0.16646 m/s**. These are
same-seed model separations, not measured orbit errors or irreducible residuals
after fitting: a new fit can absorb part of them in its state, clocks and biases.
They establish a concrete reason to retain the J2 comparison and qualify force
errors rather than declaring central gravity an exact constraint.

Proceed toward a **shared dynamical RF fit with free differential code biases
and excluded RF predictions**. Preserve independent short arcs as the comparison.
Do not promote this feasibility calculation to a production uncertainty, change
floors/masks or start S3. The failed reference-direction correction remains rejected.

## Inputs and target boundary

Only the exposed [full-hour RF report](G12_FULL_HOUR.md) and its admitted station
coordinates are read. No target orbit, satellite-clock product, oracle-error
file or reference satellite's trajectory seeds the target. The nominal state is
the first chronological accepted **code-only RF arc**, at 10:01:00 GPST:

```text
ECEF position (m):   [-10088232.5505, -23794901.6392,  5817082.4796]
ECEF velocity (m/s): [       89.7261,      -821.8780,     -3054.5698]
```

These are already exposed inverse estimates, not true orbit data. The seed is
used to specify a point at which to calculate derivatives and model separation;
it is not a state prior, an uncertainty bound or a new dynamic fit. All six
shared initial-state components remain free columns in the information design.
No target orbital radius, period, energy or previously propagated state is
imposed as a constraint. Numerical propagation is restricted to exterior-Earth
states and explicitly integrated times; it cannot silently extrapolate.

The existing forty cases and their status labels are retained. Profiles use the
same **33 accepted code arcs** or **12 accepted phase arcs**, without selecting
new cases by dynamical residual. All six whole-window mask failures, the code
prediction failure and all 22 phase rejections remain visible. Selection is
conditional on the historical exposed RF qualifications, not observation-blind
confirmation. There is no new fit, acceptance test or target RF reveal here.

## Physical and observation models

Integrate central gravity, and separately central gravity plus a nominal J2
term, in a uniformly rotating terrestrial frame. Include Coriolis and
centrifugal accelerations. The rotation rate is the existing RF-model constant,
`7.2921151467e-5 rad/s`; it is not time-dependent Earth orientation. The existing
GPS/GRS80 gravitational constant is `3.986005e14 m^3/s^2`; equatorial radius
`6378137 m` and nominal GRS80 J2 `1.08263e-3` are documented in the
[US Naval Research Laboratory constants](https://github.com/USNavalResearchLaboratory/TrackerComponentLibrary/blob/master/Physical_Values/Constants.m).
These describe declared force approximations, not a complete gravity solution.

The reusable `research/kinematic/orbital_dynamics.py` integrates forward and
backward from epoch zero using DOP853 and dense output. Receiver tags are GPST
offsets from that epoch. Correct each receiver tag by its fitted affine clock,
solve emission time from geometric light time without measured code, rotate
the emission position to the reception frame with the existing Sagnac sign,
and apply the local transmit-time satellite clock. Phase observables are
differences of predicted endpoint ranges divided by 30 s, not instantaneous
Doppler. No carrier ambiguity level is treated as an absolute range anchor.

This diagnostic preserves the old conditional code/phase/clock/ground weighting:
20 m code sigma, 0.02 m phase-endpoint sigma, 2 m receiver-clock offset sigma,
0.01 m/s receiver-clock slope sigma and 0.5 m terrestrial-coordinate sigma.
Endpoint differencing retains the phase-rate correlations. Covariances across
distinct arcs are assumed independent for this comparison; shared calibration
and temporal correlations remain unqualified.

Each arc keeps two free satellite-clock coefficients and the original receiver
clock and ground-coordinate nuisance parameters. Whiten their design using the
old covariance, eliminate all of them by QR, then stack the remaining six-column
shared-state sensitivities and five global zero-mean station-bias contrasts.
Eliminate the shared state jointly, rather than separately at each arc. The
drift alternative adds five code-only contrasts for the bias change across the
admitted endpoint span; it adds no fictitious carrier-bias slope. Absolute common
constant code bias remains a satellite-clock gauge.

The additive satellite-clock-offset derivative is analytic: exactly -1 for
code and zero for carrier increments. A regression test found that finite
differencing large ranges otherwise creates a small spurious constraint on
this gauge; the exact derivative removes it. The existing receiver-time,
short-arc solver and historical evidence are unchanged.

## Conditional information and numerical checks

All 45 admitted arc/model geometries evaluate for each force model. A failed
geometry would retain its case and invalidate the aggregate for that estimator;
it cannot be rescued by silently stacking a smaller subset.

| Bias model / observations | Independent arcs (m) | Central dynamics (m) | Central + J2 (m) |
|---|---:|---:|---:|
| Constant / code, 33 arcs | 5,162.6 | 380.098 | 380.088 |
| Constant / code + phase, 12 arcs | 1,992.6 | 217.267 | 217.262 |
| Constant + drift / code, 33 arcs | 10,910,413 | 15,113.3 | 15,114.0 |
| Constant + drift / code + phase, 12 arcs | 2,171.8 | 239.941 | 239.935 |

Values are reciprocals of the weakest bias-profile singular value, in metres
of contrast coefficient under the conditional weights. Constant models have
rank 5/5; drift models 10/10. The nominal trajectory differs from the separately
fitted historical arc points, so this comparison changes the trajectory model
and its evaluation geometry; it is not a controlled position-accuracy ratio.

Scaled state derivative steps 0.5e-5, 1e-5 and 2e-5 retain all ranks and change
the displayed scales by less than 0.0002%. Tightening integration relative
tolerance from 2e-12 to 2e-13 changes endpoint positions by at most 1.3e-8 m and
velocities by 1.9e-12 m/s in this run. These are numerical comparisons, not
estimates of physical force-model error or absolute integrator-error guarantees.

## Model adequacy remains open

The same-seed central/J2 comparison includes all forty endpoint times. Vacuum
RF differences are evaluated for all 34 historically available cases: 510 code
values and 340 interval-rate values. Their RMS separations are **132.032 m**
and **0.092985 m/s**, with the maxima given above. The other six cases retain
explicit unavailable-observable status; no mask relaxation creates RF values.

With J2, propagation from the single RF seed differs from the historical accepted
code-fit positions by median **1,674 m**, maximum **3,088 m**. Against accepted
phase-fit positions it differs by median **869 m**, maximum **2,758 m**. These
are disagreements between RF-derived estimates and propagation, not independent
accuracy measurements or proof of force-model rejection. Initial RF velocity
uncertainty, effective bias, local polynomial approximation and model omissions
can all contribute. No uncertainty is estimated by calling these differences
Gaussian noise or rescaling covariance to fit them.

Before physical qualification, the dynamic fit needs adequate terrestrial-frame
orientation, a force-error budget beyond nominal J2, the relationship between
the RF radiating point and satellite mass centre, and the existing propagation,
clock, bias-stability and correlation budgets. A stable information spectrum
does not qualify any of those. Neither reference-only records nor dynamics
should supply a falsely exact prior just because the old bias mode is weak.

The next implementation should estimate the common initial state and effective
biases jointly from RF, retain clock/ground freedom and every failure, and predict
observations outside fitting. Compare it to the short-arc baseline and report
worsening cases. A successful exposed-data fit would still need a justified
total uncertainty and new independent confirmation before S3/S4 claims.

## Reproduction

```console
python -m research.exploratory.g12_dynamics_feasibility NEW_OUTPUT.json
python -m pytest research/kinematic/tests/test_orbital_dynamics.py research/exploratory/tests/test_g12_dynamics_feasibility.py -q
```

The complete [result](results/g12_dynamics_feasibility_v1.json) records both
input hashes, the two producer hashes, all historical outcomes, per-arc RF-state
disagreements, all force-model separations and derivative/integration checks.
The old full-hour result and coordinate hashes retain their existing provenance;
Git preserves implementation versions. No seal, checked wrapper or new authority
is introduced. CI discovers the ten new tests in its existing Linux/Windows
matrix: analytic circular propagation in both time directions, inertial energy
and momentum, J2 limits, light-time/clock conventions, joint profiling, clock
gauge, failure retention and actual report coverage. Full numerical generation
is available through the command above, not claimed as part of every CI run.
