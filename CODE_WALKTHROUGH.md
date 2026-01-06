# SIS-PRO Code Architecture Walkthrough

This document provides a detailed technical breakdown of every source file in the Satellite Intelligence System. It explains the **Purpose**, **Mechanism** (How it works), and **Dependencies** for each component.

---

## 1. Core Module (`core/`)

### `core/config.py`
*   **Purpose**: Centralized configuration management using `pydantic-settings`.
*   **Mechanism**:
    *   Defines a `Settings` class that inherits from `BaseSettings`.
    *   Automatically loads variables from `.env` or system environment variables.
    *   Validates types (e.g., ensuring `RECEIVER_FREQ` is an integer).
*   **Key Logic**: Resolves hierarchy: *Environment Vars > .env file > Defaults*.

### `core/database.py`
*   **Purpose**: Object-Relational Mapping (ORM) and Database connection.
*   **Mechanism**:
    *   Uses `SQLAlchemy` for the ORM layer.
    *   Defines models: `Satellite` (Catalog), `Observation` (RF Hits), `Telemetry` (TT&C), `Analysis` (Vulnerability Reports).
    *   **Special Feature**: Integrates with **TimescaleDB** (via hypertable concepts, though implemented as standard Postgres tables here initially) for efficient time-series storage of high-frequency signal data.
*   **Key Logic**: Renamed `metadata` column to `meta_info` to avoid collision with SQLAlchemy's internal `MetaData` class.

---

## 2. API Module (`api/`)

### `api/main.py`
*   **Purpose**: The Application Entrypoint.
*   **Mechanism**:
    *   Initializes the `FastAPI` instance.
    *   **Lifespan Events**: Handles startup (Database Init -> Receiver Process Start -> Scheduler Start) and shutdown (Graceful Worker Termination).
    *   Mounts Routers: `/intelligence`, `/satellites`, etc.
*   **Key Logic**: Manages the global state of the `ReceiverWorker` and `Scheduler` instances.

### `api/websockets.py`
*   **Purpose**: High-Performance Pub/Sub Manager for Real-Time Data.
*   **Mechanism**:
    *   `ConnectionManager` class maintains lists of active `WebSocket` connections, grouped by topic ("spectrum", "tracking", "alerts").
    *   **Serialization**: Uses `orjson` with `OPT_SERIALIZE_NUMPY` to serialize floating-point arrays (FFT data) 10x faster than standard `json`.
*   **Key Logic**: `broadcast()` takes a raw Python/NumPy object, serializes it once to bytes, and blasts it to all subscribers asynchronously.

### `api/schemas.py`
*   **Purpose**: Data Transfer Objects (DTOs) for API validation.
*   **Mechanism**: Uses `Pydantic` V2 `BaseModel`.
*   **Key Models**:
    *   `SpectrumFrame`: Optimized structure for FFT waterfalls (mostly arrays).
    *   `SignalDetection`: Event for a correlated hit.
    *   `ObservationDTO`: Standardized historical record.

### `api/routes/`
*   **`intelligence.py`**: Exposes high-value analyzed data (Vulnerabilities) and allows "Tasking" (requesting interception).
*   **`satellites.py`**: Read-only access to the Orbital Catalog.
*   **`observations.py`**: Access to historic signal logs stored in TimescaleDB.

---

## 3. Workers Module (`workers/`)

### `workers/receiver_worker.py`
*   **Purpose**: **Process-Isolated** SDR Driver Helper.
*   **Mechanism**:
    *   Uses `multiprocessing.Process` to run the SDR driver in a separate memory space from the API. This prevents the Python Global Interpreter Lock (GIL) from freezing the SDR read loop during heavy API queries.
    *   **Queue System**: Uses `multiprocessing.Queue` to send raw IQ (or FFT) frames to the Scheduler.
*   **Key Logic**: `sdr_process_loop()` is the entry point for the child process. It creates the `Receiver` instance and enters an infinite polling loop.

