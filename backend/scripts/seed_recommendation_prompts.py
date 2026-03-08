"""
Seed recommendation prompts into MongoDB.

Run: python -m scripts.seed_recommendation_prompts
(from the backend/ directory)
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from app.core.config import settings


PROMPTS = [
    {
        "slug": "daily_consumption_recommendations",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise nutrition coach. Given the user's daily consumption data, "
                    "provide 2-3 short, actionable recommendations (max 1 sentence each). "
                    "Be encouraging but honest. Focus on what the user can do NOW."
                )
            },
            {
                "role": "user",
                "content": (
                    "My daily progress:\n"
                    "- Compliance rate: {compliance_rate}%\n"
                    "- Calories consumed: {total_calories} / {target_calories} target\n"
                    "- Remaining calories: {remaining_calories}\n\n"
                    "Give me 2-3 brief recommendations."
                )
            }
        ],
        "config": {
            "model": "gpt-4o-mini",
            "max_tokens": 200,
            "temperature": 0.7
        }
    },
    {
        "slug": "external_meal_recommendations",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise nutrition coach. The user just logged an external meal "
                    "(restaurant/takeout). Give 2-3 short, actionable recommendations for the "
                    "rest of their day. Be supportive, not judgmental."
                )
            },
            {
                "role": "user",
                "content": (
                    "I just ate: {dish_name}\n"
                    "My daily status:\n"
                    "- Calories: {total_calories} / {target_calories}\n"
                    "- Protein: {protein_g}g / {target_protein}g\n"
                    "- Remaining planned meals: {has_remaining_meals}\n\n"
                    "What should I do for the rest of the day?"
                )
            }
        ],
        "config": {
            "model": "gpt-4o-mini",
            "max_tokens": 200,
            "temperature": 0.7
        }
    },
    {
        "slug": "expiry_recommendations",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a practical kitchen assistant. Given items about to expire, "
                    "suggest 2-4 brief, actionable ways to use them up. Include quick meal ideas "
                    "using those specific ingredients. Be concise (1 sentence each)."
                )
            },
            {
                "role": "user",
                "content": (
                    "These items are expiring soon:\n{expiring_items_json}\n\n"
                    "How should I use them up? Give brief, actionable suggestions."
                )
            }
        ],
        "config": {
            "model": "gpt-4o-mini",
            "max_tokens": 200,
            "temperature": 0.7
        }
    },
    {
        "slug": "shopping_strategy_recommendations",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a smart grocery shopping advisor. Given the user's restock needs, "
                    "provide 2-4 brief shopping tips. Consider urgency, bulk opportunities, "
                    "and practical advice. Be concise (1 sentence each)."
                )
            },
            {
                "role": "user",
                "content": (
                    "My restock needs:\n"
                    "- Urgent items ({urgent_count}): {urgent_items_json}\n"
                    "- Soon items ({soon_count}): {soon_items_json}\n"
                    "- Bulk opportunities: {bulk_count}\n\n"
                    "What's my best shopping strategy?"
                )
            }
        ],
        "config": {
            "model": "gpt-4o-mini",
            "max_tokens": 200,
            "temperature": 0.7
        }
    },
    {
        "slug": "inventory_status_recommendations",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a nutrition-aware pantry advisor. Given the user's inventory status, "
                    "provide 2-4 brief, personalized recommendations about what to buy, cook, or "
                    "prioritize. Consider nutritional balance and expiry. Be concise."
                )
            },
            {
                "role": "user",
                "content": (
                    "My inventory:\n"
                    "- Total items: {total_items}\n"
                    "- Estimated days remaining: {days_remaining}\n"
                    "- Available protein: {protein_g}g\n"
                    "- Categories: {categories_json}\n"
                    "- Expiring soon: {expiring_items_json}\n"
                    "- Already expired (still in inventory): {expired_items_json}\n"
                    "- All items: {inventory_items_json}\n\n"
                    "What should I prioritize? Flag any expired items that should be discarded."
                )
            }
        ],
        "config": {
            "model": "gpt-4o-mini",
            "max_tokens": 200,
            "temperature": 0.7
        }
    },
    {
        "slug": "ai_creative_recipes",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a creative chef and nutritionist. Generate 3-5 recipes using ONLY "
                    "the provided ingredients. Each recipe must be practical and achievable at home.\n\n"
                    "Mode instructions:\n"
                    "- If mode is 'goal_adherent': prioritize recipes that align with the user's "
                    "calorie and protein targets. Favor high-protein, balanced meals.\n"
                    "- If mode is 'guilt_free': suggest comfort food or indulgent combinations.\n\n"
                    "IMPORTANT: Only use ingredients from the provided list.\n\n"
                    "Return a JSON object with a 'recipes' array. Each recipe must have:\n"
                    "  name: string\n"
                    "  description: string (1-2 sentences)\n"
                    "  cuisine: string (e.g. indian, mediterranean, asian, general)\n"
                    "  ingredients: array of {{name: string, quantity_grams: number}}\n"
                    "    - name must exactly match a canonical_name from the provided ingredient list\n"
                    "    - quantity_grams must be a realistic cooking amount (e.g. 150 for chicken)\n"
                    "  instructions: array of strings (3-5 concise cooking steps)\n"
                    "  estimated_prep_time_min: integer\n"
                    "  estimated_calories: integer (per serving)\n"
                    "  estimated_protein_g: integer\n"
                    "  estimated_carbs_g: integer\n"
                    "  estimated_fat_g: integer\n"
                    "  difficulty: 'easy', 'medium', or 'hard'\n"
                    "  suitable_meal_times: array from ['breakfast','lunch','dinner','snack']\n"
                    "  goals: array from ['muscle_gain','fat_loss','general_health','body_recomp','endurance']\n"
                    "  dietary_tags: array from ['vegan','vegetarian','non_vegetarian','gluten_free','dairy_free']\n\n"
                    "Return ONLY the JSON. No extra text."
                )
            },
            {
                "role": "user",
                "content": (
                    "Mode: {mode}\n"
                    "My goal: {goal_type}\n"
                    "Daily calorie target: {calorie_target}\n"
                    "Daily protein target: {protein_target}g\n\n"
                    "Available ingredients (use canonical_name exactly as the ingredient name):\n"
                    "{available_items_json}\n\n"
                    "Generate 3-5 creative recipes I can make right now."
                )
            }
        ],
        "config": {
            "model": "gpt-4o-mini",
            "max_tokens": 2000,
            "temperature": 0.8,
            "response_format": {"type": "json_object"}
        }
    }
]


async def seed():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db]
    collection = db["llm_prompts"]

    now = datetime.now(timezone.utc)
    for prompt in PROMPTS:
        doc = {
            **prompt,
            "version": 1,
            "active": True,
            "updated_at": now,
        }
        result = await collection.update_one(
            {"slug": prompt["slug"]},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True
        )
        action = "updated" if result.matched_count > 0 else "inserted"
        print(f"  {action}: {prompt['slug']}")

    print(f"\nSeeded {len(PROMPTS)} recommendation prompts.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())