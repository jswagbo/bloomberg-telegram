"""
DexScreener Trending Service

Fetches top trending tokens from DexScreener.
Focuses on tokens trending in the last 6 hours.
"""

import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import structlog

logger = structlog.get_logger()

# Cache
_trending_cache: List[Dict[str, Any]] = []
_cache_time: Optional[datetime] = None
CACHE_DURATION = timedelta(minutes=3)  # Refresh more frequently for 6h trending


@dataclass
class TrendingToken:
    """A trending token from DexScreener"""
    address: str
    symbol: str
    name: str
    chain: str
    price_usd: Optional[float]
    price_change_24h: Optional[float]
    price_change_6h: Optional[float]  # NEW: 6-hour change
    price_change_1h: Optional[float]  # NEW: 1-hour change
    volume_24h: Optional[float]
    volume_6h: Optional[float]  # NEW: 6-hour volume
    market_cap: Optional[float]
    liquidity: Optional[float]
    image_url: Optional[str]
    dexscreener_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "chain": self.chain,
            "price_usd": self.price_usd,
            "price_change_24h": self.price_change_24h,
            "price_change_6h": self.price_change_6h,
            "price_change_1h": self.price_change_1h,
            "volume_24h": self.volume_24h,
            "volume_6h": self.volume_6h,
            "market_cap": self.market_cap,
            "liquidity": self.liquidity,
            "image_url": self.image_url,
            "dexscreener_url": self.dexscreener_url,
        }


