"""Message processing tasks"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any

from celery import shared_task

from app.workers.celery_app import celery_app
from app.core.redis import get_redis, MessageQueue, DeduplicationCache
from app.services.extraction.extractor import extraction_service
from app.services.clustering.cluster_service import clustering_service
from app.services.clustering.deduplication import deduplication_service
from app.services.ranking.source_tracker import source_tracker
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


@celery_app.task(name="app.workers.tasks.message_processing.process_message_queue")
def process_message_queue():
    """Process messages from the Redis queue"""
    return run_async(_process_message_queue())


async def _process_message_queue():
    """Async implementation of message queue processing"""
    redis = await get_redis()
    queue = MessageQueue(redis)
    dedup_cache = DeduplicationCache(redis, settings.dedup_window_minutes)
    
    # Get batch of messages
    messages = await queue.pop_batch(settings.batch_size)
    
    if not messages:
        return {"processed": 0}
    
    logger.info("processing_message_batch", count=len(messages))
    
    processed_count = 0
    
    for msg in messages:
        try:
            # Check for duplicates
            is_dup, _ = await deduplication_service.is_duplicate(
                msg.get("text", ""),
                msg.get("source_id"),
            )
            
            if is_dup:
                continue
            
            # Mark as seen
            await deduplication_service.mark_seen(msg.get("text", ""))
            
            # Extract entities
            processed = extraction_service.process_message(
                message_id=msg.get("id", ""),
                source_id=msg.get("source_id", ""),
                source_name=msg.get("source_name", ""),
                text=msg.get("text", ""),
                timestamp=datetime.fromisoformat(msg.get("timestamp", datetime.utcnow().isoformat())),
            )
            
            # Update clusters for each token
            for token in processed.tokens:
                cluster = clustering_service.add_message_to_cluster(
                    message={
                        "id": processed.id,
                        "source_id": processed.source_id,
                        "source_name": processed.source_name,
                        "timestamp": processed.timestamp,
                        "original_text": processed.original_text,
                        "tokens": processed.tokens,
                        "wallets": processed.wallets,
                        "sentiment": processed.sentiment,
                    },
                    token_address=token.get("address"),
                    token_symbol=token.get("symbol"),
                    chain=token.get("chain", "solana"),
                )
                
                # Track as call if classified
                if processed.classification == "call":
                    source_tracker.record_call(
                        telegram_id=processed.source_id,
                        name=processed.source_name,
                        source_type="channel",
                        token_address=token.get("address") or token.get("symbol", ""),
                        timestamp=processed.timestamp,
                    )
            
            processed_count += 1
            
        except Exception as e:
            logger.error("message_processing_error", error=str(e), message_id=msg.get("id"))
    
    logger.info("batch_processing_complete", processed=processed_count, total=len(messages))
    
    return {"processed": processed_count, "total": len(messages)}


@celery_app.task(name="app.workers.tasks.message_processing.process_single_message")
def process_single_message(message: Dict[str, Any]):
    """Process a single message immediately (for high-priority sources)"""
    return run_async(_process_single_message(message))


async def _process_single_message(msg: Dict[str, Any]):
    """Async implementation for single message processing"""
    try:
        # Check for duplicates
        is_dup, _ = await deduplication_service.is_duplicate(
            msg.get("text", ""),
            msg.get("source_id"),
        )
        
        if is_dup:
            return {"status": "duplicate"}
        
        # Mark as seen
        await deduplication_service.mark_seen(msg.get("text", ""))
        
        # Process
        processed = extraction_service.process_message(
            message_id=msg.get("id", ""),
            source_id=msg.get("source_id", ""),
            source_name=msg.get("source_name", ""),
            text=msg.get("text", ""),
            timestamp=datetime.fromisoformat(msg.get("timestamp", datetime.utcnow().isoformat())),
        )
        
        # Update clusters
        updated_clusters = []
        for token in processed.tokens:
            cluster = clustering_service.add_message_to_cluster(
                message={
                    "id": processed.id,
                    "source_id": processed.source_id,
                    "source_name": processed.source_name,
                    "timestamp": processed.timestamp,
                    "original_text": processed.original_text,
                    "tokens": processed.tokens,
                    "wallets": processed.wallets,
                    "sentiment": processed.sentiment,
                },
                token_address=token.get("address"),
                token_symbol=token.get("symbol"),
                chain=token.get("chain", "solana"),
            )
            updated_clusters.append(cluster.id)
        
        return {
            "status": "processed",
            "tokens_found": len(processed.tokens),
            "clusters_updated": updated_clusters,
        }
        
    except Exception as e:
        logger.error("single_message_processing_error", error=str(e))
        return {"status": "error", "error": str(e)}
