# api/schemas.py
"""
Data Transfer Objects (DTOs) with optimized serialization.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

class SatelliteDTO(BaseModel):
    id: int
    norad_id: int
    name: str
    country: Optional[str]
    type: Optional[str] = Field(alias="satellite_type")

    model_config = ConfigDict(from_attributes=True)

class SignalDetection(BaseModel):
    """Real-time signal detection event"""
    timestamp: float
    frequency_hz: float
    bandwidth_hz: float
    power_db: float
    snr_db: float
    
    # Intelligence correlation
    satellite_match: Optional[str] = None # Name of matched satellite
    confidence: float = 0.0

class SpectrumFrame(BaseModel):
    """A single frame of FFT data for the Waterfall display"""
    timestamp: float
    center_freq: float
    span_hz: float
    bins: int
    data: List[float] # Compressed or raw power values

class VulnerabilityReport(BaseModel):
    """Sensitive report structure"""
    target_satellite: str
    vulnerability_type: str # Jamming, Spoofing, Interception
    risk_score: float
    vector_analysis: str

class ObservationDTO(BaseModel):
    id: int
    satellite_id: Optional[int]
    timestamp: datetime
    frequency: float
    bandwidth: float
    power: float
    snr: float
    confidence: float
    
    model_config = ConfigDict(from_attributes=True)

