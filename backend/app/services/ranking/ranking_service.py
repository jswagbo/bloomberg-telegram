"""Ranking and prioritization service"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

from app.core.config import settings
from app.services.ranking.source_tracker import source_tracker
from app.services.clustering.cluster_service import ClusterData
import structlog

logger = structlog.get_logger()


class RankingService:
    """Service for ranking and prioritizing signals"""
    
    # Scoring weights (from config)
    def __init__(self):
        self.source_diversity_weight = settings.source_diversity_weight
        self.recency_weight = settings.recency_weight
        self.velocity_weight = settings.velocity_weight
        self.wallet_activity_weight = settings.wallet_activity_weight
        self.source_quality_weight = settings.source_quality_weight
        self.spam_penalty_weight = settings.spam_penalty_weight
    
    def calculate_priority_score(self, cluster: ClusterData) -> float:
        """
        Calculate priority score for a cluster.
        
        Components:
        - Source diversity (0-25): More unique sources = higher
        - Recency (0-20): Newer signals = higher, decays over time
        - Velocity (0-20): Faster mention rate = higher
        - Wallet activity (0-15): More whale wallets = higher
        - Source quality (0-20): Higher trust scores = higher
        - Spam penalty (-30 to 0): Spam patterns reduce score
        
        Returns:
            Priority score (0-100)
        """
        now = datetime.utcnow()
        
        # Source diversity (0-25)
        source_count = len(cluster.source_ids)
        source_diversity = min(source_count / 5.0, 1.0) * self.source_diversity_weight
        
        # Recency (0-20) - decays over 1 hour
        age_seconds = (now - cluster.first_seen).total_seconds()
        recency = max(0, 1 - age_seconds / 3600) * self.recency_weight
        
        # Velocity (0-20) - based on mentions per minute
        velocity_normalized = min(cluster.mentions_per_minute / 5.0, 1.0)
        velocity = velocity_normalized * self.velocity_weight
        
        # Wallet activity (0-15)
        wallet_count = len(cluster.wallet_addresses)
        wallet_activity = min(wallet_count / 3.0, 1.0) * self.wallet_activity_weight
        
        # Source quality (0-20) - based on average trust score
        avg_trust = source_tracker.get_average_trust_score(list(cluster.source_ids))
        source_quality = (avg_trust / 100.0) * self.source_quality_weight
        
        # Spam penalty (-30 to 0)
        spam_score = self._detect_spam_patterns(cluster)
        spam_penalty = spam_score * self.spam_penalty_weight
        
        # Calculate total
        priority_score = (
            source_diversity +
            recency +
            velocity +
            wallet_activity +
            source_quality +
            spam_penalty
        )
        
        # Clamp to 0-100
        priority_score = max(0, min(100, priority_score))
        
        logger.debug(
            "priority_calculated",
            cluster_id=cluster.id,
            score=priority_score,
            components={
                "diversity": source_diversity,
                "recency": recency,
                "velocity": velocity,
                "wallet": wallet_activity,
                "quality": source_quality,
                "spam_penalty": spam_penalty,
            },
        )
        
        return priority_score
    
    def _detect_spam_patterns(self, cluster: ClusterData) -> float:
        """
        Detect spam patterns in cluster messages.
        Returns spam score from 0 (no spam) to 1 (definite spam).
        """
        spam_score = 0.0
        
        # Collect all message texts
        texts = [msg.get("original_text", "") for msg in cluster.messages]
        combined_text = " ".join(texts).lower()
        
        # Spam indicators
        spam_patterns = [
            (r'\bgiveaway\b', 0.3),
            (r'\bairdrop\b', 0.2),
            (r'\bfree\s+(?:tokens|coins|money)\b', 0.3),
            (r'\bclick\s+(?:here|link)\b', 0.2),
            (r'\bjoin\s+(?:now|us|today)\b', 0.1),
            (r'\blimited\s+time\b', 0.2),
            (r'\bverify\s+wallet\b', 0.4),
            (r'\bconnect\s+wallet\b', 0.3),
            (r'\bdm\s+(?:me|us)\b', 0.2),
            (r'\b(?:100|1000)x\s+guaranteed\b', 0.4),
            (r'\bpresale\b', 0.15),
            (r'\bwhitelist\b', 0.1),
        ]
        
        for pattern, weight in spam_patterns:
            if re.search(pattern, combined_text):
                spam_score += weight
        
        # Check for repeated exact messages (bot behavior)
        unique_messages = len(set(texts))
        total_messages = len(texts)
        if total_messages > 3 and unique_messages / total_messages < 0.5:
            spam_score += 0.3  # Many duplicate messages
        
        # Check for single source with many messages
        if len(cluster.source_ids) == 1 and cluster.total_mentions > 10:
            spam_score += 0.2  # Single source spamming
        
        # Cap at 1.0
        return min(spam_score, 1.0)
    
    def rank_clusters(
        self,
        clusters: List[ClusterData],
        recalculate: bool = True,
    ) -> List[ClusterData]:
        """
        Rank clusters by priority score.
        
        Args:
            clusters: List of clusters to rank
            recalculate: Whether to recalculate scores
        
        Returns:
            Sorted list of clusters (highest priority first)
        """
        if recalculate:
            for cluster in clusters:
                cluster.priority_score = self.calculate_priority_score(cluster)
        
        # Sort by priority score descending
        clusters.sort(key=lambda c: c.priority_score, reverse=True)
        
        return clusters
    
    def filter_clusters(
        self,
        clusters: List[ClusterData],
        min_score: float = 0.0,
        min_sources: int = 1,
        min_mentions: int = 1,
        max_age_minutes: int = 60,
        chains: Optional[List[str]] = None,
        exclude_flagged_sources: bool = True,
    ) -> List[ClusterData]:
        """
        Filter clusters based on criteria.
        
        Args:
            clusters: List of clusters to filter
            min_score: Minimum priority score
            min_sources: Minimum unique sources
            min_mentions: Minimum total mentions
            max_age_minutes: Maximum age in minutes
            chains: Filter by specific chains
            exclude_flagged_sources: Exclude clusters from flagged sources only
        
        Returns:
            Filtered list of clusters
        """
        now = datetime.utcnow()
        max_age = timedelta(minutes=max_age_minutes)
        filtered = []
        
        for cluster in clusters:
            # Age filter
            if now - cluster.first_seen > max_age:
                continue
            
            # Score filter
            if cluster.priority_score < min_score:
                continue
            
            # Source count filter
            if len(cluster.source_ids) < min_sources:
                continue
            
            # Mention count filter
            if cluster.total_mentions < min_mentions:
                continue
            
            # Chain filter
            if chains and cluster.chain not in chains:
                continue
            
            # Flagged source filter
            if exclude_flagged_sources:
                flagged = False
                for source_id in cluster.source_ids:
                    rep = source_tracker.get_source_reputation(source_id)
                    if rep and rep.get("flags", {}).get("is_flagged"):
                        flagged = True
                        break
                
                # Only exclude if ALL sources are flagged
                if flagged and len(cluster.source_ids) == 1:
                    continue
            
            filtered.append(cluster)
        
        return filtered
    
    def get_top_signals(
        self,
        clusters: List[ClusterData],
        limit: int = 10,
        **filter_kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Get top signals with full context.
        
        Returns list of signal dicts with cluster info and scoring breakdown.
        """
        # Filter and rank
        filtered = self.filter_clusters(clusters, **filter_kwargs)
        ranked = self.rank_clusters(filtered)
        
        # Build response
        signals = []
        for cluster in ranked[:limit]:
            # Get the best discussion message (prioritizes actual discussion over scan messages)
            top_signal = self._get_best_discussion_message(cluster)
            
            signal = {
                "cluster_id": cluster.id,
                "token": {
                    "address": cluster.token_address,
                    "symbol": cluster.token_symbol,
                    "chain": cluster.chain,
                },
                "score": cluster.priority_score,
                "metrics": {
                    "unique_sources": len(cluster.source_ids),
                    "total_mentions": cluster.total_mentions,
                    "unique_wallets": len(cluster.wallet_addresses),
                    "velocity": cluster.mentions_per_minute,
                },
                "sentiment": {
                    "bullish": cluster.sentiment_bullish,
                    "bearish": cluster.sentiment_bearish,
                    "neutral": cluster.sentiment_neutral,
                    "overall": self._get_overall_sentiment(cluster),
                    "percent_bullish": self._get_bullish_percent(cluster),
                },
                "timing": {
                    "first_seen": cluster.first_seen.isoformat(),
                    "age_minutes": (datetime.utcnow() - cluster.first_seen).total_seconds() / 60,
                },
                "top_signal": top_signal,
                "sources": list(cluster.source_names)[:5],
                "wallets": list(cluster.wallet_addresses)[:3],
            }
            
            signals.append(signal)
        
        return signals

    def _get_best_discussion_message(self, cluster: ClusterData) -> Dict[str, Any]:
        """
        Find the best message to show as the 'top signal'.
        Prioritizes actual discussion/opinion messages over scan/bot messages.
        """
        # First, try context messages (surrounding discussion)
        best_context = None
        best_context_score = 0
        
        for ctx in cluster.context_messages:
            text = ctx.get("text", "")
            if not text or len(text) < 20:
                continue
            
            # Skip if it looks like a bot/scan message
            if any(skip in text.lower() for skip in ["pump.fun", "dexscreener", "birdeye", "http"]):
                continue
            if text.count("/") > 3:  # Likely a URL-heavy message
                continue
            
            # Score based on length and content quality
            score = min(len(text), 300)  # Cap length bonus
            
            # Bonus for opinion indicators
            opinion_words = ["bullish", "bearish", "ape", "buy", "sell", "moon", "pump", "dev", "team", 
                          "looks", "think", "feel", "might", "could", "should", "entry", "target",
                          "whale", "holding", "sold", "bought", "profit", "loss", "dip", "send",
                          "gem", "alpha", "early", "undervalued", "potential", "legit", "rug",
                          "scam", "careful", "risky", "safe", "trust", "based"]
            for word in opinion_words:
                if word in text.lower():
                    score += 40
            
            # Bonus for sentiment
            if ctx.get("sentiment") in ["bullish", "bearish"]:
                score += 50
            
            if score > best_context_score:
                best_context_score = score
                best_context = ctx
        
        if best_context and best_context_score > 80:
            source_name = list(cluster.source_names)[0] if cluster.source_names else "Unknown"
            return {
                "text": best_context.get("text", "")[:500],
                "source": source_name,
                "is_discussion": True,
            }
        
        # Fallback: look through regular messages for discussion-like content
        for msg in reversed(cluster.messages[-10:]):
            text = msg.get("original_text", "")
            if not text or len(text) < 30:
                continue
            
            # Skip obvious bot/scan messages
            if any(skip in text.lower() for skip in ["pump.fun/", "dexscreener.com", "birdeye.so"]):
                continue
            
            # Check if it has opinion content
            has_opinion = any(word in text.lower() for word in 
                           ["bullish", "bearish", "looks", "think", "ape", "buy", "moon", "gem"])
            
            if has_opinion or len(text) > 100:
                return {
                    "text": text[:500],
                    "source": msg.get("source_name", "Unknown"),
                    "is_discussion": has_opinion,
                }
        
        # Last resort: just return something
        if cluster.messages:
            msg = cluster.messages[-1]
            return {
                "text": msg.get("original_text", "No discussion captured")[:500],
                "source": msg.get("source_name", "Unknown"),
                "is_discussion": False,
            }
        
        return {"text": "", "source": "Unknown", "is_discussion": False}
    
    def _get_overall_sentiment(self, cluster: ClusterData) -> str:
        """Determine overall sentiment from counts"""
        total = cluster.sentiment_bullish + cluster.sentiment_bearish + cluster.sentiment_neutral
        if total == 0:
            return "neutral"
        
        if cluster.sentiment_bullish > cluster.sentiment_bearish * 2:
            return "bullish"
        elif cluster.sentiment_bearish > cluster.sentiment_bullish * 2:
            return "bearish"
        else:
            return "neutral"
    
    def _get_bullish_percent(self, cluster: ClusterData) -> float:
        """Get percentage of bullish sentiment"""
        total = cluster.sentiment_bullish + cluster.sentiment_bearish + cluster.sentiment_neutral
        if total == 0:
            return 50.0
        return (cluster.sentiment_bullish / total) * 100


# Singleton instance
ranking_service = RankingService()
