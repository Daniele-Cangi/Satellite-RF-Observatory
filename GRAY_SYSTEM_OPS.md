# GRAY SYSTEM - Operational Documentation

> **Classification**: RESTRICTED
> **System Type**: Passive RF Collection & Offline Analysis
> **Network Footprint**: ZERO

---

## 1. System Overview

**Gray System** è una piattaforma di **passive SIGINT** progettata per:
- Acquisizione RF **non attributable** (zero emissioni, zero network)
- Analisi **air-gapped** su workstation disconnesse
- **Operational security** by design

### Differenze vs Sistema Originale

| Componente | Sistema Originale | Gray System |
|------------|------------------|-------------|
| **API** | FastAPI WebSocket pubblico | ❌ RIMOSSO |
| **Database** | PostgreSQL remoto | SQLite locale (air-gapped) |
| **Cache** | Redis con networking | ❌ RIMOSSO |
| **Processing** | Real-time streaming | Batch offline |
| **Storage** | Cloud/NAS | Encrypted local disk |
| **Network** | Required | **PROHIBITED** |

---

## 2. Architettura Operativa

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: COLLECTION (Field Operations)                │
│  ┌──────────┐      ┌──────────────┐      ┌──────────┐  │
│  │ SDR      │─────▶│  Collector   │─────▶│ Encrypted│  │
│  │ Hardware │ IQ   │  (Headless)  │ Raw  │ Storage  │  │
│  └──────────┘      └──────────────┘      └──────────┘  │
│  Network: DISCONNECTED | OPSEC: ENABLED                 │
└─────────────────────────────────────────────────────────┘
                            │
                            │ USB Transfer / Courier
                            ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 2: ANALYSIS (Secure Facility)                   │
│  ┌──────────┐      ┌──────────────┐      ┌──────────┐  │
│  │ IQ Files │─────▶│ Offline      │─────▶│ SQLite   │  │
│  │ (USB)    │      │ Processor    │      │ Results  │  │
│  └──────────┘      └──────────────┘      └──────────┘  │
│  Network: AIR-GAPPED | Analysis Workstation            │
└─────────────────────────────────────────────────────────┘
                            │
                            │ Sanitized Export
                            ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 3: INTELLIGENCE (Command Center)                │
│  ┌──────────┐      ┌──────────────┐      ┌──────────┐  │
│  │ Results  │─────▶│ Correlation  │─────▶│ Reports  │  │
│  │ (JSON)   │      │ & Fusion     │      │ (Brief)  │  │
│  └──────────┘      └──────────────┘      └──────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Operational Procedures

### 3.1 COLLECTION (Field Deployment)

**Equipment Checklist**:
- [ ] SDR receiver (RTL-SDR / Airspy / USRP)
- [ ] Antenna (appropriate for target frequency)
- [ ] Laptop with Gray System software
- [ ] Encrypted external drive (min 500GB)
- [ ] Faraday bag (for transport)
- [ ] **NO network cables, NO WiFi dongles**

**Pre-Collection**:
```bash
# 1. Verify network isolation
ip link show  # All interfaces should be DOWN except 'lo'

# 2. Mount encrypted storage
cryptsetup open /dev/sdb1 iq_storage
mount /dev/mapper/iq_storage /mnt/encrypted

# 3. Verify SDR detection
SoapySDRUtil --find

# 4. Configure collection parameters
# Edit: collection_config.json
{
  "center_frequency_mhz": 145.0,
  "sample_rate_msps": 2.4,
  "duration_hours": 4,
  "stealth_mode": true
}
```

**Execute Collection**:
```bash
# Stealth mode (randomized filenames, scrubbed metadata)
python gray_system_main.py collect \
    --freq 145.0 \
    --rate 2.4 \
    --duration 14400 \
    --storage /mnt/encrypted/iq \
    --stealth \
    --encrypt \
    --enforce-offline
```

**Post-Collection**:
```bash
# 1. Verify captures
ls -lh /mnt/encrypted/iq/*.iq

# 2. Unmount and lock storage
umount /mnt/encrypted
cryptsetup close iq_storage

# 3. Power off (do not suspend - RAM may retain data)
shutdown -h now

# 4. Transport encrypted drive via secure courier
```

---

### 3.2 ANALYSIS (Air-Gapped Facility)

**Security Requirements**:
- ✅ Physically isolated network (no cables, WiFi disabled in BIOS)
- ✅ Faraday cage (optional for high-security)
- ✅ Video surveillance of workstation
- ✅ No USB ports except encrypted drive
- ✅ Screen privacy filter

**Analysis Workflow**:
```bash
# 1. Insert encrypted USB drive
cryptsetup open /dev/sdc1 analysis_drive
mount /dev/mapper/analysis_drive /mnt/usb

# 2. Verify air-gap
netstat -tuln  # Should show ZERO connections
ip link        # All interfaces DOWN

# 3. Run batch processor
python gray_system_main.py analyze \
    --input /mnt/usb/iq_data \
    --database /secure/analysis.db \
    --export /secure/results.json \
    --enforce-airgap

# Output:
# =============================================
# ANALYSIS COMPLETE
# Files processed: 47
# Signals detected: 1,283
# Satellite correlations: 892
# High-confidence matches: 156
# =============================================
```

