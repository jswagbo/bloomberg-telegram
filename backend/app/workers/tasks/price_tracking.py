"""Price tracking and outcome measurement tasks"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from celery import shared_task

from app.workers.celery_app import celery_app
from app.services.clustering.cluster_service import clustering_service
from app.services.ranking.source_tracker import source_tracker
from app.services.external_apis.price_service import price_service
import structlog

logger = structlog.get_logger()


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.price_tracking.update_cluster_prices")
def update_cluster_prices():
    """Update prices for all active clusters"""
    return run_async(_update_cluster_prices())


async def _update_cluster_prices():
    """Async implementation for price updates"""
    clusters = clustering_service.get_active_clusters(limit=100)
    
    if not clusters:
        return {"updated": 0}
    
    # Collect tokens to fetch
    tokens_to_fetch = []
    for cluster in clusters:
        if cluster.token_address:
            tokens_to_fetch.append({
                "address": cluster.token_address,
                "chain": cluster.chain,
            })
    
    if not tokens_to_fetch:
        return {"updated": 0}
    
    # Batch fetch prices
    try:
        prices = await price_service.get_multiple_prices(tokens_to_fetch)
        
        updated = 0
        for cluster in clusters:
            if cluster.token_address and cluster.token_address in prices:
                price_data = prices[cluster.token_address]
                cluster.price_current = price_data.get("price_usd")
                
                if cluster.price_at_first_mention is None:
                    cluster.price_at_first_mention = cluster.price_current
                
                updated += 1
        
        logger.info("cluster_prices_updated", count=updated)
        return {"updated": updated}
        
    except Exception as e:
        logger.error("price_update_error", error=str(e))
        return {"updated": 0, "error": str(e)}


@celery_app.task(name="app.workers.tasks.price_tracking.track_call_outcomes")
def track_call_outcomes():
    """Track outcomes of calls for source reputation"""
    return run_async(_track_call_outcomes())


async def _track_call_outcomes():
    """Async implementation for outcome tracking"""
    # This would track calls that are 1h and 24h old
    # and update their outcomes based on price performance
    
    # For now, a simplified version
    logger.info("tracking_call_outcomes")
    
    # Get clusters that are at least 1 hour old
    clusters = clustering_service.get_active_clusters(limit=200)
    now = datetime.utcnow()
    
    outcomes_tracked = 0
    
    for cluster in clusters:
        age_hours = (now - cluster.first_seen).total_seconds() / 3600
        
        # Track 1-hour outcomes
        if 1.0 <= age_hours < 1.1:  # Around 1 hour mark
            if cluster.price_at_first_mention and cluster.price_current:
                return_pct = (cluster.price_current - cluster.price_at_first_mention) / cluster.price_at_first_mention
                
                # Update source tracker for each source
                for source_id in cluster.source_ids:
                    source_tracker.record_outcome(
                        telegram_id=source_id,
                        return_percent=return_pct,
                        time_to_move_seconds=(now - cluster.first_seen).total_seconds(),
                    )
                    outcomes_tracked += 1
    
    logger.info("outcomes_tracked", count=outcomes_tracked)
    return {"tracked": outcomes_tracked}


@celery_app.task(name="app.workers.tasks.price_tracking.fetch_token_price")
def fetch_token_price(token_address: str, chain: str = "solana"):
    """Fetch price for a single token"""
    return run_async(_fetch_token_price(token_address, chain))


async def _fetch_token_price(token_address: str, chain: str):
    """Async implementation for single token price fetch"""
    try:
        price_data = await price_service.get_token_price(token_address, chain)
        return price_data
    except Exception as e:
        logger.error("price_fetch_error", token=token_address, error=str(e))
        return None
