"""
Singleton compiled LangGraph instance.

This module manages the lifecycle of the compiled nutrition graph.
The graph is compiled ONCE at application startup and reused for all requests.

Benefits:
- Eliminates 90ms graph compilation overhead per request
- Thread-safe: LangGraph compiled graphs are designed for concurrent use
- Stateless: Each request passes user_id in state, tools create own DB sessions
"""

import logging
from contextlib import asynccontextmanager
from langgraph.checkpoint.mongodb import MongoDBSaver
from app.core.config import settings
from app.core.mongodb import get_mongo_sync_client

logger = logging.getLogger(__name__)

# Global singleton instances
_compiled_graph = None
_checkpointer = None


@asynccontextmanager
async def initialize_nutrition_graph():
    """
    Initialize and compile the nutrition graph at application startup.

    This async context manager handles:
    1. Creating MongoDB checkpointer
    2. Building graph structure
    3. Compiling graph with checkpointer
    4. Cleanup on shutdown

    Usage:
        async with initialize_nutrition_graph():
            # Application runs here with compiled graph available
            pass
    """
    global _compiled_graph, _checkpointer

    logger.info("[GraphInit] 🚀 Initializing LangGraph...")

    try:
        # Create MongoDB checkpointer for conversation state persistence
        try:
            client = get_mongo_sync_client()
            _checkpointer = MongoDBSaver(client=client, db_name=settings.mongodb_db)
            logger.info("[GraphInit] ✅ MongoDB checkpointer created")
        except Exception as mongo_error:
            logger.error(f"[GraphInit] ❌ MongoDB connection failed: {mongo_error}")
            logger.warning("[GraphInit] ⚠️ Proceeding WITHOUT checkpointer (stateless mode)")
            logger.warning("[GraphInit] ⚠️ Conversations will NOT persist across sessions")
            _checkpointer = None  # Graph will work but won't persist conversations

        # Import here to avoid circular dependency
        from app.agents.nutrition_graph import create_nutrition_graph_structure

        # Build stateless graph structure
        workflow = create_nutrition_graph_structure()
        logger.info("[GraphInit] ✅ Graph structure created")

        # Compile graph with checkpointer (if available)
        # This is the expensive operation we do ONCE instead of per-request
        # Note: Message trimming implemented directly in generate_response_node
        # (StateGraph doesn't support pre_model_hook - that's only for create_react_agent)
        if _checkpointer:
            _compiled_graph = workflow.compile(checkpointer=_checkpointer)
            logger.info("[GraphInit] ✅ Graph compiled successfully WITH checkpointer")
        else:
            _compiled_graph = workflow.compile()
            logger.info("[GraphInit] ✅ Graph compiled successfully WITHOUT checkpointer (stateless mode)")
        logger.info("[GraphInit] 🎉 Nutrition graph ready for requests")

        yield  # Application runs here

    except Exception as e:
        logger.error(f"[GraphInit] ❌ Failed to initialize graph: {e}", exc_info=True)
        raise

    finally:
        # Cleanup on shutdown
        logger.info("[GraphInit] 👋 Shutting down nutrition graph...")
        _compiled_graph = None
        _checkpointer = None


def get_compiled_graph():
    """
    Get the singleton compiled graph instance.

    Returns:
        CompiledStateGraph: The compiled nutrition graph

    Raises:
        RuntimeError: If graph hasn't been initialized via initialize_nutrition_graph()

    Usage:
        app = get_compiled_graph()
        result = await app.ainvoke(initial_state, config={"configurable": {"thread_id": session_id}})
    """
    if _compiled_graph is None:
        raise RuntimeError(
            "Graph not initialized. Call initialize_nutrition_graph() during app startup."
        )
    return _compiled_graph


def is_initialized() -> bool:
    """
    Check if the graph singleton has been initialized.

    Returns:
        bool: True if graph is ready, False otherwise
    """
    return _compiled_graph is not None


def has_checkpointer() -> bool:
    """
    Check if the graph has a MongoDB checkpointer (conversation persistence).

    Returns:
        bool: True if checkpointer is available, False if running in stateless mode
    """
    return _checkpointer is not None
