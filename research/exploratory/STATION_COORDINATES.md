# Terrestrial coordinates, antenna reference points and phase centres

## Finding and scope

All fourteen fit-station/day combinations match a same-day CODE final terrestrial
solution by station code, DOMES monument, point, solution interval and antenna
type/radome. The archived coordinates reproduce **marker + RINEX H/E/N = ARP**
exactly. They are not electrical phase-centre coordinates. RINEX and SINEX
eccentricities agree for all fourteen combinations.

The SINEX-derived ARPs differ from the archived ARPs by **0.114–0.933 m**.
Their first-order range effects on the previously admitted reference directions,
after removal of each station/epoch common component, have pooled RMS
**0.307397 m for G14 and 0.250849 m for G12**. These are geometric product
sensitivities, not measured code errors, recovered accuracy or corrected residuals.
The directional regression coefficients from the previous study cannot yet be
interpreted as receiver antenna calibration.

This exploratory audit makes no target fit, clock recalibration, oracle or
excluded-receiver read. No production estimator changes. S2/G3 remain incomplete.

## Evidence and conventions

The inputs under `inputs/station_coordinates/{g14,g12}/` contain only seven fit
station headers, a restricted terrestrial SINEX extract and hash-bound receipts.
Source products are
`COD0OPSFIN_20262460000_01D_01D_SOL.SNX.gz` and
`COD0OPSFIN_20262480000_01D_01D_SOL.SNX.gz`, from the
[BKG IGS analysis-centre directory](https://igs.bkg.bund.de/root_ftp/IGSac/products/2434/).
These are **CODE final three-day solutions**, not CODE rapid coordinate products.
Daily solution ID 2 covers each event; IDs 1 and 3 are retained in the extracts
but not substituted for the event day. The original header's parameter count
describes the source, not the restricted extract.

G14 headers are extracted from the frozen `structure.json`. For G12, the seven
original CRINEX gzip files were fetched again and matched their archived raw
SHA-256 receipts before header extraction. Parsing stops at `END OF HEADER`;
no observation numbers are decoded. GOLD is not fetched or retained. SINEX
satellite blocks, non-fit stations, satellite parameter estimates and all normal
equations are discarded as text before numerical interpretation.

Per the [SINEX specification, sections 16a and 17](https://ivscc.gsfc.nasa.gov/products-data/sinex_v202.pdf),
eccentricities describe marker-to-ARP offsets; phase-centre offsets describe
ARP-to-L1/L2 offsets. SINEX UNE is reordered into ENU; RINEX H/E/N is reordered
into ENU separately. Each local vector is rotated at its own marker position.
The L1/L2 ionosphere-free phase offset uses the squared-frequency combination
described by [ESA Navipedia](https://gssc.esa.int/navipedia/index.php/Receiver_Antenna_Phase_Centre).
Those phase offsets are listed, not applied to code measurements.

All selected phase model records identify IGS20_2425, with generic serial
`-----`. Matching type/radome does not independently establish the installed
antenna serial's calibration, orientation, code response or directional PCV.
The IF phase-offset norms range from 0.038623 to 0.111111 m. They are neither
code corrections nor upper bounds on total antenna error.

## Results

All lengths below are metres. The range-change column is centred per
station/epoch over the same frozen, broadcast-selected reference set.

| Event | Station | ARP difference norm | Centred range-change RMS | Maximum absolute centred change | IF phase PCO norm |
|---|---|---:|---:|---:|---:|
| G14 | ALGO | 0.147774 | 0.088870 | 0.123539 | 0.047800 |
| G14 | BOGT | 0.682532 | 0.170213 | 0.345357 | 0.047413 |
| G14 | DRAO | 0.493541 | 0.267401 | 0.473548 | 0.110013 |
| G14 | MKEA | 0.932561 | 0.452472 | 0.659154 | 0.038623 |
| G14 | PIE1 | 0.296845 | 0.167706 | 0.278126 | 0.045791 |
| G14 | STJO | 0.565173 | 0.279530 | 0.484234 | 0.111111 |
| G14 | YELL | 0.767186 | 0.428740 | 0.675763 | 0.047800 |
| G12 | ALGO | 0.147569 | 0.085323 | 0.136987 | 0.047800 |
| G12 | DRAO | 0.491360 | 0.256558 | 0.496750 | 0.110013 |
| G12 | STJO | 0.565536 | 0.317874 | 0.600719 | 0.111111 |
| G12 | YELL | 0.764832 | 0.416985 | 0.728025 | 0.047800 |
| G12 | BOGT | 0.679935 | 0.226952 | 0.330306 | 0.047413 |
| G12 | BRAZ | 0.340759 | 0.187839 | 0.323745 | 0.094616 |
| G12 | AREQ | 0.113846 | 0.055888 | 0.099889 | 0.047413 |

There are 716/734 G14 and 747/847 G12 admitted reference paths. The remaining
18/100 paths remain outside the fixed broadcast reference sets in the bound
reference report; they are not assigned invented directions. For each evaluated
path, `delta_range = -LOS_ENU dot (ARP_SINEX - ARP_header)_ENU`.
This sign is for a **modelled range** change, not observed-minus-model residual.
The projected change is centred with `P = I - 11.T/n`. Receiver clocks, satellite
states, emission geometry and all other model terms are held fixed. There is
no claim that adding/subtracting this projection improves the code residuals.

## Limits that matter for the next model

The reported coordinate epoch is 11:59:45 of the relevant day, 28,935 s after
the G14 window midpoint and 5,235 s after G12. This is a daily static coordinate
comparison, **not an instantaneous position at the RF observation time**.
The selected windows lie well inside the day in GPST or UTC; an 18 s interior
guard avoids using an ambiguous boundary. No velocity propagation, solid-Earth
tide, ocean loading or other site-displacement correction is applied here.

The SINEX antenna model label alone does not identify its terrestrial frame
realization. Frame alignment to the rapid orbit/ray products is explicitly
`NOT_VERIFIED`; the RINEX approximate-coordinate frame and epoch are also not
established by these headers. The coordinate differences therefore mix possible
header age/approximation, frame, processing and physical site effects. Neither
daily products nor the original approximate coordinates are asserted to be
instantaneous truth. Product formal XYZ sigmas, about 0.17–0.63 mm here, are
retained as metadata, not physical coordinate accuracy or a covariance model.

The next useful trial is one coherent terrestrial frame/epoch and site-motion
model, followed by reference-only recalibration over broader geometry. Keep
receiver phase response separate from code response. This audit alone cannot
qualify target uncertainty or admit S3.

## Preserved execution and engineering repairs

Commit `db862b8ae1402f3024f369eecb70dde9ee728fe4` froze the guarded reference
replay and first station audit before execution. `reference_residual_structure_v2.py`
rejects mismatched dates, forbidden/missing/nonboolean causal flags, unequal
observation/calibration lengths, and unequal reference/residual lengths. These
address the late PR142 review. Its two v2 reports reproduce every original row,
omission, model comparison and descriptive result; no numerical conclusion changes.
The v1 sources/reports remain preserved; use the v2 entry point for further work.

PR142's post-merge Linux run also exposed a 1.31e-8 difference in a dimensionless
Pearson correlation. Only correlation replay tolerance changes to 1e-7; metre
comparisons remain at 1e-8 absolute with 1e-10 relative tolerance. No science
threshold, input, estimator or stored value is altered.

The first station audit records four comparisons and three `NOT_COMPARABLE`
marker-name failures per event. DRAO, STJO and YELL append descriptive text to
their marker codes. Commit `93e63e212ff6f62ce5f423c3ebe6dc38a31cbc80` preserves
those first reports and freezes the small v2 adapter before rerunning the audit.
The adapter accepts the exact first marker-name token, retaining the original
name and all DOMES/point/day/type checks. All fourteen then compare successfully.
No physical thresholds or station selections changed. Both report versions
remain available; `*_station_coordinates_v2.json` is the complete result.

Offline reproduction to fresh output paths:

```powershell
python -m research.exploratory.reference_residual_structure_v2 experiments/positioning_g14_doy246_network research/exploratory/inputs/timed_reference_products/g14 research/exploratory/inputs/reference_biases/g14 research/exploratory/inputs/reference_antennas/g14 research/exploratory/inputs/reference_attitudes/g14 research/exploratory/results/g14_reference_attitude_v1.json g14-reference-v2-replay.json
python -m research.exploratory.station_coordinates_v2 research/exploratory/inputs/station_coordinates/g14 experiments/positioning_g14_doy246_network/estimation/admitted.json research/exploratory/results/g14_reference_residual_structure_v2.json g14-station-replay.json
```

For G12 replace the archive with `research/exploratory/inputs/g12_doy248` and
the product/report tags with `g12`. These commands reject existing outputs.
Tests cover known-axis synthetic geometry, range sign, identity/epoch/unit
failures, poisoned excluded text, header-only parsing, forbidden causal flags,
length mismatches, complete accounting, input hashes and both report replays.
