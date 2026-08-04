# Satellite Intelligence System (SIS)

> Experimental passive satellite RF collection and analysis prototype.

SIS explores a practical question:

> Can a locally captured radio-frequency signal be compared with orbital and frequency data to produce a defensible list of possible satellite sources?

The repository contains early implementations of SDR capture, offline spectrum analysis, signal detection, orbital propagation, and Doppler-based candidate scoring.

It is **not an operational intelligence platform**, a finished monitoring product, or a validated satellite-identification system. Several components are incomplete, some belong to an older real-time architecture, and the current correlation logic still requires significant work before its results can be treated as reliable.

## Early interface proof of concept

![Early SIS map-based interface proof of concept](docs/images/sis-proof-of-concept.webp)

*Early map-based interface prototype created during the first SIS exploration. It documents the original visualization and interaction direction of the project. The labels, confidence value, sensor status, locations, and events shown are demonstration output and should not be interpreted as validated satellite identifications or production telemetry.*

## Project status

**Stage:** experimental proof of concept

**Primary direction:** deterministic offline processing of locally captured IQ data

| Component | Current state | Notes |
|---|---|---|
| SDR IQ capture | Prototype implemented | Requires SoapySDR and compatible hardware; not covered by automated hardware tests. |
| IQ file format | Partially implemented | Header-based files can be analyzed; metadata-scrubbed files are not yet compatible with the current reader. |
| Offline DSP | Prototype implemented | Periodogram, CA-CFAR-style detection, peak clustering, SQLite storage, and JSON export are present. |
| Synthetic DSP check | Implemented | Demonstrates detection of a strong synthetic carrier; it is not a full system validation. |
| TLE propagation | Partially implemented | The legacy path uses Skyfield/SGP4; the offline processor does not yet perform full propagation. |
| Satellite correlation | Experimental | Current scoring is based mainly on Doppler residuals and does not yet use a complete, verified downlink-frequency catalog. |
| Encryption | Not implemented | The encryption option currently passes data through unchanged. Do not treat captures as encrypted. |
| Secure export | Placeholder | Packaging, sanitization, checksums, and encryption still need implementation. |
| FastAPI/WebSocket system | Legacy and incomplete | Retained as architectural reference; it is not the recommended execution path. |
| Frontend | Not implemented | No supported dashboard is included. |

The engineering plan for turning this prototype into a credible system is documented in [`ROADMAP.md`](ROADMAP.md).

## What the repository is trying to build

The intended system is an offline-first satellite RF observatory:

```text
SDR hardware or recorded IQ data
                |
                v
       Versioned IQ capture
                |
                v
   Deterministic DSP pipeline
  FFT/PSD -> detection -> tracks
                |
                v
 Candidate generation and scoring
 orbit + known carrier + Doppler
                |
                v
       SQLite and JSON results
```

The key word is **candidate**. A measured frequency and a predicted Doppler shift are not, by themselves, sufficient to identify an arbitrary transmitter. Credible attribution also requires known nominal carrier frequencies, accurate timestamps, observer coordinates, receiver calibration, orbital visibility, and continuity across multiple observations.

## Current repository structure

```text
analysis/
  offline_processor.py     Offline IQ analysis and local result storage

collectors/
  passive_collector.py     Direct-to-disk SDR IQ capture

processors/
  correlation_engine.py    Experimental Doppler-based candidate scoring

trackers/
  tle_manager.py           TLE download, propagation, and visibility logic

receivers/
  base_receiver.py         Receiver abstraction
  ku_band_receiver.py      Experimental Ku-band/Starlink receiver path
  sdr_manager.py           Receiver factory prototype

workers/                   Legacy real-time acquisition and DSP workers
api/                       Legacy FastAPI and WebSocket layer
scripts/                   Synthetic checks and exploratory simulations
gray_system_main.py        Offline-first command-line entry point
```

## Supported development path

For now, work should focus on the offline path:

1. capture or provide IQ samples;
2. process them locally;
3. store signal detections;
4. compare detections with a prepared local catalog;
5. export reproducible results.

The legacy API, Redis, PostgreSQL, TimescaleDB, and WebSocket components should be treated as reference code until the offline core is correct and tested.

## Installation

### Requirements

- Python 3.10 or newer
- NumPy and SciPy
- Skyfield and SGP4
- SQLite, included with Python
- SoapySDR only when using physical SDR hardware

