"""
Recipe Repository Interface

Defines contract for recipe data access operations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from app.models.database import Recipe, RecipeIngredient


class IRecipeRepository(ABC):
    """
    Interface for recipe data access.

    Provides methods for recipe CRUD operations.
    """

    @abstractmethod
    def get_by_id(self, recipe_id: int) -> Optional[Recipe]:
        """
        Get recipe by ID.

        Args:
            recipe_id: Recipe ID

        Returns:
            Recipe if found, None otherwise
        """
        pass

    @abstractmethod
    def get_ingredients_by_recipe_id(self, recipe_id: int) -> List[RecipeIngredient]:
        """
        Get all ingredients for a recipe.

        Args:
            recipe_id: Recipe ID

        Returns:
            List of RecipeIngredient objects with relationships loaded
        """
        pass

    @abstractmethod
    async def get_ingredients_for_recipes(self, recipe_ids: List[int]) -> Dict[int, List[RecipeIngredient]]:
        """
        BATCH OPERATION: Get ingredients for multiple recipes in ONE query.

        Solves N+1 query problem - instead of N queries (one per recipe),
        this does 1 query using WHERE recipe_id IN (...).

        Args:
            recipe_ids: List of recipe IDs to fetch ingredients for

        Returns:
            Dict mapping recipe_id to list of ingredients:
            {
                123: [RecipeIngredient(...), RecipeIngredient(...)],
                124: [RecipeIngredient(...)],
                ...
            }
            Returns empty dict if recipe_ids is empty or None
        """
        pass

    @abstractmethod
    async def get_makeable_recipe_candidates(
        self,
        user_item_quantities: Dict[int, float],
        min_match_pct: float = 80.0,
        limit: int = 30
    ) -> List[Dict]:
        """
        Find recipes user can make based on inventory quantities.

        Uses database-level filtering with QUANTITY-AWARE matching.
        This is a two-phase approach:
        - Phase 1 (SQL): Coarse filter - recipes with item overlap
        - Phase 2 (Python): Fine filter - validate actual quantities

        Args:
            user_item_quantities: Dict of {item_id: quantity_grams} user has
                Example: {5: 500.0, 12: 200.0} means 500g of item_id=5, 200g of item_id=12
            min_match_pct: Minimum match percentage (default: 80%)
                Recipe must have at least this % of ingredients available
            limit: Maximum candidates to return (default: 30)

        Returns:
            List of dicts, each containing:
            {
                'recipe': Recipe object (with ingredients eager-loaded),
                'match_percentage': float (80.0-100.0),
                'available_count': int (number of ingredients user has),
                'total_count': int (total required ingredients),
                'available_items': List[str] (ingredient names user has),
                'missing_items': List[str] (ingredient names user lacks)
            }

            Sorted by: match_percentage DESC, then recipe.prep_time_min ASC
        """
        pass

    @abstractmethod
    def get_alternatives(
        self,
        recipe_id: int,
        user_id: int,
        count: int
    ) -> List[Recipe]:
        """
        Get alternative recipes similar to the given recipe.

        Args:
            recipe_id: Original recipe ID
            user_id: User ID (for filtering by preferences)
            count: Number of alternatives to return

        Returns:
            List of alternative recipes
        """
        pass

    @abstractmethod
    async def count_all_recipes(self) -> int:
        """
        Get total count of recipes in database.

        Returns:
            Total number of recipes
        """
        pass

    @abstractmethod
    async def get_filtered_recipes(
        self,
        goal_type: Optional[str] = None,
        dietary_type: Optional[str] = None,
        exclude_allergens: Optional[List[str]] = None,
        max_prep_time: Optional[int] = None
    ) -> List[Recipe]:
        """
        Get recipes filtered by preferences and constraints.

        Used by MealPlanOptimizer to filter recipe pool before optimization.

        Args:
            goal_type: Filter by goal (muscle_gain, fat_loss, general_health, etc.)
            dietary_type: Filter by dietary type (vegetarian, vegan, keto, etc.)
            exclude_allergens: List of allergens to exclude (nuts, dairy, etc.)
            max_prep_time: Maximum prep time in minutes

        Returns:
            List of recipes matching all filters (as dicts for optimizer compatibility)
        """
        pass
