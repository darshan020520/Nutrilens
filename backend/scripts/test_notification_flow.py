"""
Notification Flow Smoke Test
============================
Tests the full pipeline end-to-end without real API calls:

  STAGE 1  Publish test events
           EventPublisher → NotificationObserver → NotificationFactory → Redis queue

  STAGE 2  Drain Redis queue
           Pop each notification, render its template with fake user data

  STAGE 3  Mock channel send
           Print exactly what would go to email / push / sms / whatsapp

Requirements: Redis must be running. No DB or external API credentials needed.

Usage:
    cd backend
    python -m scripts.test_notification_flow
"""

import asyncio
import json
import sys
import os
import logging
from typing import Dict, Any, List

# Show errors/warnings from the app; suppress DEBUG/INFO noise.
# If you want full observer trace, change the second line to DEBUG.
logging.basicConfig(level=logging.WARNING)
logging.getLogger("app.infrastructure.observers").setLevel(logging.DEBUG)

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Test events — one per notification type so every code path is exercised
# ---------------------------------------------------------------------------
TEST_EVENTS = [
    (
        "meal_logged",
        {
            "user_id": 1,
            "meal_log": {"meal_type": "breakfast"},
            "daily_totals": {
                "compliance_rate": 85.0,
                "total_calories": 1200,
                "total_macros": {"protein_g": 80},
            },
            "inventory_changes": [],
        },
        "→ expects: progress_update (compliance ≥ 80%). Achievement skipped (no DB).",
    ),
    (
        "meal_skipped",
        {
            "user_id": 1,
            "meal_type": "lunch",
            "meal_log_id": 42,
            "recipe_name": "Chicken Salad",
            "reason": "not_hungry",
            "skip_patterns": {},
        },
        "→ expects: progress_update (meal skipped reminder).",
    ),
    (
        "scheduled_meal_reminder",
        {
            "user_id": 1,
            "meal_type": "dinner",
            "recipe_name": "Pasta Primavera",
            "time_until": 30,
            "scheduled_time": "7:00 PM",
        },
        "→ expects: meal_reminder (normal priority, time_until=30).",
    ),
    (
        "scheduled_meal_reminder",
        {
            "user_id": 1,
            "meal_type": "breakfast",
            "recipe_name": "Oats & Berries",
            "time_until": 10,
            "scheduled_time": "8:00 AM",
        },
        "→ expects: meal_reminder (URGENT priority, time_until≤15).",
    ),
    (
        "scheduled_daily_summary",
        {
            "user_id": 1,
            "date": "2026-02-18",
            "meals_consumed": 2,
            "compliance_rate": 66.7,
            "calories_consumed": 1500,
            "protein_g": 90,
        },
        "→ expects: daily_summary (low priority, email only).",
    ),
    (
        "scheduled_inventory_check",
        {
            "user_id": 1,
            "expiring_items": [
                {"name": "Milk", "expiry_date": "2026-02-19", "days_left": 1},
                {"name": "Yoghurt", "expiry_date": "2026-02-20", "days_left": 2},
            ],
            "days_until_expiry": 1,
            "low_stock_items": [
                {"name": "Eggs", "quantity": 2, "urgency": "high"},
            ],
        },
        "→ expects: expiry_alert (urgent) + low_stock_alert (normal).",
    ),
    (
        "inventory_updated",
        {"user_id": 1, "item_count": 5},
        "→ expects: inventory_alert (normal priority).",
    ),
]

# Fake user injected into template rendering — no DB needed
FAKE_USER = {
    "user_name": "Test User",
    "user_email": "testuser@example.com",
    "unsubscribe_url": "https://app.nutrilens.com/unsubscribe?token=FAKE",
}

# Production queue keys — the live NotificationConsumer listens on these
PROD_QUEUE_KEYS = [
    "notifications:queue:urgent",
    "notifications:queue:high",
    "notifications:queue:normal",
    "notifications:queue:low",
]

# Test-specific queue keys — the consumer does NOT know these, so it won't
# consume them mid-test.  We redirect the observer here for isolation.
TEST_QUEUE_PREFIX = "test:"
QUEUE_KEYS = [f"{TEST_QUEUE_PREFIX}{k}" for k in PROD_QUEUE_KEYS]

