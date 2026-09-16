# Regularized station frame, epoch and post-seismic motion

## What this adds

The CODE IGc20 catalogue, propagated with its velocities and post-seismic
deformation (PSD) terms, reproduces the daily CODE final SINEX a-priori station
coordinates to **less than 7 micrometres** for all fourteen station/day pairs.
This establishes consistency of the regularized station-coordinate model in
these artifacts. It does not measure final/rapid frame realization error or
qualify instantaneous station positions.

Five fixed station-coordinate variants per event recalibrate the same exposed
G14/G12 reference observations. All ten cases pass the historical calibration
checks. Relative to the header coordinates, transported final coordinates reduce
pooled reference-residual RMS by **6.163% for G14 and 0.629% for G12**. Two G14
and three G12 stations worsen. These are exploratory reference residuals, not
new target-position accuracy, predictive validation or an uncertainty budget.

## Data, frame and epoch evidence

Restricted inputs and source/extract hashes are in `inputs/station_frame/`.
The [CODE reference directory](https://code.aiub.unibe.ch/s3_script/aiub_s3_bucket_listing.php?path=BSWUSER54%2FREF)
provides `IGC20.CRD`, `IGC20.VEL` and `IGC20.PSD`. The CRD header declares
`IGc20_0` and epoch 2020-01-01 00:00:00. Only the nine short station codes used
by the two fit networks are retained. Matching also requires the exact DOMES
monument: AREQ has an obsolete, differently labelled monument in the catalogue,
which is retained as text but never substituted for the admitted monument.
Eight current monuments carry IGC20/IC20 flags; BOGT carries ITR20/IT20.
These origin flags remain visible rather than being renamed to IGC20.

[IGSMAIL-8634](https://lists.igs.org/pipermail/igsmail/2025/008630.html)
announces IGc20 from GPS week 2401 and describes it as aligned in origin,
orientation and scale with ITRF2020, with zero inter-realization transformation
parameters. The paired rapid SP3/ORBEX inputs already identify IGc20. The new
numerical a-priori comparison additionally binds these actual daily products to
the catalogue model, including BOGT, rather than inferring the frame from an
antenna calibration filename. It is not a measurement of residual datum errors.

For each day, only fit-site STAX/STAY/STAZ rows of `SOLUTION/APRIORI` are extracted
from the previously downloaded CODE final SINEX. Station/point/solution ID,
coordinate epoch and units must match the pinned station report. Satellite
parameters and normal equations are discarded as text before numeric parsing.
The comparison uses each product's daily solution ID 2, not an adjacent day.

The 1 mm a-priori consistency label was fixed in the execution source before
running. It is a numerical convention check, not a physical accuracy threshold
or an admission gate. All comparisons and all variants are retained regardless
of that label. The observed micrometre-level agreement is compatible with the
catalogue's printed coordinate precision; it does not establish micrometre
knowledge of the real monument.

## Model and fixed comparisons

The [IGN PSD equations](https://itrf.ign.fr/ftp/pub/itrf/itrf2020/ITRF2020-PSD-model-eqs-IGN.pdf)
give a linear coordinate evolution plus cumulative logarithmic and exponential
displacements after each earthquake. The implementation pairs amplitude and
relaxation-time entries by monument, point, earthquake epoch, model and ENU
component. It uses `A log(1 + dt/tau)` and `A (1 - exp(-dt/tau))`, zero before
the earthquake, and rotates ENU displacement into ECEF. Years are 365.25 days.
Amplitudes and full accumulated PSD are not subtracted at the catalogue epoch.

The five pre-execution modes are:

1. `header`: unchanged archived ARP coordinates; replays the reference baseline.
2. `catalog_linear_control`: epoch-2020 catalogue plus velocity, deliberately
   omitting PSD to expose its contribution.
3. `catalog_psd`: catalogue plus velocity and every applicable PSD term.
4. `final_static`: the previously audited daily final SINEX ARPs.
5. `final_transport`: daily final marker plus the catalogue model's change
   between the daily coordinate epoch and each observation epoch, then the
   matched marker-to-ARP eccentricity. This avoids adding accumulated PSD twice.

Station-model time uses elapsed Gregorian calendar seconds on the existing GPST
calendar. An 18 s shift control is reported; its largest coordinate effect is
0.043 micrometres for this slow model. This does not qualify time conventions
for tidal models, where absolute phase matters. There is no leap-second or
Earth-rotation reinterpretation of the existing RF model.

The secular/PSD transport from daily epoch to event midpoint is only
**2.18–68.48 micrometres**. The earlier several-hour epoch gap is consequently
negligible for this slow component; it says nothing about periodic tides.
AREQ's supplied cumulative PSD norm at the event is **0.354538 m**. Other
admitted monuments have no terms in the supplied PSD catalogue; that absence
does not establish absence of all nonlinear physical motion.

Each mode uses the same 11 epochs, seven fit stations, translated reference
codes, CODE rapid orbit/clock/bias, full attitude PCO and frozen reference sets.
The receiver-clock fit and SPP consistency checks are repeated with epoch-specific
station coordinates, including their effect on the unchanged troposphere model.
The baseline residual replay difference is exactly zero for both events.
No target fit, target orbit, excluded receiver, new RF acquisition or core
estimator modification is involved.

## Results and complete denominators

| Mode | G14 pooled RMS (m) | G12 pooled RMS (m) |
|---|---:|---:|
| Header | 0.956774734 | 1.025024985 |
| Catalogue linear control | 0.898479513 | 1.024436524 |
| Catalogue with PSD | 0.898479513 | 1.018767241 |
| Final static | 0.897808985 | 1.018575045 |
| Final transported | 0.897809488 | 1.018574846 |

All five G14 cases evaluate 716/734 observed paths, and all five G12 cases
747/847. The same 18/100 omitted paths stay explicit. All **770 station/epoch
calibrations** pass; no case or station is dropped. The largest absolute
receiver-clock changes from header are 0.361 m (G14) and 0.349 m (G12) across
all variants, expressed as range-equivalent clock values.

Per-station RMS for header versus final transported coordinates:

| Event | Station | Header (m) | Final transported (m) |
|---|---|---:|---:|
| G14 | ALGO | 0.735093 | 0.746318 |
| G14 | BOGT | 1.076128 | 1.123676 |
| G14 | DRAO | 1.076892 | 1.029281 |
| G14 | MKEA | 0.950975 | 0.714978 |
| G14 | PIE1 | 0.796665 | 0.781560 |
| G14 | STJO | 0.687515 | 0.647877 |
| G14 | YELL | 1.170678 | 1.075232 |
| G12 | ALGO | 1.005647 | 1.031988 |
| G12 | DRAO | 1.679836 | 1.663149 |
| G12 | STJO | 0.889368 | 0.857295 |
| G12 | YELL | 0.925037 | 0.959127 |
| G12 | BOGT | 1.005000 | 0.937338 |
| G12 | BRAZ | 0.708509 | 0.714220 |
| G12 | AREQ | 0.648033 | 0.646551 |

Omitting PSD increases AREQ RMS from 0.646450 to 0.704670 m within the catalogue
comparison. The G14 linear/PSD cases coincide because none of its fit monuments
has a term in this supplied PSD model. Final static/transported pooled RMS
differs by less than 0.6 micrometres; the epoch transport is not responsible
for the much larger improvement relative to approximate header coordinates.

## Limits and next physical component

Coordinates remain regularized. Solid-Earth tides, pole tides, ocean and
atmospheric loading, seasonal motion, receiver code response and physical
cross-covariance are still unmodelled. The published
[CODE analysis summary](https://www.aiub.unibe.ch/download/CODE/CODE_ACN.TXT)
describes tidal corrections including the permanent tide in its tide model,
not in station coordinates. Its frame paragraph still mentions IGb20, so it
is not used here as current IGc20 frame proof. A matching, explicit displacement
model is required before calling the new coordinates instantaneous.

The next trial should implement and validate the periodic site-displacement
terms at the RF epochs, then repeat reference-only checks over broader geometry.
This study does not close S2/G3, justify a reduced uncertainty floor or admit S3.

## Reproduction and provenance

Execution source was frozen in `93a630a7e79278ffbf92db420fa2f55a241a23c8`.
An erroneous test expectation for the obsolete AREQ monument was corrected
before execution; the executed checkout was
`1fd8c9e5678c21396e8e3419e4c1ef3d6cb75c56`. All 38 reported source bindings
were verified against that commit. No prior scientific source or report changed.
The new input receipt is pinned in code; complete prior evidence uses the active
strict/pinned verifier from PR143. JSON parsing and hashing use the same bytes.

```powershell
python -m research.exploratory.station_frame_epoch g14 g14-frame-replay.json
python -m research.exploratory.station_frame_epoch g12 g12-frame-replay.json
```

Outputs must be new paths. Tests cover PSD signs/units/cumulative earthquakes,
pre-earthquake zero, exact monument matching, malformed PSD pairs, final-epoch
anchoring without double counting, input tampering, retained failures and full
report replays. SPP-coordinate replay permits 3 mm platform variation from the
nonlinear finite-difference solver; clock/residual replay uses 0.1 micrometre.
