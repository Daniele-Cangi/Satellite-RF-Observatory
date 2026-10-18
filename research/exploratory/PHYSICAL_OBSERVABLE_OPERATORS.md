# Physical complementary readouts and absolute calibration levels

This exploratory increment follows [stable source differentials](STABLE_SOURCE_DIFFERENTIAL.md).
The question is which physical readout operators constrain the remaining source
combinations, once their instrument levels and mechanical reference transfers
are included. It does not acquire independent observations or admit a source
covariance. All archived outcomes remain unchanged.

## Scope and support

The same 22 exposed candidates, 440 windows, 63 prepared arcs and five supported
local source designs are retained. Their RF trajectories still have the
archived `BRANCH_SEARCH_INCOMPLETE` terminal; the other 17 preparations remain
insufficient. There is no new RF trajectory fit, RF/MW or CODE state score,
candidate correction, G12 state access, production-floor change or S3 campaign.
The target is the same fixed nominal RF source-to-state sensitivity, not a new
joint estimator covariance or demonstrated orbital accuracy.

Geometry uses only admitted non-target COM/attitude products and terrestrial
coordinates. The schedule is every original reference row whose receive tag
is a multiple of 300 seconds; its hypothetical range bounce epoch is tag minus
0.1 second. This is a fixed geometry schedule, independent of RF values and
held scores. Each scheduled geometry attempt and failure is retained without
replacement. Wet readouts occur once per station/time, not per visible reference;
antenna readouts occur once per reference/body-axis/frequency.

**Equipment, independent data, survey ties and calibration availability are
`NOT_ESTABLISHED`.** A GNSS station coordinate is not evidence of a co-located
laser station or radiometer, and no reflector payload is assumed available.
The nominal zero reflector lever arm is an explicit geometry control, not a
spacecraft parameter. None of the information cases can establish physical
readiness, even if its numerical benchmark passes.

## Physical readout operators

### Two-way range

The observable is half the roundtrip vacuum light-time, `c*(t_rx-t_tx)/2`,
with the transmit epoch held fixed during a source perturbation. The nominal
bounce position is the admitted COM. Both legs include rigid Earth rotation;
the implicit derivative includes COM inertial velocity and ground motion.
It therefore observes a changing projection of RTN error, not three directly
measured RTN coordinates. A centred finite perturbation of the full moving
path independently checks this Jacobian.

Let `u_up,u_down` point from the transmitting/receiving station to the bounce
point, `v` be the bounce velocity and `v_tx,v_rx` the station velocities in the
local inertial frame. Then

```
dt_b/dx = u_up / (c-u_up.v)
dt_rx/dx = [u_down + (c+u_down.v)*dt_b/dx] / (c+u_down.v_rx)
g = c/2 * dt_rx/dx
```

The range row uses `g*B_RTN` for reference orbit coordinates. It uses the same
`g*A_body` for a reflector offset and for the mechanical-origin/COM transfer.
It has no RF antenna PCO or phenomenological code-bias term. Additional nuisance
columns retain station interval zero, timing-scale error, epoch-tag error and
an optical zenith residual. The scale variable is fractional scale times
25,000,000 m; the epoch variable is `c*delta_t` in metres. The optical residual
uses each leg's secant elevation shape with its implicit timing transfer.

This is a conditional local flat-spacetime/rigid-Earth operator, **not an SLR
processor or optical atmosphere accuracy claim**. It does not introduce an
optical refraction model by reusing VMF3. Terrestrial coordinates, nominal
attitude and body-axis orientation remain conditional. Relativistic propagation,
PCV, reflector signatures and time-varying calibration processes need further
models before a real measurement can be admitted.

### Frequency-specific antenna metrology

Independent antenna calibration must refer its electrical PCO to a mechanical
origin and then to the COM. Let `a=ALPHA`, `b=BETA` with `a+b=1`, and let
`d=p2-p1` remain free. For the existing IF source coordinate `theta_ant`,
the raw residual operators are

```
p1 = theta_ant - b*d - origin
p2 = theta_ant + a*d - origin
```

Their IF combination is `a*p1+b*p2 = theta_ant-origin`; no equality of the two
frequency offsets is imposed. The same `origin` coordinate enters range with
the opposite transfer sign. It is one shared physical nuisance, not two
independent copies. The raw readout covariance is propagated through this
frequency law. Existing ANTEX values define the admitted model; they are not
reclassified as a new independent antenna calibration.

