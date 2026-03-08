"""
seed_120_recipes.py
--------------------
1. Seeds 10 new ingredient items (skips any that already exist by canonical_name).
2. Inserts up to 120 recipes from meal_plan_recipes_120.json (skips by title).
3. Calculates macros_per_serving from actual DB nutrition data.
4. Inserts RecipeIngredient rows for each recipe.
5. Supports --dry-run flag (no writes).

Run inside the api container:
  docker compose exec api python scripts/seed_120_recipes.py

DRY RUN:
  docker compose exec api python scripts/seed_120_recipes.py --dry-run
"""

import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import SessionLocal, Recipe, RecipeIngredient, Item

RECIPES_FILE = os.path.join(os.path.dirname(__file__), "meal_plan_recipes_120.json")

# ---------------------------------------------------------------------------
# New items to seed — nutrition per 100g
# ---------------------------------------------------------------------------
NEW_ITEMS = [
    {
        "canonical_name": "apple",
        "aliases": ["apples", "green apple", "red apple"],
        "category": "fruit",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 52, "protein_g": 0.3, "carbs_g": 13.8,
            "fat_g": 0.2, "fiber_g": 2.4, "sodium_mg": 1.0
        },
    },
    {
        "canonical_name": "berries",
        "aliases": ["mixed berries", "blueberries", "strawberries", "raspberries"],
        "category": "fruit",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 57, "protein_g": 0.7, "carbs_g": 14.0,
            "fat_g": 0.3, "fiber_g": 2.0, "sodium_mg": 1.0
        },
    },
    {
        "canonical_name": "cabbage",
        "aliases": ["green cabbage", "lettuce leaves"],
        "category": "vegetable",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 25, "protein_g": 1.3, "carbs_g": 5.8,
            "fat_g": 0.1, "fiber_g": 2.5, "sodium_mg": 18.0
        },
    },
    {
        "canonical_name": "cheddar_cheese",
        "aliases": ["cheddar", "shredded cheddar"],
        "category": "dairy",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 402, "protein_g": 25.0, "carbs_g": 1.3,
            "fat_g": 33.1, "fiber_g": 0.0, "sodium_mg": 621.0
        },
    },
    {
        "canonical_name": "cod",
        "aliases": ["cod fillet", "baked cod"],
        "category": "seafood",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 82, "protein_g": 17.8, "carbs_g": 0.0,
            "fat_g": 0.7, "fiber_g": 0.0, "sodium_mg": 54.0
        },
    },
    {
        "canonical_name": "flaxseeds",
        "aliases": ["flax seeds", "ground flaxseed", "linseed"],
        "category": "seeds",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 534, "protein_g": 18.3, "carbs_g": 28.9,
            "fat_g": 42.2, "fiber_g": 27.3, "sodium_mg": 30.0
        },
    },
    {
        "canonical_name": "ground_beef",
        "aliases": ["minced beef", "lean ground beef", "ground lamb"],
        "category": "meat",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 250, "protein_g": 26.1, "carbs_g": 0.0,
            "fat_g": 15.0, "fiber_g": 0.0, "sodium_mg": 75.0
        },
    },
    {
        "canonical_name": "lemon",
        "aliases": ["lemon juice", "lime", "lime juice"],
        "category": "fruit",
        "unit": "g",
        "is_staple": True,
        "nutrition_per_100g": {
            "calories": 29, "protein_g": 1.1, "carbs_g": 9.3,
            "fat_g": 0.3, "fiber_g": 2.8, "sodium_mg": 2.0
        },
    },
    {
        "canonical_name": "mozzarella",
        "aliases": ["fresh mozzarella", "mozzarella cheese"],
        "category": "dairy",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 280, "protein_g": 19.9, "carbs_g": 2.2,
            "fat_g": 22.4, "fiber_g": 0.0, "sodium_mg": 627.0
        },
    },
    {
        "canonical_name": "tempeh",
        "aliases": ["fermented soy tempeh"],
        "category": "protein",
        "unit": "g",
        "is_staple": False,
        "nutrition_per_100g": {
            "calories": 192, "protein_g": 20.3, "carbs_g": 7.6,
            "fat_g": 10.8, "fiber_g": 0.0, "sodium_mg": 9.0
        },
    },
]


