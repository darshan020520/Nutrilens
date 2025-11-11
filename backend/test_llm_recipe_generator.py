"""
Test LLM Recipe Generator
==========================

Test the structured recipe generator with:
1. Basic generation
2. Different goal types
3. Different cuisines
4. Nutrition validation
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.llm_recipe_generator import StructuredRecipeGenerator


def calculate_optimizer_constraints(goal_type: str, user_data: dict):
    """Calculate constraints exactly like optimizer (from previous test)"""

    GOAL_ADJUSTMENTS = {
        'muscle_gain': 500,
        'fat_loss': -500,
        'body_recomp': 0,
        'weight_training': 300,
        'endurance': 200,
        'general_health': 0
    }

    MACRO_RATIOS = {
        'muscle_gain': {"protein": 0.30, "carbs": 0.45, "fat": 0.25},
        'fat_loss': {"protein": 0.35, "carbs": 0.35, "fat": 0.30},
        'body_recomp': {"protein": 0.35, "carbs": 0.40, "fat": 0.25},
        'weight_training': {"protein": 0.30, "carbs": 0.50, "fat": 0.20},
        'endurance': {"protein": 0.20, "carbs": 0.55, "fat": 0.25},
        'general_health': {"protein": 0.25, "carbs": 0.45, "fat": 0.30}
    }

    ACTIVITY_MULTIPLIERS = {
        'sedentary': 1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active': 1.725,
        'extra_active': 1.9
    }

    # Calculate BMR
    bmr = 10 * user_data['weight_kg'] + 6.25 * user_data['height_cm'] - 5 * user_data['age']
    if user_data['sex'] == 'male':
        bmr += 5
    else:
        bmr -= 161

    # Calculate TDEE
    tdee = bmr * ACTIVITY_MULTIPLIERS[user_data['activity_level']]

    # Calculate goal calories
    goal_calories = tdee + GOAL_ADJUSTMENTS[goal_type]

    # Calculate macro targets
    macros = MACRO_RATIOS[goal_type]
    protein_g = (goal_calories * macros['protein']) / 4
    carbs_g = (goal_calories * macros['carbs']) / 4
    fat_g = (goal_calories * macros['fat']) / 9

    # Per-meal targets
    meals_per_day = user_data.get('meals_per_day', 3)
    cal_per_meal = goal_calories / meals_per_day
    protein_per_meal = protein_g / meals_per_day
    carbs_per_meal = carbs_g / meals_per_day
    fat_per_meal = fat_g / meals_per_day

    return {
        'bmr': round(bmr, 2),
        'tdee': round(tdee, 2),
        'goal_calories': round(goal_calories, 2),
        'cal_per_meal': round(cal_per_meal, 2),
        'protein_per_meal': round(protein_per_meal, 2),
        'carbs_per_meal': round(carbs_per_meal, 2),
        'fat_per_meal': round(fat_per_meal, 2),
        'meals_per_day': meals_per_day
    }


async def test_basic_generation():
    """Test 1: Basic recipe generation"""
    print("\n" + "="*80)
    print("TEST 1: Basic Recipe Generation (MUSCLE_GAIN)")
    print("="*80)

    # Sample user
    user_data = {
        'weight_kg': 75,
        'height_cm': 175,
        'age': 28,
        'sex': 'male',
        'activity_level': 'moderately_active',
        'meals_per_day': 3
    }

    # Calculate constraints
    constraints = calculate_optimizer_constraints('muscle_gain', user_data)

    print(f"\nUser Profile:")
    print(f"  75kg male, 28 years old, moderately active")
    print(f"\nOptimizer Constraints:")
    print(f"  Daily Calories: {constraints['goal_calories']} kcal")
    print(f"  Per-Meal Target: {constraints['cal_per_meal']} kcal, "
          f"{constraints['protein_per_meal']}g protein")

    # Generate recipe
    generator = StructuredRecipeGenerator()

    recipe = await generator.generate_recipe(
        goal_type="muscle_gain",
        target_calories=constraints['cal_per_meal'],
        target_protein=constraints['protein_per_meal'],
        target_carbs=constraints['carbs_per_meal'],
        target_fat=constraints['fat_per_meal'],
        cuisine="mediterranean",
        dietary_restrictions=["high-protein"],
        check_duplicates=False  # No DB in test
    )

    print(f"\n{'='*80}")
    print("GENERATED RECIPE")
    print("="*80)
    print(f"\n📝 Name: {recipe.name}")
    print(f"🍽️  Cuisine: {recipe.cuisine}")
    print(f"👥 Servings: {recipe.servings}")
    print(f"⏱️  Prep Time: {recipe.prep_time_minutes} minutes")
    print(f"🏷️  Tags: {', '.join(recipe.dietary_tags)}")

    print(f"\n📊 Nutrition (per serving):")
    print(f"  • Calories: {recipe.calories} kcal")
    print(f"  • Protein: {recipe.protein_g}g")
    print(f"  • Carbs: {recipe.carbs_g}g")
    print(f"  • Fat: {recipe.fat_g}g")
    print(f"  • Fiber: {recipe.fiber_g}g")

    # Validate macro math
    calculated_cal = (
        recipe.protein_g * 4 +
        recipe.carbs_g * 4 +
        recipe.fat_g * 9
    )
    variance = abs(calculated_cal - recipe.calories) / recipe.calories

    print(f"\n✅ Macro Validation:")
    print(f"  Stated Calories: {recipe.calories} kcal")
    print(f"  Calculated (P×4 + C×4 + F×9): {calculated_cal:.0f} kcal")
    print(f"  Variance: {variance*100:.1f}% {'✓ PASS' if variance < 0.05 else '✗ FAIL'}")

    # Check target match
    target_variance = abs(recipe.calories - constraints['cal_per_meal']) / constraints['cal_per_meal']
    print(f"\n🎯 Target Match:")
    print(f"  Target: {constraints['cal_per_meal']} kcal, {constraints['protein_per_meal']}g protein")
    print(f"  Actual: {recipe.calories} kcal, {recipe.protein_g}g protein")
    print(f"  Variance: {target_variance*100:.1f}% {'✓ PASS' if target_variance < 0.15 else '✗ FAIL'}")

    print(f"\n🥗 Ingredients ({len(recipe.ingredients)}):")
    for i, ing in enumerate(recipe.ingredients, 1):
        prep_note = f" ({ing.preparation})" if ing.preparation else ""
        print(f"  {i}. {ing.quantity_grams}g {ing.food_name}{prep_note}")

    print(f"\n👨‍🍳 Instructions ({len(recipe.instructions)} steps):")
    for i, step in enumerate(recipe.instructions, 1):
        print(f"  {i}. {step}")

    return recipe


async def test_different_goals():
    """Test 2: Generate recipes for different goal types"""
    print("\n\n" + "="*80)
    print("TEST 2: Different Goal Types")
    print("="*80)

    user_data = {
        'weight_kg': 70,
        'height_cm': 170,
        'age': 30,
        'sex': 'female',
        'activity_level': 'moderately_active',
        'meals_per_day': 3
    }

    generator = StructuredRecipeGenerator()

    # Test different goals
    goals_to_test = [
        ('fat_loss', 'asian'),
        ('body_recomp', 'indian'),
    ]

    for goal_type, cuisine in goals_to_test:
        print(f"\n{'-'*80}")
        print(f"Goal: {goal_type.upper()}, Cuisine: {cuisine.title()}")
        print('-'*80)

        constraints = calculate_optimizer_constraints(goal_type, user_data)

        recipe = await generator.generate_recipe(
            goal_type=goal_type,
            target_calories=constraints['cal_per_meal'],
            target_protein=constraints['protein_per_meal'],
            target_carbs=constraints['carbs_per_meal'],
            target_fat=constraints['fat_per_meal'],
            cuisine=cuisine,
            dietary_restrictions=["vegetarian"] if cuisine == "indian" else [],
            check_duplicates=False
        )

        print(f"\n✓ Generated: {recipe.name}")
        print(f"  Nutrition: {recipe.calories} cal, "
              f"{recipe.protein_g}g protein")
        print(f"  Main ingredients: {', '.join([ing.food_name for ing in recipe.ingredients[:3]])}")


async def test_validation():
    """Test 3: Nutrition validation"""
    print("\n\n" + "="*80)
    print("TEST 3: Nutrition Validation")
    print("="*80)

    generator = StructuredRecipeGenerator()

    # Generate a recipe
    recipe = await generator.generate_recipe(
        goal_type="muscle_gain",
        target_calories=1000,
        target_protein=75,
        target_carbs=115,
        target_fat=30,
        cuisine="mediterranean",
        check_duplicates=False
    )

    print(f"\nRecipe: {recipe.name}")
    print(f"\nValidation Checks:")

    # Check 1: Macro math
    calculated_cal = (
        recipe.protein_g * 4 +
        recipe.carbs_g * 4 +
        recipe.fat_g * 9
    )
    macro_variance = abs(calculated_cal - recipe.calories) / recipe.calories

    print(f"\n1. Macro Math:")
    print(f"   Protein: {recipe.protein_g}g × 4 = {recipe.protein_g * 4} cal")
    print(f"   Carbs: {recipe.carbs_g}g × 4 = {recipe.carbs_g * 4} cal")
    print(f"   Fat: {recipe.fat_g}g × 9 = {recipe.fat_g * 9} cal")
    print(f"   Total: {calculated_cal:.0f} cal")
    print(f"   Stated: {recipe.calories} cal")
    print(f"   ✓ PASS - Variance: {macro_variance*100:.1f}%" if macro_variance < 0.05 else f"   ✗ FAIL - Variance: {macro_variance*100:.1f}%")

    # Check 2: Target match
    target_cal_variance = abs(recipe.calories - 1000) / 1000
    target_protein_variance = abs(recipe.protein_g - 75) / 75

    print(f"\n2. Target Match:")
    print(f"   Calories: {recipe.calories} vs 1000 target (variance: {target_cal_variance*100:.1f}%)")
    print(f"   Protein: {recipe.protein_g}g vs 75g target (variance: {target_protein_variance*100:.1f}%)")
    print(f"   ✓ PASS" if target_cal_variance < 0.15 and target_protein_variance < 0.15 else "   ✗ FAIL")

    # Check 3: Realistic ranges
    print(f"\n3. Realistic Ranges:")
    checks = [
        ("Calories", recipe.calories, 200, 2000),
        ("Protein", recipe.protein_g, 5, 200),
        ("Carbs", recipe.carbs_g, 0, 300),
        ("Fat", recipe.fat_g, 0, 150),
    ]

    all_pass = True
    for name, value, min_val, max_val in checks:
        in_range = min_val <= value <= max_val
        status = "✓" if in_range else "✗"
        print(f"   {status} {name}: {value} (range: {min_val}-{max_val})")
        if not in_range:
            all_pass = False

    print(f"\n   {'✓ ALL CHECKS PASSED' if all_pass else '✗ SOME CHECKS FAILED'}")


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("LLM RECIPE GENERATOR TESTS")
    print("="*80)

    try:
        # Test 1: Basic generation
        await test_basic_generation()

        # Test 2: Different goals
        await test_different_goals()

        # Test 3: Validation
        await test_validation()

        print("\n\n" + "="*80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nNext Steps:")
        print("1. Implement RecipeIngredientProcessor (match ingredients to DB)")
        print("2. Implement auto-seeding for missing ingredients")
        print("3. Create complete pipeline with database storage")
        print("4. Bulk generate 500 recipes for all goal types")

    except Exception as e:
        print(f"\n\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check API key
    from app.core.config import settings

    if not hasattr(settings, 'openai_api_key') or not settings.openai_api_key:
        print("\n❌ ERROR: OpenAI API key not found!")
        print("Please add to your .env file:")
        print("OPENAI_API_KEY=your_key_here")
        sys.exit(1)

    asyncio.run(main())
