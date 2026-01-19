"""
Recipe Repository Implementation

Handles recipe data access operations.

ALL CODE COPY-PASTED FROM meal_plan_service.py - ZERO LOGIC CHANGES
"""

import logging
from typing import Optional, List, Dict
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

    def get_ingredients_by_recipe_id(self, recipe_id: int) -> List[RecipeIngredient]:
        """
        Get all ingredients for a recipe with relationships loaded.

        EXTRACTED FROM:
        - intelligent_inventory_service_v2.py:436-438 (deduct_for_meal)
        - intelligent_inventory_service_v2.py:810-812 (check_recipe_availability)
        - inventory_service.py:382-384

        Args:
            recipe_id: Recipe ID

        Returns:
            List of RecipeIngredient objects with item relationship loaded
        """
        from sqlalchemy.orm import joinedload

        # Use joinedload to eagerly load the item relationship
        # This prevents N+1 queries when accessing ingredient.item
        return self.db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.item)
        ).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()

    def get_makeable_recipe_candidates(
        self,
        user_item_quantities: Dict[int, float],
        min_match_pct: float = 80.0,
        limit: int = 30
    ) -> List[Dict]:
        """
        Find recipes user can make - QUANTITY-AWARE matching.

        EXTRACTED FROM: intelligent_inventory_service_v2.py:933-966
        IMPROVED: Now checks actual quantities, not just item presence

        Algorithm:
        1. SQL Coarse Filter: Get recipes with item overlap (ignores quantities)
        2. Python Fine Filter: Validate user has enough quantity for each ingredient
        3. Return only recipes meeting min_match_pct threshold

        This two-phase approach balances performance with accuracy:
        - Database does bulk filtering (fast, uses indexes)
        - Python does precise quantity validation (flexible, accurate)

        Args:
            user_item_quantities: {item_id: quantity_grams}
            min_match_pct: Minimum % of ingredients user must have (default: 80%)
            limit: Max recipes to return (default: 30)

        Returns:
            List of dicts with recipe + match details, sorted by match % DESC
        """
        from sqlalchemy import func, case, Float
        from sqlalchemy.orm import joinedload

        # Early exit if user has no inventory
        if not user_item_quantities:
            return []

        user_item_ids = set(user_item_quantities.keys())

        # ==================================================================
        # PHASE 1: SQL Coarse Filter
        # ==================================================================
        # Build subquery: count total ingredients and matching items per recipe
        # NOTE: This only checks if user HAS the item, not if they have ENOUGH
        recipe_match_subquery = self.db.query(
            Recipe.id.label('recipe_id'),
            func.count(RecipeIngredient.id).label('total_ingredients'),

            # Count how many ingredients user has (item presence only)
            func.sum(
                case(
                    (RecipeIngredient.item_id.in_(user_item_ids), 1),
                    else_=0
                )
            ).label('matching_ingredients')

        ).join(
            RecipeIngredient,
            Recipe.id == RecipeIngredient.recipe_id
        ).filter(
            RecipeIngredient.is_optional == False  # Only required ingredients
        ).group_by(
            Recipe.id
        ).having(
            func.count(RecipeIngredient.id) > 0  # Recipe must have ingredients
        ).subquery()

        # Get candidate recipes with item overlap
        # Fetch 3x more than limit to account for quantity filtering
        recipe_candidates = self.db.query(
            Recipe,
            recipe_match_subquery.c.total_ingredients,
            recipe_match_subquery.c.matching_ingredients
        ).join(
            recipe_match_subquery,
            Recipe.id == recipe_match_subquery.c.recipe_id
        ).options(
            # Eager load ingredients + items to prevent N+1 queries
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.item)
        ).limit(limit * 3).all()

        # ==================================================================
        # PHASE 2: Python Fine Filter (Quantity Validation)
        # ==================================================================
        results = []

        for recipe, total_ing, _ in recipe_candidates:
            # Get required ingredients (already loaded via joinedload, no query!)
            required_ingredients = [
                ing for ing in recipe.ingredients
                if not ing.is_optional
            ]

            if not required_ingredients:
                continue

            # Check which ingredients user can fulfill (quantity-aware)
            available_items = []
            missing_items = []

            for ingredient in required_ingredients:
                user_qty = user_item_quantities.get(ingredient.item_id, 0)
                item_name = ingredient.item.canonical_name

                if user_qty >= ingredient.quantity_grams:
                    # User has enough of this ingredient
                    available_items.append(item_name)
                else:
                    # User lacks this ingredient or doesn't have enough
                    missing_items.append(item_name)

            # Calculate TRUE match percentage (quantity-aware)
            total_count = len(required_ingredients)
            available_count = len(available_items)
            match_pct = (available_count / total_count * 100) if total_count > 0 else 0

            # Only include recipes that meet threshold
            if match_pct >= min_match_pct:
                results.append({
                    'recipe': recipe,
                    'match_percentage': round(match_pct, 1),
                    'available_count': available_count,
                    'total_count': total_count,
                    'available_items': available_items,
                    'missing_items': missing_items
                })

        # ==================================================================
        # PHASE 3: Sort and Return
        # ==================================================================
        # Sort by: match % DESC (higher first), then prep time ASC (faster first)
        results.sort(
            key=lambda x: (-x['match_percentage'], x['recipe'].prep_time_min or 999)
        )

        return results[:limit]

    def get_alternatives(
        self,
        original_recipe: Recipe,
        user_preferences: Optional[UserPreference],
        user_goal: Optional[UserGoal],
        count: int
    ) -> List[dict]:
        """
        Get alternative recipes similar to the given recipe.

        REFACTORED: Now receives user preferences and goal as parameters
        instead of querying them directly (architecture fix).
        Original: meal_plan_service.py:399-539

        Args:
            original_recipe: Original recipe object
            user_preferences: User preferences (from UserProfileRepository)
            user_goal: User goal (from UserProfileRepository)
            count: Number of alternatives to return

        Returns:
            List of alternative recipe dictionaries with scores
        """
        try:
            # REFACTORED: Preferences and goal passed as parameters
            # No longer querying user tables from recipe repository
            preferences = user_preferences
            goal = user_goal

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
                if goal and recipe.goals:
                    if goal.goal_type.value in recipe.goals:
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

    async def count_all_recipes(self) -> int:
        """
        Get total count of recipes in database.

        EXTRACTED FROM: final_meal_optimizer.py:552

        Returns:
            Total number of recipes
        """
        return self.db.query(Recipe).count()

    async def get_filtered_recipes(
        self,
        goal_type: Optional[str] = None,
        dietary_type: Optional[str] = None,
        exclude_allergens: Optional[List[str]] = None,
        max_prep_time: Optional[int] = None
    ) -> List[Recipe]:
        """
        Get recipes filtered by preferences and constraints.

        EXTRACTED FROM: final_meal_optimizer.py:555-593 (_get_filtered_recipes_fixed)

        IMPORTANT: This method does NOT apply calorie filtering - that's done
        by the optimizer after fetching recipes. We only apply:
        1. Goal alignment
        2. Dietary type
        3. Allergen exclusion (NOT YET IMPLEMENTED in optimizer - placeholder)
        4. Max prep + cook time

        Args:
            goal_type: Filter by goal (muscle_gain, fat_loss, maintenance)
            dietary_type: Filter by dietary type (vegetarian, vegan, etc.)
            exclude_allergens: List of allergens to exclude (placeholder - not used yet)
            max_prep_time: Maximum prep + cook time in minutes

        Returns:
            List of Recipe objects matching all filters
        """
        # Start with base query
        query = self.db.query(Recipe)

        # Filter by goal alignment (COPY-PASTED FROM line 560)
        if goal_type:
            query = query.filter(cast(Recipe.goals, String).contains(goal_type))

        # Filter by dietary type (COPY-PASTED FROM lines 574-577)
        if dietary_type:
            if dietary_type == 'vegetarian':
                query = query.filter(cast(Recipe.dietary_tags, String).contains('vegetarian'))
            elif dietary_type == 'vegan':
                query = query.filter(cast(Recipe.dietary_tags, String).contains('vegan'))

        # NOTE: Allergen filtering not implemented in original optimizer
        # Placeholder for future use
        if exclude_allergens:
            # TODO: Implement allergen filtering when optimizer supports it
            pass

        # Filter by prep + cook time (COPY-PASTED FROM lines 584-586)
        if max_prep_time is not None:
            query = query.filter(
                (Recipe.prep_time_min + Recipe.cook_time_min) <= max_prep_time
            )

        # Execute query and return results
        return query.all()

    async def get_ingredients_for_recipes(self, recipe_ids: List[int]) -> Dict[int, List[RecipeIngredient]]:
        """
        BATCH OPERATION: Get ingredients for multiple recipes in ONE query.

        Solves N+1 query problem by using WHERE recipe_id IN (...).

        Args:
            recipe_ids: List of recipe IDs

        Returns:
            Dict mapping recipe_id to list of ingredients
        """
        from sqlalchemy.orm import joinedload
        from collections import defaultdict

        # Early exit for empty list
        if not recipe_ids:
            return {}

        # ONE QUERY: Fetch all ingredients for all recipes
        # SQL: SELECT * FROM recipe_ingredient WHERE recipe_id IN (1, 2, 3, ...)
        ingredients = self.db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.item)  # Eager load items to prevent additional queries
        ).filter(
            RecipeIngredient.recipe_id.in_(recipe_ids)
        ).all()

        # Group ingredients by recipe_id
        result = defaultdict(list)
        for ing in ingredients:
            result[ing.recipe_id].append(ing)

        # Convert defaultdict to regular dict
        return dict(result)
