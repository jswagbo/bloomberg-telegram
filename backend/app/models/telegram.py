"""Telegram account and source models"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class TelegramAccount(Base, UUIDMixin, TimestampMixin):
    """User's Telegram account for API access"""
    
    __tablename__ = "telegram_accounts"
    
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    
    # Credentials (encrypted)
    api_id_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_hash_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    phone_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Session
    session_string_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="telegram_accounts")
    sources = relationship("TelegramSource", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TelegramAccount {self.session_name}>"


class TelegramSource(Base, UUIDMixin, TimestampMixin):
    """Telegram source (group, channel, bot) to monitor"""
    
    __tablename__ = "telegram_sources"
    
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("telegram_accounts.id"), index=True, nullable=False)
    
    # Source identification
    telegram_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # Telegram's internal ID
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # group, channel, bot
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Configuration
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Filters
    filters: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example: {"chains": ["solana"], "minMentions": 1, "excludeKeywords": ["giveaway"]}
    
    # Statistics
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    processed_messages: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Trust/reputation linkage
    source_reputation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Relationships
    account = relationship("TelegramAccount", back_populates="sources")
    
    def __repr__(self):
        return f"<TelegramSource {self.name} ({self.source_type})>"


class TelegramSourceTemplate(Base, UUIDMixin, TimestampMixin):
    """Pre-configured source templates for common alpha channels"""
    
    __tablename__ = "telegram_source_templates"
    
    # Source info
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telegram_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Categorization
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # whale_alerts, call_channel, dev_updates, etc.
    chains: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Suggested settings
    suggested_priority: Mapped[str] = mapped_column(String(20), default="medium")
    suggested_filters: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Community metrics
    subscriber_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    community_rating: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Status
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
