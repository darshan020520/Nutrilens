"""
Inventory Repository Implementation

Implements data access operations for user inventory management.
Extracted from TrackingAgent and IntelligentInventoryService for clean repository pattern.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.models.database import UserInventory, Item, Recipe, RecipeIngredient

logger = logging.getLogger(__name__)


class InventoryRepository(IInventoryRepository):
    """
    Repository for inventory data access operations.

    All user inventory database queries are implemented here.
    NO business logic - only data access.
    """

    def __init__(self, db: Session):
        """
        Initialize inventory repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # =========================================================================
    # BASIC CRUD OPERATIONS
    # =========================================================================

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
        try:
            inventory = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.id == inventory_id,
                    UserInventory.user_id == user_id
                )
            ).first()

            return inventory

        except Exception as e:
            logger.error(f"Error getting inventory {inventory_id}: {e}")
            raise

    async def get_all_for_user(
        self,
        user_id: int,
        include_zero_quantity: bool = False
    ) -> List[UserInventory]:
        """
        Get all inventory items for a user.

        Source: backend/app/agents/tracking_agent.py:97

        Args:
            user_id: User ID
            include_zero_quantity: If True, include items with 0 quantity

        Returns:
            List of inventory items ordered by item name
        """
        try:
            query = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                UserInventory.user_id == user_id
            )

            if not include_zero_quantity:
                query = query.filter(UserInventory.quantity_grams > 0)

            inventory_items = query.join(
                Item, UserInventory.item_id == Item.id
            ).order_by(
                Item.canonical_name
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting inventory for user {user_id}: {e}")
            raise

    async def get_by_item_id(
        self,
        user_id: int,
        item_id: int
    ) -> Optional[UserInventory]:
        """
        Get inventory record for a specific item.

        Source: backend/app/services/inventory_service.py (pattern)

        Args:
            user_id: User ID
            item_id: Item ID

        Returns:
            UserInventory if found, None otherwise
        """
        try:
            inventory = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.item_id == item_id
                )
            ).first()

            return inventory

        except Exception as e:
            logger.error(f"Error getting inventory for item {item_id}: {e}")
            raise

    async def create(self, inventory: UserInventory) -> UserInventory:
        """
        Create new inventory record.

        Args:
            inventory: UserInventory entity to create

        Returns:
            Created inventory with ID populated
        """
        try:
            self.db.add(inventory)
            self.db.commit()
            self.db.refresh(inventory)

            logger.info(f"Created inventory {inventory.id} for user {inventory.user_id}")
            return inventory

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating inventory: {e}")
            raise

    async def update(self, inventory: UserInventory) -> UserInventory:
        """
        Update existing inventory record.

        Args:
            inventory: UserInventory entity to update (must have ID)

        Returns:
            Updated inventory
        """
        try:
            inventory.last_updated = datetime.utcnow()
            self.db.commit()
            self.db.refresh(inventory)

            logger.info(f"Updated inventory {inventory.id}")
            return inventory

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating inventory {inventory.id}: {e}")
            raise

    async def delete(self, inventory_id: int, user_id: int) -> bool:
        """
        Delete inventory record by ID with user validation.

        Args:
            inventory_id: ID of inventory to delete
            user_id: User ID for ownership validation

        Returns:
            True if deleted, False if not found or unauthorized
        """
        try:
            result = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.id == inventory_id,
                    UserInventory.user_id == user_id
                )
            ).delete()

            self.db.commit()

            if result > 0:
                logger.info(f"Deleted inventory {inventory_id}")
                return True
            else:
                logger.warning(f"Inventory {inventory_id} not found for deletion")
                return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting inventory {inventory_id}: {e}")
            raise

    # =========================================================================
    # QUANTITY OPERATIONS
    # =========================================================================

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

        Source: backend/app/services/inventory_service.py:add_item

        Args:
            user_id: User ID
            item_id: Item ID
            quantity_grams: Amount to add (grams)
            expiry_date: Optional expiry date
            source: Source of addition (manual, ocr, etc.)

        Returns:
            Updated or created UserInventory
        """
        try:
            # Check if inventory exists
            existing = await self.get_by_item_id(user_id, item_id)

            if existing:
                # Add to existing quantity
                existing.quantity_grams += quantity_grams
                if expiry_date:
                    existing.expiry_date = expiry_date
                existing.last_updated = datetime.utcnow()
                existing.source = source

                self.db.commit()
                self.db.refresh(existing)

                logger.info(f"Added {quantity_grams}g to inventory {existing.id}")
                return existing
            else:
                # Create new inventory record
                new_inventory = UserInventory(
                    user_id=user_id,
                    item_id=item_id,
                    quantity_grams=quantity_grams,
                    expiry_date=expiry_date,
                    source=source,
                    purchase_date=datetime.utcnow(),
                    last_updated=datetime.utcnow()
                )

                return await self.create(new_inventory)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding quantity to inventory: {e}")
            raise

    async def deduct_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float
    ) -> UserInventory:
        """
        Deduct quantity from inventory.

        Source: backend/app/services/inventory_service.py:deduct_item

        Args:
            user_id: User ID
            item_id: Item ID
            quantity_grams: Amount to deduct (grams)

        Returns:
            Updated UserInventory

        Raises:
            ValueError: If inventory item not found
        """
        try:
            inventory = await self.get_by_item_id(user_id, item_id)

            if not inventory:
                raise ValueError(f"Inventory item {item_id} not found for user {user_id}")

            # Deduct quantity (set to 0 if goes negative)
            inventory.quantity_grams = max(0, inventory.quantity_grams - quantity_grams)
            inventory.last_updated = datetime.utcnow()
            inventory.source = "deduction"

            self.db.commit()
            self.db.refresh(inventory)

            logger.info(f"Deducted {quantity_grams}g from inventory {inventory.id}")
            return inventory

        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deducting quantity from inventory: {e}")
            raise

    async def set_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date] = None
    ) -> UserInventory:
        """
        Set inventory quantity to a specific value (overwrite).

        Args:
            user_id: User ID
            item_id: Item ID
            quantity_grams: New quantity (grams)
            expiry_date: Optional expiry date

        Returns:
            Updated or created UserInventory
        """
        try:
            existing = await self.get_by_item_id(user_id, item_id)

            if existing:
                # Update existing
                existing.quantity_grams = quantity_grams
                if expiry_date:
                    existing.expiry_date = expiry_date
                existing.last_updated = datetime.utcnow()

                self.db.commit()
                self.db.refresh(existing)

                logger.info(f"Set inventory {existing.id} to {quantity_grams}g")
                return existing
            else:
                # Create new
                new_inventory = UserInventory(
                    user_id=user_id,
                    item_id=item_id,
                    quantity_grams=quantity_grams,
                    expiry_date=expiry_date,
                    source="manual",
                    purchase_date=datetime.utcnow(),
                    last_updated=datetime.utcnow()
                )

                return await self.create(new_inventory)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error setting quantity: {e}")
            raise

    async def bulk_update_quantities(
        self,
        user_id: int,
        updates: List[Dict]
    ) -> List[Dict]:
        """
        Perform bulk quantity updates in one transaction.

        Source: backend/app/agents/tracking_agent.py:314-400

        Args:
            user_id: User ID
            updates: List of update operations

        Returns:
            List of results with success/failure for each update
        """
        results = []

        try:
            for update in updates:
                try:
                    item_id = update.get("item_id")
                    quantity = update.get("quantity_grams")
                    operation = update.get("operation", "add")
                    expiry_date_str = update.get("expiry_date")

                    if not item_id or quantity is None:
                        results.append({
                            "item_id": item_id,
                            "success": False,
                            "error": "Missing item_id or quantity"
                        })
                        continue

                    # Parse expiry date if provided
                    expiry_date = None
                    if expiry_date_str:
                        try:
                            expiry_date = datetime.fromisoformat(expiry_date_str).date()
                        except:
                            pass

                    # Get current quantity
                    inventory = await self.get_by_item_id(user_id, item_id)
                    old_quantity = inventory.quantity_grams if inventory else 0

                    # Perform operation
                    if operation == "add":
                        result_inv = await self.add_quantity(user_id, item_id, quantity, expiry_date)
                    elif operation == "deduct":
                        result_inv = await self.deduct_quantity(user_id, item_id, quantity)
                    elif operation == "set":
                        result_inv = await self.set_quantity(user_id, item_id, quantity, expiry_date)
                    else:
                        results.append({
                            "item_id": item_id,
                            "success": False,
                            "error": f"Invalid operation: {operation}"
                        })
                        continue

                    results.append({
                        "item_id": item_id,
                        "success": True,
                        "old_quantity": old_quantity,
                        "new_quantity": result_inv.quantity_grams
                    })

                except Exception as e:
                    logger.error(f"Error processing update for item {item_id}: {e}")
                    results.append({
                        "item_id": item_id,
                        "success": False,
                        "error": str(e)
                    })

            return results

        except Exception as e:
            logger.error(f"Error in bulk update: {e}")
            raise

    # =========================================================================
    # RECIPE INGREDIENT DEDUCTIONS
    # =========================================================================

    async def deduct_recipe_ingredients(
        self,
        user_id: int,
        recipe: Recipe,
        portion_multiplier: float = 1.0
    ) -> List[Dict]:
        """
        Deduct all ingredients for a recipe from inventory.

        Args:
            user_id: User ID
            recipe: Recipe entity with ingredients loaded
            portion_multiplier: Multiplier for portion size

        Returns:
            List of deduction results
        """
        try:
            results = []

            if not recipe.ingredients:
                logger.warning(f"Recipe {recipe.id} has no ingredients")
                return results

            for ingredient in recipe.ingredients:
                try:
                    quantity_needed = ingredient.quantity_grams * portion_multiplier

                    # Try to deduct
                    try:
                        inventory = await self.deduct_quantity(
                            user_id=user_id,
                            item_id=ingredient.item_id,
                            quantity_grams=quantity_needed
                        )

                        results.append({
                            "item_id": ingredient.item_id,
                            "item_name": ingredient.item.canonical_name if ingredient.item else "Unknown",
                            "quantity_deducted": quantity_needed,
                            "old_quantity": inventory.quantity_grams + quantity_needed,
                            "new_quantity": inventory.quantity_grams,
                            "success": True
                        })

                    except ValueError as e:
                        # Item not in inventory
                        results.append({
                            "item_id": ingredient.item_id,
                            "item_name": ingredient.item.canonical_name if ingredient.item else "Unknown",
                            "success": False,
                            "error": str(e)
                        })

                except Exception as e:
                    logger.error(f"Error deducting ingredient {ingredient.item_id}: {e}")
                    results.append({
                        "item_id": ingredient.item_id,
                        "success": False,
                        "error": str(e)
                    })

            return results

        except Exception as e:
            logger.error(f"Error deducting recipe ingredients: {e}")
            raise

    async def check_recipe_ingredients_availability(
        self,
        user_id: int,
        recipe: Recipe,
        portion_multiplier: float = 1.0
    ) -> Dict:
        """
        Check if user has enough inventory to make a recipe.

        Args:
            user_id: User ID
            recipe: Recipe entity with ingredients loaded
            portion_multiplier: Multiplier for portion size

        Returns:
            Dict with availability info and missing items
        """
        try:
            missing_items = []
            low_stock_items = []
            available = True

            if not recipe.ingredients:
                return {
                    "available": True,
                    "missing_items": [],
                    "low_stock_items": []
                }

            for ingredient in recipe.ingredients:
                quantity_needed = ingredient.quantity_grams * portion_multiplier
                inventory = await self.get_by_item_id(user_id, ingredient.item_id)

                if not inventory or inventory.quantity_grams < quantity_needed:
                    available = False
                    available_grams = inventory.quantity_grams if inventory else 0

                    missing_items.append({
                        "item_id": ingredient.item_id,
                        "item_name": ingredient.item.canonical_name if ingredient.item else "Unknown",
                        "required_grams": quantity_needed,
                        "available_grams": available_grams,
                        "deficit_grams": quantity_needed - available_grams
                    })
                elif inventory.quantity_grams < (quantity_needed * 1.5):
                    # Low stock warning (less than 1.5x needed)
                    low_stock_items.append({
                        "item_id": ingredient.item_id,
                        "item_name": ingredient.item.canonical_name if ingredient.item else "Unknown",
                        "required_grams": quantity_needed,
                        "available_grams": inventory.quantity_grams
                    })

            return {
                "available": available,
                "missing_items": missing_items,
                "low_stock_items": low_stock_items
            }

        except Exception as e:
            logger.error(f"Error checking recipe availability: {e}")
            raise

    # =========================================================================
    # EXPIRY AND FRESHNESS QUERIES
    # =========================================================================

    async def get_expiring_items(
        self,
        user_id: int,
        days_threshold: int = 3
    ) -> List[UserInventory]:
        """
        Get inventory items expiring within N days.

        Source: backend/app/agents/tracking_agent.py:682-821

        Args:
            user_id: User ID
            days_threshold: Number of days ahead to check

        Returns:
            List of inventory items expiring soon, ordered by expiry_date ASC
        """
        try:
            expiry_threshold = datetime.utcnow() + timedelta(days=days_threshold)

            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.expiry_date.isnot(None),
                    UserInventory.expiry_date <= expiry_threshold
                )
            ).order_by(
                UserInventory.expiry_date
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting expiring items: {e}")
            raise

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
        try:
            now = datetime.utcnow()

            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.expiry_date.isnot(None),
                    UserInventory.expiry_date < now
                )
            ).order_by(
                UserInventory.expiry_date.desc()
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting expired items: {e}")
            raise

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
        try:
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.expiry_date.is_(None)
                )
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting items without expiry: {e}")
            raise

    # =========================================================================
    # STOCK LEVEL QUERIES
    # =========================================================================

    async def get_low_stock_items(
        self,
        user_id: int,
        threshold_grams: float = 100
    ) -> List[UserInventory]:
        """
        Get inventory items below a quantity threshold.

        Args:
            user_id: User ID
            threshold_grams: Quantity threshold

        Returns:
            List of low stock items, ordered by quantity ASC
        """
        try:
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.quantity_grams <= threshold_grams
                )
            ).order_by(
                UserInventory.quantity_grams
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            raise

    async def get_out_of_stock_items(
        self,
        user_id: int
    ) -> List[UserInventory]:
        """
        Get inventory items with zero or near-zero quantity.

        Args:
            user_id: User ID

        Returns:
            List of out-of-stock items
        """
        try:
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams <= 0
                )
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting out of stock items: {e}")
            raise

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
        try:
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams >= threshold_grams
                )
            ).order_by(
                UserInventory.quantity_grams.desc()
            ).all()

            return inventory_items

        except Exception as e:
            logger.error(f"Error getting well stocked items: {e}")
            raise

    # =========================================================================
    # CATEGORIZATION AND GROUPING
    # =========================================================================

    async def get_inventory_by_category(
        self,
        user_id: int
    ) -> Dict[str, List[UserInventory]]:
        """
        Group inventory items by food category.

        Args:
            user_id: User ID

        Returns:
            Dict mapping category to items
        """
        try:
            inventory_items = await self.get_all_for_user(user_id, include_zero_quantity=False)

            by_category = {}
            for inv_item in inventory_items:
                if inv_item.item:
                    category = inv_item.item.category or "other"
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append(inv_item)

            return by_category

        except Exception as e:
            logger.error(f"Error grouping inventory by category: {e}")
            raise

    async def get_inventory_by_source(
        self,
        user_id: int
    ) -> Dict[str, List[UserInventory]]:
        """
        Group inventory items by source (manual, ocr, deduction).

        Args:
            user_id: User ID

        Returns:
            Dict mapping source to items
        """
        try:
            inventory_items = await self.get_all_for_user(user_id, include_zero_quantity=False)

            by_source = {}
            for inv_item in inventory_items:
                source = inv_item.source or "manual"
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(inv_item)

            return by_source

        except Exception as e:
            logger.error(f"Error grouping inventory by source: {e}")
            raise

    # =========================================================================
    # ANALYTICS AND STATISTICS
    # =========================================================================

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
        try:
            total = self.db.query(
                func.sum(UserInventory.quantity_grams)
            ).filter(
                UserInventory.user_id == user_id
            ).scalar()

            return float(total) if total else 0.0

        except Exception as e:
            logger.error(f"Error calculating total weight: {e}")
            raise

    async def calculate_inventory_value_estimate(
        self,
        user_id: int
    ) -> float:
        """
        Estimate total monetary value of inventory.

        Placeholder for future feature.

        Args:
            user_id: User ID

        Returns:
            Estimated value (currently 0.0)
        """
        # Placeholder - would need item prices
        return 0.0

    async def get_inventory_status_summary(
        self,
        user_id: int
    ) -> Dict:
        """
        Get comprehensive inventory status summary.

        Args:
            user_id: User ID

        Returns:
            Dict with summary statistics
        """
        try:
            all_items = await self.get_all_for_user(user_id, include_zero_quantity=False)
            total_weight = await self.calculate_total_inventory_weight(user_id)

            low_stock = await self.get_low_stock_items(user_id, threshold_grams=100)
            out_of_stock = await self.get_out_of_stock_items(user_id)
            expiring_soon = await self.get_expiring_items(user_id, days_threshold=3)
            expired = await self.get_expired_items(user_id)

            by_category = await self.get_inventory_by_category(user_id)
            category_counts = {cat: len(items) for cat, items in by_category.items()}

            return {
                "total_items": len(all_items),
                "total_weight_grams": total_weight,
                "low_stock_count": len(low_stock),
                "out_of_stock_count": len(out_of_stock),
                "expiring_soon_count": len(expiring_soon),
                "expired_count": len(expired),
                "items_by_category": category_counts
            }

        except Exception as e:
            logger.error(f"Error getting inventory status summary: {e}")
            raise

    async def get_consumption_velocity(
        self,
        user_id: int,
        item_id: int,
        days_to_analyze: int = 14
    ) -> Dict:
        """
        Calculate how quickly an item is being consumed.

        Placeholder for future analytics feature.

        Args:
            user_id: User ID
            item_id: Item ID
            days_to_analyze: Number of days to look back

        Returns:
            Dict with velocity data (placeholder)
        """
        # Placeholder - would need consumption history tracking
        return {
            "item_id": item_id,
            "average_daily_consumption_grams": 0,
            "days_until_depleted": 0,
            "depletion_date": None
        }

    # =========================================================================
    # HISTORICAL TRACKING
    # =========================================================================

    async def get_inventory_changes_history(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict]:
        """
        Get history of inventory changes.

        Placeholder for future feature (requires separate history table).

        Args:
            user_id: User ID
            days: Number of days to look back

        Returns:
            Empty list (placeholder)
        """
        # Placeholder - would need inventory_history table
        return []

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    async def bulk_create_inventory(
        self,
        inventory_items: List[UserInventory]
    ) -> List[UserInventory]:
        """
        Create multiple inventory records in one transaction.

        Args:
            inventory_items: List of UserInventory entities

        Returns:
            List of created inventory items with IDs
        """
        try:
            self.db.add_all(inventory_items)
            self.db.commit()

            for inventory in inventory_items:
                self.db.refresh(inventory)

            logger.info(f"Bulk created {len(inventory_items)} inventory items")
            return inventory_items

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk creating inventory: {e}")
            raise

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
        try:
            result = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.id.in_(inventory_ids),
                    UserInventory.user_id == user_id
                )
            ).delete(synchronize_session=False)

            self.db.commit()

            logger.info(f"Bulk deleted {result} inventory items")
            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk deleting inventory: {e}")
            raise

    async def reset_user_inventory(
        self,
        user_id: int
    ) -> int:
        """
        Delete ALL inventory for a user.

        Args:
            user_id: User ID

        Returns:
            Number of records deleted
        """
        try:
            result = self.db.query(UserInventory).filter(
                UserInventory.user_id == user_id
            ).delete()

            self.db.commit()

            logger.warning(f"Reset inventory for user {user_id} ({result} items deleted)")
            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error resetting user inventory: {e}")
            raise