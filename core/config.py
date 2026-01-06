# core/config.py
"""
Centralized configuration management.
Supports environment variables, YAML files, and runtime overrides.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from functools import lru_cache

class DatabaseConfig(BaseSettings):
    """Database configuration"""
    
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT")
    database: str = Field(default="satint", env="DB_NAME")
    user: str = Field(default="satint", env="DB_USER")
    password: str = Field(default="", env="DB_PASSWORD")
    pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, env="DB_MAX_OVERFLOW")
    
    @property
    def url(self) -> str:
        """PostgreSQL connection URL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    class Config:
        env_prefix = "DB_"

class RedisConfig(BaseSettings):
    """Redis configuration"""
    
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    class Config:
        env_prefix = "REDIS_"

class RabbitMQConfig(BaseSettings):
    """RabbitMQ configuration"""
    
    host: str = Field(default="localhost", env="RABBITMQ_HOST")
    port: int = Field(default=5672, env="RABBITMQ_PORT")
    user: str = Field(default="guest", env="RABBITMQ_USER")
    password: str = Field(default="guest", env="RABBITMQ_PASSWORD")
    vhost: str = Field(default="/", env="RABBITMQ_VHOST")
    
    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/{self.vhost}"
    
    class Config:
        env_prefix = "RABBITMQ_"

class ReceiverConfig(BaseSettings):
    """SDR Receiver configuration"""
    
    enabled: bool = Field(default=True, env="RECEIVER_ENABLED")
    devices: Dict[str, Any] = Field(default_factory=dict)
    recording_path: Path = Field(default=Path("/data/recordings"), env="RECORDING_PATH")
    max_recording_size_gb: int = Field(default=100, env="MAX_RECORDING_SIZE_GB")
    
    @validator("recording_path")
    def create_recording_path(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    class Config:
        env_prefix = "RECEIVER_"

class SpaceTrackConfig(BaseSettings):
    """Space-Track.org API configuration"""
    
    username: str = Field(default="", env="SPACETRACK_USERNAME")
    password: str = Field(default="", env="SPACETRACK_PASSWORD")
    update_interval_hours: int = Field(default=6, env="TLE_UPDATE_INTERVAL")
    
    class Config:
        env_prefix = "SPACETRACK_"

class AlertConfig(BaseSettings):
    """Alert system configuration"""
    
    email_enabled: bool = Field(default=False, env="ALERT_EMAIL_ENABLED")
    email_smtp_host: str = Field(default="", env="ALERT_SMTP_HOST")
    email_smtp_port: int = Field(default=587, env="ALERT_SMTP_PORT")
    email_from: str = Field(default="", env="ALERT_EMAIL_FROM")
    email_to: list = Field(default_factory=list, env="ALERT_EMAIL_TO")
    
    webhook_enabled: bool = Field(default=False, env="ALERT_WEBHOOK_ENABLED")
    webhook_url: str = Field(default="", env="ALERT_WEBHOOK_URL")
    
    class Config:
        env_prefix = "ALERT_"

class LocationConfig(BaseSettings):
    """Observer location configuration"""
    
    latitude: float = Field(default=55.6761, env="LOCATION_LAT")  # Copenhagen
    longitude: float = Field(default=12.5683, env="LOCATION_LON")
    altitude_m: float = Field(default=10.0, env="LOCATION_ALT")
    timezone: str = Field(default="Europe/Copenhagen", env="LOCATION_TZ")
    
    class Config:
        env_prefix = "LOCATION_"

class MLConfig(BaseSettings):
    """Machine Learning configuration"""
    
    models_path: Path = Field(default=Path("ml_models"), env="ML_MODELS_PATH")
    device: str = Field(default="cpu", env="ML_DEVICE")  # cpu, cuda, mps
    batch_size: int = Field(default=32, env="ML_BATCH_SIZE")
    
    class Config:
        env_prefix = "ML_"

class Config(BaseSettings):
    """Main configuration class"""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    receiver: ReceiverConfig = Field(default_factory=ReceiverConfig)
    spacetrack: SpaceTrackConfig = Field(default_factory=SpaceTrackConfig)
    alert: AlertConfig = Field(default_factory=AlertConfig)
    location: LocationConfig = Field(default_factory=LocationConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    
    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=4, env="API_WORKERS")
    
    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    data_path: Path = Field(default=Path("/data"), env="DATA_PATH")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def load_yaml(cls, config_file: Path) -> "Config":
        """Load configuration from YAML file"""
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def save_yaml(self, config_file: Path):
        """Save configuration to YAML file"""
        with open(config_file, 'w') as f:
            yaml.dump(self.dict(), f, default_flow_style=False)

@lru_cache()
def get_config() -> Config:
    """
    Get configuration singleton.
    Checks for config.yaml, then environment variables, then defaults.
    """
    config_file = Path("config/config.yaml")
    
    if config_file.exists():
        return Config.load_yaml(config_file)
    else:
        return Config()

# Global config instance
config = get_config()
