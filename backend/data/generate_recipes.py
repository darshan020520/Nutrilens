import json
from typing import List, Dict

def generate_all_recipes() -> List[Dict]:
    """Generate 100 diverse recipes for different goals"""
    
    recipes = []
    
    # Recipe templates for different goals
    muscle_gain_recipes = [
        # Add 30 muscle gain recipes
        {
            "title": f"Protein Power Bowl {i}",
            "goals": ["muscle_gain", "weight_training"],
            "tags": ["high_protein", "post_workout"],
            # ... complete recipe
        }
        for i in range(1, 31)
    ]
    
    fat_loss_recipes = [
        # Add 30 fat loss recipes
        {
            "title": f"Lean & Green {i}",
            "goals": ["fat_loss", "body_recomp"],
            "tags": ["low_calorie", "high_fiber"],
            # ... complete recipe
        }
        for i in range(1, 31)
    ]
    
    balanced_recipes = [
        # Add 40 balanced recipes
        {
            "title": f"Balanced Meal {i}",
            "goals": ["general_health", "endurance"],
            "tags": ["balanced", "nutritious"],
            # ... complete recipe
        }
        for i in range(1, 41)
    ]
    
    # Combine all recipes
    recipes.extend(muscle_gain_recipes)
    recipes.extend(fat_loss_recipes)
    recipes.extend(balanced_recipes)
    
    return recipes

if __name__ == "__main__":
    recipes = generate_all_recipes()
    with open('recipes_complete.json', 'w') as f:
        json.dump({"recipes": recipes}, f, indent=2)