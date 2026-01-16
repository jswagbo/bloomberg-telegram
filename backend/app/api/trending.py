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
from app.services.trending.chat_summarizer import chat_summarizer, TokenChatAnalysis
from app.services.trending.telegram_token_scanner import telegram_token_scanner
from app.services.trending.chat_first_scanner import chat_first_scanner
from app.services.trending.contextual_scanner import contextual_scanner

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


class ChatSummaryResponse(BaseModel):
    """Summary of what one chat says about a token"""
    chat_name: str
    summary: str
    sentiment: str  # bullish, bearish, neutral
    mention_count: int


class NewPairResponse(BaseModel):
    """A new token pair with holder data and chat analysis"""
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
    launchpad: str  # "pump.fun", "bags.fm", "bonk", or ""
    
    image_url: Optional[str]
    dexscreener_url: str
    gecko_terminal_url: str
    
    # Chat analysis (NEW)
    total_scans: int  # Number of chats that scanned/mentioned this token
    total_mentions: int  # Total mentions across all chats
    consensus_summary: str  # What the collective chats say
    overall_sentiment: str  # bullish, bearish, neutral
    chat_summaries: List[ChatSummaryResponse]  # Per-chat summaries
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
_last_scan_time: Optional[datetime] = None  # Track when Telegram was actually scanned


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
    
    logger.info("refresh_messages_start", user_id=str(current_user.id))
    
    # Get user's telegram accounts
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.user_id == current_user.id,
            TelegramAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    
    logger.info("refresh_accounts_found", count=len(accounts))
    
    # Always update scan time when refresh is called
    global _last_scan_time
    _last_scan_time = datetime.utcnow()
    
    if not accounts:
        logger.warning("refresh_no_accounts", user_id=str(current_user.id))
        return {
            "status": "no_accounts", 
            "messages": 0, 
            "accounts": 0, 
            "sources": 0,
            "refreshed_at": _last_scan_time.isoformat(),
        }
    
    total_messages = 0
    total_sources = 0
    connected_accounts = 0
    errors = []
    
    for account in accounts:
        # Get active sources
        result = await db.execute(
            select(TelegramSource).where(
                TelegramSource.account_id == account.id,
                TelegramSource.is_active == True,
            )
        )
        sources = result.scalars().all()
        
        logger.info("refresh_account_sources", 
                    account=account.session_name, 
                    sources=len(sources))
        
        if not sources:
            continue
        
        # Connect to Telegram
        if account.session_name not in telegram_service._active_clients:
            logger.info("refresh_connecting", account=account.session_name)
            connected = await telegram_service.connect_account(
                session_name=account.session_name,
                api_id_encrypted=account.api_id_encrypted,
                api_hash_encrypted=account.api_hash_encrypted,
                session_string_encrypted=account.session_string_encrypted,
            )
            if not connected:
                errors.append(f"Failed to connect account {account.session_name}")
                logger.error("refresh_connect_failed", account=account.session_name)
                continue
        
        client = telegram_service._active_clients.get(account.session_name)
        if not client:
            errors.append(f"No client for {account.session_name}")
            continue
        
        connected_accounts += 1
        
        # Fetch messages from each source
        for source in sources:
            try:
                try:
                    entity_id = int(source.telegram_id)
                    entity = await client.get_entity(entity_id)
                except ValueError:
                    entity = await client.get_entity(source.telegram_id)
                
                messages = await client.get_messages(entity, limit=500)  # Fetch more messages
                
                # Cache messages
                source_key = f"{current_user.id}:{source.telegram_id}"
                cached_msgs = [
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
                _message_cache[source_key] = cached_msgs
                
                total_messages += len(cached_msgs)
                total_sources += 1
                
                logger.info("refresh_source_success", 
                            source=source.name, 
                            messages=len(cached_msgs))
                
            except Exception as e:
                error_msg = f"Error in {source.name}: {str(e)}"
                errors.append(error_msg)
                logger.error("refresh_source_error", source=source.name, error=str(e))
    
    global _cache_time
    _cache_time = datetime.utcnow()
    _last_scan_time = _cache_time  # Already declared global above
    
    logger.info("refresh_complete", 
                messages=total_messages, 
                sources=total_sources,
                accounts=connected_accounts,
                errors=len(errors))
    
    return {
        "status": "ok" if total_messages > 0 else "no_messages",
        "messages": total_messages,
        "sources": total_sources,
        "accounts": connected_accounts,
        "errors": errors[:5] if errors else [],  # Return first 5 errors
        "refreshed_at": _cache_time.isoformat(),
    }


async def _get_all_messages(
    user_id: str, 
    db: AsyncSession, 
    lookback_hours: int = 72
) -> List[dict]:
    """
    Get all cached messages for a user's sources.
    
    Args:
        user_id: The user's ID
        db: Database session
        lookback_hours: Only include messages from the last N hours (default 72)
    
    Returns:
        List of message dictionaries
    """
    from datetime import timedelta, timezone
    
    # Get user's sources
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.user_id == user_id,
            TelegramAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    
    all_messages = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    
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
                # Filter by time
                for msg in _message_cache[source_key]:
                    ts_str = msg.get("timestamp")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts >= cutoff_time:
                                all_messages.append(msg)
                        except:
                            all_messages.append(msg)  # Include if can't parse
                    else:
                        all_messages.append(msg)  # Include if no timestamp
    
    logger.info("messages_retrieved", 
                total=len(all_messages), 
                lookback_hours=lookback_hours,
                accounts=len(accounts))
    
    return all_messages


# ============================================================================
# NEW PAIRS ENDPOINT - Uses GeckoTerminal for holder filtering
# ============================================================================

@router.get("/new-pairs", response_model=NewPairsFeedResponse)
async def get_new_pairs_feed(
    min_holders: int = Query(25, ge=1, description="Minimum number of holders"),
    max_top_10_percent: float = Query(50.0, ge=0, le=100, description="Max % held by top 10 wallets"),
    max_age_hours: int = Query(72, ge=1, le=168, description="Max age in hours"),
    require_boosted: bool = Query(False, description="Only show dex-paid tokens"),
    min_liquidity: float = Query(500, ge=0, description="Minimum liquidity in USD"),
    chain: Optional[str] = Query(None, description="Filter by chain"),
    include_no_mentions: bool = Query(False, description="Include tokens with no Telegram mentions"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get new token pairs with advanced filtering.
    
    Focuses on MIGRATED tokens from pump.fun, bags.fm, bonk.
    
    ONLY shows tokens that have been mentioned in Telegram (unless include_no_mentions=true).
    Searches for: address, ticker, name, and common misspellings.
    Looks back 72 hours in Telegram messages.
    
    Filters:
    - min_holders: Minimum 25 holders (default)
    - max_top_10_percent: Top 10 wallets hold less than 50% (default)
    - max_age_hours: Launched in last 72 hours (default)
    - require_boosted: Only dex-paid tokens (optional)
    - min_liquidity: Minimum $500 liquidity (default)
    """
    chains = [chain] if chain else ["solana"]  # Focus on Solana for launchpad tokens
    
    # 1. Get new pairs (migrated from launchpads)
    new_pairs = await new_pairs_service.get_new_pairs(
        chains=chains,
        min_holders=min_holders,
        max_top_10_percent=max_top_10_percent,
        max_age_hours=max_age_hours,
        require_boosted=require_boosted,
        min_liquidity=min_liquidity,
        limit=limit * 2,  # Fetch more since we'll filter by mentions
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
            last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
            messages_scanned=0,
        )
    
    # 2. Get Telegram messages (last 72 hours)
    messages = await _get_all_messages(current_user.id, db, lookback_hours=72)
    
    # 3. Analyze chat discussions for each token (summaries, not individual messages)
    token_dicts = [
        {"address": p.address, "symbol": p.symbol, "name": p.name, "chain": p.chain}
        for p in new_pairs
    ]
    chat_analyses = await chat_summarizer.analyze_tokens_batch(messages, token_dicts)
    
    # 4. Filter to only tokens WITH scans (unless include_no_mentions is true)
    pairs_with_scans = []
    pairs_without_scans = 0
    
    for pair in new_pairs:
        analysis = chat_analyses.get(pair.address)
        if analysis and analysis.total_scans > 0:
            pairs_with_scans.append(pair)
        else:
            pairs_without_scans += 1
            if include_no_mentions:
                pairs_with_scans.append(pair)
    
    logger.info(
        "scan_filtering",
        total_pairs=len(new_pairs),
        with_scans=len(pairs_with_scans) - (pairs_without_scans if include_no_mentions else 0),
        without_scans=pairs_without_scans,
        showing=len(pairs_with_scans),
    )
    
    # 5. Check for KOL activity
    kol_results = {}
    for pair in pairs_with_scans:
        analysis = chat_analyses.get(pair.address)
        token_messages = []
        if analysis:
            # Extract all message texts for KOL check
            for summary in analysis.chat_summaries:
                token_messages.append({"text": summary.summary})
        
        kol_summary = await kol_wallet_service.check_kol_activity(
            pair.address, token_messages
        )
        kol_results[pair.address] = kol_summary
    
    # 6. Build response with chat summaries
    response_pairs = []
    
    for pair in pairs_with_scans:
        analysis = chat_analyses.get(pair.address)
        kol_data = kol_results.get(pair.address)
        
        # Build chat summaries for response
        chat_summaries = []
        if analysis:
            for cs in analysis.chat_summaries[:5]:  # Top 5 chats
                chat_summaries.append(ChatSummaryResponse(
                    chat_name=cs.chat_name,
                    summary=cs.summary,
                    sentiment=cs.sentiment,
                    mention_count=cs.mention_count,
                ))
        
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
            launchpad=pair.launchpad,
            image_url=pair.image_url,
            dexscreener_url=pair.dexscreener_url,
            gecko_terminal_url=pair.gecko_terminal_url,
            total_scans=analysis.total_scans if analysis else 0,
            total_mentions=analysis.total_mentions if analysis else 0,
            consensus_summary=analysis.consensus_summary if analysis else "No chat data.",
            overall_sentiment=analysis.overall_sentiment if analysis else "neutral",
            chat_summaries=chat_summaries,
            kol_count=kol_data.total_kol_holders if kol_data else 0,
        ))
    
    # Sort by total scans (most chats discussing first), then by holder count
    response_pairs.sort(key=lambda p: (p.total_scans, p.holder_count), reverse=True)
    
    return NewPairsFeedResponse(
        pairs=response_pairs[:limit],
        total_pairs=len(response_pairs),
        filters_applied={
            "min_holders": min_holders,
            "max_top_10_percent": max_top_10_percent,
            "max_age_hours": max_age_hours,
            "require_boosted": require_boosted,
            "min_liquidity": min_liquidity,
            "include_no_mentions": include_no_mentions,
        },
        last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
        messages_scanned=len(messages),
    )


# ============================================================================
# TELEGRAM TOKENS ENDPOINT - Scans Telegram for ALL tokens mentioned
# ============================================================================

class TelegramTokenResponse(BaseModel):
    """A token found in Telegram messages"""
    address: str
    chain: str
    symbol: str
    name: str
    mention_count: int
    chat_count: int
    chats: List[str]
    sample_messages: List[str]
    price_usd: Optional[float]
    market_cap: Optional[float]
    liquidity_usd: Optional[float]
    price_change_24h: Optional[float]
    volume_24h: Optional[float]
    dexscreener_url: str
    image_url: Optional[str]


class TelegramTokensFeedResponse(BaseModel):
    """Response for telegram tokens feed"""
    tokens: List[TelegramTokenResponse]
    total_found: int
    messages_scanned: int
    last_updated: str


@router.get("/telegram-tokens", response_model=TelegramTokensFeedResponse)
async def get_telegram_tokens_feed(
    min_mentions: int = Query(1, ge=1, description="Minimum mentions to show"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Scan Telegram messages and find ALL tokens mentioned.
    
    This is the reverse of the new-pairs endpoint:
    - Instead of finding trending tokens and checking Telegram
    - This finds tokens IN Telegram and enriches with market data
    
    This is what you want if you see tokens in your chats that aren't showing up.
    """
    # 1. Get all messages (last 72 hours)
    messages = await _get_all_messages(current_user.id, db, lookback_hours=72)
    
    if not messages:
        return TelegramTokensFeedResponse(
            tokens=[],
            total_found=0,
            messages_scanned=0,
            last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
        )
    
    # 2. Scan messages for token addresses and enrich
    found_tokens = await telegram_token_scanner.scan_and_enrich(
        messages=messages,
        min_mentions=min_mentions,
        limit=limit,
    )
    
    # 3. Build response
    response_tokens = []
    for token in found_tokens:
        response_tokens.append(TelegramTokenResponse(
            address=token.address,
            chain=token.chain,
            symbol=token.symbol or "???",
            name=token.name or "Unknown Token",
            mention_count=token.mention_count,
            chat_count=len(token.chats),
            chats=list(token.chats)[:5],
            sample_messages=token.sample_messages[:3],
            price_usd=token.price_usd,
            market_cap=token.market_cap,
            liquidity_usd=token.liquidity_usd,
            price_change_24h=token.price_change_24h,
            volume_24h=token.volume_24h,
            dexscreener_url=token.dexscreener_url or f"https://dexscreener.com/search?q={token.address}",
            image_url=token.image_url,
        ))
    
    return TelegramTokensFeedResponse(
        tokens=response_tokens,
        total_found=len(found_tokens),
        messages_scanned=len(messages),
        last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
    )


# ============================================================================
# CHAT-FIRST FEED - Finds tokens IN chats, then enriches with market data
# ============================================================================

class ChatDiscoveredTokenResponse(BaseModel):
    """A token discovered in chat messages"""
    address: str
    chain: str
    symbol: str
    name: str
    discovery_method: str  # url, address, ticker
    
    # Chat data
    mention_count: int
    chat_count: int
    chats: List[str]
    chat_summary: Optional[str]
    sentiment: Optional[str]
    per_chat_summaries: List[dict]
    
    # Market data
    price_usd: Optional[float]
    market_cap: Optional[float]
    liquidity_usd: Optional[float]
    price_change_1h: Optional[float]
    price_change_24h: Optional[float]
    volume_24h: Optional[float]
    
    # Meta
    first_seen: Optional[str]
    last_seen: Optional[str]
    dex_url: Optional[str]
    image_url: Optional[str]


class ChatFirstFeedResponse(BaseModel):
    """Response for chat-first feed"""
    tokens: List[ChatDiscoveredTokenResponse]
    total_discovered: int
    messages_scanned: int
    last_updated: str


@router.get("/chat-first", response_model=ChatFirstFeedResponse)
async def get_chat_first_feed(
    limit: int = Query(50, ge=1, le=100, description="Max tokens to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CHAT-FIRST FEED
    
    Inverted flow:
    1. Scans ALL Telegram messages for token mentions (addresses, $SYMBOLS, URLs)
    2. Deduplicates and ranks by recency
    3. Enriches each with DexScreener market data
    4. Generates AI summaries of chat discussions
    
    This finds tokens being discussed even if they're not "trending" on DexScreener.
    """
    # 1. Get all messages
    messages = await _get_all_messages(current_user.id, db, lookback_hours=72)
    
    if not messages:
        return ChatFirstFeedResponse(
            tokens=[],
            total_discovered=0,
            messages_scanned=0,
            last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
        )
    
    # 2. Scan chats for tokens
    discovered_tokens = await chat_first_scanner.scan_chats(
        messages=messages,
        limit=limit,
    )
    
    # 3. Build response
    response_tokens = []
    for token in discovered_tokens:
        response_tokens.append(ChatDiscoveredTokenResponse(
            address=token.address,
            chain=token.chain,
            symbol=token.symbol or "???",
            name=token.name or "Unknown",
            discovery_method=token.discovery_method,
            mention_count=token.mention_count,
            chat_count=len(token.chats),
            chats=list(token.chats)[:5],
            chat_summary=token.chat_summary,
            sentiment=token.sentiment,
            per_chat_summaries=token.per_chat_summaries[:3],
            price_usd=token.price_usd,
            market_cap=token.market_cap,
            liquidity_usd=token.liquidity_usd,
            price_change_1h=token.price_change_1h,
            price_change_24h=token.price_change_24h,
            volume_24h=token.volume_24h,
            first_seen=token.first_seen.isoformat() if token.first_seen else None,
            last_seen=token.last_seen.isoformat() if token.last_seen else None,
            dex_url=token.dex_url or f"https://dexscreener.com/search?q={token.address}",
            image_url=token.image_url,
        ))
    
    return ChatFirstFeedResponse(
        tokens=response_tokens,
        total_discovered=len(discovered_tokens),
        messages_scanned=len(messages),
        last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
    )


# ============================================================================
# CONTEXTUAL DISCUSSIONS - Captures conversation context around token mentions
# ============================================================================

class DiscussionResponse(BaseModel):
    """A token discussion with context"""
    address: str
    chain: str
    symbol: str
    name: str
    
    # Market data
    price_usd: float
    market_cap: Optional[float]
    liquidity_usd: Optional[float]
    price_change_1h: Optional[float]
    price_change_24h: Optional[float]
    volume_24h: Optional[float]
    dex_url: str
    image_url: Optional[str]
    
    # Discussion data
    mention_count: int
    chat_count: int
    chats: List[str]
    summary: str
    sentiment: str
    
    # Timestamps
    first_seen: Optional[str]
    last_seen: Optional[str]


class DiscussionsFeedResponse(BaseModel):
    """Response for contextual discussions feed"""
    tokens: List[DiscussionResponse]
    total_found: int
    messages_scanned: int
    last_updated: str


@router.get("/discussions", response_model=DiscussionsFeedResponse)
async def get_discussions_feed(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CONTEXTUAL DISCUSSIONS FEED
    
    Improved approach:
    1. Find token mentions in messages
    2. Capture SURROUNDING messages (10 min window) for context
    3. Only show tokens with valid DexScreener data
    4. Generate AI summaries from actual discussions
    
    This filters out tokens without DexScreener pages and
    captures the real conversation context, not just mentions.
    """
    # 1. Get all messages
    messages = await _get_all_messages(current_user.id, db, lookback_hours=72)
    
    if not messages:
        return DiscussionsFeedResponse(
            tokens=[],
            total_found=0,
            messages_scanned=0,
            last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
        )
    
    # 2. Scan with contextual scanner
    discussions = await contextual_scanner.scan(
        messages=messages,
        limit=limit,
    )
    
    # 3. Build response
    response_tokens = []
    for token in discussions:
        response_tokens.append(DiscussionResponse(
            address=token.address,
            chain=token.chain,
            symbol=token.symbol,
            name=token.name,
            price_usd=token.price_usd,
            market_cap=token.market_cap,
            liquidity_usd=token.liquidity_usd,
            price_change_1h=token.price_change_1h,
            price_change_24h=token.price_change_24h,
            volume_24h=token.volume_24h,
            dex_url=token.dex_url,
            image_url=token.image_url,
            mention_count=token.mention_count,
            chat_count=len(token.chats),
            chats=list(token.chats)[:5],
            summary=token.summary,
            sentiment=token.sentiment,
            first_seen=token.first_seen.isoformat() if token.first_seen else None,
            last_seen=token.last_seen.isoformat() if token.last_seen else None,
        ))
    
    return DiscussionsFeedResponse(
        tokens=response_tokens,
        total_found=len(discussions),
        messages_scanned=len(messages),
        last_updated=(_last_scan_time or datetime.utcnow()).isoformat(),
    )
