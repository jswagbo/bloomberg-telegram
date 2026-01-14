"""Celery application configuration"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "bloomberg_telegram",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.message_processing",
        "app.workers.tasks.price_tracking",
        "app.workers.tasks.reputation_update",
        "app.workers.tasks.cleanup",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Process message queue every 2 seconds
        "process-message-queue": {
            "task": "app.workers.tasks.message_processing.process_message_queue",
            "schedule": 2.0,
        },
        
        # Update token prices every minute
        "update-token-prices": {
            "task": "app.workers.tasks.price_tracking.update_cluster_prices",
            "schedule": 60.0,
        },
        
        # Track call outcomes every 5 minutes
        "track-call-outcomes": {
            "task": "app.workers.tasks.price_tracking.track_call_outcomes",
            "schedule": 300.0,
        },
        
        # Update source reputations every 15 minutes
        "update-source-reputations": {
            "task": "app.workers.tasks.reputation_update.update_all_reputations",
            "schedule": 900.0,
        },
        
        # Archive old clusters every hour
        "archive-old-clusters": {
            "task": "app.workers.tasks.cleanup.archive_old_clusters",
            "schedule": 3600.0,
        },
        
        # Clean up old data daily at 3 AM
        "daily-cleanup": {
            "task": "app.workers.tasks.cleanup.daily_cleanup",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)
