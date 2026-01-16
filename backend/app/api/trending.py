"""
Trending API - DexScreener trending coins + Telegram mentions

This is the main feed endpoint. Only shows coins that are:
1. Trending on DexScreener (top 100 in last 6 hours)
2. Have at least ONE mention in Telegram chats (no mentions = hidden)
3. Cross-referenced with KOL wallet activity
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.telegram import TelegramAccount, TelegramSource
from app.services.trending.dexscreener_trending import trending_service
from app.services.trending.mention_scanner import mention_scanner, TokenMentionSummary
from app.services.trending.kol_wallets import kol_wallet_service
from app.services.trending.new_pairs_service import new_pairs_service, NewPairToken

logger = structlog.get_logger()

router = APIRouter()


class KOLHolder(BaseModel):
    """A KOL who holds or mentioned this token"""
    address: str
    name: str
    twitter: Optional[str]
    tier: str  # mega, large, medium, small


class TrendingTokenResponse(BaseModel):
    """A trending token with mention data"""
    # Token info (from DexScreener)
    address: str
    symbol: str
    name: str
    chain: str
    price_usd: Optional[float]
    price_change_24h: Optional[float]
    price_change_6h: Optional[float]
    price_change_1h: Optional[float]
    volume_24h: Optional[float]
    volume_6h: Optional[float]
    market_cap: Optional[float]
    liquidity: Optional[float]
    image_url: Optional[str]
    dexscreener_url: str
    
    # Mention data (from Telegram)
    total_mentions: int
    human_discussions: int
    sources: List[str]
    sentiment: dict
    
    # KOL data
    kol_holders: List[KOLHolder]
    kol_count: int
    
    # Top discussion messages (human only)
    top_messages: List[dict]


class TrendingFeedResponse(BaseModel):
    """Response for the trending feed"""
    tokens: List[TrendingTokenResponse]
    total_tokens: int
    tokens_with_mentions: int  # How many had mentions
    tokens_hidden: int  # How many were hidden (no mentions)
    last_updated: str
    messages_scanned: int


class TokenDetailResponse(BaseModel):
    """Detailed view of a token with all mentions"""
    # Token info
    address: str
    symbol: str
    name: str
    chain: str
    price_usd: Optional[float]
    price_change_24h: Optional[float]
    price_change_6h: Optional[float]
    volume_24h: Optional[float]
    volume_6h: Optional[float]
    market_cap: Optional[float]
    dexscreener_url: str
    
    # Mention data
    total_mentions: int
    human_discussions: int
    sources: List[str]
    sentiment: dict
    
    # KOL data
    kol_holders: List[KOLHolder]
    kol_count: int
    
    # All human discussion messages
    messages: List[dict]


class NewPairResponse(BaseModel):
    """A new token pair with holder data"""
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
    
    # Holder data
    holder_count: int
    top_10_percent: float
    top_11_30_percent: float
    top_31_50_percent: float
    rest_percent: float
    
    # Metadata
    age_hours: float
    dex_name: str
    is_boosted: bool
    is_pump_fun: bool  # From pump.fun
    is_migrated: bool  # Migrated to PumpSwap/Raydium
    
    image_url: Optional[str]
    dexscreener_url: str
    gecko_terminal_url: str
    
    # Telegram mentions
    total_mentions: int
    human_discussions: int
    top_messages: List[dict]
    kol_count: int


class NewPairsFeedResponse(BaseModel):
    """Response for new pairs feed"""
    pairs: List[NewPairResponse]
    total_pairs: int
    filters_applied: dict
    last_updated: str
    messages_scanned: int


# In-memory message cache (per source)
_message_cache: dict = {}
_cache_time: Optional[datetime] = None


@router.get("/feed", response_model=TrendingFeedResponse)
async def get_trending_feed(
    limit: int = Query(50, ge=1, le=100),
    chain: Optional[str] = Query(None, description="Filter by chain"),
    include_no_mentions: bool = Query(False, description="Include tokens with no mentions"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get trending tokens feed (last 6 hours).
    
    Returns top trending tokens from DexScreener, cross-referenced with
    what Telegram chats are saying about them.
    
    By default, tokens with NO mentions are hidden.
    """
    global _message_cache, _cache_time
    
    # 1. Get trending tokens from DexScreener (last 6 hours)
    chains = [chain] if chain else ["solana", "base", "bsc"]
    trending_tokens = await trending_service.get_trending_tokens(
        chains=chains,
        limit=limit * 2,  # Fetch more since we'll filter
        hours=6,
    )
    
    if not trending_tokens:
        return TrendingFeedResponse(
            tokens=[],
            total_tokens=0,
            tokens_with_mentions=0,
            tokens_hidden=0,
            last_updated=datetime.utcnow().isoformat(),
            messages_scanned=0,
        )
    
    # 2. Get all messages from Telegram sources
    messages = await _get_all_messages(current_user.id, db)
    
    # 3. Scan messages for each trending token
    token_dicts = [
        {"address": t.address, "symbol": t.symbol, "chain": t.chain}
        for t in trending_tokens
    ]
    mention_results = mention_scanner.scan_messages_for_tokens(messages, token_dicts)
    
    # 4. Check for KOL mentions
    kol_results = {}
    for token in trending_tokens:
        # Get messages that mention this token
        token_messages = []
        if token.address in mention_results:
            mentions = mention_results[token.address]
            token_messages = [{"text": m.text} for m in mentions.mentions]
        
        kol_summary = await kol_wallet_service.check_kol_activity(
            token.address, token_messages
        )
        kol_results[token.address] = kol_summary
    
    # 5. Build response - ONLY include tokens with mentions (unless include_no_mentions=True)
    response_tokens = []
    tokens_hidden = 0
    
    for token in trending_tokens:
        mentions = mention_results.get(token.address)
        kol_data = kol_results.get(token.address)
        
        total_mentions = mentions.total_mentions if mentions else 0
        
        # Skip tokens with no mentions (unless explicitly requested)
        if not include_no_mentions and total_mentions == 0:
            tokens_hidden += 1
            continue
        
        # Get top human discussion messages
        top_messages = []
        if mentions:
            human_msgs = [m for m in mentions.mentions if m.is_human_discussion]
            top_messages = [m.to_dict() for m in human_msgs[:3]]
        
        # Format KOL holders
        kol_holders = []
        if kol_data and kol_data.named_holders:
            kol_holders = [
                KOLHolder(
                    address=h["address"],
                    name=h["name"],
                    twitter=h.get("twitter"),
                    tier=h["tier"],
                )
                for h in kol_data.named_holders
            ]
        
        response_tokens.append(TrendingTokenResponse(
            address=token.address,
            symbol=token.symbol,
            name=token.name,
            chain=token.chain,
            price_usd=token.price_usd,
            price_change_24h=token.price_change_24h,
            price_change_6h=token.price_change_6h,
            price_change_1h=token.price_change_1h,
            volume_24h=token.volume_24h,
            volume_6h=token.volume_6h,
            market_cap=token.market_cap,
            liquidity=token.liquidity,
            image_url=token.image_url,
            dexscreener_url=token.dexscreener_url,
            total_mentions=total_mentions,
            human_discussions=mentions.human_discussions if mentions else 0,
            sources=mentions.sources if mentions else [],
            sentiment=mentions.to_dict()["sentiment"] if mentions else {"bullish": 0, "bearish": 0, "neutral": 0},
            kol_holders=kol_holders,
            kol_count=kol_data.total_kol_holders if kol_data else 0,
            top_messages=top_messages,
        ))
    
    # Sort by mentions (tokens being discussed first)
    response_tokens.sort(key=lambda t: (t.total_mentions, t.human_discussions), reverse=True)
    
    # Limit to requested amount
    response_tokens = response_tokens[:limit]
    
    return TrendingFeedResponse(
        tokens=response_tokens,
        total_tokens=len(response_tokens),
        tokens_with_mentions=len(response_tokens),
        tokens_hidden=tokens_hidden,
        last_updated=datetime.utcnow().isoformat(),
        messages_scanned=len(messages),
    )


