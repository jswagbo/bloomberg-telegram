"""DEX Screener API client - Free tier"""

from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

from app.core.config import settings
import structlog

logger = structlog.get_logger()


class DexScreenerClient:
    """Client for DEX Screener API (free, no auth required)"""
    
    BASE_URL = "https://api.dexscreener.com"
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get_token_by_address(
        self,
        address: str,
        chain: str = "solana"
    ) -> Optional[Dict[str, Any]]:
        """
        Get token info by contract address.
        
        DEX Screener uses chain identifiers:
        - solana
        - ethereum
        - bsc
        - base
        """
        client = await self._get_client()
        
        # Map chain names
        chain_map = {
            "solana": "solana",
            "ethereum": "ethereum", 
            "eth": "ethereum",
            "bsc": "bsc",
            "bnb": "bsc",
            "base": "base",
        }
        dex_chain = chain_map.get(chain.lower(), chain)
        
        try:
            response = await client.get(f"/latest/dex/tokens/{address}")
            response.raise_for_status()
            data = response.json()
            
            if not data.get("pairs"):
                return None
            
            # Find the main pair (highest liquidity)
            pairs = data["pairs"]
            
            # Filter by chain if specified
            if dex_chain:
                pairs = [p for p in pairs if p.get("chainId") == dex_chain]
            
            if not pairs:
                return None
            
            # Sort by liquidity
            pairs.sort(key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0, reverse=True)
            main_pair = pairs[0]
            
            return self._parse_pair(main_pair)
            
        except httpx.HTTPError as e:
            logger.error("dexscreener_error", address=address, error=str(e))
            return None
    
    async def search_tokens(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        client = await self._get_client()
        
        try:
            response = await client.get(f"/latest/dex/search/?q={query}")
            response.raise_for_status()
            data = response.json()
            
            pairs = data.get("pairs", [])[:limit]
            return [self._parse_pair(p) for p in pairs]
            
        except httpx.HTTPError as e:
            logger.error("dexscreener_search_error", query=query, error=str(e))
            return []
    
    async def get_pair_by_address(
        self,
        pair_address: str,
        chain: str = "solana"
    ) -> Optional[Dict[str, Any]]:
        """Get specific pair info"""
        client = await self._get_client()
        
        chain_map = {
            "solana": "solana",
            "ethereum": "ethereum",
            "bsc": "bsc",
            "base": "base",
        }
        dex_chain = chain_map.get(chain.lower(), chain)
        
        try:
            response = await client.get(f"/latest/dex/pairs/{dex_chain}/{pair_address}")
            response.raise_for_status()
            data = response.json()
            
            if data.get("pair"):
                return self._parse_pair(data["pair"])
            return None
            
        except httpx.HTTPError as e:
            logger.error("dexscreener_pair_error", pair=pair_address, error=str(e))
            return None
    
    async def get_trending(
        self,
        chain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get trending tokens (uses boosted endpoint)"""
        client = await self._get_client()
        
        try:
            # Get boosted tokens (trending)
            response = await client.get("/token-boosts/latest/v1")
            response.raise_for_status()
            data = response.json()
            
            tokens = []
            for item in data[:20]:
                if chain and item.get("chainId") != chain:
                    continue
                tokens.append({
                    "address": item.get("tokenAddress"),
                    "chain": item.get("chainId"),
                    "amount": item.get("amount"),
                })
            
            return tokens
            
        except httpx.HTTPError as e:
            logger.error("dexscreener_trending_error", error=str(e))
            return []
    
    def _parse_pair(self, pair: Dict[str, Any]) -> Dict[str, Any]:
        """Parse DEX Screener pair data into standard format"""
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        return {
            "address": base_token.get("address"),
            "symbol": base_token.get("symbol"),
            "name": base_token.get("name"),
            "chain": pair.get("chainId"),
            
            # Price data
            "price_usd": float(pair.get("priceUsd") or 0),
            "price_native": float(pair.get("priceNative") or 0),
            
            # Changes
            "price_change_5m": pair.get("priceChange", {}).get("m5"),
            "price_change_1h": pair.get("priceChange", {}).get("h1"),
            "price_change_6h": pair.get("priceChange", {}).get("h6"),
            "price_change_24h": pair.get("priceChange", {}).get("h24"),
            
            # Volume
            "volume_5m": pair.get("volume", {}).get("m5"),
            "volume_1h": pair.get("volume", {}).get("h1"),
            "volume_6h": pair.get("volume", {}).get("h6"),
            "volume_24h": pair.get("volume", {}).get("h24"),
            
            # Liquidity
            "liquidity_usd": pair.get("liquidity", {}).get("usd"),
            "liquidity_base": pair.get("liquidity", {}).get("base"),
            "liquidity_quote": pair.get("liquidity", {}).get("quote"),
            
            # Market cap (FDV)
            "market_cap": pair.get("fdv"),
            
            # Pair info
            "pair_address": pair.get("pairAddress"),
            "dex_id": pair.get("dexId"),
            "dex_screener_url": pair.get("url"),
            
            # Transactions
            "txns_5m_buys": pair.get("txns", {}).get("m5", {}).get("buys"),
            "txns_5m_sells": pair.get("txns", {}).get("m5", {}).get("sells"),
            "txns_1h_buys": pair.get("txns", {}).get("h1", {}).get("buys"),
            "txns_1h_sells": pair.get("txns", {}).get("h1", {}).get("sells"),
            "txns_24h_buys": pair.get("txns", {}).get("h24", {}).get("buys"),
            "txns_24h_sells": pair.get("txns", {}).get("h24", {}).get("sells"),
            
            # Metadata
            "pair_created_at": pair.get("pairCreatedAt"),
            "fetched_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
dexscreener_client = DexScreenerClient()
