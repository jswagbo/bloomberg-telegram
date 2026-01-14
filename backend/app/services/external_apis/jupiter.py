"""Jupiter API client for Solana tokens - Free"""

from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

from app.core.config import settings
import structlog

logger = structlog.get_logger()


class JupiterClient:
    """Client for Jupiter Price API (Solana) - Free, no auth"""
    
    PRICE_API_URL = "https://price.jup.ag/v6"
    TOKEN_API_URL = "https://token.jup.ag"
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._token_list: Optional[Dict[str, Any]] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get_price(
        self,
        token_address: str,
        vs_token: str = "So11111111111111111111111111111111111111112"  # SOL
    ) -> Optional[Dict[str, Any]]:
        """
        Get token price from Jupiter.
        
        Args:
            token_address: Token mint address
            vs_token: Quote token (default SOL)
        """
        client = await self._get_client()
        
        try:
            # Get price vs SOL and USDC
            response = await client.get(
                f"{self.PRICE_API_URL}/price",
                params={
                    "ids": token_address,
                    "vsToken": vs_token,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("data", {}).get(token_address):
                return None
            
            price_data = data["data"][token_address]
            
            # Also get USD price
            usd_response = await client.get(
                f"{self.PRICE_API_URL}/price",
                params={
                    "ids": token_address,
                    "vsToken": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                }
            )
            usd_data = usd_response.json()
            usd_price = usd_data.get("data", {}).get(token_address, {}).get("price")
            
            return {
                "address": token_address,
                "price_native": price_data.get("price"),
                "price_usd": usd_price,
                "vs_token": vs_token,
                "chain": "solana",
                "source": "jupiter",
                "fetched_at": datetime.utcnow().isoformat(),
            }
            
        except httpx.HTTPError as e:
            logger.error("jupiter_price_error", address=token_address, error=str(e))
            return None
    
    async def get_multiple_prices(
        self,
        token_addresses: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get prices for multiple tokens at once"""
        client = await self._get_client()
        
        try:
            # Get all prices in one call
            response = await client.get(
                f"{self.PRICE_API_URL}/price",
                params={
                    "ids": ",".join(token_addresses),
                    "vsToken": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = {}
            for address in token_addresses:
                token_data = data.get("data", {}).get(address)
                if token_data:
                    results[address] = {
                        "address": address,
                        "price_usd": token_data.get("price"),
                        "chain": "solana",
                        "source": "jupiter",
                    }
            
            return results
            
        except httpx.HTTPError as e:
            logger.error("jupiter_multi_price_error", error=str(e))
            return {}
    
    async def get_token_info(
        self,
        token_address: str
    ) -> Optional[Dict[str, Any]]:
        """Get token metadata from Jupiter token list"""
        # Load token list if not cached
        if self._token_list is None:
            await self._load_token_list()
        
        if self._token_list and token_address in self._token_list:
            token = self._token_list[token_address]
            return {
                "address": token_address,
                "symbol": token.get("symbol"),
                "name": token.get("name"),
                "decimals": token.get("decimals"),
                "logo_uri": token.get("logoURI"),
                "chain": "solana",
                "tags": token.get("tags", []),
            }
        
        return None
    
    async def _load_token_list(self):
        """Load Jupiter strict token list"""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.TOKEN_API_URL}/strict")
            response.raise_for_status()
            tokens = response.json()
            
            self._token_list = {
                t["address"]: t for t in tokens
            }
            logger.info("jupiter_token_list_loaded", count=len(self._token_list))
            
        except httpx.HTTPError as e:
            logger.error("jupiter_token_list_error", error=str(e))
            self._token_list = {}
    
    async def search_tokens(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search tokens by name or symbol"""
        if self._token_list is None:
            await self._load_token_list()
        
        if not self._token_list:
            return []
        
        query_lower = query.lower()
        results = []
        
        for address, token in self._token_list.items():
            symbol = token.get("symbol", "").lower()
            name = token.get("name", "").lower()
            
            if query_lower in symbol or query_lower in name:
                results.append({
                    "address": address,
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "decimals": token.get("decimals"),
                    "logo_uri": token.get("logoURI"),
                })
                
                if len(results) >= limit:
                    break
        
        return results


# Singleton instance
jupiter_client = JupiterClient()