Create an environment and install the Python dependencies:

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

SoapySDR should be installed through the operating system or hardware vendor packages rather than through `pip`.

## Running the existing checks

### Synthetic DSP check

```bash
python scripts/verify_dsp.py
```

This generates complex Gaussian noise plus a strong synthetic carrier and verifies that the current spectral detector can locate the carrier. It tests only the DSP detection example.

### Import check

```bash
python scripts/verify_setup.py
```

This script reports import problems, but it is not currently a strict automated test and may still exit successfully after printing failures.

### Exploratory correlation simulation

```bash
python scripts/simulation_runner.py
```

The simulation uses the same orbital model to generate and score a synthetic signal. It is useful for inspecting the intended data flow, but it should not be interpreted as independent evidence that the identification method works on real captures.

## Offline collection and analysis

### Capture IQ data

```bash
python gray_system_main.py collect \
  --freq 145.8 \
  --rate 2.4 \
  --gain 40 \
  --duration 60 \
  --storage ./iq_data
```

This requires a compatible SDR device and SoapySDR installation.

### Analyze captured files

```bash
python gray_system_main.py analyze \
  --input ./iq_data \
  --database ./analysis.db \
  --export ./results.json
```

### Important current limitations

- Do **not** rely on `--encrypt`; encryption is not implemented.
- Do **not** use `--stealth` for data intended for the current offline analyzer. That mode removes the technical header that the analyzer expects.
- Do **not** treat a high correlation score as confirmed satellite identity.
- Do **not** treat example performance figures in older documentation as benchmark results unless they are reproduced and measured again.

## Signal processing prototype

The current offline processor performs the following operations:

1. reads complex64 IQ samples;
2. estimates power spectral density with a Hann-windowed periodogram;
3. estimates a local noise floor using a CA-CFAR-style convolution kernel;
4. detects bins above an adaptive threshold;
5. clusters adjacent bins into candidate peaks;
6. estimates frequency, power, bandwidth, and SNR;
7. stores detections in SQLite;
8. optionally exports results to JSON.

This is a useful starting point, but it still needs deterministic timestamps per chunk, configurable detector parameters, edge handling, track formation across time, receiver calibration, reproducible datasets, and quantitative validation.

## Correlation model: current limits

The repository explores a Gaussian score based on the residual between measured and predicted frequency:

```text
residual = measured_frequency - predicted_frequency
score = exp(-0.5 * (residual / sigma)^2)
```

A serious implementation must calculate the predicted frequency from a known nominal carrier assigned to a candidate satellite:

```text
predicted_frequency = nominal_downlink_frequency + predicted_doppler_shift
```

The current code does not yet provide a complete, verified mapping between satellites and active downlink frequencies. Until that exists, the correlation engine is an experiment in candidate ranking, not a general identification engine.

Future scoring should combine multiple pieces of evidence:

- known frequency compatibility;
- predicted visibility and elevation;
- Doppler residual after receiver calibration;
- continuity of the Doppler curve over time;
- signal bandwidth and modulation characteristics;
- pass timing;
- antenna pointing or direction-of-arrival data, when available.

## Design principles going forward

- **Offline core first.** Networking and dashboards come after the analysis pipeline is correct.
- **Claims follow tests.** Documentation must describe measured behavior, not intended behavior.
- **Deterministic processing.** The same input and configuration should produce the same result.
- **Hardware-independent testing.** Synthetic and recorded IQ fixtures must cover the core pipeline.
- **Evidence, not labels.** Results should expose scores, residuals, assumptions, and alternative candidates.
- **Security features must be real.** Encryption and sanitization should not be advertised before implementation and review.
- **Clear separation of concerns.** Collection, DSP, orbital prediction, scoring, storage, and presentation should be independently testable.

## Legal and ethical use

This repository is intended for lawful education, amateur-radio experimentation, spectrum research, and analysis of signals the operator is authorized to receive and process.

It contains passive reception code and does not provide transmission, interference, decryption, or access-control bypass capabilities. Laws governing radio reception, recording, data retention, and satellite communications vary by jurisdiction. Users are responsible for obtaining any required authorization and complying with applicable regulations.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).

---

This repository should be read as an early technical exploration. Its value is the combination of RF collection, offline DSP, orbital prediction, and evidence-based candidate scoring. The next phase is not to add more features, but to make that narrow core correct, reproducible, and measurable.
