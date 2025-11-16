"""
Nutrition Chat API - LLM-Powered Intelligent Nutrition Assistant

Endpoints:
- POST /nutrition/chat - Process user query and return intelligent response
- GET /nutrition/chat/history - Get chat history (future)
- GET /nutrition/context - Get current user context

Author: NutriLens AI Team
Created: 2025-11-10
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging

from app.models.database import get_db, User
from app.services.auth import get_current_user_dependency as get_current_user
from app.agents.nutrition_intelligence import NutritionIntelligence
from app.agents.nutrition_context import UserContext
from app.agents.graph_instance import get_compiled_graph
from app.agents.nutrition_graph import NutritionState
from app.services.llm_client import LLMClient
from app.core.config import settings
from app.core.mongodb import save_chat_message
from langchain_core.messages import HumanMessage, AIMessage
import uuid
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nutrition", tags=["Nutrition Intelligence"])


# ==================== Request/Response Models ====================

class ChatRequest(BaseModel):
    """Request to chat with nutrition AI"""
    query: str
    include_context: bool = True
    session_id: Optional[str] = None  # For LangGraph v2 (conversation memory)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "how is my protein intake today?",
                "include_context": True,
                "session_id": "abc-123-def"
            }
        }


class ChatResponse(BaseModel):
    """Response from nutrition AI"""
    success: bool
    response: str
    intent: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    session_id: Optional[str] = None  # For LangGraph v2 (conversation tracking)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "response": "📊 Your protein intake today is 150g out of 180g target (83%). You're on track!",
                "intent": "stats",
                "data": {
                    "consumed": {"protein_g": 150, "calories": 2100},
                    "targets": {"protein_g": 180, "calories": 2500}
                },
                "processing_time_ms": 245,
                "cost_usd": 0.0005,
                "session_id": "abc-123-def"
            }
        }


class ContextResponse(BaseModel):
    """User context response"""
    success: bool
    context: Dict[str, Any]
    context_size_chars: int

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "context": {"user_id": 223, "targets": {}, "today": {}},
                "context_size_chars": 1250
            }
        }


# ==================== LLM Client Singleton ====================

_llm_client = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton"""
    global _llm_client

    if _llm_client is None:
        # Initialize with API keys from settings
        _llm_client = LLMClient(
            anthropic_api_key=getattr(settings, 'anthropic_api_key', None),
            openai_api_key=getattr(settings, 'openai_api_key', None),
            enable_cache=True,
            cache_ttl_seconds=300  # 5 minutes
        )
        logger.info("LLM client initialized")

    return _llm_client


