import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

print(f"Checking imports from {project_root}")

try:
    from core.config import config
    print("[OK] core.config imported")
    print(f"     Environment: {config.environment}")
    print(f"     DB URL: {config.database.url}")
except Exception as e:
    print(f"[FAIL] core.config: {e}")

try:
    from core.database import Base, Satellite
    print("[OK] core.database imported")
    print(f"     Satellite Table: {Satellite.__tablename__}")
except Exception as e:
    print(f"[FAIL] core.database: {e}")

try:
    from receivers.base_receiver import BaseReceiver
    print("[OK] receivers.base_receiver imported")
except Exception as e:
    print(f"[FAIL] receivers.base_receiver: {e}")

try:
    from receivers.ku_band_receiver import StarlinkBeaconReceiver
    print("[OK] receivers.ku_band_receiver imported")
except ImportError as e:
    print(f"[WARN] receivers.ku_band_receiver import warning (likely SoapySDR missing): {e}")
except Exception as e:
    print(f"[FAIL] receivers.ku_band_receiver: {e}")

try:
    from trackers.tle_manager import TLEManager
    print("[OK] trackers.tle_manager imported")
except ImportError as e:
    print(f"[WARN] trackers.tle_manager import warning (deps might be missing): {e}")
except Exception as e:
    print(f"[FAIL] trackers.tle_manager: {e}")

try:
    from processors.correlation_engine import CorrelationEngine
    print("[OK] processors.correlation_engine imported")
except ImportError as e:
    print(f"[WARN] processors.correlation_engine import warning (deps might be missing): {e}")
except Exception as e:
    print(f"[FAIL] processors.correlation_engine: {e}")

try:
    from receivers import sdr_manager
    print("[OK] receivers.sdr_manager imported")
except ImportError as e:
    print(f"[WARN] receivers.sdr_manager import warning: {e}")
except Exception as e:
    print(f"[FAIL] receivers.sdr_manager: {e}")

try:
    from workers.receiver_worker import ReceiverWorker
    print("[OK] workers.receiver_worker imported")
except ImportError as e:
    print(f"[WARN] workers.receiver_worker import warning: {e}")
except Exception as e:
    print(f"[FAIL] workers.receiver_worker: {e}")

try:
    from workers import scheduler
    print("[OK] workers.scheduler imported")
except ImportError as e:
    print(f"[WARN] workers.scheduler import warning: {e}")
except Exception as e:
    print(f"[FAIL] workers.scheduler: {e}")

print("Verification complete.")


