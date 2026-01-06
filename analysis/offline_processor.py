# analysis/offline_processor.py
"""
Offline Batch Processor for Gray System
Analyzes raw IQ captures in air-gapped environment
Zero network connectivity required
"""

import numpy as np
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import struct
import json

from scipy import signal as scipy_signal
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)

@dataclass
class IQFileMetadata:
    """Metadata extracted from IQ file"""
    filepath: Path
    sample_rate: float
    center_frequency: float
    timestamp_ns: int
    file_size_bytes: int
    num_samples: int

@dataclass
class SignalDetection:
    """Detected signal information"""
    timestamp: datetime
    frequency_hz: float
    power_db: float
    bandwidth_hz: float
    snr_db: float
    duration_sec: float

@dataclass
class SatelliteMatch:
    """Correlated satellite identification"""
    norad_id: int
    name: str
    confidence: float
    doppler_residual_hz: float
    elevation_deg: float
    azimuth_deg: float
    range_km: float

class OfflineProcessor:
    """
    Air-gapped batch processor for IQ data
    No network access, pure local analysis
    """

    def __init__(self, storage_path: Path, db_path: Path):
        self.storage_path = storage_path
        self.db_path = db_path

        # Initialize local database
        self._init_database()

        # Load TLE cache (offline copy)
        self.tle_cache = {}
        self._load_tle_cache()

    def _init_database(self):
        """Initialize SQLite database for results (air-gapped)"""

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Create tables
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                timestamp INTEGER,
                frequency_hz REAL,
                power_db REAL,
                bandwidth_hz REAL,
                snr_db REAL,
                duration_sec REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS satellite_correlations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_id INTEGER,
                norad_id INTEGER,
                name TEXT,
                confidence REAL,
                doppler_residual_hz REAL,
                elevation_deg REAL,
                azimuth_deg REAL,
                range_km REAL,
                FOREIGN KEY(detection_id) REFERENCES signal_detections(id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_metadata (
                file_path TEXT PRIMARY KEY,
                processed_at INTEGER,
                sample_rate REAL,
                center_frequency REAL,
                num_samples INTEGER,
                num_detections INTEGER
            )
        """)

        self.conn.commit()

    def _load_tle_cache(self):
        """
        Load offline TLE cache
        In operational system: USB drive with weekly TLE updates
        """
        tle_cache_file = self.storage_path.parent / "tle_cache.json"

        if tle_cache_file.exists():
            with open(tle_cache_file, 'r') as f:
                self.tle_cache = json.load(f)
            logger.info(f"Loaded {len(self.tle_cache)} TLEs from cache")
        else:
            logger.warning("No TLE cache found - correlation will be limited")

    def process_directory(self, iq_directory: Path) -> Dict:
        """
        Batch process all IQ files in directory
        Returns summary statistics
        """

        iq_files = list(iq_directory.glob("*.iq")) + list(iq_directory.glob("*.cf32"))

        logger.info(f"Found {len(iq_files)} IQ files to process")

        results = {
            'files_processed': 0,
            'total_detections': 0,
            'total_correlations': 0,
            'errors': []
        }

        for iq_file in iq_files:
            try:
                # Check if already processed
                if self._is_processed(iq_file):
                    logger.info(f"Skipping already processed: {iq_file.name}")
                    continue

                logger.info(f"Processing: {iq_file.name}")

                # Process file
                file_results = self.process_file(iq_file)

                results['files_processed'] += 1
                results['total_detections'] += file_results['num_detections']
                results['total_correlations'] += file_results['num_correlations']

            except Exception as e:
                logger.error(f"Error processing {iq_file}: {e}")
                results['errors'].append(str(e))

        return results

    def process_file(self, filepath: Path) -> Dict:
        """
        Process single IQ file
        Returns detection and correlation statistics
        """

        # Read metadata
        metadata = self._read_file_metadata(filepath)

        if metadata is None:
            raise ValueError(f"Could not read metadata from {filepath}")

        logger.info(f"File: {metadata.num_samples} samples @ {metadata.sample_rate/1e6:.1f} Msps")

        # Read IQ samples (in chunks to handle large files)
        chunk_size = int(metadata.sample_rate * 10)  # 10 second chunks

        detections = []
        correlations = []

        with open(filepath, 'rb') as f:
            # Skip header
            f.seek(96)  # Header size from collector

            while True:
                chunk = self._read_iq_chunk(f, chunk_size)

                if chunk is None or len(chunk) == 0:
                    break

                # DSP: Detect signals in chunk
                chunk_detections = self._detect_signals(
                    chunk,
                    metadata.sample_rate,
                    metadata.center_frequency
                )

                detections.extend(chunk_detections)

        # Correlate detections with satellites
        for detection in detections:
            matches = self._correlate_satellite(detection, metadata)
            correlations.extend(matches)

        # Store results in database
        self._store_results(filepath, metadata, detections, correlations)

        return {
            'num_detections': len(detections),
            'num_correlations': len(correlations)
        }

    def _read_file_metadata(self, filepath: Path) -> Optional[IQFileMetadata]:
        """Read metadata from IQ file header"""

        try:
            with open(filepath, 'rb') as f:
                header = f.read(96)

                if len(header) < 96:
                    # No header, use defaults (for raw files)
                    return IQFileMetadata(
                        filepath=filepath,
                        sample_rate=2.4e6,  # Default
                        center_frequency=145.0e6,  # Default
                        timestamp_ns=int(filepath.stat().st_mtime * 1e9),
                        file_size_bytes=filepath.stat().st_size,
                        num_samples=(filepath.stat().st_size - 96) // 8  # complex64 = 8 bytes
                    )

                # Parse header
                magic, version, sample_rate, center_freq, timestamp_ns, _ = struct.unpack(
                    '<4sIddQ64s',
                    header
                )

                if magic != b'IQRF':
                    raise ValueError("Invalid file format")

                return IQFileMetadata(
                    filepath=filepath,
                    sample_rate=sample_rate,
                    center_frequency=center_freq,
                    timestamp_ns=timestamp_ns,
                    file_size_bytes=filepath.stat().st_size,
                    num_samples=(filepath.stat().st_size - 96) // 8
                )

        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return None

    def _read_iq_chunk(self, file_handle, num_samples: int) -> Optional[np.ndarray]:
        """Read chunk of IQ samples"""

        bytes_to_read = num_samples * 8  # complex64 = 8 bytes
        data = file_handle.read(bytes_to_read)

        if len(data) == 0:
            return None

        samples = np.frombuffer(data, dtype=np.complex64)
        return samples

    def _detect_signals(self, samples: np.ndarray, sample_rate: float, center_freq: float) -> List[SignalDetection]:
        """
        Signal detection using CFAR
        Same algorithm as real-time system but offline
        """

        # Compute PSD
        freqs, psd = scipy_signal.periodogram(
            samples,
            fs=sample_rate,
            window='hann',
            scaling='density',
            return_onesided=False
        )

        freqs = np.fft.fftshift(freqs)
        psd = np.fft.fftshift(psd)
        psd_db = 10 * np.log10(psd + 1e-12)

        # CFAR Detection
        guard_cells = 4
        ref_cells = 16
        kernel = np.ones(1 + (guard_cells*2) + (ref_cells*2))
        kernel[ref_cells : ref_cells + 1 + (guard_cells*2)] = 0
        kernel = kernel / (ref_cells * 2)

        psd_linear = 10**(psd_db/10)
        noise_estimate = scipy_signal.convolve(psd_linear, kernel, mode='same')

        adaptive_threshold_linear = noise_estimate * (10**(10/10))

        detected_indices = np.where(
            (psd_linear > adaptive_threshold_linear) &
            (psd_db > -80.0)
        )[0]

        # Extract peaks
        detections = []

        if len(detected_indices) > 0:
            clusters = np.split(detected_indices, np.where(np.diff(detected_indices) > 2)[0] + 1)

            for cluster in clusters:
                if len(cluster) == 0:
                    continue

                peak_idx = cluster[np.argmax(psd_db[cluster])]

                freq_offset = freqs[peak_idx]
                abs_freq = center_freq + freq_offset
                power_db = psd_db[peak_idx]
                noise_floor_db = 10 * np.log10(noise_estimate[peak_idx] + 1e-12)
                snr_db = power_db - noise_floor_db

                # Estimate bandwidth (FWHM)
                half_power = power_db - 3.0
                left_idx = peak_idx
                right_idx = peak_idx
                while left_idx > 0 and psd_db[left_idx] > half_power:
                    left_idx -= 1
                while right_idx < len(psd_db) - 1 and psd_db[right_idx] > half_power:
                    right_idx += 1

                bandwidth = abs(freqs[right_idx] - freqs[left_idx])

                detection = SignalDetection(
                    timestamp=datetime.now(timezone.utc),
                    frequency_hz=abs_freq,
                    power_db=power_db,
                    bandwidth_hz=bandwidth,
                    snr_db=snr_db,
                    duration_sec=len(samples) / sample_rate
                )

                detections.append(detection)

        return detections

    def _correlate_satellite(self, detection: SignalDetection, metadata: IQFileMetadata) -> List[SatelliteMatch]:
        """
        Correlate detected signal with satellite catalog
        Uses offline TLE cache
        """

        matches = []

        # For each satellite in cache, compute expected Doppler
        for norad_id, tle_data in self.tle_cache.items():
            # Simplified correlation (full SGP4 propagation in production)
            expected_doppler = self._compute_doppler_from_tle(
                tle_data,
                metadata.timestamp_ns,
                metadata.center_frequency
            )

            if expected_doppler is None:
                continue

            predicted_freq = metadata.center_frequency + expected_doppler
            residual = abs(detection.frequency_hz - predicted_freq)

            # Gaussian scoring
            sigma = 2500.0  # Hz
            confidence = np.exp(-0.5 * (residual / sigma)**2)

            if confidence > 0.6:  # Threshold
                match = SatelliteMatch(
                    norad_id=int(norad_id),
                    name=tle_data.get('name', 'Unknown'),
                    confidence=confidence,
                    doppler_residual_hz=residual,
                    elevation_deg=tle_data.get('elevation', 0.0),
                    azimuth_deg=tle_data.get('azimuth', 0.0),
                    range_km=tle_data.get('range_km', 0.0)
                )
                matches.append(match)

        # Sort by confidence
        matches.sort(key=lambda x: x.confidence, reverse=True)

        return matches[:3]  # Top 3 matches

    def _compute_doppler_from_tle(self, tle_data: Dict, timestamp_ns: int, freq_hz: float) -> Optional[float]:
        """
        Compute Doppler shift from TLE
        Placeholder - full SGP4 implementation needed
        """
        # TODO: Full SGP4 propagation
        # For now, use cached value if available
        return tle_data.get('doppler_hz', 0.0)

    def _store_results(self, filepath: Path, metadata: IQFileMetadata, detections: List, correlations: List):
        """Store analysis results in local database"""

        file_id = filepath.stem

        # Store detections
        for detection in detections:
            self.cursor.execute("""
                INSERT INTO signal_detections (file_id, timestamp, frequency_hz, power_db, bandwidth_hz, snr_db, duration_sec)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                int(detection.timestamp.timestamp() * 1e9),
                detection.frequency_hz,
                detection.power_db,
                detection.bandwidth_hz,
                detection.snr_db,
                detection.duration_sec
            ))

            detection_id = self.cursor.lastrowid

            # Store correlations for this detection
            # (simplified - in full system, link detection to correlation properly)

        for correlation in correlations:
            self.cursor.execute("""
                INSERT INTO satellite_correlations (detection_id, norad_id, name, confidence, doppler_residual_hz, elevation_deg, azimuth_deg, range_km)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                detection_id,
                correlation.norad_id,
                correlation.name,
                correlation.confidence,
                correlation.doppler_residual_hz,
                correlation.elevation_deg,
                correlation.azimuth_deg,
                correlation.range_km
            ))

        # Store metadata
        self.cursor.execute("""
            INSERT OR REPLACE INTO analysis_metadata (file_path, processed_at, sample_rate, center_frequency, num_samples, num_detections)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(filepath),
            int(datetime.now(timezone.utc).timestamp()),
            metadata.sample_rate,
            metadata.center_frequency,
            metadata.num_samples,
            len(detections)
        ))

        self.conn.commit()

    def _is_processed(self, filepath: Path) -> bool:
        """Check if file already processed"""

        self.cursor.execute("""
            SELECT COUNT(*) FROM analysis_metadata WHERE file_path = ?
        """, (str(filepath),))

        count = self.cursor.fetchone()[0]
        return count > 0

    def export_results(self, output_path: Path):
        """Export results to JSON for transfer to analysis workstation"""

        results = {
            'detections': [],
            'correlations': []
        }

        # Export detections
        self.cursor.execute("SELECT * FROM signal_detections")
        for row in self.cursor.fetchall():
            results['detections'].append({
                'id': row[0],
                'file_id': row[1],
                'timestamp': row[2],
                'frequency_hz': row[3],
                'power_db': row[4],
                'bandwidth_hz': row[5],
                'snr_db': row[6],
                'duration_sec': row[7]
            })

        # Export correlations
        self.cursor.execute("SELECT * FROM satellite_correlations")
        for row in self.cursor.fetchall():
            results['correlations'].append({
                'id': row[0],
                'detection_id': row[1],
                'norad_id': row[2],
                'name': row[3],
                'confidence': row[4],
                'doppler_residual_hz': row[5],
                'elevation_deg': row[6],
                'azimuth_deg': row[7],
                'range_km': row[8]
            })

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results exported to {output_path}")

    def close(self):
        """Close database connection"""
        self.conn.close()

def main():
    """Offline processor entry point"""

    import argparse

    parser = argparse.ArgumentParser(description='Offline IQ Processor (Air-Gapped)')
    parser.add_argument('--input', type=str, required=True, help='Directory with IQ files')
    parser.add_argument('--db', type=str, default='./analysis.db', help='SQLite database path')
    parser.add_argument('--export', type=str, help='Export results to JSON')

    args = parser.parse_args()

    processor = OfflineProcessor(
        storage_path=Path(args.input),
        db_path=Path(args.db)
    )

    try:
        # Process all files
        results = processor.process_directory(Path(args.input))

        logger.info("="*60)
        logger.info("PROCESSING COMPLETE")
        logger.info(f"Files processed: {results['files_processed']}")
        logger.info(f"Total detections: {results['total_detections']}")
        logger.info(f"Total correlations: {results['total_correlations']}")
        logger.info(f"Errors: {len(results['errors'])}")
        logger.info("="*60)

        # Export if requested
        if args.export:
            processor.export_results(Path(args.export))

    finally:
        processor.close()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    main()
