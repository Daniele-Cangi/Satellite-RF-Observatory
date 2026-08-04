# SIS Engineering Roadmap

This document defines the work required to turn the current Satellite Intelligence System repository from an experimental proof of concept into a small, credible, reproducible satellite RF analysis tool.

The goal is not to preserve every existing component. The goal is to establish one narrow execution path that works correctly, can be tested without hardware, and produces results whose limitations are explicit.

## Target outcome

The first serious release should answer a constrained question:

> Given a versioned IQ recording, a calibrated observer configuration, an offline orbital catalog, and a verified list of nominal satellite carriers, which visible satellites are plausible sources of each detected signal track, and what evidence supports each candidate?

It should not claim universal satellite identification, intelligence production, vulnerability assessment, covert operation, or secure storage.

## Architectural decision

The **offline pipeline is the primary product path**.

```text
IQ source
  -> validated capture container
  -> deterministic DSP
  -> detections over time
  -> signal tracks
  -> orbital and frequency candidate generation
  -> evidence-based scoring
  -> SQLite/JSON report
```

The current FastAPI, WebSocket, Redis, PostgreSQL, and worker architecture is considered legacy until the offline core passes its release criteria.

## Non-negotiable engineering rules

1. Documentation describes implemented and measured behavior only.
2. Every core stage must be callable independently and covered by tests.
3. Synthetic data is used for unit tests, not as proof of real-world accuracy.
4. Real-world identification claims require labelled recordings and quantitative evaluation.
5. A missing security feature is described as missing, not as “ready” or “recommended.”
6. Candidate scores must expose their inputs, assumptions, and alternatives.
7. Network access must never be required during analysis.
8. Technical capture metadata must remain available even when operator metadata is removed.

---

# Milestone 0 — Establish the baseline

**Priority:** P0  
**Goal:** make the repository understandable, installable, and testable before changing the algorithm.

## Work

- [ ] Define a supported Python version range, initially Python 3.11–3.12.
- [ ] Add a `pyproject.toml` with project metadata and dependency groups.
- [ ] Separate required offline dependencies from optional hardware and legacy API dependencies.
- [ ] Add `pytest`, `ruff`, and a minimal CI workflow.
- [ ] Convert import-report scripts into tests that fail with a non-zero exit code.
- [ ] Add package `__init__.py` files where needed.
- [ ] Remove duplicate imports and dead configuration classes.
- [ ] Add a clear deprecation notice to legacy real-time modules.
- [ ] Move old architecture documentation to `docs/legacy/` or remove it when it duplicates false claims.
- [ ] Add a small `CHANGELOG.md` starting with the restructuring release.

## Acceptance criteria

- A clean clone installs in a new virtual environment using one documented command.
- `pytest` fails when a required module cannot be imported.
- `ruff check .` passes.
- CI runs on every push and pull request.
- The README and package metadata describe the same supported execution path.

---

# Milestone 1 — Define a reliable IQ container

**Priority:** P0  
**Goal:** ensure every recording can be read unambiguously and reproduced later.

## Current problem

The collector can omit its header when metadata scrubbing is enabled, while the analyzer expects that header and skips 96 bytes unconditionally. This makes part of the advertised collection path incompatible with the analysis path.

## Work

- [ ] Replace the implicit 96-byte format with a documented, versioned container specification.
- [ ] Keep mandatory technical metadata in every capture:
  - format version;
  - sample type and byte order;
  - sample rate;
  - tuned center frequency;
  - hardware timestamp or explicit absence;
  - receiver identifier or anonymized receiver class;
  - frequency correction in PPM when known.
- [ ] Separate optional operator metadata from technical metadata.
- [ ] Define whether timestamps apply to the first sample, each block, or both.
- [ ] Add block-level sample counts and optional checksums.
- [ ] Detect truncated files and invalid headers before processing.
- [ ] Support raw `complex64` only through explicit command-line parameters, never guessed defaults.
- [ ] Add a reader and writer API independent of the SDR collector.
- [ ] Add round-trip tests for header encoding, decoding, block rotation, and truncation.
- [ ] Remove the current “scrub metadata by randomizing filesystem timestamps” behavior.

