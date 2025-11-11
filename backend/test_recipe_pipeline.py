"""
Test Complete Recipe Generation Pipeline
=========================================

Tests the end-to-end flow:
1. Generate recipe with LLM (with ALL fields)
2. Validate nutrition
3. Match/auto-seed ingredients
4. Store in database

Run: python -m test_recipe_pipeline
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.models.database import SessionLocal
from app.services.recipe_pipeline import LLMRecipeGenerationPipeline


def calculate_optimizer_targets(
    goal_type: str,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str,
    meals_per_day: int = 3
) -> dict:
    """
    Calculate targets exactly like optimizer does

    This ensures recipes are compatible with optimizer constraints
    """

    # BMR (Mifflin-St Jeor)
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == 'male':
        bmr += 5
    else:
        bmr -= 161

    # TDEE
    activity_multipliers = {
        'sedentary': 1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active': 1.725,
        'extra_active': 1.9
    }
    tdee = bmr * activity_multipliers.get(activity_level, 1.55)

    # Goal adjustments
    goal_adjustments = {
        'muscle_gain': 500,
        'fat_loss': -500,
        'body_recomp': 0,
        'endurance': 200,
        'weight_training': 300
    }
    goal_calories = tdee + goal_adjustments.get(goal_type, 0)

    # Macro ratios
    macro_ratios = {
        'muscle_gain': {'protein': 0.30, 'carbs': 0.45, 'fat': 0.25},
        'fat_loss': {'protein': 0.35, 'carbs': 0.30, 'fat': 0.35},
        'body_recomp': {'protein': 0.30, 'carbs': 0.40, 'fat': 0.30},
        'endurance': {'protein': 0.20, 'carbs': 0.55, 'fat': 0.25},
        'weight_training': {'protein': 0.30, 'carbs': 0.45, 'fat': 0.25}
    }
    ratios = macro_ratios.get(goal_type, {'protein': 0.30, 'carbs': 0.40, 'fat': 0.30})

    # Calculate macros
    protein_g = (goal_calories * ratios['protein']) / 4
    carbs_g = (goal_calories * ratios['carbs']) / 4
    fat_g = (goal_calories * ratios['fat']) / 9

    # Per meal
    cal_per_meal = goal_calories / meals_per_day
    protein_per_meal = protein_g / meals_per_day
    carbs_per_meal = carbs_g / meals_per_day
    fat_per_meal = fat_g / meals_per_day

    return {
        'calories': cal_per_meal,
        'protein': protein_per_meal,
        'carbs': carbs_per_meal,
        'fat': fat_per_meal,
        'daily_totals': {
            'calories': goal_calories,
            'protein': protein_g,
            'carbs': carbs_g,
            'fat': fat_g
        },
        'calculation': {
            'bmr': bmr,
            'tdee': tdee,
            'goal_adjustment': goal_adjustments.get(goal_type, 0),
            'goal_calories': goal_calories
        }
    }


async def test_single_recipe():
    """Test generating a single recipe"""

    print("\n" + "="*80)
    print("TEST 1: SINGLE RECIPE GENERATION")
    print("="*80)

    # Simulate optimizer calculating targets
    print("\nCalculating targets (like optimizer does)...")
    user_data = {
        'weight_kg': 75,
        'height_cm': 175,
        'age': 28,
        'sex': 'male',
        'activity_level': 'moderately_active'
    }

    target_macros = calculate_optimizer_targets(
        goal_type='muscle_gain',
        **user_data
    )

    print(f"\nUser Profile:")
    print(f"  Weight: {user_data['weight_kg']}kg")
    print(f"  Height: {user_data['height_cm']}cm")
    print(f"  Age: {user_data['age']}")
    print(f"  Sex: {user_data['sex']}")
    print(f"  Activity: {user_data['activity_level']}")

    print(f"\nCalculation:")
    print(f"  BMR: {target_macros['calculation']['bmr']:.0f} kcal")
    print(f"  TDEE: {target_macros['calculation']['tdee']:.0f} kcal")
    print(f"  Goal Adjustment: {target_macros['calculation']['goal_adjustment']:+.0f} kcal")
    print(f"  Goal Calories: {target_macros['calculation']['goal_calories']:.0f} kcal")

    print(f"\nPer Meal Targets (3 meals):")
    print(f"  Calories: {target_macros['calories']:.0f} kcal")
    print(f"  Protein: {target_macros['protein']:.1f}g")
    print(f"  Carbs: {target_macros['carbs']:.1f}g")
    print(f"  Fat: {target_macros['fat']:.1f}g")

    # Generate recipe
    db = SessionLocal()
    pipeline = LLMRecipeGenerationPipeline(db)

    try:
        result = await pipeline.generate_validated_recipe(
            goal_type='muscle_gain',
            target_macros={
                'calories': target_macros['calories'],
                'protein': target_macros['protein'],
                'carbs': target_macros['carbs'],
                'fat': target_macros['fat']
            },
            cuisine='mediterranean',
            dietary_restrictions=['high-protein']
        )

        print("\n" + "="*80)
        print("RESULT")
        print("="*80)

        recipe = result['recipe']
        print(f"\nRecipe ID: {recipe.id}")
        print(f"Title: {recipe.title}")  # ✅ Fixed: 'title' not 'name'
        print(f"Description: {recipe.description}")  # ✅ New field
        print(f"Cuisine: {recipe.cuisine}")  # ✅ Fixed: single string not array
        print(f"Tags: {', '.join(recipe.tags)}")  # ✅ New field
        print(f"Dietary Tags: {', '.join(recipe.dietary_tags)}")
        print(f"Suitable Meal Times: {', '.join(recipe.suitable_meal_times)}")  # ✅ New field
        print(f"Difficulty: {recipe.difficulty_level}")  # ✅ New field
        print(f"Servings: {recipe.servings}")
        print(f"Prep Time: {recipe.prep_time_min} minutes")  # ✅ Fixed: 'prep_time_min'
        print(f"Source: {recipe.source}")

        print(f"\nLLM Nutrition (per serving):")
        nutrition = result['llm_nutrition']
        print(f"  Calories: {nutrition['calories']:.0f} kcal (target: {target_macros['calories']:.0f})")
        print(f"  Protein: {nutrition['protein_g']:.1f}g (target: {target_macros['protein']:.1f}g)")
        print(f"  Carbs: {nutrition['carbs_g']:.1f}g (target: {target_macros['carbs']:.1f}g)")
        print(f"  Fat: {nutrition['fat_g']:.1f}g (target: {target_macros['fat']:.1f}g)")
        print(f"  Fiber: {nutrition['fiber_g']:.1f}g")

        # Calculate variances
        print(f"\nVariances:")
        cal_var = abs(nutrition['calories'] - target_macros['calories']) / target_macros['calories']
        protein_var = abs(nutrition['protein_g'] - target_macros['protein']) / target_macros['protein']
        carbs_var = abs(nutrition['carbs_g'] - target_macros['carbs']) / target_macros['carbs']
        fat_var = abs(nutrition['fat_g'] - target_macros['fat']) / target_macros['fat']

        print(f"  Calories: {cal_var*100:.1f}%")
        print(f"  Protein: {protein_var*100:.1f}%")
        print(f"  Carbs: {carbs_var*100:.1f}%")
        print(f"  Fat: {fat_var*100:.1f}%")

        print(f"\nIngredient Processing:")
        print(f"  Total ingredients: {len(result['recipe_ingredients'])}")
        print(f"  Matched existing: {result['ingredients_matched']}")
        print(f"  Auto-seeded: {result['ingredients_created']}")

        print(f"\nRecipe Ingredients:")
        for ri in result['recipe_ingredients']:
            # ✅ Fixed: Use correct field name
            print(f"  - {ri.original_ingredient_text} (item_id={ri.item_id}, confidence={ri.normalized_confidence:.2f})")

        print(f"\nInstructions:")
        # ✅ Fixed: instructions is a JSON list, not a string!
        instructions_list = recipe.instructions if isinstance(recipe.instructions, list) else []
        for i, step in enumerate(instructions_list[:3], 1):
            print(f"  {i}. {step}")
        if len(instructions_list) > 3:
            remaining = len(instructions_list) - 3
            print(f"  ... and {remaining} more steps")

        print("\n✓ TEST PASSED: Recipe generated and stored successfully!")

        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        pipeline.close()
        db.close()


async def test_multiple_goals():
    """Test generating recipes for different goal types"""

    print("\n" + "="*80)
    print("TEST 2: MULTIPLE GOAL TYPES")
    print("="*80)

    goal_types = ['muscle_gain', 'fat_loss', 'body_recomp']
    cuisines = ['mediterranean', 'indian', 'italian']

    user_data = {
        'weight_kg': 70,
        'height_cm': 170,
        'age': 30,
        'sex': 'female',
        'activity_level': 'moderately_active'
    }

    db = SessionLocal()
    pipeline = LLMRecipeGenerationPipeline(db)

    results = []

    try:
        for goal_type, cuisine in zip(goal_types, cuisines):
            print(f"\n{'-'*80}")
            print(f"Testing: {goal_type.upper()} + {cuisine.upper()}")
            print(f"{'-'*80}")

            target_macros = calculate_optimizer_targets(
                goal_type=goal_type,
                **user_data
            )

            try:
                result = await pipeline.generate_validated_recipe(
                    goal_type=goal_type,
                    target_macros={
                        'calories': target_macros['calories'],
                        'protein': target_macros['protein'],
                        'carbs': target_macros['carbs'],
                        'fat': target_macros['fat']
                    },
                    cuisine=cuisine,
                    dietary_restrictions=[]
                )

                recipe = result['recipe']
                nutrition = result['llm_nutrition']

                # ✅ Fixed: Use correct field names
                print(f"\n✓ Generated: {recipe.title}")
                print(f"  Description: {recipe.description[:80]}...")  # First 80 chars
                print(f"  Tags: {', '.join(recipe.tags[:3])}")  # First 3 tags
                print(f"  Difficulty: {recipe.difficulty_level}")
                print(f"  Meal Times: {', '.join(recipe.suitable_meal_times)}")
                print(f"  Nutrition: {nutrition['calories']:.0f} cal, "
                     f"{nutrition['protein_g']:.1f}g protein, "
                     f"{nutrition['carbs_g']:.1f}g carbs, "
                     f"{nutrition['fat_g']:.1f}g fat")
                print(f"  Ingredients: {result['ingredients_matched']} matched, "
                     f"{result['ingredients_created']} created")

                results.append({
                    'goal_type': goal_type,
                    'cuisine': cuisine,
                    'recipe': recipe,
                    'success': True
                })

            except Exception as e:
                print(f"\n✗ Failed: {e}")
                results.append({
                    'goal_type': goal_type,
                    'cuisine': cuisine,
                    'success': False,
                    'error': str(e)
                })

        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)

        successes = sum(1 for r in results if r['success'])
        print(f"\nResults: {successes}/{len(results)} successful")

        for r in results:
            status = "✓" if r['success'] else "✗"
            print(f"  {status} {r['goal_type']} + {r['cuisine']}")
            if r['success']:
                print(f"     → {r['recipe'].title} (ID={r['recipe'].id})")

        if successes == len(results):
            print("\n✓ ALL TESTS PASSED!")
            return True
        else:
            print(f"\n⚠ {len(results) - successes} test(s) failed")
            return False

    finally:
        pipeline.close()
        db.close()


async def main():
    """Run all tests"""

    print("\n" + "="*80)
    print("RECIPE PIPELINE INTEGRATION TESTS")
    print("="*80)

    try:
        # Test 1: Single recipe
        test1_passed = await test_single_recipe()

        # Test 2: Multiple goals (only if test 1 passed)
        if test1_passed:
            print("\n")
            test2_passed = await test_multiple_goals()
        else:
            print("\n⚠ Skipping Test 2 because Test 1 failed")
            test2_passed = False

        # Final summary
        print("\n" + "="*80)
        print("FINAL RESULTS")
        print("="*80)
        print(f"Test 1 (Single Recipe): {'✓ PASSED' if test1_passed else '✗ FAILED'}")
        print(f"Test 2 (Multiple Goals): {'✓ PASSED' if test2_passed else '✗ FAILED'}")

        if test1_passed and test2_passed:
            print("\n✓ ALL TESTS PASSED!")
            print("\nNext steps:")
            print("  1. Review generated recipes in database")
            print("  2. Test with optimizer integration")
            print("  3. Begin bulk recipe generation (500 recipes)")
        else:
            print("\n⚠ SOME TESTS FAILED - Review errors above")

    except Exception as e:
        print(f"\n✗ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
