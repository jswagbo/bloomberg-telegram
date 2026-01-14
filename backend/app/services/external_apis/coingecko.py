"""CoinGecko API client - Free tier"""

from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

from app.core.config import settings
import structlog

logger = structlog.get_logger()


class CoinGeckoClient:
    """Client for CoinGecko API (free tier, rate limited)"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Platform IDs for different chains
    PLATFORM_MAP = {
        "solana": "solana",
        "ethereum": "ethereum",
        "eth": "ethereum",
        "bsc": "binance-smart-chain",
        "bnb": "binance-smart-chain",
        "base": "base",
    }
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "BloombergTelegram/1.0",
                },
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get_token_by_contract(
        self,
        address: str,
        chain: str = "solana"
    ) -> Optional[Dict[str, Any]]:
        """Get token info by contract address"""
        client = await self._get_client()
        platform = self.PLATFORM_MAP.get(chain.lower(), chain)
        
        try:
            response = await client.get(
                f"/coins/{platform}/contract/{address}"
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_coin_data(data, chain)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error("coingecko_contract_error", address=address, error=str(e))
            return None
        except httpx.HTTPError as e:
            logger.error("coingecko_contract_error", address=address, error=str(e))
            return None
    
    async def get_coin_by_id(
        self,
        coin_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get coin info by CoinGecko ID"""
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return self._parse_coin_data(data)
            
        except httpx.HTTPError as e:
            logger.error("coingecko_coin_error", coin_id=coin_id, error=str(e))
            return None
    
    async def search(
        self,
        query: str
    ) -> List[Dict[str, Any]]:
        """Search for coins"""
        client = await self._get_client()
        
        try:
            response = await client.get(
                "/search",
                params={"query": query}
            )
            response.raise_for_status()
            data = response.json()
            
            coins = data.get("coins", [])[:10]
            return [
                {
                    "id": c.get("id"),
                    "symbol": c.get("symbol"),
                    "name": c.get("name"),
                    "market_cap_rank": c.get("market_cap_rank"),
                    "thumb": c.get("thumb"),
                }
                for c in coins
            ]
            
        except httpx.HTTPError as e:
            logger.error("coingecko_search_error", query=query, error=str(e))
            return []
    
    async def get_trending(self) -> List[Dict[str, Any]]:
        """Get trending coins"""
        client = await self._get_client()
        
        try:
            response = await client.get("/search/trending")
            response.raise_for_status()
            data = response.json()
            
            coins = data.get("coins", [])
            return [
                {
                    "id": c.get("item", {}).get("id"),
                    "symbol": c.get("item", {}).get("symbol"),
                    "name": c.get("item", {}).get("name"),
                    "market_cap_rank": c.get("item", {}).get("market_cap_rank"),
                    "price_btc": c.get("item", {}).get("price_btc"),
                    "score": c.get("item", {}).get("score"),
                }
                for c in coins
            ]
            
        except httpx.HTTPError as e:
            logger.error("coingecko_trending_error", error=str(e))
            return []
    
    async def get_simple_price(
        self,
        ids: List[str],
        vs_currencies: List[str] = ["usd"]
    ) -> Dict[str, Dict[str, float]]:
        """Get simple price for multiple coins"""
        client = await self._get_client()
        
        try:
            response = await client.get(
                "/simple/price",
                params={
                    "ids": ",".join(ids),
                    "vs_currencies": ",".join(vs_currencies),
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true",
                    "include_market_cap": "true",
                }
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error("coingecko_simple_price_error", error=str(e))
            return {}
    
    def _parse_coin_data(
        self,
        data: Dict[str, Any],
        chain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse CoinGecko coin data into standard format"""
        market_data = data.get("market_data", {})
        
        # Get contract address for specified chain
        platforms = data.get("platforms", {})
        address = None
        if chain:
            platform_key = self.PLATFORM_MAP.get(chain.lower())
            if platform_key:
                address = platforms.get(platform_key)
        
        return {
            "id": data.get("id"),
            "symbol": data.get("symbol", "").upper(),
            "name": data.get("name"),
            "address": address,
            "chain": chain,
            
            # Price data
            "price_usd": market_data.get("current_price", {}).get("usd"),
            "price_btc": market_data.get("current_price", {}).get("btc"),
            
            # Changes
            "price_change_24h": market_data.get("price_change_percentage_24h"),
            "price_change_7d": market_data.get("price_change_percentage_7d"),
            "price_change_30d": market_data.get("price_change_percentage_30d"),
            
            # Volume
            "volume_24h": market_data.get("total_volume", {}).get("usd"),
            
            # Market cap
            "market_cap": market_data.get("market_cap", {}).get("usd"),
            "market_cap_rank": data.get("market_cap_rank"),
            "fully_diluted_valuation": market_data.get("fully_diluted_valuation", {}).get("usd"),
            
            # Supply
            "circulating_supply": market_data.get("circulating_supply"),
            "total_supply": market_data.get("total_supply"),
            "max_supply": market_data.get("max_supply"),
            
            # ATH/ATL
            "ath": market_data.get("ath", {}).get("usd"),
            "ath_change_percentage": market_data.get("ath_change_percentage", {}).get("usd"),
            "atl": market_data.get("atl", {}).get("usd"),
            "atl_change_percentage": market_data.get("atl_change_percentage", {}).get("usd"),
            
            # Metadata
            "image": data.get("image", {}).get("small"),
            "last_updated": data.get("last_updated"),
            "source": "coingecko",
        }


# Singleton instance
coingecko_client = CoinGeckoClient()
