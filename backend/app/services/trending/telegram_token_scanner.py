"""
Telegram Token Scanner

Scans Telegram messages to find token mentions (addresses, tickers, links).
Then enriches them with market data from DexScreener/GeckoTerminal.
"""

import re
import httpx
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import structlog

logger = structlog.get_logger()


# Patterns to extract token addresses
SOLANA_ADDRESS_PATTERN = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
EVM_ADDRESS_PATTERN = r'\b0x[a-fA-F0-9]{40}\b'

# Patterns for token links
TOKEN_LINK_PATTERNS = [
    # pump.fun
    r'pump\.fun/(?:coin/)?([1-9A-HJ-NP-Za-km-z]{32,44})',
    # dexscreener
    r'dexscreener\.com/\w+/([1-9A-HJ-NP-Za-km-z]{32,44}|0x[a-fA-F0-9]{40})',
    # birdeye
    r'birdeye\.so/token/([1-9A-HJ-NP-Za-km-z]{32,44})',
    # solscan
    r'solscan\.io/token/([1-9A-HJ-NP-Za-km-z]{32,44})',
    # raydium
    r'raydium\.io/swap/?\?.*(?:inputMint|outputMint)=([1-9A-HJ-NP-Za-km-z]{32,44})',
    # jupiter
    r'jup\.ag/swap/[^/]+/([1-9A-HJ-NP-Za-km-z]{32,44})',
    # photon
    r'photon-sol\.tinyastro\.io/[^/]+/([1-9A-HJ-NP-Za-km-z]{32,44})',
    # gecko terminal
    r'geckoterminal\.com/\w+/pools/([1-9A-HJ-NP-Za-km-z]{32,44}|0x[a-fA-F0-9]{40})',
]


@dataclass
class FoundToken:
    """A token found in Telegram messages"""
    address: str
    chain: str  # solana, base, bsc, ethereum
    mention_count: int
    chats: Set[str]  # Chat names where mentioned
    first_seen: datetime
    last_seen: datetime
    sample_messages: List[str]
    
    # Enriched data (from DexScreener)
    symbol: Optional[str] = None
    name: Optional[str] = None
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    liquidity_usd: Optional[float] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    dexscreener_url: Optional[str] = None
    image_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "chain": self.chain,
            "symbol": self.symbol or "UNKNOWN",
            "name": self.name or "Unknown Token",
            "mention_count": self.mention_count,
            "chat_count": len(self.chats),
            "chats": list(self.chats),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "sample_messages": self.sample_messages[:3],
            "price_usd": self.price_usd,
            "market_cap": self.market_cap,
            "liquidity_usd": self.liquidity_usd,
            "price_change_24h": self.price_change_24h,
            "volume_24h": self.volume_24h,
            "dexscreener_url": self.dexscreener_url or f"https://dexscreener.com/search?q={self.address}",
            "image_url": self.image_url,
        }


