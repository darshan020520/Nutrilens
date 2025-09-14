import json
import os
from sqlalchemy.orm import Session
from app.models.database import Item, Recipe, RecipeIngredient
from app.core.config import settings
from typing import Dict, List
import logging



logger = logging.getLogger(__name__)

class DataSeeder:
    def __init__(self, db: Session):
        self.db = db
        self.items_map = {}  # canonical_name -> item_id mapping
        
    def seed_all(self):
        """Seed all data"""
        logger.info("Starting data seeding...")
        
        # Order matters - items first, then recipes
        self.seed_items()
        self.seed_recipes()
        
        logger.info("Data seeding complete!")
    
    def seed_items(self):
        """Load and seed food items"""
        # Check if items already exist
        existing_count = self.db.query(Item).count()
        if existing_count > 0:
            logger.info(f"Items already seeded ({existing_count} items). Skipping...")
            self._load_items_map()
            return
        
        # Load items from JSON files
        items_data = []
        
        # Load main items file
        items_file = os.path.join(settings.base_dir, 'data', 'food_items.json')
        print("CWD:", os.getcwd())
        print("Resolved path:", os.path.abspath(items_file))
        print("Exists?", os.path.exists(items_file))
        if os.path.exists(items_file):
            with open(items_file, 'r') as f:
                data = json.load(f)
                items_data.extend(data['items'])
        
        # Load extended items file
        extended_file = os.path.join(settings.base_dir, 'data', 'food_items_extended.json')
        if os.path.exists(extended_file):
            with open(extended_file, 'r') as f:
                data = json.load(f)
                items_data.extend(data['items'])
        
        # Insert items into database
        for item_data in items_data:
            item = Item(
                canonical_name=item_data['canonical_name'],
                aliases=item_data.get('aliases', []),
                category=item_data.get('category'),
                unit=item_data.get('unit', 'g'),
                is_staple=item_data.get('is_staple', False),
                nutrition_per_100g=item_data.get('nutrition_per_100g', {}),
                density_g_per_ml=item_data.get('density_g_per_ml')
            )
            self.db.add(item)
        
        self.db.commit()
        logger.info(f"Seeded {len(items_data)} food items")
        
        # Load items map for recipe seeding
        self._load_items_map()
    
    def _load_items_map(self):
        """Load mapping of canonical names to item IDs"""
        items = self.db.query(Item).all()
        self.items_map = {item.canonical_name: item.id for item in items}
    
    def seed_recipes(self):
        """Load and seed recipes"""
        # Check if recipes already exist
        existing_count = self.db.query(Recipe).count()
        if existing_count > 0:
            logger.info(f"Recipes already seeded ({existing_count} recipes). Skipping...")
            return
        
        # Load recipes from JSON
        recipes_file = os.path.join(settings.base_dir, 'data', 'recipes.json')
        if not os.path.exists(recipes_file):
            logger.warning("Recipes file not found")
            return
        
        with open(recipes_file, 'r') as f:
            data = json.load(f)
            recipes_data = data['recipes']
        
        # Insert recipes
        for recipe_data in recipes_data:
            # Calculate nutrition from ingredients
            nutrition = self._calculate_recipe_nutrition(recipe_data['ingredients'])
            
            recipe = Recipe(
                title=recipe_data['title'],
                description=recipe_data.get('description'),
                goals=recipe_data.get('goals', []),
                tags=recipe_data.get('tags', []),
                dietary_tags=recipe_data.get('dietary_tags', []),
                suitable_meal_times=recipe_data.get('suitable_meal_times', []),
                instructions=recipe_data.get('instructions', []),
                cuisine=recipe_data.get('cuisine'),
                prep_time_min=recipe_data.get('prep_time_min'),
                cook_time_min=recipe_data.get('cook_time_min'),
                difficulty_level=recipe_data.get('difficulty_level', 'medium'),
                servings=recipe_data.get('servings', 1),
                macros_per_serving=nutrition,
                meal_prep_notes=recipe_data.get('meal_prep_notes'),
                chef_tips=recipe_data.get('chef_tips')
            )
            self.db.add(recipe)
            self.db.flush()  # Get recipe ID
            
            # Add ingredients
            for ingredient in recipe_data['ingredients']:
                item_name = ingredient['item_name']
                if item_name in self.items_map:
                    recipe_ingredient = RecipeIngredient(
                        recipe_id=recipe.id,
                        item_id=self.items_map[item_name],
                        quantity_grams=ingredient['quantity_grams'],
                        is_optional=ingredient.get('is_optional', False),
                        preparation_notes=ingredient.get('preparation_notes')
                    )
                    self.db.add(recipe_ingredient)
                else:
                    logger.warning(f"Item '{item_name}' not found for recipe '{recipe.title}'")
        
        self.db.commit()
        logger.info(f"Seeded {len(recipes_data)} recipes")
    
    def _calculate_recipe_nutrition(self, ingredients: List[Dict]) -> Dict:
        """Calculate total nutrition for a recipe from ingredients"""
        total_nutrition = {
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "fiber_g": 0,
            "sodium_mg": 0
        }
        
        for ingredient in ingredients:
            item_name = ingredient['item_name']
            quantity_g = ingredient['quantity_grams']
            
            # Get item from database
            item = self.db.query(Item).filter(
                Item.canonical_name == item_name
            ).first()
            
            if item and item.nutrition_per_100g:
                # Calculate nutrition based on quantity
                factor = quantity_g / 100.0
                for nutrient, value in item.nutrition_per_100g.items():
                    if nutrient in total_nutrition:
                        total_nutrition[nutrient] += value * factor
        
        # Round values
        for key in total_nutrition:
            total_nutrition[key] = round(total_nutrition[key], 2)
        
        return total_nutrition