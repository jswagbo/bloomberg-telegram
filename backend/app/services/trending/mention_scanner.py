"""
Mention Scanner

Searches Telegram messages for mentions of specific tokens.
Extracts human discussion (not bot/scan messages).
"""

import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class TokenMention:
    """A mention of a token in a Telegram message"""
    text: str
    source_name: str
    source_id: str
    message_id: int
    timestamp: Optional[datetime]
    is_human_discussion: bool  # True if real discussion, False if just a scan
    sentiment: str = "neutral"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source_name": self.source_name,
            "source_id": self.source_id,
            "message_id": self.message_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "is_human_discussion": self.is_human_discussion,
            "sentiment": self.sentiment,
        }


@dataclass  
class TokenMentionSummary:
    """Summary of all mentions for a token"""
    address: str
    symbol: str
    chain: str
    total_mentions: int = 0
    human_discussions: int = 0  # Count of real discussions (not scans)
    sources: List[str] = field(default_factory=list)
    mentions: List[TokenMention] = field(default_factory=list)
    sentiment_bullish: int = 0
    sentiment_bearish: int = 0
    sentiment_neutral: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        # Only return human discussions
        human_mentions = [m.to_dict() for m in self.mentions if m.is_human_discussion]
        
        return {
            "address": self.address,
            "symbol": self.symbol,
            "chain": self.chain,
            "total_mentions": self.total_mentions,
            "human_discussions": self.human_discussions,
            "sources": list(set(self.sources)),
            "mentions": human_mentions[:20],  # Limit to 20 for API
            "sentiment": {
                "bullish": self.sentiment_bullish,
                "bearish": self.sentiment_bearish,
                "neutral": self.sentiment_neutral,
            }
        }


