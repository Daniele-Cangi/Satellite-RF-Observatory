# workers/scheduler.py
"""
Task scheduler and main analysis loop.
"""

import asyncio
import logging
import numpy as np
import time
from typing import List, Dict, Optional
from queue import Empty

from processors.correlation_engine import correlation_engine
from core.database import get_db, Observation
from processors.correlation_engine import correlation_engine
from core.database import get_db, Observation
from api.schemas import SignalDetection  # For websocket broadcast structure
from scipy import signal as scipy_signal

logger = logging.getLogger(__name__)

class Scheduler:
    """
    Manages the analysis loop and coordinates between Receiver and API.
    """
    
    def __init__(self, receiver_worker, websocket_manager):
        self.receiver_worker = receiver_worker
        self.manager = websocket_manager # ConnectionManager instance
        self.is_running = False
        
    async def run(self):
        """
        Async loop that consumes data from SDR and runs correlation.
        """
        self.is_running = True
        
        # Wait for TLE initialization
        from trackers.tle_manager import tle_manager
        if not tle_manager.satellites:
            logger.info("Scheduler waiting for TLE update...")
            await tle_manager.update_tles()
        
        logger.info("Scheduler loop started.")
        
        while self.is_running:
            # 1. Drain Queue from Receiver Process
            batch_samples = []
            try:
                # Get all available items (up to a limit)
                for _ in range(10): 
                     if self.receiver_worker and self.receiver_worker.data_queue:
                        try:
                            data, metrics = self.receiver_worker.data_queue.get_nowait()
                            batch_samples.append((data, metrics))
                        except Empty:
                            break
            except Exception as e:
                logger.error(f"Scheduler queue error: {e}")
                
            if not batch_samples:
                await asyncio.sleep(0.01)
                continue
                
            # 2. Process Batch
            for samples, metrics in batch_samples:
                # Ensure samples are numpy array
                if not isinstance(samples, np.ndarray):
                    samples = np.array(samples)
                    
                if len(samples) == 0:
                    continue

                center_freq = self.receiver_worker.config.center_frequency \
                    if hasattr(self.receiver_worker, 'config') else 145000000
                sample_rate = self.receiver_worker.config.sample_rate \
                    if hasattr(self.receiver_worker, 'config') else 2400000

                # --- DSP: Periodogram (FFT) ---
                # Calculate Power Spectral Density
                freqs, psd = scipy_signal.periodogram(
                    samples, 
                    fs=sample_rate, 
                    window='hann', 
                    scaling='density',
                    return_onesided=False # We want full spectrum for complex IQ
                )
                
                # Shift zero-frequency to center
                freqs = np.fft.fftshift(freqs)
                psd = np.fft.fftshift(psd)
                
                # Convert to dB
                psd_db = 10 * np.log10(psd + 1e-12)
                
                # --- WebSocket Broadcast: Spectrum ---
                # Downsample for UI (1024 bins) to reduce bandwidth
                target_bins = 1024
                step = max(1, len(psd_db) // target_bins)
                psd_downsampled = psd_db[::step][:target_bins]
                
                spectrum_frame = {
                    "timestamp": time.time(),
                    "center_freq": center_freq,
                    "span_hz": sample_rate,
                    "bins": len(psd_downsampled),
                    "data": psd_downsampled.tolist()
                }
                # Broadcast fire-and-forget
                asyncio.create_task(self.manager.broadcast("spectrum", spectrum_frame))

                # --- DSP: Adaptive CFAR Detection ---
                # Cell-Averaging Constant False Alarm Rate (CA-CFAR)
                # Used in radar/sonar to detect targets in varying noise backgrounds.
                
                # CFAR Parameters
                guard_cells = 4
                ref_cells = 16
                bias = 3.0 # Multiplier for threshold (linear scale) or offset (dB)
                
                # CFAR Logic (1D Rolling Filter)
                # Using a sliding window to estimate local noise floor per bin
                
                # Pre-calculate kernel for fast convolution
                # Kernel: [1...1, 0...0, 1...1] / N_ref
                kernel = np.ones(1 + (guard_cells*2) + (ref_cells*2))
                kernel[ref_cells : ref_cells + 1 + (guard_cells*2)] = 0
                kernel = kernel / (ref_cells * 2)
                
                # Convolve to get noise estimate (Linear Power)
                # We use linear power for averaging, then convert to dB for thresholding, or stay in linear
                psd_linear = 10**(psd_db/10)
                noise_estimate = scipy_signal.convolve(psd_linear, kernel, mode='same')
                
                # Thresholding
                # adaptive_threshold = noise_estimate * bias (if linear)
                # To be robust, we often use dB logic: Threshold_dB = 10*log10(noise_estimate) + 10*log10(bias)
                adaptive_threshold_linear = noise_estimate * (10**(10/10)) # +10dB offset hardcoded for now, or use 'bias' param
                
                # Find indices where signal > adaptive_threshold
                # We also enforce a global minimum to avoid detecting noise in dead bands
                global_min_db = -80.0
                
                detected_indices = np.where(
                    (psd_linear > adaptive_threshold_linear) & 
                    (psd_db > global_min_db)
                )[0]
                
                # Clean up adjacent detections (cluster/peak identification)
                # If we have [100, 101, 102], taking the max of the cluster is better.
                # Simplified clustering for this high-speed loop:
                
                peaks = []
                if len(detected_indices) > 0:
                    # Group consecutive indices
                    clusters = np.split(detected_indices, np.where(np.diff(detected_indices) > 2)[0] + 1)
                    
                    for cluster in clusters:
                        if len(cluster) == 0: continue
                        
                        # Find max in this cluster
                        peak_idx = cluster[np.argmax(psd_db[cluster])]
                        
                        freq_offset = freqs[peak_idx]
                        abs_freq = center_freq + freq_offset
                        power_db_val = psd_db[peak_idx]
                        
                        peaks.append({
                            'freq': abs_freq,
                            'center_freq': center_freq,
                            'power': 10**(power_db_val/10),
                            'power_db': power_db_val,
                            'cfar_margin_db': power_db_val - 10*np.log10(noise_estimate[peak_idx] + 1e-12)
                        })
                
                if peaks:
                    # 3. Correlate Batch
                    correlated_signals = correlation_engine.correlated_batch_analysis(peaks)
                    
                    for signal in correlated_signals:
                        match = signal.get('match')
                        
                        # Prepare Alert / Tracking Update
                        detection_event = {
                            "timestamp": time.time(),
                            "frequency_hz": signal['freq'],
                            "bandwidth_hz": 0,
                            "power_db": signal.get('power_db', -100),
                            "snr_db": signal.get('power_db', -100) - noise_floor_db,
                            "satellite_match": match['name'] if match else None,
                            "confidence": match['confidence'] if match else 0.0
                        }
                        
                        # --- WebSocket Broadcast: Alerts/Tracking ---
                        # Broadcast ALL detections to 'tracking' topic
                        asyncio.create_task(self.manager.broadcast("tracking", detection_event))
                        
                        if match and match['confidence'] > 0.6:
                             logger.info(f"MATCH: {match['name']} (Conf: {match['confidence']:.2f})")
                             # Only high confidence to alerts
                             asyncio.create_task(self.manager.broadcast("alerts", detection_event))

    def stop(self):
        self.is_running = False

