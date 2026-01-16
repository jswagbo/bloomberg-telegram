"""
New Pairs Discovery Service

Focuses on MIGRATED tokens (pump.fun → PumpSwap/Raydium) which are
the tokens that actually get discussed in Telegram chats.

Since March 2025, pump.fun tokens migrate to PumpSwap instead of Raydium.
These "graduated" tokens hit ~$69k market cap and get real liquidity.
"""

import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
import re
import structlog

logger = structlog.get_logger()

# Cache
_new_pairs_cache: List[Dict[str, Any]] = []
_cache_time: Optional[datetime] = None
CACHE_DURATION = timedelta(minutes=2)  # Refresh frequently for new pairs

# Launchpad identifiers
PUMP_FUN_SUFFIX = "pump"  # Tokens ending in "pump" are from pump.fun
PUMPSWAP_DEX_IDS = ["pumpswap", "pump_swap", "pump-swap"]
RAYDIUM_DEX_IDS = ["raydium", "raydium_clmm", "raydium_cp"]

# bags.fm (formerly believe) - another Solana launchpad
BAGS_FM_IDENTIFIERS = ["bags", "believe", "bags.fm"]

# bonkbot / bonk launchpad
BONK_IDENTIFIERS = ["bonk", "bonkbot", "letsbonk"]

# All migrated DEXes
MIGRATED_DEX_IDS = PUMPSWAP_DEX_IDS + RAYDIUM_DEX_IDS + ["orca", "meteora"]


@dataclass
class NewPairToken:
    """A newly discovered token pair (preferably migrated from pump.fun)"""
    address: str
    symbol: str
    name: str
    chain: str
    price_usd: Optional[float]
    price_change_24h: Optional[float]
    price_change_1h: Optional[float]
    volume_24h: Optional[float]
    liquidity_usd: Optional[float]
    market_cap: Optional[float]
    
    # Holder data (from GeckoTerminal)
    holder_count: int
    top_10_percent: float  # Percentage held by top 10
    top_11_30_percent: float
    top_31_50_percent: float
    rest_percent: float
    
    # Metadata
    pool_created_at: Optional[datetime]
    age_hours: float
    dex_name: str
    is_boosted: bool  # Dex paid
    is_pump_fun: bool  # From pump.fun (address ends in "pump")
    is_migrated: bool  # Migrated to PumpSwap/Raydium
    launchpad: str  # "pump.fun", "bags.fm", "bonk", or ""
    
    image_url: Optional[str]
    dexscreener_url: str
    gecko_terminal_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "chain": self.chain,
            "price_usd": self.price_usd,
            "price_change_24h": self.price_change_24h,
            "price_change_1h": self.price_change_1h,
            "volume_24h": self.volume_24h,
            "liquidity_usd": self.liquidity_usd,
            "market_cap": self.market_cap,
            "holder_count": self.holder_count,
            "top_10_percent": self.top_10_percent,
            "top_11_30_percent": self.top_11_30_percent,
            "top_31_50_percent": self.top_31_50_percent,
            "rest_percent": self.rest_percent,
            "pool_created_at": self.pool_created_at.isoformat() if self.pool_created_at else None,
            "age_hours": self.age_hours,
            "dex_name": self.dex_name,
            "is_boosted": self.is_boosted,
            "is_pump_fun": self.is_pump_fun,
            "is_migrated": self.is_migrated,
            "launchpad": self.launchpad,
            "image_url": self.image_url,
            "dexscreener_url": self.dexscreener_url,
            "gecko_terminal_url": self.gecko_terminal_url,
        }


