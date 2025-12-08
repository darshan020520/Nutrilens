"""
Base Repository Interface

Generic repository interface with common CRUD operations.
All specific repositories can inherit from this.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')


class IRepository(ABC, Generic[T]):
    """
    Base repository interface for common operations.

    T: Domain model type (e.g., MealPlan, MealLog, etc.)
    """

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with ID populated
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        Update existing entity.

        Args:
            entity: Entity to update (must have ID)

        Returns:
            Updated entity
        """
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """
        Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """
        Get all entities with pagination.

        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip

        Returns:
            List of entities
        """
        pass
