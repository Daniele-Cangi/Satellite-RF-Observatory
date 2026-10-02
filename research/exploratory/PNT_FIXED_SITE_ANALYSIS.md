# Fixed-site analysis: software exercise on already exposed observations

The reusable [`pnt` command](../../pnt/README.md) advances the offline path from
coverage intake to model diagnostics. It accepts local and external files
without experiment-specific station names, attack labels or a clean
counterfactual. The former TEXBAT clock fit and NAV adapter are shared
primitives; replaying that study produces its unchanged historical JSON.

For software qualification we used the same three BKG observation files as
the [earlier intake](PNT_FIXED_SITE_INTAKE.md): NYA200NOR as an exercise local
receiver, TRO100NOR and KIRU00SWE as external receivers on 2024-09-11. The
window is 08:00–08:10 GPST, selected as a short execution exercise on exposed
data, not selected blindly as a benign or attack episode. GPS broadcast NAV
comes from [NOAA's daily composite](https://noaa-cors-pds.s3.amazonaws.com/rinex/2024/255/brdc2550.24n.gz).
The [complete report](results/pnt_fixed_site_analysis_2024255_v1.json) retains
all four source hashes, coordinates, exclusions and every requested epoch.

All **20 requested epochs** have matched fits, with 8–9 common GPS satellites
above 10 degrees at all three sites. The largest absolute mean modeled double
difference is 7.03 m, and the largest pairwise external satellite-difference
disagreement is 10.85 m. Both named reference channels are preserved so that
their mean cannot hide disagreement. These are descriptive model residuals,
not accuracy, benign population statistics, false-alarm rates or an attack
decision. No numerical cutoff was inferred from this exercise.

Positions are header-derived approximate antenna points. There is no
independent ground survey, acquisition clock, attack schedule or local victim
under a documented challenge. The local/external files share the BKG delivery
path; separate physical markers do not establish independent clocks or
provider trust. NOAA NAV is an admitted common hypothesis, not a separately
verified orbit. The receiver-clock contrasts remain GNSS-derived.

The result is **reusable offline incident diagnostics**, with missing evidence
explicit. It adds no detection-gain claim and does not close the decisive P2
comparison. The next scientific evidence still needs a matched benign/challenge
recording with plausible local controls and independent truth; a new wrapper
or another locally obvious episode does not supply that information.

## Reproduce

Obtain the three exact files linked by the [intake](PNT_FIXED_SITE_INTAKE.md)
and the NOAA file above, then run at this repository revision:

```console
python -m pnt analyze 2024-09-11 NYA200NOR_R_20242550000_01D_30S_MO.crx.gz brdc2550.24n.gz --reference TRO1=TRO100NOR_S_20242550000_01D_30S_MO.crx.gz --reference KIRU=KIRU00SWE_R_20242550000_01D_30S_MO.crx.gz --start 28800 --stop 29400 --output NEW_REPORT.json
```

The original compressed observation bytes match the earlier intake hashes.
Repeated execution produces identical report bytes. This is software
qualification on exposed data, with no new prospective experiment.
