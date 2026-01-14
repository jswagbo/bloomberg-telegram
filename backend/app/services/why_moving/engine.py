"""Why Is This Moving? Engine - Correlates signals to explain price movements"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from app.core.database import get_db_context
from app.services.clustering.cluster_service import clustering_service
from app.services.ranking.source_tracker import source_tracker
from app.services.external_apis.price_service import price_service
import structlog

logger = structlog.get_logger()


class EventType(str, Enum):
    FIRST_MENTION = "first_mention"
    WHALE_BUY = "whale_buy"
    WHALE_SELL = "whale_sell"
    CALL_POSTED = "call_posted"
    VOLUME_SPIKE = "volume_spike"
    PRICE_MOVE = "price_move"
    MULTIPLE_SOURCES = "multiple_sources"
    DEV_ACTIVITY = "dev_activity"
    SOCIAL_SPIKE = "social_spike"


@dataclass
class TimelineEvent:
    """Event in the movement timeline"""
    timestamp: datetime
    event_type: EventType
    description: str
    source: Optional[str] = None
    confidence: float = 0.5
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MovementExplanation:
    """Complete explanation for a price movement"""
    token_address: str
    token_symbol: Optional[str]
    chain: str
    
    # Price change info
    price_change_percent: float
    price_from: Optional[float]
    price_to: Optional[float]
    timeframe_minutes: int
    
    # Analysis
    timeline: List[TimelineEvent]
    top_reasons: List[str]
    confidence: float
    
    # Summary
    summary: str


class WhyMovingService:
    """Service for explaining price movements"""
    
    async def explain_movement(
        self,
        token_address: str,
        chain: str = "solana",
        window_minutes: int = 30,
    ) -> MovementExplanation:
        """
        Analyze and explain why a token is moving.
        
        Correlates:
        - Telegram mentions
        - Whale wallet activity
        - Call channel posts
        - Volume spikes
        - Social signals
        
        Returns:
            MovementExplanation with timeline and reasons
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        logger.info(
            "analyzing_movement",
            token=token_address,
            chain=chain,
            window_minutes=window_minutes,
        )
        
        # Gather all signals
        events: List[TimelineEvent] = []
        
        # 1. Get price data
        price_data = await self._get_price_data(token_address, chain, window_minutes)
        token_symbol = price_data.get("symbol")
        
        # 2. Get Telegram mentions from cluster
        cluster = clustering_service.get_cluster_by_token(
            token_address=token_address,
            chain=chain,
        )
        
        if cluster:
            telegram_events = self._extract_telegram_events(cluster, window_start)
            events.extend(telegram_events)
        
        # 3. Get whale activity (from recent messages mentioning wallets)
        whale_events = await self._get_whale_events(token_address, chain, window_start)
        events.extend(whale_events)
        
        # 4. Check for volume spikes
        if price_data.get("volume_change_percent", 0) > 100:
            events.append(TimelineEvent(
                timestamp=now - timedelta(minutes=5),
                event_type=EventType.VOLUME_SPIKE,
                description=f"Volume up {price_data['volume_change_percent']:.0f}% in last hour",
                confidence=0.8,
                data={"volume_change": price_data.get("volume_change_percent")},
            ))
        
        # 5. Add price movement event
        if price_data.get("price_change_percent"):
            direction = "up" if price_data["price_change_percent"] > 0 else "down"
            events.append(TimelineEvent(
                timestamp=now,
                event_type=EventType.PRICE_MOVE,
                description=f"Price {direction} {abs(price_data['price_change_percent']):.1f}%",
                confidence=1.0,
                data=price_data,
            ))
        
        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)
        
        # Generate explanations
        top_reasons = self._generate_reasons(events, cluster)
        confidence = self._calculate_confidence(events, top_reasons)
        summary = self._generate_summary(token_symbol or token_address[:8], events, top_reasons)
        
        return MovementExplanation(
            token_address=token_address,
            token_symbol=token_symbol,
            chain=chain,
            price_change_percent=price_data.get("price_change_percent", 0),
            price_from=price_data.get("price_from"),
            price_to=price_data.get("price_to"),
            timeframe_minutes=window_minutes,
            timeline=events,
            top_reasons=top_reasons,
            confidence=confidence,
            summary=summary,
        )
    
    async def _get_price_data(
        self,
        token_address: str,
        chain: str,
        window_minutes: int,
    ) -> Dict[str, Any]:
        """Get price data for the token"""
        try:
            # Get current price
            current = await price_service.get_token_price(token_address, chain)
            
            if not current:
                return {}
            
            return {
                "symbol": current.get("symbol"),
                "price_to": current.get("price_usd"),
                "price_from": current.get("price_usd"),  # Would need historical data
                "price_change_percent": current.get("price_change_24h", 0),
                "volume_24h": current.get("volume_24h"),
                "volume_change_percent": current.get("volume_change_24h", 0),
                "market_cap": current.get("market_cap"),
            }
        except Exception as e:
            logger.error("price_fetch_error", error=str(e))
            return {}
    
    def _extract_telegram_events(
        self,
        cluster,
        window_start: datetime,
    ) -> List[TimelineEvent]:
        """Extract events from cluster data"""
        events = []
        
        # First mention
        if cluster.first_seen >= window_start:
            events.append(TimelineEvent(
                timestamp=cluster.first_seen,
                event_type=EventType.FIRST_MENTION,
                description=f"First mentioned in {list(cluster.source_names)[0] if cluster.source_names else 'Telegram'}",
                source=list(cluster.source_names)[0] if cluster.source_names else None,
                confidence=0.9,
            ))
        
        # Multiple sources convergence
        if len(cluster.source_ids) >= 3:
            events.append(TimelineEvent(
                timestamp=cluster.peak_activity_time or cluster.last_seen,
                event_type=EventType.MULTIPLE_SOURCES,
                description=f"{len(cluster.source_ids)} sources mentioning (signal convergence)",
                confidence=0.85,
                data={"source_count": len(cluster.source_ids)},
            ))
        
        # High-trust caller
        for source_id in cluster.source_ids:
            rep = source_tracker.get_source_reputation(source_id)
            if rep and rep.get("scores", {}).get("trust", 0) > 70:
                events.append(TimelineEvent(
                    timestamp=cluster.first_seen,
                    event_type=EventType.CALL_POSTED,
                    description=f"{rep['name']} called it (Trust: {rep['scores']['trust']:.0f})",
                    source=rep["name"],
                    confidence=0.8,
                    data={"trust_score": rep["scores"]["trust"]},
                ))
                break  # Only add one high-trust caller
        
        # Whale wallet mentions
        if cluster.wallet_addresses:
            for wallet in list(cluster.wallet_addresses)[:2]:
                events.append(TimelineEvent(
                    timestamp=cluster.first_seen + timedelta(minutes=2),
                    event_type=EventType.WHALE_BUY,
                    description=f"Whale wallet {wallet[:8]}... mentioned",
                    confidence=0.7,
                    data={"wallet": wallet},
                ))
        
        return events
    
    async def _get_whale_events(
        self,
        token_address: str,
        chain: str,
        window_start: datetime,
    ) -> List[TimelineEvent]:
        """Get whale activity events (would integrate with on-chain data)"""
        # This would ideally fetch from on-chain APIs
        # For now, return empty as we rely on Telegram mentions
        return []
    
    def _generate_reasons(
        self,
        events: List[TimelineEvent],
        cluster,
    ) -> List[str]:
        """Generate top reasons for the movement"""
        reasons = []
        
        # Analyze event types
        event_types = [e.event_type for e in events]
        
        if EventType.WHALE_BUY in event_types:
            whale_events = [e for e in events if e.event_type == EventType.WHALE_BUY]
            reasons.append(f"Whale wallet(s) bought in ({len(whale_events)} detected)")
        
        if EventType.CALL_POSTED in event_types:
            call_event = next(e for e in events if e.event_type == EventType.CALL_POSTED)
            reasons.append(f"Called by {call_event.source or 'trusted caller'}")
        
        if EventType.MULTIPLE_SOURCES in event_types:
            source_event = next(e for e in events if e.event_type == EventType.MULTIPLE_SOURCES)
            reasons.append(f"Signal convergence: {source_event.data.get('source_count', 0)}+ sources")
        
        if EventType.VOLUME_SPIKE in event_types:
            vol_event = next(e for e in events if e.event_type == EventType.VOLUME_SPIKE)
            reasons.append(f"Volume spike: +{vol_event.data.get('volume_change', 0):.0f}%")
        
        if cluster:
            # Sentiment
            total_sentiment = cluster.sentiment_bullish + cluster.sentiment_bearish + cluster.sentiment_neutral
            if total_sentiment > 0:
                bullish_pct = (cluster.sentiment_bullish / total_sentiment) * 100
                if bullish_pct > 70:
                    reasons.append(f"Strong bullish sentiment ({bullish_pct:.0f}%)")
        
        if not reasons:
            reasons.append("Movement origin unclear - monitoring for more signals")
        
        return reasons[:5]  # Top 5 reasons
    
    def _calculate_confidence(
        self,
        events: List[TimelineEvent],
        reasons: List[str],
    ) -> float:
        """Calculate overall explanation confidence"""
        if not events:
            return 0.1
        
        # Base confidence on event confidence scores
        avg_event_confidence = sum(e.confidence for e in events) / len(events)
        
        # Boost for multiple corroborating signals
        signal_boost = min(len(events) * 0.1, 0.3)
        
        # Boost for having clear reasons
        reason_boost = min(len(reasons) * 0.1, 0.2)
        
        confidence = avg_event_confidence + signal_boost + reason_boost
        return min(confidence, 1.0)
    
    def _generate_summary(
        self,
        token: str,
        events: List[TimelineEvent],
        reasons: List[str],
    ) -> str:
        """Generate human-readable summary"""
        if not reasons:
            return f"{token} is moving but the cause is unclear."
        
        if len(reasons) == 1:
            return f"{token} is moving. Main reason: {reasons[0]}"
        
        return f"{token} is moving due to: {reasons[0]}. Also: {', '.join(reasons[1:3])}"
    
    def to_dict(self, explanation: MovementExplanation) -> Dict[str, Any]:
        """Convert explanation to API response format"""
        return {
            "token": {
                "address": explanation.token_address,
                "symbol": explanation.token_symbol,
                "chain": explanation.chain,
            },
            "price_change": {
                "percent": explanation.price_change_percent,
                "from": explanation.price_from,
                "to": explanation.price_to,
                "timeframe_minutes": explanation.timeframe_minutes,
            },
            "reasons": [
                {
                    "rank": i + 1,
                    "description": reason,
                }
                for i, reason in enumerate(explanation.top_reasons)
            ],
            "timeline": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type.value,
                    "description": event.description,
                    "source": event.source,
                    "confidence": event.confidence,
                }
                for event in explanation.timeline
            ],
            "confidence": explanation.confidence,
            "summary": explanation.summary,
        }


# Singleton instance
why_moving_service = WhyMovingService()
