# receivers/ku_band_receiver.py
"""
Starlink Ku-band beacon receiver.
Hardware: Universal LNB + RTL-SDR/Airspy/USRP
"""

import numpy as np
from scipy import signal
from typing import Optional, List, Tuple
import logging
from pathlib import Path
import time

try:
    from SoapySDR import Device, SOAPY_SDR_RX, SOAPY_SDR_CF32
except ImportError:
    Device = None
    # We will log the warning inside the class initialization or usage if needed,
    # but the global import is fine to fail gracefully here as per the provided code.

from .base_receiver import BaseReceiver, ReceiverConfig, ReceiverState

logger = logging.getLogger(__name__)

# Add a warning if SoapySDR is missing
if Device is None:
    logger.warning("SoapySDR not installed, SDR functionality disabled")

class StarlinkBeaconReceiver(BaseReceiver):
    """
    Starlink Ku-band beacon receiver.
    
    Receives 11.325 GHz beacons downconverted to 1575 MHz by LNB.
    Detects beacons, measures Doppler, and extracts satellite information.
    """
    
    # Known Starlink beacon frequencies (Ku-band)
    BEACON_FREQUENCIES = [11.075e9, 11.325e9, 11.575e9]
    
    # LNB local oscillator
    LNB_LO = 9.750e9
    
    def __init__(
        self,
        device: str = "driver=rtlsdr",
        sample_rate: float = 2.4e6,
        channel: int = 2,  # 0=11.075, 1=11.325, 2=11.575 GHz
        gain: float = 40.0,
        bias_tee: bool = True
    ):
        # Calculate IF frequency (after LNB downconversion)
        rf_freq = self.BEACON_FREQUENCIES[channel]
        if_freq = rf_freq - self.LNB_LO
        
        config = ReceiverConfig(
            device=device,
            sample_rate=sample_rate,
            center_frequency=if_freq,
            gain=gain,
            bias_tee=bias_tee
        )
        
        super().__init__(config, name=f"StarlinkBeacon_{channel}")
        
        self.rf_frequency = rf_freq
        self.channel = channel
        
        # Detection parameters
        self.detection_threshold_db = 15.0  # dB above noise floor
        self.min_beacon_duration_sec = 1.0
        
        # Doppler tracking
        self.doppler_history: List[Tuple[float, float]] = []  # (timestamp, freq)
        
    def initialize_sdr(self) -> bool:
        """Initialize SDR hardware"""
        
        if Device is None:
            logger.error("SoapySDR not available")
            return False
        
        try:
            # Create device
            self._sdr = Device(self.config.device)
            
            # Configure
            self._sdr.setSampleRate(SOAPY_SDR_RX, 0, self.config.sample_rate)
            self._sdr.setFrequency(SOAPY_SDR_RX, 0, self.config.center_frequency)
            self._sdr.setGain(SOAPY_SDR_RX, 0, self.config.gain)
            
            # Enable bias-T for LNB power
            if self.config.bias_tee:
                try:
                    self._sdr.writeSetting("biastee", "true")
                    logger.info(f"{self.name}: Enabled bias-T for LNB power")
                except:
                    logger.warning(f"{self.name}: Could not enable bias-T")
            
            # Setup stream
            self._stream = self._sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
            
            logger.info(f"{self.name}: SDR initialized successfully")
            logger.info(f"{self.name}: RF={self.rf_frequency/1e9:.3f} GHz, IF={self.config.center_frequency/1e6:.1f} MHz")
            
            self.state = ReceiverState.IDLE
            return True
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to initialize SDR: {e}")
            self.state = ReceiverState.ERROR
            return False
    
    def start(self):
        """Start receiving"""
        
        if self._sdr is None:
            raise RuntimeError("SDR not initialized")
        
        self._sdr.activateStream(self._stream)
        self.state = ReceiverState.RUNNING
        logger.info(f"{self.name}: Started receiving")
        
        # Start processing loop (in separate thread typically)
        # Note: In a real app this would be a thread, but for the provided class we just have the method.
        # We will assume consumption is done externally or via a threaded wrapper calling _run_loop.
        # But per the provided code, there is no thread spawn here, just the _run_loop method definition.
        
        # self._run_loop() # Blocking call if run here!
    
    def stop(self):
        """Stop receiving"""
        
        if self._sdr and self._stream:
            self._sdr.deactivateStream(self._stream)
            self._sdr.closeStream(self._stream)
            self.state = ReceiverState.STOPPED
            logger.info(f"{self.name}: Stopped receiving")
    
    def _run_loop(self):
        """Main processing loop"""
        
        buffer_size = 16384
        buffer = np.zeros(buffer_size, dtype=np.complex64)
        
        while self.state == ReceiverState.RUNNING:
            try:
                # Read samples
                sr = self._sdr.readStream(self._stream, [buffer], buffer_size)
                
                if sr.ret > 0:
                    samples = buffer[:sr.ret]
                    
                    # Process samples
                    self._process_samples(samples)
                    
                    # Detect beacons
                    beacons = self._detect_beacons(samples)
                    
                    if beacons and self._on_signal_detected_callback:
                        self._on_signal_detected_callback(beacons)
                
            except Exception as e:
                logger.error(f"{self.name}: Error in processing loop: {e}")
                if self._on_error_callback:
                    self._on_error_callback(e)
                self.state = ReceiverState.ERROR
                break
    
    def _detect_beacons(self, samples: np.ndarray) -> List[Dict]:
        """
        Detect Starlink beacons in samples.
        
        Returns:
            List of detected beacons with characteristics
        """
        
        # Compute PSD
        f, psd = signal.periodogram(
            samples,
            fs=self.config.sample_rate,
            window='hann',
            scaling='density'
        )
        
        psd_db = 10 * np.log10(psd + 1e-12)
        
        # Estimate noise floor (median)
        noise_floor_db = np.median(psd_db)
        
        # Find peaks above threshold
        threshold_db = noise_floor_db + self.detection_threshold_db
        peaks, properties = signal.find_peaks(
            psd_db,
            height=threshold_db,
            distance=int(self.config.sample_rate * 0.0001)  # Min 100 Hz spacing
        )
        
        # Extract beacon characteristics
        beacons = []
        
        for peak_idx in peaks:
            freq_offset = f[peak_idx]
            power_db = psd_db[peak_idx]
            snr_db = power_db - noise_floor_db
            
            beacon = {
                'timestamp': datetime.utcnow(),
                'rf_frequency': self.rf_frequency,
                'if_frequency': self.config.center_frequency + freq_offset,
                'doppler_hz': freq_offset,  # Relative to center
                'power_db': power_db,
                'snr_db': snr_db,
                'receiver': self.name
            }
            
            beacons.append(beacon)
            
            # Track Doppler
            self.doppler_history.append((time.time(), freq_offset))
        
        return beacons
    
    def get_doppler_curve(self, duration_sec: float = 600) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get Doppler history curve.
        
        Args:
            duration_sec: Duration to retrieve (seconds)
            
        Returns:
            (time_array, doppler_array)
        """
        
        if not self.doppler_history:
            return np.array([]), np.array([])
        
        # Filter by time
        cutoff_time = time.time() - duration_sec
        recent = [(t, d) for t, d in self.doppler_history if t >= cutoff_time]
        
        if not recent:
            return np.array([]), np.array([])
        
        times = np.array([t for t, d in recent])
        dopplers = np.array([d for t, d in recent])
        
        # Normalize time (relative to first sample)
        times = times - times[0]
        
        return times, dopplers
    
    def fit_satellite_pass(self) -> Optional[Dict]:
        """
        Fit Doppler curve to satellite pass model.
        
        Returns:
            Satellite parameters if fit successful
        """
        
        times, dopplers = self.get_doppler_curve()
        
        if len(times) < 10:  # Need minimum data points
            return None
        
        try:
            from scipy.optimize import curve_fit
            
            # Parabolic Doppler model
            def doppler_model(t, t0, f0, max_doppler, duration):
                t_norm = (t - t0) / duration
                return f0 + max_doppler * (1 - 4 * t_norm**2)
            
            # Initial guess
            t0_guess = times[len(times)//2]
            f0_guess = np.mean(dopplers)
            max_doppler_guess = (np.max(dopplers) - np.min(dopplers)) / 2
            duration_guess = times[-1] - times[0]
            
            # Fit
            params, covariance = curve_fit(
                doppler_model,
                times,
                dopplers,
                p0=[t0_guess, f0_guess, max_doppler_guess, duration_guess]
            )
            
            t0, f0, max_doppler, duration = params
            
            # Calculate satellite parameters
            # Doppler = (v/c) * f
            # Max Doppler occurs at closest approach
            c = 3e8  # Speed of light
            satellite_velocity_ms = (max_doppler / self.rf_frequency) * c
            
            result = {
                'closest_approach_time': t0,
                'center_frequency': f0,
                'max_doppler_hz': max_doppler,
                'pass_duration_sec': duration,
                'satellite_velocity_ms': satellite_velocity_ms,
                'fit_quality': 1.0 / (1.0 + np.sum(covariance.diagonal()))  # Simple metric
            }
            
            logger.info(f"{self.name}: Satellite pass fit: velocity={satellite_velocity_ms:.0f} m/s, duration={duration:.0f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to fit satellite pass: {e}")
            return None
