"""Wallet models for tracking and profiling"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class Wallet(Base, UUIDMixin, TimestampMixin):
    """Wallet profile and tracking"""
    
    __tablename__ = "wallets"
    
    # Identification
    address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    
    # Labels
    label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # whale, sniper, dev, known_caller
    tags: Mapped[List[str]] = mapped_column(JSONB, default=list)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # If known entity
    
    # Behavior patterns
    tokens_touched: Mapped[int] = mapped_column(Integer, default=0)
    avg_hold_time_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    typical_position_size_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Performance metrics
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Activity tracking
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Notable activity
    notable_wins: Mapped[List[dict]] = mapped_column(JSONB, default=list)
    # [{"token": "COWSAY", "return": 5.5, "timestamp": "..."}]
    
    # Linked wallets
    linked_wallets: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("idx_wallets_address_chain", "address", "chain", unique=True),
        Index("idx_wallets_label", "label"),
    )


class WalletActivity(Base, UUIDMixin):
    """Wallet activity/transaction tracking"""
    
    __tablename__ = "wallet_activities"
    
    wallet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Transaction info
    tx_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Activity type
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # buy, sell, transfer
    
    # Token involved
    token_address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Amount
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    amount_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_per_token: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Source of info
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # telegram, on_chain, api
    source_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("idx_wallet_activity_wallet_timestamp", "wallet_id", "timestamp"),
        Index("idx_wallet_activity_token", "token_address"),
    )


class WalletMention(Base, UUIDMixin):
    """When a wallet is mentioned in Telegram"""
    
    __tablename__ = "wallet_mentions"
    
    wallet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Source
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # Timing
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Context
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Surrounding text
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    
    # Associated token (if mentioned together)
    token_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    __table_args__ = (
        Index("idx_wallet_mentions_wallet_timestamp", "wallet_id", "timestamp"),
    )