class MentionScanner:
    """Scans messages for token mentions"""
    
    # Patterns that indicate a bot/scan message (not human discussion)
    SCAN_PATTERNS = [
        r'^https?://',  # Starts with URL
        r'pump\.fun/',
        r'dexscreener\.com/',
        r'birdeye\.so/',
        r'raydium\.io/',
        r'jupiter\.ag/',
        r'^CA[:\s]',  # "CA: address"
        r'^Contract[:\s]',
        r'^Mint[:\s]',
        r'^Token[:\s]',
        r'🔥\s*NEW',  # Bot announcement patterns
        r'🚀\s*LAUNCH',
        r'💎\s*GEM\s*ALERT',
    ]
    
    # Patterns that indicate human discussion
    DISCUSSION_PATTERNS = [
        r'\b(think|believe|feel|looks?|seems?|might|could|should)\b',
        r'\b(bullish|bearish|ape|buying|selling|holding|bought|sold)\b',
        r'\b(dev|team|community|project)\b',
        r'\b(entry|exit|target|dip|pump|moon)\b',
        r'\b(why|how|when|what)\b',
        r'\b(good|bad|great|terrible|solid|risky)\b',
        r'\?$',  # Questions
    ]
    
    # Sentiment patterns
    BULLISH_WORDS = [
        'bullish', 'long', 'buy', 'moon', 'pump', 'gem', 'alpha', 'based',
        'lfg', 'wagmi', 'love', 'great', 'solid', 'strong', 'confident',
        'ape', 'aped', 'loading', 'accumulating', 'fire', '🚀', '🔥', '💎',
    ]
    
    BEARISH_WORDS = [
        'bearish', 'short', 'sell', 'dump', 'rug', 'scam', 'dead', 'ngmi',
        'hate', 'bad', 'weak', 'worried', 'careful', 'risky', 'exit',
        'selling', 'sold', 'taking profits', '📉', '💀', '⚠️',
    ]
    
    def __init__(self):
        self._scan_patterns = [re.compile(p, re.IGNORECASE) for p in self.SCAN_PATTERNS]
        self._discussion_patterns = [re.compile(p, re.IGNORECASE) for p in self.DISCUSSION_PATTERNS]
    
    def _is_scan_message(self, text: str) -> bool:
        """Check if message is a bot/scan message"""
        if not text or len(text.strip()) < 15:
            return True
        
        # Check for scan patterns
        for pattern in self._scan_patterns:
            if pattern.search(text):
                return True
        
        # If message is mostly a contract address
        if len(text) < 100:
            # Count alphanumeric characters that look like an address
            addr_chars = sum(1 for c in text if c.isalnum())
            if addr_chars > len(text) * 0.7:
                return True
        
        return False
    
    def _is_human_discussion(self, text: str) -> bool:
        """Check if message is human discussion"""
        if self._is_scan_message(text):
            return False
        
        # Must have some discussion indicators
        has_discussion = any(p.search(text) for p in self._discussion_patterns)
        
        # Or be a reasonably long message
        if len(text) > 50:
            has_discussion = True
        
        return has_discussion
    
    def _get_sentiment(self, text: str) -> str:
        """Determine sentiment of message"""
        text_lower = text.lower()
        
        bullish_count = sum(1 for word in self.BULLISH_WORDS if word in text_lower)
        bearish_count = sum(1 for word in self.BEARISH_WORDS if word in text_lower)
        
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        return "neutral"
    
    def _message_mentions_token(
        self,
        text: str,
        address: str,
        symbol: str,
    ) -> bool:
        """Check if a message mentions a specific token"""
        text_lower = text.lower()
        
        # Check for contract address (case-insensitive for some, exact for others)
        if address.lower() in text_lower:
            return True
        
        # Check for first/last 6 chars of address (common truncation)
        if len(address) > 12:
            if address[:6].lower() in text_lower or address[-6:].lower() in text_lower:
                return True
        
        # Check for $SYMBOL
        symbol_pattern = rf'\${re.escape(symbol)}\b'
        if re.search(symbol_pattern, text, re.IGNORECASE):
            return True
        
        # Check for just SYMBOL (but be careful with short symbols)
        if len(symbol) >= 3:
            # Word boundary check
            symbol_word_pattern = rf'\b{re.escape(symbol)}\b'
            if re.search(symbol_word_pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def scan_messages_for_token(
        self,
        messages: List[Dict[str, Any]],
        address: str,
        symbol: str,
        chain: str,
    ) -> TokenMentionSummary:
        """
        Scan a list of messages for mentions of a specific token.
        
        Args:
            messages: List of message dicts with 'text', 'source_name', etc.
            address: Token contract address
            symbol: Token symbol
            chain: Blockchain
        
        Returns:
            TokenMentionSummary with all mentions
        """
        summary = TokenMentionSummary(
            address=address,
            symbol=symbol,
            chain=chain,
        )
        
        for msg in messages:
            text = msg.get("text", "")
            if not text:
                continue
            
            # Check if message mentions this token
            if not self._message_mentions_token(text, address, symbol):
                continue
            
            # Found a mention!
            summary.total_mentions += 1
            
            source_name = msg.get("source_name", "Unknown")
            if source_name not in summary.sources:
                summary.sources.append(source_name)
            
            # Determine if it's human discussion
            is_human = self._is_human_discussion(text)
            if is_human:
                summary.human_discussions += 1
            
            # Get sentiment
            sentiment = self._get_sentiment(text)
            if sentiment == "bullish":
                summary.sentiment_bullish += 1
            elif sentiment == "bearish":
                summary.sentiment_bearish += 1
            else:
                summary.sentiment_neutral += 1
            
            # Parse timestamp
            timestamp = None
            if msg.get("timestamp"):
                try:
                    ts_str = msg["timestamp"]
                    if isinstance(ts_str, str):
                        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    elif isinstance(ts_str, datetime):
                        timestamp = ts_str
                except:
                    pass
            
            mention = TokenMention(
                text=text[:500],  # Limit text length
                source_name=source_name,
                source_id=str(msg.get("source_id", "")),
                message_id=msg.get("message_id", 0),
                timestamp=timestamp,
                is_human_discussion=is_human,
                sentiment=sentiment,
            )
            summary.mentions.append(mention)
        
        # Sort mentions by timestamp (newest first)
        summary.mentions.sort(
            key=lambda m: m.timestamp or datetime.min,
            reverse=True,
        )
        
        return summary
    
    def scan_messages_for_tokens(
        self,
        messages: List[Dict[str, Any]],
        tokens: List[Dict[str, Any]],  # List of {address, symbol, chain}
    ) -> Dict[str, TokenMentionSummary]:
        """
        Scan messages for multiple tokens at once.
        
        Returns:
            Dict mapping token address to TokenMentionSummary
        """
        results = {}
        
        for token in tokens:
            address = token.get("address", "")
            symbol = token.get("symbol", "")
            chain = token.get("chain", "solana")
            
            if not address:
                continue
            
            summary = self.scan_messages_for_token(messages, address, symbol, chain)
            results[address] = summary
        
        return results


# Singleton
mention_scanner = MentionScanner()