# Mapping from priority name → test queue key (mirrors NotificationObserver.QUEUE_KEYS)
TEST_QUEUE_MAP = {
    "urgent": f"{TEST_QUEUE_PREFIX}notifications:queue:urgent",
    "high":   f"{TEST_QUEUE_PREFIX}notifications:queue:high",
    "normal": f"{TEST_QUEUE_PREFIX}notifications:queue:normal",
    "low":    f"{TEST_QUEUE_PREFIX}notifications:queue:low",
}

SEP = "─" * 70


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def header(text: str) -> None:
    print(f"\n{'═' * 70}")
    print(f"  {text}")
    print(f"{'═' * 70}")


def section(text: str) -> None:
    print(f"\n{SEP}")
    print(f"  {text}")
    print(SEP)


def ok(text: str) -> None:
    print(f"  ✅  {text}")


def warn(text: str) -> None:
    print(f"  ⚠️   {text}")


def fail(text: str) -> None:
    print(f"  ❌  {text}")


# ---------------------------------------------------------------------------
# Stage 1 — Publish
# ---------------------------------------------------------------------------

async def stage_publish(event_publisher, redis_client) -> int:
    header("STAGE 1 — Publishing test events")
    count = 0
    for event_type, data, note in TEST_EVENTS:
        print(f"\n  [EVENT] {event_type}")
        print(f"          {note}")
        try:
            await event_publisher.publish(event_type=event_type, data=data)
            ok("published")
            count += 1

            # Snapshot queue sizes immediately after publish so we can see
            # exactly which event produced which notifications
            sizes = {}
            for q in QUEUE_KEYS:
                n = await redis_client.llen(q)
                if n:
                    sizes[q.split(":")[-1]] = n
            if sizes:
                print(f"          queued → {sizes}")
            else:
                print(f"          queued → (nothing added to any queue)")

        except Exception as e:
            fail(f"publish failed: {e}")
    print(f"\n  → {count}/{len(TEST_EVENTS)} events published")
    return count


# ---------------------------------------------------------------------------
# Stage 2 & 3 — Drain + Render + Mock send
# ---------------------------------------------------------------------------