### Retrieved wet path and component timing

An independently retrieved station zenith wet-path readout has the local law
`retrieved_path = theta_wet + instrument_zero`. It is a retrieved path operator,
not a microwave brightness/radiative-transfer model. Absolute retrieval level,
co-location and mapping/gradient errors need separate physical qualification.

For hardware, the current source coordinate is a total per-link stable IF
bias. A component-delay model can only claim

```
theta_link_IF = ALPHA*(receiver_P1 + transmitter_P1) + link_remainder_IF
```

with the link remainder retained. Independent component readouts do not
constrain an arbitrary total-link coordinate while that remainder is free.
The component incidence and exact gauge are retained in the artifact. No
laboratory component calibration is silently promoted to an observation of
the total link bias. A separate **unavailable total-link closure control** adds
the ideal missing functional only to diagnose this operator gap; it is not a
physical package or evidence of a feasible measurement route.

## Calibration/support observations and stochastic scenarios

Every physical package has a joint readout law `y=H*theta+B*z+noise` and separate
calibration/support readouts `y_cal=C*z+noise_cal`. Whiten both and profile the
same nuisance vector jointly. Calibration/support rows can require mechanical
COM transfer, reflector characterization, timing metrology or optical-path
information; they are not all laboratory zero measurements. No values are
observed or estimated here, and none of these rows is an admitted source prior.

| Level law | What is observed |
|---|---|
| Free | No independent level information. |
| Relative | Orthonormal contrasts within each nuisance type/axis; the common absolute level remains free. |
| Anchored relative | The same contrasts plus one measured first-member anchor per type/axis; the member is fixed by lexical identity. |
| Individually absolute | One independent level/support readout for every eligible nuisance. |
| Ideal control | Eligible levels treated as known, only as an information upper-bound control. |

Frequency differences always remain free; they are not calibration zeros.
Anchor observations retain their uncertainty and resulting common covariance.
The random-readout grid is `.001,.01,.1 m`; the finite calibration/support
sigma grid is `.0001,.001,.01,.1,1 m`, in each declared coordinate's units.
A common numerical sigma across roles is a diagnostic grid, not a universal
instrument specification or an assumption of achievable accuracy.

Two random covariance scenarios use marginal sigma as stated: independent
readouts, or correlation `.5**abs(delta_t/300 s)` within each range link/wet
station, with raw L1/L2 PCO pair correlation .5. Cross-family random errors are
conditionally independent; constant levels and the common COM origin remain
shared. No physical temporal covariance is qualified. Repeating noisy readouts
cannot resolve a free constant level; finite calibration information leaves a
level-uncertainty limit even as the random averaging error decreases.

The fixed finite case schedule has 212 cases per supported fold: 102 full
range+wet+antenna cases, 60 proper-family ablations and 50 unavailable total-link
closure controls. All 1,060 cases retain the three existing absolute source-rank
cuts (`1e-9,1e-10,1e-11` times the original RF source scale). Stronger external
precision does not raise the cut. The existing complete-image/null criterion
and joint 1 m / 1 mm/s design benchmark remain unchanged. Worst unresolved
source/calibration directions at the central cut are algebraic diagnostics,
not measured source or calibration errors.

## Primary physical references

[ILRS](https://ilrs.gsfc.nasa.gov/docs/AOGS_ILRS_0708.pdf) defines the roundtrip
time observable and its optical/reflector corrections; the [spacecraft COM
information](https://ilrs.gsfc.nasa.gov/missions/spacecraft_parameters/index.html)
explains the required reflector-to-COM transfer. [IGS antenna guidance](https://www.igs.org/wg/antenna/)
distinguishes frequency-specific phase-centre models and reference points.
The [JPL radiometry study](https://ipnpr.jpl.nasa.gov/progress_report/42-226/42-226F.html)
gives a physical route to wet-path readouts. [BIPM calibration guidance](https://webtai.bipm.org/ftp/pub/tai/publication/gnss-calibration/guidelines/bipmcalibration_guidelines_v40.pdf)
describes delay-transfer references and retained calibration uncertainty.
These references motivate observable types and missing metrology. No precision,
equipment coverage, calibration value or independent data is imported from them.
