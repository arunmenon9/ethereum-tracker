from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ethereum_tracker"
    
    # Redis
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    
    # Etherscan API
    ETHERSCAN_API_KEY: str = 'G4X1CG2P7UCT6DQH487W3MZ5US2PWH848Z'
    ETHERSCAN_BASE_URL: str = "https://api.etherscan.io/v2/api"
    ETHERSCAN_RATE_LIMIT: float = 5.0  # requests per second
    
    # Authentication
    API_KEY: str = "your-secret-api-key"
    SECRET_KEY: str = "your-secret-key"
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # CSV Export
    MAX_EXPORT_RECORDS: int = 50000
    EXPORT_BATCH_SIZE: int = 1000
    
    # Cache TTL (seconds)
    CACHE_TTL_TRANSACTIONS: int = 300  # 5 minutes
    CACHE_TTL_BLOCKS: int = 3600       # 1 hour

@lru_cache()
def get_settings():
    return Settings()