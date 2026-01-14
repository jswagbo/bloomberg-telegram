"""Message models for raw and processed messages"""

from typing import Optional, List
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin


class RawMessage(Base, UUIDMixin):
    """Raw message from Telegram (time-series optimized)"""
    
    __tablename__ = "raw_messages"
    
    # Source info
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Message info
    telegram_message_id: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reply_to: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Media
    media: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Raw payload
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Deduplication
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index("idx_raw_messages_source_timestamp", "source_id", "timestamp"),
        Index("idx_raw_messages_content_hash", "content_hash"),
    )


class ProcessedMessage(Base, UUIDMixin):
    """Processed message with extracted entities"""
    
    __tablename__ = "processed_messages"
    
    # Link to raw message
    raw_message_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    
    # Source info (denormalized for query efficiency)
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    
    # Extracted entities
    tokens: Mapped[List[dict]] = mapped_column(JSONB, default=list)
    # [{"symbol": "COWSAY", "address": "7xKXt...", "chain": "solana", "confidence": 0.95}]
    
    wallets: Mapped[List[dict]] = mapped_column(JSONB, default=list)
    # [{"address": "7xKXt...", "chain": "solana", "label": "whale"}]
    
    prices: Mapped[List[dict]] = mapped_column(JSONB, default=list)
    # [{"value": 0.00012, "unit": "USD"}]
    
    # Sentiment
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")  # bullish, bearish, neutral
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)  # -1 to 1
    
    # Classification
    classification: Mapped[str] = mapped_column(String(20), default="discussion")  # call, alert, discussion, spam
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Original text (truncated)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Embedding status
    has_embedding: Mapped[bool] = mapped_column(default=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Cluster assignment
    cluster_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_processed_messages_source_timestamp", "source_id", "timestamp"),
        Index("idx_processed_messages_sentiment", "sentiment"),
        Index("idx_processed_messages_classification", "classification"),
        Index("idx_processed_messages_cluster", "cluster_id"),
    )
    
    def get_token_addresses(self) -> List[str]:
        """Get list of token addresses from this message"""
        return [t.get("address") for t in self.tokens if t.get("address")]
    
    def get_wallet_addresses(self) -> List[str]:
        """Get list of wallet addresses from this message"""
        return [w.get("address") for w in self.wallets if w.get("address")]
