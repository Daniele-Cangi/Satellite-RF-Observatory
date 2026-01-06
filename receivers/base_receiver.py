# receivers/base_receiver.py
"""
Abstract base class for all SDR receivers.
Defines common interface and functionality.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import numpy as np
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ReceiverState(Enum):
    """Receiver operational state"""
    IDLE = "idle"
    RUNNING = "running"
    RECORDING = "recording"
    ERROR = "error"
    STOPPED = "stopped"

@dataclass
class ReceiverConfig:
    """Receiver configuration parameters"""
    device: str
    sample_rate: float
    center_frequency: float
    gain: float
    bandwidth: Optional[float] = None
    antenna: Optional[str] = None
    bias_tee: bool = False

@dataclass
class SignalMetrics:
    """Signal quality metrics"""
    timestamp: datetime
    power_dbm: float
    snr_db: Optional[float]
    frequency_error_hz: Optional[float]
    sample_count: int

class BaseReceiver(ABC):
    """
    Abstract base class for SDR receivers.
    
    All specific receivers (VHF, L-band, Ku-band, etc) inherit from this.
    """
    
    def __init__(self, config: ReceiverConfig, name: str = "BaseReceiver"):
        self.config = config
        self.name = name
        self.state = ReceiverState.IDLE
        
        self._sdr = None
        self._recording = False
        self._recording_file = None
        self._samples_recorded = 0
        
        # Callbacks
        self._on_samples_callback: Optional[Callable] = None
        self._on_signal_detected_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        
        logger.info(f"Initialized {self.name} receiver")
    
    @abstractmethod
    def initialize_sdr(self) -> bool:
        """
        Initialize SDR hardware.
        Must be implemented by subclasses.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def start(self):
        """Start receiving"""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop receiving"""
        pass
    
    def set_frequency(self, frequency_hz: float):
        """Set center frequency"""
        if self._sdr is None:
            raise RuntimeError("SDR not initialized")
        
        self._sdr.set_center_freq(frequency_hz)
        self.config.center_frequency = frequency_hz
        logger.info(f"{self.name}: Set frequency to {frequency_hz/1e6:.3f} MHz")
    
    def set_sample_rate(self, sample_rate: float):
        """Set sample rate"""
        if self._sdr is None:
            raise RuntimeError("SDR not initialized")
        
        self._sdr.set_sample_rate(sample_rate)
        self.config.sample_rate = sample_rate
        logger.info(f"{self.name}: Set sample rate to {sample_rate/1e6:.3f} Msps")
    
    def set_gain(self, gain: float):
        """Set RF gain"""
        if self._sdr is None:
            raise RuntimeError("SDR not initialized")
        
        self._sdr.set_gain(gain)
        self.config.gain = gain
        logger.info(f"{self.name}: Set gain to {gain} dB")
    
    def start_recording(self, output_path: Path, max_samples: Optional[int] = None):
        """
        Start recording IQ samples to file.
        
        Args:
            output_path: Output file path
            max_samples: Maximum samples to record (None = unlimited)
        """
        if self._recording:
            logger.warning(f"{self.name}: Already recording")
            return
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._recording_file = open(output_path, 'wb')
        self._recording = True
        self._samples_recorded = 0
        self._max_samples = max_samples
        
        logger.info(f"{self.name}: Started recording to {output_path}")
    
    def stop_recording(self) -> Dict[str, Any]:
        """
        Stop recording.
        
        Returns:
            dict: Recording statistics
        """
        if not self._recording:
            logger.warning(f"{self.name}: Not recording")
            return {}
        
        self._recording = False
        
        if self._recording_file:
            self._recording_file.close()
            file_size = self._recording_file.tell()
            self._recording_file = None
        else:
            file_size = 0
        
        stats = {
            'samples_recorded': self._samples_recorded,
            'file_size_bytes': file_size,
            'duration_sec': self._samples_recorded / self.config.sample_rate
        }
        
        logger.info(f"{self.name}: Stopped recording. Stats: {stats}")
        return stats
    
    def _process_samples(self, samples: np.ndarray):
        """
        Process received samples (internal).
        
        This is called by subclasses with received IQ data.
        """
        # Update state
        self.state = ReceiverState.RUNNING
        
        # Record if enabled
        if self._recording and self._recording_file:
            samples.tofile(self._recording_file)
            self._samples_recorded += len(samples)
            
            # Check max samples
            if self._max_samples and self._samples_recorded >= self._max_samples:
                self.stop_recording()
        
        # Calculate metrics
        metrics = self._calculate_metrics(samples)
        
        # Call user callback
        if self._on_samples_callback:
            try:
                self._on_samples_callback(samples, metrics)
            except Exception as e:
                logger.error(f"{self.name}: Error in samples callback: {e}")
    
    def _calculate_metrics(self, samples: np.ndarray) -> SignalMetrics:
        """Calculate signal quality metrics"""
        
        # Power (dBFS)
        power_linear = np.mean(np.abs(samples)**2)
        power_dbfs = 10 * np.log10(power_linear + 1e-12)
        
        # Estimate noise floor (simple: lowest 10% of samples)
        sorted_power = np.sort(np.abs(samples)**2)
        noise_floor = np.mean(sorted_power[:len(sorted_power)//10])
        noise_floor_dbfs = 10 * np.log10(noise_floor + 1e-12)
        
        # SNR
        snr_db = power_dbfs - noise_floor_dbfs if power_dbfs > noise_floor_dbfs else None
        
        return SignalMetrics(
            timestamp=datetime.utcnow(),
            power_dbm=power_dbfs,  # Would need calibration for true dBm
            snr_db=snr_db,
            frequency_error_hz=None,  # Subclass can override
            sample_count=len(samples)
        )
    
    def set_on_samples_callback(self, callback: Callable):
        """Set callback for received samples"""
        self._on_samples_callback = callback
    
    def set_on_signal_detected_callback(self, callback: Callable):
        """Set callback for signal detection"""
        self._on_signal_detected_callback = callback
    
    def set_on_error_callback(self, callback: Callable):
        """Set callback for errors"""
        self._on_error_callback = callback
    
    def get_state(self) -> ReceiverState:
        """Get current receiver state"""
        return self.state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get receiver statistics"""
        return {
            'name': self.name,
            'state': self.state.value,
            'config': {
                'device': self.config.device,
                'sample_rate': self.config.sample_rate,
                'center_frequency': self.config.center_frequency,
                'gain': self.config.gain
            },
            'recording': self._recording,
            'samples_recorded': self._samples_recorded
        }
    
    def __enter__(self):
        """Context manager entry"""
        self.initialize_sdr()
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        if self._recording:
            self.stop_recording()
