# G08: one Internet-only inverse position

One frozen event was executed on 2026-09-08 using public RINEX observations for
2026-09-06. Five terrestrial receivers estimated GPS G08's position and an
emission-time/clock parameter, without a target orbit or target clock product.
GOLD and then an IGS rapid orbit were revealed after the solution hash was saved.

**Formal outcome: `UNCERTAINTY_TOO_LARGE`.** The measured position error was
**188.705 m** and the held-out GOLD residual was **1.849 m**, but the pre-oracle
95% outer uncertainty radius was **21,607.660 m**, exceeding the frozen 10 km
limit. This event therefore does **not** receive
`INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED`.

The earlier DRAO labelled-forward result remains closed and unchanged.

## Frozen experiment

- Target: receiver-labelled GPS G08, 2026-09-06 GPST.
- Fit: ALGO00CAN, DRAO00CAN, STJO00CAN, YELL00CAN, BOGT00COL.
- Held-out receiver: GOLD00USA; only its non-target observations calibrated its clock.
- First structurally admissible window: 00:00–00:05 GPST, eleven 30 s epochs.
- Observable: IF combination of C1C and C2W.
- Reference clocks: healthy **non-G08** GPS broadcast orbits and clocks, plus
  fixed terrestrial coordinates. At least four references above 10 degrees.
- Target state: xyz and B only; no target dynamics or satellite-radius constraint.
- Emission epoch: 00:02:29.924690536 GPST.
- Primary oracle: `IGS0OPSRAP_20262490000_01D_15M_ORB.SP3.gz`.

Solution hash:

`213da6154cbb8c3c7dc278b2e81cd82f60da6d5852cdc89da3d03d57a55c8462`

Freeze: 20:24:40.028281 UTC. GOLD reveal: 20:26:23.821795 UTC.
Orbit access: 20:26:25.649730 UTC, all on 2026-09-08.

## Code and replay

`qualification.py` checks code-field presence, framing, and the chronological
window without numerical target values. A phase-only Galileo header update at
YELL is handled explicitly; clock or coordinate updates are rejected.

`calibration.py` strips G08 navigation blocks before parsing, refuses target
propagation and target observations in calibration, models reference clocks and
light time, and verifies reference residuals and independent ground coordinates.
Only the historical `parse_gps_record` primitive is reused.

`solver.py` reconstructs common emitted-code tags, uses algebraic range
initialization and unsquared least squares, searches four-root branches, checks
the infinite-range alternative, and propagates the declared error model.

Replay from the repository root:

```powershell
python -m experiments.gnss_inverse_positioning.replay experiments/gnss_inverse_positioning/event_2026249/frozen_solver_input.json
python -m pytest experiments/gnss_inverse_positioning/tests -q
```

Replay accepts measurements, calibrated clocks, terrestrial coordinates, and
the covariance derived before oracle access. It receives no estimated or true
target position. It reproduces the sealed calculation and is not a new proof.
The compact replay package was assembled after reveal from already hashed
pre-reveal inputs; original timestamps and hashes are in the evidence archive.

Executed environment: Python 3.13, NumPy 2.3.3, SciPy 1.17.1, Hatanaka 2.8.1.
Hatanaka is needed to decode original observations; numerical replay only needs
NumPy/SciPy. Ten focused tests cover framing, selection, target-state rejection,
reference propagation, inverse recovery, and clock-gauge invariance.

## Interpretation and limitation

The point estimate is derived from RF measurements. Its 189 m oracle error does
not replace the uncertainty predicted before reveal. The 20 m statistical floor
and ±20 m per-root systematic design envelope were not reduced after seeing the
small residuals. The poor radial/clock separation produced a radial-clock
correlation of approximately -0.999991 and a worst position sigma of 4.836 km.

The uncertainty is conditional on the declared noise, reference-error,
coordinate, and systematic-envelope model. The ±20 m envelope is an explicit
design assumption, not a certified universal receiver bound. Nonlinear axis
profiles and bias-box corners are diagnostics, not a formal global coverage
theorem. A single event cannot establish population coverage.

The IGS oracle is independently produced and excluded causally from the solver.
Its processing may include these ground stations; statistical disjointness of
all underlying measurements has not been established. G08 is a receiver label;
this experiment does not independently establish identity, velocity, or an orbit.

## Failure analysis, without changing this event

**Physical block:** the frozen geometry amplifies the declared code/clock errors
too strongly for the 10 km uncertainty requirement. Data availability, reference
calibration, and the held-out measurement did not fail.

**Information value:** one public network supports an inverse point estimate
that predicts a separate receiver and agrees with the unopened orbit within
189 m. Accurate observed error and prospective precision remain different claims.

**Alternatives for a separate future experiment:** (A) predeclare a receiver
geometry with stronger radial information; (B) independently qualify a smaller
code/clock error budget; (C) add multiple emitted events with a free initial state
and explicit generic dynamics; (D) use onboard GNSS observations for a different
receiver/transmitter geometry, changing the terrestrial-network claim.

**Shortest next physical path:** a separately preregistered event with improved
geometric information and an error budget qualified without its target oracle.
No target/window search, threshold reduction, or new execution follows from this
failure. This event is closed with its original result.
