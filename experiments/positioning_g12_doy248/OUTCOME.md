# G12 DOY248 — new independently reconstructed position

**Frozen terminal: `UNCERTAINTY_TOO_LARGE`; primary_pass = false.**

A new position was calculated from public RF pseudoranges without G12 orbit or
clock products in estimation. The subsequently revealed orbit comparison gave
**15.139240688 m** 3D error. Excluded GOLD was confirmed with a **-3.136704572 m**
residual. The prospectively frozen uncertainty radius was **10,121.468778325 m**,
above the unchanged 10,000 m limit. The good comparison does not reverse that
failure; the position-demonstration milestone has not passed.

## Event and information order

- Target: receiver-labelled G12; date 2026-09-05 GPST.
- Fit: ALGO, DRAO, STJO, YELL, BOGT, BRAZ, AREQ; excluded receiver: GOLD.
- First structurally qualified window: 10:30:00–10:35:00 GPST, eleven samples.
- All eight non-target receiver-clock/ground-coordinate calibrations qualified.
- Estimated emission: 37,949.92176914985 s after GPST midnight.
- Estimated ECEF at emission: [-9,784,123.26287933,
  -24,686,516.3765085, -103,977.30517087923] m.

The estimator's frozen xyz uses axes fixed at u0; the ECEF coordinates above
apply the declared Earth-rotation conversion to emission axes for comparison.
The conversion is not an oracle-fitted alignment.

1. Plan and implementation pushed as `118c683c8a826343212649b1b54036d7dbc7afda`.
   GitHub CI creation: 2026-09-08 23:29:08 UTC; local plan freeze: 23:29:22 UTC.
2. Offline solution freeze: **2026-09-08T23:30:50.972190+00:00**.
3. Solution and source snapshots pushed as
   `622ea88d8f13071ace56e584b13b2f91f7e559c7` before confirmation. Its GitHub CI
   creation is recorded at 23:31:35 UTC.
4. GOLD reveal: **2026-09-08T23:31:52.424993+00:00**.
5. Oracle receipt: **2026-09-08T23:31:53.138407+00:00**.

Solution SHA-256:
`59db724da7f701682f1c7ea82a697cfbab6fc396538a02f64c7be3e7e2b9d1e0`.
Plan SHA-256:
`5289e1098f25cc6e6217ca5a5d2760e19045194735120cd3d69f3a4a3b9c572e`.

GitHub publication and local receipts support the recorded order; they do not
prove absence of every possible prior human access or constitute a formal
independent timestamping service. Source snapshots preserve the executed bytes.

## Frozen uncertainty and confirmation

| Quantity | Value | Assessment |
|---|---:|---|
| Statistical 95% numerical extent | 5,589.162 m | Conditional model |
| Maximum sampled systematic displacement | 4,050.332 m | Finite bias probes |
| Declared numerical margin | 1.05 | Retained |
| Total prospective radius | 10,121.469 m | Fails <=10,000 m |
| Excluded-GOLD residual | -3.137 m | Passes 100 m and 164.517 m predictive band |
| External orbit 3D error | 15.139 m | Passes 10 km and frozen-radius consistency |
| Nine/eight-node oracle interpolation control | 0.00716 m | Passes 10 m |

The effective code sigma remains 20 m. The full receiver/ground/reference
covariances, all 128 bias corners, 64 deterministic interior probes and axis
profiles are retained in `solution.json`. Only one admissible branch was found;
the numerical branch/axis search is not a proof of global uniqueness or 95%
population coverage. The inferred radial-distance/clock correlation remains
-0.999901689. Independent reference ephemerides are allowed calibration inputs.

## What changed physically and what remains unresolved

The earlier DOY250 experiment stopped at its 41-epoch support rule. This
separately declared DOY248 event used the eleven epochs needed by the local
interpolation and per-epoch clock calibration; see `SUPPORT.md`. It successfully
reached new position estimation and unexposed confirmation. The total radius
is lower than G08's 21.608 km, but different target/day/network mean this is not
a controlled causal estimate of the station improvement.

The remaining failure is prospective uncertainty, not the observed 3D error,
structural availability or receiver confirmation. Being only 121.469 m above
the threshold does not justify deleting the margin or reducing uncertainty.

A further bounded event should investigate additional independent terrestrial
geometry or a separately validated calibration-error model. Any such change
must be declared before its new confirmation evidence is opened. Do not reopen
this event, select another window here or turn repeated attempts into a hidden
search for a passing example.

This is one historical receiver-labelled GPS position. It provides no velocity,
autonomous identity, live-service guarantee or population reliability claim.
The independently produced IGS orbit may share underlying station observations;
statistically disjoint oracle data are not claimed.

G08, G12 DOY250 and the closed DRAO result remain unchanged.
