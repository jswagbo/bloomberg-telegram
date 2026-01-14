"""Source reputation update tasks"""

import asyncio
from datetime import datetime

from app.workers.celery_app import celery_app
from app.services.ranking.source_tracker import source_tracker
from app.services.memory.memory_service import memory_service
import structlog

logger = structlog.get_logger()


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.tasks.reputation_update.update_all_reputations")
def update_all_reputations():
    """Update all source reputations and persist to database"""
    return run_async(_update_all_reputations())


async def _update_all_reputations():
    """Async implementation for reputation updates"""
    logger.info("updating_source_reputations")
    
    updated = 0
    
    # Get all tracked sources
    for telegram_id, stats in source_tracker._sources.items():
        try:
            # Persist to database
            await memory_service.update_source_reputation(
                telegram_id=telegram_id,
                name=stats.name,
                source_type=stats.source_type,
                stats={
                    "total_calls": stats.total_calls,
                    "successful_calls": stats.successful_calls,
                    "failed_calls": stats.failed_calls,
                    "hit_rate": stats.hit_rate,
                    "avg_return": stats.avg_return,
                    "trust_score": stats.trust_score,
                    "speed_score": stats.speed_score,
                    "last_call": stats.last_call,
                }
            )
            updated += 1
            
        except Exception as e:
            logger.error("reputation_update_error", source=telegram_id, error=str(e))
    
    logger.info("reputation_update_complete", count=updated)
    return {"updated": updated}


@celery_app.task(name="app.workers.tasks.reputation_update.recalculate_source_stats")
def recalculate_source_stats(telegram_id: str):
    """Recalculate stats for a specific source from database"""
    return run_async(_recalculate_source_stats(telegram_id))


async def _recalculate_source_stats(telegram_id: str):
    """Async implementation for single source recalculation"""
    # This would fetch all calls from database and recalculate
    # For now, just trigger a score recalculation
    
    source = source_tracker._sources.get(telegram_id)
    if source:
        source_tracker._recalculate_scores(source)
        return {"status": "recalculated", "trust_score": source.trust_score}
    
    return {"status": "not_found"}