**Result Review**:
```bash
# Query results database
sqlite3 /secure/analysis.db

# Top satellite detections
SELECT name, COUNT(*) as detections, AVG(confidence) as avg_conf
FROM satellite_correlations
WHERE confidence > 0.8
GROUP BY norad_id, name
ORDER BY detections DESC
LIMIT 20;

# Frequency spectrum analysis
SELECT frequency_hz/1e6 as freq_mhz, COUNT(*) as hits, AVG(snr_db)
FROM signal_detections
GROUP BY CAST(frequency_hz/1e5 AS INTEGER)
ORDER BY hits DESC;
```

---

### 3.3 EXPORT & TRANSFER

**Sanitization Protocol**:
```bash
# Export sanitized results (removes location, timestamps)
python gray_system_main.py export \
    --input /secure/results.json \
    --output /mnt/transfer \
    --sanitize

# Generate checksum manifest
cd /mnt/transfer
sha256sum * > MANIFEST.sha256

# Encrypt for transport (GPG)
gpg --encrypt --recipient intelligence@agency.gov results.json
```

**Transfer Methods**:
- **High Security**: One-way data diode hardware
- **Medium Security**: Encrypted USB via authorized courier
- **Low Security**: Secure file transfer (VPN + encrypted payload)

---

## 4. OPSEC Considerations

### 4.1 Collection Site Security

**Physical Security**:
- Site selection: Non-attributable location (not registered to operator)
- Visual concealment: Antenna should not be visible from public areas
- Quick teardown: < 5 minutes to pack and evacuate

**Electronic Security**:
- RF emissions: SDR is receive-only (passive), but laptop may emit EM
- Tempest shielding: Faraday bag for storage drive during transport
- No geolocation: Disable GPS, Bluetooth, WiFi in BIOS

**Operational Security**:
- Cover story: "Amateur radio enthusiast" or "Wireless ISP survey"
- Documentation: No logs, no photos, no notes with real identifiers
- Communication: Burner phone only, pre-established check-in times

### 4.2 Data Handling

**At Rest**:
- Encryption: AES-256-GCM (hardware-accelerated)
- Key management: Stored on separate HSM/Yubikey
- Metadata scrubbing: Remove GPS coordinates, timestamps, operator IDs

**In Transit**:
- Physical: Tamper-evident seals on USB drives
- Electronic: GPG encryption + detached signatures
- Chain of custody: Logged transfers with dual signatures

**Analysis**:
- Air-gap verification: Automated network check before processing
- Access control: Biometric + PIN for workstation
- Screen recording: All analysis sessions logged (security review)

---

## 5. Target Profiles

### 5.1 LEO Communication Satellites

**Targets**:
- Orbcomm (IoT/M2M telemetry)
- Iridium (satellite phone)
- Globalstar (data relay)

**Collection Parameters**:
```json
{
  "center_frequency_mhz": 137.5,
  "bandwidth_mhz": 2.4,
  "sample_rate_msps": 2.4,
  "duration_hours": 4,
  "expected_doppler_khz": ±15
}
```

**Intelligence Value**:
- Intercept unencrypted M2M telemetry
- Identify ground station locations (TDOA with multi-site)
- Pattern analysis: Communication schedules reveal operator activities

### 5.2 Weather Satellites (NOAA, Meteor)

**Targets**:
- NOAA 15/18/19 (137 MHz APT)
- Meteor-M2 (137 MHz LRPT)

**Collection Parameters**:
```json
{
  "center_frequency_mhz": 137.1,
  "bandwidth_mhz": 0.5,
  "sample_rate_msps": 1.0,
  "duration_hours": 2
}
```

**Intelligence Value**:
- Verify satellite health status
- Detect anomalous transmissions (espionage payload on "civilian" sat)
- Practice for harder targets (military weather sats use similar protocols)

### 5.3 Military Satellites (Classified)

**Targets**:
- UHF SATCOM (240-270 MHz, 292-318 MHz)
- X-band downlinks (8 GHz)

**Collection Parameters**:
```json
{
  "REDACTED": "CLASSIFIED"
}
```

**Intelligence Value**:
- Emission schedules (when/where they transmit)
- Signal fingerprinting (hardware identification)
- Encryption detection (presence of crypto = military confirmation)

---

## 6. Advanced Capabilities

### 6.1 Multi-Site TDOA (Time Difference of Arrival)

**Concept**: 3+ geographically separated collectors synchronize to geolocate transmitters

**Requirements**:
- GPS-disciplined clocks (1 PPS reference)
- Precise timestamp on every sample (nanosecond accuracy)
- Post-processing correlation to extract time delays

