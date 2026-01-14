"""Signals API routes - Clusters and Why Moving"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_optional_user
from app.models.user import User
from app.services.clustering.cluster_service import clustering_service
from app.services.ranking.ranking_service import ranking_service
from app.services.why_moving.engine import why_moving_service

router = APIRouter()


class SignalResponse(BaseModel):
    cluster_id: str
    token: dict
    score: float
    metrics: dict
    sentiment: dict
    timing: dict
    top_signal: dict
    sources: List[str]
    wallets: List[str]


class ClusterDetailResponse(BaseModel):
    id: str
    token: dict
    timing: dict
    metrics: dict
    scores: dict
    sentiment: dict
    sources: List[str]
    wallets: List[str]
    top_messages: List[dict]
    price: dict


class WhyMovingResponse(BaseModel):
    token: dict
    price_change: dict
    reasons: List[dict]
    timeline: List[dict]
    confidence: float
    summary: str


@router.get("/feed", response_model=List[SignalResponse])
async def get_signal_feed(
    chain: Optional[str] = None,
    min_score: float = Query(default=0, ge=0, le=100),
    min_sources: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: Optional[str] = Depends(get_optional_user),
):
    """
    Get the main signal feed.
    Returns ranked clusters sorted by priority score.
    """
    # Get active clusters
    clusters = clustering_service.get_active_clusters(
        min_sources=min_sources,
        min_mentions=1,
        chain=chain,
        limit=limit * 2,  # Get more to filter
    )
    
    # Filter and rank
    filtered = ranking_service.filter_clusters(
        clusters,
        min_score=min_score,
        min_sources=min_sources,
        chains=[chain] if chain else None,
    )
    
    # Get top signals
    signals = ranking_service.get_top_signals(
        filtered,
        limit=limit,
    )
    
    return signals


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster_detail(
    cluster_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get detailed cluster information"""
    # Find cluster by ID
    for cluster in clustering_service._active_clusters.values():
        if cluster.id == cluster_id:
            return clustering_service.to_dict(cluster)
    
    raise HTTPException(
        status_code=404,
        detail="Cluster not found",
    )


@router.get("/token/{chain}/{token_address}", response_model=ClusterDetailResponse)
async def get_token_cluster(
    chain: str,
    token_address: str,
    user_id: Optional[str] = Depends(get_optional_user),
):
    """Get cluster for a specific token"""
    cluster = clustering_service.get_cluster_by_token(
        token_address=token_address,
        chain=chain,
    )
    
    if not cluster:
        raise HTTPException(
            status_code=404,
            detail="No active cluster for this token",
        )
    
    return clustering_service.to_dict(cluster)


@router.get("/why-moving/{chain}/{token_address}", response_model=WhyMovingResponse)
async def why_is_this_moving(
    chain: str,
    token_address: str,
    window_minutes: int = Query(default=30, ge=5, le=120),
    current_user: User = Depends(get_current_user),
):
    """
    Explain why a token is moving.
    Correlates Telegram signals, whale activity, and price data.
    """
    explanation = await why_moving_service.explain_movement(
        token_address=token_address,
        chain=chain,
        window_minutes=window_minutes,
    )
    
    return why_moving_service.to_dict(explanation)


@router.get("/trending", response_model=List[SignalResponse])
async def get_trending_signals(
    chain: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=50),
    user_id: Optional[str] = Depends(get_optional_user),
):
    """
    Get trending signals (highest velocity).
    """
    clusters = clustering_service.get_active_clusters(
        min_sources=2,
        min_mentions=3,
        chain=chain,
        sort_by="mentions_per_minute",
        limit=limit,
    )
    
    return ranking_service.get_top_signals(clusters, limit=limit)


@router.get("/new", response_model=List[SignalResponse])
async def get_new_signals(
    chain: Optional[str] = None,
    max_age_minutes: int = Query(default=10, ge=1, le=60),
    limit: int = Query(default=10, ge=1, le=50),
    user_id: Optional[str] = Depends(get_optional_user),
):
    """
    Get newest signals (highest novelty).
    """
    clusters = clustering_service.get_active_clusters(
        min_sources=1,
        min_mentions=1,
        chain=chain,
        sort_by="novelty_score",
        limit=limit * 2,
    )
    
    # Filter by age
    filtered = ranking_service.filter_clusters(
        clusters,
        max_age_minutes=max_age_minutes,
    )
    
    return ranking_service.get_top_signals(filtered, limit=limit)


@router.get("/whale-alerts", response_model=List[SignalResponse])
async def get_whale_alerts(
    chain: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=50),
    user_id: Optional[str] = Depends(get_optional_user),
):
    """
    Get signals with whale wallet activity.
    """
    clusters = clustering_service.get_active_clusters(
        min_sources=1,
        chain=chain,
        limit=50,
    )
    
    # Filter to only clusters with wallets
    whale_clusters = [c for c in clusters if len(c.wallet_addresses) > 0]
    
    # Sort by wallet count
    whale_clusters.sort(key=lambda c: len(c.wallet_addresses), reverse=True)
    
    return ranking_service.get_top_signals(whale_clusters, limit=limit)
