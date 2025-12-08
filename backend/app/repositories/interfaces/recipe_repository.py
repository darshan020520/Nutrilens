"""
Recipe Repository Interface

Defines contract for recipe data access operations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from app.models.database import Recipe


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
