# processors/correlation_engine.py
"""
Deep Tech Correlation Engine.
Implements Bayesian Likelihood Estimation & Hungarian Algorithm for Signal Assignment.

FEATURES:
- Probabilistic Matching: Uses Gaussian likelihoods for Doppler residuals.
- Multi-Target Tracking: Handles multiple simultaneous signals and satellites.
- Global Optimization: Uses Linear Sum Assignment (Hungarian Algo) to prevent conflicts.
"""

import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import logging
from scipy.optimize import linear_sum_assignment
from dataclasses import dataclass

from trackers.tle_manager import tle_manager

logger = logging.getLogger(__name__)

@dataclass
class CorrelationHypothesis:
    norad_id: int
    name: str
    confidence: float
    doppler_residual: float
    signal_freq: float
    predicted_freq: float
    
class CorrelationEngine:
    """
    Advanced Signal Correlator.
    """
    
    def __init__(self):
        self.frequency_tolerance_hz = 10000.0  # Coarse window
        self.doppler_tolerance_hz = 2500.0     # Fine window for confidence
        self.min_confidence_threshold = 0.6    # Minimum valid match
        
    def correlated_batch_analysis(self, 
                                detected_signals: List[Dict]) -> List[Dict]:
        """
        Process a batch of signals efficiently using Matrix operations.
        
        Args:
            detected_signals: List of dicts {'freq': float, 'power': float, 'bw': float}
            
        Returns:
            List of detected_signals with added 'match' fields.
        """
        if not detected_signals:
            return []
            
        # 1. Update Ephemeris Cache
        tle_manager.refresh_visible_cache(horizon_deg=5.0)
        visible_ids = tle_manager.active_subset
        
        if not visible_ids:
            return detected_signals # No satellites to correlate against
            
        # 2. Build Cost Matrix
        # Rows = Signals, Cols = Satellites
        n_signals = len(detected_signals)
        n_sats = len(visible_ids)
        
        # Matrix of residuals (Signal Freq - (Sat Center + Doppler))
        # We need a reference frequency for each satellite.
        # SYSTEM ASSUMPTION: Monitoring a specific band where center_freq is known.
        # For this implementation, we assume the Receiver Center Frequency is the target.
        # In a real system, we'd query the DB for each satellite's downlink freq.
        
        cost_matrix = np.full((n_signals, n_sats), 1e9) # Initialize with high cost
        
        # Pre-compute Dopplers for all visible sats
        # Optimization: We can do this once per batch
        sat_dopplers = {}
        target_freq = detected_signals[0]['center_freq'] # Assuming all signals from same capture
        
        for idx, nid in enumerate(visible_ids):
            sat_dopplers[idx] = tle_manager.predict_doppler(nid, target_freq)
            
        # Fill Matrix
        hypotheses_map = {} # (sig_idx, sat_idx) -> Hypothesis
        
        for r, signal in enumerate(detected_signals):
            meas_freq = signal['freq']
            
            for c, nid in enumerate(visible_ids):
                pred_doppler = sat_dopplers[c]
                expected_freq = target_freq + pred_doppler
                
                residual = abs(meas_freq - expected_freq)
                
                if residual < self.frequency_tolerance_hz:
                    # Calculate Cost (Inverse Confidence)
                    # Gaussian Score: exp(-residual^2 / 2sigma^2)
                    sigma = self.doppler_tolerance_hz / 3.0
                    confidence = np.exp(-0.5 * (residual / sigma)**2)
                    
                    cost_matrix[r, c] = 1.0 - confidence
                    
                    hypotheses_map[(r, c)] = CorrelationHypothesis(
                        norad_id=nid,
                        name=tle_manager.metadata.get(nid, {}).get('name', str(nid)),
                        confidence=confidence,
                        doppler_residual=residual,
                        signal_freq=meas_freq,
                        predicted_freq=expected_freq
                    )
        
        # 3. Hungarian Algorithm for Global Assignment
        # This prevents one satellite matching multiple signals (unless multi-carrier, 
        # but for simple correlation we assume 1-to-1 or best-fit)
        
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # 4. Compile Results
        results = detected_signals.copy()
        
        for r, c in zip(row_ind, col_ind):
            cost = cost_matrix[r, c]
            if cost < (1.0 - self.min_confidence_threshold): # If improved confidence meets threshold
                if (r, c) in hypotheses_map:
                    hypo = hypotheses_map[(r, c)]
                    results[r]['match'] = {
                        'norad_id': hypo.norad_id,
                        'name': hypo.name,
                        'confidence': hypo.confidence,
                        'residual': hypo.doppler_residual,
                        'doppler_shift': sat_dopplers[c]
                    }
        
        return results

    def correlate_instantaneous(self, measured_freq: float, center_freq: float) -> List[Dict]:
        """
        Legacy/Single wrapper for the batch engine.
        Useful for individual checks from the Scheduler.
        """
        signal = {'freq': measured_freq, 'center_freq': center_freq, 'power': 0}
        results = self.correlated_batch_analysis([signal])
        
        if results and 'match' in results[0]:
            match = results[0]['match']
            return [match] # Return list for compatibility with previous interface
        return []

# Singleton
correlation_engine = CorrelationEngine()
