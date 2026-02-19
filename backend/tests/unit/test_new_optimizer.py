# test_meal_optimizer_simple.py
# Simple version without external dependencies

import json
from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints

def print_meal_plan_simple(result, constraints, test_name):
    """Print meal plan in simple format"""
    
    print("\n" + "="*80)
    print(f"TEST: {test_name}")
    print("="*80)
    
    if not result:
        print("❌ No meal plan generated!")
        return
    
    print(f"\n📊 OPTIMIZATION METHOD: {result['optimization_method']}")
    
    if 'warning' in result:
        print(f"⚠️  Warning: {result['warning']}")
    
    # Summary
    print(f"\n📈 SUMMARY:")
    print(f"  Total Weekly Calories: {result['total_calories']:.0f}")
    print(f"  Avg Daily Calories: {result.get('avg_daily_calories', result['total_calories']/7):.0f}")
    print(f"  Avg Daily Protein: {result['avg_macros']['protein_g']:.1f}g (Target min: {constraints.daily_protein_min}g)")
    print(f"  Avg Daily Carbs: {result['avg_macros']['carbs_g']:.1f}g")
    print(f"  Avg Daily Fat: {result['avg_macros']['fat_g']:.1f}g")
    
    # Track recipe usage
    recipe_usage = {}
    
    # Show each day's meals
    print(f"\n📅 DAILY MEAL PLANS:")
    print("-"*80)
    
    for day_key in sorted(result['week_plan'].keys()):
        day_num = int(day_key.split('_')[1]) + 1
        day_data = result['week_plan'][day_key]
        
        print(f"\n>>> Day {day_num}")
        
        meals = day_data.get('meals', {})
        day_calories = 0
        day_protein = 0
        day_carbs = 0
        day_fat = 0
        
        if not meals:
            print("   No meals found!")
            continue
        
        for meal_time, recipe in meals.items():
            if recipe:
                recipe_id = recipe.get('id', 0)
                recipe_name = recipe.get('title', 'Unknown')
                macros = recipe.get('macros_per_serving', {})
                
                # Track usage
                if recipe_id not in recipe_usage:
                    recipe_usage[recipe_id] = {'name': recipe_name, 'count': 0}
                recipe_usage[recipe_id]['count'] += 1
                
                # Accumulate day totals
                calories = macros.get('calories', 0)
                protein = macros.get('protein_g', 0)
                carbs = macros.get('carbs_g', 0)
                fat = macros.get('fat_g', 0)
                
                day_calories += calories
                day_protein += protein
                day_carbs += carbs
                day_fat += fat
                
                # Print meal details
                print(f"\n   {meal_time.upper()}:")
                print(f"      Recipe: {recipe_name}")
                print(f"      Calories: {calories:.0f} | Protein: {protein:.1f}g | Carbs: {carbs:.1f}g | Fat: {fat:.1f}g")
            else:
                print(f"\n   {meal_time.upper()}: No recipe assigned")
        
        # Day totals
        print(f"\n   Day {day_num} Totals:")
        print(f"      Calories: {day_calories:.0f} ", end="")
        
        # Check constraints
        if constraints.daily_calories_min <= day_calories <= constraints.daily_calories_max:
            print("✓")
        else:
            print(f"(Target: {constraints.daily_calories_min}-{constraints.daily_calories_max})")
        
        print(f"      Protein: {day_protein:.1f}g ", end="")
        if day_protein >= constraints.daily_protein_min:
            print("✓")
        else:
            print(f"(Below min: {constraints.daily_protein_min}g)")
        
        print(f"      Carbs: {day_carbs:.1f}g | Fat: {day_fat:.1f}g")
    
    # Recipe variety check
    print(f"\n🔄 RECIPE USAGE:")
    print("-"*40)
    
    repetition_issues = []
    for recipe_id, data in recipe_usage.items():
        print(f"  {data['name']}: used {data['count']} times", end="")
        if data['count'] > constraints.max_recipe_repeat_in_days:
            print(" ⚠️ (exceeds repetition limit)")
            repetition_issues.append(data['name'])
        else:
            print(" ✓")
    
    # Final verdict
    print(f"\n✅ CONSTRAINT CHECK:")
    print("-"*40)
    
    avg_calories = result['total_calories'] / len(result['week_plan'])
    
    # Check all constraints
    checks_passed = []
    checks_failed = []
    
    # Calories (with 15% tolerance)
    if constraints.daily_calories_min * 0.85 <= avg_calories <= constraints.daily_calories_max * 1.15:
        checks_passed.append(f"Calories: {avg_calories:.0f} (within tolerance)")
    else:
        checks_failed.append(f"Calories: {avg_calories:.0f} (outside tolerance)")
    
    # Protein (with 10% tolerance)
    if result['avg_macros']['protein_g'] >= constraints.daily_protein_min * 0.9:
        checks_passed.append(f"Protein: {result['avg_macros']['protein_g']:.1f}g ≥ minimum")
    else:
        checks_failed.append(f"Protein: {result['avg_macros']['protein_g']:.1f}g < minimum")
    
    # Variety
    if not repetition_issues:
        checks_passed.append("Recipe variety maintained")
    else:
        checks_failed.append(f"Recipe repetition issues: {', '.join(repetition_issues[:3])}")
    
    print("  PASSED:")
    for check in checks_passed:
        print(f"    ✓ {check}")
    
    if checks_failed:
        print("  FAILED:")
        for check in checks_failed:
            print(f"    ✗ {check}")
    
    print("\n" + "="*80)

