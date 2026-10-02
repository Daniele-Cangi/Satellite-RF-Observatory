# Offline fixed-site PNT diagnostics

`python -m pnt analyze` turns one local receiver recording, at least two
external recordings and a declared broadcast navigation model into one JSON
report. It is a reusable diagnostic tool for the PNT plan's offline path.
It does not yet implement a qualified spoofing detector or absolute-time
verification. No detector threshold, benign label or attack verdict is inferred.

Install `requirements-positioning.txt`, then run from the repository root:

```console
python -m pnt analyze 2024-09-11 LOCAL.crx.gz brdc2550.24n.gz --reference TRO1=TRO1.crx.gz --reference KIRU=KIRU.crx.gz --start 28800 --stop 29400 --output incident.json
```

Inputs are GPS C1C/C2W observations in RINEX 3, plain, gzip or Hatanaka as
supported by the existing decoder. Epochs must follow the 30-second GPST grid
within the existing 0.001-second tolerance; no resampling, retiming or alternate
signal fallback is performed. Navigation currently accepts plain or gzipped
**RINEX 2 GPS NAV**, such as NOAA's daily composite. Other observation signals
and navigation formats require a qualified adapter. Applied code/clock
corrections and nonordinary events need explicit interpretation and are rejected
by the shared observation reader.

