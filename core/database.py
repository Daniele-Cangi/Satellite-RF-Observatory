# core/database.py
"""
Database models using SQLAlchemy + TimescaleDB for time-series data.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, 
    Boolean, JSON, Text, ForeignKey, Index, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from geoalchemy2 import Geography

from .config import get_config

config = get_config()

# Database engine
engine = create_engine(
    config.database.url,
    poolclass=QueuePool,
    pool_size=config.database.pool_size,
    max_overflow=config.database.max_overflow,
    echo=config.debug
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============================================================================
# Models
# ============================================================================

class Satellite(Base):
    """Satellite catalog"""
    
    __tablename__ = "satellites"
    
    id = Column(Integer, primary_key=True, index=True)
    norad_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    international_designator = Column(String(20))
    country = Column(String(10), index=True)
    launch_date = Column(DateTime)
    
    # Current orbital elements (latest TLE)
    tle_line1 = Column(String(69))
    tle_line2 = Column(String(69))
    tle_epoch = Column(DateTime, index=True)
    
    # Classification
    satellite_type = Column(String(50), index=True)  # reconnaissance, navigation, communication, weather, etc
    purpose = Column(String(20), index=True)  # civilian, military, dual-use
    
    # Status
    active = Column(Boolean, default=True)
    last_observed = Column(DateTime)
    
    # Metadata
    meta_info = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    observations = relationship("Observation", back_populates="satellite")
    maneuvers = relationship("Maneuver", back_populates="satellite")
    downlinks = relationship("Downlink", back_populates="satellite")
    
    def __repr__(self):
        return f"<Satellite(norad_id={self.norad_id}, name={self.name})>"

class Observation(Base):
    """Satellite observation records (time-series)"""
    
    __tablename__ = "observations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Satellite
    satellite_id = Column(Integer, ForeignKey("satellites.id"), nullable=False, index=True)
    satellite = relationship("Satellite", back_populates="observations")
    
    # Observer location
    observer_lat = Column(Float)
    observer_lon = Column(Float)
    observer_alt = Column(Float)
    
    # Signal characteristics
    frequency_hz = Column(BigInteger, index=True)
    bandwidth_hz = Column(Integer)
    signal_type = Column(String(50), index=True)  # beacon, telemetry, downlink, etc
    modulation = Column(String(50))
    
    # Reception quality
    power_dbm = Column(Float)
    snr_db = Column(Float)
    doppler_hz = Column(Float)
    
    # Data
    recording_path = Column(String(500))
    recording_size_bytes = Column(BigInteger)
    decoded_data = Column(JSON)
    
    # Metadata
    meta_info = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    telemetry = relationship("Telemetry", back_populates="observation", uselist=False)
    
    def __repr__(self):
        return f"<Observation(satellite_id={self.satellite_id}, timestamp={self.timestamp})>"

# TimescaleDB hypertable (convert to time-series)
# Execute after table creation:
# SELECT create_hypertable('observations', 'timestamp', if_not_exists => TRUE);

class Telemetry(Base):
    """Decoded satellite telemetry"""
    
    __tablename__ = "telemetry"
    
    id = Column(BigInteger, primary_key=True, index=True)
    observation_id = Column(BigInteger, ForeignKey("observations.id"), unique=True)
    observation = relationship("Observation", back_populates="telemetry")
    
    timestamp = Column(DateTime, nullable=False, index=True)
    satellite_id = Column(Integer, ForeignKey("satellites.id"), index=True)
    
    # Telemetry data (structure depends on satellite)
    format = Column(String(50))  # CCSDS, AX.25, custom, etc
    data = Column(JSON)
    
    # Parsed fields (common across satellites)
    battery_voltage = Column(Float)
    battery_current = Column(Float)
    solar_voltage = Column(Float)
    temperature_c = Column(Float)
    
    # Position (if GPS included in telemetry)
    position = Column(Geography(geometry_type='POINT', srid=4326))
    
    # Metadata
    confidence = Column(Float)  # 0.0-1.0 confidence in decoding
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Telemetry(satellite_id={self.satellite_id}, timestamp={self.timestamp})>"

class Maneuver(Base):
    """Detected orbital maneuvers"""
    
    __tablename__ = "maneuvers"
    
    id = Column(Integer, primary_key=True, index=True)
    satellite_id = Column(Integer, ForeignKey("satellites.id"), nullable=False, index=True)
    satellite = relationship("Satellite", back_populates="maneuvers")
    
    detected_at = Column(DateTime, nullable=False, index=True)
    
    # Orbital elements before/after
    tle_before_line1 = Column(String(69))
    tle_before_line2 = Column(String(69))
    tle_before_epoch = Column(DateTime)
    
    tle_after_line1 = Column(String(69))
    tle_after_line2 = Column(String(69))
    tle_after_epoch = Column(DateTime)
    
    # Delta-v estimation
    delta_v_estimate_ms = Column(Float)
    semi_major_axis_change_km = Column(Float)
    inclination_change_deg = Column(Float)
    
    # Classification
    maneuver_type = Column(String(50))  # station-keeping, repositioning, deorbit
    purpose_inference = Column(Text)
    confidence = Column(Float)
    
    # Metadata
    meta_info = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Maneuver(satellite_id={self.satellite_id}, detected_at={self.detected_at})>"

class Downlink(Base):
    """Satellite downlink activity"""
    
    __tablename__ = "downlinks"
    
    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    satellite_id = Column(Integer, ForeignKey("satellites.id"), nullable=False, index=True)
    satellite = relationship("Satellite", back_populates="downlinks")
    
    # Downlink characteristics
    frequency_hz = Column(BigInteger)
    duration_sec = Column(Float)
    bandwidth_hz = Column(Integer)
    power_dbm = Column(Float)
    
    # Ground station (if known)
    ground_station = Column(String(100), index=True)
    ground_station_location = Column(Geography(geometry_type='POINT', srid=4326))
    
    # Data volume estimate
    data_volume_estimate_mb = Column(Float)
    
    # Intelligence inference
    purpose_inference = Column(Text)  # tasking, health check, emergency, etc
    
    # Metadata
    meta_info = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Downlink(satellite_id={self.satellite_id}, timestamp={self.timestamp})>"

class Alert(Base):
    """System alerts"""
    
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Alert classification
    alert_type = Column(String(50), nullable=False, index=True)  # gps_jamming, maneuver, anomaly, etc
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical
    
    # Related entities
    satellite_id = Column(Integer, ForeignKey("satellites.id"), index=True)
    observation_id = Column(BigInteger, ForeignKey("observations.id"))
    
    # Alert details
    title = Column(String(200))
    description = Column(Text)
    data = Column(JSON)
    
    # Status
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(100))
    
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    
    # Notifications sent
    notifications_sent = Column(JSON)  # List of notification methods and timestamps
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Alert(type={self.alert_type}, severity={self.severity}, timestamp={self.timestamp})>"

class VulnerabilityAssessment(Base):
    """Vulnerability assessment results"""
    
    __tablename__ = "vulnerability_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Target
    satellite_id = Column(Integer, ForeignKey("satellites.id"), index=True)
    constellation = Column(String(100), index=True)  # GPS, BeiDou, Starlink, etc
    country = Column(String(10), index=True)
    
    # Assessment type
    assessment_type = Column(String(50), index=True)  # jamming, spoofing, cyber, kinetic, etc
    
    # Results
    vulnerability_score = Column(Float)  # 0.0-1.0
    difficulty = Column(String(20))  # trivial, easy, medium, hard, extreme
    cost_estimate_usd = Column(Integer)
    
    # Details
    attack_vectors = Column(JSON)
    mitigation_measures = Column(JSON)
    strategic_implications = Column(Text)
    
    # Metadata
    methodology = Column(Text)
    confidence = Column(Float)
    data = Column(JSON)
    
    def __repr__(self):
        return f"<VulnerabilityAssessment(constellation={self.constellation}, type={self.assessment_type})>"

class IntelligenceReport(Base):
    """Generated intelligence reports"""
    
    __tablename__ = "intelligence_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Report metadata
    report_type = Column(String(50), index=True)  # daily, crisis, vulnerability, strategic
    title = Column(String(200))
    
    # Time period covered
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    
    # Content
    executive_summary = Column(Text)
    content = Column(JSON)  # Structured report content
    
    # Files
    pdf_path = Column(String(500))
    data_files = Column(JSON)
    
    # Distribution
    classification = Column(String(20), default="UNCLASSIFIED")
    distribution_list = Column(JSON)
    
    def __repr__(self):
        return f"<IntelligenceReport(type={self.report_type}, created_at={self.created_at})>"

# ============================================================================
# Indexes
# ============================================================================

# Composite indexes for common queries
Index('idx_observations_satellite_time', Observation.satellite_id, Observation.timestamp)
Index('idx_observations_freq_time', Observation.frequency_hz, Observation.timestamp)
Index('idx_telemetry_satellite_time', Telemetry.satellite_id, Telemetry.timestamp)
Index('idx_downlinks_satellite_time', Downlink.satellite_id, Downlink.timestamp)
Index('idx_alerts_type_severity', Alert.alert_type, Alert.severity)

# ============================================================================
# Database utilities
# ============================================================================

@contextmanager
def get_db() -> Session:
    """
    Context manager for database sessions.
    
    Usage:
        with get_db() as db:
            satellites = db.query(Satellite).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database (create tables)"""
    Base.metadata.create_all(bind=engine)
    
    # Enable TimescaleDB extension and create hypertable
    with get_db() as db:
        try:
            db.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            db.execute("SELECT create_hypertable('observations', 'timestamp', if_not_exists => TRUE)")
            db.execute("SELECT create_hypertable('telemetry', 'timestamp', if_not_exists => TRUE)")
            db.commit()
        except Exception as e:
            print(f"Warning: Could not enable TimescaleDB: {e}")

def drop_all_tables():
    """Drop all tables (use with caution!)"""
    Base.metadata.drop_all(bind=engine)
