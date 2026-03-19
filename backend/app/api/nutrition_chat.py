from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging
import json

from app.models.database import User
from app.dependencies import (
    get_current_user,
    get_user_profile_repository,
    get_tracking_repository,
    get_inventory_repository,
    get_recipe_repository,
    get_consumption_analytics_repository,
    get_onboarding_service,
    get_token_governor,
    get_prompt_registry
)
from app.agents.nutrition_context import UserContext
from app.agents.graph_instance import get_compiled_graph, is_initialized
from app.agents.nutrition_graph_v3 import NutritionState, NutritionContextSchema
from app.core.mongodb import save_chat_message
from langchain_core.messages import HumanMessage, AIMessage
import uuid
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nutrition", tags=["Nutrition Chat"])


class ChatRequest(BaseModel):
    query: str
    include_context: bool = True
    session_id: Optional[str] = None

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
    session_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "response": "Your protein intake today is 150g out of 180g target (83%). You're on track!",
                "intent": None,
                "data": None,
                "processing_time_ms": 245,
                "cost_usd": 0.003,
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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    user_profile_repo=Depends(get_user_profile_repository),
    tracking_repo=Depends(get_tracking_repository),
    inventory_repo=Depends(get_inventory_repository),
    recipe_repo=Depends(get_recipe_repository),
    analytics_repo=Depends(get_consumption_analytics_repository),
    onboarding_service=Depends(get_onboarding_service)
):
    """
    Chat with the NutriLens nutrition assistant.

    The assistant can answer questions about nutrition stats, meal plans,
    inventory, dietary suggestions, and general nutrition knowledge.
    Conversations persist across requests via session_id.
    """
    start_time = time.time()

    try:
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"[Chat] Processing message for user={current_user.id}, session={session_id}")

        app = get_compiled_graph()

        user_context = UserContext(
            user_id=current_user.id,
            user_profile_repo=user_profile_repo,
            tracking_repo=tracking_repo,
            inventory_repo=inventory_repo,
            recipe_repo=recipe_repo,
            analytics_repo=analytics_repo,
            onboarding_service=onboarding_service
        )

        governor = get_token_governor()
        prompt_registry = get_prompt_registry()

        context = NutritionContextSchema(
            user_context=user_context,
            governor=governor,
            prompt_registry=prompt_registry
        )

        initial_state: NutritionState = {
            "messages": [HumanMessage(content=request.query)],
            "user_context": {},
            "user_id": current_user.id,
            "session_id": session_id,
            "turn_count": 0
        }

        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": 10,
        }

        result = await app.ainvoke(initial_state, config=config, context=context)

        messages = result.get("messages", [])
        assistant_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
        last_message = assistant_messages[-1] if assistant_messages else None

        if last_message:
            response_text = last_message.content
        else:
            response_text = "I'm sorry, I couldn't process your request."

        processing_time = int((time.time() - start_time) * 1000)

        # Derive intent from tool calls used (if any)
        tool_names_used = []
        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_names_used.extend([tc['name'] for tc in msg.tool_calls])
        intent = tool_names_used[0] if tool_names_used else None

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
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/context", response_model=ContextResponse)
async def get_user_context(
    minimal: bool = False,
    current_user: User = Depends(get_current_user),
    user_profile_repo=Depends(get_user_profile_repository),
    tracking_repo=Depends(get_tracking_repository),
    inventory_repo=Depends(get_inventory_repository),
    recipe_repo=Depends(get_recipe_repository),
    analytics_repo=Depends(get_consumption_analytics_repository),
    onboarding_service=Depends(get_onboarding_service)
):
    """Get the current user's nutrition context data."""
    try:
        context_builder = UserContext(
            user_id=current_user.id,
            user_profile_repo=user_profile_repo,
            tracking_repo=tracking_repo,
            inventory_repo=inventory_repo,
            recipe_repo=recipe_repo,
            analytics_repo=analytics_repo,
            onboarding_service=onboarding_service
        )

        context = await context_builder.build_context(minimal=minimal)

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
    """Check nutrition chat service health."""
    try:
        graph_ready = is_initialized()

        return {
            "status": "healthy" if graph_ready else "degraded",
            "graph_initialized": graph_ready,
            "services": {
                "langgraph": "operational" if graph_ready else "not_initialized",
                "context_builder": "operational",
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "error": str(e)
        }
