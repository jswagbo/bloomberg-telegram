"""Application configuration"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    app_name: str = "Bloomberg Telegram"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production")
    encryption_key: str = Field(default="your-encryption-key-32bytes!")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week
    
    # Database
    database_url: str = Field(default="postgresql://bloomberg:telegram_secret@localhost:5432/bloomberg_telegram")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379")
    
    # Qdrant
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_collection: str = "telegram_messages"
    
    # Telegram
    telegram_session_path: str = "/app/sessions"
    
    # ML Models
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Processing
    batch_size: int = 100
    batch_interval_seconds: float = 2.0
    cluster_window_minutes: int = 30
    dedup_window_minutes: int = 5
    similarity_threshold: float = 0.85
    
    # External APIs
    dexscreener_base_url: str = "https://api.dexscreener.com"
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    jupiter_base_url: str = "https://price.jup.ag/v4"
    birdeye_base_url: str = "https://public-api.birdeye.so"
    
    # Chains configuration
    supported_chains: List[str] = ["solana", "base", "bsc"]
    
    # Scoring weights
    source_diversity_weight: float = 25.0
    recency_weight: float = 20.0
    velocity_weight: float = 20.0
    wallet_activity_weight: float = 15.0
    source_quality_weight: float = 20.0
    spam_penalty_weight: float = -30.0
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
