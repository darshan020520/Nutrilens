"""
fetch_recipes_for_audit.py
--------------------------
Dumps every recipe (with full ingredient details and item nutrition) to
scripts/recipe_audit/current_recipes.json  for offline review.

Run inside the api container:
  docker compose exec api python scripts/fetch_recipes_for_audit.py
"""

import json
import os
import sys

# Make sure the app package is importable when run from /app in the container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, Recipe, RecipeIngredient, Item

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "recipe_audit")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current_recipes.json")


def fetch_all_recipes(db) -> list:
    recipes = db.query(Recipe).order_by(Recipe.id).all()
    result = []

    for r in recipes:
        ingredients = []
        for ri in r.ingredients:
            item = ri.item
            ingredients.append({
                "recipe_ingredient_id": ri.id,
                "item_id": item.id if item else None,
                "canonical_name": item.canonical_name if item else None,
                "category": item.category if item else None,
                "quantity_grams": ri.quantity_grams,
                "is_optional": ri.is_optional,
                "preparation_notes": ri.preparation_notes,
                "original_ingredient_text": ri.original_ingredient_text,
                # nutrition per 100g so we can recalculate macros independently
                "nutrition_per_100g": item.nutrition_per_100g if item else None,
            })

        result.append({
            "recipe_id": r.id,
            "title": r.title,
            "description": r.description,
            "source": r.source,
            "cuisine": r.cuisine,
            "goals": r.goals,
            "tags": r.tags,
            "dietary_tags": r.dietary_tags,
            "suitable_meal_times": r.suitable_meal_times,
            "prep_time_min": r.prep_time_min,
            "cook_time_min": r.cook_time_min,
            "difficulty_level": r.difficulty_level,
            "servings": r.servings,
            # Stored macros — we will re-verify these against ingredients below
            "macros_per_serving_stored": r.macros_per_serving,
            # Recalculated from ingredient nutrition data
            "macros_per_serving_calculated": _calculate_macros(ingredients, r.servings or 1),
            "instructions": r.instructions,
            "meal_prep_notes": r.meal_prep_notes,
            "chef_tips": r.chef_tips,
            "ingredients": ingredients,
        })

    return result


def _calculate_macros(ingredients: list, servings: int) -> dict:
    """
    Sum macros across all (non-optional) ingredients using nutrition_per_100g
    and quantity_grams, then divide by servings.
    Returns None if any ingredient is missing nutrition data.
    """
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0,
               "fat_g": 0.0, "fiber_g": 0.0, "sodium_mg": 0.0}
    missing = []

    for ing in ingredients:
        if ing.get("is_optional"):
            continue
        n = ing.get("nutrition_per_100g")
        qty = ing.get("quantity_grams") or 0
        name = ing.get("canonical_name", "?")
        if not n:
            missing.append(name)
            continue
        factor = qty / 100.0
        totals["calories"]   += (n.get("calories", 0) or 0) * factor
        totals["protein_g"]  += (n.get("protein_g", 0) or 0) * factor
        totals["carbs_g"]    += (n.get("carbs_g", 0) or 0) * factor
        totals["fat_g"]      += (n.get("fat_g", 0) or 0) * factor
        totals["fiber_g"]    += (n.get("fiber_g", 0) or 0) * factor
        totals["sodium_mg"]  += (n.get("sodium_mg", 0) or 0) * factor

    per_serving = {k: round(v / servings, 1) for k, v in totals.items()}
    if missing:
        per_serving["_missing_nutrition_for"] = missing
    return per_serving


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db = SessionLocal()
    try:
        print("Fetching recipes from database...")
        recipes = fetch_all_recipes(db)
        print(f"  Found {len(recipes)} recipes")
    finally:
        db.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False, default=str)

    print(f"Written to: {OUTPUT_FILE}")

    # Quick summary
    print("\n--- Summary ---")
    suspicious = [
        r for r in recipes
        if any(kw in r["title"].lower() for kw in [
            "flexible", "builder", "generic", "custom", "template",
            "meal", "protein", "bulk", "cut", "option"
        ])
    ]
    print(f"  Recipes with generic/arbitrary titles: {len(suspicious)}")
    for r in suspicious:
        print(f"    [{r['recipe_id']}] {r['title']}")

    # Macro mismatch check
    mismatches = []
    for r in recipes:
        stored = r["macros_per_serving_stored"] or {}
        calc   = r["macros_per_serving_calculated"]
        s_cal  = stored.get("calories", 0) or 0
        c_cal  = calc.get("calories", 0) or 0
        if abs(s_cal - c_cal) > 50:   # > 50 kcal difference
            mismatches.append((r["recipe_id"], r["title"], s_cal, c_cal))

    print(f"\n  Recipes with calorie mismatch > 50 kcal (stored vs calculated): {len(mismatches)}")
    for rid, title, s, c in mismatches:
        print(f"    [{rid}] {title}: stored={s:.0f} kcal  calculated={c:.0f} kcal")


if __name__ == "__main__":
    main()
