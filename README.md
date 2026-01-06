# Satellite Intelligence System (SIS-PRO)

> **Gray System - Passive RF Collection & Offline Analysis Framework**
> *Zero Network Footprint | Air-Gapped Processing | Operational Security by Design*

## ⚠️ NOTICE

**This is a gray system architecture for authorized defensive security research and educational purposes.**

- ✅ **Legal Use**: Spectrum monitoring, amateur radio, authorized SIGINT research
- ✅ **Educational**: Signal processing, orbital mechanics, RF engineering
- ❌ **Prohibited**: Unauthorized interception, malicious surveillance, export violations

**Operator Responsibility**: Ensure compliance with local regulations and authorization requirements.

---

## 1. Executive Summary

SIS-PRO is a **passive SIGINT collection and analysis framework** designed for environments requiring operational security. The system operates in three distinct phases:

1. **COLLECTION**: Headless RF capture with zero network footprint
2. **ANALYSIS**: Air-gapped batch processing on isolated workstation
3. **EXPORT**: Sanitized intelligence product for secure transfer

Unlike traditional monitoring systems with network APIs and real-time dashboards, SIS-PRO eliminates attribution risk through complete network isolation and encrypted storage.

### Key Capabilities

**Operational Security**:
- ✅ Zero network footprint during collection
- ✅ Encrypted storage (AES-256-GCM)
- ✅ Air-gapped batch processing
- ✅ Metadata scrubbing (OPSEC)
- ✅ Randomized filenames (stealth mode)

**Technical Capabilities**:
- **Passive Collection**: Direct-to-disk IQ recording with SDR hardware
- **Signal Processing**: CFAR detection, FFT analysis, peak extraction
- **Orbital Mechanics**: Vectorized SGP4 propagation for 20,000+ objects
- **Correlation Engine**: Bayesian Doppler-based satellite identification
- **Offline Analysis**: Complete processing without network dependency

---

## 2. System Architecture

The system is modular, designed for stability and scalability:

```mermaid
graph TD
    subgraph Hardware Layer
        SDR[SDR Device] -->|I/Q Samples| RW[Receiver Worker]
    end

    subgraph "Backend Core (Python/FastAPI)"
        RW -->|SharedQueue| SCH[Scheduler & DSP]
        SCH -->|FFT & Peak Detect| CE[Correlation Engine]
        TM[TLE Manager] -->|Orbital State| CE
        CE -->|Matches| WS[WebSocket Manager]
        WS -->|JSON Stream| CLIENT[Frontend Dashboard]
    end

    subgraph "Data Persistence"
        TSDB[(TimescaleDB)]
        REDIS[(Redis Cache)]
    end

    SCH -->|.add()| TSDB
    TM -->|.set()| REDIS
```

### 2.1 Component Breakdown

#### **Receiver Worker (`workers/receiver_worker.py`)**
*   **Role**: Interfaces with hardware (RTL-SDR, Airspy, USP) via `SoapySDR`.
*   **Design**: Runs as a separate OS process. Detaches from appropriate locks/GIL to handle high-throughput I/Q streams.
*   **Output**: Pushes raw IQ buffers or computed FFT frames to a multiprocessing `Queue`.

#### **Scheduler (`workers/scheduler.py`)**
*   **Role**: The "Heartbeat" of the system.
*   **DSP**: Performs FFT (`scipy.signal.periodogram`), noise floor estimation, and Peak Detection.
*   **Logic**: 
    1.  Ingests signal peaks.
    2.  Queries `CorrelationEngine` for matches.
    3.  Broadcasts events (`spectrum`, `tracking`, `alerts`) via WebSockets.
    4.  Persists observations to TimescaleDB.

#### **TLE Manager (`trackers/tle_manager.py`)**
*   **Role**: Manages the "Catalog of Objects".
*   **Tech**: Fetches TLEs from Space-Track/Celestrak. Updates every 6 hours.
*   **Optimization**: 
    *   **Vectorized Propagation**: Propagates all 23,000+ satellites in batches using `numpy` vs scalar loops.
    *   **Horizon Filtering**: Quickly discards objects below the observer's horizon (-5° margin).

