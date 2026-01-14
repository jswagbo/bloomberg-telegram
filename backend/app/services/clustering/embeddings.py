"""Embedding service using sentence-transformers"""

from typing import List, Optional
import numpy as np

from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Lazy load model to avoid startup delay
_model = None


def get_embedding_model():
    """Get or create the embedding model (lazy loading)"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("embedding_model_loaded")
    return _model


class EmbeddingService:
    """Service for generating text embeddings"""
    
    def __init__(self):
        self._model = None
    
    @property
    def model(self):
        """Lazy load model on first use"""
        if self._model is None:
            self._model = get_embedding_model()
        return self._model
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not texts:
            return []
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(vec1)
        b = np.array(vec2)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def find_similar(
        self,
        query_embedding: List[float],
        embeddings: List[List[float]],
        threshold: float = 0.7,
    ) -> List[tuple]:
        """
        Find similar embeddings above threshold.
        Returns list of (index, similarity_score) tuples.
        """
        results = []
        query = np.array(query_embedding)
        query_norm = np.linalg.norm(query)
        
        if query_norm == 0:
            return []
        
        for i, emb in enumerate(embeddings):
            emb_array = np.array(emb)
            emb_norm = np.linalg.norm(emb_array)
            
            if emb_norm == 0:
                continue
            
            similarity = float(np.dot(query, emb_array) / (query_norm * emb_norm))
            
            if similarity >= threshold:
                results.append((i, similarity))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def cluster_by_similarity(
        self,
        embeddings: List[List[float]],
        threshold: float = 0.85,
    ) -> List[List[int]]:
        """
        Cluster embeddings by similarity.
        Returns list of clusters, where each cluster is a list of indices.
        """
        n = len(embeddings)
        if n == 0:
            return []
        
        # Track which items are already clustered
        clustered = [False] * n
        clusters = []
        
        for i in range(n):
            if clustered[i]:
                continue
            
            # Start new cluster
            cluster = [i]
            clustered[i] = True
            
            # Find similar items
            for j in range(i + 1, n):
                if clustered[j]:
                    continue
                
                similarity = self.cosine_similarity(embeddings[i], embeddings[j])
                if similarity >= threshold:
                    cluster.append(j)
                    clustered[j] = True
            
            clusters.append(cluster)
        
        return clusters


# Singleton instance
embedding_service = EmbeddingService()
