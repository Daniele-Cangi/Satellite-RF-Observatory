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
**RINEX 2/3 GPS NAV**, such as NOAA's daily composite or a software receiver's
GPS-only export. Mixed-constellation NAV and RINEX 4 are rejected. Other observation signals
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

The original and perturbed matched satellite sets must be identical. A
single-satellite ramp needs at least one trained pair containing that satellite
at the evaluated epoch. Mere presence in the common satellite set is not enough:
`PERTURBATION_OUTSIDE_MATCHED_SUPPORT` also covers missing trained partners.
Missing support, a perturbation outside the scored pairs, changed admission, failed fits
and insufficient calibration remain inconclusive with their denominators.
The reference-disagreement diagnostic remains separate; it does not certify
the reference network or automatically identify which receiver is wrong.
Clock changes are retained, but no absolute-time authentication is inferred.

Original records are **unlabeled**, not certified benign: exceedances are not
measured false alarms. Software-ramp responses are not measured RF detection
rates. [The exposed-data exercise](../research/exploratory/PNT_COMPARISON_BENCHMARK.md)
retains the full comparison, including worse combined behavior and missed
common-clock modes. The `analyze` command's diagnostic contract is unchanged.

## Held-out reference transfer

```console
python -m pnt transfer 2024-09-11 LOCAL.crx.gz brdc2550.24n.gz --reference TRO1=TRO1.crx.gz --reference KIRU=KIRU.crx.gz --start 28800 --train-stop 30600 --stop 34200 --output transfer.json
```

This asks whether a component of local pair-residual variation can be predicted
from external pair residuals at later epochs. It compares three methods on
identical qualified pairs: no correction, subtraction of the mean external
innovation, and subtraction of a training-only learned multiple of that mean.
It introduces no detector threshold, attack verdict or false-alarm claim.

Pair-specific local and external medians use only the training interval.
For each qualified pair, let `u` be the centered local residual and `v` the
centered mean external residual. One zero-intercept coefficient is fitted as
`sum_epochs(mean_pairs(u*v)) / sum_epochs(mean_pairs(v*v))`. Each eligible
training epoch has equal weight; pairs remain correlated. Defaults require
five training samples per pair, six trained pairs at an epoch and 20 eligible
training epochs. The coefficient is applied unchanged after `--train-stop`.
There is no reference selection, clipping, regularization or evaluation tuning.
Insufficient training or zero remote training variation retains an explicit
inconclusive outcome without a coefficient fallback.

The report retains source hashes, baselines, the coefficient and training
products, every requested epoch, pair innovations/errors, model failures,
unsupported pairs and the clock/reference-disagreement diagnostics. Its main
continuous metric is RMS from the mean squared pair error at each epoch,
averaged equally over eligible epochs. It also retains per-epoch maxima,
improved/worsened/equal epoch counts and summaries by scored-pair count.
All three methods share the same support and denominators. Cardinality groups
describe changes in support; they do not establish independent measurements
or remove selection effects.

Local values are admitted in supervised training. This is not independent
target calibration or prospective confirmation. A smaller residual can result
from removing a shared model error or harmful manipulation; it does not prove
RF authenticity, accuracy or useful attack detection. Contaminated training
can teach a harmful correction. The slope has no qualified uncertainty bound.

The [two-window, three-receiver exercise](../research/exploratory/PNT_REFERENCE_TRANSFER.md)
retains all six comparisons. Unit subtraction worsens each comparison; the
learned slope gives small improvements and worsenings without a consistent
advantage. The previous comparison's thresholds and report remain unchanged.

The [short-baseline WegenerNet exercise](../research/exploratory/PNT_CLOSE_REFERENCE_TRANSFER.md)
reuses this command on three receivers 4.6–9.9 km apart in the same A/B windows.
Learned transfer improves aggregate MSE by only 0.372–2.287% in six comparisons;
unit subtraction worsens all six, and individual epoch worsenings are retained.
Earlier declared coordinates, original/converted inputs and the omitted final
epoch are preserved. This is a small descriptive effect, not detection benefit,
surveyed accuracy or RF authentication. No further slope search is warranted
on these windows; P2 still needs matched benign/challenge evidence.

## Decoded navigation witnesses

```console
python -m pnt navigation 2012-09-14 LOCAL.12n.gz --witness NOAA=EXTERNAL.12n.gz --start 43200 --stop 50400 --output navigation.json
```

This compares locally declared **decoded navigation messages** with explicitly
supplied external archives. It accepts plain/gzipped RINEX 2/3 GPS NAV, using
the existing block normalizer. It does not require external residuals to
predict local noise. At least one named `--witness NAME=PATH` is required;
names and differing file hashes do not certify independent physical sources.
Identical input hashes and duplicate external content are exposed in coverage.

