"""
Singleton compiled WhatsApp LangGraph instance.

Same pattern as graph_instance.py for the nutrition bot.
The graph is compiled ONCE at application startup and reused for all requests.

Benefits:
- Eliminates graph compilation overhead per request
- Thread-safe: LangGraph compiled graphs are designed for concurrent use
- Stateless: Each request passes user_id in state, tools create own DB sessions
"""

import logging
from contextlib import asynccontextmanager
from langgraph.checkpoint.mongodb import MongoDBSaver
from app.core.config import settings
from app.core.mongodb import get_mongo_sync_client
from app.agents.whatsapp_graph import create_whatsapp_graph_structure

logger = logging.getLogger(__name__)

# Global singleton instances (separate from nutrition bot's)
_compiled_graph = None
_checkpointer = None


@asynccontextmanager
async def initialize_whatsapp_graph():
    """
    Initialize and compile the WhatsApp graph at application startup.

    Handles:
    1. Creating MongoDB checkpointer (required for interrupt/resume)
    2. Building graph structure
    3. Compiling graph with checkpointer
    4. Cleanup on shutdown

    Usage:
        async with initialize_whatsapp_graph():
            # Application runs here with compiled graph available
            pass
    """
    global _compiled_graph, _checkpointer

    logger.info("[WA:GraphInit] Initializing WhatsApp LangGraph...")

    try:
        # Create MongoDB checkpointer for conversation state + interrupt persistence
        try:
            client = get_mongo_sync_client()
            _checkpointer = MongoDBSaver(client=client, db_name=settings.mongodb_db)
            logger.info("[WA:GraphInit] MongoDB checkpointer created")
        except Exception as mongo_error:
            logger.error(f"[WA:GraphInit] MongoDB connection failed: {mongo_error}")
            logger.warning("[WA:GraphInit] Proceeding WITHOUT checkpointer (stateless mode)")
            logger.warning("[WA:GraphInit] HITL interrupts will NOT work without checkpointer")
            _checkpointer = None

        # Build graph structure
        workflow = create_whatsapp_graph_structure()
        logger.info("[WA:GraphInit] Graph structure created")

        # Compile graph with checkpointer (if available)
        if _checkpointer:
            _compiled_graph = workflow.compile(checkpointer=_checkpointer)
            logger.info("[WA:GraphInit] Graph compiled WITH checkpointer")
        else:
            _compiled_graph = workflow.compile()
            logger.info("[WA:GraphInit] Graph compiled WITHOUT checkpointer (stateless)")

        logger.info("[WA:GraphInit] WhatsApp graph ready for requests")

        yield

    except Exception as e:
        logger.error(f"[WA:GraphInit] Failed: {e}", exc_info=True)
        raise

    finally:
        logger.info("[WA:GraphInit] Shutting down WhatsApp graph...")
        _compiled_graph = None
        _checkpointer = None


def get_whatsapp_graph():
    """
    Get the singleton compiled WhatsApp graph instance.

    Returns:
        CompiledStateGraph: The compiled WhatsApp graph

    Raises:
        RuntimeError: If graph hasn't been initialized
    """
    if _compiled_graph is None:
        raise RuntimeError(
            "WhatsApp graph not initialized. "
            "Call initialize_whatsapp_graph() during app startup."
        )
    return _compiled_graph


def is_whatsapp_initialized() -> bool:
    """Check if the WhatsApp graph has been initialized."""
    return _compiled_graph is not None