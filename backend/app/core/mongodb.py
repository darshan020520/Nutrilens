from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


_sync_client: Optional[MongoClient] = None

_async_client: Optional[AsyncIOMotorClient] = None


def get_mongo_sync_client() -> MongoClient:
    global _sync_client
    if _sync_client is None:
        logger.info(f"Connecting to MongoDB at {settings.mongodb_url}")
        _sync_client = MongoClient(settings.mongodb_url)
        _sync_client.admin.command('ping')
        logger.info("MongoDB sync client connected successfully")
    return _sync_client


def get_mongo_async_client() -> AsyncIOMotorClient:
    global _async_client
    if _async_client is None:
        logger.info(f"Connecting to async MongoDB at {settings.mongodb_url}")
        _async_client = AsyncIOMotorClient(settings.mongodb_url)
        logger.info("MongoDB async client connected successfully")
    return _async_client


def close_mongo_clients():
    global _sync_client, _async_client
    if _sync_client:
        _sync_client.close()
        _sync_client = None
        logger.info("MongoDB sync client closed")
    if _async_client:
        _async_client.close()
        _async_client = None
        logger.info("MongoDB async client closed")


def init_mongodb_collections():
    """Initialize MongoDB collections and indexes for agent state."""
    client = get_mongo_sync_client()
    db = client[settings.mongodb_db]

    logger.info("Initializing MongoDB collections...")

    try:
        db.create_collection("checkpoints")
        logger.info("Created 'checkpoints' collection")
    except CollectionInvalid:
        logger.info("'checkpoints' collection already exists")

    checkpoints = db["checkpoints"]
    checkpoints.create_index([("thread_id", ASCENDING), ("checkpoint_ns", ASCENDING)])
    checkpoints.create_index([("created_at", DESCENDING)])
    logger.info("Created indexes for 'checkpoints' collection")

    try:
        db.create_collection("chat_history")
        logger.info("Created 'chat_history' collection")
    except CollectionInvalid:
        logger.info("'chat_history' collection already exists")


    chat_history = db["chat_history"]
    chat_history.create_index([("user_id", ASCENDING), ("session_id", ASCENDING)])
    chat_history.create_index([("created_at", DESCENDING)])

    chat_history.create_index(
        [("created_at", ASCENDING)],
        expireAfterSeconds=7776000 
    )
    logger.info("Created indexes for 'chat_history' collection")

    try:
        db.create_collection("sessions")
        logger.info("Created 'sessions' collection")
    except CollectionInvalid:
        logger.info("'sessions' collection already exists")

    sessions = db["sessions"]
    sessions.create_index([("user_id", ASCENDING)])
    sessions.create_index([("created_at", DESCENDING)])
    logger.info("Created indexes for 'sessions' collection")

    try:
        db.create_collection("llm_prompts")
        logger.info("Created 'llm_prompts' collection")
    except CollectionInvalid:
        logger.info("'llm_prompts' collection already exists")

    llm_prompts = db["llm_prompts"]

    llm_prompts.create_index(
        [("slug", ASCENDING), ("version", ASCENDING)],
        unique=True
    )

    llm_prompts.create_index([("slug", ASCENDING), ("active", ASCENDING)])
    logger.info("Created indexes for 'llm_prompts' collection")

    logger.info("MongoDB initialization complete!")


async def save_chat_message(
    user_id: int,
    session_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    tool_calls: Optional[list] = None,
    metadata: Optional[dict] = None
):
    """Save a chat message to MongoDB history."""
    from datetime import datetime

    client = get_mongo_async_client()
    db = client[settings.mongodb_db]
    chat_history = db["chat_history"]

    message = {
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "intent": intent,
        "tool_calls": tool_calls or [],
        "metadata": metadata or {},
        "created_at": datetime.utcnow()
    }

    await chat_history.insert_one(message)


async def get_chat_history(
    user_id: int,
    session_id: str,
    limit: int = 50
) -> list:
    """Retrieve chat history for a session."""
    client = get_mongo_async_client()
    db = client[settings.mongodb_db]
    chat_history = db["chat_history"]

    cursor = chat_history.find(
        {"user_id": user_id, "session_id": session_id}
    ).sort("created_at", ASCENDING).limit(limit)

    messages = []
    async for msg in cursor:
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
            "intent": msg.get("intent"),
            "tool_calls": msg.get("tool_calls", []),
            "created_at": msg["created_at"].isoformat()
        })

    return messages


async def get_user_sessions(user_id: int, limit: int = 10) -> list:
    """Get recent sessions for a user."""
    client = get_mongo_async_client()
    db = client[settings.mongodb_db]
    sessions = db["sessions"]

    cursor = sessions.find(
        {"user_id": user_id}
    ).sort("created_at", DESCENDING).limit(limit)

    session_list = []
    async for session in cursor:
        session_list.append({
            "session_id": session["session_id"],
            "title": session.get("title", "Untitled Chat"),
            "created_at": session["created_at"].isoformat(),
            "message_count": session.get("message_count", 0)
        })

    return session_list
