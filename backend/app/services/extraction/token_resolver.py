"""
Token Resolver - Figures out which token an opinion applies to.

When someone says "this looks bullish" or "dev is based", we need to figure out
WHICH token they're talking about. This module resolves token references by:

1. Direct mention - $SYMBOL or contract address in the message
2. Conversation context - What token was mentioned nearby (before/after)
3. Reply context - What message they're replying to
4. Channel context - What token the channel is about (if token-specific)
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.extraction.opinion_extractor import ExtractedOpinion


def utcnow() -> datetime:
    """Get current UTC time as timezone-aware datetime"""
    return datetime.now(timezone.utc)


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp string to timezone-aware datetime"""
    if not ts_str:
        return utcnow()
    try:
        # Handle ISO format with Z
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        # If naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except:
        return utcnow()


@dataclass
class TokenReference:
    """A reference to a token found in conversation"""
    symbol: Optional[str]
    address: Optional[str]
    chain: str
    confidence: float  # 0-1 how confident we are this is the right token
    source: str  # Where we found this reference: "direct", "nearby", "reply", "channel"
    
    def __hash__(self):
        return hash((self.address or self.symbol, self.chain))
    
    def __eq__(self, other):
        if not isinstance(other, TokenReference):
            return False
        return (self.address or self.symbol) == (other.address or other.symbol) and self.chain == other.chain


