# Active inverse-positioning code

The network-availability path has now completed a new preregistered G14 DOY246
event with all declared criteria met: 31.017 m observed 3D error, 5755.157 m
prospective conditional uncertainty radius and -0.846 m excluded-GOLD residual.
The first eligible eleven-epoch window selected seven roots from the frozen
ten-station pool; no later network/window was tried. See
`experiments/positioning_g14_doy246_network/OUTCOME.md`. This is one conditional
historical demonstration, not a general accuracy or coverage guarantee.

This is the small active implementation for the independent-position mission
in the root `AGENTS.md`. The original G08 implementation remains frozen under
`experiments/gnss_inverse_positioning/`.

The first active real-data attempt is G12 DOY250 with seven fit receivers and
GOLD held out. It closed at structural admission: 18 consecutive common epochs
were available, below the predeclared 41. No new position or oracle comparison
was produced. See `experiments/positioning_g12_doy250/OUTCOME.md`.

The separately preregistered G12 DOY248 eleven-epoch attempt completed the full
real-data pipeline: 15.139 m external orbit error and -3.137 m excluded-receiver
residual. Its 10.121 km prospective uncertainty exceeded the fixed 10 km limit;
the primary outcome remains `UNCERTAINTY_TOO_LARGE`. See
`experiments/positioning_g12_doy248/OUTCOME.md`.

The configurable G13 DOY247 request completed without manual stage transitions.
All eight source files arrived, but no eligible epoch was common to all roots;
the terminal is `SOURCE_OR_MEASUREMENT_NOT_QUALIFIED`. No position or oracle
access followed. Its immutable dossier and source snapshots are under
`experiments/positioning_g13_doy247_request/`. This verifies a real negative
request path; it is not a new numerical positioning result.

## Portable execution

### Availability and predeclared station pools

`gps-code-network-v1` accepts 7–12 candidate fit stations and a fixed excluded
receiver. It selects exactly seven fit stations at the first eleven-epoch
30-second window available across those roots and the excluded receiver.
At that time it chooses the first lexical subset meeting >=2000 km maximum
terrestrial baseline and >=20 degrees geocentric latitude span. Header positions
must have finite terrestrial radii (6000–6500 km). These are ground-distribution
requirements, not an assurance of target observability or position accuracy.

```powershell
python -m positioning plan G14 2026-09-03 work/network-plan.json --pool ALGO00CAN DRAO00CAN STJO00CAN YELL00CAN BOGT00COL BRAZ00BRA AREQ00PER AMC400USA PIE100USA MKEA00USA --prior-access "Declare actual exposure; this command alone does not certify blinding."
python -m positioning availability work/network-plan.json work/network-run
python -m positioning run work/network-plan.json work/network-run
```

The optional availability stage freezes the plan and source implementation,
downloads only observation files, scans field presence and terrestrial header
coordinates, and writes `availability.json` with per-station reasons and the
selected network/time. It never parses numerical target observations or accesses
navigation/orbit files. A valid availability check can be promoted to a job
without changing the frozen plan or implementation. Acquisition verifies cached
raw bytes and reproduces the selected network before admitting target values.
Running a job directly performs the same selection automatically.

An HTTP 404 or unsupported structural header makes that candidate unavailable;
other transport failures stop the request. The excluded receiver cannot be
replaced. A malformed compressed payload stops as an engineering/source-decoding
error for inspection. No second subset/window is tried after calibration or fit
failure. The estimator re-derives the selected roles from the frozen structural
record; the uncertainty floors and confirmation thresholds are unchanged.

Availability means only that this declared network/window can proceed to
calibration. It does not mean a satellite position has been verified. The closed
G13 DOY247 request must not be reopened under this new selection rule.

### Configurable request (current product slice)

The `gps-code-snapshot-v1` profile fixes the physical model, eleven-epoch
selection, calibration and uncertainty/confirmation criteria. Target, historical
GPST date and 5–8 fit station IDs plus a distinct excluded station are explicit.
URL generation includes the GPS-week rollover. Unsupported settings and arbitrary
source URLs are rejected before a job starts. Prior exposure must be declared;
the software cannot certify that a person has never seen an event's orbit.

```powershell
python -m positioning plan G13 2026-09-04 work/example-plan.json --prior-access "Example only: declare actual prior exposure before an experiment."
python -m positioning run work/example-plan.json work/example-run
python -m positioning status work/example-run
python -m positioning dossier work/example-run
```

