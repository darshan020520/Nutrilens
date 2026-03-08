"""
seed_macro_targets_prompt.py
-----------------------------
Inserts (or upserts) the 'calculate_macro_targets' prompt into MongoDB llm_prompts collection.

Run inside the api container:
  docker compose exec api python scripts/seed_macro_targets_prompt.py
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

PROMPT = {
    "slug": "calculate_macro_targets",
    "messages": [
        {
            "role": "system",
            "content": (
                "You are a certified sports nutritionist and dietitian specialising in "
                "personalised nutrition planning. Given a user's complete health profile, "
                "calculate their optimal daily nutrition targets.\n\n"
                "Return ONLY a JSON object with these exact keys:\n"
                "  goal_calories  – personalised daily calorie target (integer)\n"
                "  protein_g      – daily protein in grams\n"
                "  fat_g          – daily fat in grams\n"
                "  carbs_g        – daily carbohydrates in grams (fill remaining calories)\n"
                "  reasoning      – 1-2 sentence explanation of your recommendations\n\n"
                "Hard constraints you MUST satisfy:\n"
                "- protein_g × 4 + carbs_g × 4 + fat_g × 9 must equal goal_calories (±5%)\n"
                "- protein_g must be between 0.8 g/kg and 3.0 g/kg of the user's body weight\n"
                "- fat_g must be at least 0.5 g/kg of body weight\n"
                "- carbs_g must be ≥ 0\n"
                "- goal_calories must be within ±700 kcal of the provided TDEE\n"
                "No extra text, no markdown — pure JSON only."
            )
        },
        {
            "role": "user",
            "content": (
                "Calculate personalised macro targets for this user:\n\n"
                "Age: {age} years\n"
                "Sex: {sex}\n"
                "Weight: {weight_kg} kg\n"
                "Height: {height_cm} cm\n"
                "BMI: {bmi}\n"
                "Activity Level: {activity_level}\n"
                "Fitness Goal: {goal_type}\n"
                "TDEE (maintenance calories): {tdee} kcal/day\n\n"
                "Consider how age, sex, BMI, and activity level should influence each macro "
                "beyond the basic goal-type bucket. Return the JSON object now."
            )
        }
    ],
    "config": {
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": 300,
        "response_format": {"type": "json_object"}
    }
}


async def seed():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db]
    collection = db["llm_prompts"]

    now = datetime.now(timezone.utc)
    doc = {
        **PROMPT,
        "version": 1,
        "active": True,
        "updated_at": now,
    }
    result = await collection.update_one(
        {"slug": PROMPT["slug"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True
    )
    action = "updated" if result.matched_count > 0 else "inserted"
    print(f"  {action}: {PROMPT['slug']}")
    print("Done.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