### `workers/scheduler.py`
*   **Purpose**: The central coordination loop (The "Brain" loop).
*   **Mechanism**:
    *   Runs as an `asyncio` task within the Main API process.
    *   **DSP Chain**:
        1.  Drains queues from Receiver Worker.
        2.  **FFT**: calls `scipy.signal.periodogram` to convert time-domain IQ to Frequency Domain.
        3.  **Peak Detection**: calls `scipy.signal.find_peaks` to identify signals above the noise floor.
    *   **Correlation**: Passes detected peaks to the `CorrelationEngine`.
    *   **Broadcasting**: Pushes results to `ConnectionManager`.

---

## 4. Trackers Module (`trackers/`)

### `trackers/tle_manager.py`
*   **Purpose**: Managing Orbital Propagations (SGP4).
*   **Mechanism**:
    *   **Data Source**: Fetches TLEs (Two-Line Elements) from Space-Track or Celestrak.
    *   **Library**: Uses `Skyfield` and `sgp4`.
    *   **Optimization**:
        *   `refresh_visible_cache`: Instead of checking 20,000 satellites every request, it pre-calculates which ones are currently above the horizon (Altitude > 0) every minute.
        *   **Vectorization**: While Python SGP4 is scalar, the manager structures data to allow fast iteration.
*   **Key Logic**: Handles `datetime` timezone complexities (forcing Scalar UTC) to ensure compatibility with Skyfield strictly.

---

## 5. Processors Module (`processors/`)

### `processors/correlation_engine.py`
*   **Purpose**: Identifying the source of a radio signal.
*   **Mechanism**: **Bayesian Probability Matching**.
    *   **Input**: A detected frequency (e.g., 145.801 MHz).
    *   **Process**:
        1.  Iterates over all *Visible* satellites.
        2.  Calculates the **Predicted Doppler Shift** for each satellite relative to the observer.
        3.  Compares `Predicted Freq` vs `Measured Freq`.
        4.  Calculates a **Residual** (Difference).
    *   **Scoring**: Uses a Gaussian function. If the Residual is 0 Hz, Score is 1.0. As Residual increases, Score drops.
*   **Key Logic**: `active_subset` optimization allows checking 200 satellites instead of 23,000 per signal.

---

## 6. Receivers Module (`receivers/`)

### `receivers/base_receiver.py`
*   **Purpose**: Abstract Interface (Protocol) for all hardware.
*   **Mechanism**: Defines methods like `start()`, `stop()`, `set_frequency()`, `get_data()`. Enforces a standard API so the Worker doesn't care if it's an Airspy or RTL-SDR.

### `receivers/ku_band_receiver.py`
*   **Purpose**: Implementation for Starlink/Ku-band Beacons.
*   **Mechanism**:
    *   Handles **LNB Offset**: Subtracts the Local Oscillator (9.75 GHz) freq to map the high-frequency satellite signal to the L-Band range of the SDR (950-2150 MHz).
    *   **SoapySDR**: Uses the Python bindings for SoapySDR to talk to the USB hardware.

### `receivers/sdr_manager.py`
*   **Purpose**: Factory Pattern.
*   **Mechanism**: `create_receiver(config)` inspects the configuration (e.g., frequency range) and instantiates the correct class (e.g., `StarlinkBeaconReceiver` or a generic one).

---

## 7. Scripts (`scripts/`)

### `scripts/simulation_runner.py`
*   **Purpose**: System Validation (End-to-End Test).
*   **Mechanism**:
    *   **Mocking**: Injects a "Fake" signal into the pipeline that mathematically matches a specific satellite (e.g., ISS) at the current time.
    *   **Monkey Patching**: Temporarily overrides filters (like horizon checks) to force validation even if the satellite isn't actually visible during the test run.
    *   **Verification**: Asserts that the `CorrelationEngine` returns the correct NORAD ID for the injected signal.

### `scripts/verify_setup.py` & `scripts/verify_api.py`
*   **Purpose**: Sanity checks.
*   **Mechanism**: Simple import scripts to ensure all dependencies are installed and modules can talk to each other without `ModuleNotFoundError`.
