"""Source reputation tracking service"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from app.core.config import settings
import structlog

logger = structlog.get_logger()


@dataclass
class SourceStats:
    """In-memory source statistics"""
    telegram_id: str
    name: str
    source_type: str
    
    # Performance
    total_calls: int = 0
    successful_calls: int = 0  # +50% within 1h
    failed_calls: int = 0  # -30% within 1h
    
    # Returns
    total_return: float = 0.0
    returns: List[float] = field(default_factory=list)
    
    # Timing
    first_tracked: Optional[datetime] = None
    last_call: Optional[datetime] = None
    time_to_moves: List[float] = field(default_factory=list)  # seconds to price move
    
    # Computed scores
    hit_rate: float = 0.5  # Default 50%
    avg_return: float = 0.0
    speed_score: float = 50.0
    trust_score: float = 50.0
    
    # Flags
    is_flagged: bool = False
    flag_reason: Optional[str] = None


class SourceTracker:
    """Service for tracking source reputation"""
    
    # Thresholds
    SUCCESS_THRESHOLD = 0.5  # +50% return = success
    FAILURE_THRESHOLD = -0.3  # -30% return = failure
    MIN_CALLS_FOR_SCORE = 3  # Minimum calls before calculating real score
    
    def __init__(self):
        self._sources: Dict[str, SourceStats] = {}
    
    def get_or_create_source(
        self,
        telegram_id: str,
        name: str,
        source_type: str = "channel",
    ) -> SourceStats:
        """Get or create source stats"""
        if telegram_id not in self._sources:
            self._sources[telegram_id] = SourceStats(
                telegram_id=telegram_id,
                name=name,
                source_type=source_type,
                first_tracked=datetime.utcnow(),
            )
        return self._sources[telegram_id]
    
    def record_call(
        self,
        telegram_id: str,
        name: str,
        source_type: str,
        token_address: str,
        timestamp: datetime,
    ) -> SourceStats:
        """Record a new call from a source"""
        source = self.get_or_create_source(telegram_id, name, source_type)
        
        source.total_calls += 1
        source.last_call = timestamp
        
        logger.debug(
            "source_call_recorded",
            source_id=telegram_id,
            name=name,
            total_calls=source.total_calls,
        )
        
        return source
    
    def record_outcome(
        self,
        telegram_id: str,
        return_percent: float,
        time_to_move_seconds: Optional[float] = None,
    ):
        """Record the outcome of a call"""
        source = self._sources.get(telegram_id)
        if not source:
            return
        
        # Track return
        source.returns.append(return_percent)
        source.total_return += return_percent
        
        # Track timing
        if time_to_move_seconds is not None:
            source.time_to_moves.append(time_to_move_seconds)
        
        # Classify outcome
        if return_percent >= self.SUCCESS_THRESHOLD:
            source.successful_calls += 1
        elif return_percent <= self.FAILURE_THRESHOLD:
            source.failed_calls += 1
        
        # Recalculate scores
        self._recalculate_scores(source)
        
        logger.debug(
            "source_outcome_recorded",
            source_id=telegram_id,
            return_percent=return_percent,
            hit_rate=source.hit_rate,
            trust_score=source.trust_score,
        )
    
    def _recalculate_scores(self, source: SourceStats):
        """Recalculate all scores for a source"""
        # Hit rate
        if source.total_calls > 0:
            source.hit_rate = source.successful_calls / source.total_calls
        
        # Average return
        if source.returns:
            source.avg_return = sum(source.returns) / len(source.returns)
        
        # Speed score (based on time to move)
        if source.time_to_moves:
            avg_time = sum(source.time_to_moves) / len(source.time_to_moves)
            # Faster = better, normalize to 0-100
            # < 60s = 100, > 3600s = 0
            source.speed_score = max(0, min(100, 100 - (avg_time / 36)))
        
        # Trust score (composite)
        if source.total_calls >= self.MIN_CALLS_FOR_SCORE:
            # Weighted combination
            hit_component = source.hit_rate * 40  # 0-40
            return_component = min(source.avg_return / 5, 1) * 30  # 0-30 (cap at 500% avg)
            speed_component = source.speed_score * 0.2  # 0-20
            volume_component = min(source.total_calls / 50, 1) * 10  # 0-10 (cap at 50 calls)
            
            source.trust_score = hit_component + return_component + speed_component + volume_component
        else:
            # Default score for new sources
            source.trust_score = 50.0
        
        # Flag bad actors
        self._check_for_flags(source)
    
    def _check_for_flags(self, source: SourceStats):
        """Check if source should be flagged"""
        source.is_flagged = False
        source.flag_reason = None
        
        # Flag if hit rate is very low with enough data
        if source.total_calls >= 10 and source.hit_rate < 0.15:
            source.is_flagged = True
            source.flag_reason = f"Very low hit rate: {source.hit_rate:.0%}"
        
        # Flag if many rugs
        if source.failed_calls >= 5 and source.failed_calls / max(source.total_calls, 1) > 0.5:
            source.is_flagged = True
            source.flag_reason = f"High failure rate: {source.failed_calls} failures"
        
        # Flag if average return is negative
        if source.total_calls >= 5 and source.avg_return < -0.2:
            source.is_flagged = True
            source.flag_reason = f"Negative average return: {source.avg_return:.0%}"
    
    def get_source_reputation(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """Get source reputation as dictionary"""
        source = self._sources.get(telegram_id)
        if not source:
            return None
        
        return {
            "telegram_id": source.telegram_id,
            "name": source.name,
            "source_type": source.source_type,
            "metrics": {
                "total_calls": source.total_calls,
                "successful_calls": source.successful_calls,
                "failed_calls": source.failed_calls,
                "hit_rate": source.hit_rate,
                "avg_return": source.avg_return,
            },
            "scores": {
                "speed": source.speed_score,
                "trust": source.trust_score,
            },
            "timing": {
                "first_tracked": source.first_tracked.isoformat() if source.first_tracked else None,
                "last_call": source.last_call.isoformat() if source.last_call else None,
            },
            "flags": {
                "is_flagged": source.is_flagged,
                "reason": source.flag_reason,
            },
        }
    
    def get_leaderboard(
        self,
        min_calls: int = 5,
        limit: int = 20,
        include_flagged: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get source leaderboard sorted by trust score"""
        sources = []
        
        for source in self._sources.values():
            if source.total_calls < min_calls:
                continue
            if not include_flagged and source.is_flagged:
                continue
            
            sources.append(self.get_source_reputation(source.telegram_id))
        
        # Sort by trust score
        sources.sort(key=lambda s: s["scores"]["trust"], reverse=True)
        
        return sources[:limit]
    
    def get_flagged_sources(self) -> List[Dict[str, Any]]:
        """Get all flagged sources"""
        flagged = []
        
        for source in self._sources.values():
            if source.is_flagged:
                flagged.append(self.get_source_reputation(source.telegram_id))
        
        return flagged
    
    def get_average_trust_score(self, source_ids: List[str]) -> float:
        """Get average trust score for a list of sources"""
        if not source_ids:
            return 50.0  # Default
        
        scores = []
        for source_id in source_ids:
            source = self._sources.get(source_id)
            if source:
                scores.append(source.trust_score)
        
        if not scores:
            return 50.0
        
        return sum(scores) / len(scores)


# Singleton instance
source_tracker = SourceTracker()
