# Satellite RF Observatory

**Android GNSS acquisition, external time checks and reproducible evidence for PNT security research.**

[![PNT tests](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-tests.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-tests.yml)
[![Android app](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/android-collector.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/android-collector.yml)
[![Offline experiments](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/live-instrument-tests.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/live-instrument-tests.yml)
[![Web archive](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-archive.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-archive.yml)
[![Python 3.13](docs/assets/badges/python.svg)](requirements-positioning.txt)
[![License: Apache 2.0](docs/assets/badges/license.svg)](LICENSE)
[![Status: Research prototype](docs/assets/badges/research.svg)](docs/PROJECT_STATUS.md)

[Quick start](#quick-start) · [Capabilities](#capabilities) · [Evidence](#current-evidence) · [Documentation](#documentation)

## What this project does

Satellite RF Observatory compares a local receiver's GNSS observations with
external receiver recordings obtained through the Internet. It produces
geometry and clock diagnostics, exposes missing or conflicting evidence, and
retains source hashes for reproducible incident analysis.

The Android app turns an existing phone into a measurement collector: one
button records native GNSS measurements and authenticated Internet time (NTS),
then exports both originals in a ZIP. Collection needs Internet and sky view,
with the app visible; it needs no Termux, PC or USB cable. Analysis and replay
run in the existing Python engine on a PC; version 0.4 returns its report to
the phone through an explicit document import.

The first use case is a **fixed GPS receiver at independently known coordinates**.
The active goal is to establish whether external observations add useful
security evidence beyond sensible local controls.

```text
Local GNSS log + external observations + declared broadcast navigation
                 ↓
        Local and matched-network diagnostics
                 ↓
       JSON evidence, source hashes and coverage gaps
```

**Current scope:** a foreground Android collector and offline research tools, with no qualified spoofing verdict
or operational timing protection. Regular remote receivers do not authenticate
the RF received locally. Double differences cancel common receiver-clock terms;
absolute-time verification requires a separate qualified time reference.

## Capabilities

| Command / component | Available behavior |
|---|---|
| [PNT Clock Collector](pnt/android-collector/README.md) | Same-app GNSS + NTS, live diagnostics, session ZIP export and input-bound PC report import; Android 10+ development APK |
| `python -m pnt android-session` | Native session ZIP to a phone-readable report; missing budgets remain insufficient, explicit analysis reuses the existing time engine |
| `python -m pnt analyze` | Fixed-site RINEX geometry, local and matched-network clock fits, double differences and data gaps |
| `python -m pnt android-raw` | Android GPS L1/L5 measurement intake with source fields, signal identity and unusable-row accounting |
| `python -m pnt time-probe` / `android-time-probe` | Authenticated Internet time acquisition with declared assumptions; the Android command uses the phone's CLOCK_BOOTTIME |
| `python -m pnt android-time-compare` | GNSS UTC versus same-phone NTS with explicit association and error budgets; missing bounds remain insufficient |
| `python -m pnt time-sensitivity` | Offline receiver UTC offset sensitivity with fixed budgets and visible unsupported cases |
| `python -m pnt android-analyze` | Android L1/C1C compared with external C1C observations at explicit fixed coordinates |
| `python -m pnt compare` | Development comparison with separate training/calibration/evaluation windows and software code ramps |
| `python -m pnt transfer` | Training-only prediction of later local residuals from external observations |
| `python -m pnt navigation` | Decoded GPS navigation comparison against supplied external messages; RINEX and UBX SFRBX inputs |
| `python -m pnt navigation-compare` | Paired OBS/NAV cases evaluated on identical support with original-only calibration |
| `python -m service` | Trusted local request queue, worker and evidence retrieval for the general verification workflow |
| Experimental web archive | Read-only historical results and evidence downloads; no solver runs in the browser |

See the [PNT command reference](pnt/README.md), [service guide](service/README.md)
and [web archive guide](web/README.md) for formats, options and limitations.
Public HTTP/browser submission and an operational security service are not delivered.

Android GPS L1/L5 intake and the L1/C1C network diagnostic path are available
on `main`. Android geometry requires explicit fixed antenna coordinates;
single-frequency ionosphere and signal group delays remain uncorrected
nuisances. These commands do not issue an authenticated-signal or attack verdict.

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

| Question | What the evidence supports |
|---|---|
| Do network residuals improve local prediction? | Mixed results on distant references; small improvements on nearby WegenerNet references. No demonstrated security benefit at matched false-alarm rates. |
| Does agreement with archived navigation authenticate local RF? | No. Navigation fields can agree during a recorded attack; missing issues and conflicts remain visible. |
| Can Internet time distinguish receiver UTC offsets? | On one real phone capture, software offsets of ±10 ms remain invisible and ±50 ms separate under uncalibrated budgets. This is conditional sensitivity, not RF authentication. |
| Does the native clock metadata qualify the phone's time association? | No. The reported alignment uncertainty is about 7 ms at 68% confidence on one outdoor capture; the earlier 1 ms assumption remains unqualified. |
| Can the inverse research estimate a satellite without fitting its target orbit? | One conditional G14 event reached its declared milestone. Other events retain their failures or uncertainty limits. This is separate from qualifying a cyber detector. |

Detailed outcomes, numerical results and next physical questions live in
[project status](docs/PROJECT_STATUS.md), the
[PNT security plan](docs/PNT_SECURITY_PLAN.md) and the
[scientific roadmap](docs/SCIENTIFIC_ROADMAP.md).
Synthetic exercises test software mechanisms; they are not measured RF
detection performance. Closed results remain unchanged.

The [Android workflow](docs/PNT_SECURITY_PLAN.md#roadmap-operativa-dal-telefono-al-rapporto)
now delivers autonomous GNSS/NTS acquisition and live acquisition diagnostics.
The next increment is an export-to-analysis-to-phone report workflow using
the existing engine. Timing qualification and a documented
benign/challenge comparison remain necessary to establish security benefit.
Website and deployment work follow that physical demonstration.

## Documentation

| Start here | Purpose |
|---|---|
| [PNT security plan](docs/PNT_SECURITY_PLAN.md) | Active objective, evidence requirements and product direction |
| [Project status](docs/PROJECT_STATUS.md) | Current results, failures and remaining work |
| [PNT tools](pnt/README.md) | Offline diagnostic commands and signal/time conventions |
| [Android app](pnt/android-collector/README.md) / [Android time guide](docs/ANDROID_GNSS_TIME.md) | Build, record, export and distinguish transport evidence from a qualified comparison |
| [General verification workflow](docs/GENERAL_VERIFICATION_WORKFLOW.md) | Request-to-result architecture and local service |
| [Positioning implementation](positioning/README.md) | Independent target-state estimation and historical replay |
| [Scientific roadmap](docs/SCIENTIFIC_ROADMAP.md) | Preserved inverse research, uncertainty and qualification work |
| [Exploratory reports](research/exploratory/) / [kinematic research](research/kinematic/) | Detailed experiments and reproducible evidence |
| [Historical experiments](experiments/) / [forward-era README](docs/history/README_forward.md) | Original outcomes and earlier project direction |
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
