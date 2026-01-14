"""Message deduplication service"""

from typing import List, Optional, Set, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from app.core.security import hash_message
from app.core.redis import DeduplicationCache, get_redis
from app.services.clustering.embeddings import embedding_service
from app.core.config import settings
import structlog

logger = structlog.get_logger()


class DeduplicationService:
    """Service for deduplicating messages"""
    
    def __init__(self):
        self._recent_hashes: Dict[str, datetime] = {}
        self._hash_window = timedelta(minutes=settings.dedup_window_minutes)
        self._similarity_threshold = settings.similarity_threshold
        self._recent_embeddings: List[tuple] = []  # (hash, embedding, timestamp)
        self._max_embeddings_cache = 1000
    
    async def is_duplicate(
        self,
        text: str,
        source_id: Optional[str] = None,
        use_semantic: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if message is a duplicate.
        
        Returns:
            (is_duplicate, duplicate_hash if found)
        """
        # Clean old entries
        self._clean_old_entries()
        
        # 1. Check exact hash match
        text_hash = hash_message(text)
        
        if text_hash in self._recent_hashes:
            logger.debug("exact_duplicate_found", hash=text_hash[:16])
            return True, text_hash
        
        # 2. Check semantic similarity if enabled
        if use_semantic and len(text) > 20:  # Skip very short messages
            is_semantic_dup, similar_hash = await self._check_semantic_duplicate(text)
            if is_semantic_dup:
                logger.debug("semantic_duplicate_found", similar_hash=similar_hash[:16] if similar_hash else None)
                return True, similar_hash
        
        return False, None
    
    async def mark_seen(self, text: str, store_embedding: bool = True):
        """Mark a message as seen"""
        text_hash = hash_message(text)
        self._recent_hashes[text_hash] = datetime.utcnow()
        
        if store_embedding and len(text) > 20:
            embedding = embedding_service.embed_text(text)
            self._recent_embeddings.append((text_hash, embedding, datetime.utcnow()))
            
            # Trim if too many
            if len(self._recent_embeddings) > self._max_embeddings_cache:
                self._recent_embeddings = self._recent_embeddings[-self._max_embeddings_cache:]
    
    async def _check_semantic_duplicate(self, text: str) -> tuple[bool, Optional[str]]:
        """Check for semantically similar messages"""
        if not self._recent_embeddings:
            return False, None
        
        # Generate embedding for new text
        new_embedding = embedding_service.embed_text(text)
        
        # Compare with recent embeddings
        for stored_hash, stored_embedding, timestamp in self._recent_embeddings:
            similarity = embedding_service.cosine_similarity(new_embedding, stored_embedding)
            if similarity >= self._similarity_threshold:
                return True, stored_hash
        
        return False, None
    
    def _clean_old_entries(self):
        """Remove entries older than the window"""
        cutoff = datetime.utcnow() - self._hash_window
        
        # Clean hashes
        self._recent_hashes = {
            h: t for h, t in self._recent_hashes.items()
            if t > cutoff
        }
        
        # Clean embeddings
        self._recent_embeddings = [
            (h, e, t) for h, e, t in self._recent_embeddings
            if t > cutoff
        ]
    
    def deduplicate_batch(
        self,
        messages: List[Dict[str, Any]],
        key_field: str = "content_hash",
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate a batch of messages.
        Keeps the first occurrence of each unique message.
        """
        seen_hashes: Set[str] = set()
        unique_messages = []
        
        for msg in messages:
            msg_hash = msg.get(key_field)
            if not msg_hash:
                msg_hash = hash_message(msg.get("text", "") or msg.get("original_text", ""))
            
            if msg_hash not in seen_hashes:
                seen_hashes.add(msg_hash)
                unique_messages.append(msg)
        
        logger.debug(
            "batch_deduplicated",
            original_count=len(messages),
            unique_count=len(unique_messages),
            duplicates_removed=len(messages) - len(unique_messages),
        )
        
        return unique_messages
    
    def group_similar_messages(
        self,
        messages: List[Dict[str, Any]],
        text_field: str = "original_text",
        similarity_threshold: float = 0.85,
    ) -> List[List[Dict[str, Any]]]:
        """
        Group messages by semantic similarity.
        Returns list of groups, where each group contains similar messages.
        """
        if not messages:
            return []
        
        # Extract texts and generate embeddings
        texts = [msg.get(text_field, "") for msg in messages]
        embeddings = embedding_service.embed_texts(texts)
        
        # Cluster by similarity
        cluster_indices = embedding_service.cluster_by_similarity(embeddings, similarity_threshold)
        
        # Build groups
        groups = []
        for indices in cluster_indices:
            group = [messages[i] for i in indices]
            groups.append(group)
        
        return groups


# Singleton instance
deduplication_service = DeduplicationService()
