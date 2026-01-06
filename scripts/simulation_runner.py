import asyncio
import numpy as np
import logging
import sys
import os
from datetime import datetime, timedelta, timezone
import random

# Setup Paths
sys.path.append(os.getcwd())

# Configuration
from core.config import get_config
config = get_config()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulation")

from skyfield.api import utc

# Import Core Components
from trackers.tle_manager import tle_manager
from processors.correlation_engine import correlation_engine
from workers.scheduler import Scheduler

# Mock Receiver Worker
class MockReceiverWorker:
    def __init__(self, start_freq=137.5e6):
        self.config = type('Config', (), {'center_frequency': start_freq})()
        # We don't need real queues for this synchronous/step-wise simulation runner
        # or we can simulate the interaction.
        self.data_queue = None 

async def run_simulation():
    print("="*60)
    print("SIS-PRO: END-TO-END LOGIC SIMULATION")
    print("="*60)

    # 1. Initialize TLEs
    print("[1] Initializing TLE Manager (Space-Track/Celestrak)...")
    await tle_manager.update_tles()
    
    if not tle_manager.satellites:
        print("[WARN] No TLEs loaded via Network. Injecting DUMMY TLE for Simulation.")
        # Inject ISS TLE
        dummy_tle_line1 = "1 25544U 98067A   24001.00000000  .00016717  00000+0  10270-3 0  9990"
        dummy_tle_line2 = "2 25544  51.6416 348.5133 0005423 128.5377 348.8687 15.49524672  017"
        
        from sgp4.api import Satrec
        from skyfield.api import EarthSatellite
        
        satrec = Satrec.twoline2rv(dummy_tle_line1, dummy_tle_line2)
        target_norad = 25544
        target_name = "ISS (MOCK)"
        
        if satrec.error == 0:
            tle_manager.satellites[target_norad] = satrec
            tle_manager.skyfield_sats[target_norad] = EarthSatellite(dummy_tle_line1, dummy_tle_line2, target_name, tle_manager.ts)
            tle_manager.metadata[target_norad] = {'name': target_name}
        else:
            print("[FAIL] Dummy TLE invalid.")
            return
            
        print(f"[OK] 1 Mock Satellite Loaded.")
    else:
         print(f"[OK] {len(tle_manager.satellites)} Satellites Loaded.")
    
    # 2. Select a Target Satellite for Simulation (e.g., a NOAA or ISS)
    # Let's find a visible satellite or just pick a known popular one
    target_norad = 25544 # ISS
    target_name = "ISS"
    
    if target_norad not in tle_manager.satellites:
        # Fallback to first available
        target_norad = list(tle_manager.satellites.keys())[0]
        target_name = tle_manager.metadata[target_norad]['name']
    else:
        target_name = tle_manager.metadata[target_norad]['name']

    print(f"[2] Simulation Target: {target_name} ({target_norad})")
    
    # 3. Predict Doppler Shift
    print(f"[3] Calculating Geometry & Doppler...")
    # Simulate current time
    now = datetime.now(utc)
    
    # We force the satellite to be 'visible' for the test by using its current state
    # regardless of actual horizon (assuming we are tracking it)
    state = tle_manager.compute_satellite_state(target_norad, now)
    
    if not state:
        print("[FAIL] Could not compute state.")
        return

    print(f"    Position (km): {state.position_eci_km}")
    print(f"    Range (km): {state.range_km:.2f}")
    print(f"    Elevation (deg): {state.elevation_deg:.2f}")
    
    # Simulate a signal at 145.800 MHz to match receiver center freq (Simplification for Engine verify)
    base_freq = 145800000.0 
    expected_doppler = -(state.range_rate_kms / 299792.458) * base_freq
    received_freq = base_freq + expected_doppler
    
    # Add some noise/drift to make it realistic
    measured_freq = received_freq + random.uniform(-100, 100) # +/- 100 Hz error
    
    print(f"    Base Freq: {base_freq/1e6:.6f} MHz")
    print(f"    Expected Doppler: {expected_doppler:.2f} Hz")
    print(f"    Simulated Rx Freq: {measured_freq/1e6:.6f} MHz")

    # 4. Inject into Correlation Engine
    print("[4] Injecting Signal into Correlation Engine...")
    
    # We pretend the receiver is tuned to close to this frequency
    center_freq = 145800000.0
    
    # Create synthetic peak detection
    synthetic_signal = {
        'freq': measured_freq,
        'center_freq': center_freq,
        'power': 0.05, # Linear power
        'bw': 12500
    }
    
    # Run Batch Analysis
    # NOTE: The engine usually re-computes 'visible' cache. 
    # For this test to work, the satellite MUST be in the active_subset.
    # If ISS is below horizon, it won't be in active_subset.
    # We force it into active_subset if needed for the test.
    
    tle_manager.refresh_visible_cache(horizon_deg=-90.0) # Force all visible for test
    print(f"DEBUG: Active Subset Size: {len(tle_manager.active_subset)}")
    print(f"DEBUG: Active Subset: {tle_manager.active_subset}")
    
    # Monkey patch to prevent engine from filtering out our test satellite (since it calls refresh again with +5 deg)
    original_refresh = tle_manager.refresh_visible_cache
    tle_manager.refresh_visible_cache = lambda *args, **kwargs: None
    
    try:
        results = correlation_engine.correlated_batch_analysis([synthetic_signal])
    finally:
        tle_manager.refresh_visible_cache = original_refresh
    
    # 5. Analyze Results
    print("[5] Analyzing Results...")
    match_found = False
    
    for res in results:
        if 'match' in res:
            m = res['match']
            print(f"    [MATCH DETECTED]")
            print(f"    Object: {m['name']} ({m['norad_id']})")
            print(f"    Confidence: {m['confidence']:.4f}")
            print(f"    Residual: {m['residual']:.2f} Hz")
            
            if m['norad_id'] == target_norad:
                match_found = True
                print("    >>> SUCCESS: Correct Object Identified! <<<")
            else:
                print("    >>> WARNING: Indirect Match / False Positive <<<")
        else:
            print("    [NO MATCH]")

    if not match_found:
        print("\n[FAIL] Simulation failed to identify target.")
        
        # Debugging aid
        print("Debugging:")
        pred_dop = tle_manager.predict_doppler(target_norad, center_freq)
        print(f"Predicted Doppler by Manager: {pred_dop}")
    else:
        print("\n[SUCCESS] Pipeline Verification Passed.")

import traceback

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except Exception:
        traceback.print_exc()

