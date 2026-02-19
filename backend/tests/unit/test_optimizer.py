# backend/app/tests/test_optimizer_phase4_feasible.py

from app.services.meal_optimizer import MealPlanOptimizerPhase4, OptimizationConstraintsPhase4

# Generate enough recipes to satisfy weekly slots
recipes = [
    {
        'id': i,
        'macros_per_serving': {'calories': 300 + i*50, 'protein_g': 20 + i*5},
        'suitable_meal_times': ['breakfast', 'lunch', 'dinner']
    } for i in range(1, 13)  # 12 recipes
]

optimizer = MealPlanOptimizerPhase4()
constraints = OptimizationConstraintsPhase4(
    daily_calories_min=1800,
    daily_calories_max=2200,
    daily_protein_min=120,
    daily_protein_max=160,
    max_recipe_repeats_per_week=2,
    meals_per_day=3,
    consecutive_day_penalty_weight=1.0
)

meal_plan = optimizer.optimize(days=7, constraints=constraints, recipes=recipes)

print("--- Phase 4: 7-Day Optimized Meal Plan ---")
for day, meals in meal_plan.items():
    print(f"{day}:")
    for meal_type, recipe in meals.items():
        print(f"  {meal_type}: Recipe {recipe['id']} | Calories: {recipe['macros_per_serving']['calories']} | Protein: {recipe['macros_per_serving']['protein_g']}")

# Optional: print weekly recipe counts
recipe_count = {}
for day, meals in meal_plan.items():
    for recipe in meals.values():
        recipe_count[recipe['id']] = recipe_count.get(recipe['id'], 0) + 1

print("\n--- Weekly Recipe Counts ---")
for rid, count in recipe_count.items():
    print(f"Recipe {rid}: {count} times")