Messages are matched by satellite, GPST `toc`, continuous week, `toe`, IODE
and IODC. No nearest-message substitution is performed when that issue is
missing. All 27 clock/orbit-1..6 fields are retained, including unhealthy
records, IODC and L2 flags that orbit fitting does not use. Integer fields are
compared exactly; other fields allow only rounding to the last written decimal
digit. Duplicate issues must have compatible field intervals. Different
transmission times and optional derived fit durations are not payload conflicts;
ionosphere/UTC headers and spare fields are outside this first comparison.

Each local record whose `toc` lies in the requested half-open GPST window is
retained with its source index, fields and every witness's matching records.
Outcomes are `COMPATIBLE_WITH_EXTERNAL`, `DIFFERENT_FROM_EXTERNAL`,
`INSUFFICIENT_EVIDENCE`, `CONFLICTING_LOCAL_RECORDS` or
`EXTERNAL_RECORD_CONFLICT`. Missing witnesses remain visible; agreement is
conditional on witnesses that contain that same issue. Conflicting witnesses
are not resolved by majority voting. Structural/nonfinite/missing required
fields are input errors rather than silently discarded records. These are
message diagnostics, not ALLOW/BLOCK or RF-authenticity verdicts.

The [public RF reference exercise](../research/exploratory/PNT_PUBLIC_RF_NAVIGATION.md)
decodes a freely available recording with GNSS-SDR and feeds its GPS-only
RINEX 3 export into this same command. All five exported messages differ from
the NOAA archive. Receiver export errors, archive serialization and L2-code
disagreement remain visible; none is labeled a spoofing detection. Do not
assume that a software receiver's NAV export preserves every broadcast field.

The [first mechanism exercise](../research/exploratory/PNT_NAVIGATION_WITNESS.md)
shows why the comparison can add information: a software change in all
satellite clock biases can enter the local receiver-clock fit while leaving
geometry almost unchanged, yet differ from external message fields. It uses
real archived codes with **synthetic local navigation variants**, not a
recorded RF attack. Unchanged messages can accompany harmful RF manipulation;
a match does not authenticate pseudoranges, freshness, position or absolute time.

For a receiver's raw UBX recording, select the adapter explicitly:

```console
python -m pnt navigation 2024-09-11 capture.ubx --local-format ubx --witness NOAA=brdc2550.24n.gz --output navigation-ubx.json
```

This supports **RXM-SFRBX version 2, GPS L1 C/A LNAV**. Other GNSS/signals
are counted rather than interpreted as LNAV. It reuses the existing UBX packet
reader and the same issue/field comparator. It decodes all 27 fields from
complete subframes 1/2/3 for the same satellite and HOW 30-second cycle, with
consistent IODE/IODC. Missing pieces are never borrowed from another cycle.
Repeated frames and conflicts, incomplete cycles, raw GPS payloads and packet
indices remain in `sources.local`; decoded records link back to their cycle.
The conservative cycle rule limits coverage when receiver output is sparse.

UBX mode retains **every decoded issue in the file**, including `toc` outside
the declared day. `--start`/`--stop` windows are unavailable in this mode: the
message's own time must not hide an anomalous message, and capture time is not
qualified. The supplied GPST day resolves only the 1024-week era. The v2 report
has `selection=ALL_DECODED_UBX_ISSUES`, a null window, and counts decoded `toc`
outside that day. The RINEX v1 contract and its `toc` selection are unchanged.

Bad UBX checksums reject the input by default. `--recover-corrupt` explicitly
excludes and counts damaged packets; they never become evidence. Receiver
parity processing is reported by u-blox; the adapter does **not independently
validate RF parity or authenticate the receiver output**. It strips padding
and parity from already de-inverted data. Binary scales are exact; semicircle
conversion uses decimal pi with a numerical bound of 1e-58 rad (or rad/s).
URA is mapped to ICD nominal metres; unavailable URA/TGD and malformed
reference times retain an unusable-cycle outcome. RINEX written precision can
limit a field comparison, especially zero coefficients with coarse exponents.

The [actual JammerTest 2.1.1 comparison](../research/exploratory/PNT_NAVIGATION_JAMMERTEST_211.md)
retains three complete cycles and 204 incomplete cycles: two complete issues
match NOAA; a third declares 1 October in an 11 September capture and lacks a
same-issue witness. This is missing corroboration, not a matched-field conflict,
qualified attack attribution or measured incremental detection benefit.

## LNAV representation qualification

Add `--qualify-lnav` to `navigation` to retain the existing written-decimal
comparison and add encodable-value qualification under schema v3:

```console
python -m pnt navigation 2024-09-11 capture.ubx --local-format ubx --witness NOAA=brdc2550.24n.gz --qualify-lnav --output NEW.json
```

Each written interval must contain exactly one GPS LNAV value. Zero or
multiple candidates, invalid L2-code metadata and unavailable URA/TGD remain
unqualified. The report retains all fields, duplicates, conflicting witnesses
and missing issues. It never selects the nearest integer, infers lost precision
or repairs exported fields. Unique agreement is conditional representation
agreement, not source independence, freshness, RF authentication or an allow
verdict. With the flag absent, v1/v2 output stays unchanged.