class TelegramTokenScanner:
    """Scans Telegram messages for token addresses and enriches with market data"""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._token_cache: Dict[str, Dict] = {}  # address -> DexScreener data
        self._cache_time: Dict[str, datetime] = {}
        self._trending_tokens: List[Dict] = []  # Cached trending tokens for name/symbol search
        self._trending_cache_time: Optional[datetime] = None
        self.cache_duration = timedelta(minutes=5)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def _get_trending_tokens(self) -> List[Dict]:
        """Fetch trending tokens from DexScreener for name/symbol matching"""
        # Check cache
        if (self._trending_cache_time and 
            datetime.utcnow() - self._trending_cache_time < self.cache_duration and
            self._trending_tokens):
            return self._trending_tokens
        
        try:
            client = await self._get_client()
            
            # Get trending from DexScreener
            response = await client.get(
                "https://api.dexscreener.com/token-boosts/top/v1",
                params={"chainId": "solana"}
            )
            
            tokens = []
            if response.status_code == 200:
                data = response.json()
                for item in data[:100]:  # Top 100 trending
                    tokens.append({
                        "address": item.get("tokenAddress", ""),
                        "symbol": item.get("symbol", ""),
                        "name": item.get("name", ""),
                        "chain": item.get("chainId", "solana"),
                    })
            
            # Also get new pairs
            response2 = await client.get(
                "https://api.dexscreener.com/latest/dex/pairs/solana",
                params={"sort": "pairCreatedAt", "order": "desc"}
            )
            
            if response2.status_code == 200:
                data2 = response2.json()
                for pair in data2.get("pairs", [])[:50]:
                    base = pair.get("baseToken", {})
                    tokens.append({
                        "address": base.get("address", ""),
                        "symbol": base.get("symbol", ""),
                        "name": base.get("name", ""),
                        "chain": pair.get("chainId", "solana"),
                    })
            
            self._trending_tokens = tokens
            self._trending_cache_time = datetime.utcnow()
            logger.info("trending_tokens_fetched", count=len(tokens))
            return tokens
            
        except Exception as e:
            logger.warning("trending_tokens_fetch_failed", error=str(e))
            return self._trending_tokens or []
    
    def _message_mentions_token(self, text: str, symbol: str, name: str) -> bool:
        """Check if message mentions a token by symbol or name"""
        text_lower = text.lower()
        
        # Check $SYMBOL (with dollar sign)
        if symbol and len(symbol) >= 2:
            if re.search(rf'\${re.escape(symbol)}\b', text, re.IGNORECASE):
                return True
            # Check SYMBOL as standalone word (for symbols 3+ chars to avoid false positives)
            if len(symbol) >= 3:
                if re.search(rf'\b{re.escape(symbol)}\b', text, re.IGNORECASE):
                    return True
        
        # Check name (4+ chars to avoid false positives)
        if name and len(name) >= 4:
            # Avoid common words
            common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'from', 'they', 'will', 'what', 'when', 'make', 'like', 'time', 'just', 'know', 'take', 'come', 'could', 'good', 'some', 'them', 'than', 'then', 'look', 'only', 'over', 'such', 'with', 'into', 'year', 'your', 'well', 'back', 'even', 'also', 'after', 'want', 'give', 'most', 'test', 'open', 'work', 'coin', 'token', 'pump', 'base'}
            if name.lower() not in common_words:
                if re.search(rf'\b{re.escape(name)}\b', text, re.IGNORECASE):
                    return True
        
        return False
    
    def _detect_chain(self, address: str) -> str:
        """Detect blockchain from address format"""
        if address.startswith("0x"):
            return "ethereum"  # Could be base, bsc, eth - need to check
        elif len(address) >= 32 and len(address) <= 44:
            # Likely Solana
            return "solana"
        return "unknown"
    
    def _extract_addresses_from_text(self, text: str) -> List[tuple]:
        """Extract token addresses from message text"""
        addresses = []
        
        # First, try to extract from known token links
        for pattern in TOKEN_LINK_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match:
                    chain = self._detect_chain(match)
                    addresses.append((match, chain))
        
        # Then extract standalone Solana addresses
        sol_matches = re.findall(SOLANA_ADDRESS_PATTERN, text)
        for addr in sol_matches:
            # Filter out common false positives
            if len(addr) >= 32 and len(addr) <= 44:
                # Skip if it looks like a transaction hash or other non-token
                if not any(x in text.lower() for x in ['tx:', 'transaction:', 'sig:']):
                    addresses.append((addr, "solana"))
        
        # Extract EVM addresses
        evm_matches = re.findall(EVM_ADDRESS_PATTERN, text)
        for addr in evm_matches:
            addresses.append((addr, "ethereum"))
        
        return addresses
    
    def scan_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, FoundToken]:
        """
        Scan messages and extract all token addresses.
        
        Returns:
            Dict mapping address to FoundToken
        """
        found_tokens: Dict[str, FoundToken] = {}
        
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
            
            # Extract addresses
            addresses = self._extract_addresses_from_text(text)
            
            for address, chain in addresses:
                address_lower = address.lower()
                
                if address_lower in found_tokens:
                    # Update existing
                    token = found_tokens[address_lower]
                    token.mention_count += 1
                    token.chats.add(source_name)
                    if timestamp < token.first_seen:
                        token.first_seen = timestamp
                    if timestamp > token.last_seen:
                        token.last_seen = timestamp
                    if len(token.sample_messages) < 5 and text not in token.sample_messages:
                        # Clean up the message for display
                        clean_text = text[:200] + "..." if len(text) > 200 else text
                        token.sample_messages.append(clean_text)
                else:
                    # New token
                    clean_text = text[:200] + "..." if len(text) > 200 else text
                    found_tokens[address_lower] = FoundToken(
                        address=address,
                        chain=chain,
                        mention_count=1,
                        chats={source_name},
                        first_seen=timestamp,
                        last_seen=timestamp,
                        sample_messages=[clean_text],
                    )
        
        logger.info("tokens_scanned", total_found=len(found_tokens))
        return found_tokens
    
    async def enrich_token(self, token: FoundToken) -> FoundToken:
        """Enrich a token with market data from DexScreener"""
        # Check cache
        cache_key = token.address.lower()
        if cache_key in self._token_cache:
            cache_time = self._cache_time.get(cache_key, datetime.min)
            if datetime.utcnow() - cache_time < self.cache_duration:
                data = self._token_cache[cache_key]
                token.symbol = data.get("symbol")
                token.name = data.get("name")
                token.price_usd = data.get("price_usd")
                token.market_cap = data.get("market_cap")
                token.liquidity_usd = data.get("liquidity_usd")
                token.price_change_24h = data.get("price_change_24h")
                token.volume_24h = data.get("volume_24h")
                token.dexscreener_url = data.get("dexscreener_url")
                token.image_url = data.get("image_url")
                token.chain = data.get("chain", token.chain)
                return token
        
        try:
            client = await self._get_client()
            
            # Try DexScreener API
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token.address}"
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                
                if pairs:
                    # Use the highest liquidity pair
                    pairs.sort(key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0, reverse=True)
                    pair = pairs[0]
                    
                    token_data = pair.get("baseToken", {})
                    if token_data.get("address", "").lower() != token.address.lower():
                        token_data = pair.get("quoteToken", {})
                    
                    enriched = {
                        "symbol": token_data.get("symbol", "???"),
                        "name": token_data.get("name", "Unknown"),
                        "price_usd": float(pair.get("priceUsd", 0) or 0),
                        "market_cap": pair.get("fdv"),
                        "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                        "price_change_24h": pair.get("priceChange", {}).get("h24"),
                        "volume_24h": pair.get("volume", {}).get("h24"),
                        "dexscreener_url": pair.get("url"),
                        "image_url": pair.get("info", {}).get("imageUrl"),
                        "chain": pair.get("chainId", token.chain),
                    }
                    
                    # Cache
                    self._token_cache[cache_key] = enriched
                    self._cache_time[cache_key] = datetime.utcnow()
                    
                    # Apply to token
                    token.symbol = enriched["symbol"]
                    token.name = enriched["name"]
                    token.price_usd = enriched["price_usd"]
                    token.market_cap = enriched["market_cap"]
                    token.liquidity_usd = enriched["liquidity_usd"]
                    token.price_change_24h = enriched["price_change_24h"]
                    token.volume_24h = enriched["volume_24h"]
                    token.dexscreener_url = enriched["dexscreener_url"]
                    token.image_url = enriched["image_url"]
                    token.chain = enriched["chain"]
                    
        except Exception as e:
            logger.warning("enrich_token_failed", address=token.address, error=str(e))
        
        return token
    
    async def scan_and_enrich(
        self,
        messages: List[Dict[str, Any]],
        min_mentions: int = 1,
        limit: int = 50,
    ) -> List[FoundToken]:
        """
        Scan messages for tokens and enrich with market data.
        
        Searches for:
        1. Contract addresses (full and in links)
        2. Token symbols ($SYMBOL)
        3. Token names (for trending tokens)
        
        Args:
            messages: List of message dicts
            min_mentions: Minimum mentions to include
            limit: Max tokens to return
            
        Returns:
            List of FoundToken sorted by mention count
        """
        # 1. Scan for token addresses in messages
        found_tokens = self.scan_messages(messages)
        
        # 2. Also scan for trending token names/symbols
        trending = await self._get_trending_tokens()
        
        for token_info in trending:
            address = token_info.get("address", "")
            symbol = token_info.get("symbol", "")
            name = token_info.get("name", "")
            chain = token_info.get("chain", "solana")
            
            if not address:
                continue
            
            address_lower = address.lower()
            
            # Check each message for name/symbol mentions
            for msg in messages:
                text = msg.get("text", "")
                if not text:
                    continue
                
                # Skip if we already found this token by address
                if address_lower in found_tokens:
                    # Still count the name/symbol mention
                    if self._message_mentions_token(text, symbol, name):
                        found_tokens[address_lower].mention_count += 1
                        found_tokens[address_lower].chats.add(msg.get("source_name", "Unknown"))
                    continue
                
                # Check if message mentions this token by name/symbol
                if self._message_mentions_token(text, symbol, name):
                    source_name = msg.get("source_name", "Unknown")
                    timestamp_str = msg.get("timestamp")
                    
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.utcnow()
                        if timestamp.tzinfo:
                            timestamp = timestamp.replace(tzinfo=None)
                    except:
                        timestamp = datetime.utcnow()
                    
                    clean_text = text[:200] + "..." if len(text) > 200 else text
                    
                    if address_lower in found_tokens:
                        # Update existing
                        found_tokens[address_lower].mention_count += 1
                        found_tokens[address_lower].chats.add(source_name)
                        if len(found_tokens[address_lower].sample_messages) < 5:
                            found_tokens[address_lower].sample_messages.append(clean_text)
                    else:
                        # New token found by name/symbol
                        found_tokens[address_lower] = FoundToken(
                            address=address,
                            chain=chain,
                            mention_count=1,
                            chats={source_name},
                            first_seen=timestamp,
                            last_seen=timestamp,
                            sample_messages=[clean_text],
                            symbol=symbol,
                            name=name,
                        )
        
        logger.info("tokens_after_name_scan", 
                    total=len(found_tokens),
                    trending_checked=len(trending))
        
        # Filter by min mentions
        filtered = [t for t in found_tokens.values() if t.mention_count >= min_mentions]
        
        # Sort by mentions
        filtered.sort(key=lambda t: t.mention_count, reverse=True)
        
        # Limit
        filtered = filtered[:limit]
        
        # Enrich with market data
        enriched = []
        for token in filtered:
            enriched_token = await self.enrich_token(token)
            enriched.append(enriched_token)
        
        logger.info("scan_complete", 
                    total_found=len(found_tokens),
                    filtered=len(filtered),
                    enriched=len(enriched))
        
        return enriched


# Singleton
telegram_token_scanner = TelegramTokenScanner()
