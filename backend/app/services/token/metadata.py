"""Token metadata service - fetches and caches token info from DexScreener"""

import httpx
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

# In-memory cache for token metadata
_token_cache: Dict[str, Dict[str, Any]] = {}
_cache_expiry: Dict[str, datetime] = {}
_pending_lookups: Dict[str, asyncio.Event] = {}

CACHE_DURATION = timedelta(hours=1)


class TokenMetadataService:
    """Service for fetching and caching token metadata"""
    
    def __init__(self):
        self.base_url = "https://api.dexscreener.com/latest/dex/tokens"
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def get_token_info(self, address: str, chain: str = "solana") -> Optional[Dict[str, Any]]:
        """
        Get token metadata from cache or DexScreener.
        
        Returns:
            Dict with symbol, name, price_usd, market_cap, liquidity, etc.
        """
        cache_key = f"{chain}:{address}"
        
        # Check cache
        if cache_key in _token_cache:
            if datetime.utcnow() < _cache_expiry.get(cache_key, datetime.min):
                return _token_cache[cache_key]
        
        # Check if another request is already fetching this token
        if cache_key in _pending_lookups:
            await _pending_lookups[cache_key].wait()
            return _token_cache.get(cache_key)
        
        # Mark as pending
        _pending_lookups[cache_key] = asyncio.Event()
        
        try:
            # Fetch from DexScreener
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/{address}")
            
            if response.status_code != 200:
                logger.warning("dexscreener_fetch_failed", address=address, status=response.status_code)
                return None
            
            data = response.json()
            pairs = data.get("pairs", [])
            
            if not pairs:
                # Cache empty result to avoid repeated lookups
                _token_cache[cache_key] = {"address": address, "symbol": None, "name": None}
                _cache_expiry[cache_key] = datetime.utcnow() + timedelta(minutes=5)
                return None
            
            # Get the most liquid pair for this chain, or just the most liquid overall
            chain_pairs = [p for p in pairs if p.get("chainId", "").lower() == chain]
            if chain_pairs:
                pairs = chain_pairs
            
            pairs = sorted(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
            pair = pairs[0]
            
            base_token = pair.get("baseToken", {})
            
            token_info = {
                "address": address,
                "symbol": base_token.get("symbol"),
                "name": base_token.get("name"),
                "chain": pair.get("chainId", chain),
                "price_usd": float(pair.get("priceUsd", 0) or 0),
                "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0) or 0),
                "market_cap": float(pair.get("marketCap", 0) or 0),
                "fdv": float(pair.get("fdv", 0) or 0),
                "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                "pair_address": pair.get("pairAddress"),
                "dex_id": pair.get("dexId"),
                "url": pair.get("url"),
                "fetched_at": datetime.utcnow().isoformat(),
            }
            
            # Cache the result
            _token_cache[cache_key] = token_info
            _cache_expiry[cache_key] = datetime.utcnow() + CACHE_DURATION
            
            logger.info(
                "token_metadata_fetched",
                address=address,
                symbol=token_info["symbol"],
                name=token_info["name"],
            )
            
            return token_info
            
        except Exception as e:
            logger.error("token_metadata_error", address=address, error=str(e))
            return None
        finally:
            # Signal completion
            if cache_key in _pending_lookups:
                _pending_lookups[cache_key].set()
                del _pending_lookups[cache_key]
    
    async def batch_get_token_info(self, tokens: list) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for multiple tokens in parallel.
        
        Args:
            tokens: List of dicts with 'address' and 'chain' keys
        
        Returns:
            Dict mapping "chain:address" to token info
        """
        tasks = []
        for token in tokens:
            address = token.get("address")
            chain = token.get("chain", "solana")
            if address:
                tasks.append(self.get_token_info(address, chain))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for token, result in zip(tokens, results):
            if isinstance(result, dict):
                key = f"{token.get('chain', 'solana')}:{token.get('address')}"
                output[key] = result
        
        return output
    
    def get_cached_symbol(self, address: str, chain: str = "solana") -> Optional[str]:
        """Get cached symbol for an address (sync, from cache only)"""
        cache_key = f"{chain}:{address}"
        if cache_key in _token_cache:
            return _token_cache[cache_key].get("symbol")
        return None
    
    def get_cached_name(self, address: str, chain: str = "solana") -> Optional[str]:
        """Get cached name for an address (sync, from cache only)"""
        cache_key = f"{chain}:{address}"
        if cache_key in _token_cache:
            return _token_cache[cache_key].get("name")
        return None
    
    def update_cache(self, address: str, chain: str, symbol: str, name: str):
        """Manually update the cache (e.g., from user input)"""
        cache_key = f"{chain}:{address}"
        if cache_key not in _token_cache:
            _token_cache[cache_key] = {"address": address, "chain": chain}
        _token_cache[cache_key]["symbol"] = symbol
        _token_cache[cache_key]["name"] = name
        _cache_expiry[cache_key] = datetime.utcnow() + CACHE_DURATION
    
    def clear_cache(self, address: Optional[str] = None, chain: Optional[str] = None):
        """Clear the cache"""
        global _token_cache, _cache_expiry
        if address and chain:
            cache_key = f"{chain}:{address}"
            _token_cache.pop(cache_key, None)
            _cache_expiry.pop(cache_key, None)
        else:
            _token_cache = {}
            _cache_expiry = {}


# Singleton instance
token_metadata_service = TokenMetadataService()
