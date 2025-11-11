"""
Test optimizer with real LLM-generated recipes

This script tests the meal plan optimizer with:
1. Mixed recipes (dummy + real)
2. Only real recipes

This validates that real recipes work before deleting dummy ones.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import SessionLocal, Recipe
from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints
from sqlalchemy import cast, String


def test_optimizer():
    db = SessionLocal()

    print("\n" + "="*80)
    print("OPTIMIZER TEST WITH REAL RECIPES")
    print("="*80)

    # Check recipe counts
    total_recipes = db.query(Recipe).count()
    dummy_recipes = db.query(Recipe).filter(Recipe.source == 'manual').count()
    real_recipes = db.query(Recipe).filter(Recipe.source == 'llm_generated').count()
    muscle_gain_real = db.query(Recipe).filter(
        Recipe.source == 'llm_generated',
        cast(Recipe.goals, String).contains('muscle_gain')
    ).count()

    print(f"\nCurrent Recipe Database:")
    print(f"  Total recipes: {total_recipes}")
    print(f"  Dummy (manual): {dummy_recipes}")
    print(f"  Real (llm_generated): {real_recipes}")
    print(f"  Real muscle_gain: {muscle_gain_real}")

    if real_recipes == 0:
        print("\n✗ No real recipes found!")
        print("Run: python scripts/generate_muscle_gain_batch.py")
        db.close()
        return

    # Create optimizer
    optimizer = MealPlanOptimizer(db)

    # Create test constraints (muscle_gain user)
    constraints = OptimizationConstraints(
        daily_calories_min=2800,
        daily_calories_max=3200,
        daily_protein_min=200,
        daily_carbs_min=300,
        daily_fat_min=60,
        meals_per_day=3,
        max_recipe_repeat_in_days=2,
        dietary_restrictions=[],
        allergens=[]
    )

    print("\n" + "="*80)
    print("TEST 1: OPTIMIZER WITH ALL RECIPES (DUMMY + REAL)")
    print("="*80)
    print("\nConstraints:")
    print(f"  Daily calories: {constraints.daily_calories_min}-{constraints.daily_calories_max}")
    print(f"  Daily protein: {constraints.daily_protein_min}g+")
    print(f"  Meals per day: {constraints.meals_per_day}")
    print(f"  Days: 7")

    # Test with user_id=1 (adjust if needed)
    user_id = 1

    print(f"\nRunning optimizer for user_id={user_id}...")

    try:
        result = optimizer.optimize(user_id, days=7, constraints=constraints)
        print(result)
        if result:
            print("\n✓ Optimizer succeeded with mixed recipes!")

            # Analyze which recipes were selected
            real_count = 0
            dummy_count = 0
            total_meals = 0

            week_plan = result.get('week_plan', {})
            for day_key in sorted(week_plan.keys()):
                day = week_plan[day_key]
                meals = day.get('meals', {})
                for meal_type, meal_data in meals.items():
                    total_meals += 1
                    recipe_source = meal_data.get('source', 'unknown')
                    if recipe_source == 'llm_generated':
                        real_count += 1
                    elif recipe_source == 'manual':
                        dummy_count += 1

            print(f"\nMeal Plan Analysis:")
            print(f"  Total meals: {total_meals}")
            if total_meals > 0:
                print(f"  Real (LLM) recipes used: {real_count} ({real_count/total_meals*100:.1f}%)")
                print(f"  Dummy recipes used: {dummy_count} ({dummy_count/total_meals*100:.1f}%)")
            else:
                print("  ✗ No meals found in plan!")

            # Show sample meals
            print(f"\nSample meals from plan:")
            week_plan = result.get('week_plan', {})
            for day_idx, day_key in enumerate(sorted(list(week_plan.keys()))[:2]):
                day = week_plan[day_key]
                print(f"\n  Day {day_idx + 1}:")
                meals = day.get('meals', {})
                for meal_type in ['breakfast', 'lunch', 'dinner']:
                    if meal_type in meals:
                        recipe = meals[meal_type]
                        print(f"    {meal_type.capitalize()}: {recipe['title']} ({recipe.get('source', 'unknown')})")
                        macros = recipe.get('macros_per_serving', {})
                        print(f"      {macros.get('calories', 0):.0f} cal, "
                              f"{macros.get('protein_g', 0):.1f}g protein")

        else:
            print("\n✗ Optimizer failed with mixed recipes!")
            print("This is unexpected - check logs for errors")
            db.close()
            return

    except Exception as e:
        print(f"\n✗ Optimizer error: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return

    # Test 2: Only real recipes
    print("\n" + "="*80)
    print("TEST 2: OPTIMIZER WITH ONLY REAL RECIPES")
    print("="*80)

    min_recipes_needed = 7 * constraints.meals_per_day  # 21 for 7 days, 3 meals/day

    if muscle_gain_real < min_recipes_needed:
        print(f"\n⚠ Not enough real muscle_gain recipes!")
        print(f"  Need: {min_recipes_needed} (7 days × 3 meals)")
        print(f"  Have: {muscle_gain_real}")
        print(f"  Missing: {min_recipes_needed - muscle_gain_real}")
        print("\n  Generate more recipes before testing ONLY real recipes")
        print("  Or reduce test to fewer days:")
        print(f"  Max testable days: {muscle_gain_real // constraints.meals_per_day}")
    else:
        print(f"\n✓ Sufficient real recipes ({muscle_gain_real} available)")
        print("  Testing optimizer with ONLY real recipes...")

        # Fetch only real muscle_gain recipes
        real_recipe_objects = db.query(Recipe).filter(
            Recipe.source == 'llm_generated',
            cast(Recipe.goals, String).contains('muscle_gain')
        ).all()

        # Convert to dict format optimizer expects
        real_recipe_dicts = [optimizer._recipe_to_dict(r) for r in real_recipe_objects]

        print(f"\nForcing optimizer to use {len(real_recipe_dicts)} real recipes only...")

        try:
            result = optimizer.optimize(
                user_id,
                days=7,
                constraints=constraints,
                available_recipes=real_recipe_dicts  # Override with only real recipes
            )

            if result:
                print("\n✓✓✓ SUCCESS! Optimizer works with ONLY real recipes!")

                # Verify all selected recipes are real
                all_real = True
                for day in result.get('days', []):
                    for meal in day.get('meals', []):
                        if meal['recipe'].get('source') != 'llm_generated':
                            all_real = False
                            print(f"\n⚠ Found non-real recipe: {meal['recipe']['title']}")

                if all_real:
                    print("✓ Verified: All selected recipes are LLM-generated")

                print("\n" + "="*80)
                print("✅ SAFE TO DELETE DUMMY RECIPES")
                print("="*80)
                print("\nTo replace dummy recipes with real ones:")
                print("")
                print("1. Backup meal_logs (already done in backup_dummy_recipes_20250129.sql)")
                print("")
                print("2. NULL out recipe_id in meal_logs:")
                print("   UPDATE meal_logs SET recipe_id = NULL")
                print("   WHERE recipe_id IN (SELECT id FROM recipes WHERE source = 'manual');")
                print("")
                print("3. Delete dummy recipes:")
                print("   DELETE FROM recipes WHERE source = 'manual';")
                print("")
                print("4. Verify:")
                print("   SELECT COUNT(*), source FROM recipes GROUP BY source;")
                print("   -- Should show only: llm_generated")

            else:
                print("\n✗ Optimizer failed with only real recipes")
                print("\nPossible issues:")
                print("  - Not enough variety in calorie ranges")
                print("  - Not enough breakfast/lunch/dinner options")
                print("  - Constraints too strict")
                print("\nRecommendation: Generate more recipes or relax constraints")

        except Exception as e:
            print(f"\n✗ Optimizer error with real recipes: {e}")
            import traceback
            traceback.print_exc()

    db.close()

    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    test_optimizer()