## Proposed module boundary

```text
sis/io/container.py
  CaptureHeader
  CaptureBlock
  CaptureReader
  CaptureWriter
```

## Acceptance criteria

- Every file produced by the collector can be opened by the analyzer.
- A reader never silently assumes sample rate or center frequency.
- Invalid and truncated files produce explicit errors.
- Writing and reading the same synthetic samples preserves the samples and technical metadata exactly.

---

# Milestone 2 — Make the DSP deterministic and measurable

**Priority:** P0  
**Goal:** turn the current detection example into a reusable signal-processing pipeline.

## Work

- [ ] Move DSP code out of `OfflineProcessor` and `Scheduler` into pure functions or small stateless classes.
- [ ] Introduce an explicit `DSPConfig` containing:
  - FFT size;
  - overlap;
  - window;
  - detector guard cells;
  - detector reference cells;
  - threshold or target false-alarm rate;
  - minimum SNR;
  - clustering distance;
  - edge policy.
- [ ] Use fixed capture timestamps instead of `datetime.now()` during file analysis.
- [ ] Produce one timestamp per analysis frame derived from sample offset and sample rate.
- [ ] Handle DC spikes and configurable excluded bands.
- [ ] Replace the hard-coded `-80 dB` floor with calibrated or data-relative logic.
- [ ] Correctly handle detector edges, NaNs, zeros, and very short blocks.
- [ ] Define power units clearly: dBFS unless hardware calibration supports dBm.
- [ ] Add frequency correction for known oscillator error.
- [ ] Separate individual spectral detections from tracks evolving across frames.
- [ ] Add track formation using frequency proximity, time continuity, and configurable gaps.
- [ ] Save detector configuration with every analysis result.

## Test fixtures

- [ ] noise only;
- [ ] one continuous carrier;
- [ ] multiple simultaneous carriers;
- [ ] drifting carrier;
- [ ] intermittent burst;
- [ ] signal at the FFT edge;
- [ ] strong DC component;
- [ ] changing noise floor;
- [ ] known sample-rate and oscillator offsets.

## Metrics

At minimum, tests should measure:

- frequency estimation error;
- detection probability at defined SNR values;
- false detections per processed minute;
- track continuity;
- runtime and peak memory for fixed fixture sizes.

## Acceptance criteria

- The same input, configuration, and software version produce identical detections.
- Unit tests cover all listed fixtures.
- Detection performance is reported as measured data, not qualitative claims.
- Processing never uses wall-clock time as the timestamp of historical samples.

---

# Milestone 3 — Build an offline orbital and frequency catalog

**Priority:** P0  
**Goal:** provide the information required for legitimate candidate generation.

## Current problem

The existing correlation engine effectively treats the receiver center frequency as the nominal carrier for every candidate satellite. The offline processor does not perform full SGP4 propagation and can fall back to cached Doppler values or zero.

## Work

- [ ] Define a local catalog schema for satellites, TLEs, and known radio carriers.
- [ ] Store TLE source, retrieval time, epoch, and checksum.
- [ ] Store carrier source, frequency, uncertainty, band, mode, and validity period.
- [ ] Keep orbital data and frequency data as separate evidence sources.
- [ ] Implement an explicit catalog import command that can run on a connected machine.
- [ ] Export a signed or checksummed offline catalog package for the analysis machine.
- [ ] Load all catalog data locally during analysis.
- [ ] Propagate candidate satellites at each signal-track timestamp using SGP4.
- [ ] Filter candidates by visibility and configurable minimum elevation.
- [ ] Calculate range, range rate, azimuth, elevation, and expected Doppler.
- [ ] Reject stale TLEs according to a documented policy.
- [ ] Support multiple known carriers per satellite.
- [ ] Represent unknown or uncertain carrier data explicitly rather than inventing defaults.

## Proposed local schema

