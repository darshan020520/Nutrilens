#!/usr/bin/env python3
"""
NutriLens AI Database Seeder
Populates recipes, food items, and recipe_ingredients tables
"""

import sys
import os

# Add the app directory to Python path (matching your project structure)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models.database import Recipe, RecipeIngredient, Item
from app.core.config import settings
import json
from typing import List, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NutriLensSeeder:
    def __init__(self):
        self.engine = create_engine(settings.database_url)
        self.food_items_cache = {}

    def create_food_items(self) -> Dict[str, int]:
        """Create essential food items and return mapping of name to ID"""
        food_items = [
            # Proteins
            {
                'canonical_name': 'chicken_breast',
                'aliases': ['chicken breast', 'chicken', 'grilled chicken'],
                'category': 'protein',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 165, 'protein_g': 31, 'carbs_g': 0, 'fat_g': 3.6, 'fiber_g': 0
                },
                'is_staple': True
            },
            {
                'canonical_name': 'eggs',
                'aliases': ['egg', 'whole eggs', 'fresh eggs'],
                'category': 'protein',
                'unit': 'pieces',
                'nutrition_per_100g': {
                    'calories': 155, 'protein_g': 13, 'carbs_g': 1.1, 'fat_g': 11, 'fiber_g': 0
                },
                'is_staple': True
            },
            {
                'canonical_name': 'greek_yogurt',
                'aliases': ['greek yogurt', 'yogurt', 'plain yogurt'],
                'category': 'dairy',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 97, 'protein_g': 10, 'carbs_g': 3.6, 'fat_g': 5, 'fiber_g': 0
                },
                'is_staple': True
            },
            {
                'canonical_name': 'paneer',
                'aliases': ['cottage cheese', 'fresh cheese'],
                'category': 'dairy',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 265, 'protein_g': 18, 'carbs_g': 1.2, 'fat_g': 20, 'fiber_g': 0
                },
                'is_staple': True
            },
            {
                'canonical_name': 'tofu',
                'aliases': ['soy tofu', 'bean curd'],
                'category': 'protein',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 70, 'protein_g': 8, 'carbs_g': 1.9, 'fat_g': 4.2, 'fiber_g': 0.4
                },
                'is_staple': True
            },
            
            # Carbohydrates
            {
                'canonical_name': 'brown_rice',
                'aliases': ['brown rice', 'whole grain rice'],
                'category': 'carbs',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 112, 'protein_g': 2.6, 'carbs_g': 22, 'fat_g': 0.9, 'fiber_g': 1.8
                },
                'is_staple': True
            },
            {
                'canonical_name': 'quinoa',
                'aliases': ['quinoa grain', 'cooked quinoa'],
                'category': 'carbs',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 120, 'protein_g': 4.4, 'carbs_g': 22, 'fat_g': 1.9, 'fiber_g': 2.8
                },
                'is_staple': True
            },
            {
                'canonical_name': 'oats',
                'aliases': ['rolled oats', 'oatmeal', 'porridge oats'],
                'category': 'carbs',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 68, 'protein_g': 2.4, 'carbs_g': 12, 'fat_g': 1.4, 'fiber_g': 1.7
                },
                'is_staple': True
            },
            {
                'canonical_name': 'whole_wheat_bread',
                'aliases': ['whole wheat bread', 'brown bread', 'wheat bread'],
                'category': 'carbs',
                'unit': 'slices',
                'nutrition_per_100g': {
                    'calories': 247, 'protein_g': 13, 'carbs_g': 41, 'fat_g': 4.2, 'fiber_g': 6
                },
                'is_staple': True
            },
            {
                'canonical_name': 'sweet_potato',
                'aliases': ['sweet potato', 'yam', 'roasted sweet potato'],
                'category': 'carbs',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 90, 'protein_g': 2, 'carbs_g': 21, 'fat_g': 0.1, 'fiber_g': 3.3
                },
                'is_staple': True
            },
            
            # Vegetables
            {
                'canonical_name': 'broccoli',
                'aliases': ['fresh broccoli', 'steamed broccoli'],
                'category': 'vegetable',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 25, 'protein_g': 3, 'carbs_g': 5, 'fat_g': 0.4, 'fiber_g': 2.6
                },
                'is_staple': True
            },
            {
                'canonical_name': 'spinach',
                'aliases': ['fresh spinach', 'leafy spinach'],
                'category': 'vegetable',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 23, 'protein_g': 2.9, 'carbs_g': 3.6, 'fat_g': 0.4, 'fiber_g': 2.2
                },
                'is_staple': True
            },
            {
                'canonical_name': 'tomato',
                'aliases': ['fresh tomato', 'tomatoes'],
                'category': 'vegetable',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 18, 'protein_g': 0.9, 'carbs_g': 3.9, 'fat_g': 0.2, 'fiber_g': 1.2
                },
                'is_staple': True
            },
            
            # Healthy Fats
            {
                'canonical_name': 'avocado',
                'aliases': ['fresh avocado', 'ripe avocado'],
                'category': 'fat',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 160, 'protein_g': 2, 'carbs_g': 9, 'fat_g': 15, 'fiber_g': 7
                },
                'is_staple': True
            },
            {
                'canonical_name': 'almonds',
                'aliases': ['raw almonds', 'almond nuts'],
                'category': 'nuts',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 576, 'protein_g': 21, 'carbs_g': 22, 'fat_g': 49, 'fiber_g': 12
                },
                'is_staple': True
            },
            {
                'canonical_name': 'olive_oil',
                'aliases': ['extra virgin olive oil', 'cooking oil'],
                'category': 'oil',
                'unit': 'ml',
                'nutrition_per_100g': {
                    'calories': 884, 'protein_g': 0, 'carbs_g': 0, 'fat_g': 100, 'fiber_g': 0
                },
                'is_staple': True
            },
            
            # Indian Staples
            {
                'canonical_name': 'dal_lentils',
                'aliases': ['dal', 'lentils', 'cooked lentils', 'moong dal'],
                'category': 'legumes',
                'unit': 'grams',
                'nutrition_per_100g': {
                    'calories': 115, 'protein_g': 9, 'carbs_g': 20, 'fat_g': 0.4, 'fiber_g': 8
                },
                'is_staple': True
            },
            {
                'canonical_name': 'roti',
                'aliases': ['chapati', 'indian bread', 'wheat roti'],
                'category': 'carbs',
                'unit': 'pieces',
                'nutrition_per_100g': {
                    'calories': 297, 'protein_g': 12, 'carbs_g': 58, 'fat_g': 3.7, 'fiber_g': 11
                },
                'is_staple': True
            },
            
            # Fruits
            {
                'canonical_name': 'banana',
                'aliases': ['fresh banana', 'ripe banana'],
                'category': 'fruit',
                'unit': 'pieces',
                'nutrition_per_100g': {
                    'calories': 89, 'protein_g': 1.1, 'carbs_g': 23, 'fat_g': 0.3, 'fiber_g': 2.6
                },
                'is_staple': True
            },
            {
                'canonical_name': 'apple',
                'aliases': ['fresh apple', 'red apple'],
                'category': 'fruit',
                'unit': 'pieces',
                'nutrition_per_100g': {
                    'calories': 52, 'protein_g': 0.3, 'carbs_g': 14, 'fat_g': 0.2, 'fiber_g': 2.4
                },
                'is_staple': True
            }
        ]
        
        item_id_mapping = {}
        new_items_added = 0
        existing_items_found = 0
        
        with Session(self.engine) as session:
            for item_data in food_items:
                # Check if item already exists
                existing_item = session.query(Item).filter(
                    Item.canonical_name == item_data['canonical_name']
                ).first()
                
                if existing_item:
                    item_id_mapping[item_data['canonical_name']] = existing_item.id
                    existing_items_found += 1
                    logger.debug(f"Found existing item: {item_data['canonical_name']}")
                    continue
                
                # Create new item
                item = Item(
                    canonical_name=item_data['canonical_name'],
                    aliases=item_data['aliases'],
                    category=item_data['category'],
                    unit=item_data['unit'],
                    nutrition_per_100g=item_data['nutrition_per_100g'],
                    is_staple=item_data['is_staple']
                )
                
                session.add(item)
                session.flush()  # To get the ID
                item_id_mapping[item_data['canonical_name']] = item.id
                new_items_added += 1
                logger.info(f"Created new food item: {item_data['canonical_name']} with ID {item.id}")
            
            session.commit()
        
        logger.info(f"Food items summary: {new_items_added} new, {existing_items_found} existing, {len(item_id_mapping)} total available")
        return item_id_mapping

    def get_recipe_ingredients(self, recipe_type: str, calorie_range: str) -> List[Tuple[str, int, bool]]:
        """Return ingredients for recipe type and calorie range"""
        # Format: (item_name, quantity_grams, is_optional)
        
        ingredient_templates = {
            'breakfast': {
                'low': [  # 300-500 calories
                    ('oats', 40, False),
                    ('greek_yogurt', 100, False),
                    ('banana', 100, False),
                    ('almonds', 10, True),
                ],
                'high': [  # 500-800 calories
                    ('oats', 80, False),
                    ('greek_yogurt', 150, False),
                    ('banana', 120, False),
                    ('almonds', 20, False),
                    ('eggs', 100, False),  # 2 eggs
                ]
            },
            'lunch': {
                'low': [  # 400-600 calories
                    ('chicken_breast', 100, False),
                    ('brown_rice', 80, False),
                    ('broccoli', 100, False),
                    ('olive_oil', 5, False),
                ],
                'high': [  # 700-1000 calories
                    ('chicken_breast', 150, False),
                    ('brown_rice', 120, False),
                    ('broccoli', 150, False),
                    ('avocado', 50, False),
                    ('olive_oil', 10, False),
                ]
            },
            'dinner': {
                'low': [  # 450-650 calories
                    ('chicken_breast', 120, False),
                    ('quinoa', 80, False),
                    ('spinach', 100, False),
                    ('tomato', 80, False),
                    ('olive_oil', 7, False),
                ],
                'high': [  # 800-1100 calories
                    ('chicken_breast', 180, False),
                    ('quinoa', 120, False),
                    ('spinach', 150, False),
                    ('sweet_potato', 150, False),
                    ('avocado', 60, False),
                    ('olive_oil', 10, False),
                ]
            },
            'flexible': [  # Various calories
                ('dal_lentils', 100, False),
                ('roti', 60, False),  # 2 rotis
                ('spinach', 80, False),
                ('tomato', 50, False),
                ('olive_oil', 5, False),
            ]
        }
        
        if recipe_type == 'flexible':
            return ingredient_templates['flexible']
        
        return ingredient_templates.get(recipe_type, {}).get(calorie_range, [])

    def generate_recipes_with_ingredients(self) -> List[Dict]:
        """Generate recipes similar to your _get_filtered_recipes_fixed method"""
        recipes = []
        
        # High-calorie options for muscle gain (2000+ calories)
        # Power breakfasts (500-800 calories)
        for i in range(10):
            recipe_data = {
                'id': i + 1,
                'title': f'Power Breakfast {i+1}',
                'description': f'High-protein breakfast for muscle gain - option {i+1}',
                'goals': ['muscle_gain'],
                'tags': ['high_protein', 'breakfast', 'muscle_building'],
                'dietary_tags': ['vegetarian' if i % 3 == 0 else 'non_vegetarian'],
                'suitable_meal_times': ['breakfast'],
                'macros_per_serving': {
                    'calories': 500 + (i * 30),
                    'protein_g': 35 + (i * 2),
                    'carbs_g': 55 + (i * 3),
                    'fat_g': 18 + (i % 3),
                    'fiber_g': 7
                },
                'prep_time_min': 10,
                'cook_time_min': 15,
                'difficulty_level': 'easy',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('breakfast', 'high')
            }
            recipes.append(recipe_data)
        
        # Power lunches (700-1000 calories)
        for i in range(10):
            recipe_data = {
                'id': i + 101,
                'title': f'Power Lunch {i+1}',
                'description': f'High-calorie lunch for muscle gain - option {i+1}',
                'goals': ['muscle_gain'],
                'tags': ['high_protein', 'lunch', 'muscle_building'],
                'dietary_tags': ['non_vegetarian'],
                'suitable_meal_times': ['lunch'],
                'macros_per_serving': {
                    'calories': 700 + (i * 30),
                    'protein_g': 50 + (i * 2),
                    'carbs_g': 70 + (i * 3),
                    'fat_g': 25 + (i % 4),
                    'fiber_g': 10
                },
                'prep_time_min': 15,
                'cook_time_min': 25,
                'difficulty_level': 'medium',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('lunch', 'high')
            }
            recipes.append(recipe_data)
        
        # Power dinners (800-1100 calories)
        for i in range(10):
            recipe_data = {
                'id': i + 201,
                'title': f'Power Dinner {i+1}',
                'description': f'High-calorie dinner for muscle gain - option {i+1}',
                'goals': ['muscle_gain'],
                'tags': ['high_protein', 'dinner', 'muscle_building'],
                'dietary_tags': ['non_vegetarian'],
                'suitable_meal_times': ['dinner'],
                'macros_per_serving': {
                    'calories': 800 + (i * 30),
                    'protein_g': 60 + (i * 2),
                    'carbs_g': 75 + (i * 3),
                    'fat_g': 30 + (i % 5),
                    'fiber_g': 12
                },
                'prep_time_min': 20,
                'cook_time_min': 35,
                'difficulty_level': 'medium',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('dinner', 'high')
            }
            recipes.append(recipe_data)
        
        # Regular breakfasts (300-500 calories) for fat loss
        for i in range(10):
            recipe_data = {
                'id': i + 301,
                'title': f'Lean Breakfast {i+1}',
                'description': f'Balanced breakfast for fat loss - option {i+1}',
                'goals': ['fat_loss', 'maintenance'],
                'tags': ['balanced', 'breakfast', 'fat_loss'],
                'dietary_tags': ['vegetarian' if i % 2 == 0 else 'non_vegetarian'],
                'suitable_meal_times': ['breakfast'],
                'macros_per_serving': {
                    'calories': 300 + (i * 20),
                    'protein_g': 25 + (i * 2),
                    'carbs_g': 35 + (i * 2),
                    'fat_g': 10 + (i % 3),
                    'fiber_g': 5
                },
                'prep_time_min': 10,
                'cook_time_min': 15,
                'difficulty_level': 'easy',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('breakfast', 'low')
            }
            recipes.append(recipe_data)
        
        # Regular lunches (400-600 calories)
        for i in range(10):
            recipe_data = {
                'id': i + 401,
                'title': f'Balanced Lunch {i+1}',
                'description': f'Balanced lunch for maintenance - option {i+1}',
                'goals': ['fat_loss', 'maintenance'],
                'tags': ['balanced', 'lunch'],
                'dietary_tags': ['non_vegetarian'],
                'suitable_meal_times': ['lunch'],
                'macros_per_serving': {
                    'calories': 400 + (i * 20),
                    'protein_g': 35 + (i * 2),
                    'carbs_g': 40 + (i * 2),
                    'fat_g': 15 + (i % 4),
                    'fiber_g': 8
                },
                'prep_time_min': 15,
                'cook_time_min': 20,
                'difficulty_level': 'easy',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('lunch', 'low')
            }
            recipes.append(recipe_data)
        
        # Regular dinners (450-650 calories)
        for i in range(10):
            recipe_data = {
                'id': i + 501,
                'title': f'Balanced Dinner {i+1}',
                'description': f'Balanced dinner for maintenance - option {i+1}',
                'goals': ['fat_loss', 'maintenance'],
                'tags': ['balanced', 'dinner'],
                'dietary_tags': ['non_vegetarian'],
                'suitable_meal_times': ['dinner'],
                'macros_per_serving': {
                    'calories': 450 + (i * 20),
                    'protein_g': 40 + (i * 2),
                    'carbs_g': 45 + (i * 2),
                    'fat_g': 18 + (i % 5),
                    'fiber_g': 10
                },
                'prep_time_min': 20,
                'cook_time_min': 30,
                'difficulty_level': 'medium',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('dinner', 'low')
            }
            recipes.append(recipe_data)
        
        # Flexible/snack options (various calories)
        for i in range(20):
            base_cal = 300 + (i * 30)  # 300-900 range
            recipe_data = {
                'id': i + 601,
                'title': f'Flexible Meal {i+1}',
                'description': f'Versatile meal option - {i+1}',
                'goals': ['muscle_gain', 'fat_loss', 'maintenance'],
                'tags': ['flexible', 'versatile'],
                'dietary_tags': ['vegetarian' if i % 3 == 0 else 'non_vegetarian'],
                'suitable_meal_times': ['breakfast', 'lunch', 'dinner', 'snack'],
                'macros_per_serving': {
                    'calories': base_cal,
                    'protein_g': 20 + (i * 2),
                    'carbs_g': 30 + (i * 2),
                    'fat_g': 10 + (i % 6),
                    'fiber_g': 5
                },
                'prep_time_min': 10,
                'cook_time_min': 15,
                'difficulty_level': 'easy',
                'servings': 1,
                'ingredients': self.get_recipe_ingredients('flexible', 'medium')
            }
            recipes.append(recipe_data)
        
        return recipes

    def seed_recipes(self, item_id_mapping: Dict[str, int]):
        """Seed recipes and recipe ingredients"""
        recipes_data = self.generate_recipes_with_ingredients()
        
        new_recipes_added = 0
        existing_recipes_found = 0
        
        with Session(self.engine) as session:
            for recipe_data in recipes_data:
                # Check if recipe already exists
                existing_recipe = session.query(Recipe).filter(
                    Recipe.title == recipe_data['title']
                ).first()
                
                if existing_recipe:
                    existing_recipes_found += 1
                    logger.debug(f"Found existing recipe: {recipe_data['title']}")
                    continue
                
                # Create recipe
                recipe = Recipe(
                    title=recipe_data['title'],
                    description=recipe_data['description'],
                    goals=recipe_data['goals'],
                    tags=recipe_data['tags'],
                    dietary_tags=recipe_data['dietary_tags'],
                    macros_per_serving=recipe_data['macros_per_serving'],
                    suitable_meal_times=recipe_data['suitable_meal_times'],
                    prep_time_min=recipe_data['prep_time_min'],
                    cook_time_min=recipe_data['cook_time_min'],
                    difficulty_level=recipe_data['difficulty_level'],
                    servings=recipe_data['servings']
                )
                
                session.add(recipe)
                session.flush()  # To get the recipe ID
                
                # Create recipe ingredients
                ingredients_added = 0
                for ingredient_data in recipe_data['ingredients']:
                    item_name, quantity_grams, is_optional = ingredient_data
                    
                    if item_name in item_id_mapping:
                        recipe_ingredient = RecipeIngredient(
                            recipe_id=recipe.id,
                            item_id=item_id_mapping[item_name],
                            quantity_grams=quantity_grams,
                            is_optional=is_optional
                        )
                        session.add(recipe_ingredient)
                        ingredients_added += 1
                        logger.debug(f"Added ingredient {item_name} to recipe {recipe.title}")
                    else:
                        logger.warning(f"Item {item_name} not found in item_id_mapping")
                
                new_recipes_added += 1
                logger.info(f"Created new recipe: {recipe_data['title']} with {ingredients_added} ingredients")
            
            session.commit()
        
        logger.info(f"Recipes summary: {new_recipes_added} new, {existing_recipes_found} existing")
        
        if new_recipes_added > 0:
            logger.info(f"Successfully added {new_recipes_added} new recipes to database")
        else:
            logger.info("No new recipes added - all recipes already exist in database")

    def run_incremental_seed(self):
        """Run incremental seeding process - safe to run multiple times"""
        logger.info("Starting NutriLens incremental database seeding...")
        logger.info("This process will preserve existing data and only add new items")
        
        try:
            # Step 1: Create food items (with duplicate checking)
            logger.info("Step 1: Adding new food items (preserving existing)...")
            item_id_mapping = self.create_food_items()
            logger.info(f"Food item mapping ready: {len(item_id_mapping)} items available")
            
            # Step 2: Create recipes with ingredients (with duplicate checking)
            logger.info("Step 2: Adding new recipes with ingredients (preserving existing)...")
            self.seed_recipes(item_id_mapping)
            
            logger.info("Incremental database seeding completed successfully!")
            
            # Print summary
            recipe_count = self.db.query(Recipe).count()
            item_count = self.db.query(Item).count()
            ingredient_count = self.db.query(RecipeIngredient).count()
            
            logger.info(f"Final Summary:")
            logger.info(f"- Total recipes in database: {recipe_count}")
            logger.info(f"- Total food items in database: {item_count}")
            logger.info(f"- Total recipe-ingredient relationships: {ingredient_count}")
            
        except Exception as e:
            logger.error(f"Error during incremental seeding: {str(e)}")
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def run_incremental_seed(self):
        """Run incremental seeding process - safe to run multiple times"""
        logger.info("Starting NutriLens incremental database seeding...")
        logger.info("This process will preserve existing data and only add new items")
        
        try:
            # Step 1: Create food items (with duplicate checking)
            logger.info("Step 1: Adding new food items (preserving existing)...")
            item_id_mapping = self.create_food_items()
            logger.info(f"Food item mapping ready: {len(item_id_mapping)} items available")
            
            # Step 2: Create recipes with ingredients (with duplicate checking)
            logger.info("Step 2: Adding new recipes with ingredients (preserving existing)...")
            self.seed_recipes(item_id_mapping)
            
            logger.info("Incremental database seeding completed successfully!")
            
            # Print summary
            with Session(self.engine) as session:
                recipe_count = session.query(Recipe).count()
                item_count = session.query(Item).count()
                ingredient_count = session.query(RecipeIngredient).count()
                
                logger.info(f"Final Summary:")
                logger.info(f"- Total recipes in database: {recipe_count}")
                logger.info(f"- Total food items in database: {item_count}")
                logger.info(f"- Total recipe-ingredient relationships: {ingredient_count}")
            
        except Exception as e:
            logger.error(f"Error during incremental seeding: {str(e)}")
            raise

    def run_full_seed(self):
        """Run complete seeding process (for reference - use run_incremental_seed for safety)"""
        logger.info("Starting NutriLens database seeding...")
        logger.warning("This is the full seed method - consider using run_incremental_seed() for safer operation")
        
        try:
            # Step 1: Create food items
            logger.info("Step 1: Creating food items...")
            item_id_mapping = self.create_food_items()
            logger.info(f"Created {len(item_id_mapping)} food items")
            
            # Step 2: Create recipes with ingredients
            logger.info("Step 2: Creating recipes with ingredients...")
            self.seed_recipes(item_id_mapping)
            
            logger.info("Database seeding completed successfully!")
            
            # Print summary
            with Session(self.engine) as session:
                recipe_count = session.query(Recipe).count()
                item_count = session.query(Item).count()
                ingredient_count = session.query(RecipeIngredient).count()
                
                logger.info(f"Summary:")
                logger.info(f"- Total recipes: {recipe_count}")
                logger.info(f"- Total food items: {item_count}")
                logger.info(f"- Total recipe-ingredient relationships: {ingredient_count}")
            
        except Exception as e:
            logger.error(f"Error during seeding: {str(e)}")
            raise

def main():
    """Main function to run the seeder"""
    seeder = NutriLensSeeder()
    seeder.run_full_seed()

if __name__ == "__main__":
    main()