"""Unified price service that aggregates from multiple sources"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.services.external_apis.dexscreener import dexscreener_client
from app.services.external_apis.jupiter import jupiter_client
from app.services.external_apis.coingecko import coingecko_client
from app.core.redis import get_redis
import structlog

logger = structlog.get_logger()


class PriceService:
    """Unified service for getting token prices from multiple sources"""
    
    # Cache TTL in seconds
    CACHE_TTL = 60  # 1 minute
    
    def __init__(self):
        self._cache: Dict[str, tuple] = {}  # (data, timestamp)
    
    def _get_cache_key(self, address: str, chain: str) -> str:
        return f"price:{chain}:{address}"
    
    def _get_from_cache(self, address: str, chain: str) -> Optional[Dict[str, Any]]:
        """Get from local cache if not expired"""
        key = self._get_cache_key(address, chain)
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.utcnow() - timestamp < timedelta(seconds=self.CACHE_TTL):
                return data
        return None
    
    def _set_cache(self, address: str, chain: str, data: Dict[str, Any]):
        """Set local cache"""
        key = self._get_cache_key(address, chain)
        self._cache[key] = (data, datetime.utcnow())
    
    async def get_token_price(
        self,
        address: str,
        chain: str = "solana"
    ) -> Optional[Dict[str, Any]]:
        """
        Get token price from best available source.
        
        Priority:
        1. DEX Screener (most comprehensive for DEX tokens)
        2. Jupiter (Solana-specific, fast)
        3. CoinGecko (fallback, rate limited)
        """
        # Check cache first
        cached = self._get_from_cache(address, chain)
        if cached:
            return cached
        
        result = None
        
        # Try DEX Screener first (works for all chains)
        try:
            dex_data = await dexscreener_client.get_token_by_address(address, chain)
            if dex_data and dex_data.get("price_usd"):
                result = self._normalize_price_data(dex_data, "dexscreener")
        except Exception as e:
            logger.debug("dexscreener_failed", address=address, error=str(e))
        
        # Try Jupiter for Solana
        if not result and chain.lower() == "solana":
            try:
                jup_data = await jupiter_client.get_price(address)
                if jup_data and jup_data.get("price_usd"):
                    result = self._normalize_price_data(jup_data, "jupiter")
            except Exception as e:
                logger.debug("jupiter_failed", address=address, error=str(e))
        
        # Try CoinGecko as fallback
        if not result:
            try:
                cg_data = await coingecko_client.get_token_by_contract(address, chain)
                if cg_data and cg_data.get("price_usd"):
                    result = self._normalize_price_data(cg_data, "coingecko")
            except Exception as e:
                logger.debug("coingecko_failed", address=address, error=str(e))
        
        if result:
            self._set_cache(address, chain, result)
        
        return result
    
    async def get_multiple_prices(
        self,
        tokens: List[Dict[str, str]]  # [{"address": "...", "chain": "..."}]
    ) -> Dict[str, Dict[str, Any]]:
        """Get prices for multiple tokens efficiently"""
        results = {}
        
        # Group by chain
        by_chain: Dict[str, List[str]] = {}
        for token in tokens:
            chain = token.get("chain", "solana")
            address = token["address"]
            
            # Check cache first
            cached = self._get_from_cache(address, chain)
            if cached:
                results[address] = cached
            else:
                if chain not in by_chain:
                    by_chain[chain] = []
                by_chain[chain].append(address)
        
        # Fetch Solana tokens via Jupiter (batch)
        if "solana" in by_chain:
            try:
                jup_prices = await jupiter_client.get_multiple_prices(by_chain["solana"])
                for address, data in jup_prices.items():
                    normalized = self._normalize_price_data(data, "jupiter")
                    results[address] = normalized
                    self._set_cache(address, "solana", normalized)
            except Exception as e:
                logger.debug("jupiter_batch_failed", error=str(e))
        
        # Fetch remaining via DEX Screener (individual calls)
        for chain, addresses in by_chain.items():
            for address in addresses:
                if address in results:
                    continue
                
                try:
                    data = await self.get_token_price(address, chain)
                    if data:
                        results[address] = data
                except Exception as e:
                    logger.debug("price_fetch_failed", address=address, error=str(e))
        
        return results
    
    async def get_token_info(
        self,
        address: str,
        chain: str = "solana"
    ) -> Optional[Dict[str, Any]]:
        """Get comprehensive token info (price + metadata)"""
        # Get price data
        price_data = await self.get_token_price(address, chain)
        
        # Get additional metadata from Jupiter for Solana
        if chain.lower() == "solana":
            try:
                jup_info = await jupiter_client.get_token_info(address)
                if jup_info and price_data:
                    price_data.update({
                        "name": jup_info.get("name") or price_data.get("name"),
                        "symbol": jup_info.get("symbol") or price_data.get("symbol"),
                        "decimals": jup_info.get("decimals"),
                        "logo_uri": jup_info.get("logo_uri"),
                    })
            except Exception as e:
                logger.debug("jupiter_info_failed", address=address, error=str(e))
        
        return price_data
    
    async def search_tokens(
        self,
        query: str,
        chain: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for tokens across multiple sources"""
        results = []
        seen_addresses = set()
        
        # Search DEX Screener
        try:
            dex_results = await dexscreener_client.search_tokens(query, limit)
            for token in dex_results:
                if chain and token.get("chain") != chain:
                    continue
                if token.get("address") not in seen_addresses:
                    seen_addresses.add(token["address"])
                    results.append(token)
        except Exception as e:
            logger.debug("dexscreener_search_failed", error=str(e))
        
        # Search Jupiter for Solana
        if not chain or chain.lower() == "solana":
            try:
                jup_results = await jupiter_client.search_tokens(query, limit)
                for token in jup_results:
                    if token.get("address") not in seen_addresses:
                        seen_addresses.add(token["address"])
                        token["chain"] = "solana"
                        results.append(token)
            except Exception as e:
                logger.debug("jupiter_search_failed", error=str(e))
        
        return results[:limit]
    
    def _normalize_price_data(
        self,
        data: Dict[str, Any],
        source: str
    ) -> Dict[str, Any]:
        """Normalize price data to consistent format"""
        return {
            "address": data.get("address"),
            "symbol": data.get("symbol"),
            "name": data.get("name"),
            "chain": data.get("chain"),
            
            "price_usd": data.get("price_usd"),
            "price_native": data.get("price_native"),
            
            "price_change_5m": data.get("price_change_5m"),
            "price_change_1h": data.get("price_change_1h"),
            "price_change_24h": data.get("price_change_24h"),
            
            "volume_24h": data.get("volume_24h"),
            "volume_change_24h": data.get("volume_change_percent"),
            
            "liquidity_usd": data.get("liquidity_usd"),
            "market_cap": data.get("market_cap"),
            
            "dex_screener_url": data.get("dex_screener_url"),
            
            "source": source,
            "fetched_at": datetime.utcnow().isoformat(),
        }
    
    async def close(self):
        """Close all API clients"""
        await dexscreener_client.close()
        await jupiter_client.close()
        await coingecko_client.close()


# Singleton instance
price_service = PriceService()
