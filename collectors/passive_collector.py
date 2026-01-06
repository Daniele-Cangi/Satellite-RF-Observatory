# collectors/passive_collector.py
"""
Passive RF Collector - Sistema Grigio
Zero network footprint, direct-to-disk IQ recording
"""

import numpy as np
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
import struct
import hashlib
import os

try:
    from SoapySDR import Device, SOAPY_SDR_RX, SOAPY_SDR_CF32
except ImportError:
    Device = None

logger = logging.getLogger(__name__)

@dataclass
class CollectionConfig:
    """Configuration for passive collection"""

    # SDR Hardware
    device: str = "driver=rtlsdr"
    sample_rate: float = 2.4e6
    center_frequency: float = 145.0e6
    gain: float = 40.0

    # Storage
    storage_path: Path = Path("/mnt/encrypted/iq_captures")
    max_file_size_mb: int = 1024  # 1GB per file
    compression: bool = True
    encryption_key: Optional[bytes] = None

    # Operational Security
    randomize_filenames: bool = True
    scrub_metadata: bool = True  # Remove timestamps, GPS coords, etc.

    # Collection Parameters
    duration_seconds: int = 3600  # 1 hour continuous
    bandwidth_hz: float = 2.4e6

class PassiveCollector:
    """
    Headless IQ recorder - zero network, zero API
    Designed for covert/gray collection operations
    """

    def __init__(self, config: CollectionConfig):
        self.config = config
        self.sdr = None
        self.stream = None
        self.current_file = None
        self.bytes_written = 0

        # Create storage directory
        self.config.storage_path.mkdir(parents=True, exist_ok=True)

        # Generate session ID (random if OPSEC enabled)
        if config.randomize_filenames:
            self.session_id = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
        else:
            self.session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def initialize_sdr(self) -> bool:
        """Initialize SDR hardware in stealth mode"""

        if Device is None:
            logger.error("SoapySDR not available")
            return False

        try:
            self.sdr = Device(self.config.device)

            # Configure receiver
            self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.config.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.config.center_frequency)
            self.sdr.setGain(SOAPY_SDR_RX, 0, self.config.gain)

            # Disable any LED/indicators if supported
            try:
                self.sdr.writeSetting("led", "off")
            except:
                pass

            # Setup stream
            self.stream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)

            logger.info(f"SDR initialized: {self.config.center_frequency/1e6:.3f} MHz @ {self.config.sample_rate/1e6:.1f} Msps")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize SDR: {e}")
            return False

    def start_collection(self):
        """Start continuous IQ capture"""

        if not self.sdr or not self.stream:
            raise RuntimeError("SDR not initialized")

        self.sdr.activateStream(self.stream)
        logger.info(f"Collection started - Session: {self.session_id}")

        buffer_size = 16384
        buffer = np.zeros(buffer_size, dtype=np.complex64)

        start_time = time.time()
        samples_captured = 0

        try:
            while True:
                # Check duration limit
                if time.time() - start_time >= self.config.duration_seconds:
                    logger.info("Collection duration reached")
                    break

                # Read samples from SDR
                sr = self.sdr.readStream(self.stream, [buffer], buffer_size, timeoutUs=1000000)

                if sr.ret > 0:
                    samples = buffer[:sr.ret]

                    # Write to disk
                    self._write_samples(samples, sr.timeNs)

                    samples_captured += sr.ret

                    # Status update (every 10 seconds)
                    if samples_captured % int(self.config.sample_rate * 10) == 0:
                        gb_written = self.bytes_written / (1024**3)
                        logger.info(f"Captured: {samples_captured/1e6:.1f}M samples, {gb_written:.2f} GB written")

        except KeyboardInterrupt:
            logger.info("Collection interrupted by user")
        except Exception as e:
            logger.error(f"Collection error: {e}")
        finally:
            self._close_current_file()
            self.sdr.deactivateStream(self.stream)
            logger.info(f"Collection stopped - Total: {samples_captured/1e6:.1f}M samples")

    def _write_samples(self, samples: np.ndarray, timestamp_ns: int):
        """Write IQ samples to disk with optional encryption"""

        # Check if we need a new file (size limit)
        if self.current_file is None or self.bytes_written >= self.config.max_file_size_mb * 1024**2:
            self._close_current_file()
            self._open_new_file()

        # Convert to bytes
        data = samples.tobytes()

        # Optional encryption (AES-256-GCM recommended in production)
        if self.config.encryption_key:
            data = self._encrypt_chunk(data)

        # Write to file
        self.current_file.write(data)
        self.bytes_written += len(data)

    def _open_new_file(self):
        """Create new IQ data file"""

        # Generate filename
        if self.config.randomize_filenames:
            # Random filename for OPSEC
            filename = f"{hashlib.sha256(os.urandom(16)).hexdigest()[:32]}.iq"
        else:
            # Timestamp-based filename
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"iq_{timestamp}.cf32"

        filepath = self.config.storage_path / filename

        self.current_file = open(filepath, 'wb')
        self.bytes_written = 0

        # Write metadata header (if not scrubbed)
        if not self.config.scrub_metadata:
            header = self._create_header()
            self.current_file.write(header)

        logger.info(f"New file: {filepath}")

    def _close_current_file(self):
        """Close current file and scrub metadata if required"""

        if self.current_file:
            self.current_file.close()

            # Scrub filesystem metadata (timestamps, etc.)
            if self.config.scrub_metadata:
                # Set random timestamps to prevent correlation
                random_time = time.time() - np.random.randint(86400, 86400*365)
                os.utime(self.current_file.name, (random_time, random_time))

            self.current_file = None

    def _create_header(self) -> bytes:
        """
        Create binary header with collection metadata
        Format: [magic][version][sample_rate][center_freq][timestamp][reserved]
        """
        magic = b'IQRF'
        version = 1

        header = struct.pack(
            '<4sIddQ64s',
            magic,
            version,
            self.config.sample_rate,
            self.config.center_frequency,
            int(time.time() * 1e9),  # nanosecond timestamp
            b'\x00' * 64  # Reserved for future use
        )

        return header

    def _encrypt_chunk(self, data: bytes) -> bytes:
        """
        Encrypt data chunk (placeholder - use proper crypto in production)
        Recommended: AES-256-GCM with authenticated encryption
        """
        # TODO: Implement proper encryption
        # from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        # cipher = AESGCM(self.config.encryption_key)
        # nonce = os.urandom(12)
        # encrypted = cipher.encrypt(nonce, data, None)
        # return nonce + encrypted

        return data  # Placeholder

    def stop(self):
        """Emergency stop"""
        if self.sdr and self.stream:
            self.sdr.deactivateStream(self.stream)
            self.sdr.closeStream(self.stream)
        self._close_current_file()

def main():
    """Headless collector entry point"""

    import argparse

    parser = argparse.ArgumentParser(description='Passive RF Collector (Gray System)')
    parser.add_argument('--freq', type=float, default=145.0, help='Center frequency (MHz)')
    parser.add_argument('--rate', type=float, default=2.4, help='Sample rate (Msps)')
    parser.add_argument('--gain', type=float, default=40.0, help='RF gain (dB)')
    parser.add_argument('--duration', type=int, default=3600, help='Collection duration (seconds)')
    parser.add_argument('--storage', type=str, default='/mnt/encrypted/iq', help='Storage path')
    parser.add_argument('--stealth', action='store_true', help='Enable OPSEC features')

    args = parser.parse_args()

    config = CollectionConfig(
        center_frequency=args.freq * 1e6,
        sample_rate=args.rate * 1e6,
        gain=args.gain,
        duration_seconds=args.duration,
        storage_path=Path(args.storage),
        randomize_filenames=args.stealth,
        scrub_metadata=args.stealth
    )

    collector = PassiveCollector(config)

    if collector.initialize_sdr():
        collector.start_collection()
    else:
        logger.error("Failed to initialize collector")
        return 1

    return 0

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    sys.exit(main())