class TokenResolver:
    """Resolves which token an opinion is referring to"""
    
    def __init__(self):
        # Cache of recent token mentions by source
        # {source_id: [(timestamp, TokenReference), ...]}
        self._recent_tokens: Dict[str, List[Tuple[datetime, TokenReference]]] = {}
        self._cache_window = timedelta(minutes=30)  # How far back to look
    
    def _extract_tokens_from_text(self, text: str) -> List[TokenReference]:
        """Extract all token references from a piece of text"""
        tokens = []
        
        # Look for $SYMBOL
        symbol_matches = re.findall(r'\$([A-Za-z][A-Za-z0-9]{1,10})\b', text)
        for symbol in symbol_matches:
            tokens.append(TokenReference(
                symbol=symbol.upper(),
                address=None,
                chain="solana",  # Default, will be refined
                confidence=0.7,
                source="direct",
            ))
        
        # Look for Solana addresses (base58)
        sol_matches = re.findall(r'\b([1-9A-HJ-NP-Za-km-z]{32,44})\b', text)
        for addr in sol_matches:
            # Verify it looks like an address
            if re.search(r'[a-z]', addr) and re.search(r'[A-Z]', addr) and re.search(r'\d', addr):
                tokens.append(TokenReference(
                    symbol=None,
                    address=addr,
                    chain="solana",
                    confidence=0.95,
                    source="direct",
                ))
        
        # Look for ETH/Base addresses
        eth_matches = re.findall(r'\b(0x[a-fA-F0-9]{40})\b', text)
        for addr in eth_matches:
            # Determine chain based on context
            chain = "base"  # Default to base for 0x addresses
            if "eth" in text.lower() or "ethereum" in text.lower():
                chain = "ethereum"
            elif "bsc" in text.lower() or "bnb" in text.lower():
                chain = "bsc"
            
            tokens.append(TokenReference(
                symbol=None,
                address=addr.lower(),
                chain=chain,
                confidence=0.95,
                source="direct",
            ))
        
        # Look for pump.fun links
        pump_matches = re.findall(r'pump\.fun/([1-9A-HJ-NP-Za-km-z]{32,44})', text)
        for addr in pump_matches:
            tokens.append(TokenReference(
                symbol=None,
                address=addr,
                chain="solana",
                confidence=0.99,
                source="direct",
            ))
        
        return tokens
    
    def record_token_mention(
        self,
        source_id: str,
        timestamp: datetime,
        tokens: List[TokenReference],
    ):
        """Record token mentions for future context lookups"""
        if source_id not in self._recent_tokens:
            self._recent_tokens[source_id] = []
        
        # Add new mentions
        for token in tokens:
            self._recent_tokens[source_id].append((timestamp, token))
        
        # Clean up old entries
        cutoff = utcnow() - self._cache_window
        self._recent_tokens[source_id] = [
            (ts, tok) for ts, tok in self._recent_tokens[source_id]
            if ts > cutoff
        ]
    
    def get_recent_tokens(
        self,
        source_id: str,
        around_time: datetime,
        window_minutes: int = 10,
    ) -> List[TokenReference]:
        """Get tokens mentioned recently in a source"""
        if source_id not in self._recent_tokens:
            return []
        
        window = timedelta(minutes=window_minutes)
        start = around_time - window
        end = around_time + window
        
        recent = []
        for ts, token in self._recent_tokens[source_id]:
            if start <= ts <= end:
                # Adjust confidence based on time distance
                time_dist = abs((ts - around_time).total_seconds()) / 60
                conf_decay = max(0.3, 1.0 - (time_dist / window_minutes) * 0.5)
                
                recent.append(TokenReference(
                    symbol=token.symbol,
                    address=token.address,
                    chain=token.chain,
                    confidence=token.confidence * conf_decay,
                    source="nearby",
                ))
        
        return recent
    
    def resolve_token_for_opinion(
        self,
        opinion: ExtractedOpinion,
        nearby_messages: List[Dict[str, Any]] = None,
        reply_to_message: Dict[str, Any] = None,
    ) -> Optional[TokenReference]:
        """
        Resolve which token an opinion is about.
        
        Priority:
        1. Direct mention in the opinion itself
        2. Reply context (if replying to a message with a token)
        3. Nearby messages in the same chat
        4. Recent activity in the same channel
        
        Returns:
            TokenReference if resolved, None if unable to determine
        """
        candidates = []
        
        # 1. Direct mention in opinion
        if opinion.token_address:
            candidates.append(TokenReference(
                symbol=opinion.token_symbol,
                address=opinion.token_address,
                chain="solana",  # Will refine based on address format
                confidence=0.95,
                source="direct",
            ))
        elif opinion.token_symbol:
            candidates.append(TokenReference(
                symbol=opinion.token_symbol,
                address=None,
                chain="solana",
                confidence=0.75,
                source="direct",
            ))
        
        # 2. Check reply context
        if reply_to_message:
            reply_text = reply_to_message.get("text", "")
            reply_tokens = self._extract_tokens_from_text(reply_text)
            for token in reply_tokens:
                token.confidence *= 0.9  # Slightly lower than direct
                token.source = "reply"
                candidates.append(token)
        
        # 3. Check nearby messages
        if nearby_messages:
            for msg in nearby_messages:
                msg_text = msg.get("text", "")
                msg_tokens = self._extract_tokens_from_text(msg_text)
                for token in msg_tokens:
                    # Confidence based on proximity (assume messages are ordered by time)
                    token.confidence *= 0.7
                    token.source = "nearby"
                    candidates.append(token)
        
        # 4. Check recent channel activity
        if opinion.source_id:
            ts = parse_timestamp(opinion.timestamp)
            recent = self.get_recent_tokens(opinion.source_id, ts)
            candidates.extend(recent)
        
        # Select best candidate
        if not candidates:
            return None
        
        # Sort by confidence and return best
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        best = candidates[0]
        
        # Only return if reasonably confident
        if best.confidence >= 0.5:
            return best
        
        return None
    
    def resolve_tokens_batch(
        self,
        opinions: List[ExtractedOpinion],
        all_messages: List[Dict[str, Any]],
    ) -> List[Tuple[ExtractedOpinion, Optional[TokenReference]]]:
        """
        Resolve tokens for a batch of opinions.
        
        This is more efficient than resolving one by one because we can
        build context from all messages first.
        
        Args:
            opinions: List of extracted opinions
            all_messages: All messages from the source (for context)
        
        Returns:
            List of (opinion, resolved_token) tuples
        """
        # First pass: Extract and record all token mentions from messages
        msg_by_id = {msg.get("message_id"): msg for msg in all_messages if msg.get("message_id")}
        
        for msg in all_messages:
            text = msg.get("text") or msg.get("original_text", "")
            source_id = str(msg.get("source_id", ""))
            ts = parse_timestamp(msg.get("timestamp", ""))
            
            tokens = self._extract_tokens_from_text(text)
            if tokens:
                self.record_token_mention(source_id, ts, tokens)
        
        # Second pass: Resolve each opinion
        results = []
        
        for opinion in opinions:
            # Find nearby messages (within 5 messages)
            nearby = []
            for msg in all_messages:
                if msg.get("source_id") == opinion.source_id:
                    msg_id = msg.get("message_id", 0)
                    if abs(msg_id - opinion.message_id) <= 5 and msg_id != opinion.message_id:
                        nearby.append(msg)
            
            # Find reply target if it's a reply
            reply_to = None
            # (Would need reply_to_message_id in the message data)
            
            token = self.resolve_token_for_opinion(opinion, nearby, reply_to)
            results.append((opinion, token))
        
        return results


# Singleton instance
token_resolver = TokenResolver()
