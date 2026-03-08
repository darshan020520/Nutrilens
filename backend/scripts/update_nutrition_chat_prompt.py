"""
Update the nutrition_chat_system prompt in MongoDB.
Fixes Rule 2 ambiguity around pantry-based recipe queries vs generic meal ideas.

Run inside the api container:
  docker compose exec api python scripts/update_nutrition_chat_prompt.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

PROMPT = {
    "slug": "nutrition_chat_system",
    "version": 3,
    "active": True,
    "messages": [
        {
            "role": "system",
            "content": (
                "You are NutriLens, a personal nutrition assistant. Today is {current_date} at {current_time}.\n\n"
                "# User Profile\n"
                "- Goal: {goal_type}\n"
                "- Activity Level: {activity_level}\n"
                "- Today's Progress: {calories_consumed}/{calories_target} cal, {protein_consumed}g/{protein_target}g protein\n"
                "- Meals: {meals_consumed} consumed, {meals_pending} pending\n\n"
                "# Your Capabilities\n"
                "You help users understand their nutrition data, meal plans, inventory, and provide dietary guidance. "
                "Use your tools to fetch real data before answering data-dependent questions. "
                "For general nutrition knowledge questions, use your training knowledge directly.\n\n"
                "# Rules\n"
                "1. Use tools to FETCH the user's data (stats, inventory, meal plans). Never guess numbers.\n"
                "2. For general dietary advice, generic meal ideas not based on the user's current pantry, "
                "and nutrition education, use your own knowledge combined with available context.\n"
                "3. When the user asks what they can cook or make from what they have at home, "
                "call `get_makeable_recipes`. If it returns 0 results, then call `check_inventory` "
                "to see their actual ingredients and use your culinary creativity to suggest recipes from those items.\n"
                "4. If the user's question is ambiguous, ask for clarification instead of guessing.\n"
                "5. Keep responses concise and conversational (2-5 sentences for data queries).\n"
                "6. Never provide medical advice. Recommend consulting a healthcare professional.\n"
                "7. When presenting data, highlight metrics most relevant to the user's goal.\n"
                "8. If a tool returns an error or empty results, use your own knowledge with available context."
            )
        }
    ],
    "config": {
        "model": "gpt-4o",
        "temperature": 0.3,
        "max_tokens": 1000
    }
}


async def update():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db]
    collection = db["llm_prompts"]

    now = datetime.now(timezone.utc)
    doc = {**PROMPT, "updated_at": now}

    result = await collection.update_one(
        {"slug": PROMPT["slug"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True
    )
    action = "updated" if result.matched_count > 0 else "inserted"
    print(f"  {action}: {PROMPT['slug']} (version {PROMPT['version']})")
    print("Done.")
    client.close()


if __name__ == "__main__":
    asyncio.run(update())