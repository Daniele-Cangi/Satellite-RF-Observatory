# receivers/sdr_manager.py
"""
SDR Device Manager.
Handles device detection, initialization, and factory creation.
"""

from typing import Optional, Dict
from dataclasses import dataclass
from .base_receiver import BaseReceiver, ReceiverConfig

# Registry of available receiver implementations
# receiver_type -> class
_RECEIVER_REGISTRY = {}

def register_receiver(name: str, cls):
    """Register a new receiver class"""
    _RECEIVER_REGISTRY[name] = cls

def create_receiver(config: ReceiverConfig) -> BaseReceiver:
    """
    Factory function to create a receiver instance based on configuration.
    
    Args:
        config: Receiver configuration object
        
    Returns:
        Instance of BaseReceiver subclass
    """
    # Simple logic for now: if freq > 10GHz, use Ku-band, else generic or future implementations
    # In a real system, we might have a 'type' field in config or infer from device string
    
    if config.center_frequency > 10e9 or "Starlink" in str(config):
        from .ku_band_receiver import StarlinkBeaconReceiver
        return StarlinkBeaconReceiver(
            device=config.device,
            sample_rate=config.sample_rate,
            center_frequency=config.center_frequency, # Note: StarlinkReceiver calculates IF internally, might need adjustment
            gain=config.gain,
            bias_tee=config.bias_tee
        )
    else:
        # Default or fallback
        # Ideally we'd have a GenericReceiver
        from .ku_band_receiver import StarlinkBeaconReceiver
        return StarlinkBeaconReceiver(
            device=config.device,
            sample_rate=config.sample_rate,
            gain=config.gain,
            bias_tee=config.bias_tee
        )
    
    raise ValueError(f"No suitable receiver found for config: {config}")

# Register known receivers (could be done via decoration or explicit calls)
# register_receiver("starlink", StarlinkBeaconReceiver)
