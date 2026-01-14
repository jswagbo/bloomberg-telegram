"""Memory service for historical analysis and persistence"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.token import Token, TokenHistory, TokenMention
from app.models.wallet import Wallet, WalletActivity, WalletMention
from app.models.cluster import SignalCluster, ClusterMessage, ClusterEvent
from app.models.source import SourceReputation, SourceCall
from app.core.database import get_db_context
import structlog

logger = structlog.get_logger()


class MemoryService:
    """Service for storing and querying historical data"""
    
    async def store_token(
        self,
        address: str,
        chain: str,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
        price_usd: Optional[float] = None,
        market_cap: Optional[float] = None,
        **kwargs
    ) -> Token:
        """Store or update token information"""
        async with get_db_context() as db:
            # Check if token exists
            result = await db.execute(
                select(Token).where(
                    and_(Token.address == address, Token.chain == chain)
                )
            )
            token = result.scalar_one_or_none()
            
            if token:
                # Update existing
                if symbol:
                    token.symbol = symbol
                if name:
                    token.name = name
                if price_usd is not None:
                    token.price_usd = price_usd
                if market_cap is not None:
                    token.market_cap = market_cap
                for key, value in kwargs.items():
                    if hasattr(token, key):
                        setattr(token, key, value)
            else:
                # Create new
                token = Token(
                    address=address,
                    chain=chain,
                    symbol=symbol,
                    name=name,
                    price_usd=price_usd,
                    market_cap=market_cap,
                    first_mention=datetime.utcnow(),
                    **kwargs
                )
                db.add(token)
            
            token.last_mention = datetime.utcnow()
            token.total_mentions = (token.total_mentions or 0) + 1
            
            await db.flush()
            return token
    
    async def record_token_mention(
        self,
        token_id: str,
        address: str,
        chain: str,
        source_id: str,
        source_name: str,
        message_id: str,
        timestamp: datetime,
        price_at_mention: Optional[float] = None,
        mention_type: str = "mention",
        sentiment: str = "neutral",
    ) -> TokenMention:
        """Record a token mention for caller tracking"""
        async with get_db_context() as db:
            mention = TokenMention(
                token_id=token_id,
                address=address,
                chain=chain,
                source_id=source_id,
                source_name=source_name,
                message_id=message_id,
                timestamp=timestamp,
                price_at_mention=price_at_mention,
                mention_type=mention_type,
                sentiment=sentiment,
            )
            db.add(mention)
            await db.flush()
            return mention
    
    async def store_wallet(
        self,
        address: str,
        chain: str,
        label: Optional[str] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Wallet:
        """Store or update wallet information"""
        async with get_db_context() as db:
            result = await db.execute(
                select(Wallet).where(
                    and_(Wallet.address == address, Wallet.chain == chain)
                )
            )
            wallet = result.scalar_one_or_none()
            
            if wallet:
                if label:
                    wallet.label = label
                if tags:
                    wallet.tags = list(set(wallet.tags or []) | set(tags))
                wallet.last_seen = datetime.utcnow()
                wallet.mention_count = (wallet.mention_count or 0) + 1
            else:
                wallet = Wallet(
                    address=address,
                    chain=chain,
                    label=label,
                    tags=tags or [],
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    **kwargs
                )
                db.add(wallet)
            
            await db.flush()
            return wallet
    
    async def record_wallet_activity(
        self,
        wallet_id: str,
        address: str,
        chain: str,
        activity_type: str,
        token_address: str,
        amount: float,
        timestamp: datetime,
        **kwargs
    ) -> WalletActivity:
        """Record wallet activity (buy/sell/transfer)"""
        async with get_db_context() as db:
            activity = WalletActivity(
                wallet_id=wallet_id,
                address=address,
                chain=chain,
                activity_type=activity_type,
                token_address=token_address,
                amount=amount,
                timestamp=timestamp,
                source="telegram",
                **kwargs
            )
            db.add(activity)
            await db.flush()
            return activity
    
    async def store_cluster(
        self,
        cluster_data: Dict[str, Any]
    ) -> SignalCluster:
        """Store a signal cluster to database"""
        async with get_db_context() as db:
            cluster = SignalCluster(
                id=cluster_data["id"],
                token_address=cluster_data.get("token_address"),
                token_symbol=cluster_data.get("token_symbol"),
                chain=cluster_data["chain"],
                first_seen=cluster_data["first_seen"],
                last_seen=cluster_data["last_seen"],
                peak_activity_time=cluster_data.get("peak_activity_time"),
                unique_sources=cluster_data.get("unique_sources", 0),
                total_mentions=cluster_data.get("total_mentions", 0),
                unique_wallets=cluster_data.get("unique_wallets", 0),
                mentions_per_minute=cluster_data.get("mentions_per_minute", 0),
                priority_score=cluster_data.get("priority_score", 0),
                urgency_score=cluster_data.get("urgency_score", 0),
                novelty_score=cluster_data.get("novelty_score", 0),
                confidence_score=cluster_data.get("confidence_score", 0),
                sentiment_bullish=cluster_data.get("sentiment_bullish", 0),
                sentiment_bearish=cluster_data.get("sentiment_bearish", 0),
                sentiment_neutral=cluster_data.get("sentiment_neutral", 0),
                source_ids=cluster_data.get("source_ids", []),
                source_names=cluster_data.get("source_names", []),
                wallet_addresses=cluster_data.get("wallet_addresses", []),
                status="active",
            )
            db.add(cluster)
            await db.flush()
            return cluster
    
    async def update_source_reputation(
        self,
        telegram_id: str,
        name: str,
        source_type: str,
        stats: Dict[str, Any]
    ) -> SourceReputation:
        """Update source reputation in database"""
        async with get_db_context() as db:
            result = await db.execute(
                select(SourceReputation).where(
                    SourceReputation.telegram_id == telegram_id
                )
            )
            reputation = result.scalar_one_or_none()
            
            if reputation:
                # Update stats
                reputation.total_calls = stats.get("total_calls", reputation.total_calls)
                reputation.successful_calls = stats.get("successful_calls", reputation.successful_calls)
                reputation.failed_calls = stats.get("failed_calls", reputation.failed_calls)
                reputation.hit_rate = stats.get("hit_rate", reputation.hit_rate)
                reputation.avg_return_1h = stats.get("avg_return", reputation.avg_return_1h)
                reputation.trust_score = stats.get("trust_score", reputation.trust_score)
                reputation.speed_score = stats.get("speed_score", reputation.speed_score)
                reputation.last_call = stats.get("last_call")
            else:
                reputation = SourceReputation(
                    telegram_id=telegram_id,
                    name=name,
                    source_type=source_type,
                    total_calls=stats.get("total_calls", 0),
                    successful_calls=stats.get("successful_calls", 0),
                    failed_calls=stats.get("failed_calls", 0),
                    hit_rate=stats.get("hit_rate", 0.5),
                    trust_score=stats.get("trust_score", 50.0),
                    first_tracked=datetime.utcnow(),
                )
                db.add(reputation)
            
            await db.flush()
            return reputation
    
    async def get_token_history(
        self,
        address: str,
        chain: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get token history with mentions and price data"""
        async with get_db_context() as db:
            # Get token
            result = await db.execute(
                select(Token).where(
                    and_(Token.address == address, Token.chain == chain)
                )
            )
            token = result.scalar_one_or_none()
            
            if not token:
                return None
            
            # Get mentions
            since = datetime.utcnow() - timedelta(days=days)
            mentions_result = await db.execute(
                select(TokenMention).where(
                    and_(
                        TokenMention.address == address,
                        TokenMention.timestamp >= since
                    )
                ).order_by(TokenMention.timestamp.desc())
            )
            mentions = mentions_result.scalars().all()
            
            # Get price history
            history_result = await db.execute(
                select(TokenHistory).where(
                    and_(
                        TokenHistory.address == address,
                        TokenHistory.timestamp >= since
                    )
                ).order_by(TokenHistory.timestamp)
            )
            history = history_result.scalars().all()
            
            return {
                "token": {
                    "address": token.address,
                    "chain": token.chain,
                    "symbol": token.symbol,
                    "name": token.name,
                    "price_usd": token.price_usd,
                    "market_cap": token.market_cap,
                    "status": token.status,
                },
                "lifecycle": {
                    "first_mention": token.first_mention.isoformat() if token.first_mention else None,
                    "last_mention": token.last_mention.isoformat() if token.last_mention else None,
                    "total_mentions": token.total_mentions,
                    "unique_sources": token.unique_sources,
                },
                "mentions": [
                    {
                        "source_name": m.source_name,
                        "timestamp": m.timestamp.isoformat(),
                        "price_at_mention": m.price_at_mention,
                        "return_1h": m.return_1h,
                        "return_24h": m.return_24h,
                        "mention_type": m.mention_type,
                    }
                    for m in mentions[:50]
                ],
                "price_history": [
                    {
                        "timestamp": h.timestamp.isoformat(),
                        "price_usd": h.price_usd,
                        "volume": h.volume,
                        "mention_count": h.mention_count,
                    }
                    for h in history
                ],
            }
    
    async def get_wallet_profile(
        self,
        address: str,
        chain: str
    ) -> Optional[Dict[str, Any]]:
        """Get wallet profile with activity history"""
        async with get_db_context() as db:
            result = await db.execute(
                select(Wallet).where(
                    and_(Wallet.address == address, Wallet.chain == chain)
                )
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                return None
            
            # Get recent activity
            activity_result = await db.execute(
                select(WalletActivity).where(
                    WalletActivity.wallet_id == wallet.id
                ).order_by(WalletActivity.timestamp.desc()).limit(50)
            )
            activities = activity_result.scalars().all()
            
            return {
                "wallet": {
                    "address": wallet.address,
                    "chain": wallet.chain,
                    "label": wallet.label,
                    "tags": wallet.tags,
                    "name": wallet.name,
                },
                "behavior": {
                    "tokens_touched": wallet.tokens_touched,
                    "avg_hold_time_hours": wallet.avg_hold_time_hours,
                    "typical_position_size_usd": wallet.typical_position_size_usd,
                },
                "performance": {
                    "total_trades": wallet.total_trades,
                    "winning_trades": wallet.winning_trades,
                    "win_rate": wallet.win_rate,
                    "avg_return": wallet.avg_return,
                    "total_pnl_usd": wallet.total_pnl_usd,
                },
                "notable_wins": wallet.notable_wins or [],
                "linked_wallets": wallet.linked_wallets or [],
                "recent_activity": [
                    {
                        "timestamp": a.timestamp.isoformat(),
                        "type": a.activity_type,
                        "token": a.token_symbol or a.token_address[:8],
                        "amount": a.amount,
                        "amount_usd": a.amount_usd,
                    }
                    for a in activities
                ],
            }
    
    async def get_source_performance(
        self,
        telegram_id: str,
        days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Get detailed source performance"""
        async with get_db_context() as db:
            result = await db.execute(
                select(SourceReputation).where(
                    SourceReputation.telegram_id == telegram_id
                )
            )
            reputation = result.scalar_one_or_none()
            
            if not reputation:
                return None
            
            # Get recent calls
            since = datetime.utcnow() - timedelta(days=days)
            calls_result = await db.execute(
                select(SourceCall).where(
                    and_(
                        SourceCall.source_telegram_id == telegram_id,
                        SourceCall.timestamp >= since
                    )
                ).order_by(SourceCall.timestamp.desc())
            )
            calls = calls_result.scalars().all()
            
            return {
                "source": {
                    "telegram_id": reputation.telegram_id,
                    "name": reputation.name,
                    "type": reputation.source_type,
                },
                "overall_metrics": {
                    "total_calls": reputation.total_calls,
                    "successful_calls": reputation.successful_calls,
                    "failed_calls": reputation.failed_calls,
                    "hit_rate": reputation.hit_rate,
                    "avg_return_1h": reputation.avg_return_1h,
                    "avg_return_24h": reputation.avg_return_24h,
                },
                "scores": {
                    "trust": reputation.trust_score,
                    "speed": reputation.speed_score,
                    "consistency": reputation.consistency_score,
                },
                "flags": {
                    "is_flagged": reputation.is_flagged,
                    "reason": reputation.flag_reason,
                    "is_verified": reputation.is_verified,
                },
                f"calls_last_{days}d": [
                    {
                        "token": c.token_symbol or c.token_address[:8],
                        "timestamp": c.timestamp.isoformat(),
                        "return_1h": c.return_1h,
                        "return_24h": c.return_24h,
                        "max_return": c.max_return_24h,
                        "outcome": c.outcome,
                    }
                    for c in calls[:50]
                ],
            }


# Singleton instance
memory_service = MemoryService()
