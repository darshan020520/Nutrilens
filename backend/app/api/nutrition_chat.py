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
from app.services.llm_client import LLMClient
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nutrition", tags=["Nutrition Intelligence"])


# ==================== Request/Response Models ====================

class ChatRequest(BaseModel):
    """Request to chat with nutrition AI"""
    query: str
    include_context: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "query": "how is my protein intake today?",
                "include_context": True
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
                "cost_usd": 0.0005
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
