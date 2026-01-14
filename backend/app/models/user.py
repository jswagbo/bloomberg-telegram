"""User model"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class User(Base, UUIDMixin, TimestampMixin):
    """User account model"""
    
    __tablename__ = "users"
    
    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Profile
    username: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Subscription
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")  # free, pro, enterprise
    subscription_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Settings
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    telegram_accounts = relationship("TelegramAccount", back_populates="user", cascade="all, delete-orphan")
    tracked_tokens = relationship("TrackedToken", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("UserAlert", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class TrackedToken(Base, UUIDMixin, TimestampMixin):
    """Tokens a user is tracking"""
    
    __tablename__ = "tracked_tokens"
    
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    token_address: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Tracking settings
    alert_on_mention: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_price_change: Mapped[float] = mapped_column(default=0.2)  # 20% by default
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="tracked_tokens")


class UserAlert(Base, UUIDMixin, TimestampMixin):
    """User alerts/notifications"""
    
    __tablename__ = "user_alerts"
    
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    
    # Alert details
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # mention, price, whale, cluster
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    
    # Related entities
    token_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Extra data
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="alerts")
