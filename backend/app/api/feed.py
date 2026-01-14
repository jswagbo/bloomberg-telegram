"""Real-time feed API routes and WebSocket"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
import asyncio
import json

from app.api.deps import get_optional_user
from app.services.clustering.cluster_service import clustering_service
from app.services.ranking.ranking_service import ranking_service
import structlog

logger = structlog.get_logger()
router = APIRouter()


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
        
        logger.info("websocket_connected", user_id=user_id)
    
    def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if user_id and user_id in self.user_connections:
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
        
        logger.info("websocket_disconnected", user_id=user_id)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific user"""
        if user_id not in self.user_connections:
            return
        
        disconnected = []
        for connection in self.user_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            if conn in self.user_connections[user_id]:
                self.user_connections[user_id].remove(conn)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time signal updates.
    
    Client can send:
    - {"type": "subscribe", "channels": ["signals", "alerts"]}
    - {"type": "unsubscribe", "channels": ["alerts"]}
    
    Server sends:
    - {"type": "signal", "data": {...}}
    - {"type": "alert", "data": {...}}
    - {"type": "cluster_update", "data": {...}}
    """
    # TODO: Validate token and get user_id
    user_id = None
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive and handle messages
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "subscribe":
                    channels = message.get("channels", [])
                    await websocket.send_json({
                        "type": "subscribed",
                        "channels": channels
                    })
                
                elif msg_type == "get_feed":
                    # Send current feed state
                    clusters = clustering_service.get_active_clusters(
                        min_sources=1,
                        limit=20,
                    )
                    signals = ranking_service.get_top_signals(clusters, limit=20)
                    await websocket.send_json({
                        "type": "feed",
                        "data": signals
                    })
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


@router.get("/stats")
async def get_feed_stats():
    """Get real-time feed statistics"""
    clusters = clustering_service.get_active_clusters(limit=1000)
    
    return {
        "active_clusters": len(clusters),
        "total_mentions": sum(c.total_mentions for c in clusters),
        "unique_sources": len(set(s for c in clusters for s in c.source_ids)),
        "chains": list(set(c.chain for c in clusters)),
        "top_score": max((c.priority_score for c in clusters), default=0),
        "timestamp": datetime.utcnow().isoformat(),
    }


# Function to broadcast updates (called from message processing)
async def broadcast_signal_update(cluster_data: dict):
    """Broadcast a signal update to all connected clients"""
    await manager.broadcast({
        "type": "signal_update",
        "data": cluster_data,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def broadcast_new_signal(signal_data: dict):
    """Broadcast a new signal alert"""
    await manager.broadcast({
        "type": "new_signal",
        "data": signal_data,
        "timestamp": datetime.utcnow().isoformat(),
    })