def calculate_macros(ingredient_rows: list, servings: int) -> dict:
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
    print(f"  Seed 120 Recipes  —  {mode} MODE")
    print(f"  {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")

    with open(RECIPES_FILE, "r", encoding="utf-8") as f:
        recipes_to_seed = json.load(f)
    print(f"Loaded {len(recipes_to_seed)} recipe(s) from file.\n")

    db = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # Step 1: Seed new items
        # ------------------------------------------------------------------
        print("Step 1: Seeding new items...")
        existing_items = {
            item.canonical_name
            for item in db.query(Item.canonical_name).all()
        }

        items_inserted = []
        items_skipped = []

        for item_data in NEW_ITEMS:
            cname = item_data["canonical_name"]
            if cname in existing_items:
                items_skipped.append(cname)
                print(f"  SKIP  {cname} (already exists)")
                continue

            print(f"  ADD   {cname}  [{item_data.get('category')}]")
            if not dry_run:
                db.add(Item(
                    canonical_name=cname,
                    aliases=item_data.get("aliases", []),
                    category=item_data.get("category"),
                    unit=item_data.get("unit", "g"),
                    is_staple=item_data.get("is_staple", False),
                    nutrition_per_100g=item_data.get("nutrition_per_100g"),
                    source="custom",
                ))
            items_inserted.append(cname)

        if not dry_run:
            db.flush()

        print(f"\n  Items: {len(items_inserted)} added, {len(items_skipped)} skipped.\n")

        # ------------------------------------------------------------------
        # Step 2: Resolve all ingredient canonical_names
        # ------------------------------------------------------------------
        print("Step 2: Resolving ingredient canonical names against items table...")
        all_names = {
            ing["canonical_name"]
            for recipe in recipes_to_seed
            for ing in recipe.get("ingredients", [])
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
            print(f"  All {len(all_names)} ingredient name(s) resolved OK.")
        print()

        # ------------------------------------------------------------------
        # Step 3: Seed recipes
        # ------------------------------------------------------------------
        print(f"Step 3: Inserting recipes...\n")

        existing_titles = {
            r.title
            for r in db.query(Recipe.title).all()
        }

        recipes_inserted = 0
        recipes_skipped = []

        for idx, design in enumerate(recipes_to_seed, 1):
            title = design.get("title", f"Recipe {idx}")

            if title in existing_titles:
                recipes_skipped.append(title)
                print(f"  [{idx:03d}] SKIP  {title}")
                continue

            ingredient_rows = []
            recipe_missing = []
            for ing_design in design.get("ingredients", []):
                cname = ing_design["canonical_name"]
                item = items_by_name.get(cname)
                if item is None:
                    recipe_missing.append(cname)
                else:
                    ingredient_rows.append({
                        "item":              item,
                        "quantity_grams":    float(ing_design["quantity_grams"]),
                        "is_optional":       bool(ing_design.get("is_optional", False)),
                        "preparation_notes": ing_design.get("preparation_notes"),
                    })

            servings = design.get("servings", 1) or 1
            macros = calculate_macros(ingredient_rows, servings)
            missing_nut = macros.pop("_missing_nutrition_for", [])

            status = "OK" if not recipe_missing else f"PARTIAL (missing: {', '.join(recipe_missing)})"
            print(f"  [{idx:03d}] {title}")
            print(f"         {macros['calories']:.0f} kcal | "
                  f"P {macros['protein_g']:.1f}g | "
                  f"C {macros['carbs_g']:.1f}g | "
                  f"F {macros['fat_g']:.1f}g  [{status}]")
            if missing_nut:
                print(f"         (no nutrition data for: {missing_nut})")

            if dry_run:
                recipes_inserted += 1
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
            db.flush()

            for row in ingredient_rows:
                db.add(RecipeIngredient(
                    recipe_id=recipe.id,
                    item_id=row["item"].id,
                    quantity_grams=row["quantity_grams"],
                    is_optional=row["is_optional"],
                    preparation_notes=row["preparation_notes"],
                ))

            recipes_inserted += 1

        # ------------------------------------------------------------------
        # Commit / rollback
        # ------------------------------------------------------------------
        if not dry_run:
            db.commit()
        else:
            db.rollback()

        print(f"\n{'='*60}")
        print(f"  {'COMMITTED' if not dry_run else 'DRY RUN — nothing written'}")
        print(f"\n  Items inserted   : {len(items_inserted)}")
        print(f"  Items skipped    : {len(items_skipped)}")
        print(f"  Recipes inserted : {recipes_inserted}")
        print(f"  Recipes skipped  : {len(recipes_skipped)}")
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
    parser = argparse.ArgumentParser(description="Seed 120 recipes into NutriLens DB")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without writing to the database"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