```text
satellites
  norad_id
  name
  metadata

orbital_elements
  norad_id
  tle_line_1
  tle_line_2
  epoch
  source
  retrieved_at
  checksum

carriers
  carrier_id
  norad_id
  nominal_frequency_hz
  uncertainty_hz
  bandwidth_hz
  mode
  source
  valid_from
  valid_to
```

## Acceptance criteria

- Candidate generation never assumes that all satellites transmit at the tuned center frequency.
- Every predicted frequency can be traced to a nominal carrier and a specific orbital element set.
- Analysis runs with networking disabled.
- Tests verify orbital calculations against known SGP4 reference cases.

---

# Milestone 4 — Replace “identification” with evidence-based candidate scoring

**Priority:** P0  
**Goal:** rank plausible candidates without overstating certainty.

## Candidate generation

A satellite/carrier pair should be considered only when:

- the satellite is geometrically visible;
- the carrier falls within the observed band after predicted Doppler and uncertainty;
- the observation timestamp falls within the validity period of the catalog entry;
- the TLE is not rejected as stale.

## Initial scoring features

- frequency residual after Doppler correction;
- expected carrier uncertainty;
- receiver frequency-calibration uncertainty;
- elevation angle;
- consistency across the complete observed Doppler track;
- pass start and end timing;
- signal bandwidth compatibility;
- modulation compatibility when a classifier exists;
- optional antenna pointing compatibility.

## Work

- [ ] Rename correlation output from `match` to `candidate` or `hypothesis`.
- [ ] Return the top N candidates, not only a winner.
- [ ] Include raw feature values and rejection reasons.
- [ ] Define a transparent baseline scoring function before introducing machine learning.
- [ ] Avoid the word “Bayesian” unless the implementation defines priors, likelihoods, normalization, and posterior interpretation.
- [ ] Calibrate score thresholds on labelled data.
- [ ] Add an explicit `unresolved` result when evidence is insufficient.
- [ ] Prevent a global assignment algorithm from encoding unsupported assumptions such as one carrier per satellite.
- [ ] Model multi-carrier satellites and repeated observations correctly.

## Example result shape

```json
{
  "track_id": "track-0012",
  "status": "candidate_list",
  "candidates": [
    {
      "norad_id": 25544,
      "carrier_id": "carrier-145800000",
      "score": 0.82,
      "frequency_residual_hz": 184.0,
      "track_rmse_hz": 326.0,
      "elevation_deg": 42.1,
      "evidence": [
        "known carrier in observed band",
        "visible throughout track",
        "Doppler curve consistent within calibration uncertainty"
      ]
    }
  ]
}
```

## Acceptance criteria

- Every score is reproducible and explainable from stored inputs.
- The system can return “unresolved.”
- Competing candidates remain visible in the output.
- No result is described as confirmed identity solely because it exceeds an arbitrary Gaussian threshold.

---

# Milestone 5 — Create an actual validation dataset

**Priority:** P0  
**Goal:** establish whether the method works outside its own synthetic model.

## Dataset layers

### Layer A — deterministic synthetic fixtures

Used for unit tests and exact edge cases.

### Layer B — generated orbital scenarios

Signals are generated from orbital trajectories, but the generation and inference code must be independently implemented or cross-checked.

### Layer C — public labelled IQ recordings

Use recordings with known satellite, frequency, pass time, observer location, and receiver configuration where licensing permits redistribution.

### Layer D — locally captured labelled passes

Capture known amateur-radio or weather-satellite transmissions using a documented setup and pass prediction.

## Work

- [ ] Define a dataset manifest format.
- [ ] Record source, license, checksum, sample format, observer location precision, hardware, and expected label.
- [ ] Add small fixtures directly to the repository when licensing and size allow.
- [ ] Provide download scripts plus checksums for larger public fixtures.
- [ ] Create negative examples containing no target transmission.
- [ ] Evaluate competing satellites using overlapping or nearby carrier frequencies.
- [ ] Keep training, calibration, and final evaluation sets separate if learned models are later introduced.

## Required evaluation metrics

- top-1 candidate accuracy;
- top-3 candidate recall;
- unresolved rate;
- false attribution rate;
- frequency-track RMSE;
- performance grouped by elevation, SNR, band, and TLE age.

