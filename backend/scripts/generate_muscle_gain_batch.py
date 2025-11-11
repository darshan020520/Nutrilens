"""
Generate muscle_gain recipes in calorie bands for optimizer coverage

Strategy: Generate 75 recipes across 3 calorie bands to cover ALL muscle_gain users
- Band 1 (750-950 cal): 30 recipes - covers small-medium users (672-933 cal/meal need)
- Band 2 (950-1150 cal): 25 recipes - covers medium-large users (933-1222 cal/meal need)
- Band 3 (1150-1350 cal): 20 recipes - covers large users (1222-1303 cal/meal need)

With optimizer's 0.5x-1.5x flexibility, each band covers a wide user range.

Dietary mix: 60% non-veg, 30% veg, 10% vegan
All recipes have suitable_meal_times = ["breakfast", "lunch", "dinner", "snack"]
for maximum optimizer flexibility.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import SessionLocal
from app.services.recipe_pipeline import LLMRecipeGenerationPipeline


async def generate_muscle_gain_recipes():
    """Generate 75 muscle_gain recipes across 3 calorie bands"""

    db = SessionLocal()
    pipeline = LLMRecipeGenerationPipeline(db)

    # Generate in calorie bands to cover all user types
    # Start with Band 1 only - test with optimizer before generating others
    batches = [
        {'name': 'Band 1 (Small-Medium)', 'count': 30, 'cal_range': (750, 950)},
        # TODO: Uncomment after Band 1 is tested with optimizer
        # {'name': 'Band 2 (Medium-Large)', 'count': 25, 'cal_range': (950, 1150)},
        # {'name': 'Band 3 (Large)', 'count': 20, 'cal_range': (1150, 1350)},
    ]

    cuisines = ['mediterranean', 'indian', 'continental', 'asian', 'mexican']

    # Dietary distribution: 60% non-veg, 30% veg, 10% vegan
    dietary_options = [
        ['high-protein'],                    # non-veg
        ['high-protein'],                    # non-veg
        ['high-protein'],                    # non-veg
        ['high-protein', 'vegetarian'],      # vegetarian
        ['high-protein', 'vegetarian'],      # vegetarian
        ['high-protein', 'vegan'],           # vegan
    ]

    total_generated = 0
    total_failed = 0

    for batch_idx, batch in enumerate(batches):
        print(f"\n{'='*80}")
        print(f"BATCH {batch_idx+1}: {batch['name']} ({batch['count']} recipes)")
        print(f"Calorie Range: {batch['cal_range'][0]}-{batch['cal_range'][1]} cal")
        print(f"{'='*80}\n")

        min_cal, max_cal = batch['cal_range']
        step = (max_cal - min_cal) // batch['count']

        batch_success = 0
        batch_failed = 0

        for i in range(batch['count']):
            target_cal = min_cal + (i * step)

            # Calculate macros (muscle_gain ratios: 30% protein, 45% carbs, 25% fat)
            protein = (target_cal * 0.30) / 4  # 4 cal per gram
            carbs = (target_cal * 0.45) / 4
            fat = (target_cal * 0.25) / 9  # 9 cal per gram

            # Alternate cuisines and dietary restrictions
            cuisine = cuisines[i % len(cuisines)]
            dietary = dietary_options[i % len(dietary_options)]

            print(f"\nGenerating recipe {i+1}/{batch['count']}...")
            print(f"  Target: {target_cal} cal | {protein:.1f}g protein | {carbs:.1f}g carbs | {fat:.1f}g fat")
            print(f"  Cuisine: {cuisine} | Dietary: {dietary}")

            try:
                result = await pipeline.generate_validated_recipe(
                    goal_type='muscle_gain',
                    target_macros={
                        'calories': target_cal,
                        'protein': protein,
                        'carbs': carbs,
                        'fat': fat
                    },
                    cuisine=cuisine,
                    dietary_restrictions=dietary
                )

                recipe = result['recipe']
                actual_cal = recipe.macros_per_serving['calories']
                variance = abs(actual_cal - target_cal) / target_cal * 100

                print(f"  ✓ Generated: {recipe.title} (ID={recipe.id})")
                print(f"  ✓ Actual: {actual_cal:.0f} cal (variance: {variance:.1f}%)")
                print(f"  ✓ Ingredients: {result['ingredients_matched']} matched, {result['ingredients_created']} created")
                print(f"  ✓ Source: {recipe.source}")

                batch_success += 1
                total_generated += 1

            except Exception as e:
                print(f"  ✗ FAILED: {e}")
                batch_failed += 1
                total_failed += 1
                # Continue with next recipe

        print(f"\n{'='*80}")
        print(f"{batch['name']} COMPLETE")
        print(f"{'='*80}")
        print(f"Success: {batch_success}/{batch['count']}")
        print(f"Failed: {batch_failed}/{batch['count']}")

        # Exit after first batch to test with optimizer before continuing
        print(f"\nExiting after {batch['name']}.")
        print("Test with optimizer before uncommenting next band.")

    pipeline.close()
    db.close()

    print(f"\n{'='*80}")
    print("GENERATION COMPLETE!")
    print(f"{'='*80}")
    print(f"\nTotal recipes generated: {total_generated}")
    print(f"Total failed: {total_failed}")

    if total_generated > 0:
        print("\n✓ Recipes successfully added to database")
        print("✓ Recipes marked with source='llm_generated'")
        print("✓ Dummy recipes (source='manual') still intact")

        print("\n" + "="*80)
        print("NEXT STEPS:")
        print("="*80)
        print("1. Review generated recipes in database:")
        print("   SELECT id, title, source, macros_per_serving->>'calories' as cal")
        print("   FROM recipes WHERE source='llm_generated' ORDER BY id DESC LIMIT 20;")
        print("")
        print("2. Test optimizer with real recipes:")
        print("   python scripts/test_optimizer_with_real_recipes.py")
        print("")
        print("3. If tests pass, delete dummy recipes:")
        print("   -- See instructions in test script output")
    else:
        print("\n✗ No recipes generated successfully")
        print("Check errors above and retry")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("MUSCLE_GAIN RECIPE GENERATOR - BAND 1 (750-950 CAL)")
    print("="*80)
    print("\nThis will generate 30 recipes covering small-medium users:")
    print("  - Calorie range: 750-950 cal")
    print("  - Covers users needing: 500-1425 cal/meal (via optimizer flexibility)")
    print("  - Target macros: 30% protein, 45% carbs, 25% fat")
    print("  - Dietary mix: 60% non-veg, 30% veg, 10% vegan")
    print("  - Cuisines: Mediterranean, Indian, Continental, Asian, Mexican")
    print("  - All recipes suitable for any meal time (optimizer-compatible)")
    print("\nEstimated time: ~75 minutes")
    print("Estimated cost: ~$6-7")
    print("\n" + "="*80)
    print("After completion: Test with optimizer before generating Band 2")
    print("="*80)

    confirm = input("\nContinue? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    asyncio.run(generate_muscle_gain_recipes())
