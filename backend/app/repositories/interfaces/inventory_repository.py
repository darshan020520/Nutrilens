"""
Inventory Repository Interface

Defines data access operations for user inventory management.
All inventory-related database queries should go through this interface.
"""

from abc import abstractmethod
from datetime import date, datetime
from typing import Optional, List, Dict
from app.repositories.interfaces.base_repository import IRepository
from app.models.database import UserInventory, Recipe


class IInventoryRepository(IRepository[UserInventory]):
    """
    Interface for inventory data access operations.

    Responsibilities:
    - CRUD operations for user inventory
    - Quantity operations (add, deduct, set)
    - Recipe ingredient deductions
    - Analytics queries (expiring, low stock, overstocked)
    - Inventory categorization and status

    This is a DATA ACCESS layer - NO business logic here.
    """

    # =========================================================================
    # BASIC CRUD OPERATIONS (extend base repository)
    # =========================================================================

    @abstractmethod
    async def get_by_id(
        self,
        inventory_id: int,
        user_id: int
    ) -> Optional[UserInventory]:
        """
        Get inventory item by ID with user validation.

        Args:
            inventory_id: ID of inventory item
            user_id: User ID for ownership validation

        Returns:
            UserInventory if found and belongs to user, None otherwise
        """
        pass

    @abstractmethod
    async def get_all_for_user(
        self,
        user_id: int,
        include_zero_quantity: bool = False
    ) -> List[UserInventory]:
        """
        Get all inventory items for a user.

        Args:
            user_id: User ID
            include_zero_quantity: If True, include items with 0 quantity

        Returns:
            List of inventory items ordered by item name
        """
        pass

    @abstractmethod
    async def get_by_item_id(
        self,
        user_id: int,
        item_id: int
    ) -> Optional[UserInventory]:
        """
        Get inventory record for a specific item.

        LIMITATION: Returns only ONE UserInventory record.
        If multiple records exist (different expiry dates), behavior is undefined.

        For FIFO inventory with multiple expiry dates, use get_all_inventory_for_item() instead.

        Args:
            user_id: User ID
            item_id: Item ID

        Returns:
            UserInventory if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_all_inventory_for_item(
        self,
        user_id: int,
        item_id: int,
        order_by_expiry_desc: bool = True
    ) -> List[UserInventory]:
        """
        Get ALL inventory records for a specific user and item.

        Supports multiple inventory records per item (different expiry dates).
        This enables FIFO (First In, First Out) inventory management.

        Args:
            user_id: User ID
            item_id: Item ID
            order_by_expiry_desc: If True, orders by expiry_date DESC (newest first)
                                  If False, orders by expiry_date ASC (oldest first)

        Returns:
            List of inventory records for the item, ordered by expiry date.
            Returns empty list if no records found.
        """
        pass

    @abstractmethod
    async def get_by_item_ids(
        self,
        user_id: int,
        item_ids: List[int]
    ) -> Dict[int, UserInventory]:
        """
        BATCH OPERATION: Get inventory for multiple items in ONE query.

        Solves N+1 query problem - instead of N queries (one per item),
        this does 1 query using WHERE item_id IN (...).

        Args:
            user_id: User ID
            item_ids: List of item IDs to fetch inventory for

        Returns:
            Dict mapping item_id to UserInventory:
            {
                5: UserInventory(item_id=5, quantity_grams=500, ...),
                12: UserInventory(item_id=12, quantity_grams=200, ...),
                ...
            }

            If user has no inventory for an item, it won't be in the dict.
            Returns empty dict if item_ids is empty or None.
        """
        pass

    @abstractmethod
    async def create(self, inventory: UserInventory) -> UserInventory:
        """
        Create new inventory record.

        Args:
            inventory: UserInventory entity to create

        Returns:
            Created inventory with ID populated
        """
        pass

    @abstractmethod
    async def update(self, inventory: UserInventory) -> UserInventory:
        """
        Update existing inventory record.

        Args:
            inventory: UserInventory entity to update (must have ID)

        Returns:
            Updated inventory
        """
        pass

    @abstractmethod
    async def delete(self, inventory_id: int, user_id: int) -> bool:
        """
        Delete inventory record by ID with user validation.

        Args:
            inventory_id: ID of inventory to delete
            user_id: User ID for ownership validation

        Returns:
            True if deleted, False if not found or unauthorized
        """
        pass

    # =========================================================================
    # QUANTITY OPERATIONS
    # =========================================================================

    @abstractmethod
    async def add_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date] = None,
        source: str = "manual"
    ) -> UserInventory:
        """
        Add quantity to existing inventory or create new record.

        If inventory record exists: increases quantity
        If not exists: creates new record

        Args:
            user_id: User ID
            item_id: Item ID
            quantity_grams: Amount to add (grams)
            expiry_date: Optional expiry date
            source: Source of addition (manual, ocr, etc.)

        Returns:
            Updated or created UserInventory
        """
        pass

    @abstractmethod
    async def deduct_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float
    ) -> UserInventory:
        """
        Deduct quantity from inventory.

        Decreases quantity. If quantity goes to or below 0, sets to 0.

        Args:
            user_id: User ID
            item_id: Item ID
            quantity_grams: Amount to deduct (grams)

        Returns:
            Updated UserInventory

        Raises:
            ValueError: If inventory item not found
        """
        pass

    @abstractmethod
    async def set_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date] = None
    ) -> UserInventory:
        """
        Set inventory quantity to a specific value (overwrite).

        Creates record if not exists.

        Args:
            user_id: User ID
            item_id: Item ID
            quantity_grams: New quantity (grams)
            expiry_date: Optional expiry date

        Returns:
            Updated or created UserInventory
        """
        pass

    @abstractmethod
    async def bulk_update_quantities(
        self,
        user_id: int,
        updates: List[Dict]
    ) -> List[Dict]:
        """
        Perform bulk quantity updates in one transaction.

        Updates format:
        [
            {
                "item_id": 1,
                "quantity_grams": 500,
                "operation": "add" | "deduct" | "set",
                "expiry_date": "2025-12-31" (optional)
            },
            ...
        ]

        Args:
            user_id: User ID
            updates: List of update operations

        Returns:
            List of results: [
                {
                    "item_id": 1,
                    "success": True,
                    "old_quantity": 200,
                    "new_quantity": 700
                },
                {
                    "item_id": 2,
                    "success": False,
                    "error": "Item not found"
                },
                ...
            ]
        """
        pass

    # =========================================================================
    # RECIPE INGREDIENT DEDUCTIONS
    # =========================================================================

    @abstractmethod
    async def deduct_recipe_ingredients(
        self,
        user_id: int,
        recipe: Recipe,
        portion_multiplier: float = 1.0
    ) -> List[Dict]:
        """
        Deduct all ingredients for a recipe from inventory.

        Automatically calculates quantities based on:
        - Recipe servings
        - Portion multiplier
        - Ingredient quantities in recipe

        Args:
            user_id: User ID
            recipe: Recipe entity with ingredients loaded
            portion_multiplier: Multiplier for portion size (default 1.0)

        Returns:
            List of deduction results: [
                {
                    "item_id": 1,
                    "item_name": "Chicken Breast",
                    "quantity_deducted": 200,
                    "old_quantity": 1000,
                    "new_quantity": 800,
                    "success": True
                },
                {
                    "item_id": 2,
                    "item_name": "Tomato",
                    "success": False,
                    "error": "Insufficient inventory"
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def check_recipe_ingredients_availability(
        self,
        user_id: int,
        recipe: Recipe,
        portion_multiplier: float = 1.0
    ) -> Dict:
        """
        Check if user has enough inventory to make a recipe.

        Does NOT deduct - just checks availability.

        Args:
            user_id: User ID
            recipe: Recipe entity with ingredients loaded
            portion_multiplier: Multiplier for portion size

        Returns:
            Dict: {
                "available": True | False,
                "missing_items": [
                    {
                        "item_id": 2,
                        "item_name": "Tomato",
                        "required_grams": 150,
                        "available_grams": 50,
                        "deficit_grams": 100
                    },
                    ...
                ],
                "low_stock_items": [...]
            }
        """
        pass

    # =========================================================================
    # EXPIRY AND FRESHNESS QUERIES
    # =========================================================================

    @abstractmethod
    async def get_expiring_items(
        self,
        user_id: int,
        days_threshold: int = 3
    ) -> List[UserInventory]:
        """
        Get inventory items expiring within N days.

        Args:
            user_id: User ID
            days_threshold: Number of days ahead to check (default 3)

        Returns:
            List of inventory items expiring soon, ordered by expiry_date ASC
        """
        pass

    @abstractmethod
    async def get_expired_items(
        self,
        user_id: int
    ) -> List[UserInventory]:
        """
        Get inventory items that have already expired.

        Args:
            user_id: User ID

        Returns:
            List of expired inventory items, ordered by expiry_date DESC
        """
        pass

    @abstractmethod
    async def get_items_without_expiry(
        self,
        user_id: int
    ) -> List[UserInventory]:
        """
        Get inventory items without expiry date set.

        Args:
            user_id: User ID

        Returns:
            List of inventory items with no expiry date
        """
        pass

    # =========================================================================
    # STOCK LEVEL QUERIES
    # =========================================================================

    @abstractmethod
    async def get_low_stock_items(
        self,
        user_id: int,
        threshold_grams: float = 100
    ) -> List[UserInventory]:
        """
        Get inventory items below a quantity threshold.

        Args:
            user_id: User ID
            threshold_grams: Quantity threshold (default 100g)

        Returns:
            List of low stock items, ordered by quantity ASC
        """
        pass

    @abstractmethod
    async def get_out_of_stock_items(
        self,
        user_id: int
    ) -> List[UserInventory]:
        """
        Get inventory items with zero or near-zero quantity.

        Args:
            user_id: User ID

        Returns:
            List of out-of-stock items (quantity <= 0)
        """
        pass

    @abstractmethod
    async def get_well_stocked_items(
        self,
        user_id: int,
        threshold_grams: float = 500
    ) -> List[UserInventory]:
        """
        Get inventory items with healthy stock levels.

        Args:
            user_id: User ID
            threshold_grams: Minimum quantity to consider "well stocked"

        Returns:
            List of well-stocked items, ordered by quantity DESC
        """
        pass

    # =========================================================================
    # CATEGORIZATION AND GROUPING
    # =========================================================================

    @abstractmethod
    async def get_inventory_by_category(
        self,
        user_id: int
    ) -> Dict[str, List[UserInventory]]:
        """
        Group inventory items by food category.

        Args:
            user_id: User ID

        Returns:
            Dict mapping category to items: {
                "protein": [UserInventory, ...],
                "vegetables": [UserInventory, ...],
                "grains": [UserInventory, ...],
                ...
            }
        """
        pass

    @abstractmethod
    async def get_inventory_by_source(
        self,
        user_id: int
    ) -> Dict[str, List[UserInventory]]:
        """
        Group inventory items by source (manual, ocr, deduction).

        Args:
            user_id: User ID

        Returns:
            Dict mapping source to items: {
                "manual": [UserInventory, ...],
                "ocr": [UserInventory, ...],
                "deduction": [UserInventory, ...]
            }
        """
        pass

    # =========================================================================
    # ANALYTICS AND STATISTICS
    # =========================================================================

    @abstractmethod
    async def calculate_total_inventory_weight(
        self,
        user_id: int
    ) -> float:
        """
        Calculate total weight of all inventory items.

        Args:
            user_id: User ID

        Returns:
            Total weight in grams
        """
        pass

    @abstractmethod
    async def calculate_inventory_value_estimate(
        self,
        user_id: int
    ) -> float:
        """
        Estimate total monetary value of inventory.

        Uses item prices if available (future feature).
        For now, returns 0.0 (placeholder).

        Args:
            user_id: User ID

        Returns:
            Estimated value in currency
        """
        pass

    @abstractmethod
    async def get_inventory_status_summary(
        self,
        user_id: int
    ) -> Dict:
        """
        Get comprehensive inventory status summary.

        Args:
            user_id: User ID

        Returns:
            Dict: {
                "total_items": 45,
                "total_weight_grams": 15000,
                "low_stock_count": 5,
                "out_of_stock_count": 2,
                "expiring_soon_count": 3,
                "expired_count": 1,
                "items_by_category": {
                    "protein": 10,
                    "vegetables": 15,
                    ...
                }
            }
        """
        pass

    @abstractmethod
    async def get_consumption_velocity(
        self,
        user_id: int,
        item_id: int,
        days_to_analyze: int = 14
    ) -> Dict:
        """
        Calculate how quickly an item is being consumed.

        Analyzes past deductions to estimate daily consumption rate.

        Args:
            user_id: User ID
            item_id: Item ID
            days_to_analyze: Number of days to look back

        Returns:
            Dict: {
                "item_id": 1,
                "average_daily_consumption_grams": 75,
                "days_until_depleted": 8.5,
                "depletion_date": "2025-12-05"
            }
        """
        pass

    # =========================================================================
    # HISTORICAL TRACKING
    # =========================================================================

    @abstractmethod
    async def get_inventory_changes_history(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict]:
        """
        Get history of inventory changes (additions/deductions).

        Note: This requires tracking inventory history in a separate table.
        For now, returns empty list (future feature).

        Args:
            user_id: User ID
            days: Number of days to look back

        Returns:
            List of change records: [
                {
                    "timestamp": "2025-11-25T10:30:00",
                    "item_id": 1,
                    "item_name": "Chicken",
                    "change_type": "deduction",
                    "quantity_grams": -200,
                    "source": "meal_log",
                    "related_id": 123  # meal_log_id
                },
                ...
            ]
        """
        pass

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    @abstractmethod
    async def bulk_create_inventory(
        self,
        inventory_items: List[UserInventory]
    ) -> List[UserInventory]:
        """
        Create multiple inventory records in one transaction.

        Used when adding items from receipt scanning or bulk import.

        Args:
            inventory_items: List of UserInventory entities

        Returns:
            List of created inventory items with IDs
        """
        pass

    @abstractmethod
    async def bulk_delete_inventory(
        self,
        inventory_ids: List[int],
        user_id: int
    ) -> int:
        """
        Delete multiple inventory records in one transaction.

        Args:
            inventory_ids: List of inventory IDs to delete
            user_id: User ID for validation

        Returns:
            Number of records deleted
        """
        pass

    @abstractmethod
    async def reset_user_inventory(
        self,
        user_id: int
    ) -> int:
        """
        Delete ALL inventory for a user.

        Use with caution - this is destructive.

        Args:
            user_id: User ID

        Returns:
            Number of records deleted
        """
        pass