`run` starts bounded acquisition, offline estimation and post-freeze verification
in separate processes (30-minute limit per stage). Source/measurement failures
stop before estimation or oracle access. Each stage writes a log under `logs/`.
An unknown software exception produces `FAILED` / `ENGINEERING_FAILURE`, not a
scientific rejection or a passing result. A completed request is read back without
re-execution; interrupted/failed requests require inspection and are not retried
automatically. The initial directory must be empty. Do not delete an attempt to
retry a revealed event or search for a passing result.

`dossier.json` provides one summary schema for successful, rejected and missing
positions, with UTF-8 source/input/result evidence and SHA-256 hashes. Unavailable
position/error fields are null, never zero. `terminal_receipt.json` seals the
published dossier and its included artifacts; a later edit is rejected on read.
Raw observations and the post-freeze SP3 remain in the run directory and have
separate acquisition receipts. These local hashes are not a trusted timestamp.

This is the local worker foundation. The deployed archive remains read-only;
it does not yet accept or execute requests. Running a new local request does not
automatically publish it or add it to the historical archive.

From the repository root, using Python 3.13:

```powershell
python -m pip install -r requirements-positioning.txt
python -m positioning acquire experiments/positioning_g12_doy250/plan.json work/g12_reproduction
python -m positioning estimate work/g12_reproduction
python -m positioning verify work/g12_reproduction
```

This example reproduces a **closed failed qualification**, not a new experiment.
It does not change the closed event. A fresh experiment needs a separately
predeclared plan and unexposed confirmation evidence.

- `acquire` freezes the exact plan before downloads, hashes compressed sources
  before decoding, scans structure, selects the frozen window, then constructs
  reference-only navigation and observation inputs. Held-out target codes remain
  outside the estimator packet. Mixed raw navigation is not persisted.
- `estimate` uses only admitted inputs. The CLI denies Python socket operations
  and subprocess creation in this stage. It calibrates clocks, reconstructs an
  emitted event, solves xyz+B, evaluates uncertainty, predicts the excluded
  receiver, and saves solution/hash before any confirmation access.
- `verify` first checks the freeze, source hashes and input hashes. It reveals
  the excluded receiver, then downloads the specified oracle. It never refits
  the position. An existing terminal result is returned without new access.

All stages now retain byte-exact source snapshots alongside their hash receipts.
Acquisition also returns a closed terminal without re-downloading or rewriting
the experiment. Odd support/fit sizes and the implemented reference count are
validated before new acquisition.

The offline audit hook prevents accidental networking through these Python
capabilities. It is not a security boundary against malicious native code or an
administrator. File hashes and stage separation are audit evidence, not a
trusted external timestamp.

The kernel supports GPS RINEX 3 C1C/C2W data, 5–8 distinct fit roots and one
excluded root. Date, target, window and station set are explicit inputs. GPST
calendar and GPS-week offsets are handled separately from fine local time.
The currently implemented calibration thresholds are checked against the plan;
unsupported threshold changes are rejected rather than silently ignored.

Unknown clock/code/coordinate header changes are not silently accepted. The
current parser supports the phase-only header updates needed by the measured
files. It is deliberately not a universal RINEX implementation.

## Error and claim limits

Keep a 20 m statistical code floor, shared-reference and terrestrial-coordinate
uncertainty, and a stated ±20 m per-root systematic design envelope for the new
event. The G12 plan adds 64 deterministic interior bias probes to all 128 corners
and a 5% numerical envelope margin. These probes investigate sensitivity;
they do not certify global coverage or remove unknown physical biases.

An uncertainty-qualified numerical solution is not yet externally confirmed.
The primary label requires the frozen uncertainty, excluded-receiver and oracle
criteria all to pass. A small observed error does not permit retroactive
uncertainty reduction.

## Verification

```powershell
python -m pytest positioning/tests experiments/gnss_inverse_positioning/tests -q
```

If a local sandbox does not permit the system temporary directory, add
`--basetemp work/pytest-positioning-local` with a dedicated workspace directory.
GitHub Actions runs these suites on Windows and Linux. A workflow definition
is not evidence that a remote CI run has already occurred.

Tests include target mutation/removal, independent clock-gauge shifts, GPST day
and week rollover, 7-root inverse recovery, rank failure, frozen G08 regression,
and the complete acquisition-independent calibration/freeze/reveal chain using
previously revealed G08 excerpts. The oracle is supplied from a local fixture
in that regression; it is never counted as new scientific evidence.

The initial 32 active/frozen tests passed locally and on GitHub Actions Windows
and Linux at preregistration commit `118c683`. The suite has since expanded.
G14 DOY246 subsequently satisfied all criteria for one conditional historical
event; the earlier G08 and G12 uncertainty failures remain unchanged. This is
not yet a demonstrated general verification service.
