"""Cleanup and archival tasks"""

import asyncio
from datetime import datetime, timedelta

from app.workers.celery_app import celery_app
from app.services.clustering.cluster_service import clustering_service
from app.services.memory.memory_service import memory_service
from app.core.config import settings
import structlog

logger = structlog.get_logger()


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.cleanup.archive_old_clusters")
def archive_old_clusters():
    """Archive clusters older than the active window"""
    return run_async(_archive_old_clusters())


async def _archive_old_clusters():
    """Async implementation for cluster archival"""
    logger.info("archiving_old_clusters")
    
    now = datetime.utcnow()
    window = timedelta(minutes=settings.cluster_window_minutes)
    archived = 0
    
    # Find old clusters
    clusters_to_archive = []
    
    for key, cluster in list(clustering_service._active_clusters.items()):
        if now - cluster.last_seen > window:
            clusters_to_archive.append((key, cluster))
    
    # Archive each cluster
    for key, cluster in clusters_to_archive:
        try:
            # Persist to database
            await memory_service.store_cluster({
                "id": cluster.id,
                "token_address": cluster.token_address,
                "token_symbol": cluster.token_symbol,
                "chain": cluster.chain,
                "first_seen": cluster.first_seen,
                "last_seen": cluster.last_seen,
                "peak_activity_time": cluster.peak_activity_time,
                "unique_sources": len(cluster.source_ids),
                "total_mentions": cluster.total_mentions,
                "unique_wallets": len(cluster.wallet_addresses),
                "mentions_per_minute": cluster.mentions_per_minute,
                "priority_score": cluster.priority_score,
                "urgency_score": cluster.urgency_score,
                "novelty_score": cluster.novelty_score,
                "confidence_score": cluster.confidence_score,
                "sentiment_bullish": cluster.sentiment_bullish,
                "sentiment_bearish": cluster.sentiment_bearish,
                "sentiment_neutral": cluster.sentiment_neutral,
                "source_ids": list(cluster.source_ids),
                "source_names": list(cluster.source_names),
                "wallet_addresses": list(cluster.wallet_addresses),
            })
            
            # Remove from active clusters
            del clustering_service._active_clusters[key]
            
            # Clean up minute buckets
            if cluster.id in clustering_service._minute_buckets:
                del clustering_service._minute_buckets[cluster.id]
            
            archived += 1
            
        except Exception as e:
            logger.error("cluster_archive_error", cluster_id=cluster.id, error=str(e))
    
    logger.info("clusters_archived", count=archived)
    return {"archived": archived}


@celery_app.task(name="app.workers.tasks.cleanup.daily_cleanup")
def daily_cleanup():
    """Daily cleanup of old data"""
    return run_async(_daily_cleanup())


async def _daily_cleanup():
    """Async implementation for daily cleanup"""
    logger.info("running_daily_cleanup")
    
    # Clean up old deduplication cache entries (handled by TTL)
    # Clean up old cluster data in database (keep last 30 days)
    # Clean up old message data (keep last 7 days)
    
    # For now, just log
    logger.info("daily_cleanup_complete")
    
    return {"status": "complete"}


@celery_app.task(name="app.workers.tasks.cleanup.clear_cache")
def clear_cache():
    """Clear all in-memory caches"""
    # Clear clustering cache
    clustering_service._active_clusters.clear()
    clustering_service._minute_buckets.clear()
    
    # Clear source tracker cache  
    source_tracker._sources.clear()
    
    logger.info("caches_cleared")
    return {"status": "cleared"}
