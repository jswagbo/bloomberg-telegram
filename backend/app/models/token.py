"""Token models for tracking and history"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Token(Base, UUIDMixin, TimestampMixin):
    """Token entity"""
    
    __tablename__ = "tokens"
    
    # Identification
    address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Metadata
    decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Market data (cached)
    price_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # On-chain data
    holder_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_supply: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Platform info
    dex_screener_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Signal stats
    first_mention: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_mention: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_mentions: Mapped[int] = mapped_column(Integer, default=0)
    unique_sources: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, dead, rugged
    is_honeypot: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Extra data
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Unique constraint
    __table_args__ = (
        Index("idx_tokens_address_chain", "address", "chain", unique=True),
    )


class TokenHistory(Base, UUIDMixin):
    """Token price and signal history (time-series)"""
    
    __tablename__ = "token_history"
    
    token_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Price data
    price_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Signal data
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_avg: Mapped[float] = mapped_column(Float, default=0.0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Time-series index
    __table_args__ = (
        Index("idx_token_history_token_timestamp", "token_id", "timestamp"),
    )


class TokenMention(Base, UUIDMixin):
    """Individual token mention for caller tracking"""
    
    __tablename__ = "token_mentions"
    
    token_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Source info
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # Timing
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Price at mention (for performance tracking)
    price_at_mention: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap_at_mention: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Outcome tracking (updated later)
    price_1h_later: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_24h_later: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Classification
    mention_type: Mapped[str] = mapped_column(String(20), default="mention")  # call, alert, discussion
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    
    __table_args__ = (
        Index("idx_token_mentions_token_timestamp", "token_id", "timestamp"),
        Index("idx_token_mentions_source_timestamp", "source_id", "timestamp"),
    )
