"""
reseed_recipes.py
-----------------
1. Nullifies recipe_id in meal_logs for all recipes being deleted.
2. Deactivates all existing meal_plans (they reference old recipe IDs in plan_data JSON).
3. Deletes all existing recipes 1-213 (recipe_ingredients cascade automatically).
4. Inserts 45 new well-designed recipes from new_recipes_design.json.
5. Calculates macros_per_serving from actual ingredient nutrition data in the DB.
6. Prints a clear summary at the end.

Run inside the api container:
  docker compose exec api python scripts/reseed_recipes.py

DRY RUN (no writes):
  docker compose exec api python scripts/reseed_recipes.py --dry-run
"""

import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, Recipe, RecipeIngredient, Item, MealLog, MealPlan

DESIGN_FILE = os.path.join(os.path.dirname(__file__), "recipe_audit", "new_recipes_design.json")
DELETE_RANGE = (1, 213)


def calculate_macros(ingredient_rows: list, servings: int) -> dict:
    """
    Sum macros across all ingredients (including optional ones — they are
    normally present) then divide by servings.
    ingredient_rows: list of dicts with keys 'item' (Item ORM), 'quantity_grams', 'is_optional'
    """
    totals = {k: 0.0 for k in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"]}
    missing_nutrition = []

    for row in ingredient_rows:
        item = row["item"]
        qty = row["quantity_grams"] or 0.0
        n = item.nutrition_per_100g or {}
        if not n:
            missing_nutrition.append(item.canonical_name)
            continue
        factor = qty / 100.0
        totals["calories"]  += (n.get("calories",  0) or 0) * factor
        totals["protein_g"] += (n.get("protein_g", 0) or 0) * factor
        totals["carbs_g"]   += (n.get("carbs_g",   0) or 0) * factor
        totals["fat_g"]     += (n.get("fat_g",     0) or 0) * factor
        totals["fiber_g"]   += (n.get("fiber_g",   0) or 0) * factor
        totals["sodium_mg"] += (n.get("sodium_mg", 0) or 0) * factor

    per_serving = {k: round(v / servings, 1) for k, v in totals.items()}
    if missing_nutrition:
        per_serving["_missing_nutrition_for"] = missing_nutrition
    return per_serving


def main(dry_run: bool = False):
    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"  Recipe Reseed Script  —  {mode} MODE")
    print(f"  {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")

    with open(DESIGN_FILE, "r", encoding="utf-8") as f:
        designs = json.load(f)
    print(f"Loaded {len(designs)} recipe designs from design file.\n")

    db = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # Step 1: resolve all canonical_names up front
        # ------------------------------------------------------------------
        print("Step 1: Resolving ingredient canonical names against items table...")
        all_names = {
            ing["canonical_name"]
            for d in designs
            for ing in d.get("ingredients", [])
        }
        items_by_name = {
            item.canonical_name: item
            for item in db.query(Item).filter(Item.canonical_name.in_(all_names)).all()
        }
        missing_global = all_names - set(items_by_name.keys())
        if missing_global:
            print(f"  WARNING — {len(missing_global)} canonical name(s) not found in DB "
                  f"(those ingredients will be skipped):")
            for n in sorted(missing_global):
                print(f"    - {n}")
        else:
            print(f"  All {len(all_names)} item names resolved OK.")
        print()

        # ------------------------------------------------------------------
        # Step 2: null recipe_id in meal_logs
        # ------------------------------------------------------------------
        lo, hi = DELETE_RANGE
        print(f"Step 2: Nullifying recipe_id in meal_logs for recipe IDs {lo}–{hi}...")
        affected_logs = (
            db.query(MealLog)
            .filter(MealLog.recipe_id.between(lo, hi))
            .count()
        )
        print(f"  {affected_logs} meal_log row(s) will have recipe_id set to NULL.")
        if not dry_run:
            db.query(MealLog).filter(MealLog.recipe_id.between(lo, hi)).update(
                {"recipe_id": None}, synchronize_session=False
            )
            db.flush()

        # ------------------------------------------------------------------
        # Step 3: deactivate meal plans
        # ------------------------------------------------------------------
        print("\nStep 3: Deactivating all active meal_plans...")
        active_plans = db.query(MealPlan).filter(MealPlan.is_active == True).count()
        print(f"  {active_plans} active meal_plan(s) will be set is_active=False.")
        if not dry_run:
            db.query(MealPlan).filter(MealPlan.is_active == True).update(
                {"is_active": False}, synchronize_session=False
            )
            db.flush()

        # ------------------------------------------------------------------
        # Step 4: delete old recipes (recipe_ingredients cascade)
        # ------------------------------------------------------------------
        print(f"\nStep 4: Deleting recipes {lo}–{hi}...")
        old_recipe_count = db.query(Recipe).filter(Recipe.id.between(lo, hi)).count()
        old_ri_count = (
            db.query(RecipeIngredient)
            .filter(RecipeIngredient.recipe_id.between(lo, hi))
            .count()
        )
        print(f"  Recipes to delete        : {old_recipe_count}")
        print(f"  RecipeIngredient rows    : {old_ri_count} (cascade)")
        if not dry_run:
            for recipe in db.query(Recipe).filter(Recipe.id.between(lo, hi)).all():
                db.delete(recipe)
            db.flush()

        # ------------------------------------------------------------------
        # Step 5: insert new recipes
        # ------------------------------------------------------------------
        print(f"\nStep 5: Inserting {len(designs)} new recipes...\n")
        inserted = 0

        for idx, design in enumerate(designs, 1):
            title = design.get("title", f"Recipe {idx}")

            # Skip internal metadata keys (used as section markers)
            if set(design.keys()) == {"_note"}:
                continue

            # Resolve ingredients for this recipe
            ingredient_rows = []
            recipe_missing = []
            for ing_design in design.get("ingredients", []):
                cname = ing_design["canonical_name"]
                item = items_by_name.get(cname)
                if item is None:
                    recipe_missing.append(cname)
                else:
                    ingredient_rows.append({
                        "item": item,
                        "quantity_grams": float(ing_design["quantity_grams"]),
                        "is_optional": bool(ing_design.get("is_optional", False)),
                        "preparation_notes": ing_design.get("preparation_notes"),
                    })

            servings = design.get("servings", 1) or 1
            macros = calculate_macros(ingredient_rows, servings)
            missing_nut = macros.pop("_missing_nutrition_for", [])

            # Print per-recipe summary
            status = "OK" if not recipe_missing else f"PARTIAL (missing: {', '.join(recipe_missing)})"
            print(f"  [{idx:02d}] {title}")
            print(f"         {macros['calories']:.0f} kcal | "
                  f"P {macros['protein_g']:.1f}g | "
                  f"C {macros['carbs_g']:.1f}g | "
                  f"F {macros['fat_g']:.1f}g  [{status}]")
            if missing_nut:
                print(f"         (no nutrition data for: {missing_nut})")

            if dry_run:
                inserted += 1
                continue

            recipe = Recipe(
                title=title,
                description=design.get("description"),
                source="custom",
                cuisine=design.get("cuisine"),
                goals=design.get("goals", []),
                tags=design.get("tags", []),
                dietary_tags=design.get("dietary_tags", []),
                suitable_meal_times=design.get("suitable_meal_times", []),
                prep_time_min=design.get("prep_time_min"),
                cook_time_min=design.get("cook_time_min"),
                difficulty_level=design.get("difficulty_level"),
                servings=servings,
                macros_per_serving=macros,
                instructions=design.get("instructions", []),
                meal_prep_notes=design.get("meal_prep_notes"),
                chef_tips=design.get("chef_tips"),
            )
            db.add(recipe)
            db.flush()  # populate recipe.id before adding RecipeIngredients

            for row in ingredient_rows:
                db.add(RecipeIngredient(
                    recipe_id=recipe.id,
                    item_id=row["item"].id,
                    quantity_grams=row["quantity_grams"],
                    is_optional=row["is_optional"],
                    preparation_notes=row["preparation_notes"],
                ))

            inserted += 1

        # ------------------------------------------------------------------
        # Commit / rollback
        # ------------------------------------------------------------------
        if not dry_run:
            db.commit()
        else:
            db.rollback()

        print(f"\n{'='*60}")
        print(f"  {'COMMITTED' if not dry_run else 'DRY RUN — nothing written'}")
        print(f"\n  Old recipes deleted      : {old_recipe_count}")
        print(f"  RecipeIngredients deleted: {old_ri_count}")
        print(f"  meal_logs nulled         : {affected_logs}")
        print(f"  meal_plans deactivated   : {active_plans}")
        print(f"  New recipes inserted     : {inserted}")
        print(f"{'='*60}\n")

    except Exception as e:
        db.rollback()
        print(f"\nERROR — rolled back: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reseed NutriLens recipe database")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without writing to the database"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