async def stage_drain_and_render(redis_client, renderer) -> int:
    header("STAGE 2 & 3 — Drain queue → Render templates → Mock send")

    total = 0
    for queue_key in QUEUE_KEYS:
        priority = queue_key.split(":")[-1].upper()
        queue_had_items = False

        while True:
            raw = await redis_client.lpop(queue_key)
            if not raw:
                break

            if not queue_had_items:
                section(f"Queue: {priority}")
                queue_had_items = True

            notification: Dict[str, Any] = json.loads(raw)
            n_type = notification["type"]
            channels: List[str] = notification.get("channels", [])
            context: Dict[str, Any] = notification.get("context", {})
            total += 1

            print(f"\n  [{priority}] {n_type}")
            print(f"  user_id  : {notification['user_id']}")
            print(f"  channels : {channels}")
            print(f"  context  : {json.dumps(context, indent=14)}")

            # Render each channel's template
            for channel in channels:
                print(f"\n  ── channel: {channel} ──")
                try:
                    rendered = renderer.render(
                        notification_type=n_type,
                        channel=channel,
                        context=context,
                        user_data=FAKE_USER,
                    )

                    # Mock send — print what the channel would receive
                    if channel == "push":
                        print(f"    [MOCK PUSH]")
                        print(f"    title : {rendered['title']}")
                        print(f"    body  : {rendered['body']}")
                        print(f"    data  : {rendered['data']}")

                    elif channel == "email":
                        # Only print subject line — HTML body is too long for console
                        print(f"    [MOCK EMAIL]")
                        print(f"    to      : {FAKE_USER['user_email']}")
                        print(f"    subject : {rendered['title']}")
                        body_preview = rendered["body"].replace("\n", " ").strip()[:120]
                        print(f"    body    : {body_preview}…")

                    elif channel == "sms":
                        print(f"    [MOCK SMS]")
                        print(f"    to   : +91XXXXXXXXXX")
                        print(f"    body : {rendered['body']}")

                    elif channel == "whatsapp":
                        print(f"    [MOCK WHATSAPP]")
                        print(f"    to   : +91XXXXXXXXXX")
                        print(f"    body : {rendered['body']}")

                    ok("template rendered")

                except Exception as e:
                    fail(f"render failed for {n_type}/{channel}: {e}")

    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    from app.infrastructure.events.event_publisher import EventPublisher
    from app.infrastructure.observers.notification_observer import NotificationObserver
    from app.infrastructure.notifications.templates.template_renderer import TemplateRenderer
    from app.core.redis_client import get_redis_client

    header("NOTIFICATION FLOW SMOKE TEST")
    print("  No DB or external API credentials required.")
    print("  Achievement checks skipped (session_factory=None).")
    print("  Channels are mocked — nothing is actually sent.")

    # ── Connect to Redis ──────────────────────────────────────────────────
    redis_client = get_redis_client()
    try:
        await redis_client.ping()
        ok("Redis connected")
    except Exception as e:
        fail(f"Cannot reach Redis: {e}")
        fail("Start Redis and retry.")
        sys.exit(1)

    # ── Clear stale queues ────────────────────────────────────────────────
    for q in QUEUE_KEYS:
        await redis_client.delete(q)
    ok("Notification queues cleared")

    # ── Wire up pipeline ──────────────────────────────────────────────────
    event_publisher = EventPublisher()
    # session_factory=None → achievement checks are skipped (no DB needed)
    observer = NotificationObserver(session_factory=None)

    # Redirect the observer to TEST queue keys so the live NotificationConsumer
    # (running as a separate Docker service) doesn't consume our test items.
    observer.QUEUE_KEYS = TEST_QUEUE_MAP

    event_publisher.attach(observer)
    ok("EventPublisher + NotificationObserver wired")
    ok("Observer redirected to test queue keys (consumer won't interfere)")

    renderer = TemplateRenderer()
    ok(f"TemplateRenderer ready → {renderer.template_dir}")

    # ── Run stages ────────────────────────────────────────────────────────
    published = await stage_publish(event_publisher, redis_client)

    # Brief pause (EventPublisher awaits observers, but just in case)
    await asyncio.sleep(0.3)

    total_rendered = await stage_drain_and_render(redis_client, renderer)

    # ── Summary ───────────────────────────────────────────────────────────
    header("SUMMARY")
    print(f"  Events published    : {published}")
    print(f"  Notifications queued: {total_rendered}")

    if total_rendered == 0:
        # Check if this is because the live consumer raced us on prod keys
        prod_total = 0
        for q in PROD_QUEUE_KEYS:
            prod_total += await redis_client.llen(q)
        if prod_total > 0:
            warn(f"Test queue keys were empty but prod queues have {prod_total} items.")
            warn("The live consumer may have consumed test notifications.")
            warn("Re-run the script — the observer now uses isolated test queue keys.")
        else:
            warn("Nothing was queued — observer may not have fired.")
            warn("Check observer is attached and QUEUE_KEYS are correct.")
    else:
        ok(f"Full flow working: {total_rendered} notifications rendered and mock-sent.")

        # Bonus: check the dead letter queue for any consumer failures
        dead_count = await redis_client.llen("notifications:dead_letter")
        if dead_count:
            warn(f"Dead letter queue has {dead_count} failed notification(s) from the live consumer.")
            warn("Run: redis-cli LRANGE notifications:dead_letter 0 -1  to inspect them.")
        else:
            ok("Dead letter queue is empty — no delivery failures recorded.")

        print()
        print("  Next steps to test real delivery:")
        print("    1. Set SENDGRID_API_KEY / FCM_SERVER_KEY / TWILIO_* env vars")
        print("    2. Run the consumer:  python -m app.workers.notification_worker consumer")
        print("    3. Re-publish events: python -m scripts.test_notification_flow")

    # Clean up test queue keys and Redis connection
    for q in QUEUE_KEYS:
        await redis_client.delete(q)
    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