# ==================== Endpoints ====================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_nutrition_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with AI-powered nutrition assistant

    This endpoint:
    1. Builds complete user context from all services
    2. Classifies intent using LLM (Haiku)
    3. Routes to appropriate handler (rule-based or LLM)
    4. Returns intelligent, personalized response

    Performance:
    - Simple queries (stats): ~50ms, $0.0005
    - Complex queries (recommendations): ~500ms, $0.003

    Examples:
    - "how is my protein intake?"
    - "what if I eat 2 samosas?"
    - "suggest a lunch meal"
    - "what can I make with my inventory?"
    - "show my meal plan"
    """
    try:
        # Get LLM client
        llm_client = get_llm_client()

        # Create intelligence layer
        intelligence = NutritionIntelligence(
            db=db,
            user_id=current_user.id,
            llm_client=llm_client
        )

        # Process query
        result = await intelligence.process_query(
            query=request.query,
            include_context=request.include_context
        )

        # Return response
        return ChatResponse(
            success=result.success,
            response=result.response_text,
            intent=result.intent_detected,
            data=result.data,
            processing_time_ms=result.processing_time_ms,
            cost_usd=result.cost_usd
        )

    except Exception as e:
        logger.error(f"Error in nutrition chat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/context", response_model=ContextResponse)
async def get_user_context(
    minimal: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get complete user nutrition context

    Returns all user data gathered from existing services:
    - Profile (age, weight, goal)
    - Daily targets (calories, macros)
    - Today's consumption
    - Inventory summary
    - Weekly stats (if not minimal)
    - Preferences (if not minimal)
    - Meal history (if not minimal)
    - Upcoming meals (if not minimal)

    Use minimal=true for faster response with essential data only.
    """
    try:
        context_builder = UserContext(db, current_user.id)

        context = context_builder.build_context(minimal=minimal)

        # Calculate context size
        import json
        context_json = json.dumps(context, default=str)
        context_size = len(context_json)

        return ContextResponse(
            success=True,
            context=context,
            context_size_chars=context_size
        )

    except Exception as e:
        logger.error(f"Error getting user context: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check for nutrition intelligence system

    Returns:
    - LLM client status
    - Available providers
    - Cache statistics
    """
    try:
        llm_client = get_llm_client()
        stats = llm_client.get_stats()

        return {
            "status": "healthy",
            "llm_client": {
                "anthropic_available": stats["anthropic_available"],
                "openai_available": stats["openai_available"],
                "cache_enabled": stats["cache_enabled"],
                "cache_size": stats["cache_size"]
            },
            "services": {
                "context_builder": "operational",
                "intent_classifier": "operational",
                "handlers": "operational"
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "error": str(e)
        }


# ==================== LangGraph V2 Endpoint (New!) ====================

@router.post("/chat/v2", response_model=ChatResponse)
async def chat_with_langgraph(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with AI nutrition assistant using LangGraph (V2)

    **New Features in V2:**
    - ✅ Stateful conversations with memory
    - ✅ Tool execution (log meals, swap recipes)
    - ✅ Multi-turn conversations
    - ✅ State persistence via MongoDB
    - ✅ Conversation history across sessions
    - ✅ Singleton graph (compiled once at startup)

    **How to use:**
    1. Generate a session_id for a new conversation (or reuse existing one)
    2. Send queries with the same session_id to maintain context
    3. Agent remembers previous messages and can execute actions

    **Example conversation:**
    ```
    User: "How is my protein today?" (session_id: "abc-123")
    Assistant: "Your protein is 85/150g..."

    User: "What if I eat 2 eggs?" (session_id: "abc-123")
    Assistant: "Adding 2 eggs would give you 12g more protein..."
    ```

    **Performance:**
    - First message: ~600-900ms (improved with singleton!)
    - Follow-up messages: ~400-700ms (uses cached state)
    - Cost: ~$0.002 per query

    **Backward Compatible:**
    Returns same response format as /chat endpoint
    """
    start_time = time.time()

    try:
        # Generate session_id if not provided
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"[V2] Processing message for user={current_user.id}, session={session_id}")

        # Get pre-compiled graph singleton (compiled once at startup)
        app = get_compiled_graph()

        # Prepare initial state
        initial_state: NutritionState = {
            "messages": [HumanMessage(content=request.query)],
            "user_context": {},
            "intent": None,
            "confidence": 0.0,
            "entities": {},
            "user_id": current_user.id,
            "session_id": session_id,
            "turn_count": 0,
            "processing_time_ms": 0,
            "cost_usd": 0.0
        }

        # Configure with thread_id for state persistence
        config = {"configurable": {"thread_id": session_id}}

        # Invoke pre-compiled graph
        result = await app.ainvoke(initial_state, config=config)

        # Extract response from result
        messages = result.get("messages", [])
        assistant_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        last_message = assistant_messages[-1] if assistant_messages else None

        if last_message:
            response_text = last_message.content
            intent = result.get("intent", "unknown")
        else:
            response_text = "I'm sorry, I couldn't process your request."
            intent = "error"

        # Calculate metrics
        processing_time = int((time.time() - start_time) * 1000)

        # Save to chat history
        await save_chat_message(
            user_id=current_user.id,
            session_id=session_id,
            role="user",
            content=request.query
        )

        await save_chat_message(
            user_id=current_user.id,
            session_id=session_id,
            role="assistant",
            content=response_text,
            intent=intent
        )

        # Return response (same format as V1)
        return ChatResponse(
            success=True,
            response=response_text,
            intent=intent,
            data=None,
            processing_time_ms=processing_time,
            cost_usd=result.get("cost_usd", 0.0),
            session_id=session_id
        )

    except Exception as e:
        logger.error(f"Error in LangGraph chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )
