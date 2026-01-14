"""Token history and tracking service"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

import structlog

logger = structlog.get_logger()


@dataclass
class TokenData:
    """In-memory token data"""
    address: str
    chain: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    
    # Lifecycle
    first_mention: Optional[datetime] = None
    last_mention: Optional[datetime] = None
    peak_mention_time: Optional[datetime] = None
    peak_mentions_count: int = 0
    
    # Mentions
    total_mentions: int = 0
    mentions_by_source: Dict[str, int] = field(default_factory=dict)
    
    # Price history
    price_at_first_mention: Optional[float] = None
    price_at_peak: Optional[float] = None
    current_price: Optional[float] = None
    max_price: Optional[float] = None
    
    # Callers
    callers: List[Dict[str, Any]] = field(default_factory=list)
    
    # Outcome
    max_return: Optional[float] = None
    time_to_max_seconds: Optional[int] = None
    status: str = "active"  # active, dead, rugged


class TokenTracker:
    """Service for tracking token history"""
    
    def __init__(self):
        self._tokens: Dict[str, TokenData] = {}  # key: address:chain
    
    def get_token_key(self, address: str, chain: str) -> str:
        """Generate unique key for token"""
        return f"{address.lower()}:{chain.lower()}"
    
    def get_or_create_token(
        self,
        address: str,
        chain: str,
        symbol: Optional[str] = None,
    ) -> TokenData:
        """Get or create token data"""
        key = self.get_token_key(address, chain)
        
        if key not in self._tokens:
            self._tokens[key] = TokenData(
                address=address,
                chain=chain,
                symbol=symbol,
            )
        elif symbol and not self._tokens[key].symbol:
            self._tokens[key].symbol = symbol
        
        return self._tokens[key]
    
    def record_mention(
        self,
        address: str,
        chain: str,
        source_id: str,
        source_name: str,
        timestamp: datetime,
        price: Optional[float] = None,
        symbol: Optional[str] = None,
        is_call: bool = False,
    ) -> TokenData:
        """Record a token mention"""
        token = self.get_or_create_token(address, chain, symbol)
        
        # Update mention counts
        token.total_mentions += 1
        token.mentions_by_source[source_id] = token.mentions_by_source.get(source_id, 0) + 1
        
        # Update timeline
        if token.first_mention is None:
            token.first_mention = timestamp
            token.price_at_first_mention = price
        
        token.last_mention = timestamp
        
        # Track peak activity
        # (simplified - in production would use time windows)
        if token.total_mentions > token.peak_mentions_count:
            token.peak_mentions_count = token.total_mentions
            token.peak_mention_time = timestamp
            token.price_at_peak = price
        
        # Update price
        if price is not None:
            token.current_price = price
            if token.max_price is None or price > token.max_price:
                token.max_price = price
                
                # Calculate return if we have first mention price
                if token.price_at_first_mention and token.price_at_first_mention > 0:
                    token.max_return = (price - token.price_at_first_mention) / token.price_at_first_mention
                    token.time_to_max_seconds = int((timestamp - token.first_mention).total_seconds())
        
        # Record caller if it's a call
        if is_call:
            token.callers.append({
                "source_id": source_id,
                "source_name": source_name,
                "timestamp": timestamp.isoformat(),
                "price_at_call": price,
            })
        
        logger.debug(
            "token_mention_recorded",
            address=address[:16] + "...",
            chain=chain,
            total_mentions=token.total_mentions,
            sources=len(token.mentions_by_source),
        )
        
        return token
    
    def update_price(
        self,
        address: str,
        chain: str,
        price: float,
        timestamp: Optional[datetime] = None,
    ):
        """Update token price"""
        key = self.get_token_key(address, chain)
        token = self._tokens.get(key)
        
        if not token:
            return
        
        token.current_price = price
        
        if token.max_price is None or price > token.max_price:
            token.max_price = price
            ts = timestamp or datetime.utcnow()
            
            if token.price_at_first_mention and token.price_at_first_mention > 0:
                token.max_return = (price - token.price_at_first_mention) / token.price_at_first_mention
                if token.first_mention:
                    token.time_to_max_seconds = int((ts - token.first_mention).total_seconds())
    
    def set_status(self, address: str, chain: str, status: str):
        """Set token status"""
        key = self.get_token_key(address, chain)
        token = self._tokens.get(key)
        
        if token:
            token.status = status
            logger.info("token_status_changed", address=address[:16], status=status)
    
    def get_token(self, address: str, chain: str) -> Optional[Dict[str, Any]]:
        """Get token data as dictionary"""
        key = self.get_token_key(address, chain)
        token = self._tokens.get(key)
        
        if not token:
            return None
        
        return {
            "address": token.address,
            "chain": token.chain,
            "symbol": token.symbol,
            "name": token.name,
            "lifecycle": {
                "first_mention": token.first_mention.isoformat() if token.first_mention else None,
                "last_mention": token.last_mention.isoformat() if token.last_mention else None,
                "peak_mention_time": token.peak_mention_time.isoformat() if token.peak_mention_time else None,
            },
            "mentions": {
                "total": token.total_mentions,
                "unique_sources": len(token.mentions_by_source),
            },
            "price": {
                "at_first_mention": token.price_at_first_mention,
                "at_peak": token.price_at_peak,
                "current": token.current_price,
                "max": token.max_price,
            },
            "outcome": {
                "max_return": token.max_return,
                "time_to_max_seconds": token.time_to_max_seconds,
                "status": token.status,
            },
            "callers": token.callers[-10:],  # Last 10 callers
        }
    
    def get_tokens_by_source(
        self,
        source_id: str,
        min_return: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get tokens mentioned by a source"""
        results = []
        
        for token in self._tokens.values():
            if source_id in token.mentions_by_source:
                if min_return is not None and (token.max_return is None or token.max_return < min_return):
                    continue
                
                results.append(self.get_token(token.address, token.chain))
        
        # Sort by max return
        results.sort(key=lambda t: t.get("outcome", {}).get("max_return") or 0, reverse=True)
        
        return results
    
    def get_trending_tokens(
        self,
        hours: int = 24,
        min_mentions: int = 3,
        min_sources: int = 2,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get trending tokens"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        trending = []
        
        for token in self._tokens.values():
            if token.first_mention is None or token.first_mention < cutoff:
                continue
            
            if token.total_mentions < min_mentions:
                continue
            
            if len(token.mentions_by_source) < min_sources:
                continue
            
            trending.append(self.get_token(token.address, token.chain))
        
        # Sort by total mentions
        trending.sort(key=lambda t: t.get("mentions", {}).get("total", 0), reverse=True)
        
        return trending[:limit]
    
    def find_similar_history(
        self,
        address: str,
        chain: str,
        min_sources: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find tokens with similar mention patterns"""
        key = self.get_token_key(address, chain)
        target = self._tokens.get(key)
        
        if not target:
            return []
        
        target_source_count = len(target.mentions_by_source)
        
        similar = []
        for token in self._tokens.values():
            if token.address == address:
                continue
            
            source_count = len(token.mentions_by_source)
            if source_count < min_sources:
                continue
            
            # Check for similar source count pattern
            if abs(source_count - target_source_count) <= 2:
                similar.append({
                    "token": self.get_token(token.address, token.chain),
                    "similarity": {
                        "source_count_match": True,
                        "outcome": token.max_return,
                    }
                })
        
        # Sort by outcome
        similar.sort(key=lambda x: x.get("token", {}).get("outcome", {}).get("max_return") or 0, reverse=True)
        
        return similar[:10]


# Singleton instance
token_tracker = TokenTracker()