The representation profile V2 uses exact rational bounds and a candidate-scaled
pi interval; it adds no fixed angular tolerance, including around zero.
For UBX, complete issues with unavailable URA/TGD also receive field diagnostics
while retaining their original unusable-cycle outcome. These rows have a
`representation_record_index` and `sfrbx_cycle_index`; `local_record_index` is
null when the prior comparator rejected the issue, with the reason retained
as `written_decimal_rejection`. Structural/issue/time checks are still required.

The [exposed RF qualification](../research/exploratory/PNT_NAVIGATION_REPRESENTATION.md)
retains all five native discrepancies and marks the archived representations
unqualified. The subsequent [GFZ NavBit intake](../research/exploratory/PNT_GFZ_NAVIGATION_WITNESS.md)
retains transmitted words from one public Internet provider: all 27 fields
agree in each of the ten complete exposed CTTC cycles. The reusable
`pnt.lnav.decode_lnav_words` checks parity and de-inverts transmitted words;
it must not be applied to already recovered receiver output. This is offline
fixture intake, not a new CLI adapter. NOAA conflicts and the five incomplete
local cycles remain visible; source independence and a matched benign/attack
comparison remain open before measuring detection benefit.

`pnt.gfz_navbit.read_gfz_navbit_issues(path)` now reads one local daily GFZ
NetCDF-v1 `.nc.gz` member into representation rows and a complete CEI outcome
trace. It checks parity, slot order, metadata and HOW, retaining mixed issues,
incomplete cycles and invalid frames. All 2,880 daily cycles remain in the
denominator, including those whose SF1–SF3 rows are entirely absent.
Unavailable URA/TGD stay diagnostic rows
and require representation qualification; they are not admitted accuracy bounds.
The [recorded-attack test](../research/exploratory/PNT_GFZ_RECORDED_ATTACK.md)
finds two matching JammerTest cycles and one missing future-dated issue.
One match occurs in the provisionally associated attack ramp. Matching NAV
must not produce an RF authenticity/allow verdict. This API adds no downloader,
tar extraction or CLI format fallback.

## Paired navigation comparison

```console
python -m pnt navigation-compare 2024-09-11 LOCAL.crx.gz ORIGINAL.n.gz --case altered LOCAL.crx.gz ALTERED.n --witness NOAA=ORIGINAL.n.gz --start 28800 --calibration-stop 30600 --stop 34200 --output comparison.json
```

Each repeated `--case NAME OBS NAV` supplies an observation file and its
navigation hypothesis. A case can reuse the original observations or supply
a retained variant. This supports the same RINEX 3 GPS C1C/C2W observations
and RINEX 2/3 GPS NAV as the fixed-site diagnostic. It uses one original antenna
coordinate in every case; other observations must declare the same receiver
marker. An explicit `--local-ecef` needs `--position-source`.

Two local scores are the largest minus smallest satellite residual, and the
absolute fitted-clock change between consecutive 30-second grid epochs.
Original-only calibration uses the prefix ending at `--calibration-stop`,
with at least 20 epochs where both scores exist. Default thresholds are the
95% nearest-rank quantiles; exceedance means strict `>`. The union of the two
controls has no prescribed combined false-alarm rate. Candidate values and
later original values never set these thresholds. No gap is bridged for a
clock step. A partially scored epoch retains its available diagnostic but
does not enter the paired two-control comparison.

Every requested epoch remains visible. Cases are fitted independently; a
changed satellite set at this or the preceding epoch makes the comparison
inconclusive rather than reducing both fits to a passing intersection.
All NAV records are compared without a `toc` filter. Per-epoch external
content evidence refers only to source indices used by that local fit;
unused contradictions cannot create evidence for the scored satellites.
Missing issues, conflicting records, all-unhealthy inputs, model failures,
partial controls and unsupported comparisons are retained without fallback.
`navigation_comparison` retains the complete message evidence separately.

Reports contain the original and each supplied case, hashes, used NAV indices,
per-satellite residuals, fitted clocks, control scores/thresholds, witness
outcomes and counts on identical paired support. Counts of external message
discordance while these local controls stay quiet are **not** RF detections.
Passing two controls does not establish plausibility under C/N0, Doppler,
PVT, receiver flags, oscillator specifications or other local checks.
Matching messages cannot authenticate changed ranges. Absolute time and
source independence remain unqualified.

The [six-case exercise](../research/exploratory/PNT_NAVIGATION_COMPARISON.md)
uses already exposed public observations with five supplied software variants.
It includes both common-clock changes and negative controls; the earlier
JammerTest result and its report replay are unchanged. A matched physical
benign/attack recording remains the next P2 evidence requirement.
