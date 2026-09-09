# G14 DOY246 — conditional one-event demonstration

The preregistered availability-to-position request completed all frozen criteria.
Status: `INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED`, `primary_pass=true`.
Prerequisite commit `ad70eff5e59138d13dafa711e2f4ab586d75516f` was pushed before acquisition.
Plan SHA-256: `e6cdea397bde4226fcaa491ee033b672f2159b3531e1dba607d850feba0734d5`.

## Independent result and confirmation

- Target G14, 2026-09-03 GPST; emitted event at 14249.930249678 seconds after GPST midnight (03:57:29.930249678 GPST).
- Estimated ECEF at emission: [-5576672.269816278, -14732618.65743286, 21508680.23801228] metres.
- Post-freeze external orbit 3D error: **31.016966 m**, limit 10,000 m.
- Prospective conditional 95% numerical radius: **5755.157156 m**, limit 10,000 m.
- Excluded GOLD residual: **-0.845590 m**; within both 100 m and the frozen 124.397192 m predictive band.
- All eight receiver calibrations qualified. Fit ambiguity flag false; fit residuals below 0.44 m; minimum fitted elevation 19.49 degrees.
- Oracle interpolation control: 0.006090260 m, limit 10 m.

The reported uncertainty retains 20 m code floor, 5 m shared-reference and
ground-coordinate terms, +/-20 m per-root systematic probes and the 1.05 margin.
Its components were 2991.964917 m
statistical extent and 2489.137136 m
maximum sampled bias displacement. No floor, threshold, station subset or event
was changed after inspecting the fit or confirmation.

## Availability and selection

The frozen pool contained ALGO, AMC4, AREQ, BOGT, BRAZ, DRAO, MKEA, PIE1,
STJO and YELL, with GOLD fixed as the excluded receiver. The exact expected
AMC4 observation filename returned HTTP 404; its absence was handled by the
predeclared rule, without trying alternative filenames or sources.

At the first qualifying window, 03:55–04:00 GPST, the selected fit stations
were ALGO00CAN, BOGT00COL, DRAO00CAN, MKEA00USA, PIE100USA, STJO00CAN, YELL00CAN.
Their maximum terrestrial baseline was 8517.361 km and geocentric latitude
span 57.714 degrees. Selection used field presence and terrestrial header
metadata, never target orbit or numeric target-fit quality. No second network
or window was attempted after this choice.

## Freeze and reveal order

- Plan freeze: 2026-09-09T08:12:13.071875+00:00.
- Solution freeze: 2026-09-09T08:14:24.411590+00:00.
- Excluded receiver reveal: 2026-09-09T08:14:28.274729+00:00.
- Oracle access: 2026-09-09T08:14:28.955617+00:00.
- Frozen solution SHA-256: `ed0e06d1ce7dadca42672f7a0c0699b0e1cea14c60fb7e4a9fc6a72489c94eb9`.

The reference-only navigation excludes G14 before numerical parsing. Admitted
reference observations contain no G14 values; excluded GOLD target values are
absent from the estimator packet. The solution and all recorded input hashes
were checked again when archiving. Job stages ran in separate processes; the
estimation CLI denied Python sockets and subprocess creation.

## Scope and reproduction

This is one receiver-labelled historical GPS snapshot under the declared
conditional model. Finite bias probes and axis profiles do not certify global
confidence bounds or population 95% coverage. The oracle may share ground
measurements with the experiment. This is not a velocity/orbit solution, an
autonomous identity determination, a universal accuracy claim or proof of a
globally unique service. The 31 m observed error is not a prospective 31 m guarantee.

The original G08, G12 and G13 outcomes remain unchanged. This directory retains
the exact plan, availability scan, admitted data, source snapshots, calibration,
frozen solution, confirmations, terminal seal and dossier. Raw compressed
observations and SP3 are preserved in the full downloadable ZIP and local run.
The published website remains the earlier read-only archive; this change does
not yet provide web job submission or publish this new event to that site.
