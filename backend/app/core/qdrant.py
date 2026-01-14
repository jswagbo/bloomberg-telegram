"""Qdrant vector database client"""

from typing import List, Optional, Dict, Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from app.core.config import settings


class QdrantManager:
    """Qdrant vector database manager"""
    
    _instance: Optional["QdrantManager"] = None
    _client: Optional[QdrantClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def connect(self) -> QdrantClient:
        """Connect to Qdrant"""
        if self._client is None:
            self._client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
        return self._client
    
    def get_client(self) -> QdrantClient:
        """Get Qdrant client"""
        if self._client is None:
            self.connect()
        return self._client
    
    async def init_collection(self):
        """Initialize the messages collection"""
        client = self.get_client()
        
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if settings.qdrant_collection not in collection_names:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )
            
            # Create payload indexes for filtering
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name="source_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name="chain",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name="timestamp",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
    
    def close(self):
        """Close connection"""
        if self._client:
            self._client.close()
            self._client = None


qdrant_manager = QdrantManager()


def get_qdrant() -> QdrantClient:
    """Dependency to get Qdrant client"""
    return qdrant_manager.get_client()


class VectorStore:
    """Vector store operations"""
    
    def __init__(self, client: QdrantClient):
        self.client = client
        self.collection = settings.qdrant_collection
    
    def upsert_messages(self, messages: List[Dict[str, Any]], embeddings: List[List[float]]):
        """Upsert messages with their embeddings"""
        points = []
        for msg, embedding in zip(messages, embeddings):
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "message_id": msg.get("id"),
                        "source_id": msg.get("source_id"),
                        "source_name": msg.get("source_name"),
                        "text": msg.get("text", "")[:1000],  # Limit text size
                        "timestamp": msg.get("timestamp"),
                        "chain": msg.get("chain", "unknown"),
                        "tokens": msg.get("tokens", []),
                        "sentiment": msg.get("sentiment"),
                    }
                )
            )
        
        if points:
            self.client.upsert(
                collection_name=self.collection,
                points=points,
            )
    
    def search_similar(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar messages"""
        filter_conditions = None
        if filters:
            must_conditions = []
            for key, value in filters.items():
                if isinstance(value, list):
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=value),
                        )
                    )
                else:
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value),
                        )
                    )
            filter_conditions = models.Filter(must=must_conditions)
        
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=filter_conditions,
        )
        
        return [
            {
                "id": str(r.id),
                "score": r.score,
                **r.payload,
            }
            for r in results
        ]
    
    def search_by_token(
        self,
        token_address: str,
        limit: int = 50,
        since_timestamp: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search messages by token address"""
        must_conditions = [
            models.FieldCondition(
                key="tokens",
                match=models.MatchAny(any=[token_address]),
            )
        ]
        
        if since_timestamp:
            must_conditions.append(
                models.FieldCondition(
                    key="timestamp",
                    range=models.Range(gte=since_timestamp),
                )
            )
        
        results = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=models.Filter(must=must_conditions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )[0]
        
        return [
            {
                "id": str(r.id),
                **r.payload,
            }
            for r in results
        ]
