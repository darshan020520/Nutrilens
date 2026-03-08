from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.core.datetime_utils import DateTimeHelper
from app.models.database import UserInventory, Item, User, MealLog, UserProfile, Recipe, RecipeIngredient, SessionLocal
from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces import IUserProfileRepository
from app.infrastructure.normalization.batch.batch_normalizer import BatchNormalizer
from app.core.exceptions import TokenBudgetExceeded
import asyncio
import json
import logging
from dataclasses import dataclass
from app.infrastructure.normalization.repositories.item_repository import ItemRepository
from app.services.grocery_service import GroceryService
from app.repositories.interfaces.meal_plan_repository import IMealPlanRepository

logger = logging.getLogger(__name__)

@dataclass
class InventoryStatus:
    """Comprehensive inventory status for AI decision making"""
    total_items: int
    total_weight_g: float
    expiring_soon: List[Dict]  # Items expiring in next 3 days
    low_stock: List[Dict]  # Items below 20% of usual quantity
    categories_available: Dict[str, int]  # Count by category
    nutritional_capacity: Dict[str, float]  # Total protein, carbs, etc available
    estimated_days_remaining: int  # Based on consumption patterns
    recommendations: List[str]  # AI recommendations

class IntelligentInventoryServiceV2:

    CATEGORY_SHELF_LIFE = {
        'vegetables': 7,
        'fruits': 7,
        'dairy': 7,
        'meat': 5,
        'poultry': 5,
        'seafood': 3,
        'eggs': 21,
        'grains': 365,
        'legumes': 365,
        'nuts': 180,
        'oils': 180,
        'spices': 365,
        'condiments': 90,
        'beverages': 30,
        'default': 14
    }

    def __init__(
        self,
        inventory_repo: IInventoryRepository,
        recipe_repo:  IRecipeRepository,
        normalizer: BatchNormalizer,
        item_repo: ItemRepository,
        db: Session,
        llm_orchestrator=None,
        embedding_adapter=None,
        user_profile_repo: IUserProfileRepository = None,
        meal_plan_repo: IMealPlanRepository = None,
        grocery_service: GroceryService = None
    ):
        self.inventory_repo = inventory_repo
        self.recipe_repo = recipe_repo
        self.normalizer = normalizer
        self.item_repo = item_repo
        self.db = db
        self.llm_orchestrator = llm_orchestrator
        self.embedding_adapter = embedding_adapter
        self.user_profile_repo = user_profile_repo
        self.meal_plan_repo = meal_plan_repo
        self.grocery_service = grocery_service or GroceryService(recipe_repo, inventory_repo)

    def _get_default_expiry_days(self, item: Item) -> int:
        """Get default shelf life for item based on category"""
        category = item.category.lower() if item.category else 'default'
        return self.CATEGORY_SHELF_LIFE.get(category, self.CATEGORY_SHELF_LIFE['default'])

    async def add_item(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[datetime] = None,
        source: str = "manual"
    ) -> Dict:

        try:

            item = await self.item_repo.get_item_by_id(item_id)
            if not item:
                return {"success": False, "error": "Item not found"}

            expiry_days = None
            if expiry_date:
                expiry_date = DateTimeHelper.ensure_utc(expiry_date)
                expiry_days = (expiry_date - DateTimeHelper.now_utc()).days


            await self._add_to_inventory(
                user_id=user_id,
                item_id=item_id,
                quantity_grams=quantity_grams,
                expiry_days=expiry_days,
                source=source
            )

            self.db.commit()

            batches = await self.inventory_repo.get_all_inventory_for_item(
                user_id=user_id,
                item_id=item_id
            )
            total_remaining = sum(batch.quantity_grams for batch in batches)

            return {
                "success": True,
                "item": item.canonical_name,
                "quantity_added": quantity_grams,
                "remaining_quantity": total_remaining
            }

        except Exception as e:
            logger.error(f"Error adding item: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def bulk_add_from_restock(
        self,
        user_id: int,
        items: List[Dict]
    ) -> Dict:
        """
        Bulk add items from restock list to inventory.
        Reuses _add_to_inventory() for each item (expiry auto-assignment, batch merging).
        Single commit at end for atomicity.
        """
        added_items = []
        failed_items = []

        try:
            for item_data in items:
                item_id = item_data["item_id"]
                quantity_grams = item_data["quantity_grams"]

                try:
                    await self._add_to_inventory(
                        user_id=user_id,
                        item_id=item_id,
                        quantity_grams=quantity_grams,
                        expiry_days=None,
                        source="restock"
                    )

                    item = await self.item_repo.get_item_by_id(item_id)
                    added_items.append({
                        "item_id": item_id,
                        "item_name": item.canonical_name if item else f"Item {item_id}",
                        "quantity_added": quantity_grams,
                    })

                except Exception as e:
                    logger.error(f"Failed to add item {item_id}: {str(e)}")
                    failed_items.append({
                        "item_id": item_id,
                        "error": str(e)
                    })

            self.db.commit()
            logger.info(f"Bulk add from restock: {len(added_items)} added, {len(failed_items)} failed for user {user_id}")

            return {
                "success": len(failed_items) == 0,
                "total_requested": len(items),
                "successfully_added": len(added_items),
                "failed_count": len(failed_items),
                "added_items": added_items,
                "failed_items": failed_items,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Bulk add from restock failed: {str(e)}")
            raise

    async def deduct_item(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float
    ) -> Dict:

        try:

            inventory_item = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.item_id == item_id
                )
            ).first()

            if not inventory_item:
                return {
                    "success": False,
                    "error": "Item not in inventory",
                    "remaining_quantity": 0
                }

            item = self.db.query(Item).filter(Item.id == item_id).first()

            if inventory_item.quantity_grams < quantity_grams:
                deducted = inventory_item.quantity_grams
                inventory_item.quantity_grams = 0
                warning = f"Only {deducted}g available, deducted all"
            else:
                inventory_item.quantity_grams -= quantity_grams
                deducted = quantity_grams
                warning = None

            inventory_item.last_updated = datetime.now(timezone.utc)
            self.db.commit()

            result = {
                "success": True,
                "item": item.canonical_name if item else "Unknown",
                "quantity_deducted": deducted,
                "remaining_quantity": inventory_item.quantity_grams
            }

            if warning:
                result["warning"] = warning

            return result

        except Exception as e:
            logger.error(f"Error deducting item: {str(e)}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "remaining_quantity": 0
            }

    async def add_items_from_text(self, user_id: int, text_input: str) -> Dict:

        lines = [line.strip() for line in text_input.strip().split('\n') if line.strip()]

        results = {
            'successful': [],
            'needs_confirmation': [],
            'failed': [],
            'summary': {}
        }

        if not lines:
            return results

        try:
            batch_results = await self.normalizer.process_batch(lines, user_id=user_id)

            for idx, result in enumerate(batch_results):
                line = result.get('input') or f"Item {idx + 1}"

                if not result.get('success'):
                    if result.get('error') == 'unknown_item_detected' and result.get('unknown_item'):
                        unknown = result['unknown_item']

                        logger.info(f"UNKNOWN ITEM DETECTED: {unknown['normalized_name']} (category: {unknown['category']})")

                        # TODO: Add to pending_items table here
                        # For now, add to needs_confirmation with special action
                        results['needs_confirmation'].append({
                            'original': line,
                            'action': 'add_to_pending',
                            'suggested_name': unknown['normalized_name'],
                            'category': unknown['category'],
                            'confidence': unknown['confidence'],
                            'message': f"{unknown['normalized_name']} not in database. Added to pending items.",
                            'extracted': result.get('extracted', {})
                        })
                        continue

                    logger.info(f"FAILED - {result.get('error', 'Unknown error')}")
                    results['failed'].append({
                        'original': line,
                        'reason': result.get('error', 'Could not normalize item'),
                        'suggestions': []
                    })
                    continue

                item_id = result['item_id']
                item_name = result['item_name']
                quantity_grams = result['quantity_grams']
                confidence = result.get('confidence', 0.0)
                match_strategy = result.get('match_strategy', 'unknown')

                if confidence >= 0.85:
                    try:
                        inventory_item = await self._add_to_inventory(
                            user_id,
                            item_id,
                            quantity_grams
                        )

                        results['successful'].append({
                            'original': line,
                            'matched': item_name,
                            'quantity': f"{inventory_item.quantity_grams}g",
                            'confidence': confidence
                        })

                    except Exception as e:
                        results['failed'].append({
                            'original': line,
                            'reason': f"Failed to add to inventory: {str(e)}",
                            'suggestions': []
                        })

                elif confidence >= 0.6:
                    results['needs_confirmation'].append({
                        'original': line,
                        'item_id': item_id,
                        'suggested': item_name,
                        'quantity_grams': quantity_grams,
                        'alternatives': [],  # TODO: Add alternatives from vector search
                        'confidence': confidence
                    })
                else:

                    results['needs_confirmation'].append({
                        'original': line,
                        'item_id': item_id,
                        'suggested': item_name,
                        'quantity_grams': quantity_grams,
                        'suggestions': [],  # TODO: Add suggestions from vector search
                        'confidence': confidence
                    })

            total_items = len(batch_results)
            results['summary'] = {
                'total_processed': total_items,
                'successful': len(results['successful']),
                'needs_confirmation': len(results['needs_confirmation']),
                'failed': len(results['failed']),
                'success_rate': len(results['successful']) / total_items if total_items else 0
            }

            self.db.commit()

        except Exception as e:

            self.db.rollback()
            raise

        return results

    async def _add_to_inventory(self, user_id, item_id, quantity_grams, expiry_days=None, source="manual"):
        """
        Add item to inventory with smart batch management
        - Auto-assigns expiry based on category if not provided
        - Creates new record if expiry differs by >2 days
        - Merges with existing record if expiry is similar (≤2 days)

        Clean Architecture:
        - Business logic (2-day threshold, category-based expiry) in service
        - Data access delegated to repositories

        NOTE: Does NOT commit - caller controls transaction boundary
        """
        logger.info(f"   _add_to_inventory called: user_id={user_id}, item_id={item_id}, quantity_grams={quantity_grams}")

        item = await self.item_repo.get_item_by_id(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")


        if expiry_days is None:
            expiry_days = self._get_default_expiry_days(item)
            logger.info(f"   Auto-assigned expiry: {expiry_days} days (category: {item.category})")

        new_expiry_date = datetime.now(timezone.utc) + timedelta(days=expiry_days)  # ✅ UTC


        existing_inventory = await self.inventory_repo.get_all_inventory_for_item(
            user_id=user_id,
            item_id=item_id,
            order_by_expiry_desc=True
        )


        matching_record = None
        for inv in existing_inventory:
            if inv.expiry_date:
                expiry_date = DateTimeHelper.ensure_utc(inv.expiry_date)
                new_expiry_date = DateTimeHelper.ensure_utc(new_expiry_date)
                days_diff = abs((expiry_date - new_expiry_date).days)
                if days_diff <= 2:
                    matching_record = inv
                    break

        if matching_record:

            current_grams = matching_record.quantity_grams or 0
            logger.info(f"   Merging with existing record (expiry: {matching_record.expiry_date.date()})")
            logger.info(f"   Current: {current_grams}g -> New: {current_grams + quantity_grams}g")

            matching_record.quantity_grams = current_grams + quantity_grams
            matching_record.last_updated = datetime.now(timezone.utc)
            inventory_item = await self.inventory_repo.update(matching_record)
        else:

            logger.info(f"   Creating new record (expiry: {new_expiry_date.date()})")

            inventory_item = UserInventory(
                user_id=user_id,
                item_id=item_id,
                quantity_grams=quantity_grams,
                purchase_date=datetime.now(timezone.utc),
                expiry_date=new_expiry_date,
                source=source,
                last_updated=datetime.now(timezone.utc)
            )
            inventory_item = await self.inventory_repo.create(inventory_item)

        logger.info(f"   Added to inventory (pending commit) - Quantity: {inventory_item.quantity_grams}g")
        return inventory_item

    async def deduct_for_meal(
        self,
        user_id: int,
        recipe_id: int,
        portion_multiplier: float = 1.0
    ) -> Dict:

        ingredients = self.recipe_repo.get_ingredients_by_recipe_id(recipe_id)

        deductions = []
        warnings = []

        for ingredient in ingredients:
            if ingredient.is_optional:
                continue

            required_amount = ingredient.quantity_grams * portion_multiplier

            inventory_item = await self.inventory_repo.get_by_user_and_item(
                user_id=user_id,
                item_id=ingredient.item_id
            )

            if not inventory_item:
                warnings.append(f"Item {ingredient.item.canonical_name} not in inventory")
                continue

            if inventory_item.quantity_grams < required_amount:
                warnings.append(
                    f"Not enough {ingredient.item.canonical_name}: "
                    f"needed {required_amount}g, have {inventory_item.quantity_grams}g"
                )

                deducted = inventory_item.quantity_grams
                inventory_item.quantity_grams = 0
            else:

                inventory_item.quantity_grams -= required_amount
                deducted = required_amount

            inventory_item.last_updated = DateTimeHelper.now_utc()

            deductions.append({
                'item': ingredient.item.canonical_name,
                'deducted': deducted,
                'remaining': inventory_item.quantity_grams
            })


            if inventory_item.quantity_grams < 50:
                warnings.append(f"{ingredient.item.canonical_name} is running low")

        self.db.commit()

        return {
            'deductions': deductions,
            'warnings': warnings,
            'success': len(warnings) == 0
        }

    async def get_inventory_status(self, user_id: int) -> Dict:

        inventory = await self.inventory_repo.get_all_for_user(
            user_id=user_id,
            include_zero_quantity=False
        )

        if not inventory:
            return {
                "total_items": 0,
                "total_weight_g": 0,
                "expiring_soon": [],
                "low_stock": [],
                "categories": {},
                "nutritional_capacity": {
                    'protein_g': 0,
                    'carbs_g': 0,
                    'fat_g': 0,
                    'calories': 0
                },
                "estimated_days_remaining": 0,
                "ai_recommendations": ["Your inventory is empty. Add items to get started!"]
            }


        total_items = len(inventory)
        total_weight = sum(item.quantity_grams or 0 for item in inventory)

        expiring_soon = []
        expired_items = []
        categories = {}
        nutritional_capacity = {
            'calories': 0,
            'protein_g': 0,
            'carbs_g': 0,
            'fat_g': 0
        }

        now_utc = DateTimeHelper.now_utc()
        three_days_later = now_utc + timedelta(days=3)

        for inv_item in inventory:
            item = inv_item.item

            if not item:
                continue

            expiry = DateTimeHelper.ensure_utc(inv_item.expiry_date)

            qty = inv_item.quantity_grams or 0

            if expiry:
                days_until = DateTimeHelper.days_until(expiry)
                if expiry < now_utc:
                    expired_items.append({
                        'item': item.canonical_name,
                        'quantity': qty,
                        'expired_days_ago': abs(days_until)
                    })
                elif expiry <= three_days_later:
                    expiring_soon.append({
                        'item': item.canonical_name,
                        'quantity': qty,
                        'expires_in_days': days_until
                    })

            category = item.category or 'uncategorized'
            categories[category] = categories.get(category, 0) + 1

            if item.nutrition_per_100g and qty > 0:
                factor = qty / 100
                for nutrient in nutritional_capacity:
                    if nutrient in item.nutrition_per_100g:
                        nutritional_capacity[nutrient] += item.nutrition_per_100g[nutrient] * factor

        # Low stock: items where current inventory < meal plan requirement
        low_stock = await self._calculate_low_stock(user_id)

        # Estimate days remaining based on user's calorie needs
        # TODO: Create UserProfileRepository and replace this direct query
        # For now, keeping this query as UserProfile repository doesn't exist yet
        user_profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if user_profile and user_profile.goal_calories:
            days_remaining = int(nutritional_capacity['calories'] / user_profile.goal_calories) if user_profile.goal_calories > 0 else 0
        else:
            days_remaining = int(nutritional_capacity['calories'] / 2000) if nutritional_capacity['calories'] > 0 else 0

        # Generate AI recommendations
        recommendations = await self._generate_recommendations(
            inventory,
            expiring_soon,
            categories,
            nutritional_capacity,
            days_remaining,
            user_id,
            expired_items
        )

        return {
            "total_items": total_items,
            "total_weight_g": total_weight,
            "expiring_soon": expiring_soon,
            "expired_items": expired_items,
            "low_stock": low_stock,
            "categories": categories,
            "nutritional_capacity": nutritional_capacity,
            "estimated_days_remaining": days_remaining,
            "ai_recommendations": recommendations
        }

    async def _calculate_low_stock(self, user_id: int) -> List[Dict]:
        """
        Calculate low stock items by comparing current inventory against
        the active meal plan's ingredient requirements.
        Reuses GroceryService.calculate_for_plan() — same logic as the shopping list.
        """
        if not self.meal_plan_repo:
            return []

        active_plan = await self.meal_plan_repo.get_active_plan(user_id)
        if not active_plan or not active_plan.plan_data:
            return []

        grocery_result = await self.grocery_service.calculate_for_plan(
            active_plan.plan_data, user_id
        )

        low_stock = []
        for item_data in grocery_result.get("items", {}).values():
            if item_data["to_buy"] > 0:
                low_stock.append({
                    'item': item_data["item_name"],
                    'quantity': item_data["quantity_available"],
                    'needed': item_data["quantity_needed"],
                    'shortage': item_data["to_buy"]
                })

        return low_stock

    async def get_inventory_items(
        self,
        user_id: int,
        category: Optional[str] = None,
        low_stock_only: bool = False,
        expiring_soon: bool = False
    ) -> Dict:

        if expiring_soon:
            inventory_items = await self.inventory_repo.get_expiring_items(
                user_id=user_id,
                days_threshold=3
            )
        elif low_stock_only:
            inventory_items = await self.inventory_repo.get_low_stock_items(
                user_id=user_id,
                threshold_grams=100
            )
        else:
            inventory_items = await self.inventory_repo.get_all_for_user(
                user_id=user_id,
                include_zero_quantity=False
            )

        items = []
        for inv in inventory_items:
            item = inv.item

            if not item:
                continue

            if category and item.category != category:
                continue

            expiry = DateTimeHelper.ensure_utc(inv.expiry_date) if inv.expiry_date else None
            days_until_expiry = DateTimeHelper.days_until(expiry)


            is_depleted = self._is_item_depleted(inv.quantity_grams)

            items.append({
                "id": inv.id,
                "item_id": item.id,
                "item_name": item.canonical_name,
                "category": item.category,
                "quantity_grams": inv.quantity_grams,
                "expiry_date": inv.expiry_date.isoformat() if inv.expiry_date else None,
                "days_until_expiry": days_until_expiry,
                "is_depleted": is_depleted
            })

        return {
            "count": len(items),
            "items": items
        }

    def _is_item_depleted(self, quantity_grams: float) -> bool:

        return (quantity_grams or 0) <= 0

    async def get_user_inventory(self, user_id: int, category: str = None, low_stock_only: bool = False, expiring_soon: bool = False):

        query = self.db.query(UserInventory).filter(UserInventory.user_id == user_id)

        if low_stock_only:
            query = query.filter(UserInventory.quantity_grams < 100)

        if expiring_soon:
            three_days_later = DateTimeHelper.now_utc() + timedelta(days=3)
            query = query.filter(UserInventory.expiry_date <= three_days_later)

        inventory_items = query.all()

        items = []
        for inv in inventory_items:
            item = self.db.query(Item).filter(Item.id == inv.item_id).first()
            if category and item.category != category:
                continue

            days_until_expiry = None
            if inv.expiry_date:
                expiry = DateTimeHelper.ensure_utc(inv.expiry_date)
                days_until_expiry = (expiry - DateTimeHelper.now_utc()).days if expiry else None

            items.append({
                "id": inv.id,
                "item_id": item.id,
                "item_name": item.canonical_name,
                "category": item.category,
                "quantity_grams": inv.quantity_grams,
                "expiry_date": inv.expiry_date.isoformat() if inv.expiry_date else None,
                "days_until_expiry": days_until_expiry
            })

        return {"count": len(items), "items": items}

    async def _generate_recommendations(
        self,
        inventory: List[UserInventory],
        expiring_soon: List[Dict],
        categories: Dict,
        nutritional_capacity: Dict,
        days_remaining: int,
        user_id: int = 0,
        expired_items: List[Dict] = None
    ) -> List[str]:
        """Generate inventory recommendations. Uses AI with hardcoded fallback."""
        # Try AI recommendations
        if self.llm_orchestrator and user_id:
            try:
                from app.schemas.recommendation import RecommendationResponse
                expiring_json = [{"item": i["item"], "expires_in_days": i.get("expires_in_days", "?")} for i in expiring_soon[:5]]
                expired_json = [{"item": i["item"], "expired_days_ago": i.get("expired_days_ago", "?")} for i in (expired_items or [])[:5]]
                # Build full inventory item list for better AI context
                inventory_items_json = []
                for inv in inventory[:20]:  # Limit to 20 items for prompt size
                    if inv.item:
                        inventory_items_json.append({
                            "name": inv.item.canonical_name,
                            "category": inv.item.category or "other",
                            "quantity_g": round(inv.quantity_grams or 0, 0)
                        })
                result = await self.llm_orchestrator.run(
                    user_id=user_id,
                    slug="inventory_status_recommendations",
                    variables={
                        "total_items": len(inventory),
                        "days_remaining": days_remaining,
                        "protein_g": round(nutritional_capacity.get("protein_g", 0), 1),
                        "categories_json": json.dumps(categories),
                        "expiring_items_json": json.dumps(expiring_json),
                        "expired_items_json": json.dumps(expired_json),
                        "inventory_items_json": json.dumps(inventory_items_json),
                    },
                    response_model=RecommendationResponse
                )
                return result.recommendations
            except (TokenBudgetExceeded, Exception) as e:
                logger.warning(f"AI inventory recommendations unavailable ({type(e).__name__}), using fallback")

        # Fallback: hardcoded logic
        recommendations = []

        if expired_items:
            expired_str = ', '.join([item['item'] for item in expired_items[:3]])
            recommendations.append(f"Discard expired items: {expired_str}")
        if expiring_soon:
            items_str = ', '.join([item['item'] for item in expiring_soon[:3]])
            recommendations.append(f"Use soon: {items_str}")
        if len(categories) < 3:
            recommendations.append("Add more variety - you're missing key food groups")
        if nutritional_capacity['protein_g'] < 200:
            recommendations.append("Low protein stock - consider adding chicken, paneer, or lentils")
        if days_remaining < 3:
            recommendations.append(f"Only {days_remaining} days of food remaining - time to shop!")
        elif days_remaining > 14:
            recommendations.append("Well stocked! You have plenty of food")
        if 'vegetables' not in categories or categories.get('vegetables', 0) < 3:
            recommendations.append("Add more vegetables for balanced nutrition")
        if 'protein' not in categories:
            recommendations.append("No protein sources found - essential for your goals")

        return recommendations if recommendations else ["Inventory looks good!"]

    async def check_recipe_availability(self, user_id: int, recipe_id: int) -> Dict:

        recipe = self.recipe_repo.get_by_id(recipe_id)
        if not recipe:
            return {'available': False, 'reason': 'Recipe not found'}

        ingredients = self.recipe_repo.get_ingredients_by_recipe_id(recipe_id)

        if not ingredients:
            return {
                'recipe': recipe.title,
                'can_make': False,
                'reason': 'Recipe has no ingredients',
                'missing_items': [],
                'insufficient_items': [],
                'available_items': [],
                'coverage_percentage': 0
            }

        user_inventory_list = await self.inventory_repo.get_all_for_user(
            user_id=user_id,
            include_zero_quantity=False
        )

        inventory_lookup = {inv.item_id: inv for inv in user_inventory_list}

        availability = {
            'recipe': recipe.title,
            'can_make': True,
            'missing_items': [],
            'insufficient_items': [],
            'available_items': [],
            'coverage_percentage': 0
        }

        total_ingredients = 0
        available_count = 0

        for ingredient in ingredients:
            if ingredient.is_optional:
                continue

            total_ingredients += 1

            inventory_item = inventory_lookup.get(ingredient.item_id)

            item = ingredient.item

            if not inventory_item:
                availability['missing_items'].append({
                    'item': item.canonical_name,
                    'required': ingredient.quantity_grams
                })
                availability['can_make'] = False
            elif inventory_item.quantity_grams < ingredient.quantity_grams:
                availability['insufficient_items'].append({
                    'item': item.canonical_name,
                    'required': ingredient.quantity_grams,
                    'available': inventory_item.quantity_grams,
                    'shortage': ingredient.quantity_grams - inventory_item.quantity_grams
                })
                availability['can_make'] = False
            else:
                availability['available_items'].append({
                    'item': item.canonical_name,
                    'required': ingredient.quantity_grams,
                    'available': inventory_item.quantity_grams
                })
                available_count += 1

        availability['coverage_percentage'] = (available_count / total_ingredients * 100) if total_ingredients > 0 else 0

        return availability

    async def get_makeable_recipes(
        self,
        user_id: int,
        limit: int = 10,
        partial_threshold: float = 80.0
    ) -> Dict[str, List[Dict]]:

        inventory_items = await self.inventory_repo.get_all_for_user(
            user_id=user_id,
            include_zero_quantity=False
        )

        if not inventory_items:
            return {'fully_makeable': [], 'partially_makeable': []}

        user_item_quantities = {
            inv.item_id: inv.quantity_grams
            for inv in inventory_items
        }

        candidates = await self.recipe_repo.get_makeable_recipe_candidates(
            user_item_quantities=user_item_quantities,
            min_match_pct=partial_threshold,
            limit=limit * 2
        )

        fully_makeable = []
        partially_makeable = []

        for candidate in candidates:
            recipe = candidate['recipe']
            match_pct = candidate['match_percentage']

            recipe_data = {
                'recipe_id': recipe.id,
                'recipe_name': recipe.title,
                'description': recipe.description,
                'prep_time_minutes': recipe.prep_time_min,
                'servings': recipe.servings,
                'available_ingredients': candidate['available_count'],
                'total_ingredients': candidate['total_count'],
                'available_ingredient_names': candidate['available_items'],
                'match_percentage': match_pct,
                'macros': recipe.macros_per_serving,
                'goals': recipe.goals
            }

            if match_pct == 100.0:

                fully_makeable.append(recipe_data)
            else:
                recipe_data['missing_ingredient_names'] = candidate['missing_items']
                partially_makeable.append(recipe_data)

            if len(fully_makeable) >= limit and len(partially_makeable) >= limit:
                break

        fully_makeable.sort(key=lambda x: x.get('prep_time_minutes', 999))
        partially_makeable.sort(
            key=lambda x: (-x.get('match_percentage', 0), x.get('prep_time_minutes', 999))
        )

        return {
            'fully_makeable': fully_makeable[:limit],
            'partially_makeable': partially_makeable[:limit]
        }

    async def process_receipt_items(
        self,
        user_id: int,
        receipt_items: List[Dict],
        auto_add_threshold: float = 0.75
    ) -> Dict:

        try:
            normalized_results = await self.normalizer.process_extracted_items(receipt_items)

            auto_added = []
            needs_confirmation = []

            for result in normalized_results:

                if not result.get('success'):
                    needs_confirmation.append(result)
                    logger.info(f"Failed to normalize: {result.get('error', 'Unknown error')}")
                    continue

                item_id = result['item_id']
                item_name = result['item_name']
                quantity_grams = result['quantity_grams']
                confidence = result.get('confidence', 0.0)


                if confidence >= auto_add_threshold:
                    try:
                        inventory_item = await self._add_to_inventory(
                            user_id=user_id,
                            item_id=item_id,
                            quantity_grams=quantity_grams,
                            expiry_days=None,
                            source="receipt"
                        )
                        auto_added.append(result)
                        logger.info(f"Auto-added: {item_name} ({quantity_grams}g)")
                    except Exception as e:
                        logger.error(f"Failed to add {item_name} to inventory: {str(e)}")
                        needs_confirmation.append(result)
                else:
                    needs_confirmation.append(result)
                    logger.info(f"Needs confirmation: {item_name} (confidence: {confidence:.2f})")


            self.db.commit()
            logger.info(f"✅ Transaction committed - {len(auto_added)} items saved to inventory")

            return {
                "auto_added": auto_added,
                "needs_confirmation": needs_confirmation
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Transaction rolled back due to error: {str(e)}")
            logger.error(f"Error processing receipt items: {str(e)}")
            raise

    async def generate_ai_recipes(self, user_id: int, mode: str = "goal_adherent") -> Dict:
        """
        Generate creative AI recipe suggestions from current inventory.

        Args:
            user_id: User ID
            mode: 'goal_adherent' or 'guilt_free'

        Returns:
            Dict with recipes list and metadata
        """
        if not self.llm_orchestrator:
            return {"recipes": [], "message": "AI recipe generation unavailable"}

        try:
            # Get inventory items (non-zero, non-expired)
            inventory_items = await self.inventory_repo.get_all_for_user(
                user_id=user_id,
                include_zero_quantity=False
            )

            if not inventory_items:
                return {"recipes": [], "message": "No items in inventory"}

            now = DateTimeHelper.now_utc()
            available_items = []
            for inv in inventory_items:
                if not inv.item:
                    continue
                # Skip expired items
                if inv.expiry_date:
                    expiry = DateTimeHelper.ensure_utc(inv.expiry_date)
                    if expiry < now:
                        continue
                available_items.append({
                    "name": inv.item.canonical_name,
                    "category": inv.item.category or "other",
                    "quantity_g": round(inv.quantity_grams, 0)
                })

            if not available_items:
                return {"recipes": [], "message": "No usable items in inventory"}

            # Get user goals
            goal_type = "general health"
            calorie_target = 2000
            protein_target = 150

            if self.user_profile_repo:
                profile = await self.user_profile_repo.get_profile(user_id)
                goal = await self.user_profile_repo.get_active_goal(user_id)
                if profile:
                    calorie_target = getattr(profile, 'goal_calories', None) or calorie_target
                    protein_target = getattr(profile, 'goal_protein', None) or protein_target
                if goal:
                    goal_type = getattr(goal, 'goal_type', None) or goal_type

            from app.schemas.recommendation import AIRecipeResponse
            result = await self.llm_orchestrator.run(
                user_id=user_id,
                slug="ai_creative_recipes",
                variables={
                    "mode": mode,
                    "goal_type": goal_type,
                    "calorie_target": calorie_target,
                    "protein_target": protein_target,
                    "available_items_json": json.dumps(available_items),
                },
                response_model=AIRecipeResponse
            )

            # Fire-and-forget: seed valid AI recipes to DB in background
            if result.recipes:
                asyncio.create_task(
                    self._seed_ai_recipes_to_db(result.recipes)
                )

            return {
                "recipes": [r.model_dump() for r in result.recipes],
                "mode": mode,
                "items_available": len(available_items),
            }

        except (TokenBudgetExceeded, Exception) as e:
            logger.warning(f"AI recipe generation failed ({type(e).__name__}): {e}")
            return {"recipes": [], "message": "AI recipe generation unavailable"}

    async def _seed_ai_recipes_to_db(self, recipes) -> None:
        """
        Background task: persist AI-generated recipes to the recipes table.
        Uses embedding cosine-similarity (threshold 0.92) to block near-duplicates.
        Generates and stores embeddings for every newly seeded recipe.
        """
        if not self.embedding_adapter:
            logger.warning("[AIRecipeSeed] No embedding adapter — skipping seeding.")
            return

        import numpy as np
        from app.repositories.recipe_repository import RecipeRepository

        SIMILARITY_THRESHOLD = 0.92

        db: Session = SessionLocal()
        try:
            repo = RecipeRepository(db)

            # Load existing titles + embeddings via repo
            existing = await repo.get_titles_and_embeddings()
            existing_titles = {title for title, _ in existing}
            existing_vecs = []
            for _, emb_str in existing:
                if emb_str:
                    try:
                        existing_vecs.append(np.array(json.loads(emb_str), dtype=np.float32))
                    except Exception:
                        pass

            def _is_near_duplicate(vec: "np.ndarray") -> bool:
                if not existing_vecs:
                    return False
                matrix = np.stack(existing_vecs)
                norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(vec) + 1e-9
                return float((matrix @ vec / norms).max()) >= SIMILARITY_THRESHOLD

            def _embedding_text(s) -> str:
                parts = [s.name]
                if s.cuisine:
                    parts.append(s.cuisine)
                parts.extend(ing.name for ing in s.ingredients[:5])
                return " ".join(parts).lower().strip()

            # Filter exact-title duplicates before calling the embedding API
            candidates = [s for s in recipes if s.name not in existing_titles]
            if not candidates:
                logger.info("[AIRecipeSeed] All recipes already exist (exact title match).")
                return

            # Batch-generate embeddings for all candidates via the shared adapter
            texts = [_embedding_text(s) for s in candidates]
            raw_embeddings = await self.embedding_adapter.get_embeddings_batch(texts)
            candidate_vecs = [np.array(e, dtype=np.float32) for e in raw_embeddings]

            # Load item lookup via repo (single query)
            all_ingredient_names = {ing.name for s in candidates for ing in s.ingredients}
            items_by_name = await repo.get_items_by_canonical_names(list(all_ingredient_names))

            seeded = 0
            for suggestion, cand_vec in zip(candidates, candidate_vecs):
                if _is_near_duplicate(cand_vec):
                    logger.info(f"[AIRecipeSeed] Skipping near-duplicate: {suggestion.name!r}")
                    continue

                macros = {
                    "calories":  float(suggestion.estimated_calories),
                    "protein_g": float(suggestion.estimated_protein_g),
                    "carbs_g":   float(suggestion.estimated_carbs_g),
                    "fat_g":     float(suggestion.estimated_fat_g),
                    "fiber_g":   0.0,
                }
                embedding_str = await self.embedding_adapter.embedding_to_db_string(cand_vec.tolist())

                recipe = Recipe(
                    title=suggestion.name,
                    description=suggestion.description,
                    source="ai_generated",
                    cuisine=suggestion.cuisine,
                    goals=suggestion.goals,
                    dietary_tags=suggestion.dietary_tags,
                    suitable_meal_times=suggestion.suitable_meal_times,
                    prep_time_min=suggestion.estimated_prep_time_min,
                    cook_time_min=0,
                    difficulty_level=suggestion.difficulty,
                    servings=1,
                    macros_per_serving=macros,
                    instructions=suggestion.instructions,
                    embedding=embedding_str,
                )
                await repo.create_recipe(recipe)

                for ing in suggestion.ingredients:
                    item = items_by_name.get(ing.name)
                    if item:
                        await repo.add_recipe_ingredient(RecipeIngredient(
                            recipe_id=recipe.id,
                            item_id=item.id,
                            quantity_grams=float(ing.quantity_grams),
                            is_optional=False,
                        ))

                # Include in pool so subsequent candidates in this batch are checked
                existing_vecs.append(cand_vec)
                seeded += 1

            db.commit()
            if seeded:
                logger.info(f"[AIRecipeSeed] Seeded {seeded} AI-generated recipe(s) to DB.")
            else:
                logger.info("[AIRecipeSeed] No new recipes to seed (all near-duplicates).")
        except Exception as exc:
            db.rollback()
            logger.warning(f"[AIRecipeSeed] Background seeding failed: {exc}", exc_info=True)
        finally:
            db.close()

    async def delete_inventory_item(self, user_id: int, inventory_id: int) -> bool:

        try:
            deleted = await self.inventory_repo.delete(
                inventory_id=inventory_id,
                user_id=user_id
            )

            if deleted:
                self.db.commit()
                logger.info(f"Deleted inventory {inventory_id} for user {user_id}")
            else:
                logger.warning(f"Inventory {inventory_id} not found for user {user_id}")

            return deleted

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting inventory {inventory_id}: {e}")
            raise
