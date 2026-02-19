import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.models.database import *
from app.core.config import settings
import json
from datetime import datetime
from tabulate import tabulate
import pandas as pd

def visualize_database():
    """Complete database visualization"""
    engine = create_engine(settings.database_url)
    
    print("=" * 100)
    print("📊 NUTRILENS DATABASE COMPLETE VISUALIZATION")
    print("=" * 100)
    print(f"Database: {settings.database_url.split('/')[-1]}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    with Session(engine) as session:
        # 1. USERS AND PROFILES
        print("\n" + "="*50)
        print("👤 USERS & PROFILES")
        print("="*50)
        
        users = session.query(User).all()
        if users:
            user_data = []
            for user in users:
                profile = session.query(UserProfile).filter(UserProfile.user_id == user.id).first()
                goal = session.query(UserGoal).filter(UserGoal.user_id == user.id).first()
                
                user_data.append([
                    user.id,
                    user.email[:20],
                    profile.name if profile else "No Profile",
                    goal.goal_type.value if goal and goal.goal_type else "No Goal",
                    profile.goal_calories if profile else "N/A"
                ])
            
            print(tabulate(user_data, 
                         headers=["ID", "Email", "Name", "Goal", "Calories"],
                         tablefmt="grid"))
        else:
            print("❌ No users found")
        
        # 2. FOOD ITEMS
        print("\n" + "="*50)
        print("🍎 FOOD ITEMS DATABASE")
        print("="*50)
        
        items = session.query(Item).all()
        print(f"Total Items: {len(items)}")
        
        if items:
            # Show first 10 items
            print("\nFirst 10 Food Items:")
            item_data = []
            for item in items[:10]:
                nutrition = item.nutrition_per_100g or {}
                item_data.append([
                    item.id,
                    item.canonical_name[:20],
                    item.category,
                    f"{nutrition.get('calories', 0):.0f}",
                    f"{nutrition.get('protein_g', 0):.1f}",
                    f"{nutrition.get('carbs_g', 0):.1f}",
                    f"{nutrition.get('fat_g', 0):.1f}"
                ])
            
            print(tabulate(item_data,
                         headers=["ID", "Name", "Category", "Cal", "Protein", "Carbs", "Fat"],
                         tablefmt="grid"))
            
            # Category breakdown
            categories = {}
            for item in items:
                cat = item.category or "uncategorized"
                categories[cat] = categories.get(cat, 0) + 1
            
            print("\nItems by Category:")
            for cat, count in sorted(categories.items()):
                print(f"  {cat}: {count} items")
        else:
            print("❌ No food items found")
        
        # 3. RECIPES
        print("\n" + "="*50)
        print("🍳 RECIPES DATABASE")
        print("="*50)
        
        recipes = session.query(Recipe).all()
        print(f"Total Recipes: {len(recipes)}")
        
        if recipes:
            # Show first 10 recipes
            print("\nFirst 10 Recipes:")
            recipe_data = []
            for recipe in recipes[:10]:
                macros = recipe.macros_per_serving or {}
                recipe_data.append([
                    recipe.id,
                    recipe.title[:30],
                    recipe.cuisine or "N/A",
                    f"{recipe.prep_time_min or 0}min",
                    f"{macros.get('calories', 0):.0f}",
                    f"{macros.get('protein_g', 0):.1f}g"
                ])
            
            print(tabulate(recipe_data,
                         headers=["ID", "Title", "Cuisine", "Prep", "Calories", "Protein"],
                         tablefmt="grid"))
            
            # Goals distribution
            print("\nRecipes by Goal:")
            goal_counts = {}
            for recipe in recipes:
                if recipe.goals:
                    for goal in recipe.goals:
                        goal_counts[goal] = goal_counts.get(goal, 0) + 1
            
            for goal, count in sorted(goal_counts.items()):
                print(f"  {goal}: {count} recipes")
            
            # Meal time distribution
            print("\nRecipes by Meal Time:")
            meal_counts = {}
            for recipe in recipes:
                if recipe.suitable_meal_times:
                    for meal in recipe.suitable_meal_times:
                        meal_counts[meal] = meal_counts.get(meal, 0) + 1
            
            for meal, count in sorted(meal_counts.items()):
                print(f"  {meal}: {count} recipes")
            
            # Dietary distribution
            print("\nRecipes by Dietary Type:")
            diet_counts = {}
            for recipe in recipes:
                if recipe.dietary_tags:
                    for diet in recipe.dietary_tags:
                        diet_counts[diet] = diet_counts.get(diet, 0) + 1
            
            for diet, count in sorted(diet_counts.items()):
                print(f"  {diet}: {count} recipes")
        else:
            print("❌ No recipes found")
        
        # 4. RECIPE INGREDIENTS
        print("\n" + "="*50)
        print("🥘 RECIPE INGREDIENTS MAPPING")
        print("="*50)
        
        ingredients = session.query(RecipeIngredient).all()
        print(f"Total Ingredient Mappings: {len(ingredients)}")
        
        if ingredients and recipes:
            # Show ingredients for first recipe
            first_recipe = recipes[0] if recipes else None
            if first_recipe:
                print(f"\nIngredients for '{first_recipe.title}':")
                recipe_ings = session.query(
                    RecipeIngredient, Item
                ).join(
                    Item, RecipeIngredient.item_id == Item.id
                ).filter(
                    RecipeIngredient.recipe_id == first_recipe.id
                ).all()
                
                ing_data = []
                for ring, item in recipe_ings:
                    ing_data.append([
                        item.canonical_name,
                        f"{ring.quantity_grams}g",
                        "Optional" if ring.is_optional else "Required"
                    ])
                
                if ing_data:
                    print(tabulate(ing_data,
                                 headers=["Ingredient", "Quantity", "Type"],
                                 tablefmt="grid"))
                else:
                    print("  No ingredients found for this recipe")
        
        # 5. USER INVENTORY
        print("\n" + "="*50)
        print("📦 USER INVENTORY")
        print("="*50)
        
        inventory = session.query(UserInventory).all()
        print(f"Total Inventory Items: {len(inventory)}")
        
        if inventory:
            inv_data = []
            for inv in inventory[:10]:  # Show first 10
                item = session.query(Item).filter(Item.id == inv.item_id).first()
                user = session.query(User).filter(User.id == inv.user_id).first()
                inv_data.append([
                    user.email[:20] if user else "Unknown",
                    item.canonical_name if item else "Unknown",
                    f"{inv.quantity_grams}g",
                    inv.expiry_date.strftime("%Y-%m-%d") if inv.expiry_date else "N/A"
                ])
            
            print(tabulate(inv_data,
                         headers=["User", "Item", "Quantity", "Expiry"],
                         tablefmt="grid"))
        else:
            print("📦 No inventory items")
        
        # 6. MEAL PLANS & LOGS
        print("\n" + "="*50)
        print("📅 MEAL PLANS & LOGS")
        print("="*50)
        
        meal_plans = session.query(MealPlan).all()
        meal_logs = session.query(MealLog).all()
        
        print(f"Total Meal Plans: {len(meal_plans)}")
        print(f"Total Meal Logs: {len(meal_logs)}")
        
        # 7. DATABASE STATISTICS
        print("\n" + "="*50)
        print("📈 DATABASE STATISTICS SUMMARY")
        print("="*50)
        
        stats = {
            "Users": len(users),
            "Profiles": session.query(UserProfile).count(),
            "Goals": session.query(UserGoal).count(),
            "Food Items": len(items),
            "Recipes": len(recipes),
            "Recipe Ingredients": len(ingredients),
            "Inventory Items": len(inventory),
            "Meal Plans": len(meal_plans),
            "Meal Logs": len(meal_logs)
        }
        
        stats_data = [[k, v] for k, v in stats.items()]
        print(tabulate(stats_data,
                     headers=["Table", "Count"],
                     tablefmt="grid"))
        
        # 8. DATA QUALITY CHECK
        print("\n" + "="*50)
        print("✅ DATA QUALITY CHECK")
        print("="*50)
        
        issues = []
        
        # Check for recipes without ingredients
        recipes_without_ingredients = 0
        for recipe in recipes:
            ing_count = session.query(RecipeIngredient).filter(
                RecipeIngredient.recipe_id == recipe.id
            ).count()
            if ing_count == 0:
                recipes_without_ingredients += 1
        
        if recipes_without_ingredients > 0:
            issues.append(f"⚠️  {recipes_without_ingredients} recipes have no ingredients")
        
        # Check for recipes without nutrition
        recipes_without_nutrition = 0
        for recipe in recipes:
            if not recipe.macros_per_serving or not recipe.macros_per_serving.get('calories'):
                recipes_without_nutrition += 1
        
        if recipes_without_nutrition > 0:
            issues.append(f"⚠️  {recipes_without_nutrition} recipes have no nutrition data")
        
        # Check for items without nutrition
        items_without_nutrition = 0
        for item in items:
            if not item.nutrition_per_100g or not item.nutrition_per_100g.get('calories'):
                items_without_nutrition += 1
        
        if items_without_nutrition > 0:
            issues.append(f"⚠️  {items_without_nutrition} items have no nutrition data")
        
        if issues:
            for issue in issues:
                print(issue)
        else:
            print("✅ All data quality checks passed!")
        
        print("\n" + "="*100)
        print("📊 VISUALIZATION COMPLETE")
        print("="*100)

def export_to_csv():
    """Export database tables to CSV for easier viewing"""
    engine = create_engine(settings.database_url)
    
    print("\n📁 Exporting to CSV files...")
    
    # Create exports directory
    os.makedirs("exports", exist_ok=True)
    
    with Session(engine) as session:
        # Export Items
        items = session.query(Item).all()
        if items:
            items_data = []
            for item in items:
                nutrition = item.nutrition_per_100g or {}
                items_data.append({
                    'id': item.id,
                    'name': item.canonical_name,
                    'category': item.category,
                    'calories': nutrition.get('calories', 0),
                    'protein_g': nutrition.get('protein_g', 0),
                    'carbs_g': nutrition.get('carbs_g', 0),
                    'fat_g': nutrition.get('fat_g', 0)
                })
            df = pd.DataFrame(items_data)
            df.to_csv('exports/food_items.csv', index=False)
            print("✅ Exported food_items.csv")
        
        # Export Recipes
        recipes = session.query(Recipe).all()
        if recipes:
            recipes_data = []
            for recipe in recipes:
                macros = recipe.macros_per_serving or {}
                recipes_data.append({
                    'id': recipe.id,
                    'title': recipe.title,
                    'goals': ', '.join(recipe.goals) if recipe.goals else '',
                    'dietary_tags': ', '.join(recipe.dietary_tags) if recipe.dietary_tags else '',
                    'meal_times': ', '.join(recipe.suitable_meal_times) if recipe.suitable_meal_times else '',
                    'cuisine': recipe.cuisine,
                    'prep_time': recipe.prep_time_min,
                    'calories': macros.get('calories', 0),
                    'protein_g': macros.get('protein_g', 0)
                })
            df = pd.DataFrame(recipes_data)
            df.to_csv('exports/recipes.csv', index=False)
            print("✅ Exported recipes.csv")
    
    print("📁 CSV files saved in 'exports' directory")

if __name__ == "__main__":
    print("\n🚀 Starting Database Visualization...\n")
    
    # Check if pandas is installed for CSV export
    try:
        import pandas as pd
        visualize_database()
        
        # Ask if user wants CSV export
        print("\n" + "="*50)
        print("Would you like to export data to CSV files?")
        print("This will create files you can open in Excel")
        print("="*50)
        # For Docker, we'll auto-export
        export_to_csv()
    except ImportError:
        print("Installing pandas for better visualization...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
        import pandas as pd
        visualize_database()
        export_to_csv()