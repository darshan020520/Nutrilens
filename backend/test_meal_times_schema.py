"""
Quick test to verify schema change forces all 4 meal times

Tests that LLM returns ["breakfast", "lunch", "dinner", "snack"]
with the new min_items=4, max_items=4 constraint.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.models.database import SessionLocal
from app.services.recipe_pipeline import LLMRecipeGenerationPipeline


async def test_meal_times_schema():
    """Generate 3 test recipes and verify suitable_meal_times field"""

    db = SessionLocal()
    pipeline = LLMRecipeGenerationPipeline(db)

    print("\n" + "="*80)
    print("TESTING MEAL TIMES SCHEMA CHANGE")
    print("="*80)
    print("\nExpected: All recipes should have exactly 4 meal times:")
    print("  [\"breakfast\", \"lunch\", \"dinner\", \"snack\"]")
    print("\n" + "="*80)

    test_cases = [
        {
            "name": "Breakfast Recipe",
            "target_macros": {
                "calories": 600,
                "protein": 45,
                "carbs": 67.5,
                "fat": 16.7
            },
            "cuisine": "mediterranean"
        },
        {
            "name": "Lunch Recipe",
            "target_macros": {
                "calories": 900,
                "protein": 67.5,
                "carbs": 101.25,
                "fat": 25
            },
            "cuisine": "indian"
        },
        {
            "name": "Dinner Recipe",
            "target_macros": {
                "calories": 1000,
                "protein": 75,
                "carbs": 112.5,
                "fat": 27.8
            },
            "cuisine": "asian"
        }
    ]

    success_count = 0
    failure_count = 0
    all_have_4_meal_times = True

    for i, test_case in enumerate(test_cases):
        print(f"\n{'='*80}")
        print(f"TEST {i+1}/3: {test_case['name']}")
        print(f"{'='*80}")
        print(f"Target: {test_case['target_macros']['calories']} cal | "
              f"{test_case['target_macros']['protein']:.1f}g protein")
        print(f"Cuisine: {test_case['cuisine']}")

        try:
            result = await pipeline.generate_validated_recipe(
                goal_type='muscle_gain',
                target_macros=test_case['target_macros'],
                cuisine=test_case['cuisine'],
                dietary_restrictions=['high-protein']
            )

            recipe = result['recipe']
            meal_times = recipe.suitable_meal_times

            print(f"\n✓ Recipe Generated: {recipe.title}")
            print(f"  ID: {recipe.id}")
            print(f"  Suitable Meal Times: {meal_times}")
            print(f"  Count: {len(meal_times)}")

            # Verify schema compliance
            if len(meal_times) == 4:
                expected_set = {"breakfast", "lunch", "dinner", "snack"}
                actual_set = set(meal_times)

                if actual_set == expected_set:
                    print(f"  ✓✓ SCHEMA COMPLIANT: All 4 meal times present")
                    success_count += 1
                else:
                    print(f"  ✗ WRONG VALUES: Expected {expected_set}, got {actual_set}")
                    all_have_4_meal_times = False
                    failure_count += 1
            else:
                print(f"  ✗ WRONG COUNT: Expected 4 meal times, got {len(meal_times)}")
                all_have_4_meal_times = False
                failure_count += 1

            # Show nutrition
            actual_cal = recipe.macros_per_serving['calories']
            target_cal = test_case['target_macros']['calories']
            variance = abs(actual_cal - target_cal) / target_cal * 100

            print(f"  Actual Nutrition: {actual_cal:.0f} cal (variance: {variance:.1f}%)")
            print(f"  Ingredients: {result['ingredients_matched']} matched, "
                  f"{result['ingredients_created']} created")

        except Exception as e:
            print(f"\n✗ GENERATION FAILED: {e}")
            failure_count += 1
            all_have_4_meal_times = False
            import traceback
            traceback.print_exc()

    pipeline.close()
    db.close()

    print(f"\n{'='*80}")
    print("TEST RESULTS")
    print(f"{'='*80}")
    print(f"Success: {success_count}/3")
    print(f"Failures: {failure_count}/3")

    if all_have_4_meal_times and success_count == 3:
        print("\n✓✓✓ ALL TESTS PASSED!")
        print("✓ Schema change successful - LLM returns all 4 meal times")
        print("✓ Safe to proceed with batch generation")

        print("\n" + "="*80)
        print("NEXT STEP: Generate 20 breakfast recipes")
        print("="*80)
        print("\nRun:")
        print("  python scripts/generate_muscle_gain_batch.py")
        print("\nOr adjust to generate only breakfast batch first")

    else:
        print("\n✗ TESTS FAILED")
        print("Schema change did NOT work as expected")
        print("\nPossible issues:")
        print("  1. LLM not respecting min_items/max_items constraints")
        print("  2. Schema not properly updated in RecipeStructured model")
        print("  3. OpenAI API caching old schema")
        print("\nDo NOT proceed with batch generation until this is fixed")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("MEAL TIMES SCHEMA TEST")
    print("="*80)
    print("\nThis will generate 3 test recipes to verify schema change")
    print("Estimated time: ~5 minutes")
    print("Estimated cost: ~$0.50")
    print("\n" + "="*80)

    asyncio.run(test_meal_times_schema())
