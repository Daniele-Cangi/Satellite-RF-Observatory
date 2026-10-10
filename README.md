# Satellite RF Observatory

**Offline GNSS consistency checks and reproducible evidence for PNT security research.**

[![PNT tests](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-tests.yml/badge.svg?branch=main)](https://github.com/Daniele-Cangi/Satellite-RF-Observatory/actions/workflows/positioning-tests.yml)
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

**Current scope:** an offline research tool, with no qualified spoofing verdict
or operational timing protection. Regular remote receivers do not authenticate
the RF received locally. Double differences cancel common receiver-clock terms;
absolute-time verification requires a separate qualified time reference.

## Capabilities

| Command / component | Available behavior |
|---|---|
| `python -m pnt analyze` | Fixed-site RINEX geometry, local and matched-network clock fits, double differences and data gaps |
| `python -m pnt android-raw` | Android GPS L1/L5 measurement intake with source fields, signal identity and unusable-row accounting |
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
| Can the inverse research estimate a satellite without fitting its target orbit? | One conditional G14 event reached its declared milestone. Other events retain their failures or uncertainty limits. This is separate from qualifying a cyber detector. |

Detailed outcomes, numerical results and next physical questions live in
[project status](docs/PROJECT_STATUS.md), the
[PNT security plan](docs/PNT_SECURITY_PLAN.md) and the
[scientific roadmap](docs/SCIENTIFIC_ROADMAP.md).
Synthetic exercises test software mechanisms; they are not measured RF
detection performance. Closed results remain unchanged.

The next delivery priority is an [autonomous Android acquisition and reporting
workflow](docs/PNT_SECURITY_PLAN.md#roadmap-operativa-dal-telefono-al-rapporto):
GNSS and authenticated Internet time collected in one app, with the existing
analysis engine and replay. This is planned work; the native collector is its
first component. Timing qualification and a documented benign/challenge
comparison remain necessary to establish security benefit. Website and
deployment work follow that physical demonstration.

## Documentation

| Start here | Purpose |
|---|---|
| [PNT security plan](docs/PNT_SECURITY_PLAN.md) | Active objective, evidence requirements and product direction |
| [Project status](docs/PROJECT_STATUS.md) | Current results, failures and remaining work |
| [PNT tools](pnt/README.md) | Offline diagnostic commands and signal/time conventions |
| [General verification workflow](docs/GENERAL_VERIFICATION_WORKFLOW.md) | Request-to-result architecture and local service |
| [Positioning implementation](positioning/README.md) | Independent target-state estimation and historical replay |
| [Scientific roadmap](docs/SCIENTIFIC_ROADMAP.md) | Preserved inverse research, uncertainty and qualification work |
| [Exploratory reports](research/exploratory/) / [kinematic research](research/kinematic/) | Detailed experiments and reproducible evidence |
| [Historical experiments](experiments/) / [forward-era README](docs/history/README_forward.md) | Original outcomes and earlier project direction |
| [Development workflow](docs/DEVELOPMENT_WORKFLOW.md) / [AGENTS.md](AGENTS.md) | Integration and operational principles: freeze claims, not ordinary engineering |

## Development

PNT and positioning CI runs on **Linux and Windows**. Separate workflows check
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
