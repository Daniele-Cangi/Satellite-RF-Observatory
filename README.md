# Satellite RF Observatory

Reconstruct satellite positions from public RF observations obtained through
the Internet, without supplying the target's orbit to the calculation. Declare
uncertainty before testing an excluded receiver and opening an orbit reference.

The active objective is a new real positioning event that passes both a
prospective 10 km uncertainty criterion and an eventual 10 km position-error
criterion. The project is research software, not yet a general verification
service. The future website will publish positions with their measurements,
uncertainties, withheld tests and reproducible evidence, including failures.

## Current evidence

| Experiment | What was measured | Frozen outcome |
|---|---|---|
| DRAO labelled-forward DOY234 | A known orbit predicts held-out RF dynamics better than the frozen alternatives | `ORBITAL_MODEL_PREDICTIVELY_PREFERRED`; closed |
| G08 DOY249 inverse | 188.705 m orbit error; 1.849 m excluded-GOLD residual; 21.608 km prospective uncertainty radius | `UNCERTAINTY_TOO_LARGE`; closed |
| G12 DOY250, seven fit roots | Eight sources individually contain G12, but only 18 consecutive common epochs against a required 41 | `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`; closed before fit/oracle |

The small G08 error did not override its uncertainty failure. The G12 attempt
adds southern stations to address radial/clock degeneracy, but its predeclared
common support block was absent. It yielded no new position. Neither old result
has been reopened or improved after confirmation.

- [Active mission and operating rules](AGENTS.md)
- [Active positioning implementation](positioning/README.md)
- [Closed G08 experiment](experiments/gnss_inverse_positioning/README.md)
- [G12 plan](experiments/positioning_g12_doy250/plan.json)
- [G12 outcome and physical interpretation](experiments/positioning_g12_doy250/OUTCOME.md)

## Calculation before comparison

```
frozen experiment plan
  -> Internet RF measurements and non-target clock references
  -> offline xyz + emission time + uncertainty
  -> frozen solution, input hashes and excluded-receiver prediction
  -> excluded receiver, then external orbit comparison
  -> complete result and downloadable evidence
```

Terrestrial coordinates and explicitly non-target satellite ephemerides are
allowed calibration inputs. Target navigation blocks are removed before
numerical parsing. The estimator does not receive target orbit/clock products
or the excluded receiver's target values. The verification stage checks the
freeze and never fits the position.

This is target-state independence, not absence of all reference ephemerides.
Receiver labels do not independently establish satellite identity. The IGS
oracle may share underlying station observations; statistical disjointness is
not claimed. Numerical uncertainty remains conditional on its declared model.

## Run and test

Python 3.13, from this checkout:

```powershell
python -m pip install -r requirements-positioning.txt
python -m positioning acquire experiments/positioning_g12_doy250/plan.json work/g12_reproduction
python -m positioning estimate work/g12_reproduction
python -m positioning verify work/g12_reproduction
python -m pytest positioning/tests experiments/gnss_inverse_positioning/tests -q
```

These commands reproduce the closed G12 qualification failure. They do not
silently switch to another event. A new scientific attempt requires its own
predeclared plan and unexposed confirmation evidence. On a sandbox restricting
the system temporary directory, add `--basetemp work/pytest-positioning-local`
to the test command with a dedicated workspace directory.

The dedicated CI workflow tests the active package and frozen G08 regression on
Windows and Linux. Local test results and remote CI execution are distinct.

## Next physical work

The G12 outcome showed that the chosen twenty-minute support requirement was
too restrictive for the available common observations. It is not a mathematical
minimum for snapshot positioning. Justify the necessary interpolation/clock
support duration before preregistering a new event; retain the closed plan and
failure rather than shortening its rule after access.

Software work must serve that next physical result. Date, GPS week, target,
station roles and time window are explicit inputs. Frozen experiments stay
separate from the active implementation. Product interfaces, monitoring and
infrastructure follow supported scientific claims.

## Historical work

The forward-orbit and measurement-integrity experiments remain available under
`experiments/orbital_discriminability/` and `experiments/live_instrument/`.
Their former roadmap is archived in
[the previous project README](docs/history/README_forward.md). It does not
override the current independent-position mission in `AGENTS.md`.

Licensed under [Apache 2.0](LICENSE).
