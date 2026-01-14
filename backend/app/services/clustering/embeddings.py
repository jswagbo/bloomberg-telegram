"""Embedding service - DISABLED to reduce memory usage

ML embedding features are disabled to allow the app to run on Railway's
free tier with limited memory. The sentence-transformers model requires
significant memory that can cause the app to crash.

To re-enable:
1. Uncomment the ML imports and model loading code
2. Update the methods to use actual embeddings
"""

from typing import List
import structlog

logger = structlog.get_logger()

# ML features disabled - set to True to enable (requires more memory)
EMBEDDINGS_ENABLED = False


class EmbeddingService:
    """Service for generating text embeddings (DISABLED - returns placeholders)"""
    
    def __init__(self):
        self._enabled = EMBEDDINGS_ENABLED
        if not self._enabled:
            logger.warning("embedding_service_disabled", 
                          reason="ML features disabled to reduce memory usage")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text (returns empty placeholder)"""
        if not self._enabled:
            return []
        return []
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (returns empty placeholders)"""
        if not self._enabled:
            return [[] for _ in texts]
        return []
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        # Return 0 when embeddings are disabled
        if not self._enabled or not vec1 or not vec2:
            return 0.0
        return 0.0
    
    def find_similar(
        self,
        query_embedding: List[float],
        embeddings: List[List[float]],
        threshold: float = 0.7,
    ) -> List[tuple]:
        """
        Find similar embeddings above threshold.
        Returns empty list when disabled.
        """
        if not self._enabled:
            return []
        return []
    
    def cluster_by_similarity(
        self,
        embeddings: List[List[float]],
        threshold: float = 0.85,
    ) -> List[List[int]]:
        """
        Cluster embeddings by similarity.
        Returns each item in its own cluster when disabled.
        """
        n = len(embeddings)
        if n == 0:
            return []
        
        # When disabled, each item is its own cluster
        if not self._enabled:
            return [[i] for i in range(n)]
        
        return [[i] for i in range(n)]


# Singleton instance
embedding_service = EmbeddingService()