class NewPairsService:
    """Service to discover new token pairs with filtering"""
    
    def __init__(self):
        self.gecko_base_url = "https://api.geckoterminal.com/api/v2"
        self.dexscreener_url = "https://api.dexscreener.com"
        self._client: Optional[httpx.AsyncClient] = None
        self._boosted_tokens: set = set()  # Cache of boosted token addresses
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"}
            )
        return self._client
    
    def _normalize_chain(self, chain: str) -> str:
        """Normalize chain names between APIs"""
        chain_map = {
            "eth": "ethereum",
            "ethereum": "ethereum", 
            "sol": "solana",
            "solana": "solana",
            "bsc": "bsc",
            "bnb": "bsc",
            "base": "base",
            "arbitrum": "arbitrum",
            "polygon": "polygon",
        }
        return chain_map.get(chain.lower(), chain.lower())
    
    def _gecko_chain_id(self, chain: str) -> str:
        """Convert chain name to GeckoTerminal network ID"""
        chain_map = {
            "solana": "solana",
            "ethereum": "eth",
            "bsc": "bsc",
            "base": "base",
            "arbitrum": "arbitrum_one",
            "polygon": "polygon_pos",
        }
        return chain_map.get(chain, chain)
    
    async def _fetch_boosted_tokens(self) -> set:
        """Fetch list of boosted (dex paid) tokens from DexScreener"""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.dexscreener_url}/token-boosts/top/v1")
            if resp.status_code == 200:
                data = resp.json()
                return {item.get("tokenAddress", "").lower() for item in data if item.get("tokenAddress")}
        except Exception as e:
            logger.warning("fetch_boosted_failed", error=str(e))
        return set()
    
    def _is_pump_fun_token(self, address: str) -> bool:
        """Check if token is from pump.fun (addresses end in 'pump')"""
        return address.lower().endswith(PUMP_FUN_SUFFIX)
    
    def _is_bags_fm_token(self, name: str, symbol: str, dex_id: str) -> bool:
        """Check if token is from bags.fm launchpad"""
        name_lower = (name or "").lower()
        symbol_lower = (symbol or "").lower()
        dex_lower = (dex_id or "").lower()
        
        for identifier in BAGS_FM_IDENTIFIERS:
            if identifier in name_lower or identifier in symbol_lower or identifier in dex_lower:
                return True
        return False
    
    def _is_bonk_token(self, name: str, symbol: str, dex_id: str) -> bool:
        """Check if token is from bonk launchpad"""
        name_lower = (name or "").lower()
        symbol_lower = (symbol or "").lower()
        dex_lower = (dex_id or "").lower()
        
        for identifier in BONK_IDENTIFIERS:
            if identifier in name_lower or identifier in symbol_lower or identifier in dex_lower:
                return True
        return False
    
    def _is_migrated_dex(self, dex_id: str) -> bool:
        """Check if DEX is a migration target (PumpSwap, Raydium, Orca, Meteora)"""
        dex_lower = (dex_id or "").lower()
        return any(d in dex_lower for d in MIGRATED_DEX_IDS)
    
    def _get_launchpad(self, address: str, name: str, symbol: str, dex_id: str) -> str:
        """Determine which launchpad a token came from"""
        if self._is_pump_fun_token(address):
            return "pump.fun"
        if self._is_bags_fm_token(name, symbol, dex_id):
            return "bags.fm"
        if self._is_bonk_token(name, symbol, dex_id):
            return "bonk"
        return ""
    
    async def _fetch_migrated_tokens(
        self, 
        chains: List[str], 
        boosted_tokens: set,
        max_age_hours: int,
        min_liquidity: float,
        min_market_cap: float = 30000,  # Lower threshold to catch more tokens
    ) -> List[Dict[str, Any]]:
        """Fetch newly migrated tokens from pump.fun, bags.fm, bonk"""
        all_pairs = []
        client = await self._get_client()
        
        # Search for tokens from all launchpads
        search_queries = [
            "pump",  # pump.fun tokens
            "pumpswap",  # PumpSwap DEX
            "raydium",  # Raydium (old migration target)
            "bags",  # bags.fm
            "believe",  # bags.fm (old name)
            "bonk",  # bonk launchpad
            "meteora",  # Another popular Solana DEX
        ]
        
        for query in search_queries:
            try:
                resp = await client.get(
                    f"{self.dexscreener_url}/latest/dex/search",
                    params={"q": query}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    pairs = data.get("pairs", [])
                    
                    for pair in pairs:
                        base_token = pair.get("baseToken", {})
                        token_address = base_token.get("address", "")
                        dex_id = pair.get("dexId", "")
                        chain_id = pair.get("chainId", "")
                        
                        if not token_address:
                            continue
                        
                        # Only Solana for pump.fun tokens
                        if self._normalize_chain(chain_id) != "solana":
                            continue
                        
                        # Check if it's from a launchpad or on migrated DEX
                        token_name = base_token.get("name", "")
                        token_symbol = base_token.get("symbol", "")
                        
                        is_pump = self._is_pump_fun_token(token_address)
                        is_bags = self._is_bags_fm_token(token_name, token_symbol, dex_id)
                        is_bonk = self._is_bonk_token(token_name, token_symbol, dex_id)
                        is_migrated = self._is_migrated_dex(dex_id)
                        launchpad = self._get_launchpad(token_address, token_name, token_symbol, dex_id)
                        
                        # Include if from any launchpad OR on a migrated DEX
                        if not (is_pump or is_bags or is_bonk or is_migrated):
                            continue
                        
                        # Parse creation time
                        created_at = None
                        age_hours = 12
                        pair_created = pair.get("pairCreatedAt")
                        if pair_created:
                            try:
                                created_at = datetime.fromtimestamp(pair_created / 1000)
                                age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
                            except:
                                pass
                        
                        # Skip if too old
                        if age_hours > max_age_hours:
                            continue
                        
                        # Check liquidity (migrated tokens have real liquidity)
                        liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
                        if liquidity < min_liquidity:
                            continue
                        
                        # Check market cap (graduated = ~$69k+)
                        market_cap = pair.get("marketCap") or pair.get("fdv") or 0
                        if market_cap < min_market_cap:
                            continue
                        
                        price_change = pair.get("priceChange", {})
                        volume = pair.get("volume", {})
                        
                        all_pairs.append({
                            "pool_address": pair.get("pairAddress", token_address),
                            "name": token_name or "Unknown",
                            "base_token_address": token_address,
                            "base_token_symbol": token_symbol or "???",
                            "base_token_name": token_name or "Unknown",
                            "price_usd": float(pair.get("priceUsd") or 0) if pair.get("priceUsd") else None,
                            "price_change_24h": price_change.get("h24"),
                            "price_change_1h": price_change.get("h1"),
                            "volume_24h": float(volume.get("h24") or 0) if volume.get("h24") else None,
                            "liquidity_usd": liquidity,
                            "fdv_usd": market_cap,
                            "market_cap": market_cap,
                            "created_at": created_at,
                            "age_hours": age_hours,
                            "dex_name": dex_id,
                            "chain": "solana",
                            "is_boosted": token_address.lower() in boosted_tokens,
                            "is_pump_fun": is_pump,
                            "is_migrated": is_migrated,
                            "launchpad": launchpad,
                            "image_url": pair.get("info", {}).get("imageUrl"),
                        })
                    
                logger.info("migrated_tokens_search", query=query, found=len(all_pairs))
                    
            except Exception as e:
                logger.warning("migrated_search_error", query=query, error=str(e))
            
            await asyncio.sleep(0.3)
        
        # Deduplicate by address
        seen = set()
        unique_pairs = []
        for pair in all_pairs:
            addr = pair.get("base_token_address", "").lower()
            if addr and addr not in seen:
                seen.add(addr)
                unique_pairs.append(pair)
        
        # Sort by market cap (higher = more legitimate migrated token)
        unique_pairs.sort(key=lambda x: x.get("market_cap", 0) or 0, reverse=True)
        
        logger.info("migrated_tokens_total", count=len(unique_pairs))
        return unique_pairs
    
    async def _fetch_from_dexscreener(
        self, 
        chains: List[str], 
        boosted_tokens: set,
        max_age_hours: int,
        min_liquidity: float
    ) -> List[Dict[str, Any]]:
        """Fallback: Fetch new pairs from DexScreener search"""
        # First try to get migrated tokens (these are what Telegram discusses)
        migrated = await self._fetch_migrated_tokens(
            chains, boosted_tokens, max_age_hours, min_liquidity
        )
        
        if migrated:
            return migrated
        
        # If no migrated tokens, fall back to general search
        all_pairs = []
        client = await self._get_client()
        
        for chain in chains:
            try:
                resp = await client.get(
                    f"{self.dexscreener_url}/latest/dex/search",
                    params={"q": f"chain:{chain}"}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    pairs = data.get("pairs", [])[:30]
                    
                    for pair in pairs:
                        base_token = pair.get("baseToken", {})
                        token_address = base_token.get("address", "")
                        
                        if not token_address:
                            continue
                        
                        created_at = None
                        age_hours = 12
                        pair_created = pair.get("pairCreatedAt")
                        if pair_created:
                            try:
                                created_at = datetime.fromtimestamp(pair_created / 1000)
                                age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
                            except:
                                pass
                        
                        if age_hours > max_age_hours:
                            continue
                        
                        liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
                        if liquidity < min_liquidity:
                            continue
                        
                        price_change = pair.get("priceChange", {})
                        volume = pair.get("volume", {})
                        market_cap = pair.get("marketCap") or pair.get("fdv") or 0
                        
                        all_pairs.append({
                            "pool_address": pair.get("pairAddress", token_address),
                            "name": base_token.get("name", "Unknown"),
                            "base_token_address": token_address,
                            "base_token_symbol": base_token.get("symbol", "???"),
                            "base_token_name": base_token.get("name", "Unknown"),
                            "price_usd": float(pair.get("priceUsd") or 0) if pair.get("priceUsd") else None,
                            "price_change_24h": price_change.get("h24"),
                            "price_change_1h": price_change.get("h1"),
                            "volume_24h": float(volume.get("h24") or 0) if volume.get("h24") else None,
                            "liquidity_usd": liquidity,
                            "fdv_usd": market_cap,
                            "market_cap": market_cap,
                            "created_at": created_at,
                            "age_hours": age_hours,
                            "dex_name": pair.get("dexId", "unknown"),
                            "chain": self._normalize_chain(pair.get("chainId", chain)),
                            "is_boosted": token_address.lower() in boosted_tokens,
                            "is_pump_fun": self._is_pump_fun_token(token_address),
                            "is_migrated": False,
                            "image_url": pair.get("info", {}).get("imageUrl"),
                        })
                    
                    logger.info("dexscreener_fallback", chain=chain, pairs=len(all_pairs))
                    
            except Exception as e:
                logger.warning("dexscreener_fallback_error", chain=chain, error=str(e))
            
            await asyncio.sleep(0.2)
        
        return all_pairs
    
    async def _fetch_new_pools(self, chain: str) -> List[Dict[str, Any]]:
        """Fetch new pools from GeckoTerminal"""
        client = await self._get_client()
        network = self._gecko_chain_id(chain)
        pools = []
        
        try:
            # Fetch new pools with included token data
            resp = await client.get(
                f"{self.gecko_base_url}/networks/{network}/new_pools",
                params={"page": 1, "include": "base_token,quote_token"}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                raw_pools = data.get("data", [])
                included = data.get("included", [])
                
                # Build lookup for included token data
                token_lookup = {}
                for item in included:
                    if item.get("type") == "token":
                        token_lookup[item.get("id")] = item.get("attributes", {})
                
                # Enrich pools with token data
                for pool in raw_pools:
                    pool["_token_lookup"] = token_lookup
                    pools.append(pool)
                
                logger.info("fetched_new_pools", chain=chain, count=len(pools))
            else:
                logger.warning("new_pools_fetch_failed", chain=chain, status=resp.status_code)
                
        except Exception as e:
            logger.error("new_pools_error", chain=chain, error=str(e))
        
        return pools
    
    async def _fetch_token_info(self, chain: str, address: str) -> Optional[Dict[str, Any]]:
        """Fetch token info including holder data from GeckoTerminal"""
        client = await self._get_client()
        network = self._gecko_chain_id(chain)
        
        try:
            resp = await client.get(
                f"{self.gecko_base_url}/networks/{network}/tokens/{address}/info"
            )
            
            if resp.status_code == 200:
                data = resp.json()
                attrs = data.get("data", {}).get("attributes", {})
                logger.debug(
                    "token_info_response",
                    address=address[:10],
                    has_holders=bool(attrs.get("holders")),
                    holder_count=attrs.get("holders", {}).get("count") if attrs.get("holders") else None
                )
                return attrs
            elif resp.status_code == 404:
                logger.debug("token_info_not_found", chain=chain, address=address[:10])
            else:
                logger.warning("token_info_bad_status", chain=chain, address=address[:10], status=resp.status_code)
                
        except Exception as e:
            logger.warning("token_info_error", chain=chain, address=address[:10], error=str(e))
        
        return None
    
    def _parse_pool(self, pool_data: Dict[str, Any], chain: str, boosted_tokens: set) -> Optional[Dict[str, Any]]:
        """Parse pool data from GeckoTerminal"""
        try:
            attrs = pool_data.get("attributes", {})
            relationships = pool_data.get("relationships", {})
            token_lookup = pool_data.get("_token_lookup", {})
            
            # Get base token info from relationships + lookup
            base_token_ref = relationships.get("base_token", {}).get("data", {})
            base_token_id = base_token_ref.get("id", "")
            base_token_data = token_lookup.get(base_token_id, {})
            
            # Extract token address from the id (format: "network_address")
            base_token_address = base_token_data.get("address", "")
            if not base_token_address and "_" in base_token_id:
                base_token_address = base_token_id.split("_", 1)[-1]
            
            base_token_symbol = base_token_data.get("symbol", "???")
            base_token_name = base_token_data.get("name", "Unknown")
            
            pool_address = attrs.get("address", "")
            
            # Parse creation time
            created_at_str = attrs.get("pool_created_at")
            created_at = None
            age_hours = 999
            
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    age_hours = (datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600
                except:
                    pass
            
            # Get price changes
            price_change = attrs.get("price_change_percentage", {})
            volume = attrs.get("volume_usd", {})
            
            return {
                "pool_address": pool_address,
                "name": attrs.get("name", "Unknown"),
                "base_token_address": base_token_address,
                "base_token_symbol": base_token_symbol,
                "base_token_name": base_token_name,
                "price_usd": float(attrs.get("base_token_price_usd") or 0) if attrs.get("base_token_price_usd") else None,
                "price_change_24h": float(price_change.get("h24") or 0) if price_change.get("h24") else None,
                "price_change_1h": float(price_change.get("h1") or 0) if price_change.get("h1") else None,
                "volume_24h": float(volume.get("h24") or 0) if volume.get("h24") else None,
                "liquidity_usd": float(attrs.get("reserve_in_usd") or 0) if attrs.get("reserve_in_usd") else None,
                "fdv_usd": float(attrs.get("fdv_usd") or 0) if attrs.get("fdv_usd") else None,
                "created_at": created_at,
                "age_hours": age_hours,
                "dex_name": attrs.get("dex_id", "unknown"),
                "chain": chain,
                "is_boosted": base_token_address.lower() in boosted_tokens if base_token_address else False,
                "image_url": base_token_data.get("image_url"),
            }
            
        except Exception as e:
            logger.warning("parse_pool_error", error=str(e))
            return None
    
    async def get_new_pairs(
        self,
        chains: List[str] = None,
        min_holders: int = 50,
        max_top_10_percent: float = 40.0,
        max_age_hours: int = 24,
        require_boosted: bool = False,
        min_liquidity: float = 1000,
        limit: int = 50,
        force_refresh: bool = False,
    ) -> List[NewPairToken]:
        """
        Fetch new token pairs with filtering.
        
        Args:
            chains: Chains to search (default: solana, base, bsc)
            min_holders: Minimum number of holders (default: 50)
            max_top_10_percent: Max % held by top 10 wallets (default: 40%)
            max_age_hours: Max age in hours (default: 24)
            require_boosted: Only show dex-paid tokens
            min_liquidity: Minimum liquidity in USD
            limit: Max results to return
            force_refresh: Bypass cache
        
        Returns:
            List of new pairs matching criteria
        """
        global _new_pairs_cache, _cache_time
        
        # Check cache
        if not force_refresh and _cache_time and datetime.utcnow() - _cache_time < CACHE_DURATION:
            if _new_pairs_cache:
                logger.info("new_pairs_cache_hit", count=len(_new_pairs_cache))
                return [NewPairToken(**p) for p in _new_pairs_cache[:limit]]
        
        if chains is None:
            chains = ["solana", "base", "bsc"]
        
        # Fetch boosted tokens first
        boosted_tokens = await self._fetch_boosted_tokens()
        self._boosted_tokens = boosted_tokens
        logger.info("fetched_boosted_tokens", count=len(boosted_tokens))
        
        all_pairs = []
        
        # Fetch new pools from each chain using GeckoTerminal
        for chain in chains:
            pools = await self._fetch_new_pools(chain)
            logger.info("gecko_pools_raw", chain=chain, count=len(pools))
            
            for pool in pools:
                parsed = self._parse_pool(pool, chain, boosted_tokens)
                if not parsed:
                    continue
                
                # Filter by age
                if parsed["age_hours"] > max_age_hours:
                    continue
                
                # Filter by liquidity
                if parsed.get("liquidity_usd") and parsed["liquidity_usd"] < min_liquidity:
                    continue
                
                # Filter by boosted if required
                if require_boosted and not parsed["is_boosted"]:
                    continue
                
                all_pairs.append(parsed)
            
            await asyncio.sleep(0.2)  # Rate limiting
        
        logger.info("pre_holder_filter", count=len(all_pairs))
        
        # If GeckoTerminal returns nothing or few results, try migrated tokens from DexScreener
        # Migrated tokens (pump.fun → PumpSwap) are what Telegram actually discusses
        if len(all_pairs) < 10:
            logger.info("trying_migrated_tokens")
            migrated = await self._fetch_migrated_tokens(chains, boosted_tokens, max_age_hours, min_liquidity)
            if migrated:
                # Add migrated tokens to the pool
                existing_addresses = {p.get("base_token_address", "").lower() for p in all_pairs}
                for m in migrated:
                    if m.get("base_token_address", "").lower() not in existing_addresses:
                        all_pairs.append(m)
                logger.info("added_migrated_tokens", count=len(migrated))
        
        # If still nothing, try general DexScreener fallback
        if not all_pairs:
            logger.warning("gecko_empty_trying_dexscreener")
            all_pairs = await self._fetch_from_dexscreener(chains, boosted_tokens, max_age_hours, min_liquidity)
        
        # Now fetch holder info for each token and filter
        filtered_pairs = []
        skipped_no_address = 0
        skipped_holder_count = 0
        skipped_top_10 = 0
        skipped_no_info = 0
        
        for pair in all_pairs[:100]:  # Limit API calls
            token_address = pair.get("base_token_address")
            chain = pair.get("chain")
            
            if not token_address:
                skipped_no_address += 1
                continue
            
            # Fetch holder info
            token_info = await self._fetch_token_info(chain, token_address)
            
            # Default values if no holder info
            holder_count = 0
            top_10 = 50.0  # Assume 50% if unknown
            top_11_30 = 20.0
            top_31_50 = 15.0
            rest = 15.0
            
            if token_info:
                holders = token_info.get("holders") or {}
                holder_count = holders.get("count") or 0
                
                # Get distribution percentages
                distribution = holders.get("distribution_percentage") or {}
                if distribution:
                    top_10 = float(distribution.get("top_10") or 50)
                    top_11_30 = float(distribution.get("11_to_30") or distribution.get("11_30") or 20)
                    top_31_50 = float(distribution.get("31_to_50") or distribution.get("31_50") or 15)
                    rest = float(distribution.get("rest") or 15)
                
                logger.info(
                    "holder_info",
                    symbol=pair.get("base_token_symbol"),
                    holders=holder_count,
                    top_10=top_10
                )
            else:
                skipped_no_info += 1
                logger.warning("no_token_info", address=token_address[:10], chain=chain)
            
            # Apply holder filters (but allow if we have data)
            if holder_count > 0:  # Only filter if we have data
                if holder_count < min_holders:
                    skipped_holder_count += 1
                    continue
                
                if top_10 > max_top_10_percent:
                    skipped_top_10 += 1
                    continue
            elif holder_count == 0 and not token_info:
                # No holder data available, include anyway if it passes other filters
                # This ensures we still show something even if holder API fails
                pass
            
            # Create the token object
            # Determine launchpad
            token_name = pair.get("base_token_name", "")
            token_symbol = pair.get("base_token_symbol", "")
            dex_name = pair.get("dex_name", "")
            launchpad = pair.get("launchpad") or self._get_launchpad(token_address, token_name, token_symbol, dex_name)
            
            new_pair = NewPairToken(
                address=token_address,
                symbol=token_symbol or "???",
                name=token_name or "Unknown",
                chain=chain,
                price_usd=pair.get("price_usd"),
                price_change_24h=pair.get("price_change_24h"),
                price_change_1h=pair.get("price_change_1h"),
                volume_24h=pair.get("volume_24h"),
                liquidity_usd=pair.get("liquidity_usd"),
                market_cap=pair.get("market_cap") or pair.get("fdv_usd"),
                holder_count=holder_count,
                top_10_percent=top_10,
                top_11_30_percent=top_11_30,
                top_31_50_percent=top_31_50,
                rest_percent=rest,
                pool_created_at=pair.get("created_at"),
                age_hours=pair.get("age_hours", 0),
                dex_name=dex_name or "unknown",
                is_boosted=pair.get("is_boosted", False),
                is_pump_fun=pair.get("is_pump_fun", self._is_pump_fun_token(token_address)),
                is_migrated=pair.get("is_migrated", False),
                launchpad=launchpad,
                image_url=pair.get("image_url") or (token_info.get("image_url") if token_info else None),
                dexscreener_url=f"https://dexscreener.com/{chain}/{token_address}",
                gecko_terminal_url=f"https://www.geckoterminal.com/{self._gecko_chain_id(chain)}/pools/{pair.get('pool_address', token_address)}",
            )
            
            filtered_pairs.append(new_pair)
            
            await asyncio.sleep(0.1)  # Rate limiting for token info calls
        
        logger.info(
            "filtering_stats",
            total=len(all_pairs),
            skipped_no_address=skipped_no_address,
            skipped_holder_count=skipped_holder_count,
            skipped_top_10=skipped_top_10,
            skipped_no_info=skipped_no_info,
            passed=len(filtered_pairs)
        )
        
        # Sort by holder count (more holders = more legitimate), then by age (newer first)
        filtered_pairs.sort(key=lambda x: (x.holder_count, -x.age_hours), reverse=True)
        
        # If we got no results with strict filters, try again with relaxed filters
        if not filtered_pairs and all_pairs:
            logger.warning("no_results_with_filters_relaxing")
            # Return all pairs that passed age/liquidity filters (ignore holder filters)
            for pair in all_pairs[:50]:
                token_address = pair.get("base_token_address")
                if not token_address:
                    continue
                
                chain = pair.get("chain", "solana")
                token_name = pair.get("base_token_name", "")
                token_symbol = pair.get("base_token_symbol", "")
                dex_name = pair.get("dex_name", "")
                launchpad = pair.get("launchpad") or self._get_launchpad(token_address, token_name, token_symbol, dex_name)
                
                new_pair = NewPairToken(
                    address=token_address,
                    symbol=token_symbol or "???",
                    name=token_name or "Unknown",
                    chain=chain,
                    price_usd=pair.get("price_usd"),
                    price_change_24h=pair.get("price_change_24h"),
                    price_change_1h=pair.get("price_change_1h"),
                    volume_24h=pair.get("volume_24h"),
                    liquidity_usd=pair.get("liquidity_usd"),
                    market_cap=pair.get("market_cap") or pair.get("fdv_usd"),
                    holder_count=0,  # Unknown
                    top_10_percent=50.0,  # Unknown - assume middle
                    top_11_30_percent=20.0,
                    top_31_50_percent=15.0,
                    rest_percent=15.0,
                    pool_created_at=pair.get("created_at"),
                    age_hours=pair.get("age_hours", 0),
                    dex_name=dex_name or "unknown",
                    is_boosted=pair.get("is_boosted", False),
                    is_pump_fun=pair.get("is_pump_fun", self._is_pump_fun_token(token_address)),
                    is_migrated=pair.get("is_migrated", False),
                    launchpad=launchpad,
                    image_url=pair.get("image_url"),
                    dexscreener_url=f"https://dexscreener.com/{chain}/{token_address}",
                    gecko_terminal_url=f"https://www.geckoterminal.com/{self._gecko_chain_id(chain)}/pools/{pair.get('pool_address', token_address)}",
                )
                filtered_pairs.append(new_pair)
        
        # Cache results
        _new_pairs_cache = [p.to_dict() for p in filtered_pairs[:limit]]
        _cache_time = datetime.utcnow()
        
        logger.info("new_pairs_filtered", count=len(filtered_pairs))
        
        return filtered_pairs[:limit]
    
    async def get_token_info(self, address: str, chain: str) -> Optional[NewPairToken]:
        """Get info for a specific token"""
        token_info = await self._fetch_token_info(chain, address)
        
        if not token_info:
            return None
        
        holders = token_info.get("holders", {})
        distribution = holders.get("distribution_percentage", {})
        
        return NewPairToken(
            address=address,
            symbol=token_info.get("symbol", "???"),
            name=token_info.get("name", "Unknown"),
            chain=chain,
            price_usd=None,
            price_change_24h=None,
            price_change_1h=None,
            volume_24h=None,
            liquidity_usd=None,
            market_cap=None,
            holder_count=holders.get("count", 0) or 0,
            top_10_percent=float(distribution.get("top_10", 0) or 0),
            top_11_30_percent=float(distribution.get("11_to_30", 0) or 0),
            top_31_50_percent=float(distribution.get("31_to_50", 0) or 0),
            rest_percent=float(distribution.get("rest", 0) or 0),
            pool_created_at=None,
            age_hours=0,
            dex_name="unknown",
            is_boosted=address.lower() in self._boosted_tokens,
            image_url=token_info.get("image_url"),
            dexscreener_url=f"https://dexscreener.com/{chain}/{address}",
            gecko_terminal_url=f"https://www.geckoterminal.com/{self._gecko_chain_id(chain)}/tokens/{address}",
        )


# Singleton instance
new_pairs_service = NewPairsService()
