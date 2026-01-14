"""Redis connection and utilities"""

import json
from typing import Any, Optional, List
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import settings


class RedisManager:
    """Redis connection manager"""
    
    _instance: Optional["RedisManager"] = None
    _redis: Optional[Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self) -> Redis:
        """Connect to Redis"""
        if self._redis is None:
            self._redis = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    async def get_redis(self) -> Redis:
        """Get Redis connection"""
        if self._redis is None:
            await self.connect()
        return self._redis


redis_manager = RedisManager()


async def get_redis() -> Redis:
    """Dependency to get Redis connection"""
    return await redis_manager.get_redis()


class MessageQueue:
    """Message queue for processing"""
    
    QUEUE_KEY = "telegram:messages:queue"
    PRIORITY_QUEUE_KEY = "telegram:messages:priority"
    PROCESSING_KEY = "telegram:messages:processing"
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def push(self, message: dict, priority: bool = False):
        """Push message to queue"""
        key = self.PRIORITY_QUEUE_KEY if priority else self.QUEUE_KEY
        await self.redis.lpush(key, json.dumps(message))
    
    async def pop_batch(self, batch_size: int = 100) -> List[dict]:
        """Pop a batch of messages from queue"""
        messages = []
        
        # First check priority queue
        for _ in range(batch_size):
            msg = await self.redis.rpop(self.PRIORITY_QUEUE_KEY)
            if msg:
                messages.append(json.loads(msg))
            else:
                break
        
        # Then check regular queue
        remaining = batch_size - len(messages)
        for _ in range(remaining):
            msg = await self.redis.rpop(self.QUEUE_KEY)
            if msg:
                messages.append(json.loads(msg))
            else:
                break
        
        return messages
    
    async def queue_size(self) -> int:
        """Get total queue size"""
        priority_size = await self.redis.llen(self.PRIORITY_QUEUE_KEY)
        regular_size = await self.redis.llen(self.QUEUE_KEY)
        return priority_size + regular_size


class DeduplicationCache:
    """Cache for message deduplication"""
    
    PREFIX = "dedup:"
    
    def __init__(self, redis_client: Redis, window_minutes: int = 5):
        self.redis = redis_client
        self.window = timedelta(minutes=window_minutes)
    
    async def is_duplicate(self, message_hash: str) -> bool:
        """Check if message is a duplicate"""
        key = f"{self.PREFIX}{message_hash}"
        exists = await self.redis.exists(key)
        return bool(exists)
    
    async def mark_seen(self, message_hash: str):
        """Mark message as seen"""
        key = f"{self.PREFIX}{message_hash}"
        await self.redis.setex(key, self.window, "1")


class ClusterCache:
    """Cache for active signal clusters"""
    
    PREFIX = "cluster:"
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def get_cluster(self, cluster_id: str) -> Optional[dict]:
        """Get cluster data"""
        data = await self.redis.get(f"{self.PREFIX}{cluster_id}")
        if data:
            return json.loads(data)
        return None
    
    async def set_cluster(self, cluster_id: str, data: dict, ttl_minutes: int = 60):
        """Set cluster data"""
        await self.redis.setex(
            f"{self.PREFIX}{cluster_id}",
            timedelta(minutes=ttl_minutes),
            json.dumps(data)
        )
    
    async def get_active_clusters(self) -> List[dict]:
        """Get all active clusters"""
        keys = await self.redis.keys(f"{self.PREFIX}*")
        clusters = []
        for key in keys:
            data = await self.redis.get(key)
            if data:
                clusters.append(json.loads(data))
        return clusters


class RateLimiter:
    """Rate limiter for API calls"""
    
    PREFIX = "ratelimit:"
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is allowed"""
        redis_key = f"{self.PREFIX}{key}"
        current = await self.redis.get(redis_key)
        
        if current is None:
            await self.redis.setex(redis_key, window_seconds, 1)
            return True
        
        if int(current) >= max_requests:
            return False
        
        await self.redis.incr(redis_key)
        return True