## Acceptance criteria

- At least one evaluation uses real IQ data not generated by SIS.
- Results can be reproduced from a published manifest and configuration.
- A benchmark report includes failures and ambiguous cases, not only successful examples.

---

# Milestone 6 — Rebuild the offline command-line workflow

**Priority:** P1  
**Goal:** provide one coherent operator workflow after the underlying modules are correct.

## Proposed commands

```bash
sis catalog import --tle active.tle --carriers carriers.csv --output catalog.sisdb

sis capture \
  --device driver=rtlsdr \
  --frequency 145.8MHz \
  --sample-rate 2.4MHz \
  --duration 600s \
  --output pass.siq

sis analyze \
  --input pass.siq \
  --catalog catalog.sisdb \
  --observer observer.toml \
  --config analysis.toml \
  --output analysis.sisdb

sis report \
  --analysis analysis.sisdb \
  --format json \
  --output report.json
```

## Work

- [ ] Replace the monolithic controller with subcommands backed by testable service functions.
- [ ] Validate all units and accept explicit suffixes such as MHz, kHz, and seconds.
- [ ] Store the complete analysis configuration and software version.
- [ ] Add structured error messages and meaningful exit codes.
- [ ] Support progress reporting without changing analysis results.
- [ ] Add resumable processing for large captures.
- [ ] Make repeated processing idempotent or create explicit analysis runs.
- [ ] Define a stable SQLite schema and migrations.

## Acceptance criteria

- A documented command sequence processes a fixture from capture file to JSON report.
- Invalid inputs fail before expensive processing begins.
- The report contains enough provenance to reproduce the run.

---

# Milestone 7 — Implement security features only when required

**Priority:** P1  
**Goal:** remove placeholder security language and implement narrowly defined protections correctly.

## Work

- [ ] Decide whether capture encryption is an actual project requirement.
- [ ] Until implemented, remove or reject the `--encrypt` option rather than silently writing plaintext.
- [ ] If implemented, use an authenticated encryption construction such as AES-GCM through a maintained library.
- [ ] Define nonce generation, key storage, rotation, recovery, and failure behavior.
- [ ] Never generate a key next to the data without explicit user consent and documentation.
- [ ] Add tamper detection and known-answer tests.
- [ ] Define metadata minimization separately from technical metadata required for analysis.
- [ ] Replace “air-gap verification” claims with explicit checks that report their limited scope.
- [ ] Add checksums and a manifest to export packages.

## Acceptance criteria

- Enabling encryption cannot produce plaintext silently.
- Corrupted or modified encrypted data is rejected.
- Security documentation has been reviewed separately from feature documentation.
- No “secure,” “stealth,” or “air-gapped” claim depends only on checking active network interfaces.

---

# Milestone 8 — Integrate physical SDR hardware

**Priority:** P1  
**Goal:** make hardware capture reliable after the file and DSP layers are stable.

## Work

- [ ] Implement a genuine generic SoapySDR receiver.
- [ ] Stop using the Ku-band receiver as the fallback for unrelated frequencies.
- [ ] Start and supervise the actual read loop.
- [ ] Handle stream timeout, overflow, dropped samples, and device removal.
- [ ] Record hardware time, dropped-sample counters, gain mode, and driver information.
- [ ] Add optional PPM calibration using a known reference signal.
- [ ] Test file rotation without losing or duplicating samples.
- [ ] Separate LNB RF frequency, local oscillator, and SDR intermediate frequency explicitly.
- [ ] Validate supported devices one by one rather than claiming generic support.

## Initial supported profile

Start with one tested configuration, for example:

- RTL-SDR;
- VHF/UHF direct reception;
- Linux or Windows, selected explicitly;
- complex64 output;
- one known satellite service.

Expand only after that profile is repeatable.

## Acceptance criteria

- A ten-minute capture completes without an unreported overflow on the reference setup.
- Sample counts and file sizes agree within documented framing overhead.
- Hardware loss produces a clear incomplete-capture result.
- The resulting file passes all container validation checks.

