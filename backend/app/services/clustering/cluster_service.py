"""Signal clustering service"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
import uuid

from app.core.config import settings
from app.services.clustering.embeddings import embedding_service
import structlog

logger = structlog.get_logger()


@dataclass
class ClusterData:
    """In-memory cluster data"""
    id: str
    token_address: Optional[str]
    token_symbol: Optional[str]
    chain: str
    
    # Timing
    first_seen: datetime
    last_seen: datetime
    peak_activity_time: Optional[datetime] = None
    
    # Collections
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context_messages: List[Dict[str, Any]] = field(default_factory=list)  # NEW: surrounding discussion
    source_ids: Set[str] = field(default_factory=set)
    source_names: Set[str] = field(default_factory=set)
    wallet_addresses: Set[str] = field(default_factory=set)
    
    # Metrics
    total_mentions: int = 0
    mentions_per_minute: float = 0.0
    peak_mentions_per_minute: float = 0.0
    
    # Sentiment
    sentiment_bullish: int = 0
    sentiment_bearish: int = 0
    sentiment_neutral: int = 0
    
    # Scores (calculated)
    urgency_score: float = 0.0
    novelty_score: float = 0.0
    confidence_score: float = 0.0
    priority_score: float = 0.0
    
    # Price data
    price_at_first_mention: Optional[float] = None
    price_current: Optional[float] = None


class ClusteringService:
    """Service for clustering signals by token"""
    
    def __init__(self):
        self._active_clusters: Dict[str, ClusterData] = {}
        self._cluster_window = timedelta(minutes=settings.cluster_window_minutes)
        self._minute_buckets: Dict[str, Dict[int, int]] = {}  # cluster_id -> {minute_ts: count}
    
    def get_cluster_key(self, token_address: Optional[str], token_symbol: Optional[str], chain: str) -> str:
        """Generate unique key for a token cluster"""
        if token_address:
            return f"{token_address}:{chain}"
        elif token_symbol:
            return f"${token_symbol}:{chain}"
        else:
            return f"unknown:{chain}:{uuid.uuid4().hex[:8]}"
    
    def add_message_to_cluster(
        self,
        message: Dict[str, Any],
        token_address: Optional[str],
        token_symbol: Optional[str],
        chain: str,
    ) -> ClusterData:
        """
        Add a message to a cluster (creates cluster if needed).
        
        Args:
            message: Processed message dict
            token_address: Token contract address
            token_symbol: Token symbol (e.g., "COWSAY")
            chain: Blockchain name
        
        Returns:
            Updated or created cluster
        """
        cluster_key = self.get_cluster_key(token_address, token_symbol, chain)
        now = datetime.utcnow()
        
        # Get or create cluster
        if cluster_key in self._active_clusters:
            cluster = self._active_clusters[cluster_key]
            
            # Check if cluster is still active (within window)
            if now - cluster.last_seen > self._cluster_window:
                # Archive old cluster and create new one
                self._archive_cluster(cluster)
                cluster = self._create_cluster(token_address, token_symbol, chain, now)
                self._active_clusters[cluster_key] = cluster
        else:
            cluster = self._create_cluster(token_address, token_symbol, chain, now)
            self._active_clusters[cluster_key] = cluster
        
        # Update cluster with message
        self._update_cluster_with_message(cluster, message, now)
        
        return cluster
    
    def _create_cluster(
        self,
        token_address: Optional[str],
        token_symbol: Optional[str],
        chain: str,
        timestamp: datetime,
    ) -> ClusterData:
        """Create a new cluster"""
        cluster_id = str(uuid.uuid4())
        
        cluster = ClusterData(
            id=cluster_id,
            token_address=token_address,
            token_symbol=token_symbol,
            chain=chain,
            first_seen=timestamp,
            last_seen=timestamp,
            novelty_score=100.0,  # New clusters start with high novelty
        )
        
        self._minute_buckets[cluster_id] = {}
        
        logger.info(
            "cluster_created",
            cluster_id=cluster_id,
            token=token_address or token_symbol,
            chain=chain,
        )
        
        return cluster
    
    def _update_cluster_with_message(
        self,
        cluster: ClusterData,
        message: Dict[str, Any],
        timestamp: datetime,
    ):
        """Update cluster with new message"""
        # Add message
        cluster.messages.append(message)
        cluster.last_seen = timestamp
        cluster.total_mentions += 1
        
        # Add context messages (the surrounding discussion)
        context_msgs = message.get("context_messages", [])
        for ctx in context_msgs:
            # Avoid duplicates by checking text
            ctx_text = ctx.get("text", "")
            existing_texts = {c.get("text", "") for c in cluster.context_messages}
            if ctx_text and ctx_text not in existing_texts:
                cluster.context_messages.append(ctx)
                
                # Also count context sentiment
                ctx_sentiment = ctx.get("sentiment", "neutral")
                if ctx_sentiment == "bullish":
                    cluster.sentiment_bullish += 1
                elif ctx_sentiment == "bearish":
                    cluster.sentiment_bearish += 1
        
        # Add source
        source_id = message.get("source_id")
        source_name = message.get("source_name")
        if source_id:
            cluster.source_ids.add(source_id)
        if source_name:
            cluster.source_names.add(source_name)
        
        # Add wallets
        for wallet in message.get("wallets", []):
            if wallet.get("address"):
                cluster.wallet_addresses.add(wallet["address"])
        
        # Update sentiment
        sentiment = message.get("sentiment", "neutral")
        if sentiment == "bullish":
            cluster.sentiment_bullish += 1
        elif sentiment == "bearish":
            cluster.sentiment_bearish += 1
        else:
            cluster.sentiment_neutral += 1
        
        # Update velocity tracking
        minute_ts = int(timestamp.timestamp() // 60)
        if cluster.id not in self._minute_buckets:
            self._minute_buckets[cluster.id] = {}
        
        bucket = self._minute_buckets[cluster.id]
        bucket[minute_ts] = bucket.get(minute_ts, 0) + 1
        
        # Calculate velocity
        self._calculate_velocity(cluster, timestamp)
        
        # Recalculate scores
        self._calculate_scores(cluster, timestamp)
    
    def _calculate_velocity(self, cluster: ClusterData, now: datetime):
        """Calculate mention velocity (mentions per minute)"""
        bucket = self._minute_buckets.get(cluster.id, {})
        
        if not bucket:
            cluster.mentions_per_minute = 0.0
            return
        
        # Calculate for last 5 minutes
        current_minute = int(now.timestamp() // 60)
        recent_counts = []
        
        for i in range(5):
            minute_ts = current_minute - i
            count = bucket.get(minute_ts, 0)
            recent_counts.append(count)
        
        # Average velocity
        cluster.mentions_per_minute = sum(recent_counts) / 5.0
        
        # Track peak
        current_max = max(recent_counts) if recent_counts else 0
        if current_max > cluster.peak_mentions_per_minute:
            cluster.peak_mentions_per_minute = float(current_max)
            cluster.peak_activity_time = now
    
    def _calculate_scores(self, cluster: ClusterData, now: datetime):
        """Calculate cluster scores"""
        # Source diversity score (0-25)
        source_diversity = min(len(cluster.source_ids) / 5.0, 1.0) * 25
        
        # Recency score (0-20) - decays over time
        age_seconds = (now - cluster.first_seen).total_seconds()
        recency = max(0, 1 - age_seconds / 3600) * 20  # Decays over 1 hour
        
        # Velocity score (0-20)
        velocity = min(cluster.mentions_per_minute / 5.0, 1.0) * 20
        
        # Wallet activity score (0-15)
        wallet_activity = min(len(cluster.wallet_addresses) / 3.0, 1.0) * 15
        
        # Confidence score (based on source count and consistency)
        cluster.confidence_score = min(len(cluster.source_ids) * 15, 100)
        
        # Urgency score (based on velocity and recency)
        cluster.urgency_score = min((velocity + recency) * 1.5, 100)
        
        # Novelty score (decays as cluster ages)
        cluster.novelty_score = max(0, 100 - (age_seconds / 60))  # Drops 1 point per minute
        
        # Priority score (composite)
        cluster.priority_score = source_diversity + recency + velocity + wallet_activity + (cluster.confidence_score * 0.2)
    
    def _archive_cluster(self, cluster: ClusterData):
        """Archive a cluster (prepare for database storage)"""
        # Clean up minute buckets
        if cluster.id in self._minute_buckets:
            del self._minute_buckets[cluster.id]
        
        logger.info(
            "cluster_archived",
            cluster_id=cluster.id,
            token=cluster.token_address or cluster.token_symbol,
            total_mentions=cluster.total_mentions,
            unique_sources=len(cluster.source_ids),
        )
    
    def process_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[ClusterData]:
        """
        Process a batch of messages and update clusters.
        
        Args:
            messages: List of processed message dicts with tokens
        
        Returns:
            List of updated clusters
        """
        updated_clusters = set()
        
        for message in messages:
            tokens = message.get("tokens", [])
            
            for token in tokens:
                token_address = token.get("address")
                token_symbol = token.get("symbol")
                chain = token.get("chain", "solana")
                
                cluster = self.add_message_to_cluster(
                    message=message,
                    token_address=token_address,
                    token_symbol=token_symbol,
                    chain=chain,
                )
                updated_clusters.add(cluster.id)
        
        # Return updated clusters
        return [c for c in self._active_clusters.values() if c.id in updated_clusters]
    
    def get_active_clusters(
        self,
        min_sources: int = 1,
        min_mentions: int = 1,
        chain: Optional[str] = None,
        sort_by: str = "priority_score",
        limit: int = 50,
    ) -> List[ClusterData]:
        """
        Get active clusters sorted by specified metric.
        
        Args:
            min_sources: Minimum unique sources
            min_mentions: Minimum total mentions
            chain: Filter by chain
            sort_by: Field to sort by
            limit: Maximum clusters to return
        
        Returns:
            Sorted list of clusters
        """
        clusters = []
        now = datetime.utcnow()
        
        for cluster in self._active_clusters.values():
            # Check if still active
            if now - cluster.last_seen > self._cluster_window:
                continue
            
            # Apply filters
            if len(cluster.source_ids) < min_sources:
                continue
            if cluster.total_mentions < min_mentions:
                continue
            if chain and cluster.chain != chain:
                continue
            
            clusters.append(cluster)
        
        # Sort
        clusters.sort(key=lambda c: getattr(c, sort_by, 0), reverse=True)
        
        return clusters[:limit]
    
    def get_cluster_by_token(
        self,
        token_address: Optional[str] = None,
        token_symbol: Optional[str] = None,
        chain: str = "solana",
    ) -> Optional[ClusterData]:
        """Get cluster for a specific token"""
        cluster_key = self.get_cluster_key(token_address, token_symbol, chain)
        return self._active_clusters.get(cluster_key)
    
    def _is_scan_or_bot_message(self, text: str) -> bool:
        """Check if a message is a bot/scan message rather than real discussion"""
        if not text:
            return True
        
        text_lower = text.lower()
        
        # Skip URL-heavy messages
        if "http" in text_lower or text.count("/") > 2:
            return True
        
        # Skip messages with contract addresses
        skip_patterns = [
            "pump.fun", "dexscreener", "birdeye", "raydium", "jupiter",
            "ca:", "contract:", "mint:", "token:", "address:",
            "0x", "buy now", "presale", "airdrop live",
        ]
        if any(skip in text_lower for skip in skip_patterns):
            return True
        
        # Skip messages that are mostly hex/base58 (addresses)
        alphanumeric = sum(1 for c in text if c.isalnum())
        if alphanumeric > 0:
            uppercase_nums = sum(1 for c in text if c.isupper() or c.isdigit())
            if uppercase_nums / alphanumeric > 0.6 and len(text) < 100:
                return True
        
        # Skip very short messages
        if len(text.strip()) < 25:
            return True
        
        return False
    
    def _get_best_discussion_message(self, cluster: ClusterData) -> Dict[str, Any]:
        """
        Find the best message to show as the 'top signal'.
        Prioritizes extracted opinions over raw messages.
        """
        candidates = []
        
        for ctx in cluster.context_messages:
            text = ctx.get("text", "")
            
            # Skip if it looks like a bot/scan message
            if self._is_scan_or_bot_message(text):
                continue
            
            # Base score from length
            score = min(len(text), 200)  # Cap length contribution
            
            # MAJOR bonus if this came from opinion extraction
            opinion_type = ctx.get("opinion_type")
            if opinion_type:
                score += 100  # Extracted opinions are much more valuable
                
                # Extra bonus for specific opinion types
                if opinion_type in ["price_prediction", "entry_signal", "exit_signal"]:
                    score += 50
                elif opinion_type in ["catalyst", "warning"]:
                    score += 40
                elif opinion_type in ["social_proof", "whale_activity"]:
                    score += 30
            
            # Bonus for key claim extraction
            if ctx.get("key_claim"):
                score += 40
            
            # Bonus for price target
            if ctx.get("price_target"):
                score += 30
            
            # Bonus for confidence
            confidence = ctx.get("confidence", 0)
            if confidence:
                score += confidence * 50
            
            # Opinion word bonuses (for non-extracted messages)
            if not opinion_type:
                opinion_words = [
                    "bullish", "bearish", "looks", "think", "feel", "imo",
                    "ape", "buying", "selling", "holding", "entry", "target",
                    "dev", "team", "community", "based", "legit", "solid", "gem",
                    "whale", "volume", "chart", "pump", "moon",
                    "excited", "worried", "confident", "risky", "profit",
                ]
                for word in opinion_words:
                    if word in text.lower():
                        score += 25
            
            # Sentiment bonus
            if ctx.get("sentiment") in ["bullish", "bearish"]:
                score += 20
            
            if score > 50:
                candidates.append({
                    "text": text,
                    "source": ctx.get("source_name", ""),
                    "score": score,
                    "sentiment": ctx.get("sentiment", "neutral"),
                    "opinion_type": opinion_type,
                    "key_claim": ctx.get("key_claim"),
                    "price_target": ctx.get("price_target"),
                })
        
        # Sort by score and return best
        if candidates:
            candidates.sort(key=lambda x: x["score"], reverse=True)
            best = candidates[0]
            source = best["source"] or (list(cluster.source_names)[0] if cluster.source_names else "Unknown")
            return {
                "text": best["text"][:500],
                "source": source,
                "is_discussion": True,
                "sentiment": best["sentiment"],
                "opinion_type": best.get("opinion_type"),
                "key_claim": best.get("key_claim"),
                "price_target": best.get("price_target"),
            }
        
        return {
            "text": "",
            "source": list(cluster.source_names)[0] if cluster.source_names else "Unknown",
            "is_discussion": False,
            "sentiment": "neutral",
        }
    
    def get_aggregated_insights(self, cluster: ClusterData) -> Dict[str, Any]:
        """
        Aggregate all opinions for a token into synthesized insights.
        Returns a summary of what people are saying.
        """
        insights = {
            "total_opinions": 0,
            "opinion_types": {},
            "key_claims": [],
            "price_targets": [],
            "bullish_reasons": [],
            "bearish_reasons": [],
            "catalysts": [],
            "warnings": [],
        }
        
        for ctx in cluster.context_messages:
            opinion_type = ctx.get("opinion_type")
            if not opinion_type:
                continue
            
            insights["total_opinions"] += 1
            
            # Count opinion types
            insights["opinion_types"][opinion_type] = insights["opinion_types"].get(opinion_type, 0) + 1
            
            # Collect key claims
            if ctx.get("key_claim"):
                insights["key_claims"].append({
                    "claim": ctx["key_claim"],
                    "source": ctx.get("source_name", "Unknown"),
                    "sentiment": ctx.get("sentiment", "neutral"),
                })
            
            # Collect price targets
            if ctx.get("price_target"):
                insights["price_targets"].append(ctx["price_target"])
            
            # Categorize by sentiment
            text = ctx.get("text", "")[:200]
            sentiment = ctx.get("sentiment", "neutral")
            
            if sentiment == "bullish":
                insights["bullish_reasons"].append({
                    "text": text,
                    "source": ctx.get("source_name", ""),
                    "type": opinion_type,
                })
            elif sentiment == "bearish":
                insights["bearish_reasons"].append({
                    "text": text,
                    "source": ctx.get("source_name", ""),
                    "type": opinion_type,
                })
            
            # Collect catalysts and warnings
            if opinion_type == "catalyst":
                insights["catalysts"].append(text)
            elif opinion_type == "warning":
                insights["warnings"].append(text)
        
        # Deduplicate and limit
        insights["key_claims"] = insights["key_claims"][:5]
        insights["bullish_reasons"] = insights["bullish_reasons"][:5]
        insights["bearish_reasons"] = insights["bearish_reasons"][:5]
        insights["catalysts"] = list(set(insights["catalysts"]))[:3]
        insights["warnings"] = list(set(insights["warnings"]))[:3]
        insights["price_targets"] = list(set(insights["price_targets"]))[:3]
        
        return insights

    def to_dict(self, cluster: ClusterData) -> Dict[str, Any]:
        """Convert cluster to dictionary for API response"""
        # Get the best discussion message
        top_signal = self._get_best_discussion_message(cluster)
        
        # Get aggregated insights from all opinions
        insights = self.get_aggregated_insights(cluster)
        
        return {
            "id": cluster.id,
            "token": {
                "address": cluster.token_address,
                "symbol": cluster.token_symbol,
                "chain": cluster.chain,
            },
            "timing": {
                "first_seen": cluster.first_seen.isoformat(),
                "last_seen": cluster.last_seen.isoformat(),
                "peak_activity_time": cluster.peak_activity_time.isoformat() if cluster.peak_activity_time else None,
            },
            "metrics": {
                "unique_sources": len(cluster.source_ids),
                "total_mentions": cluster.total_mentions,
                "unique_wallets": len(cluster.wallet_addresses),
                "mentions_per_minute": cluster.mentions_per_minute,
                "total_opinions": insights["total_opinions"],
            },
            "scores": {
                "urgency": cluster.urgency_score,
                "novelty": cluster.novelty_score,
                "confidence": cluster.confidence_score,
                "priority": cluster.priority_score,
            },
            "sentiment": {
                "bullish": cluster.sentiment_bullish,
                "bearish": cluster.sentiment_bearish,
                "neutral": cluster.sentiment_neutral,
            },
            "sources": list(cluster.source_names),
            "wallets": list(cluster.wallet_addresses)[:10],
            "top_messages": cluster.messages[-5:],
            "context_messages": cluster.context_messages[-10:],
            "top_signal": top_signal,  # Best discussion message
            "insights": insights,  # Aggregated opinions/insights
            "price": {
                "at_first_mention": cluster.price_at_first_mention,
                "current": cluster.price_current,
            },
        }


# Singleton instance
clustering_service = ClusteringService()
