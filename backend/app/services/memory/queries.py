"""Query service for complex historical queries"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from app.models.token import Token, TokenMention
from app.models.wallet import Wallet, WalletActivity
from app.models.cluster import SignalCluster
from app.models.source import SourceReputation, SourceCall
from app.core.database import get_db_context
import structlog

logger = structlog.get_logger()


class QueryType(str, Enum):
    WALLET_TOKENS = "wallet_tokens"
    SOURCE_PERFORMANCE = "source_performance"
    SIMILAR_CLUSTERS = "similar_clusters"
    TOKEN_CALLERS = "token_callers"
    WHALE_ACTIVITY = "whale_activity"


class QueryService:
    """Service for complex queries against historical data"""
    
    async def query(
        self,
        query_type: str,
        **params
    ) -> Dict[str, Any]:
        """
        Execute a query based on type.
        
        Supported queries:
        - wallet_tokens: Tokens a wallet bought before they mooned
        - source_performance: Source hit rate over time period
        - similar_clusters: Historical clusters similar to current
        - token_callers: Who called a token first
        - whale_activity: Recent whale movements
        """
        query_map = {
            QueryType.WALLET_TOKENS: self._query_wallet_tokens,
            QueryType.SOURCE_PERFORMANCE: self._query_source_performance,
            QueryType.SIMILAR_CLUSTERS: self._query_similar_clusters,
            QueryType.TOKEN_CALLERS: self._query_token_callers,
            QueryType.WHALE_ACTIVITY: self._query_whale_activity,
        }
        
        try:
            query_type_enum = QueryType(query_type)
        except ValueError:
            return {"error": f"Unknown query type: {query_type}"}
        
        handler = query_map.get(query_type_enum)
        if not handler:
            return {"error": f"Query not implemented: {query_type}"}
        
        return await handler(**params)
    
    async def _query_wallet_tokens(
        self,
        wallet: str,
        min_return: float = 2.0,
        days: int = 30,
        chain: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query: Show me all tokens this wallet bought before they 5x'd
        """
        async with get_db_context() as db:
            # Get wallet
            conditions = [Wallet.address == wallet]
            if chain:
                conditions.append(Wallet.chain == chain)
            
            result = await db.execute(
                select(Wallet).where(and_(*conditions))
            )
            wallet_obj = result.scalar_one_or_none()
            
            if not wallet_obj:
                return {"error": "Wallet not found", "results": []}
            
            # Get wallet's buy activities with good returns
            since = datetime.utcnow() - timedelta(days=days)
            
            # This would need actual price tracking data
            # For now, return wallet's notable wins
            wins = wallet_obj.notable_wins or []
            filtered_wins = [
                w for w in wins 
                if w.get("return", 0) >= min_return
            ]
            
            return {
                "query": "wallet_tokens",
                "wallet": wallet,
                "min_return": min_return,
                "results": filtered_wins,
                "count": len(filtered_wins),
            }
    
    async def _query_source_performance(
        self,
        source_id: str,
        timeframe: str = "30d",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query: Show me Ray Silver's hit rate over last 30 days
        """
        # Parse timeframe
        days = int(timeframe.replace("d", ""))
        since = datetime.utcnow() - timedelta(days=days)
        
        async with get_db_context() as db:
            # Get source reputation
            result = await db.execute(
                select(SourceReputation).where(
                    SourceReputation.telegram_id == source_id
                )
            )
            source = result.scalar_one_or_none()
            
            if not source:
                return {"error": "Source not found", "results": None}
            
            # Get calls in timeframe
            calls_result = await db.execute(
                select(SourceCall).where(
                    and_(
                        SourceCall.source_telegram_id == source_id,
                        SourceCall.timestamp >= since,
                        SourceCall.is_processed == True
                    )
                ).order_by(SourceCall.timestamp)
            )
            calls = calls_result.scalars().all()
            
            # Calculate metrics
            total = len(calls)
            hits = sum(1 for c in calls if c.outcome == "hit")
            misses = sum(1 for c in calls if c.outcome == "miss")
            rugs = sum(1 for c in calls if c.outcome == "rug")
            
            returns = [c.max_return_24h for c in calls if c.max_return_24h is not None]
            avg_return = sum(returns) / len(returns) if returns else 0
            
            return {
                "query": "source_performance",
                "source": source.name,
                "timeframe": timeframe,
                "results": {
                    "total_calls": total,
                    "hits": hits,
                    "misses": misses,
                    "rugs": rugs,
                    "hit_rate": hits / total if total > 0 else 0,
                    "avg_return": avg_return,
                    "trust_score": source.trust_score,
                },
                "calls": [
                    {
                        "token": c.token_symbol,
                        "timestamp": c.timestamp.isoformat(),
                        "outcome": c.outcome,
                        "return": c.max_return_24h,
                    }
                    for c in calls[:20]
                ],
            }
    
    async def _query_similar_clusters(
        self,
        token: Optional[str] = None,
        min_sources: int = 3,
        days: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query: What happened last time $COWSAY was mentioned by 5+ sources?
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        async with get_db_context() as db:
            conditions = [
                SignalCluster.first_seen >= since,
                SignalCluster.unique_sources >= min_sources,
            ]
            
            if token:
                if token.startswith("$"):
                    conditions.append(SignalCluster.token_symbol == token[1:])
                else:
                    conditions.append(
                        or_(
                            SignalCluster.token_address == token,
                            SignalCluster.token_symbol == token
                        )
                    )
            
            result = await db.execute(
                select(SignalCluster).where(
                    and_(*conditions)
                ).order_by(desc(SignalCluster.priority_score)).limit(10)
            )
            clusters = result.scalars().all()
            
            return {
                "query": "similar_clusters",
                "token": token,
                "min_sources": min_sources,
                "results": [
                    {
                        "token": c.token_symbol or c.token_address[:8] if c.token_address else "Unknown",
                        "chain": c.chain,
                        "first_seen": c.first_seen.isoformat(),
                        "unique_sources": c.unique_sources,
                        "total_mentions": c.total_mentions,
                        "priority_score": c.priority_score,
                        "return_1h": c.return_1h,
                        "return_24h": c.return_24h,
                        "max_return": c.max_return_24h,
                    }
                    for c in clusters
                ],
                "count": len(clusters),
            }
    
    async def _query_token_callers(
        self,
        token: str,
        chain: str = "solana",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query: Who called this token first and what's their track record?
        """
        async with get_db_context() as db:
            # Get earliest mentions
            result = await db.execute(
                select(TokenMention).where(
                    and_(
                        TokenMention.address == token,
                        TokenMention.chain == chain,
                        TokenMention.mention_type == "call"
                    )
                ).order_by(TokenMention.timestamp).limit(10)
            )
            mentions = result.scalars().all()
            
            if not mentions:
                return {
                    "query": "token_callers",
                    "token": token,
                    "results": [],
                    "message": "No calls found for this token",
                }
            
            # Get source info for each caller
            callers = []
            for mention in mentions:
                source_result = await db.execute(
                    select(SourceReputation).where(
                        SourceReputation.telegram_id == mention.source_id
                    )
                )
                source = source_result.scalar_one_or_none()
                
                callers.append({
                    "source_name": mention.source_name,
                    "timestamp": mention.timestamp.isoformat(),
                    "price_at_call": mention.price_at_mention,
                    "return_1h": mention.return_1h,
                    "return_24h": mention.return_24h,
                    "source_trust_score": source.trust_score if source else None,
                    "source_hit_rate": source.hit_rate if source else None,
                    "is_first_call": mentions[0].source_id == mention.source_id,
                })
            
            return {
                "query": "token_callers",
                "token": token,
                "chain": chain,
                "first_caller": callers[0] if callers else None,
                "all_callers": callers,
                "count": len(callers),
            }
    
    async def _query_whale_activity(
        self,
        chain: str = "solana",
        hours: int = 24,
        min_usd: float = 10000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query: Recent whale activity in the last 24 hours
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        
        async with get_db_context() as db:
            # Get whale wallets
            whale_result = await db.execute(
                select(Wallet).where(
                    and_(
                        Wallet.chain == chain,
                        Wallet.label == "whale"
                    )
                )
            )
            whales = whale_result.scalars().all()
            whale_ids = [w.id for w in whales]
            
            if not whale_ids:
                return {
                    "query": "whale_activity",
                    "chain": chain,
                    "hours": hours,
                    "results": [],
                    "message": "No whale wallets tracked",
                }
            
            # Get recent activity
            activity_result = await db.execute(
                select(WalletActivity).where(
                    and_(
                        WalletActivity.wallet_id.in_(whale_ids),
                        WalletActivity.timestamp >= since,
                        WalletActivity.amount_usd >= min_usd
                    )
                ).order_by(desc(WalletActivity.timestamp)).limit(50)
            )
            activities = activity_result.scalars().all()
            
            # Group by token
            token_activity = {}
            for a in activities:
                if a.token_address not in token_activity:
                    token_activity[a.token_address] = {
                        "token": a.token_symbol or a.token_address[:8],
                        "total_volume": 0,
                        "buy_volume": 0,
                        "sell_volume": 0,
                        "whale_count": set(),
                        "activities": [],
                    }
                
                ta = token_activity[a.token_address]
                ta["total_volume"] += a.amount_usd or 0
                if a.activity_type == "buy":
                    ta["buy_volume"] += a.amount_usd or 0
                else:
                    ta["sell_volume"] += a.amount_usd or 0
                ta["whale_count"].add(a.address)
                ta["activities"].append({
                    "type": a.activity_type,
                    "amount_usd": a.amount_usd,
                    "timestamp": a.timestamp.isoformat(),
                    "wallet": a.address[:8],
                })
            
            # Convert sets to counts
            results = []
            for token_addr, data in token_activity.items():
                data["whale_count"] = len(data["whale_count"])
                data["activities"] = data["activities"][:5]
                results.append(data)
            
            # Sort by volume
            results.sort(key=lambda x: x["total_volume"], reverse=True)
            
            return {
                "query": "whale_activity",
                "chain": chain,
                "hours": hours,
                "min_usd": min_usd,
                "results": results[:20],
                "total_tokens": len(results),
            }


# Singleton instance
query_service = QueryService()
