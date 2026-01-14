"""Sources API routes - Caller reputation tracking"""

from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_optional_user
from app.models.user import User
from app.services.ranking.source_tracker import source_tracker
from app.services.memory.queries import query_service

router = APIRouter()


class SourceReputationResponse(BaseModel):
    telegram_id: str
    name: str
    source_type: str
    metrics: dict
    scores: dict
    timing: dict
    flags: dict


class LeaderboardEntry(BaseModel):
    rank: int
    telegram_id: str
    name: str
    source_type: str
    metrics: dict
    scores: dict
    flags: dict


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_source_leaderboard(
    min_calls: int = Query(default=5, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    include_flagged: bool = False,
    user_id: Optional[str] = Depends(get_optional_user),
):
    """
    Get source leaderboard sorted by trust score.
    Shows callers ranked by their hit rate and performance.
    """
    leaderboard = source_tracker.get_leaderboard(
        min_calls=min_calls,
        limit=limit,
        include_flagged=include_flagged,
    )
    
    return [
        LeaderboardEntry(rank=i + 1, **entry)
        for i, entry in enumerate(leaderboard)
    ]


@router.get("/flagged")
async def get_flagged_sources(
    current_user: User = Depends(get_current_user),
):
    """Get list of flagged/suspicious sources"""
    return {"flagged": source_tracker.get_flagged_sources()}


@router.get("/reputation/{telegram_id}", response_model=SourceReputationResponse)
async def get_source_reputation(
    telegram_id: str,
    user_id: Optional[str] = Depends(get_optional_user),
):
    """Get detailed reputation for a specific source"""
    reputation = source_tracker.get_source_reputation(telegram_id)
    
    if not reputation:
        return {
            "telegram_id": telegram_id,
            "name": "Unknown",
            "source_type": "unknown",
            "metrics": {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "hit_rate": 0.5,
                "avg_return": 0,
            },
            "scores": {
                "speed": 50,
                "trust": 50,
            },
            "timing": {
                "first_tracked": None,
                "last_call": None,
            },
            "flags": {
                "is_flagged": False,
                "reason": None,
            },
        }
    
    return reputation


@router.get("/performance/{telegram_id}")
async def get_source_performance(
    telegram_id: str,
    timeframe: str = Query(default="30d", regex=r"^\d+d$"),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed performance history for a source.
    Shows all calls and their outcomes.
    """
    result = await query_service.query(
        query_type="source_performance",
        source_id=telegram_id,
        timeframe=timeframe,
    )
    return result