class DexScreenerTrendingService:
    """Service to fetch trending tokens from DexScreener"""
    
    def __init__(self):
        self.base_url = "https://api.dexscreener.com"
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    def _normalize_chain(self, chain: str) -> str:
        """Normalize chain name to our standard format"""
        chain_map = {
            "solana": "solana",
            "ethereum": "ethereum",
            "eth": "ethereum",
            "base": "base",
            "bsc": "bsc",
            "binance": "bsc",
            "arbitrum": "arbitrum",
            "polygon": "polygon",
            "avalanche": "avalanche",
        }
        return chain_map.get(chain.lower(), chain.lower())
    
    async def get_trending_tokens(
        self,
        chains: List[str] = None,
        limit: int = 100,
        force_refresh: bool = False,
        hours: int = 6,  # Trending in last N hours
    ) -> List[TrendingToken]:
        """
        Fetch trending tokens from DexScreener - focused on last 6 hours.
        
        Args:
            chains: Filter by chains (default: solana, base, bsc)
            limit: Max tokens to return
            force_refresh: Bypass cache
            hours: Trending window (default 6 hours)
        
        Returns:
            List of trending tokens
        """
        global _trending_cache, _cache_time
        
        # Check cache
        if not force_refresh and _cache_time and datetime.utcnow() - _cache_time < CACHE_DURATION:
            if _trending_cache:
                logger.info("trending_cache_hit", count=len(_trending_cache))
                return [TrendingToken(**t) for t in _trending_cache[:limit]]
        
        if chains is None:
            chains = ["solana", "base", "bsc"]
        
        all_tokens = []
        client = await self._get_client()
        
        try:
            # 1. Get token boosts (promoted tokens - often trending)
            try:
                resp = await client.get(f"{self.base_url}/token-boosts/top/v1")
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data[:50]:
                        chain = self._normalize_chain(item.get("chainId", ""))
                        if chain in chains:
                            token = self._parse_boost_token(item)
                            if token:
                                all_tokens.append(token)
            except Exception as e:
                logger.warning("boost_fetch_failed", error=str(e))
            
            # 2. Get latest token profiles (new tokens getting attention)
            try:
                resp = await client.get(f"{self.base_url}/token-profiles/latest/v1")
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data[:50]:
                        chain = self._normalize_chain(item.get("chainId", ""))
                        if chain in chains:
                            token = self._parse_profile_token(item)
                            if token:
                                all_tokens.append(token)
            except Exception as e:
                logger.warning("profiles_fetch_failed", error=str(e))
            
            # 3. Get top gainers on each chain (most active in last 6h)
            for chain in chains:
                try:
                    # Search for tokens with high 6h volume/activity
                    resp = await client.get(
                        f"{self.base_url}/latest/dex/search",
                        params={"q": f"chain:{chain}"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        pairs = data.get("pairs", [])[:40]
                        for pair in pairs:
                            token = self._parse_pair(pair, hours=hours)
                            if token:
                                all_tokens.append(token)
                except Exception as e:
                    logger.warning("search_fetch_failed", chain=chain, error=str(e))
                
                await asyncio.sleep(0.1)  # Rate limiting
            
            # Deduplicate by address
            seen = set()
            unique_tokens = []
            for token in all_tokens:
                key = f"{token.address}:{token.chain}"
                if key not in seen:
                    seen.add(key)
                    unique_tokens.append(token)
            
            # Sort by 6h activity (volume + price change)
            def activity_score(t: TrendingToken) -> float:
                score = 0
                if t.volume_24h:
                    score += t.volume_24h / 1000  # Normalize
                if t.price_change_6h is not None:
                    score += abs(t.price_change_6h) * 100  # Big movers score higher
                return score
            
            unique_tokens.sort(key=activity_score, reverse=True)
            
            # Cache the results
            _trending_cache = [t.to_dict() for t in unique_tokens[:limit]]
            _cache_time = datetime.utcnow()
            
            logger.info("trending_fetched", count=len(unique_tokens))
            return unique_tokens[:limit]
            
        except Exception as e:
            logger.error("trending_fetch_error", error=str(e))
            # Return cached data if available
            if _trending_cache:
                return [TrendingToken(**t) for t in _trending_cache[:limit]]
            return []
    
    def _parse_boost_token(self, data: Dict[str, Any]) -> Optional[TrendingToken]:
        """Parse a token from the boosts endpoint"""
        try:
            address = data.get("tokenAddress", "")
            if not address:
                return None
            
            chain = self._normalize_chain(data.get("chainId", "solana"))
            
            return TrendingToken(
                address=address,
                symbol=data.get("symbol", "???"),
                name=data.get("name", data.get("symbol", "Unknown")),
                chain=chain,
                price_usd=None,
                price_change_24h=None,
                price_change_6h=None,
                price_change_1h=None,
                volume_24h=None,
                volume_6h=None,
                market_cap=None,
                liquidity=None,
                image_url=data.get("icon"),
                dexscreener_url=f"https://dexscreener.com/{chain}/{address}",
            )
        except Exception:
            return None
    
    def _parse_profile_token(self, data: Dict[str, Any]) -> Optional[TrendingToken]:
        """Parse a token from the profiles endpoint"""
        try:
            address = data.get("tokenAddress", "")
            if not address:
                return None
            
            chain = self._normalize_chain(data.get("chainId", "solana"))
            
            return TrendingToken(
                address=address,
                symbol=data.get("symbol", "???"),
                name=data.get("name", data.get("symbol", "Unknown")),
                chain=chain,
                price_usd=None,
                price_change_24h=None,
                price_change_6h=None,
                price_change_1h=None,
                volume_24h=None,
                volume_6h=None,
                market_cap=None,
                liquidity=None,
                image_url=data.get("icon"),
                dexscreener_url=f"https://dexscreener.com/{chain}/{address}",
            )
        except Exception:
            return None
    
    def _parse_pair(self, pair: Dict[str, Any], hours: int = 6) -> Optional[TrendingToken]:
        """Parse a token from a trading pair"""
        try:
            base_token = pair.get("baseToken", {})
            address = base_token.get("address", "")
            if not address:
                return None
            
            chain = self._normalize_chain(pair.get("chainId", "solana"))
            price_change = pair.get("priceChange", {})
            volume = pair.get("volume", {})
            
            return TrendingToken(
                address=address,
                symbol=base_token.get("symbol", "???"),
                name=base_token.get("name", base_token.get("symbol", "Unknown")),
                chain=chain,
                price_usd=float(pair.get("priceUsd", 0)) if pair.get("priceUsd") else None,
                price_change_24h=price_change.get("h24"),
                price_change_6h=price_change.get("h6"),
                price_change_1h=price_change.get("h1"),
                volume_24h=float(volume.get("h24", 0)) if volume.get("h24") else None,
                volume_6h=float(volume.get("h6", 0)) if volume.get("h6") else None,
                market_cap=float(pair.get("marketCap", 0)) if pair.get("marketCap") else None,
                liquidity=float(pair.get("liquidity", {}).get("usd", 0)) if pair.get("liquidity", {}).get("usd") else None,
                image_url=pair.get("info", {}).get("imageUrl"),
                dexscreener_url=pair.get("url", f"https://dexscreener.com/{chain}/{address}"),
            )
        except Exception:
            return None
    
    async def get_token_info(self, address: str, chain: str = "solana") -> Optional[TrendingToken]:
        """Get info for a specific token"""
        client = await self._get_client()
        
        try:
            resp = await client.get(f"{self.base_url}/latest/dex/tokens/{address}")
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Find the pair for our chain
                    for pair in pairs:
                        if self._normalize_chain(pair.get("chainId", "")) == chain:
                            return self._parse_pair(pair)
                    # Fallback to first pair
                    return self._parse_pair(pairs[0])
        except Exception as e:
            logger.error("token_info_error", address=address, error=str(e))
        
        return None


# Singleton
trending_service = DexScreenerTrendingService()
