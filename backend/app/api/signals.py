"""Signals API routes - Clusters and Why Moving"""

from typing import Optional, List
from datetime import datetime
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_optional_user
from app.models.user import User
from app.services.clustering.cluster_service import clustering_service
from app.services.ranking.ranking_service import ranking_service
from app.services.why_moving.engine import why_moving_service
from app.services.extraction.sentiment import sentiment_analyzer
from app.services.llm.summarizer import llm_summarizer
import structlog

logger = structlog.get_logger()

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


class CoinInsightsResponse(BaseModel):
    """Comprehensive coin insights"""
    token: dict
    price_data: dict
    quantitative: dict
    qualitative: dict
    chatter: dict
    risk_assessment: dict
    summary: str


@router.get("/insights/{chain}/{token_address}")
async def get_coin_insights(
    chain: str,
    token_address: str,
    user_id: Optional[str] = Depends(get_optional_user),
):
    """
    Get comprehensive insights for a token including:
    - Price data from DexScreener
    - Quantitative metrics (mentions, sources, velocity)
    - Qualitative analysis (sentiment, risk, quality)
    - Chatter summary with key quotes
    """
    # Get cluster for this token
    cluster = clustering_service.get_cluster_by_token(
        token_address=token_address,
        chain=chain,
    )
    
    # Fetch price data from DexScreener
    price_data = await fetch_dexscreener_data(token_address)
    
    # If no cluster, return minimal data with price info
    if not cluster:
        return {
            "token": {
                "address": token_address,
                "symbol": price_data.get("symbol"),
                "name": price_data.get("name"),
                "chain": chain,
            },
            "price_data": price_data,
            "quantitative": {
                "total_mentions": 0,
                "unique_sources": 0,
                "unique_wallets": 0,
                "velocity": 0,
                "first_seen": None,
                "last_seen": None,
            },
            "qualitative": {
                "overall_sentiment": "neutral",
                "sentiment_score": 0,
                "bullish_percent": 50,
                "risk_score": 50,
                "quality_score": 50,
                "risk_level": "medium",
                "quality_level": "medium",
            },
            "chatter": {
                "total_messages": 0,
                "bullish_messages": [],
                "bearish_messages": [],
                "key_quotes": [],
                "risk_factors": [],
                "quality_factors": [],
                "themes": [],
            },
            "risk_assessment": {
                "score": 50,
                "level": "medium",
                "factors": [],
                "warnings": [],
            },
            "summary": "No chatter data available for this token yet.",
        }
    
    # Analyze all messages in the cluster
    messages = cluster.messages
    all_risk_factors = []
    all_quality_factors = []
    bullish_messages = []
    bearish_messages = []
    all_signals = []
    total_risk = 0
    total_quality = 0
    
    for msg in messages:
        text = msg.get("original_text", "")
        if not text:
            continue
            
        # Get insights for each message
        insights = sentiment_analyzer.get_message_insights(text)
        
        total_risk += insights["risk_score"]
        total_quality += insights["quality_score"]
        all_risk_factors.extend(insights["risk_factors"])
        all_quality_factors.extend(insights["quality_factors"])
        all_signals.extend(insights["signals"])
        
        # Categorize messages
        if insights["sentiment"] == "bullish":
            bullish_messages.append({
                "text": text[:200],
                "source": msg.get("source_name", "Unknown"),
                "sentiment_score": insights["sentiment_score"],
                "quality_score": insights["quality_score"],
            })
        elif insights["sentiment"] == "bearish":
            bearish_messages.append({
                "text": text[:200],
                "source": msg.get("source_name", "Unknown"),
                "sentiment_score": insights["sentiment_score"],
                "risk_score": insights["risk_score"],
            })
    
    # Calculate averages
    num_messages = max(len(messages), 1)
    avg_risk = total_risk / num_messages
    avg_quality = total_quality / num_messages
    
    # Count factor frequencies
    risk_factor_counts = {}
    for factor in all_risk_factors:
        risk_factor_counts[factor] = risk_factor_counts.get(factor, 0) + 1
    
    quality_factor_counts = {}
    for factor in all_quality_factors:
        quality_factor_counts[factor] = quality_factor_counts.get(factor, 0) + 1
    
    # Get top factors
    top_risk_factors = sorted(risk_factor_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_quality_factors = sorted(quality_factor_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Extract themes from signals
    signal_counts = {}
    for signal in all_signals:
        clean_signal = signal.lstrip("+-~")
        signal_counts[clean_signal] = signal_counts.get(clean_signal, 0) + 1
    top_themes = sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Select key quotes (high quality bullish, high risk bearish)
    bullish_messages.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    bearish_messages.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    
    key_quotes = []
    for msg in bullish_messages[:3]:
        key_quotes.append({
            "text": msg["text"],
            "source": msg["source"],
            "type": "bullish",
            "highlight": "High conviction alpha",
        })
    for msg in bearish_messages[:2]:
        key_quotes.append({
            "text": msg["text"],
            "source": msg["source"],
            "type": "bearish",
            "highlight": "Risk warning",
        })
    
    # Generate warnings based on risk factors
    warnings = []
    if avg_risk > 60:
        warnings.append("High risk signals detected in community chatter")
    if "rug" in all_risk_factors or "scam" in all_risk_factors:
        warnings.append("Potential scam/rug warnings in messages")
    if "dev sold" in all_risk_factors or "dev dumped" in all_risk_factors:
        warnings.append("Developer selling activity mentioned")
    if cluster.sentiment_bearish > cluster.sentiment_bullish * 2:
        warnings.append("Predominantly bearish sentiment")
    
    # Calculate sentiment percentages
    total_sentiment = cluster.sentiment_bullish + cluster.sentiment_bearish + cluster.sentiment_neutral
    bullish_percent = (cluster.sentiment_bullish / max(total_sentiment, 1)) * 100
    
    # Prepare sentiment data for LLM
    sentiment_data = {
        "overall_sentiment": "bullish" if bullish_percent > 60 else "bearish" if bullish_percent < 40 else "neutral",
        "bullish_percent": bullish_percent,
        "risk_score": avg_risk,
        "quality_score": avg_quality,
        "risk_factors": [f for f, c in top_risk_factors],
        "quality_factors": [f for f, c in top_quality_factors],
    }
    
    # Generate AI summary using LLM
    ai_summary = await llm_summarizer.generate_token_summary(
        token_symbol=cluster.token_symbol,
        token_address=token_address,
        chain=chain,
        messages=messages,
        sentiment_data=sentiment_data,
        price_data=price_data,
    )
    
    # Fallback summary if LLM fails
    basic_summary = generate_insight_summary(
        cluster, price_data, avg_risk, avg_quality, bullish_percent, warnings
    )
    
    return {
        "token": {
            "address": token_address,
            "symbol": cluster.token_symbol or price_data.get("symbol"),
            "name": price_data.get("name"),
            "chain": chain,
        },
        "price_data": price_data,
        "quantitative": {
            "total_mentions": cluster.total_mentions,
            "unique_sources": len(cluster.source_ids),
            "unique_wallets": len(cluster.wallet_addresses),
            "velocity": cluster.mentions_per_minute,
            "peak_velocity": cluster.peak_mentions_per_minute,
            "first_seen": cluster.first_seen.isoformat(),
            "last_seen": cluster.last_seen.isoformat(),
            "age_minutes": (datetime.utcnow() - cluster.first_seen).total_seconds() / 60,
        },
        "qualitative": {
            "overall_sentiment": "bullish" if bullish_percent > 60 else "bearish" if bullish_percent < 40 else "neutral",
            "sentiment_score": (bullish_percent - 50) / 50,  # -1 to 1
            "bullish_percent": bullish_percent,
            "bullish_count": cluster.sentiment_bullish,
            "bearish_count": cluster.sentiment_bearish,
            "neutral_count": cluster.sentiment_neutral,
            "risk_score": avg_risk,
            "quality_score": avg_quality,
            "risk_level": "high" if avg_risk > 60 else "medium" if avg_risk > 30 else "low",
            "quality_level": "high" if avg_quality > 70 else "medium" if avg_quality > 40 else "low",
        },
        "chatter": {
            "total_messages": len(messages),
            "bullish_messages": bullish_messages[:5],
            "bearish_messages": bearish_messages[:5],
            "key_quotes": key_quotes,
            "risk_factors": [{"factor": f, "count": c} for f, c in top_risk_factors],
            "quality_factors": [{"factor": f, "count": c} for f, c in top_quality_factors],
            "themes": [{"theme": t, "count": c} for t, c in top_themes],
            "sources": list(cluster.source_names)[:10],
        },
        "risk_assessment": {
            "score": avg_risk,
            "level": "high" if avg_risk > 60 else "medium" if avg_risk > 30 else "low",
            "factors": [{"factor": f, "count": c} for f, c in top_risk_factors],
            "warnings": warnings,
        },
        "summary": basic_summary,
        "ai_analysis": ai_summary,
    }


async def fetch_dexscreener_data(token_address: str) -> dict:
    """Fetch token data from DexScreener API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}")
            
            if response.status_code != 200:
                return {}
            
            data = response.json()
            if not data.get("pairs"):
                return {}
            
            # Get the most liquid pair
            pairs = sorted(data["pairs"], key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
            pair = pairs[0] if pairs else {}
            
            base_token = pair.get("baseToken", {})
            
            return {
                "symbol": base_token.get("symbol"),
                "name": base_token.get("name"),
                "price_usd": float(pair.get("priceUsd", 0) or 0),
                "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0) or 0),
                "price_change_1h": float(pair.get("priceChange", {}).get("h1", 0) or 0),
                "price_change_5m": float(pair.get("priceChange", {}).get("m5", 0) or 0),
                "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                "market_cap": float(pair.get("marketCap", 0) or 0) if pair.get("marketCap") else None,
                "fdv": float(pair.get("fdv", 0) or 0) if pair.get("fdv") else None,
                "pair_address": pair.get("pairAddress"),
                "dex": pair.get("dexId"),
                "url": pair.get("url"),
            }
    except Exception as e:
        logger.error("dexscreener_fetch_error", error=str(e), token=token_address)
        return {}


def generate_insight_summary(cluster, price_data, risk_score, quality_score, bullish_percent, warnings) -> str:
    """Generate a natural language summary of the token insights"""
    parts = []
    
    # Token identification
    symbol = cluster.token_symbol or "This token"
    
    # Mention activity
    if cluster.total_mentions >= 10:
        parts.append(f"{symbol} has significant chatter with {cluster.total_mentions} mentions from {len(cluster.source_ids)} sources.")
    elif cluster.total_mentions >= 5:
        parts.append(f"{symbol} has moderate activity with {cluster.total_mentions} mentions from {len(cluster.source_ids)} sources.")
    else:
        parts.append(f"{symbol} has limited chatter with {cluster.total_mentions} mentions.")
    
    # Sentiment
    if bullish_percent > 70:
        parts.append("Community sentiment is strongly bullish.")
    elif bullish_percent > 55:
        parts.append("Community sentiment leans bullish.")
    elif bullish_percent < 30:
        parts.append("Community sentiment is bearish.")
    elif bullish_percent < 45:
        parts.append("Community sentiment leans bearish.")
    else:
        parts.append("Community sentiment is mixed.")
    
    # Quality assessment
    if quality_score > 70:
        parts.append("The quality of alpha shared is high, with conviction-based calls.")
    elif quality_score > 50:
        parts.append("The chatter quality is moderate.")
    else:
        parts.append("The chatter appears to be mostly speculative.")
    
    # Risk assessment
    if risk_score > 60:
        parts.append("⚠️ HIGH RISK: Multiple warning signals detected.")
    elif risk_score > 40:
        parts.append("Moderate risk signals present - proceed with caution.")
    else:
        parts.append("Risk signals are low.")
    
    # Warnings
    if warnings:
        parts.append(f"Key concerns: {'; '.join(warnings[:2])}")
    
    # Price context if available
    if price_data.get("price_change_24h"):
        change = price_data["price_change_24h"]
        if change > 50:
            parts.append(f"Price is up {change:.1f}% in 24h - may be extended.")
        elif change > 10:
            parts.append(f"Price is up {change:.1f}% in 24h.")
        elif change < -30:
            parts.append(f"Price is down {abs(change):.1f}% in 24h - potential capitulation.")
        elif change < -10:
            parts.append(f"Price is down {abs(change):.1f}% in 24h.")
    
    return " ".join(parts)