#### **Correlation Engine (`processors/correlation_engine.py`)**
*   **Role**: The "Brain". Matches a generic RF signal (freq X) to a specific object (NORAD ID Y).
*   **Algorithm**:
    *   **Input**: Measured Frequency ($f_m$), Observer Location.
    *   **Prediction**: For every visible satellite, calculate Range Rate ($\dot{r}$) and expected Doppler shift ($\Delta f = - \frac{\dot{r}}{c} f_c$).
    *   **Scoring**: Gaussian Probability Density Function based on the residual $|f_m - (f_c + \Delta f)|$.
    *   **Output**: Best match if Confidence > Threshold (0.8).

---

## 3. Installation

### 3.1 Prerequisites
*   **Python 3.10+**
*   **Redis** (for TLE caching)
*   **PostgreSQL + TimescaleDB** (for historic storage)
*   **SoapySDR** (Drivers for your specific hardware)

### 3.2 Setup
1.  **Clone Repository**
    ```bash
    git clone https://github.com/your-org/satellite-intelligence.git
    cd satellite-intelligence
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
    *Key libs: `fastapi`, `uvicorn`, `numpy`, `scipy`, `skyfield`, `sgp4`, `sqlalchemy`, `orjson`.*

3.  **Environment Configuration**
    Create a `.env` file:
    ```ini
    # Database
    DATABASE_URL=postgresql://user:pass@localhost:5432/sis_db
    
    # Receiver
    RECEIVER_ENABLED=true
    RECEIVER_DEVICE="driver=rtlsdr"
    RECEIVER_FREQ=137500000 
    
    # TLE Sources
    SPACE_TRACK_USER="..."
    SPACE_TRACK_PASSWORD="..."
    ```

---

## 4. Usage

### 4.1 Running the Core System
Start the FastAPI server (which automatically spawns the Workers):

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```
*   **Startup Sequence**:
    1.  Database Init.
    2.  TLE Manager fetches fresh catalog.
    3.  Receiver Worker starts (if SDR found).
    4.  Scheduler loop begins.

### 4.2 Simulation Mode
To test logic without hardware, use the Simulation Runner. This injects synthetic "perfect" signals:

```bash
python scripts/simulation_runner.py
```
*   *Verification*: This script creates a fake signal matching the ISS (International Space Station) and asserts that the Correlation Engine correctly identifies it among 23,000 other objects.

### 4.3 API Endpoints
*   **WebSocket**: `ws://localhost:8000/ws/spectrum` (Real-time FFT)
*   **WebSocket**: `ws://localhost:8000/ws/tracking` (Live Object Matches)
*   **REST**: `GET /observations/` (Historic Data)
*   **REST**: `GET /satellites/` (Catalog)

---

## 5. Development Status

| Module | Status | Notes |
| :--- | :--- | :--- |
| **SDR Interface** | ✅ Active | Supports SoapySDR (RTL/Airspy). |
| **TLE Engine** | ✅ Active | Full catalog, Vectorized SGP4. |
| **Correlation** | ✅ Active | Logic verified via Simulation. |
| **API Layer** | ✅ Active | FastAPI + WebSockets + ORJSON. |
| **Database** | ✅ Active | SQLAlchemy + TimescaleDB schema. |
| **Frontend** | 🚧 Planned | Designing React + WebGL + Deck.gl Dashboard. |

---

## 6. Mathematical Appendix: Correlation Logic

The correlation score $S$ for a satellite $i$ is calculated as:

$$ S_i = e^{-\frac{(f_{measured} - f_{predicted, i})^2}{2\sigma^2}} $$

Where:
*   $f_{predicted}$ is the downlink frequency adjusted for Doppler shift derived from the SGP4 state vector velocity.
*   $\sigma$ is the system frequency tolerance (e.g., 500 Hz for narrow band).

This probabilistic approach allows the system to differentiate between two satellites that are close in the sky but moving at different relative velocities (and thus different Doppler shifts).

---

**© 2025 Satellite Intelligence Project**
**© 2025 Satellite Intelligence Project**
*Educational Proof of Concept & SIGINT Research Demo.*