The observation layout follows the [IGS RINEX 3.05 specification]
(https://files.igs.org/pub/data/format/rinex305.pdf); this tool admits the subset
above, not every format or signal described by that specification. These
diagnostics open observation values and do not implement prospective blinding.

Navigation selection keeps the nearest healthy `toc` record and requires both
its absolute clock-reference age and orbit-reference (`toe`) age to be at most
7,200 seconds from the observation. The `toe` age is also capped by half the
declared fit duration, in hours per [RINEX 2.11, section 6.6]
(https://files.igs.org/pub/data/format/rinex211.txt), when supplied. This is a
symmetric age admission guard around `toe`, not a reconstruction of the exact
broadcast transmission/curve-fit interval. Unknown fit duration retains the
two-hour cap; invalid duration is rejected. An inadmissible nearest record is
reported as an exclusion rather than silently replaced by another record.

`--start` is inclusive and `--stop` exclusive, in seconds of the declared GPST
day. The report retains **every requested grid epoch**, including intervals
without local observations, remote support or usable ephemerides. Input errors
exit nonzero; insufficient coverage produces a report rather than a success
verdict. Existing output files are never overwritten. This command reads local
files; obtain and retain the original sources separately under their data terms.

By default antenna ECEF comes from RINEX approximate XYZ plus antenna H/E/N.
That is a source declaration, not independent position truth. Supply a distinct
antenna coordinate with `--local-ecef X Y Z --position-source "source and frame"`
when available. The coordinate refers to the antenna point, not the marker, and
is used as supplied. No terrestrial frame transformation or survey validation
is performed. Remote positions retain their header provenance.

## What the report contains

- Hashes of the exact compressed/plain input bytes that were decoded, marker
  identities, coordinate sources and full-file parser exclusion counts.
- Per-epoch standalone fits for each receiver on its own admitted satellites.
  These preserve local diagnostics when the network is unavailable.
- Separate fits on the **identical common satellite set** for the local and
  external receivers, with median common clock terms and satellite residuals.
  Use this matched section to compare channels; standalone sets can differ.
- Modeled ionosphere-free double-difference residuals against each named
  reference, the declared lowest common reference PRN, their arithmetic mean
  and pairwise reference disagreement. Opposing reference errors remain visible.
- Relative clock contrasts in metres, kept separately from the differenced
  geometry. All those clocks derive from GNSS and the same broadcast model.
  Absolute time stays `INSUFFICIENT_EVIDENCE` without an independent witness.
- Missing/stale navigation, low-elevation exclusions and failed clock fits.
  The minimum four satellites and 10-degree mask are model admission rules,
  not attack-detection thresholds.

The code reuses the repository's propagation, Earth rotation, simple
troposphere, RINEX reader and median clock fit. Remote numerical fits use only
their own codes. Matched satellite selection depends on support and elevation
at all receivers; standalone remote fits do not depend on local support.
It does not claim an uncertainty envelope: antenna metadata,
signal biases, ionosphere-free noise amplification, propagation error, time
tagging and shared source dependencies remain unqualified. A high residual
can describe a fault, propagation error or manipulation; a small residual
does not authenticate RF origin. `DIAGNOSTICS_AVAILABLE` means calculations
were obtained for at least one matched epoch. The report leaves model
consistency and detection benefit `NOT_ASSESSED` and exposes its denominator.

## Reproduction and validation

Rerun the same command into a new file using the recorded input hashes and the
same repository revision. Git history and these inputs support reproduction;
there is no additional seal, authority or replay layer.

The [public-data software exercise](../research/exploratory/PNT_FIXED_SITE_ANALYSIS.md)
documents a 10-minute window on the previously exposed three-station corpus.
The historical ds7 clock study now shares the fit/navigation primitives and
still reproduces its original report byte for byte.

```console
python -m pytest pnt/tests research/exploratory/tests -q -k "pnt or fixed_site"
```

Linux/Windows CI includes the new tests alongside all existing suites. Tests
cover actual parser-to-model execution, common clock cancellation, local
anomalies leaving remote fits unchanged, opposing remote errors, missing
sources/navigation, invalid inputs and preservation of failed epochs. These
synthetic checks qualify implementation behavior, not detection performance.

## Development comparison

```console
python -m pnt compare 2024-09-11 LOCAL.crx.gz brdc2550.24n.gz --reference TRO1=TRO1.crx.gz --reference KIRU=KIRU.crx.gz --start 28800 --train-stop 30600 --calibration-stop 32400 --stop 34200 --output comparison.json
```

This reads the same original inputs once and compares local geometry, mean
external geometry, their difference and disagreement between references.
It uses all available satellite pairs, without depending on a changing
reference PRN. Each score is the maximum absolute innovation from the
training median for each pair. Pairs need five training epochs by default;
an epoch needs at least six trained pairs. Unsupported pairs are counted.
Pair count and geometry can vary with time; no uncertainty normalization or
claim of independent pair measurements is made.

The three windows are chronological and disjoint: baseline fitting, empirical
threshold calibration, then evaluation. Defaults use the 95th-percentile
nearest-rank calibration score, at least 20 eligible calibration epochs and a
strict `score > threshold` comparison. Each method has the same calibration
tail budget and uses the same eligible epochs. Ties and distribution shifts
can yield different actual exceedance counts: the report retains those counts,
including original evaluation counts on each challenge's exact support. No
threshold is adjusted using evaluation data. These are development thresholds,
not qualified detector operating points or measured false-alarm guarantees.
The evaluation window requires at least two grid epochs for distinct ramp endpoints.

Five software ramps are applied **before** fitting: one local satellite,
local modeled geometry displacement, a common local code/clock offset, one
satellite shared across receivers, and one satellite at one external receiver.
Both C1C and C2W receive the same added range; tracking, phase, signal quality,
navigation bits and receiver PVT are not simulated. The geometry ramp adds
the existing model's range difference between the declared antenna and a
displaced ECEF hypothesis at the supplied code and zero nuisance clock. It
is a model perturbation, not a complete RF position-spoofing simulation.

Default ramp endpoints are 2, 5 and 10 metres, from zero at the first evaluation
epoch to full amplitude at the last requested epoch. Use repeated `--amplitude`
to specify different endpoints and `--direction-ecef X Y Z` for the normalized
displacement direction (default ECEF +X). The satellite is chosen only from
training support, ties by PRN, unless `--satellite Gxx` is explicit. The
reference fault affects the first named external receiver in lexical order.
Those choices are retained in the report; they are not searched for a success.

The original and perturbed matched satellite sets must be identical. Missing
support, a perturbation outside the common set, changed admission, failed fits
and insufficient calibration remain inconclusive with their denominators.
The reference-disagreement diagnostic remains separate; it does not certify
the reference network or automatically identify which receiver is wrong.
Clock changes are retained, but no absolute-time authentication is inferred.

Original records are **unlabeled**, not certified benign: exceedances are not
measured false alarms. Software-ramp responses are not measured RF detection
rates. [The exposed-data exercise](../research/exploratory/PNT_COMPARISON_BENCHMARK.md)
retains the full comparison, including worse combined behavior and missed
common-clock modes. The `analyze` command's diagnostic contract is unchanged.
