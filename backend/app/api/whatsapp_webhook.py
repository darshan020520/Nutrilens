"""
WhatsApp Webhook - Twilio Integration

Handles incoming WhatsApp messages via Twilio webhook:
1. Receives POST from Twilio with message data
2. Returns 200 OK immediately (Twilio requirement)
3. Processes message in background (FastAPI BackgroundTasks)
4. Invokes WhatsApp LangGraph agent
5. Sends reply via Twilio WhatsApp API

HITL Flow:
- Write tools (log_planned_meal, log_external_meal) call interrupt()
- Graph pauses, webhook sends confirmation message to user
- User replies yes/no, webhook resumes graph with Command(resume=...)
"""

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import Response
import logging
import re
from typing import Optional

from app.models.database import SessionLocal, NotificationPreference, User
from app.agents.whatsapp_graph_instance import get_whatsapp_graph, is_whatsapp_initialized
from app.infrastructure.notifications.channels.whatsapp_channel import WhatsAppChannel
from app.core.redis_client import get_redis_client
from app.core.config import settings
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

# Singleton WhatsApp channel for sending replies
_whatsapp_channel = None


def _get_whatsapp_channel() -> WhatsAppChannel:
    global _whatsapp_channel
    if _whatsapp_channel is None:
        _whatsapp_channel = WhatsAppChannel(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token
        )
    return _whatsapp_channel


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Twilio WhatsApp webhook.

    Receives incoming messages, deduplicates via Redis, and processes
    in background. Returns 200 OK immediately (Twilio requirement).
    """
    form_data = await request.form()

    phone = form_data.get("From", "")
    text = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid", "")

    if not phone or not text:
        logger.warning("[WA:webhook] Missing From or Body in request")
        return Response(status_code=200)

    logger.info(f"[WA:webhook] Message from {phone}: {text[:50]}... (SID: {message_sid})")

    # Deduplicate via Redis (async client, TTL 1 hour)
    redis = get_redis_client()
    if redis and message_sid:
        dedup_key = f"wa_msg:{message_sid}"
        is_new = await redis.set(dedup_key, "1", ex=3600, nx=True)
        if not is_new:
            logger.info(f"[WA:webhook] Duplicate message {message_sid}, skipping")
            return Response(status_code=200)

    # Process in background
    background_tasks.add_task(process_whatsapp_message, phone, text, message_sid)

    return Response(status_code=200)


# ============================================================================
# BACKGROUND PROCESSING
# ============================================================================

async def process_whatsapp_message(phone: str, text: str, message_sid: str):
    """Process incoming WhatsApp message in background."""
    print(f"[WA:process] START phone={phone} text={text[:60]!r} sid={message_sid}")
    db = SessionLocal()
    try:
        # 1. Look up user by WhatsApp number
        user = lookup_user_by_whatsapp(phone, db)
        print(f"[WA:process] User lookup: {'FOUND id=' + str(user.id) if user else 'NOT FOUND'} (clean_phone={phone.replace('whatsapp:', '')})")
        if not user:
            await send_whatsapp_reply(
                phone,
                "You're not registered on NutriLens yet. "
                "Please register on the app and link your WhatsApp number."
            )
            return

        logger.info(f"[WA:process] User {user.id} ({phone}), message: {text[:80]}")

        # 2. Build context (DI container for the graph)
        from app.dependencies import build_whatsapp_context
        context = await build_whatsapp_context(user.id, db)

        # 3. Get compiled graph
        graph = get_whatsapp_graph()
        thread_id = f"wa_{user.id}"
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 10
        }

        # 4. Check for pending interrupts (HITL confirmation flow)
        has_pending_interrupt = False
        try:
            current_state = await graph.aget_state(config)
            has_pending_interrupt = bool(current_state and current_state.tasks)
        except Exception:
            has_pending_interrupt = False

        # 5. Invoke graph
        if has_pending_interrupt:
            confirmation = parse_confirmation(text)

            if confirmation is not None:
                # Clear yes/no response -> resume the interrupt
                logger.info(f"[WA:process] Resuming interrupt with: {confirmation}")
                result = await graph.ainvoke(
                    Command(resume=confirmation),
                    config=config,
                    context=context
                )
            else:
                # Ambiguous response -> cancel interrupt, process as new message
                logger.info("[WA:process] Ambiguous reply during interrupt, cancelling and processing as new message")
                await graph.ainvoke(
                    Command(resume="reject"),
                    config=config,
                    context=context
                )
                initial_state = {
                    "messages": [HumanMessage(content=text)],
                    "user_context": {},
                    "user_id": user.id,
                    "thread_id": thread_id,
                    "turn_count": 0
                }
                result = await graph.ainvoke(initial_state, config=config, context=context)
        else:
            # Normal new message
            initial_state = {
                "messages": [HumanMessage(content=text)],
                "user_context": {},
                "user_id": user.id,
                "thread_id": thread_id,
                "turn_count": 0
            }
            result = await graph.ainvoke(initial_state, config=config, context=context)

        # 6. Check if graph paused at a NEW interrupt
        updated_state = await graph.aget_state(config)
        if updated_state and updated_state.tasks:
            # Extract interrupt message for user confirmation
            interrupt_value = updated_state.tasks[0].interrupts[0].value
            response_text = interrupt_value.get("message", "Please confirm: reply 'yes' or 'no'")
            print(f"[WA:process] Graph paused at interrupt, sending confirmation prompt")
        else:
            # Normal completion - get last AI message (non-tool-call)
            messages = result.get("messages", [])
            ai_messages = [
                m for m in messages
                if isinstance(m, AIMessage) and m.content and not getattr(m, 'tool_calls', None)
            ]
            print(f"[WA:process] Graph done. Total messages={len(messages)}, AI messages={len(ai_messages)}")
            response_text = ai_messages[-1].content if ai_messages else "I'm not sure how to help with that."

        # 7. Clean up for WhatsApp (strip markdown)
        response_text = strip_markdown(response_text)
        print(f"[WA:process] Sending reply ({len(response_text)} chars): {response_text[:100]!r}")

        # 8. Send reply
        await send_whatsapp_reply(phone, response_text)
        print(f"[WA:process] DONE")

    except Exception as e:
        print(f"[WA:process] EXCEPTION {type(e).__name__}: {e}")
        logger.error(f"[WA:process] Error: {e}", exc_info=True)
        await send_whatsapp_reply(
            phone,
            "Sorry, something went wrong. Please try again later."
        )
    finally:
        db.close()


# ============================================================================
# HELPERS
# ============================================================================

def lookup_user_by_whatsapp(phone: str, db) -> Optional[User]:
    """
    Look up user by WhatsApp number.

    Queries NotificationPreference.whatsapp_number -> joins User.

    Args:
        phone: Phone number (may include "whatsapp:" prefix from Twilio)
        db: SQLAlchemy session

    Returns:
        User if found, None otherwise
    """
    clean_phone = phone.replace("whatsapp:", "")

    pref = db.query(NotificationPreference).filter(
        NotificationPreference.whatsapp_number == clean_phone
    ).first()

    if pref:
        return db.query(User).filter(User.id == pref.user_id).first()

    return None


def parse_confirmation(text: str) -> Optional[str]:
    """
    Parse natural language confirmation to approve/reject.

    Returns:
        "approve" for affirmative responses
        "reject" for negative responses
        None for ambiguous (not a clear yes/no)
    """
    normalized = text.strip().lower()

    approve_words = {
        "yes", "y", "ok", "confirm", "sure", "yep", "yeah",
        "log it", "do it", "go ahead", "correct", "right"
    }
    reject_words = {
        "no", "n", "cancel", "nope", "skip", "don't", "stop",
        "nevermind", "never mind", "nah"
    }

    if normalized in approve_words:
        return "approve"
    if normalized in reject_words:
        return "reject"

    return None


def strip_markdown(text: str) -> str:
    """Strip common markdown formatting for WhatsApp plain text."""
    # Remove headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers (keep text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    return text.strip()


async def send_whatsapp_reply(phone: str, text: str):
    """
    Send a WhatsApp reply, splitting if necessary.

    Twilio has a 1600-char limit per message. Split at that boundary.
    """
    channel = _get_whatsapp_channel()
    print(f"[WA:send] client={'OK' if channel.client else 'NONE'} from={channel.from_number} to={phone}")
    MAX_LENGTH = 1600
    if len(text) <= MAX_LENGTH:
        result = await channel.send(user_phone=phone, title="", body=text)
        print(f"[WA:send] Result: {result}")
    else:
        chunks = [text[i:i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
        for i, chunk in enumerate(chunks):
            result = await channel.send(user_phone=phone, title="", body=chunk)
            print(f"[WA:send] Chunk {i+1}/{len(chunks)} result: {result}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def whatsapp_health():
    """Check WhatsApp bot health."""
    return {
        "status": "healthy" if is_whatsapp_initialized() else "degraded",
        "graph_initialized": is_whatsapp_initialized()
    }