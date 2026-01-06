import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from api import main
    print("[OK] api.main imported")
except ImportError as e:
    print(f"[FAIL] api.main import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] api.main general error: {e}")
    sys.exit(1)

try:
    from api import websockets
    print("[OK] api.websockets imported")
except ImportError as e:
    print(f"[FAIL] api.websockets import error: {e}")
except Exception as e:
    print(f"[FAIL] api.websockets error: {e}")

try:
    from api.routes import intelligence
    print("[OK] api.routes.intelligence imported")
except ImportError as e:
    print(f"[FAIL] api.routes.intelligence import error: {e}")
except Exception as e:
    print(f"[FAIL] api.routes.intelligence error: {e}")

print("API Verification Complete.")
