"""Source reputation and tracking models"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class SourceReputation(Base, UUIDMixin, TimestampMixin):
    """Source reputation tracking across all users"""
    
    __tablename__ = "source_reputations"
    
    # Source identification (unique across system)
    telegram_id: Mapped[str] = mapped_column(String(50), index=True, unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Performance metrics
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    successful_calls: Mapped[int] = mapped_column(Integer, default=0)  # +50% within 1h
    failed_calls: Mapped[int] = mapped_column(Integer, default=0)  # -30% within 1h
    
    # Time metrics
    avg_time_to_move_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_time_to_peak_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Return metrics
    avg_return_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_max_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    median_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Derived scores (0-100)
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)  # successful / total
    speed_score: Mapped[float] = mapped_column(Float, default=0.0)  # How early vs market
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)  # Low variance
    trust_score: Mapped[float] = mapped_column(Float, default=50.0, index=True)  # Composite
    
    # Activity metrics
    first_tracked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_call: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    calls_last_7d: Mapped[int] = mapped_column(Integer, default=0)
    calls_last_30d: Mapped[int] = mapped_column(Integer, default=0)
    
    # Best/worst calls
    best_call: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # {"token": "COWSAY", "return": 15.5, "timestamp": "..."}
    worst_call: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Flags
    is_flagged: Mapped[bool] = mapped_column(default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    
    # Chain focus
    primary_chains: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class SourceCall(Base, UUIDMixin):
    """Individual call/alert from a source for performance tracking"""
    
    __tablename__ = "source_calls"
    
    source_reputation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source_telegram_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    
    # Token called
    token_address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Message info
    message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Price at call
    price_at_call: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap_at_call: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Outcome (populated by background job)
    price_1h_later: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_24h_later: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_price_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    return_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    time_to_peak_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Classification
    outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # hit, miss, rug
    is_processed: Mapped[bool] = mapped_column(default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Whether this was the first call for this token
    is_first_call: Mapped[bool] = mapped_column(default=False)
    
    __table_args__ = (
        Index("idx_source_calls_source_timestamp", "source_reputation_id", "timestamp"),
        Index("idx_source_calls_token", "token_address", "chain"),
    )


class SourceDailyStat(Base, UUIDMixin):
    """Daily aggregated stats for a source"""
    
    __tablename__ = "source_daily_stats"
    
    source_reputation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Daily metrics
    calls_count: Mapped[int] = mapped_column(Integer, default=0)
    hits_count: Mapped[int] = mapped_column(Integer, default=0)
    misses_count: Mapped[int] = mapped_column(Integer, default=0)
    rugs_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Returns
    avg_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    worst_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timing
    avg_time_to_peak: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    __table_args__ = (
        Index("idx_source_daily_stats_source_date", "source_reputation_id", "date", unique=True),
    )
