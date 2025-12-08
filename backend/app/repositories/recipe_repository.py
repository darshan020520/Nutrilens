"""
Recipe Repository Implementation

Handles recipe data access operations.

ALL CODE COPY-PASTED FROM meal_plan_service.py - ZERO LOGIC CHANGES
"""

import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import cast, String

from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.models.database import Recipe, RecipeIngredient, Item, UserPreference, UserGoal

logger = logging.getLogger(__name__)


class RecipeRepository(IRecipeRepository):
    """
    Repository for recipe data access.

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan_service.py
    """

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def get_by_id(self, recipe_id: int) -> Optional[Recipe]:
        """
        Get recipe by ID.

        COPY-PASTED FROM: meal_plan_service.py:185, 308, 418

        Args:
            recipe_id: Recipe ID

        Returns:
            Recipe if found, None otherwise
        """
        # COPY-PASTED FROM meal_plan_service.py:185 - NO CHANGES
        return self.db.query(Recipe).filter_by(id=recipe_id).first()

    def get_alternatives(
        self,
        original_recipe: Recipe,
        user_id: int,
        count: int
    ) -> List[dict]:
        """
        Get alternative recipes similar to the given recipe.

        EXACT COPY-PASTE FROM: meal_plan_service.py:399-539

        Args:
            original_recipe: Original recipe object
            user_id: User ID (for filtering by preferences)
            count: Number of alternatives to return

        Returns:
            List of alternative recipe dictionaries with scores
        """
        try:
            # COPY-PASTED FROM meal_plan_service.py:423-426 - NO CHANGES
            # Get user preferences and goal
            preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
            user_goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()

            # COPY-PASTED FROM meal_plan_service.py:428-444 - NO CHANGES
            # ============================================================
            # STAGE 1: SQL PRE-FILTERING (Hard requirements)
            # ============================================================

            target_cal = original_recipe.macros_per_serving['calories']

            # Query all recipes except the current one
            query = self.db.query(Recipe).filter(Recipe.id != original_recipe.id)

            # Apply dietary type if user has one
            if preferences and preferences.dietary_type:
                dietary_tag = preferences.dietary_type.value
                query = query.filter(
                    cast(Recipe.dietary_tags, String).contains(dietary_tag)
                )

            all_recipes = query.all()

            # COPY-PASTED FROM meal_plan_service.py:446-468 - NO CHANGES
            # Filter in Python (simpler and database-agnostic)
            min_cal = target_cal * 0.7
            max_cal = target_cal * 1.3
            original_meal_times = set(original_recipe.suitable_meal_times or [])

            candidates = []
            for recipe in all_recipes:
                # Check calorie range
                calories = recipe.macros_per_serving.get('calories', 0)
                if not (min_cal <= calories <= max_cal):
                    continue

                # Check meal time overlap
                recipe_meal_times = set(recipe.suitable_meal_times or [])
                if not (original_meal_times & recipe_meal_times):
                    continue

                candidates.append(recipe)

            if not candidates:
                logger.info(f"No alternative candidates found for recipe {original_recipe.id} (filtered {len(all_recipes)} by meal time)")
                return []

            logger.info(f"Found {len(candidates)} candidate alternatives for recipe {original_recipe.id} (from {len(all_recipes)} after calorie filter)")

            # COPY-PASTED FROM meal_plan_service.py:471-526 - NO CHANGES
            # ============================================================
            # STAGE 2: SIMPLE SCORING (Soft preferences)
            # ============================================================

            scored = []
            orig_macros = original_recipe.macros_per_serving

            for recipe in candidates:
                macros = recipe.macros_per_serving

                # Calculate macro differences (as percentages)
                cal_diff = abs(macros['calories'] - orig_macros['calories']) / orig_macros['calories']
                protein_diff = abs(macros['protein_g'] - orig_macros['protein_g']) / max(orig_macros['protein_g'], 1)
                carbs_diff = abs(macros['carbs_g'] - orig_macros['carbs_g']) / max(orig_macros['carbs_g'], 1)
                fat_diff = abs(macros['fat_g'] - orig_macros['fat_g']) / max(orig_macros['fat_g'], 1)

                # Simple similarity score: 1 - weighted_average_difference
                # Lower difference = higher score
                macro_similarity = 1 - (
                    cal_diff * 0.4 +        # Calories most important
                    protein_diff * 0.35 +   # Protein second
                    carbs_diff * 0.15 +     # Carbs third
                    fat_diff * 0.1          # Fat least important
                )

                # Goal bonus: +0.2 if matches user goal, otherwise 0
                goal_bonus = 0
                if user_goal and recipe.goals:
                    if user_goal.goal_type.value in recipe.goals:
                        goal_bonus = 0.2

                # Final score = macro_similarity (0-1) + goal_bonus (0-0.2)
                # Range: 0 to 1.2
                total_score = macro_similarity + goal_bonus

                # Match AlternativesResponse schema from schemas/meal_plan.py
                scored.append({
                    'recipe': {
                        'id': recipe.id,
                        'title': recipe.title,
                        'description': recipe.description,
                        'suitable_meal_times': recipe.suitable_meal_times or [],
                        'macros_per_serving': recipe.macros_per_serving,
                        'prep_time_min': recipe.prep_time_min or 0,
                        'cook_time_min': recipe.cook_time_min or 0,
                        'servings': recipe.servings or 1,
                        'goals': recipe.goals or [],
                        'dietary_tags': recipe.dietary_tags or []
                    },
                    'similarity_score': round(total_score, 3),
                    'calorie_difference': round(macros['calories'] - orig_macros['calories'], 1),
                    'protein_difference': round(macros['protein_g'] - orig_macros['protein_g'], 1),
                    'carbs_difference': round(macros['carbs_g'] - orig_macros['carbs_g'], 1),
                    'fat_difference': round(macros['fat_g'] - orig_macros['fat_g'], 1),
                    'suitable_for_swap': True
                })

            # COPY-PASTED FROM meal_plan_service.py:528-533 - NO CHANGES
            # Sort by score and return top N
            scored.sort(key=lambda x: x['similarity_score'], reverse=True)

            logger.info(f"Returning top {count} alternatives with scores: {[s['similarity_score'] for s in scored[:count]]}")

            return scored[:count]

        except Exception as e:
            # COPY-PASTED FROM meal_plan_service.py:535-539 - NO CHANGES
            logger.error(f"Error finding alternatives for recipe {original_recipe.id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def search(
        self,
        goal: Optional[str] = None,
        dietary_type: Optional[str] = None,
        meal_time: Optional[str] = None,
        max_prep_time: Optional[int] = None,
        cuisine: Optional[str] = None,
        search_term: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Recipe]:
        """
        Search recipes with filters.

        EXTRACTED FROM: recipes.py:45-83

        Args:
            goal: Filter by goal
            dietary_type: Filter by dietary type
            meal_time: Filter by meal time
            max_prep_time: Maximum prep time in minutes
            cuisine: Filter by cuisine
            search_term: Search in title and description
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of Recipe objects matching filters
        """
        from sqlalchemy import or_

        query = self.db.query(Recipe)

        # Apply filters
        if goal:
            query = query.filter(
                cast(Recipe.goals, String).contains(goal)
            )

        if dietary_type:
            query = query.filter(
                cast(Recipe.dietary_tags, String).contains(dietary_type)
            )

        if meal_time:
            query = query.filter(
                cast(Recipe.suitable_meal_times, String).contains(meal_time)
            )

        if max_prep_time:
            query = query.filter(Recipe.prep_time_min <= max_prep_time)

        if cuisine:
            query = query.filter(Recipe.cuisine == cuisine)

        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    Recipe.title.ilike(search_pattern),
                    Recipe.description.ilike(search_pattern)
                )
            )

        # Apply pagination
        return query.offset(offset).limit(limit).all()

    def get_with_ingredients(self, recipe_id: int) -> Optional[dict]:
        """
        Get recipe with full ingredient details.

        EXTRACTED FROM: recipes.py:165-182

        Args:
            recipe_id: Recipe ID

        Returns:
            Dictionary with recipe and ingredients, or None if not found
        """
        recipe = self.get_by_id(recipe_id)
        if not recipe:
            return None

        # Get ingredients with item names
        ingredients = self.db.query(
            RecipeIngredient, Item
        ).join(
            Item, RecipeIngredient.item_id == Item.id
        ).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()

        ingredient_list = []
        for recipe_ing, item in ingredients:
            ingredient_list.append({
                "item_id": item.id,
                "item_name": item.canonical_name,
                "quantity_grams": recipe_ing.quantity_grams,
                "is_optional": recipe_ing.is_optional,
                "preparation_notes": recipe_ing.preparation_notes
            })

        return {
            "recipe": recipe,
            "ingredients": ingredient_list
        }