@router.get("/token/{chain}/{address}", response_model=TokenDetailResponse)
async def get_token_detail(
    chain: str,
    address: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed view of a specific token.
    
    Shows:
    - Token info from DexScreener
    - Total mentions count (how many times CA or symbol was mentioned)
    - All human discussion messages
    - KOL wallets that hold or mentioned this token
    - "No mentions" if not discussed
    """
    # 1. Get token info from DexScreener
    token = await trending_service.get_token_info(address, chain)
    
    if not token:
        token_symbol = "???"
        token_name = "Unknown Token"
    else:
        token_symbol = token.symbol
        token_name = token.name
    
    # 2. Get all messages and scan for this token
    messages = await _get_all_messages(current_user.id, db)
    mentions = mention_scanner.scan_messages_for_token(
        messages=messages,
        address=address,
        symbol=token_symbol if token else "",
        chain=chain,
    )
    
    # 3. Get only human discussion messages
    human_messages = [m.to_dict() for m in mentions.mentions if m.is_human_discussion]
    
    # 4. Check for KOL activity
    token_messages = [{"text": m.text} for m in mentions.mentions]
    kol_data = await kol_wallet_service.check_kol_activity(address, token_messages)
    
    # Format KOL holders
    kol_holders = []
    if kol_data and kol_data.named_holders:
        kol_holders = [
            KOLHolder(
                address=h["address"],
                name=h["name"],
                twitter=h.get("twitter"),
                tier=h["tier"],
            )
            for h in kol_data.named_holders
        ]
    
    return TokenDetailResponse(
        address=address,
        symbol=token.symbol if token else token_symbol,
        name=token.name if token else token_name,
        chain=chain,
        price_usd=token.price_usd if token else None,
        price_change_24h=token.price_change_24h if token else None,
        price_change_6h=token.price_change_6h if token else None,
        volume_24h=token.volume_24h if token else None,
        volume_6h=token.volume_6h if token else None,
        market_cap=token.market_cap if token else None,
        dexscreener_url=token.dexscreener_url if token else f"https://dexscreener.com/{chain}/{address}",
        total_mentions=mentions.total_mentions,
        human_discussions=mentions.human_discussions,
        sources=mentions.sources,
        sentiment=mentions.to_dict()["sentiment"],
        kol_holders=kol_holders,
        kol_count=kol_data.total_kol_holders if kol_data else 0,
        messages=human_messages,
    )


@router.post("/refresh")
async def refresh_messages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh Telegram messages cache.
    Fetches latest messages from all active sources.
    """
    from app.services.telegram.client import telegram_service
    
    # Get user's telegram accounts
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.user_id == current_user.id,
            TelegramAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    
    if not accounts:
        return {"status": "no_accounts", "messages": 0}
    
    total_messages = 0
    
    for account in accounts:
        # Get active sources
        result = await db.execute(
            select(TelegramSource).where(
                TelegramSource.account_id == account.id,
                TelegramSource.is_active == True,
            )
        )
        sources = result.scalars().all()
        
        if not sources:
            continue
        
        # Connect to Telegram
        if account.session_name not in telegram_service._active_clients:
            connected = await telegram_service.connect_account(
                session_name=account.session_name,
                api_id_encrypted=account.api_id_encrypted,
                api_hash_encrypted=account.api_hash_encrypted,
                session_string_encrypted=account.session_string_encrypted,
            )
            if not connected:
                continue
        
        client = telegram_service._active_clients.get(account.session_name)
        if not client:
            continue
        
        # Fetch messages from each source
        for source in sources:
            try:
                try:
                    entity_id = int(source.telegram_id)
                    entity = await client.get_entity(entity_id)
                except ValueError:
                    entity = await client.get_entity(source.telegram_id)
                
                messages = await client.get_messages(entity, limit=100)
                
                # Cache messages
                source_key = f"{current_user.id}:{source.telegram_id}"
                _message_cache[source_key] = [
                    {
                        "text": msg.text,
                        "source_name": source.name,
                        "source_id": source.telegram_id,
                        "message_id": msg.id,
                        "timestamp": msg.date.isoformat() if msg.date else None,
                    }
                    for msg in messages
                    if msg.text
                ]
                
                total_messages += len(messages)
                
            except Exception as e:
                logger.error("refresh_source_error", source=source.name, error=str(e))
    
    global _cache_time
    _cache_time = datetime.utcnow()
    
    return {
        "status": "ok",
        "messages": total_messages,
        "refreshed_at": _cache_time.isoformat(),
    }


async def _get_all_messages(user_id: str, db: AsyncSession) -> List[dict]:
    """Get all cached messages for a user's sources"""
    # Get user's sources
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.user_id == user_id,
            TelegramAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    
    all_messages = []
    
    for account in accounts:
        result = await db.execute(
            select(TelegramSource).where(
                TelegramSource.account_id == account.id,
                TelegramSource.is_active == True,
            )
        )
        sources = result.scalars().all()
        
        for source in sources:
            source_key = f"{user_id}:{source.telegram_id}"
            if source_key in _message_cache:
                all_messages.extend(_message_cache[source_key])
    
    return all_messages


# ============================================================================
# NEW PAIRS ENDPOINT - Uses GeckoTerminal for holder filtering
# ============================================================================

@router.get("/new-pairs", response_model=NewPairsFeedResponse)
async def get_new_pairs_feed(
    min_holders: int = Query(50, ge=1, description="Minimum number of holders"),
    max_top_10_percent: float = Query(40.0, ge=0, le=100, description="Max % held by top 10 wallets"),
    max_age_hours: int = Query(24, ge=1, le=168, description="Max age in hours"),
    require_boosted: bool = Query(False, description="Only show dex-paid tokens"),
    min_liquidity: float = Query(1000, ge=0, description="Minimum liquidity in USD"),
    chain: Optional[str] = Query(None, description="Filter by chain"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get new token pairs with advanced filtering.
    
    This uses GeckoTerminal API for:
    - New pools (launched in last 24h)
    - Holder counts and distribution
    
    Filters:
    - min_holders: Minimum 50 holders (default)
    - max_top_10_percent: Top 10 wallets hold less than 40% (default)
    - max_age_hours: Launched in last 24 hours (default)
    - require_boosted: Only dex-paid tokens (optional)
    - min_liquidity: Minimum $1000 liquidity (default)
    """
    chains = [chain] if chain else ["solana", "base", "bsc"]
    
    # 1. Get new pairs from GeckoTerminal with holder filtering
    new_pairs = await new_pairs_service.get_new_pairs(
        chains=chains,
        min_holders=min_holders,
        max_top_10_percent=max_top_10_percent,
        max_age_hours=max_age_hours,
        require_boosted=require_boosted,
        min_liquidity=min_liquidity,
        limit=limit,
    )
    
    if not new_pairs:
        return NewPairsFeedResponse(
            pairs=[],
            total_pairs=0,
            filters_applied={
                "min_holders": min_holders,
                "max_top_10_percent": max_top_10_percent,
                "max_age_hours": max_age_hours,
                "require_boosted": require_boosted,
                "min_liquidity": min_liquidity,
            },
            last_updated=datetime.utcnow().isoformat(),
            messages_scanned=0,
        )
    
    # 2. Get Telegram messages and scan for mentions
    messages = await _get_all_messages(current_user.id, db)
    
    # 3. Scan messages for each new pair
    token_dicts = [
        {"address": p.address, "symbol": p.symbol, "chain": p.chain}
        for p in new_pairs
    ]
    mention_results = mention_scanner.scan_messages_for_tokens(messages, token_dicts)
    
    # 4. Check for KOL activity
    kol_results = {}
    for pair in new_pairs:
        token_messages = []
        if pair.address in mention_results:
            mentions = mention_results[pair.address]
            token_messages = [{"text": m.text} for m in mentions.mentions]
        
        kol_summary = await kol_wallet_service.check_kol_activity(
            pair.address, token_messages
        )
        kol_results[pair.address] = kol_summary
    
    # 5. Build response
    response_pairs = []
    
    for pair in new_pairs:
        mentions = mention_results.get(pair.address)
        kol_data = kol_results.get(pair.address)
        
        # Get top human discussion messages
        top_messages = []
        if mentions:
            human_msgs = [m for m in mentions.mentions if m.is_human_discussion]
            top_messages = [m.to_dict() for m in human_msgs[:3]]
        
        response_pairs.append(NewPairResponse(
            address=pair.address,
            symbol=pair.symbol,
            name=pair.name,
            chain=pair.chain,
            price_usd=pair.price_usd,
            price_change_24h=pair.price_change_24h,
            price_change_1h=pair.price_change_1h,
            volume_24h=pair.volume_24h,
            liquidity_usd=pair.liquidity_usd,
            market_cap=pair.market_cap,
            holder_count=pair.holder_count,
            top_10_percent=pair.top_10_percent,
            top_11_30_percent=pair.top_11_30_percent,
            top_31_50_percent=pair.top_31_50_percent,
            rest_percent=pair.rest_percent,
            age_hours=pair.age_hours,
            dex_name=pair.dex_name,
            is_boosted=pair.is_boosted,
            is_pump_fun=pair.is_pump_fun,
            is_migrated=pair.is_migrated,
            image_url=pair.image_url,
            dexscreener_url=pair.dexscreener_url,
            gecko_terminal_url=pair.gecko_terminal_url,
            total_mentions=mentions.total_mentions if mentions else 0,
            human_discussions=mentions.human_discussions if mentions else 0,
            top_messages=top_messages,
            kol_count=kol_data.total_kol_holders if kol_data else 0,
        ))
    
    # Sort by holder count (more holders = more legitimate)
    response_pairs.sort(key=lambda p: p.holder_count, reverse=True)
    
    return NewPairsFeedResponse(
        pairs=response_pairs,
        total_pairs=len(response_pairs),
        filters_applied={
            "min_holders": min_holders,
            "max_top_10_percent": max_top_10_percent,
            "max_age_hours": max_age_hours,
            "require_boosted": require_boosted,
            "min_liquidity": min_liquidity,
        },
        last_updated=datetime.utcnow().isoformat(),
        messages_scanned=len(messages),
    )
