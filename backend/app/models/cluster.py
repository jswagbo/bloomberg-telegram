"""Signal cluster models"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class SignalCluster(Base, UUIDMixin, TimestampMixin):
    """Clustered signals for a token/event"""
    
    __tablename__ = "signal_clusters"
    
    # Token info
    token_address: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    chain: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    
    # Timing
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    peak_activity_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Strength metrics
    unique_sources: Mapped[int] = mapped_column(Integer, default=0)
    total_mentions: Mapped[int] = mapped_column(Integer, default=0)
    unique_wallets: Mapped[int] = mapped_column(Integer, default=0)
    
    # Velocity metrics
    mentions_per_minute: Mapped[float] = mapped_column(Float, default=0.0)
    peak_mentions_per_minute: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Derived scores (0-100)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    
    # Sentiment breakdown
    sentiment_bullish: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_bearish: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_neutral: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_overall: Mapped[str] = mapped_column(String(20), default="neutral")
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)  # -1 to 1
    
    # Price data at cluster creation
    price_at_first_mention: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_at_peak: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_current: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Outcome tracking
    price_1h_later: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_24h_later: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_return_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Source list (for quick access)
    source_ids: Mapped[List[str]] = mapped_column(JSONB, default=list)
    source_names: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Wallet list
    wallet_addresses: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Top message IDs
    top_message_ids: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, cooling, closed
    
    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("idx_clusters_token_chain", "token_address", "chain"),
        Index("idx_clusters_priority_status", "priority_score", "status"),
        Index("idx_clusters_first_seen", "first_seen"),
    )


class ClusterMessage(Base, UUIDMixin):
    """Message assignment to cluster"""
    
    __tablename__ = "cluster_messages"
    
    cluster_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    message_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    
    # Denormalized for efficiency
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    
    # Message preview
    text_preview: Mapped[str] = mapped_column(String(500), nullable=False)
    
    __table_args__ = (
        Index("idx_cluster_messages_cluster_timestamp", "cluster_id", "timestamp"),
    )


class ClusterEvent(Base, UUIDMixin):
    """Significant events within a cluster timeline"""
    
    __tablename__ = "cluster_events"
    
    cluster_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Event type
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # first_mention, whale_buy, call_posted, volume_spike, price_move, peak_activity, etc.
    
    # Description
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Related entities
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    wallet_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Numeric value (price change %, volume, etc.)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("idx_cluster_events_cluster_timestamp", "cluster_id", "timestamp"),
    )
