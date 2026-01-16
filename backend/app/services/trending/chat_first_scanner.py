"""
Chat-First Token Scanner

INVERTED FLOW:
1. Scan Telegram chats for ALL token mentions (addresses, $SYMBOLS, names)
2. Look up each token on DexScreener for market data
3. Generate chat summaries for each token
4. Return the last 50 unique tokens discussed

No limiting to "trending" tokens - we find what's actually being discussed.
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

# Groq API for summaries
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"


# ============================================================================
# PATTERNS FOR FINDING TOKENS
# ============================================================================

# Solana address pattern (base58, 32-44 chars)
SOLANA_ADDR_PATTERN = r'[1-9A-HJ-NP-Za-km-z]{32,44}'

# EVM address pattern
EVM_ADDR_PATTERN = r'0x[a-fA-F0-9]{40}'

# Token links - extract address from URL
TOKEN_URL_PATTERNS = [
    (r'pump\.fun/(?:coin/)?([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'dexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'dexscreener\.com/base/(0x[a-fA-F0-9]{40})', 'base'),
    (r'dexscreener\.com/bsc/(0x[a-fA-F0-9]{40})', 'bsc'),
    (r'dexscreener\.com/ethereum/(0x[a-fA-F0-9]{40})', 'ethereum'),
    (r'birdeye\.so/token/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'solscan\.io/token/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'jup\.ag/swap/[^/]+/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'raydium\.io/swap/?\?.*?(?:inputMint|outputMint)=([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'photon-sol\.tinyastro\.io/[^/]+/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'geckoterminal\.com/solana/pools/([1-9A-HJ-NP-Za-km-z]{32,44})', 'solana'),
    (r'geckoterminal\.com/base/pools/(0x[a-fA-F0-9]{40})', 'base'),
    (r'basescan\.org/token/(0x[a-fA-F0-9]{40})', 'base'),
    (r'bscscan\.com/token/(0x[a-fA-F0-9]{40})', 'bsc'),
]

# $SYMBOL pattern - captures tickers like $PEPE, $WIF
TICKER_PATTERN = r'\$([A-Za-z][A-Za-z0-9]{1,10})\b'

# Common false positive addresses to skip
FALSE_POSITIVE_ADDRS = {
    'So11111111111111111111111111111111111111112',  # Wrapped SOL
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
    '11111111111111111111111111111111',  # System program
}


@dataclass
class DiscoveredToken:
    """A token discovered in chat messages"""
    address: str
    chain: str
    discovery_method: str  # 'url', 'address', 'ticker'
    
    # From messages
    mention_count: int = 0
    chats: Set[str] = field(default_factory=set)
    messages: List[Dict] = field(default_factory=list)  # Raw messages mentioning this token
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    # From DexScreener (enriched)
    symbol: Optional[str] = None
    name: Optional[str] = None
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    liquidity_usd: Optional[float] = None
    price_change_1h: Optional[float] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    holders: Optional[int] = None
    dex_url: Optional[str] = None
    image_url: Optional[str] = None
    pair_created_at: Optional[datetime] = None
    
    # Chat summary (from LLM)
    chat_summary: Optional[str] = None
    sentiment: Optional[str] = None  # bullish, bearish, neutral
    per_chat_summaries: List[Dict] = field(default_factory=list)


class ChatFirstScanner:
    """
    Scans chats first, then enriches with market data.
    
    Flow:
    1. Extract ALL token mentions from messages
    2. Deduplicate by address
    3. Enrich each with DexScreener data
    4. Generate chat summaries
    5. Return top 50 by recency/mentions
    """
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._ticker_cache: Dict[str, str] = {}  # ticker -> address mapping
        self._enrichment_cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, datetime] = {}
        self.cache_duration = timedelta(minutes=3)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    def _extract_tokens_from_message(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extract all token references from a message.
        
        Returns:
            List of (address_or_ticker, chain, method) tuples
        """
        found = []
        
        # 1. Extract from URLs first (most reliable)
        for pattern, chain in TOKEN_URL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for addr in matches:
                if addr and addr not in FALSE_POSITIVE_ADDRS:
                    found.append((addr, chain, 'url'))
        
        # 2. Extract raw Solana addresses
        sol_addrs = re.findall(SOLANA_ADDR_PATTERN, text)
        for addr in sol_addrs:
            if addr not in FALSE_POSITIVE_ADDRS and len(addr) >= 32:
                # Skip if looks like transaction hash context
                if not any(x in text.lower() for x in ['tx:', 'transaction:', 'sig:', 'signature:']):
                    # Check it's not already found via URL
                    if not any(f[0] == addr for f in found):
                        found.append((addr, 'solana', 'address'))
        
        # 3. Extract raw EVM addresses
        evm_addrs = re.findall(EVM_ADDR_PATTERN, text)
        for addr in evm_addrs:
            if not any(f[0].lower() == addr.lower() for f in found):
                found.append((addr, 'ethereum', 'address'))  # Will detect actual chain later
        
        # 4. Extract $TICKERS
        tickers = re.findall(TICKER_PATTERN, text)
        for ticker in tickers:
            ticker_upper = ticker.upper()
            # Skip common words that look like tickers
            if ticker_upper not in {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 
                                    'CAN', 'HAD', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'USD',
                                    'SOL', 'ETH', 'BTC', 'BNB', 'USDC', 'USDT'}:
                found.append((ticker_upper, 'unknown', 'ticker'))
        
        return found
    
    async def _resolve_ticker(self, ticker: str) -> Optional[Tuple[str, str]]:
        """
        Resolve a ticker symbol to an address using DexScreener search.
        
        Returns:
            (address, chain) or None
        """
        # Check cache
        cache_key = f"ticker:{ticker}"
        if cache_key in self._ticker_cache:
            cached = self._ticker_cache[cache_key]
            if cached:
                return cached.split(':', 1) if ':' in cached else None
            return None
        
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://api.dexscreener.com/latest/dex/search",
                params={"q": ticker}
            )
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                
                # Find best match - prefer high liquidity Solana tokens
                best = None
                best_liquidity = 0
                
                for pair in pairs[:20]:  # Check top 20 results
                    base = pair.get("baseToken", {})
                    if base.get("symbol", "").upper() == ticker:
                        liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
                        if liquidity > best_liquidity:
                            best = (base.get("address"), pair.get("chainId", "solana"))
                            best_liquidity = liquidity
                
                if best:
                    self._ticker_cache[cache_key] = f"{best[0]}:{best[1]}"
                    return best
                
            self._ticker_cache[cache_key] = ""  # Cache negative result
            return None
            
        except Exception as e:
            logger.warning("ticker_resolve_failed", ticker=ticker, error=str(e))
            return None
    
    async def _enrich_token(self, token: DiscoveredToken) -> DiscoveredToken:
        """Enrich a token with DexScreener market data"""
        cache_key = token.address.lower()
        
        # Check cache
        if cache_key in self._enrichment_cache:
            cache_time = self._cache_time.get(cache_key, datetime.min)
            if datetime.utcnow() - cache_time < self.cache_duration:
                data = self._enrichment_cache[cache_key]
                self._apply_enrichment(token, data)
                return token
        
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{token.address}"
            )
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                
                if pairs:
                    # Use highest liquidity pair
                    pairs.sort(key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0, reverse=True)
                    pair = pairs[0]
                    
                    base = pair.get("baseToken", {})
                    if base.get("address", "").lower() != token.address.lower():
                        base = pair.get("quoteToken", {})
                    
                    enrichment = {
                        "symbol": base.get("symbol", "???"),
                        "name": base.get("name", "Unknown"),
                        "price_usd": float(pair.get("priceUsd") or 0),
                        "market_cap": pair.get("fdv"),
                        "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                        "price_change_1h": pair.get("priceChange", {}).get("h1"),
                        "price_change_24h": pair.get("priceChange", {}).get("h24"),
                        "volume_24h": pair.get("volume", {}).get("h24"),
                        "dex_url": pair.get("url"),
                        "image_url": pair.get("info", {}).get("imageUrl"),
                        "chain": pair.get("chainId", token.chain),
                        "pair_created_at": pair.get("pairCreatedAt"),
                    }
                    
                    # Cache it
                    self._enrichment_cache[cache_key] = enrichment
                    self._cache_time[cache_key] = datetime.utcnow()
                    
                    self._apply_enrichment(token, enrichment)
                    
        except Exception as e:
            logger.warning("enrich_failed", address=token.address, error=str(e))
        
        return token
    
    def _apply_enrichment(self, token: DiscoveredToken, data: Dict):
        """Apply enrichment data to token"""
        token.symbol = data.get("symbol")
        token.name = data.get("name")
        token.price_usd = data.get("price_usd")
        token.market_cap = data.get("market_cap")
        token.liquidity_usd = data.get("liquidity_usd")
        token.price_change_1h = data.get("price_change_1h")
        token.price_change_24h = data.get("price_change_24h")
        token.volume_24h = data.get("volume_24h")
        token.dex_url = data.get("dex_url")
        token.image_url = data.get("image_url")
        if data.get("chain"):
            token.chain = data["chain"]
        if data.get("pair_created_at"):
            try:
                token.pair_created_at = datetime.fromtimestamp(data["pair_created_at"] / 1000)
            except:
                pass
    
    async def _generate_summary(self, token: DiscoveredToken) -> DiscoveredToken:
        """Generate chat summary using LLM"""
        if not token.messages or not GROQ_API_KEY:
            return token
        
        # Group messages by chat
        by_chat: Dict[str, List[str]] = defaultdict(list)
        for msg in token.messages:
            chat = msg.get("source_name", "Unknown")
            text = msg.get("text", "")
            if text:
                by_chat[chat].append(text[:500])  # Limit message length
        
        # Generate per-chat summaries
        per_chat = []
        all_messages = []
        
        for chat_name, messages in by_chat.items():
            all_messages.extend(messages)
            
            # Simple sentiment analysis
            text_combined = " ".join(messages).lower()
            bullish_words = ['bullish', 'moon', 'pump', 'gem', 'alpha', 'lfg', 'buy', 'long', '🚀', '🔥']
            bearish_words = ['bearish', 'dump', 'rug', 'scam', 'sell', 'short', 'dead', '📉']
            
            bull_count = sum(1 for w in bullish_words if w in text_combined)
            bear_count = sum(1 for w in bearish_words if w in text_combined)
            
            chat_sentiment = "bullish" if bull_count > bear_count else "bearish" if bear_count > bull_count else "neutral"
            
            per_chat.append({
                "chat_name": chat_name,
                "message_count": len(messages),
                "sentiment": chat_sentiment,
                "summary": f"Discussed in {len(messages)} messages. Sentiment: {chat_sentiment}."
            })
        
        token.per_chat_summaries = per_chat
        
        # Generate overall summary with LLM
        try:
            client = await self._get_client()
            
            # Prepare messages for LLM
            sample_messages = all_messages[:15]  # Limit to 15 messages
            messages_text = "\n".join([f"- {m}" for m in sample_messages])
            
            prompt = f"""Analyze these Telegram chat messages about the token ${token.symbol or 'UNKNOWN'}:

{messages_text}

Provide a 2-3 sentence summary of what people are saying about this token. Include:
1. Overall sentiment (bullish/bearish/neutral)
2. Key points being discussed
3. Any warnings or alpha if mentioned

Be concise and factual."""

            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
                timeout=15.0,
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if summary:
                    token.chat_summary = summary.strip()
                    
                    # Detect sentiment from summary
                    summary_lower = summary.lower()
                    if any(w in summary_lower for w in ['bullish', 'positive', 'optimistic', 'buying']):
                        token.sentiment = "bullish"
                    elif any(w in summary_lower for w in ['bearish', 'negative', 'warning', 'careful', 'scam']):
                        token.sentiment = "bearish"
                    else:
                        token.sentiment = "neutral"
                        
        except Exception as e:
            logger.warning("summary_generation_failed", symbol=token.symbol, error=str(e))
            # Fallback summary
            total_msgs = sum(len(msgs) for msgs in by_chat.values())
            token.chat_summary = f"Mentioned {total_msgs} times across {len(by_chat)} chats."
            token.sentiment = "neutral"
        
        return token
    
    async def scan_chats(
        self,
        messages: List[Dict[str, Any]],
        limit: int = 50,
    ) -> List[DiscoveredToken]:
        """
        Main entry point: Scan messages, find tokens, enrich, summarize.
        
        Args:
            messages: List of message dicts with 'text', 'source_name', 'timestamp'
            limit: Max tokens to return
            
        Returns:
            List of DiscoveredToken sorted by last_seen (most recent first)
        """
        logger.info("chat_scan_start", message_count=len(messages))
        
        # 1. Extract all token mentions
        discovered: Dict[str, DiscoveredToken] = {}
        ticker_mentions: Dict[str, List[Dict]] = defaultdict(list)  # ticker -> messages
        
        for msg in messages:
            text = msg.get("text", "")
            if not text:
                continue
            
            source_name = msg.get("source_name", "Unknown")
            timestamp_str = msg.get("timestamp")
            
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.utcnow()
                if timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=None)
            except:
                timestamp = datetime.utcnow()
            
            # Extract tokens
            tokens_in_msg = self._extract_tokens_from_message(text)
            
            for addr_or_ticker, chain, method in tokens_in_msg:
                if method == 'ticker':
                    # Collect ticker mentions to resolve later
                    ticker_mentions[addr_or_ticker].append({
                        "text": text,
                        "source_name": source_name,
                        "timestamp": timestamp,
                    })
                else:
                    # Direct address - add to discovered
                    addr_lower = addr_or_ticker.lower()
                    
                    if addr_lower not in discovered:
                        discovered[addr_lower] = DiscoveredToken(
                            address=addr_or_ticker,
                            chain=chain,
                            discovery_method=method,
                            mention_count=1,
                            chats={source_name},
                            messages=[{"text": text, "source_name": source_name, "timestamp": timestamp}],
                            first_seen=timestamp,
                            last_seen=timestamp,
                        )
                    else:
                        token = discovered[addr_lower]
                        token.mention_count += 1
                        token.chats.add(source_name)
                        token.messages.append({"text": text, "source_name": source_name, "timestamp": timestamp})
                        if timestamp < token.first_seen:
                            token.first_seen = timestamp
                        if timestamp > token.last_seen:
                            token.last_seen = timestamp
        
        logger.info("extraction_complete", 
                    addresses_found=len(discovered),
                    tickers_found=len(ticker_mentions))
        
        # 2. Resolve tickers to addresses
        for ticker, msgs in ticker_mentions.items():
            resolved = await self._resolve_ticker(ticker)
            if resolved:
                addr, chain = resolved
                addr_lower = addr.lower()
                
                if addr_lower not in discovered:
                    first_msg = msgs[0]
                    discovered[addr_lower] = DiscoveredToken(
                        address=addr,
                        chain=chain,
                        discovery_method='ticker',
                        symbol=ticker,
                        mention_count=len(msgs),
                        chats={m["source_name"] for m in msgs},
                        messages=msgs,
                        first_seen=min(m["timestamp"] for m in msgs),
                        last_seen=max(m["timestamp"] for m in msgs),
                    )
                else:
                    token = discovered[addr_lower]
                    token.mention_count += len(msgs)
                    token.chats.update(m["source_name"] for m in msgs)
                    token.messages.extend(msgs)
                    for m in msgs:
                        if m["timestamp"] < token.first_seen:
                            token.first_seen = m["timestamp"]
                        if m["timestamp"] > token.last_seen:
                            token.last_seen = m["timestamp"]
        
        logger.info("ticker_resolution_complete", total_tokens=len(discovered))
        
        # 3. Sort by last_seen (most recent first)
        tokens_list = list(discovered.values())
        tokens_list.sort(key=lambda t: t.last_seen or datetime.min, reverse=True)
        
        # 4. Limit
        tokens_list = tokens_list[:limit]
        
        # 5. Enrich with market data
        enriched = []
        for token in tokens_list:
            enriched_token = await self._enrich_token(token)
            enriched.append(enriched_token)
        
        # 6. Generate summaries
        for token in enriched:
            await self._generate_summary(token)
        
        logger.info("scan_complete",
                    total_discovered=len(discovered),
                    returned=len(enriched))
        
        return enriched


# Singleton
chat_first_scanner = ChatFirstScanner()
