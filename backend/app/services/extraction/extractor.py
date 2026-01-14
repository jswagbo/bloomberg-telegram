"""Main extraction service that coordinates entity extraction"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib

from app.services.extraction.patterns import (
    extract_tokens,
    extract_wallets,
    extract_prices,
    TokenMatch,
    WalletMatch,
    PriceMatch,
)
from app.services.extraction.sentiment import (
    sentiment_analyzer,
    SentimentResult,
)
from app.core.security import hash_message
import structlog

logger = structlog.get_logger()


@dataclass
class ProcessedMessageData:
    """Processed message with all extracted entities"""
    id: str
    raw_message_id: str
    source_id: str
    source_name: str
    timestamp: datetime
    
    # Entities
    tokens: List[Dict[str, Any]]
    wallets: List[Dict[str, Any]]
    prices: List[Dict[str, Any]]
    
    # Sentiment
    sentiment: str
    sentiment_score: float
    
    # Classification
    classification: str
    classification_confidence: float
    
    # Content
    original_text: str
    content_hash: str


class ExtractionService:
    """Service for extracting entities from messages"""
    
    def __init__(self):
        self.sentiment_analyzer = sentiment_analyzer
    
    def process_message(
        self,
        message_id: str,
        source_id: str,
        source_name: str,
        text: str,
        timestamp: datetime,
        default_chain: str = "solana",
    ) -> ProcessedMessageData:
        """
        Process a raw message and extract all entities.
        
        Args:
            message_id: Unique message ID
            source_id: Telegram source ID
            source_name: Source name/title
            text: Message text
            timestamp: Message timestamp
            default_chain: Default blockchain to assume
        
        Returns:
            ProcessedMessageData with all extracted entities
        """
        # Extract tokens
        token_matches = extract_tokens(text, default_chain)
        tokens = [
            {
                "symbol": t.symbol,
                "address": t.address,
                "chain": t.chain,
                "confidence": t.confidence,
                "match_type": t.match_type,
            }
            for t in token_matches
        ]
        
        # Extract wallets
        wallet_matches = extract_wallets(text, default_chain)
        wallets = [
            {
                "address": w.address,
                "chain": w.chain,
                "label": w.label,
            }
            for w in wallet_matches
        ]
        
        # Filter out wallet addresses that are likely token addresses
        token_addresses = {t["address"] for t in tokens if t["address"]}
        wallets = [w for w in wallets if w["address"] not in token_addresses]
        
        # Extract prices
        price_matches = extract_prices(text)
        prices = [
            {
                "value": p.value,
                "unit": p.unit,
            }
            for p in price_matches
        ]
        
        # Analyze sentiment
        sentiment_result = self.sentiment_analyzer.analyze(text)
        
        # Classify message
        classification, classification_confidence = self.sentiment_analyzer.classify_message(text)
        
        # Generate content hash for deduplication
        content_hash = hash_message(text)
        
        # Create processed message
        processed = ProcessedMessageData(
            id=message_id,
            raw_message_id=message_id,
            source_id=source_id,
            source_name=source_name,
            timestamp=timestamp,
            tokens=tokens,
            wallets=wallets,
            prices=prices,
            sentiment=sentiment_result.sentiment.value,
            sentiment_score=sentiment_result.score,
            classification=classification,
            classification_confidence=classification_confidence,
            original_text=text[:2000],  # Truncate very long messages
            content_hash=content_hash,
        )
        
        logger.debug(
            "message_processed",
            message_id=message_id,
            tokens_found=len(tokens),
            wallets_found=len(wallets),
            sentiment=sentiment_result.sentiment.value,
            classification=classification,
        )
        
        return processed
    
    def process_batch(
        self,
        messages: List[Dict[str, Any]],
        default_chain: str = "solana",
    ) -> List[ProcessedMessageData]:
        """
        Process a batch of messages.
        
        Args:
            messages: List of message dicts with id, source_id, source_name, text, timestamp
            default_chain: Default blockchain to assume
        
        Returns:
            List of ProcessedMessageData
        """
        processed = []
        
        for msg in messages:
            try:
                result = self.process_message(
                    message_id=msg["id"],
                    source_id=msg["source_id"],
                    source_name=msg["source_name"],
                    text=msg["text"],
                    timestamp=msg["timestamp"],
                    default_chain=default_chain,
                )
                processed.append(result)
            except Exception as e:
                logger.error("batch_process_error", message_id=msg.get("id"), error=str(e))
        
        return processed
    
    def extract_token_info(self, text: str, chain: str = "solana") -> List[Dict[str, Any]]:
        """Extract just token information from text"""
        matches = extract_tokens(text, chain)
        return [
            {
                "symbol": t.symbol,
                "address": t.address,
                "chain": t.chain,
                "confidence": t.confidence,
            }
            for t in matches
        ]
    
    def extract_wallet_info(self, text: str, chain: str = "solana") -> List[Dict[str, Any]]:
        """Extract just wallet information from text"""
        matches = extract_wallets(text, chain)
        return [
            {
                "address": w.address,
                "chain": w.chain,
                "label": w.label,
            }
            for w in matches
        ]
    
    def get_sentiment(self, text: str) -> Dict[str, Any]:
        """Get sentiment analysis for text"""
        result = self.sentiment_analyzer.analyze(text)
        return {
            "sentiment": result.sentiment.value,
            "score": result.score,
            "confidence": result.confidence,
            "signals": result.signals,
        }
    
    def get_classification(self, text: str) -> Dict[str, Any]:
        """Get message classification"""
        classification, confidence = self.sentiment_analyzer.classify_message(text)
        return {
            "classification": classification,
            "confidence": confidence,
        }


# Singleton instance
extraction_service = ExtractionService()
