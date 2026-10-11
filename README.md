# Satellite RF Observatory

**Open satellite research: orbital reconstruction, RF observation, PNT diagnostics and Android acquisition.**

[![Positioning & PNT tests](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-tests.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-tests.yml)
[![Android app](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/android-collector.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/android-collector.yml)
[![Offline experiments](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/live-instrument-tests.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/live-instrument-tests.yml)
[![Web archive](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-archive.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-archive.yml)
[![Python 3.13](docs/assets/badges/python.svg)](requirements-positioning.txt)
[![License: Apache 2.0](docs/assets/badges/license.svg)](LICENSE)
[![Status: Research prototype](docs/assets/badges/research.svg)](docs/PROJECT_STATUS.md)

[Research areas](#research-areas) · [Quick start](#quick-start) · [Capabilities](#capabilities) · [Evidence](#current-evidence) · [Documentation](#documentation)

## What this project does

Satellite RF Observatory is an open research ecosystem for checking what
satellite observations can establish about geometry, motion and receiver time.
It develops independent orbital reconstruction, tests declared orbital
predictions against RF observations, and compares local GNSS measurements with
external observations for PNT incident analysis. An Android app supplies native
GNSS measurements and authenticated Internet time to the research workflow.

These areas share parsing, provenance, qualification, replay and request
infrastructure where appropriate. Each keeps its own physical model, evidence
requirements and advancement criteria. Completing an app workflow does not
confirm an orbit or validate a spoofing detector.

## Research areas

| Area | Question and implementation | Current boundary / next scientific step |
|---|---|---|
| **Orbital reconstruction** | Can position and motion be estimated without fitting the target's orbit? [Positioning](positioning/README.md), [kinematic research](research/kinematic/README.md) and [scientific roadmap](docs/SCIENTIFIC_ROADMAP.md) | Historical conditional snapshots and synthetic motion results exist. Real interval work still needs an independent constraint on station/code bias or a geometry/model that identifies it, with a defensible total-error envelope. |
| **RF observation and orbital prediction** | Does a declared orbital geometry predict held-out observations better than frozen alternatives? [Forward roadmap](ROADMAP.md) and [experiment reports](experiments/orbital_discriminability/) | A closed DRAO GNSS phase event supports a narrow orbital-model preference. Independent identity, distributed confirmation and general raw-RF capability remain unestablished. Further research needs an identifiable observable and adequate measurement timing. |
| **PNT security research** | Do external geometry/time observations add useful evidence beyond reasonable local controls? [PNT tools](pnt/README.md) and [PNT plan](docs/PNT_SECURITY_PLAN.md) | Offline diagnostics and replay are available for a fixed GPS receiver. Added physical security benefit and prospective detection performance remain open. |
| **Android acquisition** | Can an existing phone acquire GNSS/NTS, export originals and display the PC analysis? [PNT Clock Collector](pnt/android-collector/README.md) | The experimental software cycle is implemented, including optional private LAN monitoring. Timing qualification and physical attack validation remain separate research tasks. |

The areas can advance independently. The
[project status](docs/PROJECT_STATUS.md#ecosistema-e-stato-dei-verticali)
records their results, gaps and next decisions. The website remains a later
delivery step; the existing web archive preserves historical evidence.

## Capabilities

| Component / commands | Available behavior |
|---|---|
| `python -m positioning plan / run / status / dossier` | Historical GPS snapshot requests, independent target-state fitting, conditional uncertainty, excluded checks and explicit failed outcomes; see the [positioning guide](positioning/README.md) for command syntax |
| [Kinematic research](research/kinematic/README.md) | Experimental code/range-rate and phase-interval models, observability and error-budget studies; real-data qualification is incomplete |
| [RF and orbital experiments](experiments/orbital_discriminability/) | Versioned geometry, observer, held-out orbital/null and capability studies; follow the relevant plan and access boundary |
| [PNT Clock Collector](pnt/android-collector/README.md) | Foreground GNSS + NTS acquisition, diagnostics, ZIP export, input-bound PC report import and optional private HTTPS monitoring; Android 10+ development APK |
| `python -m pnt android-session / android-monitor / android-serve` | Session reports, revisable PC analysis and opt-in private LAN transfer using the existing monitor |
| `python -m pnt analyze / android-raw / android-analyze` | Fixed-site geometry, clock fits, double differences, Android GPS L1/L5 intake and an L1/C1C network path |
| `python -m pnt time-probe / android-time-probe / android-time-compare / time-sensitivity` | Authenticated Internet time acquisition and conditional timing diagnostics with declared assumptions and insufficient-evidence outcomes |
| `python -m pnt compare / transfer / navigation / navigation-compare` | Development comparisons, training-only residual prediction and decoded GPS navigation consistency |
| `python -m service` / [web archive](web/README.md) | Trusted local request queue, worker and evidence retrieval; read-only historical web results |

Slash-separated names above list separate commands. See the
[PNT command reference](pnt/README.md) and [service guide](service/README.md)
for arguments and limits. Public HTTP/browser submission and an operational
security service are not delivered.

**Scientific scope:** a historical position is conditional evidence, not live
tracking or a general accuracy guarantee. Model-consistent remote observations
do not authenticate RF received locally. Double differences cancel common
receiver-clock terms; absolute-time verification needs a qualified time
reference. Android geometry needs explicit fixed coordinates; uncorrected
single-frequency propagation and signal delays remain nuisances. No qualified
spoofing verdict or operational timing protection is currently delivered.

## Quick start

### Collect on an Android phone

Follow the [app build and installation guide](pnt/android-collector/README.md).
Install the development APK, grant precise Location, and press **Start GNSS +
NTS** outdoors with Internet access. Keep the app visible, then use **Export
last session** after the schedule finishes or after pressing Stop. The ZIP
contains the original Raw CSV and NTS JSON, including failed and unattempted
slots. Transfer it to a PC and create a report:

```console
python -m pip install -r requirements-pnt-time.txt
python -m pnt android-session pnt-session-<id>.zip --output phone-report.json
```

With no analysis assumptions, this writes an **INSUFFICIENT_EVIDENCE** report
and exits with code **2**. Copy the JSON to the phone and press **Open PC report**:
the app checks its input hashes against retained originals and shows coverage,
failures, assumptions and controls not run. The
[reporting guide](pnt/android-collector/README.md#zip-to-pc-report-to-phone)
explains conditional analysis and replay; no upload or on-device solver is added.

The live panel shows actual Raw reception, missing timing fields, clock count
changes and NTS failures. It distinguishes acquisition problems from a timing
comparison, which remains **NOT ASSESSED** during acquisition. Imported PC
results appear separately, labeled with their session and trust limits.

The app does not assign a security verdict or invent timing bounds. Its NTS
transport report intentionally leaves unqualified budgets and counter resolution
unknown; it is not yet a ready-to-run qualified `android-time-compare` input.
The [Android guide](docs/ANDROID_GNSS_TIME.md) distinguishes acquisition from
the conditional comparison workflow.

### Run an offline diagnostic

Use **Python 3.13**. Clone the repository and install the research dependencies:

```console
git clone https://github.com/Daniele-Cangi/Satellite-RF-Observatory.git
cd Satellite-RF-Observatory
python -m pip install -r requirements-positioning.txt
python -m pnt --help
```

Run an offline example using the bundled WegenerNet observations and GPS NAV.
The following commands use **PowerShell**, from the repository root:

```powershell
$observations = "pnt/tests/fixtures/wegener20240911"
$navigation = "pnt/tests/fixtures/gfz20240911/brdc2550.24n.gz"
python -m pnt analyze 2024-09-11 `
  "$observations/W181_fixed.obs.gz" $navigation `
  --reference "W182=$observations/W182_fixed.obs.gz" `
  --reference "W183=$observations/W183_fixed.obs.gz" `
  --start 28800 --stop 29400 --output incident.json
```

This writes a diagnostic report for the requested epochs, including gaps.
Choose a new output filename for each run; existing reports are not overwritten.
The fixture coordinates are provider declarations, not an independent survey.
This example does not classify an attack or demonstrate position accuracy.
For your own recordings, follow the [input requirements](pnt/README.md).

## Current evidence

### Orbital reconstruction

The [G14 DOY246 event](experiments/positioning_g14_doy246_network/OUTCOME.md)
met its declared criteria with 31.017 m observed external 3D error and a
5,755.157 m prospective conditional radius. This single event is not a general
accuracy or coverage guarantee. Other events retain uncertainty failures or
insufficient measurements.

[Real G12 interval work](research/exploratory/REAL_TARGET_INTERVAL.md) fits code
and phase without the target orbit: phase improves position in 3/5 accepted
cases and worsens it in 2/5; 15/20 phase cases remain rejected. The
[bias-identifiability study](research/exploratory/REAL_TARGET_BIAS_IDENTIFIABILITY.md)
explains why phase increments leave an absolute station-bias/position mode
unresolved. Synthetic motion results do not close this physical gap.

### RF observation and declared orbital prediction

The closed [DRAO labelled-forward event](experiments/orbital_discriminability/GNSS_DRAO_LABELLED_FORWARD_DOY234_OUTCOME_REPORT.md)
predictively preferred frozen orbital geometry over both frozen alternatives
on a real held-out GNSS phase interval, with no held-out refit. Its scope is
one labelled station and six model-conditioned tracks. It does not establish
independent satellite identity, distributed confirmation or orbit determination.
The [forward roadmap](ROADMAP.md) also retains failed acquisition and
non-discriminative routes; those outcomes remain closed.

### PNT diagnostics

The [Android Raw clock challenge](research/exploratory/PNT_ANDROID_RAW_CLOCK_CHALLENGE.md)
shifts GPS reception and transmit time together by +/-100 ms, preserving all
1,446 parsed GPS pseudoranges. NTS distinguishes both shifts on 65/156 common
clock groups while local elapsed continuity stays unchanged. It uses exposed
data and uncalibrated assumptions; 91 insufficient groups and 23/80 NTS timeouts
remain visible. This demonstrates conditional software consistency benefit.

The [callback receipt diagnostic](research/exploratory/PNT_ANDROID_CAUSAL_RECEIPT.md)
reduces alignment assumptions for impossible future claims, but leaves the same
+/-100 ms challenges invisible. Conditional receipt margins are 554.5-632.3 ms;
past claims remain unbounded.

The [JammerTest 2025 comparison](research/exploratory/PNT_JAMMERTEST_2025_COHERENT.md)
uses a physical recording and contemporaneous remote references. The anomaly
is already evident locally; added network detection benefit is not demonstrated.
Its [clock-source audit](research/exploratory/PNT_JAMMERTEST_2025_CLOCK_SOURCE.md)
finds no documented independent UTC association in the inspected recording.
The [path without further Finnish data](docs/PNT_SECURITY_PLAN.md#avanzare-senza-ulteriori-dati-dalla-finlandia)
keeps diagnostic delivery independent of that reply while retaining the physical
requirements for stronger security claims.

### Android workflow

Collector 0.6.0 implements acquisition -> original ZIP -> PC analysis ->
input-bound result on the phone, plus optional private HTTPS monitoring with
retained revisions and failures. [Outdoor trials](research/exploratory/PNT_ANDROID_NTS_COVERAGE.md)
support acquisition and conditional replay; they do not establish a stable
coverage gain or physical attack protection. PC processing and phone UI timings
remain separate from GNSS-to-operator alert latency.

Detailed evidence and gaps live in [project status](docs/PROJECT_STATUS.md).
Synthetic exercises, software challenges and exploratory replays retain their
original status; closed experimental results remain unchanged.

## Documentation

| Start here | Purpose |
|---|---|
| [Project status](docs/PROJECT_STATUS.md) | Ecosystem priorities, delivered results and independent scientific gaps |
| [Scientific roadmap](docs/SCIENTIFIC_ROADMAP.md) / [positioning implementation](positioning/README.md) | Independent reconstruction, motion, uncertainty and historical replay; original protocols preserved |
| [Forward roadmap](ROADMAP.md) / [orbital and RF reports](experiments/orbital_discriminability/) | Declared orbital prediction, observation capability and immutable outcomes |
| [PNT security plan](docs/PNT_SECURITY_PLAN.md) / [PNT tools](pnt/README.md) | PNT-specific goals, command formats and evidence requirements |
| [Android app](pnt/android-collector/README.md) / [Android time guide](docs/ANDROID_GNSS_TIME.md) | Build, collect, export and distinguish transport from a qualified comparison |
| [General verification workflow](docs/GENERAL_VERIFICATION_WORKFLOW.md) / [service](service/README.md) | Shared request-to-result infrastructure and local queue |
| [Exploratory reports](research/exploratory/) / [kinematic research](research/kinematic/) | Detailed experiments and reproducible evidence |
| [Forward-era README](docs/history/README_forward.md) | Earlier project presentation |
| [Development workflow](docs/DEVELOPMENT_WORKFLOW.md) / [AGENTS.md](AGENTS.md) | Integration and operational principles: freeze claims, not ordinary engineering |

## Development

PNT, positioning and Android app CI run on **Linux and Windows**. Separate workflows check
offline experiments, the historical Cassini regression and the web archive.
The badges above track `main`; a passing build is a software check, not
scientific confirmation.

For focused PNT checks:

```console
python -m pytest pnt/tests -q
```

See the [development workflow](docs/DEVELOPMENT_WORKFLOW.md) for integration.
Source code is licensed under [Apache 2.0](LICENSE); retained third-party
datasets and fixtures carry their own attribution and license terms.
