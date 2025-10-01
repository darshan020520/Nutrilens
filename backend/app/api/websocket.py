# backend/app/api/websocket.py
"""
WebSocket API Endpoints for Real-time Tracking Updates
"""

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from typing import Optional

from app.services.websocket_manager import websocket_manager
from app.services.auth import verify_token
from app.models.database import get_db, User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def authenticate_websocket(token: str) -> Optional[int]:
    """
    Authenticate WebSocket connection using JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        int: User ID if authenticated, None otherwise
    """
    try:
        # Verify JWT token
        payload = verify_token(token)
        if not payload:
            logger.warning("Invalid WebSocket token")
            return None
        
        # Extract user_id
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("No user_id in token payload")
            return None
        
        return int(user_id)
        
    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        return None


@router.websocket("/ws/tracking")
async def tracking_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time tracking updates
    
    Connection URL: ws://localhost:8000/ws/tracking?token=YOUR_JWT_TOKEN
    
    Message Types Received:
    - ping: Server health check
    - meal_logged: When user logs a meal
    - inventory_updated: When inventory changes
    - achievement: When user reaches milestone
    - macro_update: Real-time macro calculations
    - suggestion_update: New AI suggestions
    - expiry_alert: Items expiring soon
    
    Client Messages:
    - pong: Response to ping (keep-alive)
    - echo: Debug message echo
    - subscribe: Subscribe to specific event types
    """
    
    # Authenticate user
    user_id = await authenticate_websocket(token)
    
    if not user_id:
        # Reject connection with 403
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        logger.warning("WebSocket connection rejected: authentication failed")
        return
    
    # Connect via manager
    connection_success = await websocket_manager.connect(websocket, user_id)
    
    if not connection_success:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Connection setup failed")
        logger.error(f"Failed to setup WebSocket connection for user {user_id}")
        return
    
    logger.info(f"WebSocket connection established for user {user_id}")
    
    try:
        # Listen for client messages
        while True:
            # Wait for message from client
            data = await websocket.receive_text()
            
            try:
                # Parse JSON message
                message = json.loads(data)
                
                # Handle message via manager
                await websocket_manager.handle_client_message(websocket, user_id, message)
                
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from client: {data[:100]}")
                await websocket.send_json({
                    "event_type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": None
                })
            except Exception as e:
                logger.error(f"Error processing client message: {str(e)}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally for user {user_id}")
        
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        
    finally:
        # Always clean up connection
        await websocket_manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket cleanup completed for user {user_id}")


@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics (admin endpoint)
    
    Returns:
    - Total connections
    - Active users
    - Messages sent
    - Broadcasts count
    """
    stats = websocket_manager.get_stats()
    
    return {
        "status": "active",
        "statistics": stats
    }


@router.post("/ws/broadcast")
async def broadcast_admin_message(message: dict):
    """
    Broadcast message to all connected users (admin only)
    
    This endpoint would normally require admin authentication.
    Use for system-wide announcements, maintenance notices, etc.
    """
    # TODO: Add admin authentication check
    
    users_reached = await websocket_manager.broadcast_to_all({
        "event_type": "system_message",
        "message": message.get("message", ""),
        "priority": message.get("priority", "normal"),
        "action_required": message.get("action_required", False)
    })
    
    return {
        "success": True,
        "users_reached": users_reached,
        "message": "Broadcast sent successfully"
    }