def run_all_tests():
    """Run all test cases"""
    
    print("MEAL PLAN OPTIMIZER - DETAILED TESTING")
    print("="*80)
    
    # Create optimizer
    optimizer = MealPlanOptimizer()
    
    # Test 1: Standard muscle gain
    constraints1 = OptimizationConstraints(
        daily_calories_min=2200,
        daily_calories_max=2500,
        daily_protein_min=150,
        daily_carbs_min=200,
        daily_carbs_max=300,
        daily_fat_min=60,
        daily_fat_max=90,
        meals_per_day=3,
        max_recipe_repeat_in_days=2
    )
    
    result1 = optimizer.optimize(
        user_id=1,
        days=7,
        constraints=constraints1
    )
    
    print_meal_plan_simple(result1, constraints1, "7-DAY MUSCLE GAIN PLAN")
    
    # Test 2: Fat loss plan (3 days for brevity)
    constraints2 = OptimizationConstraints(
        daily_calories_min=1500,
        daily_calories_max=1700,
        daily_protein_min=120,
        daily_carbs_min=100,
        daily_carbs_max=150,
        daily_fat_min=40,
        daily_fat_max=60,
        meals_per_day=3,
        max_recipe_repeat_in_days=2
    )
    
    result2 = optimizer.optimize(
        user_id=2,
        days=3,
        constraints=constraints2
    )
    
    print_meal_plan_simple(result2, constraints2, "3-DAY FAT LOSS PLAN")
    
    # Test 3: 5 meals per day
    constraints3 = OptimizationConstraints(
        daily_calories_min=2800,
        daily_calories_max=3200,
        daily_protein_min=200,
        daily_carbs_min=300,
        daily_carbs_max=400,
        daily_fat_min=80,
        daily_fat_max=120,
        meals_per_day=5,
        max_recipe_repeat_in_days=3
    )
    
    result3 = optimizer.optimize(
        user_id=3,
        days=3,
        constraints=constraints3
    )
    
    print_meal_plan_simple(result3, constraints3, "3-DAY BODYBUILDER PLAN (5 MEALS/DAY)")
    
    # Test 4: Very restrictive (should trigger fallback)
    constraints4 = OptimizationConstraints(
        daily_calories_min=4000,  # Unrealistic
        daily_calories_max=4200,
        daily_protein_min=300,
        daily_carbs_min=500,
        daily_carbs_max=550,
        daily_fat_min=100,
        daily_fat_max=120,
        meals_per_day=3,
        max_recipe_repeat_in_days=2
    )
    
    result4 = optimizer.optimize(
        user_id=4,
        days=3,
        constraints=constraints4
    )
    
    print_meal_plan_simple(result4, constraints4, "EXTREME CONSTRAINTS (SHOULD USE FALLBACK)")
    
    print("\n" + "="*80)
    print("TESTING COMPLETE!")
    print("="*80)

if __name__ == "__main__":
    # Check if pulp is installed
    try:
        import pulp
        print("✓ PuLP is installed\n")
    except ImportError:
        print("✗ PuLP not installed. Run: pip install pulp")
        exit(1)
    
    run_all_tests()