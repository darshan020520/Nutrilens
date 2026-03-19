import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, and_, func, delete

from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.models.database import UserInventory, Item, Recipe

logger = logging.getLogger(__name__)


class InventoryRepository(IInventoryRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .order_by(UserInventory.id)
                .limit(limit)
                .offset(offset)
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting all inventory: {e}")
            raise

    async def get_by_id(self, inventory_id: int, user_id: int) -> Optional[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(and_(UserInventory.id == inventory_id, UserInventory.user_id == user_id))
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting inventory {inventory_id}: {e}")
            raise

    async def get_all_for_user(self, user_id: int, include_zero_quantity: bool = False) -> List[UserInventory]:
        try:
            stmt = (
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .join(Item, UserInventory.item_id == Item.id)
                .where(UserInventory.user_id == user_id)
                .order_by(Item.canonical_name)
            )

            if not include_zero_quantity:
                stmt = stmt.where(UserInventory.quantity_grams > 0)

            result = await self.db.execute(stmt)
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting inventory for user {user_id}: {e}")
            raise

    async def get_by_item_id(self, user_id: int, item_id: int) -> Optional[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(and_(UserInventory.user_id == user_id, UserInventory.item_id == item_id))
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting inventory for item {item_id}: {e}")
            raise

    async def get_all_inventory_for_item(
        self,
        user_id: int,
        item_id: int,
        order_by_expiry_desc: bool = True
    ) -> List[UserInventory]:
        try:
            stmt = (
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(and_(UserInventory.user_id == user_id, UserInventory.item_id == item_id))
            )

            if order_by_expiry_desc:
                stmt = stmt.order_by(UserInventory.expiry_date.desc())
            else:
                stmt = stmt.order_by(UserInventory.expiry_date.asc())

            result = await self.db.execute(stmt)
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting all inventory for item {item_id}: {e}")
            raise

    async def get_by_item_ids(self, user_id: int, item_ids: List[int]) -> Dict[int, UserInventory]:
        try:
            if not item_ids:
                return {}

            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.item_id.in_(item_ids)
                    )
                )
            )
            inventory_list = result.unique().scalars().all()
            return {inv.item_id: inv for inv in inventory_list}
        except Exception as e:
            logger.error(f"Error getting inventory for items {item_ids}: {e}")
            raise

    async def create(self, inventory: UserInventory) -> UserInventory:
        try:
            self.db.add(inventory)
            await self.db.flush()
            await self.db.refresh(inventory)
            logger.info(f"Created inventory {inventory.id} for user {inventory.user_id} (pending commit)")
            return inventory
        except Exception as e:
            logger.error(f"Error creating inventory: {e}")
            raise

    async def update(self, inventory: UserInventory) -> UserInventory:
        try:
            await self.db.flush()
            await self.db.refresh(inventory)
            logger.info(f"Updated inventory {inventory.id} (pending commit)")
            return inventory
        except Exception as e:
            logger.error(f"Error updating inventory {inventory.id}: {e}")
            raise

    async def delete(self, inventory_id: int, user_id: int) -> bool:
        try:
            result = await self.db.execute(
                delete(UserInventory).where(
                    and_(UserInventory.id == inventory_id, UserInventory.user_id == user_id)
                )
            )
            await self.db.flush()

            if result.rowcount > 0:
                logger.info(f"Deleted inventory {inventory_id} (pending commit)")
                return True
            else:
                logger.warning(f"Inventory {inventory_id} not found for deletion")
                return False
        except Exception as e:
            logger.error(f"Error deleting inventory {inventory_id}: {e}")
            raise

    async def add_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date] = None,
        source: str = "manual"
    ) -> UserInventory:
        try:
            existing = await self.get_by_item_id(user_id, item_id)

            if existing:
                existing.quantity_grams += quantity_grams
                if expiry_date:
                    existing.expiry_date = expiry_date
                existing.last_updated = datetime.utcnow()
                existing.source = source

                await self.db.commit()
                await self.db.refresh(existing)

                logger.info(f"Added {quantity_grams}g to inventory {existing.id}")
                return existing
            else:
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
            await self.db.rollback()
            logger.error(f"Error adding quantity to inventory: {e}")
            raise

    async def deduct_quantity(self, user_id: int, item_id: int, quantity_grams: float) -> UserInventory:
        try:
            inventory = await self.get_by_item_id(user_id, item_id)

            if not inventory:
                raise ValueError(f"Inventory item {item_id} not found for user {user_id}")

            inventory.quantity_grams = max(0, inventory.quantity_grams - quantity_grams)
            inventory.last_updated = datetime.utcnow()
            inventory.source = "deduction"

            await self.db.commit()
            await self.db.refresh(inventory)

            logger.info(f"Deducted {quantity_grams}g from inventory {inventory.id}")
            return inventory

        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deducting quantity from inventory: {e}")
            raise

    async def set_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date] = None
    ) -> UserInventory:
        try:
            existing = await self.get_by_item_id(user_id, item_id)

            if existing:
                existing.quantity_grams = quantity_grams
                if expiry_date:
                    existing.expiry_date = expiry_date
                existing.last_updated = datetime.utcnow()

                await self.db.commit()
                await self.db.refresh(existing)

                logger.info(f"Set inventory {existing.id} to {quantity_grams}g")
                return existing
            else:
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
            await self.db.rollback()
            logger.error(f"Error setting quantity: {e}")
            raise

    async def bulk_update_quantities(self, user_id: int, updates: List[Dict]) -> List[Dict]:
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

                    expiry_date = None
                    if expiry_date_str:
                        try:
                            expiry_date = datetime.fromisoformat(expiry_date_str).date()
                        except Exception:
                            pass

                    inventory = await self.get_by_item_id(user_id, item_id)
                    old_quantity = inventory.quantity_grams if inventory else 0

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

    async def deduct_recipe_ingredients(
        self,
        user_id: int,
        recipe: Recipe,
        portion_multiplier: float = 1.0
    ) -> List[Dict]:
        try:
            results = []

            if not recipe.ingredients:
                logger.warning(f"Recipe {recipe.id} has no ingredients")
                return results

            for ingredient in recipe.ingredients:
                try:
                    quantity_needed = ingredient.quantity_grams * portion_multiplier

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

    async def get_expiring_items(self, user_id: int, days_threshold: int = 3) -> List[UserInventory]:
        try:
            expiry_threshold = datetime.utcnow() + timedelta(days=days_threshold)

            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.quantity_grams > 0,
                        UserInventory.expiry_date.isnot(None),
                        UserInventory.expiry_date <= expiry_threshold
                    )
                )
                .order_by(UserInventory.expiry_date)
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting expiring items: {e}")
            raise

    async def get_expired_items(self, user_id: int) -> List[UserInventory]:
        try:
            now = datetime.utcnow()

            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.quantity_grams > 0,
                        UserInventory.expiry_date.isnot(None),
                        UserInventory.expiry_date < now
                    )
                )
                .order_by(UserInventory.expiry_date.desc())
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting expired items: {e}")
            raise

    async def get_items_without_expiry(self, user_id: int) -> List[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.quantity_grams > 0,
                        UserInventory.expiry_date.is_(None)
                    )
                )
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting items without expiry: {e}")
            raise

    async def get_low_stock_items(self, user_id: int, threshold_grams: float = 100) -> List[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.quantity_grams > 0,
                        UserInventory.quantity_grams <= threshold_grams
                    )
                )
                .order_by(UserInventory.quantity_grams)
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            raise

    async def get_out_of_stock_items(self, user_id: int) -> List[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.quantity_grams <= 0
                    )
                )
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting out of stock items: {e}")
            raise

    async def get_well_stocked_items(self, user_id: int, threshold_grams: float = 500) -> List[UserInventory]:
        try:
            result = await self.db.execute(
                select(UserInventory)
                .options(joinedload(UserInventory.item))
                .where(
                    and_(
                        UserInventory.user_id == user_id,
                        UserInventory.quantity_grams >= threshold_grams
                    )
                )
                .order_by(UserInventory.quantity_grams.desc())
            )
            return result.unique().scalars().all()
        except Exception as e:
            logger.error(f"Error getting well stocked items: {e}")
            raise

    async def get_inventory_by_category(self, user_id: int) -> Dict[str, List[UserInventory]]:
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

    async def get_inventory_by_source(self, user_id: int) -> Dict[str, List[UserInventory]]:
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

    async def calculate_total_inventory_weight(self, user_id: int) -> float:
        try:
            result = await self.db.execute(
                select(func.sum(UserInventory.quantity_grams)).where(
                    UserInventory.user_id == user_id
                )
            )
            total = result.scalar()
            return float(total) if total else 0.0
        except Exception as e:
            logger.error(f"Error calculating total weight: {e}")
            raise

    async def calculate_inventory_value_estimate(self, user_id: int) -> float:
        return 0.0

    async def get_inventory_status_summary(self, user_id: int) -> Dict:
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

    async def get_consumption_velocity(self, user_id: int, item_id: int, days_to_analyze: int = 14) -> Dict:
        return {
            "item_id": item_id,
            "average_daily_consumption_grams": 0,
            "days_until_depleted": 0,
            "depletion_date": None
        }

    async def get_inventory_changes_history(self, user_id: int, days: int = 30) -> List[Dict]:
        return []

    async def bulk_create_inventory(self, inventory_items: List[UserInventory]) -> List[UserInventory]:
        try:
            self.db.add_all(inventory_items)
            await self.db.commit()

            for inventory in inventory_items:
                await self.db.refresh(inventory)

            logger.info(f"Bulk created {len(inventory_items)} inventory items")
            return inventory_items

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error bulk creating inventory: {e}")
            raise

    async def bulk_delete_inventory(self, inventory_ids: List[int], user_id: int) -> int:
        try:
            result = await self.db.execute(
                delete(UserInventory).where(
                    and_(
                        UserInventory.id.in_(inventory_ids),
                        UserInventory.user_id == user_id
                    )
                )
            )
            await self.db.commit()
            logger.info(f"Bulk deleted {result.rowcount} inventory items")
            return result.rowcount

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error bulk deleting inventory: {e}")
            raise

    async def reset_user_inventory(self, user_id: int) -> int:
        try:
            result = await self.db.execute(
                delete(UserInventory).where(UserInventory.user_id == user_id)
            )
            await self.db.commit()
            logger.warning(f"Reset inventory for user {user_id} ({result.rowcount} items deleted)")
            return result.rowcount

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error resetting user inventory: {e}")
            raise
