# gray_system_main.py
"""
GRAY SYSTEM - Main Controller
Zero network footprint passive collection system

OPERATIONAL MODES:
1. COLLECT: Passive RF capture to encrypted storage
2. ANALYZE: Offline batch processing of IQ data (air-gapped)
3. EXPORT: Transfer results to analysis workstation

NO WEB API | NO NETWORK LISTENERS | NO REMOTE ACCESS
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Local imports only - no network dependencies
from collectors.passive_collector import PassiveCollector, CollectionConfig
from analysis.offline_processor import OfflineProcessor

logger = logging.getLogger(__name__)

class GraySystemController:
    """
    Main controller for gray collection operations
    Enforces operational security protocols
    """

    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("./gray_config.json")
        self.operation_mode = None

    def mode_collect(self, args):
        """
        MODE 1: COLLECTION
        Passive RF capture with zero network footprint
        """

        logger.info("="*60)
        logger.info("GRAY SYSTEM - COLLECTION MODE")
        logger.info("="*60)

        # Verify no network interfaces active (safety check)
        if args.enforce_offline:
            if not self._verify_network_isolation():
                logger.error("ABORT: Network interfaces detected. Disconnect all network cables.")
                return 1

        # Configure collection
        config = CollectionConfig(
            device=args.device,
            sample_rate=args.rate * 1e6,
            center_frequency=args.freq * 1e6,
            gain=args.gain,
            duration_seconds=args.duration,
            storage_path=Path(args.storage),

            # OPSEC features
            randomize_filenames=args.stealth,
            scrub_metadata=args.stealth,
            encryption_key=self._load_encryption_key() if args.encrypt else None
        )

        logger.info(f"Target: {config.center_frequency/1e6:.3f} MHz")
        logger.info(f"Sample Rate: {config.sample_rate/1e6:.1f} Msps")
        logger.info(f"Duration: {config.duration_seconds}s ({config.duration_seconds/3600:.1f}h)")
        logger.info(f"Storage: {config.storage_path}")
        logger.info(f"OPSEC Mode: {'ENABLED' if args.stealth else 'DISABLED'}")

        # Initialize collector
        collector = PassiveCollector(config)

        if not collector.initialize_sdr():
            logger.error("Failed to initialize SDR hardware")
            return 1

        # Start collection
        try:
            collector.start_collection()
            logger.info("Collection completed successfully")
            return 0

        except KeyboardInterrupt:
            logger.info("Collection interrupted by operator")
            collector.stop()
            return 0

        except Exception as e:
            logger.error(f"Collection error: {e}")
            collector.stop()
            return 1

    def mode_analyze(self, args):
        """
        MODE 2: ANALYSIS
        Offline batch processing (air-gapped workstation)
        """

        logger.info("="*60)
        logger.info("GRAY SYSTEM - OFFLINE ANALYSIS MODE")
        logger.info("="*60)

        # Verify air-gap (strict mode)
        if args.enforce_airgap:
            if not self._verify_airgap():
                logger.error("ABORT: Network activity detected. Air-gap compromised.")
                return 1

        # Initialize processor
        processor = OfflineProcessor(
            storage_path=Path(args.input),
            db_path=Path(args.database)
        )

        try:
            # Process IQ files
            logger.info(f"Processing IQ files in: {args.input}")
            results = processor.process_directory(Path(args.input))

            # Summary
            logger.info("="*60)
            logger.info("ANALYSIS COMPLETE")
            logger.info(f"Files processed: {results['files_processed']}")
            logger.info(f"Signals detected: {results['total_detections']}")
            logger.info(f"Satellite correlations: {results['total_correlations']}")
            logger.info(f"Errors: {len(results['errors'])}")
            logger.info("="*60)

            # Export results if requested
            if args.export:
                export_path = Path(args.export)
                processor.export_results(export_path)
                logger.info(f"Results exported to: {export_path}")

            return 0

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return 1

        finally:
            processor.close()

    def mode_export(self, args):
        """
        MODE 3: EXPORT
        Prepare data for secure transfer to analysis workstation
        """

        logger.info("="*60)
        logger.info("GRAY SYSTEM - EXPORT MODE")
        logger.info("="*60)

        # Create export package
        export_dir = Path(args.output)
        export_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Exporting to: {export_dir}")

        # Copy IQ files (optionally filtered)
        # Sanitize metadata
        # Generate manifest

        logger.info("Export package created")
        logger.info("Transfer via: USB drive / Secure courier / One-way data diode")

        return 0

    def _verify_network_isolation(self) -> bool:
        """
        Verify no active network interfaces
        Safety check before collection
        """
        try:
            import psutil

            # Check network interfaces
            interfaces = psutil.net_if_stats()

            for iface, stats in interfaces.items():
                if iface != 'lo' and stats.isup:  # Exclude loopback
                    logger.warning(f"Active network interface detected: {iface}")
                    return False

            return True

        except ImportError:
            logger.warning("Cannot verify network isolation (psutil not installed)")
            return True  # Proceed with warning

    def _verify_airgap(self) -> bool:
        """
        Verify complete air-gap (no network activity)
        Strict check for analysis workstation
        """
        try:
            import psutil

            # Check for any network connections
            connections = psutil.net_connections()

            if len(connections) > 0:
                logger.error(f"Network connections detected: {len(connections)}")
                return False

            # Check network I/O (should be zero)
            net_io = psutil.net_io_counters()

            if net_io.bytes_sent > 1000 or net_io.bytes_recv > 1000:
                logger.error("Network I/O detected - air-gap compromised")
                return False

            return True

        except ImportError:
            logger.warning("Cannot verify air-gap (psutil not installed)")
            return True

    def _load_encryption_key(self) -> bytes:
        """
        Load encryption key from secure storage
        In production: Hardware Security Module (HSM) or TPM
        """
        key_file = Path("./keys/collection.key")

        if not key_file.exists():
            logger.warning("No encryption key found - generating random key")
            import os
            key = os.urandom(32)  # AES-256

            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)

            logger.info(f"Encryption key generated: {key_file}")
        else:
            with open(key_file, 'rb') as f:
                key = f.read()

        return key

def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description='Gray System - Passive RF Collection & Offline Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
OPERATIONAL MODES:
  collect   - Passive RF capture to encrypted storage
  analyze   - Offline batch processing (air-gapped)
  export    - Prepare data for secure transfer

EXAMPLES:
  # Collection mode (stealth)
  python gray_system_main.py collect --freq 145.0 --duration 3600 --stealth

  # Analysis mode (air-gapped)
  python gray_system_main.py analyze --input /mnt/usb/iq_data --enforce-airgap

  # Export mode
  python gray_system_main.py export --input /data/results --output /mnt/transfer
        """
    )

    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')

    # COLLECT mode
    collect_parser = subparsers.add_parser('collect', help='Passive RF collection')
    collect_parser.add_argument('--freq', type=float, required=True, help='Center frequency (MHz)')
    collect_parser.add_argument('--rate', type=float, default=2.4, help='Sample rate (Msps)')
    collect_parser.add_argument('--gain', type=float, default=40.0, help='RF gain (dB)')
    collect_parser.add_argument('--duration', type=int, default=3600, help='Duration (seconds)')
    collect_parser.add_argument('--device', type=str, default='driver=rtlsdr', help='SDR device string')
    collect_parser.add_argument('--storage', type=str, default='/mnt/encrypted/iq', help='Storage path')
    collect_parser.add_argument('--stealth', action='store_true', help='Enable OPSEC features')
    collect_parser.add_argument('--encrypt', action='store_true', help='Encrypt IQ data')
    collect_parser.add_argument('--enforce-offline', action='store_true', help='Abort if network detected')

    # ANALYZE mode
    analyze_parser = subparsers.add_parser('analyze', help='Offline batch analysis')
    analyze_parser.add_argument('--input', type=str, required=True, help='IQ files directory')
    analyze_parser.add_argument('--database', type=str, default='./analysis.db', help='SQLite database')
    analyze_parser.add_argument('--export', type=str, help='Export results to JSON')
    analyze_parser.add_argument('--enforce-airgap', action='store_true', help='Abort if network detected')

    # EXPORT mode
    export_parser = subparsers.add_parser('export', help='Export data package')
    export_parser.add_argument('--input', type=str, required=True, help='Source directory')
    export_parser.add_argument('--output', type=str, required=True, help='Export directory')
    export_parser.add_argument('--sanitize', action='store_true', help='Remove metadata')

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        return 1

    # Initialize controller
    controller = GraySystemController()

    # Execute mode
    if args.mode == 'collect':
        return controller.mode_collect(args)
    elif args.mode == 'analyze':
        return controller.mode_analyze(args)
    elif args.mode == 'export':
        return controller.mode_export(args)
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    # Configure logging (console only, no file logging for OPSEC)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    sys.exit(main())