---

# Milestone 9 — Add presentation and networking last

**Priority:** P2  
**Goal:** expose validated results without coupling the core to a server architecture.

## Work

- [ ] Define a read-only report API over completed analysis runs.
- [ ] Keep the DSP and correlation packages independent of FastAPI.
- [ ] Add a local spectrum and track viewer only after result schemas stabilize.
- [ ] Use WebSockets only for live capture telemetry, not as a requirement for analysis.
- [ ] Add authentication and restrictive CORS before exposing any non-local service.
- [ ] Avoid Redis and TimescaleDB until measured scale justifies them.

## Acceptance criteria

- The complete offline workflow remains available with all networking disabled.
- The UI reads stable result models rather than internal worker objects.
- Removing the UI has no effect on analysis correctness.

---

# Recommended repository restructuring

```text
src/sis/
  cli.py
  config.py

  io/
    container.py
    manifest.py

  dsp/
    spectrum.py
    cfar.py
    peaks.py
    tracks.py

  catalog/
    models.py
    importers.py
    storage.py

  orbit/
    propagation.py
    visibility.py
    doppler.py

  correlation/
    candidates.py
    scoring.py
    evidence.py

  storage/
    database.py
    migrations/

  hardware/
    base.py
    soapy.py

  reporting/
    json_report.py

tests/
  fixtures/
  unit/
  integration/
  hardware/

docs/
  format/
  methodology/
  benchmarks/
  legacy/
```

---

# First implementation sprint

The next code changes should remain deliberately small.

## Sprint objective

Process one valid IQ fixture deterministically and produce correct, timestamped signal detections through a tested API.

## Ordered tasks

1. [ ] Add `pyproject.toml`, `pytest`, and CI.
2. [ ] Create `src/sis/io/container.py` with a versioned header.
3. [ ] Add round-trip and corruption tests for the container.
4. [ ] Extract the periodogram and detector into `src/sis/dsp/`.
5. [ ] Create deterministic synthetic fixtures.
6. [ ] Add tests for frequency error and false detections.
7. [ ] Create timestamped analysis frames from sample offsets.
8. [ ] Produce detections as typed data objects.
9. [ ] Write detections to a minimal SQLite schema.
10. [ ] Add one integration test from fixture file to database rows.

## Explicitly out of scope for the first sprint

- frontend work;
- FastAPI repairs;
- Redis or TimescaleDB;
- encryption;
- Starlink-specific claims;
- vulnerability or intelligence models;
- machine learning;
- broad SDR hardware support;
- satellite attribution.

---

# Release gates

## `0.1.0` — Reproducible DSP core

- [ ] clean installation;
- [ ] versioned IQ reader and writer;
- [ ] deterministic DSP;
- [ ] strict automated tests;
- [ ] SQLite detection output;
- [ ] no satellite attribution claim.

## `0.2.0` — Orbital candidate engine

- [ ] offline TLE and carrier catalog;
- [ ] tested SGP4 propagation;
- [ ] visible candidate generation;
- [ ] Doppler-track scoring;
- [ ] explainable top-N candidate output.

## `0.3.0` — Real-data validation

- [ ] labelled public or locally captured IQ dataset;
- [ ] published evaluation manifest;
- [ ] top-1, top-3, unresolved, and false-attribution metrics;
- [ ] benchmark report including failures.

## `1.0.0` — Credible narrow tool

- [ ] one fully documented hardware profile;
- [ ] repeatable capture-to-report workflow;
- [ ] stable schemas and CLI;
- [ ] security claims independently verified or omitted;
- [ ] documentation matches the released behavior exactly.

---

# Definition of “serious” for SIS

SIS becomes serious when another person can:

1. clone the repository;
2. install it from the documented instructions;
3. download or generate the same test data;
4. run the same commands;
5. obtain the same detections and candidate scores;
6. inspect why each candidate was ranked;
7. reproduce the published metrics;
8. encounter failures that are reported honestly rather than hidden by successful exit codes.

Adding more modules before reaching that point would make the repository larger, not more credible.
