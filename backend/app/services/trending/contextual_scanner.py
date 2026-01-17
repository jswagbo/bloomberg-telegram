"""
Contextual Token Scanner

IMPROVED APPROACH:
1. Find token mentions in messages
2. Capture SURROUNDING messages (conversation context)
3. Only show tokens with valid DexScreener data
4. Generate summaries from actual discussions, not just mentions

The key insight: When someone posts a token, the discussion happens
in the messages AROUND that post, not just in the post itself.
"""

import re
import httpx
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import structlog
import os

logger = structlog.get_logger()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"

# Token detection patterns
SOLANA_ADDR = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
EVM_ADDR = r'0x[a-fA-F0-9]{40}'

TOKEN_URL_PATTERNS = [
    (r'pump\.fun/(?:coin/)?([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'dexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'dexscreener\.com/base/(0x[a-fA-F0-9]{40})', 'base'),
    (r'birdeye\.so/token/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'solscan\.io/token/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'photon-sol\.tinyastro\.io/[^/]+/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
]

# Skip these common addresses
SKIP_ADDRESSES = {
    'So11111111111111111111111111111111111111112',  # SOL
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
}


@dataclass
class TokenDiscussion:
    """A token with its surrounding discussion context"""
    address: str
    chain: str
    
    # DexScreener data (required - we skip tokens without this)
    symbol: str = ""
    name: str = ""
    price_usd: float = 0
    market_cap: Optional[float] = None
    liquidity_usd: Optional[float] = None
    price_change_1h: Optional[float] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    dex_url: str = ""
    image_url: Optional[str] = None
    
    # Discussion data
    mention_count: int = 0
    chats: Set[str] = field(default_factory=set)
    discussions: List[Dict] = field(default_factory=list)  # Contextual discussions
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    # AI-generated insights
    summary: str = ""
    sentiment: str = "neutral"
    key_opinions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ContextualScanner:
    """
    Scans chats for tokens and captures surrounding discussion context.
    
    Key improvement: Instead of just finding "message contains address",
    we find the address and then grab messages in a time window around it
    to capture the actual conversation about that token.
    """
    
    CONTEXT_WINDOW_MINUTES = 10  # Capture messages within 10 min of token mention
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._dex_cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, datetime] = {}
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    def _extract_token_from_message(self, text: str) -> Optional[Tuple[str, str]]:
        """Extract token address from a message. Returns (address, chain) or None."""
        # Try URL patterns first (most reliable)
        for pattern, chain in TOKEN_URL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                addr = match.group(1)
                if addr not in SKIP_ADDRESSES:
                    return (addr, chain)
        
        # Try raw Solana address
        match = re.search(SOLANA_ADDR, text)
        if match:
            addr = match.group(0)
            if addr not in SKIP_ADDRESSES and len(addr) >= 32:
                # Skip if looks like transaction
                if not any(x in text.lower() for x in ['tx:', 'transaction:', 'sig:']):
                    return (addr, 'solana')
        
        # Try EVM address
        match = re.search(EVM_ADDR, text)
        if match:
            return (match.group(0), 'ethereum')
        
        return None
    
    async def _get_dexscreener_data(self, address: str) -> Optional[Dict]:
        """Fetch token data from DexScreener. Returns None if not found."""
        cache_key = address.lower()
        
        # Check cache
        if cache_key in self._dex_cache:
            if datetime.utcnow() - self._cache_time.get(cache_key, datetime.min) < timedelta(minutes=5):
                return self._dex_cache[cache_key]
        
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{address}"
            )
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                
                if pairs:
                    # Get highest liquidity pair
                    pairs.sort(key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0, reverse=True)
                    pair = pairs[0]
                    
                    base = pair.get("baseToken", {})
                    if base.get("address", "").lower() != address.lower():
                        base = pair.get("quoteToken", {})
                    
                    result = {
                        "symbol": base.get("symbol", ""),
                        "name": base.get("name", ""),
                        "price_usd": float(pair.get("priceUsd") or 0),
                        "market_cap": pair.get("fdv"),
                        "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                        "price_change_1h": pair.get("priceChange", {}).get("h1"),
                        "price_change_24h": pair.get("priceChange", {}).get("h24"),
                        "volume_24h": pair.get("volume", {}).get("h24"),
                        "dex_url": pair.get("url", ""),
                        "image_url": pair.get("info", {}).get("imageUrl"),
                        "chain": pair.get("chainId", "solana"),
                    }
                    
                    self._dex_cache[cache_key] = result
                    self._cache_time[cache_key] = datetime.utcnow()
                    return result
            
            # Cache negative result
            self._dex_cache[cache_key] = None
            self._cache_time[cache_key] = datetime.utcnow()
            return None
            
        except Exception as e:
            logger.warning("dexscreener_fetch_failed", address=address, error=str(e))
            return None
    
    def _get_context_messages(
        self,
        all_messages: List[Dict],
        target_chat: str,
        target_time: datetime,
        window_minutes: int = 10
    ) -> List[Dict]:
        """
        Get messages from the same chat within a time window of the target message.
        This captures the discussion context around a token mention.
        """
        context = []
        window = timedelta(minutes=window_minutes)
        
        for msg in all_messages:
            if msg.get("source_name") != target_chat:
                continue
            
            msg_time = msg.get("_parsed_time")
            if msg_time and abs((msg_time - target_time).total_seconds()) <= window.total_seconds():
                context.append(msg)
        
        # Sort by time
        context.sort(key=lambda m: m.get("_parsed_time", datetime.min))
        return context
    
    def _is_discussion_message(self, text: str) -> bool:
        """
        Check if a message is likely part of a discussion (not just a bot scan).
        Filters out automated bot messages to focus on human opinions.
        """
        text_lower = text.lower()
        
        # Skip if it's just a link/scan with no commentary
        if len(text) < 50 and any(x in text_lower for x in ['pump.fun/', 'dexscreener.com/', 'birdeye.so/']):
            # Check if there's actual text beyond the link
            text_without_urls = re.sub(r'https?://\S+', '', text)
            if len(text_without_urls.strip()) < 20:
                return False
        
        # Skip obvious bot messages
        bot_patterns = [
            r'^CA[:\s]',
            r'^Contract[:\s]',
            r'^\d+\.\d+[KMB]?\s*\|\s*\d+',  # Price | holders format
            r'^🔫|^🎯|^📊',  # Common bot emojis at start
        ]
        for pattern in bot_patterns:
            if re.match(pattern, text):
                return False
        
        return True
    
    async def _generate_discussion_summary(
        self,
        token: TokenDiscussion,
        discussions: List[Dict]
    ) -> TokenDiscussion:
        """Generate AI summary of the discussion context."""
        if not discussions or not GROQ_API_KEY:
            token.summary = f"Mentioned {token.mention_count} times across {len(token.chats)} chats."
            return token
        
        # Collect discussion texts, filtering for actual discussions
        discussion_texts = []
        for disc in discussions:
            for msg in disc.get("messages", []):
                text = msg.get("text", "")
                if text and self._is_discussion_message(text):
                    # Clean up the text
                    clean = re.sub(r'https?://\S+', '[link]', text)
                    clean = re.sub(r'[1-9A-HJ-NP-Za-km-z]{32,44}', '[address]', clean)
                    if len(clean) > 20:
                        discussion_texts.append(clean[:300])
        
        if not discussion_texts:
            token.summary = f"Token shared {token.mention_count} times but no detailed discussion found."
            return token
        
        # Prepare prompt - request concise plain text
        sample = discussion_texts[:15]  # Limit to 15 messages
        messages_text = "\n".join([f"- {m}" for m in sample])
        
        prompt = f"""You are analyzing crypto Telegram chat messages about ${token.symbol}.

Messages:
{messages_text}

Write a 2-3 sentence summary of what traders are saying. Include:
- The overall vibe (bullish/bearish/cautious)
- Any specific price targets, warnings, or calls mentioned
- Key opinions or concerns

IMPORTANT: Write in plain text only. No markdown, no bullet points, no headers. Just 2-3 natural sentences summarizing the discussion."""

        try:
            client = await self._get_client()
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
                timeout=20.0,
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if summary:
                    # Clean up any markdown formatting
                    clean_summary = summary.strip()
                    clean_summary = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_summary)  # Remove **bold**
                    clean_summary = re.sub(r'\*([^*]+)\*', r'\1', clean_summary)  # Remove *italic*
                    clean_summary = re.sub(r'^#+\s*', '', clean_summary, flags=re.MULTILINE)  # Remove headers
                    clean_summary = re.sub(r'^\d+\.\s*', '', clean_summary, flags=re.MULTILINE)  # Remove numbered lists
                    clean_summary = re.sub(r'^[-•]\s*', '', clean_summary, flags=re.MULTILINE)  # Remove bullet points
                    clean_summary = re.sub(r'\n+', ' ', clean_summary)  # Join multiple lines
                    clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()  # Normalize spaces
                    
                    token.summary = clean_summary[:500]  # Limit length
                    
                    # Extract sentiment from the raw response
                    summary_lower = summary.lower()
                    if 'bullish' in summary_lower or 'optimistic' in summary_lower or 'positive' in summary_lower:
                        token.sentiment = 'bullish'
                    elif 'bearish' in summary_lower or 'cautious' in summary_lower or 'warning' in summary_lower or 'scam' in summary_lower:
                        token.sentiment = 'bearish'
                    elif 'mixed' in summary_lower:
                        token.sentiment = 'mixed'
                    else:
                        token.sentiment = 'neutral'
                        
        except Exception as e:
            logger.warning("summary_failed", symbol=token.symbol, error=str(e))
            token.summary = f"Discussed in {len(token.chats)} chats with {len(discussion_texts)} messages."
        
        return token
    
    async def scan(
        self,
        messages: List[Dict[str, Any]],
        limit: int = 50,
    ) -> List[TokenDiscussion]:
        """
        Main scanning function.
        
        1. Parse timestamps on all messages
        2. Find token mentions
        3. For each mention, capture surrounding context
        4. Validate against DexScreener (skip if no data)
        5. Generate summaries
        6. Return sorted by recency
        """
        logger.info("contextual_scan_start", message_count=len(messages))
        
        # 1. Parse timestamps
        for msg in messages:
            ts_str = msg.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts.tzinfo:
                        ts = ts.replace(tzinfo=None)
                    msg["_parsed_time"] = ts
                except:
                    msg["_parsed_time"] = datetime.utcnow()
            else:
                msg["_parsed_time"] = datetime.utcnow()
        
        # 2. Find all token mentions
        token_mentions: Dict[str, List[Dict]] = defaultdict(list)  # address -> list of mention contexts
        
        for msg in messages:
            text = msg.get("text", "")
            if not text:
                continue
            
            token_info = self._extract_token_from_message(text)
            if token_info:
                address, chain = token_info
                token_mentions[address.lower()].append({
                    "message": msg,
                    "chain": chain,
                    "chat": msg.get("source_name", "Unknown"),
                    "time": msg.get("_parsed_time"),
                })
        
        logger.info("tokens_found", count=len(token_mentions))
        
        # 3. Build token discussions with context
        tokens: Dict[str, TokenDiscussion] = {}
        
        for address, mentions in token_mentions.items():
            # Get DexScreener data first - skip if not found
            dex_data = await self._get_dexscreener_data(address)
            if not dex_data or not dex_data.get("symbol"):
                logger.debug("skipping_no_dex_data", address=address[:16])
                continue
            
            # Create token discussion
            first_mention = mentions[0]
            token = TokenDiscussion(
                address=address,
                chain=dex_data.get("chain", first_mention["chain"]),
                symbol=dex_data["symbol"],
                name=dex_data.get("name", ""),
                price_usd=dex_data.get("price_usd", 0),
                market_cap=dex_data.get("market_cap"),
                liquidity_usd=dex_data.get("liquidity_usd"),
                price_change_1h=dex_data.get("price_change_1h"),
                price_change_24h=dex_data.get("price_change_24h"),
                volume_24h=dex_data.get("volume_24h"),
                dex_url=dex_data.get("dex_url", f"https://dexscreener.com/search?q={address}"),
                image_url=dex_data.get("image_url"),
                mention_count=len(mentions),
                chats={m["chat"] for m in mentions},
                first_seen=min(m["time"] for m in mentions if m["time"]),
                last_seen=max(m["time"] for m in mentions if m["time"]),
            )
            
            # Gather contextual discussions for each mention
            discussions = []
            seen_contexts = set()  # Avoid duplicate contexts
            
            for mention in mentions:
                chat = mention["chat"]
                time = mention["time"]
                
                if not time:
                    continue
                
                # Get surrounding messages
                context_msgs = self._get_context_messages(
                    messages, chat, time, self.CONTEXT_WINDOW_MINUTES
                )
                
                # Create unique key for this context
                context_key = f"{chat}:{time.isoformat()[:16]}"  # Round to minute
                if context_key in seen_contexts:
                    continue
                seen_contexts.add(context_key)
                
                if context_msgs:
                    discussions.append({
                        "chat": chat,
                        "time": time.isoformat(),
                        "messages": [
                            {"text": m.get("text", ""), "time": m.get("_parsed_time").isoformat() if m.get("_parsed_time") else None}
                            for m in context_msgs
                        ],
                    })
            
            token.discussions = discussions
            tokens[address] = token
        
        logger.info("tokens_with_dex_data", count=len(tokens))
        
        # 4. Generate summaries
        for token in tokens.values():
            await self._generate_discussion_summary(token, token.discussions)
        
        # 5. Sort by last_seen (most recent first) and limit
        result = list(tokens.values())
        result.sort(key=lambda t: t.last_seen or datetime.min, reverse=True)
        result = result[:limit]
        
        logger.info("scan_complete", returned=len(result))
        return result


# Singleton
contextual_scanner = ContextualScanner()
