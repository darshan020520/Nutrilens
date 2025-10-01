# backend/app/services/websocket_manager.py
"""
WebSocket Connection Manager for NutriLens AI
Handles real-time updates, connection lifecycle, and Redis pub/sub for horizontal scaling
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis
from collections import defaultdict

from app.core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time tracking updates
    Supports multiple connections per user (multi-device)
    Uses Redis pub/sub for horizontal scaling across multiple API instances
    """
    
    def __init__(self):
        # Active connections: {user_id: [WebSocket, WebSocket, ...]}
        self.active_connections: Dict[int, List[WebSocket]] = defaultdict(list)
        
        # Connection metadata: {websocket_id: {user_id, connected_at, last_ping}}
        self.connection_metadata: Dict[int, Dict[str, Any]] = {}
        
        # Redis client for pub/sub (horizontal scaling)
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        
        # Heartbeat tracking
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_timeout = 90  # seconds
        
        # Stats
        self.stats = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "total_broadcasts": 0,
            "active_users": 0
        }
        
        logger.info("WebSocket ConnectionManager initialized")
    
    async def initialize_redis(self):
        """Initialize Redis connection for pub/sub"""
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Create pub/sub
            self.pubsub = self.redis_client.pubsub()
            
            logger.info("Redis pub/sub initialized successfully")
            
            # Start listening to all user channels in background
            asyncio.create_task(self._redis_message_listener())
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis for WebSocket: {str(e)}")
            self.redis_client = None
            self.pubsub = None
    
    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        """
        Register a new WebSocket connection
        
        Args:
            websocket: FastAPI WebSocket instance
            user_id: Authenticated user ID
            
        Returns:
            bool: True if connection successful
        """
        try:
            # Accept the WebSocket connection
            await websocket.accept()
            
            # Add to active connections
            self.active_connections[user_id].append(websocket)
            
            # Store metadata
            ws_id = id(websocket)
            self.connection_metadata[ws_id] = {
                "user_id": user_id,
                "connected_at": datetime.utcnow().isoformat(),
                "last_ping": datetime.utcnow(),
                "messages_sent": 0
            }
            
            # Subscribe to user's Redis channel (for multi-instance support)
            if self.pubsub:
                await self.pubsub.subscribe(f"user:{user_id}")
            
            # Update stats
            self.stats["total_connections"] += 1
            self.stats["active_users"] = len(self.active_connections)
            
            # Send welcome message
            await self._send_to_websocket(websocket, {
                "event_type": "connected",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "WebSocket connection established",
                "server_time": datetime.utcnow().isoformat()
            })
            
            logger.info(f"WebSocket connected: user_id={user_id}, total_connections={len(self.active_connections[user_id])}")
            
            # Start heartbeat for this connection
            asyncio.create_task(self._heartbeat_loop(websocket, user_id))
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket for user {user_id}: {str(e)}")
            return False
    
    async def disconnect(self, websocket: WebSocket, user_id: int):
        """
        Remove a WebSocket connection
        
        Args:
            websocket: FastAPI WebSocket instance
            user_id: User ID
        """
        try:
            # Remove from active connections
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)
                
                # Clean up if no more connections for this user
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    
                    # Unsubscribe from Redis channel
                    if self.pubsub:
                        await self.pubsub.unsubscribe(f"user:{user_id}")
            
            # Remove metadata
            ws_id = id(websocket)
            if ws_id in self.connection_metadata:
                del self.connection_metadata[ws_id]
            
            # Update stats
            self.stats["active_users"] = len(self.active_connections)
            
            logger.info(f"WebSocket disconnected: user_id={user_id}, remaining_connections={len(self.active_connections.get(user_id, []))}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {str(e)}")
    
    async def broadcast_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """
        Broadcast message to all connections of a specific user
        Uses Redis pub/sub to reach user across multiple API instances
        
        Args:
            user_id: Target user ID
            message: Message dictionary to send
            
        Returns:
            bool: True if sent successfully
        """
        try:
            # Add metadata
            message["timestamp"] = message.get("timestamp", datetime.utcnow().isoformat())
            message["user_id"] = user_id
            
            # Publish to Redis (for other instances)
            if self.redis_client:
                await self.redis_client.publish(
                    f"user:{user_id}",
                    json.dumps(message)
                )
            
            # Send directly to local connections (optimization)
            if user_id in self.active_connections:
                disconnected = []
                
                for websocket in self.active_connections[user_id]:
                    try:
                        await self._send_to_websocket(websocket, message)
                    except Exception as e:
                        logger.warning(f"Failed to send to WebSocket: {str(e)}")
                        disconnected.append(websocket)
                
                # Clean up disconnected websockets
                for ws in disconnected:
                    await self.disconnect(ws, user_id)
            
            # Update stats
            self.stats["total_broadcasts"] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
            return False
    
    async def broadcast_to_all(self, message: Dict[str, Any]) -> int:
        """
        Broadcast message to all connected users (admin feature)
        
        Args:
            message: Message dictionary to send
            
        Returns:
            int: Number of users reached
        """
        try:
            message["timestamp"] = datetime.utcnow().isoformat()
            message["broadcast"] = True
            
            users_reached = 0
            
            for user_id in list(self.active_connections.keys()):
                success = await self.broadcast_to_user(user_id, message)
                if success:
                    users_reached += 1
            
            logger.info(f"Broadcast sent to {users_reached} users")
            return users_reached
            
        except Exception as e:
            logger.error(f"Error in broadcast_to_all: {str(e)}")
            return 0
    
    async def _send_to_websocket(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Send message to a specific WebSocket connection
        
        Args:
            websocket: WebSocket instance
            message: Message dictionary
        """
        try:
            await websocket.send_json(message)
            
            # Update stats
            ws_id = id(websocket)
            if ws_id in self.connection_metadata:
                self.connection_metadata[ws_id]["messages_sent"] += 1
            
            self.stats["total_messages_sent"] += 1
            
        except WebSocketDisconnect:
            logger.warning("WebSocket disconnected during send")
            raise
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            raise
    
    async def _heartbeat_loop(self, websocket: WebSocket, user_id: int):
        """
        Maintain connection health with periodic pings
        
        Args:
            websocket: WebSocket instance
            user_id: User ID
        """
        ws_id = id(websocket)
        
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Check if connection still exists
                if ws_id not in self.connection_metadata:
                    break
                
                # Check for timeout
                last_ping = self.connection_metadata[ws_id]["last_ping"]
                if (datetime.utcnow() - last_ping).seconds > self.heartbeat_timeout:
                    logger.warning(f"WebSocket heartbeat timeout for user {user_id}")
                    await self.disconnect(websocket, user_id)
                    break
                
                # Send ping
                try:
                    await websocket.send_json({
                        "event_type": "ping",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Wait for pong (with timeout)
                    # Note: Client should respond with {"type": "pong"}
                    # We'll update last_ping when we receive it
                    
                except Exception as e:
                    logger.warning(f"Heartbeat failed for user {user_id}: {str(e)}")
                    await self.disconnect(websocket, user_id)
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Heartbeat loop cancelled for user {user_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {str(e)}")
    
    async def handle_client_message(self, websocket: WebSocket, user_id: int, message: Dict[str, Any]):
        """
        Handle messages received from client
        
        Args:
            websocket: WebSocket instance
            user_id: User ID
            message: Received message dictionary
        """
        try:
            message_type = message.get("type", "unknown")
            
            # Handle pong response
            if message_type == "pong":
                ws_id = id(websocket)
                if ws_id in self.connection_metadata:
                    self.connection_metadata[ws_id]["last_ping"] = datetime.utcnow()
                return
            
            # Handle subscription requests (future feature)
            elif message_type == "subscribe":
                # Client can subscribe to specific event types
                # Store preferences in metadata
                pass
            
            # Echo back for debugging (can be removed in production)
            elif message_type == "echo":
                await self._send_to_websocket(websocket, {
                    "event_type": "echo_response",
                    "original_message": message,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            else:
                logger.warning(f"Unknown message type from client: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling client message: {str(e)}")
    
    async def _redis_message_listener(self):
        """
        Background task to listen for Redis pub/sub messages
        Ensures WebSocket updates work across multiple API instances
        """
        if not self.pubsub:
            return
        
        try:
            logger.info("Starting Redis message listener for WebSocket")
            
            async for message in self.pubsub.listen():
                try:
                    if message["type"] == "message":
                        # Parse channel and data
                        channel = message["channel"]
                        data = json.loads(message["data"])
                        
                        # Extract user_id from channel (format: "user:{user_id}")
                        user_id = int(channel.split(":")[1])
                        
                        # Send to local connections only (Redis already broadcast to others)
                        if user_id in self.active_connections:
                            for websocket in self.active_connections[user_id]:
                                try:
                                    await self._send_to_websocket(websocket, data)
                                except Exception as e:
                                    logger.warning(f"Failed to deliver Redis message: {str(e)}")
                                    
                except Exception as e:
                    logger.error(f"Error processing Redis message: {str(e)}")
                    
        except asyncio.CancelledError:
            logger.info("Redis message listener cancelled")
        except Exception as e:
            logger.error(f"Redis message listener error: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            **self.stats,
            "active_connections_by_user": {
                user_id: len(connections) 
                for user_id, connections in self.active_connections.items()
            },
            "total_active_connections": sum(
                len(connections) 
                for connections in self.active_connections.values()
            )
        }
    
    def is_user_connected(self, user_id: int) -> bool:
        """Check if user has any active connections"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0
    
    async def close_all_connections(self):
        """Close all WebSocket connections (graceful shutdown)"""
        logger.info("Closing all WebSocket connections...")
        
        for user_id, connections in list(self.active_connections.items()):
            for websocket in connections:
                try:
                    await websocket.close(code=1000, reason="Server shutdown")
                except Exception as e:
                    logger.warning(f"Error closing WebSocket: {str(e)}")
        
        self.active_connections.clear()
        self.connection_metadata.clear()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("All WebSocket connections closed")


# Global instance (singleton pattern)
websocket_manager = ConnectionManager()