**Intelligence Gain**:
- Locate clandestine ground stations
- Map enemy C2 infrastructure
- Validate satellite operator claims (says "civilian" but downlinks to military base)

### 6.2 Signal Fingerprinting

**Concept**: Unique hardware characteristics identify specific satellites

**Features Extracted**:
- Phase noise signature (oscillator quality)
- Spectrum mask (PA non-linearities)
- Timing jitter (clock stability)

**Intelligence Gain**:
- Track satellite even if TLE is fake/withheld
- Detect payload swaps (different transmitter = different satellite)
- Attribution: Match signature to manufacturer/country

### 6.3 Emission Pattern Analysis

**Concept**: Machine learning on transmission schedules

**Data Collected**:
- When: Time-of-day, day-of-week patterns
- Where: Ground station locations
- How Much: Data volume estimation

**Intelligence Gain**:
- Predict future communication windows (for jamming/intercept)
- Detect emergency tasking (unscheduled transmission = crisis response)
- Infer mission: Surveillance sats have predictable downlink patterns

---

## 7. Countermeasures & Threats

### 7.1 Detection Risk

**Adversary Capabilities**:
- RF Direction Finding (DF): Can locate passive receivers via LO leakage
- Tempest: Laptop screen emissions can be intercepted
- Visual surveillance: Antenna may be visible

**Mitigations**:
- Use SDRs with low LO leakage (Airspy, not cheap RTL-SDR)
- Faraday enclosure for laptop (reduces Tempest)
- Concealed antennas (inside vehicles, disguised as TV antenna)

### 7.2 Legal Risks

**Regulatory**:
- Most countries: Receiving signals is legal (transmitting is regulated)
- Exception: Decrypting military/encrypted signals may be illegal
- Export controls: ITAR restricts sharing data with foreign entities

**Operational**:
- Cover story must be plausible
- No evidence of targeting classified systems
- Deniability: Equipment is dual-use (amateur radio)

### 7.3 Data Compromise

**Threats**:
- Drive seizure: Encryption must hold under forensics
- Insider threat: Air-gap prevents exfiltration
- Supply chain: SDR firmware may have backdoors

**Mitigations**:
- Full disk encryption (LUKS + strong passphrase)
- Self-destruct mechanism (optional: thermite charge on drive)
- Open-source SDR software (inspect for backdoors)

---

## 8. Performance Benchmarks

### Expected Detection Performance

| Satellite Type | Frequency | SNR Required | Correlation Accuracy |
|----------------|-----------|--------------|---------------------|
| NOAA APT | 137 MHz | 10 dB | 99% |
| Orbcomm | 137-138 MHz | 5 dB | 85% |
| Iridium | 1616-1626 MHz | 8 dB | 70% (complex Doppler) |
| GPS L1 | 1575 MHz | -20 dB | 95% (spread spectrum) |

### Storage Requirements

| Sample Rate | Duration | File Size (Uncompressed) | Encrypted Overhead |
|-------------|----------|--------------------------|-------------------|
| 2.4 Msps | 1 hour | 69 GB | +2% (AES-GCM) |
| 10 Msps | 1 hour | 288 GB | +2% |
| 20 Msps | 1 hour | 576 GB | +2% |

**Recommendation**: Use 1TB SSD for 8-12 hours of 2.4 Msps collection

---

## 9. Quick Reference

### Common Commands

```bash
# Collection (stealth mode, 4 hours at 145 MHz)
python gray_system_main.py collect --freq 145.0 --duration 14400 --stealth --encrypt

# Analysis (air-gapped, batch process all files)
python gray_system_main.py analyze --input /mnt/usb/iq --enforce-airgap

# Export (sanitized results)
python gray_system_main.py export --input /results --output /transfer --sanitize
```

### Troubleshooting

**SDR not detected**:
```bash
# Check USB device
lsusb | grep -i rtl

# Check SoapySDR drivers
SoapySDRUtil --find

# Reload driver
sudo rmmod dvb_usb_rtl28xxu rtl2832
sudo modprobe rtl2832_sdr
```

**Disk full during collection**:
- System auto-rotates files at 1GB
- Monitor disk usage: `df -h /mnt/encrypted`
- Increase `max_file_size_mb` in config

**Poor correlation accuracy**:
- Check TLE cache freshness (update weekly)
- Verify location coordinates in config
- Increase `frequency_tolerance_hz` for higher Doppler

---

## 10. Legal Disclaimer

This system is provided for **authorized defensive security research** and **lawful intelligence operations** only.

**Prohibited Uses**:
- Unauthorized interception of communications
- Violation of export control regulations (ITAR/EAR)
- Criminal surveillance activities

**Operator Responsibility**:
- Obtain proper authorization before deployment
- Comply with local regulations on spectrum monitoring
- Handle classified data per appropriate security protocols

---

**Document Version**: 1.0
**Last Updated**: 2025-01-04
**Classification**: RESTRICTED - AUTHORIZED PERSONNEL ONLY
