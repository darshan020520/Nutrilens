#/backend/services/inventory.py
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.database import UserInventory, Item, User, MealLog, UserProfile
# Legacy normalizer (kept for backward compatibility)
# from app.services.item_normalizer import IntelligentItemNormalizer, NormalizationResult

# NEW: Clean architecture normalizer with batch processing
# RAGItemNormalizer replaced with BatchNormalizer (from infrastructure layer)
from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.infrastructure.normalization.batch.batch_normalizer import BatchNormalizer
import logging
from dataclasses import dataclass

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
    """
    Smart inventory management that enables AI meal planning
    This service is the bridge between raw inventory and intelligent decisions
    """

    # Default shelf life by category (in days)
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
        'default': 14  # 2 weeks for uncategorized items
    }

    def __init__(
        self,
        inventory_repo: IInventoryRepository,
        recipe_repo:  IRecipeRepository,
        normalizer: BatchNormalizer,  # BatchNormalizer from infrastructure layer
        item_repo,  # ItemRepository from infrastructure layer
        db: Session
    ):
        self.inventory_repo = inventory_repo
        self.recipe_repo = recipe_repo
        self.normalizer = normalizer
        self.item_repo = item_repo
        self.db = db

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
        """
        Add item to inventory - PUBLIC METHOD
        Uses _add_to_inventory for consistent expiry date handling and batch management
        """
        try:
            # ✅ Get the item using repository
            item = await self.item_repo.get_item_by_id(item_id)
            if not item:
                return {"success": False, "error": "Item not found"}

            # Calculate expiry_days if expiry_date is provided
            expiry_days = None
            if expiry_date:
                expiry_days = (expiry_date - datetime.now(timezone.utc)).days

            # Use _add_to_inventory which handles expiry dates and batch management
            await self._add_to_inventory(
                user_id=user_id,
                item_id=item_id,
                quantity_grams=quantity_grams,
                expiry_days=expiry_days,
                source=source
            )

            self.db.commit()

            # ✅ Get total remaining quantity across all batches using repository
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

    async def deduct_item(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float
    ) -> Dict:
        """
        Deduct item from inventory - PUBLIC METHOD for tracking agent
        """
        try:
            # Find item in inventory
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

            # Get item details
            item = self.db.query(Item).filter(Item.id == item_id).first()

            if inventory_item.quantity_grams < quantity_grams:
                # Not enough quantity
                deducted = inventory_item.quantity_grams
                inventory_item.quantity_grams = 0
                warning = f"Only {deducted}g available, deducted all"
            else:
                # Normal deduction
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
        """
        Process text input (like receipt) and add to inventory
        Returns detailed results for user confirmation

        Transaction Management: Commits all successful items in a single transaction
        """
        logger.info("INVENTORY SERVICE: add_items_from_text() called")
        logger.info(f"User ID: {user_id}")

        # Split and filter empty lines
        lines = [line.strip() for line in text_input.strip().split('\n') if line.strip()]
        logger.info(f"Processing {len(lines)} lines in batch")

        results = {
            'successful': [],
            'needs_confirmation': [],
            'failed': [],
            'summary': {}
        }

        if not lines:
            logger.warning("No lines to process")
            return results

        try:
            # Process all lines in single batch (major optimization)
            logger.info("Calling normalizer.process_batch()...")
            batch_results = await self.normalizer.process_batch(lines)

            # Process results
            for idx, result in enumerate(batch_results):
                line = result.get('input', lines[idx])

                logger.info(f"\n{'='*60}")
                logger.info(f"Processing result {idx+1}/{len(batch_results)}: '{line}'")

                if not result.get('success'):
                    # Check if this is an unknown item detection
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

                    # Regular failure
                    logger.info(f"FAILED - {result.get('error', 'Unknown error')}")
                    results['failed'].append({
                        'original': line,
                        'reason': result.get('error', 'Could not normalize item'),
                        'suggestions': []
                    })
                    continue

                # Extract normalized data
                item_id = result['item_id']
                item_name = result['item_name']
                quantity_grams = result['quantity_grams']
                confidence = result.get('confidence', 0.0)
                match_strategy = result.get('match_strategy', 'unknown')

                logger.info(f"Normalization result:")
                logger.info(f"   - Item: {item_name}")
                logger.info(f"   - Item ID: {item_id}")
                logger.info(f"   - Confidence: {confidence:.3f}")
                logger.info(f"   - Strategy: {match_strategy}")
                logger.info(f"   - Quantity: {result['original_quantity']} {result['original_unit']}")
                logger.info(f"   - Quantity in grams: {quantity_grams}")

                # Route based on confidence
                if confidence >= 0.85:
                    # High confidence - auto add
                    logger.info(f"HIGH CONFIDENCE (>=0.85) - Auto-adding to inventory")

                    try:
                        # ✅ Per-item error handling - continue processing other items if one fails
                        inventory_item = await self._add_to_inventory(
                            user_id,
                            item_id,
                            quantity_grams
                        )
                        logger.info(f"Added: {item_name} ({inventory_item.quantity_grams}g)")

                        results['successful'].append({
                            'original': line,
                            'matched': item_name,
                            'quantity': f"{inventory_item.quantity_grams}g",
                            'confidence': confidence
                        })

                    except Exception as e:
                        logger.error(f"Failed to add {item_name}: {str(e)}")
                        results['failed'].append({
                            'original': line,
                            'reason': f"Failed to add to inventory: {str(e)}",
                            'suggestions': []
                        })
                        # ✅ Continue processing other items

                elif confidence >= 0.6:
                    # Medium confidence - needs confirmation
                    logger.info(f"MEDIUM CONFIDENCE (0.6-0.84) - Needs confirmation")

                    results['needs_confirmation'].append({
                        'original': line,
                        'item_id': item_id,
                        'suggested': item_name,
                        'quantity': result['original_quantity'],
                        'unit': result['original_unit'],
                        'alternatives': [],  # TODO: Add alternatives from vector search
                        'confidence': confidence
                    })
                else:
                    # Low confidence - needs user selection
                    logger.info(f"LOW CONFIDENCE (<0.6) - Needs user selection")

                    results['needs_confirmation'].append({
                        'original': line,
                        'item_id': item_id,
                        'suggested': item_name,
                        'quantity_grams': quantity_grams,
                        'suggestions': [],  # TODO: Add suggestions from vector search
                        'confidence': confidence
                    })

            # Generate summary
            results['summary'] = {
                'total_processed': len(lines),
                'successful': len(results['successful']),
                'needs_confirmation': len(results['needs_confirmation']),
                'failed': len(results['failed']),
                'success_rate': len(results['successful']) / len(lines) if lines else 0
            }

            # ✅ SINGLE COMMIT - All successful items committed together
            self.db.commit()
            logger.info(f"✅ Transaction committed - {len(results['successful'])} items saved")

        except Exception as e:
            # ✅ ROLLBACK on catastrophic error
            self.db.rollback()
            logger.error(f"❌ Transaction rolled back due to error: {str(e)}")
            logger.exception("Full traceback:")
            raise

        logger.info(f"\n{'='*60}")
        logger.info("INVENTORY SERVICE: Complete")
        logger.info(f"Summary: {results['summary']}")

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

        # ✅ DATA ACCESS: Get item via ItemRepository
        item = await self.item_repo.get_item_by_id(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        # ✅ BUSINESS LOGIC: Calculate expiry date based on category
        if expiry_days is None:
            expiry_days = self._get_default_expiry_days(item)
            logger.info(f"   Auto-assigned expiry: {expiry_days} days (category: {item.category})")

        new_expiry_date = datetime.now(timezone.utc) + timedelta(days=expiry_days)  # ✅ UTC

        # ✅ DATA ACCESS: Get all existing inventory records for this item (ordered newest first)
        existing_inventory = await self.inventory_repo.get_all_inventory_for_item(
            user_id=user_id,
            item_id=item_id,
            order_by_expiry_desc=True  # ✅ Newest first for merging with latest
        )

        # ✅ BUSINESS LOGIC: Find matching record (2-day threshold)
        matching_record = None
        for inv in existing_inventory:
            if inv.expiry_date:
                days_diff = abs((inv.expiry_date - new_expiry_date).days)
                if days_diff <= 2:  # ✅ BUSINESS RULE: 2-day threshold
                    matching_record = inv
                    break  # ✅ First match = latest record (due to DESC order)

        # ✅ BUSINESS DECISION: Merge or create?
        if matching_record:
            # Merge with existing record
            logger.info(f"   Merging with existing record (expiry: {matching_record.expiry_date.date()})")
            logger.info(f"   Current: {matching_record.quantity_grams}g -> New: {matching_record.quantity_grams + quantity_grams}g")

            # ✅ DATA ACCESS: Update via repository
            matching_record.quantity_grams += quantity_grams
            matching_record.last_updated = datetime.now(timezone.utc)  # ✅ UTC - Service sets this
            inventory_item = await self.inventory_repo.update(matching_record)
        else:
            # Create new record
            logger.info(f"   Creating new record (expiry: {new_expiry_date.date()})")

            # ✅ DATA ACCESS: Create via repository
            inventory_item = UserInventory(
                user_id=user_id,
                item_id=item_id,
                quantity_grams=quantity_grams,
                purchase_date=datetime.now(timezone.utc),  # ✅ UTC
                expiry_date=new_expiry_date,
                source=source,
                last_updated=datetime.now(timezone.utc)  # ✅ UTC - Set initial value
            )
            inventory_item = await self.inventory_repo.create(inventory_item)

        # ✅ NO COMMIT - Caller (add_items_from_text) will commit
        logger.info(f"   Added to inventory (pending commit) - Quantity: {inventory_item.quantity_grams}g")
        return inventory_item

    async def deduct_for_meal(
        self,
        user_id: int,
        recipe_id: int,
        portion_multiplier: float = 1.0
    ) -> Dict:
        """
        Intelligently deduct ingredients when a meal is consumed.

        Clean Architecture V2:
        - Uses RecipeRepository for recipe ingredient queries (line 436)
        - Uses InventoryRepository for inventory queries (line 450)
        - Uses DateTimeHelper for UTC-aware datetime (line 474)

        Args:
            user_id: User ID
            recipe_id: Recipe ID
            portion_multiplier: Recipe portion multiplier (default: 1.0)

        Returns:
            Dict with deductions, warnings, and success status
        """
        from app.core.datetime_utils import DateTimeHelper

        # ✅ FIXED VIOLATION 1: Use RecipeRepository instead of direct DB query
        ingredients = self.recipe_repo.get_ingredients_by_recipe_id(recipe_id)

        deductions = []
        warnings = []

        for ingredient in ingredients:
            if ingredient.is_optional:
                continue

            required_amount = ingredient.quantity_grams * portion_multiplier

            # ✅ FIXED VIOLATION 2: Use InventoryRepository instead of direct DB query
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
                # Deduct what's available
                deducted = inventory_item.quantity_grams
                inventory_item.quantity_grams = 0
            else:
                # Normal deduction
                inventory_item.quantity_grams -= required_amount
                deducted = required_amount

            # ✅ FIXED VIOLATION 3: Use DateTimeHelper.now_utc() instead of datetime.now()
            inventory_item.last_updated = DateTimeHelper.now_utc()

            deductions.append({
                'item': ingredient.item.canonical_name,
                'deducted': deducted,
                'remaining': inventory_item.quantity_grams
            })

            # ✅ BUSINESS RULE: Low stock threshold (50g)
            if inventory_item.quantity_grams < 50:
                warnings.append(f"{ingredient.item.canonical_name} is running low")

        self.db.commit()

        return {
            'deductions': deductions,
            'warnings': warnings,
            'success': len(warnings) == 0
        }

    async def get_inventory_status(self, user_id: int) -> Dict:
        """
        Get comprehensive inventory status for AI decision making
        This is what the AI agents will use to make intelligent decisions

        Clean Architecture:
        - Uses InventoryRepository for data access
        - Repository handles eager loading optimization
        """
        # ✅ Use repository instead of direct DB query
        inventory = await self.inventory_repo.get_all_for_user(
            user_id=user_id,
            include_zero_quantity=True  # Include all items for comprehensive analytics
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

        # Calculate totals
        total_items = len(inventory)
        total_weight = sum(item.quantity_grams for item in inventory)

        # OPTIMIZATION: Single loop processes all data (was 3 separate loops)
        expiring_soon = []
        low_stock = []
        categories = {}
        nutritional_capacity = {
            'calories': 0,
            'protein_g': 0,
            'carbs_g': 0,
            'fat_g': 0
        }

        from app.core.datetime_utils import DateTimeHelper
        three_days_later = DateTimeHelper.now_utc() + timedelta(days=3)  # ✅ UTC-aware

        for inv_item in inventory:
            # Item already loaded via joinedload - NO additional query!
            item = inv_item.item

            if not item:
                continue

            # Find expiring items
            if inv_item.expiry_date and inv_item.expiry_date <= three_days_later:
                expiring_soon.append({
                    'item': item.canonical_name,
                    'quantity': inv_item.quantity_grams,
                    'expires_in_days': DateTimeHelper.days_until(inv_item.expiry_date)  # ✅ UTC-aware
                })

            # Find low stock items
            if inv_item.quantity_grams < 100:
                low_stock.append({
                    'item': item.canonical_name,
                    'quantity': inv_item.quantity_grams
                })

            # Category analysis
            category = item.category or 'uncategorized'
            categories[category] = categories.get(category, 0) + 1

            # Nutritional capacity
            if item.nutrition_per_100g:
                factor = inv_item.quantity_grams / 100
                for nutrient in nutritional_capacity:
                    if nutrient in item.nutrition_per_100g:
                        nutritional_capacity[nutrient] += item.nutrition_per_100g[nutrient] * factor

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
            days_remaining
        )

        return {
            "total_items": total_items,
            "total_weight_g": total_weight,
            "expiring_soon": expiring_soon,
            "low_stock": low_stock,
            "categories": categories,
            "nutritional_capacity": nutritional_capacity,
            "estimated_days_remaining": days_remaining,
            "ai_recommendations": recommendations
        }

    async def get_inventory_items(
        self,
        user_id: int,
        category: Optional[str] = None,
        low_stock_only: bool = False,
        expiring_soon: bool = False
    ) -> Dict:
        """
        Get user's inventory items with filters and formatting.

        This is the service layer method for the GET /items API endpoint.

        Business Logic:
        - Fetches inventory based on filters (expiring, low stock, or all)
        - Filters by category if specified
        - Calculates days until expiry (UTC-aware)
        - Determines if item is depleted
        - Formats response for API consumption

        Clean Architecture:
        - Uses InventoryRepository for data access
        - Contains business logic (filtering, calculations)
        - Returns formatted dict ready for API response

        Args:
            user_id: User ID
            category: Optional category filter (e.g., 'fruit', 'protein')
            low_stock_only: If True, return only items below threshold
            expiring_soon: If True, return only items expiring within 3 days

        Returns:
            {
                "count": int,
                "items": [
                    {
                        "id": int,
                        "item_id": int,
                        "item_name": str,
                        "category": str,
                        "quantity_grams": float,
                        "expiry_date": str (ISO format) or None,
                        "days_until_expiry": int or None,
                        "is_depleted": bool
                    },
                    ...
                ]
            }
        """
        from app.core.datetime_utils import DateTimeHelper

        # ✅ STEP 1: Fetch data using repository based on filters
        if expiring_soon:
            inventory_items = await self.inventory_repo.get_expiring_items(
                user_id=user_id,
                days_threshold=3  # Business rule: 3 days = "expiring soon"
            )
        elif low_stock_only:
            inventory_items = await self.inventory_repo.get_low_stock_items(
                user_id=user_id,
                threshold_grams=100  # Business rule: < 100g = "low stock"
            )
        else:
            inventory_items = await self.inventory_repo.get_all_for_user(
                user_id=user_id,
                include_zero_quantity=False  # Business rule: exclude empty items
            )

        # ✅ STEP 2: Process and format items with business logic
        items = []
        for inv in inventory_items:
            # Item relationship is eager-loaded by repository
            item = inv.item

            # Skip if item relation is missing
            if not item:
                continue

            # ✅ BUSINESS LOGIC: Category filtering
            if category and item.category != category:
                continue

            # ✅ BUSINESS LOGIC: Calculate days until expiry (UTC-aware)
            days_until_expiry = DateTimeHelper.days_until(inv.expiry_date)

            # ✅ BUSINESS LOGIC: Determine if item is depleted
            is_depleted = self._is_item_depleted(inv.quantity_grams)

            # Format response item
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
        """
        Business rule: Determine if an inventory item is depleted.

        An item is considered depleted if quantity is zero or None.

        Args:
            quantity_grams: Item quantity in grams

        Returns:
            True if depleted, False otherwise
        """
        return (quantity_grams or 0) <= 0

    async def get_user_inventory(self, user_id: int, category: str = None, low_stock_only: bool = False, expiring_soon: bool = False):
        """Fetch inventory items for a specific user with optional filters."""
        query = self.db.query(UserInventory).filter(UserInventory.user_id == user_id)

        if low_stock_only:
            query = query.filter(UserInventory.quantity_grams < 100)

        if expiring_soon:
            three_days_later = datetime.now() + timedelta(days=3)
            query = query.filter(UserInventory.expiry_date <= three_days_later)

        inventory_items = query.all()

        items = []
        for inv in inventory_items:
            item = self.db.query(Item).filter(Item.id == inv.item_id).first()
            if category and item.category != category:
                continue

            days_until_expiry = None
            if inv.expiry_date:
                days_until_expiry = (inv.expiry_date - datetime.now()).days

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
        days_remaining: int
    ) -> List[str]:
        """
        Generate intelligent recommendations based on inventory analysis
        This is where AI shines - providing actionable insights
        """
        recommendations = []

        # Expiry warnings
        if expiring_soon:
            items_str = ', '.join([item['item'] for item in expiring_soon[:3]])
            recommendations.append(f"Use soon: {items_str}")

        # Low diversity warning
        if len(categories) < 3:
            recommendations.append("Add more variety - you're missing key food groups")

        # Protein check
        if nutritional_capacity['protein_g'] < 200:
            recommendations.append("Low protein stock - consider adding chicken, paneer, or lentils")

        # Days remaining
        if days_remaining < 3:
            recommendations.append(f"Only {days_remaining} days of food remaining - time to shop!")
        elif days_remaining > 14:
            recommendations.append("Well stocked! You have plenty of food")

        # Category-specific
        if 'vegetables' not in categories or categories.get('vegetables', 0) < 3:
            recommendations.append("Add more vegetables for balanced nutrition")

        if 'protein' not in categories:
            recommendations.append("No protein sources found - essential for your goals")

        return recommendations if recommendations else ["Inventory looks good!"]

    async def check_recipe_availability(self, user_id: int, recipe_id: int) -> Dict:
        """
        Check if user has ingredients for a recipe.

        Queries: 3 total (recipe, ingredients, all_inventory)
        - Gets recipe by ID
        - Gets all ingredients with items eager-loaded
        - Fetches all user inventory once, then does in-memory lookups

        Args:
            user_id: User ID
            recipe_id: Recipe ID

        Returns:
            Dict with availability details (can_make, missing_items, etc.)
        """
        recipe = self.recipe_repo.get_by_id(recipe_id)
        if not recipe:
            return {'available': False, 'reason': 'Recipe not found'}

        ingredients = self.recipe_repo.get_ingredients_by_recipe_id(recipe_id)

        # Early exit: Recipe has no ingredients
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

        # Fetch ALL user inventory once (1 query instead of N queries in loop)
        user_inventory_list = await self.inventory_repo.get_all_for_user(
            user_id=user_id,
            include_zero_quantity=False
        )

        # Create lookup dict: {item_id: UserInventory} for O(1) access
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

            # O(1) in-memory lookup, no database query
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
        """
        Find recipes user can make with current inventory.

        Clean Architecture V2:
        - Uses InventoryRepository for inventory data (no direct DB queries)
        - Uses RecipeRepository for recipe matching logic
        - Service layer only orchestrates and formats responses

        Algorithm:
        1. Get user inventory from repository
        2. Get matching recipes from repository (quantity-aware!)
        3. Categorize as fully_makeable (100%) or partially_makeable (80-99%)
        4. Format and return

        Args:
            user_id: User ID
            limit: Maximum recipes per category
            partial_threshold: Minimum match percentage (default: 80%)

        Returns:
            {
                'fully_makeable': [recipe_data, ...],
                'partially_makeable': [recipe_data, ...]
            }
        """
        # ✅ STEP 1: Get user inventory using repository
        inventory_items = await self.inventory_repo.get_all_for_user(
            user_id=user_id,
            include_zero_quantity=False
        )

        if not inventory_items:
            return {'fully_makeable': [], 'partially_makeable': []}

        # Convert to dict for repository method
        user_item_quantities = {
            inv.item_id: inv.quantity_grams
            for inv in inventory_items
        }

        # ✅ STEP 2: Get matching recipes using repository
        # Repository does ALL the heavy lifting:
        # - SQL coarse filter (item overlap)
        # - Python fine filter (quantity validation)
        # - Returns only recipes meeting threshold
        candidates = self.recipe_repo.get_makeable_recipe_candidates(
            user_item_quantities=user_item_quantities,
            min_match_pct=partial_threshold,
            limit=limit * 2  # Get 2x for both categories
        )

        # ✅ STEP 3: Categorize and format results
        fully_makeable = []
        partially_makeable = []

        for candidate in candidates:
            recipe = candidate['recipe']
            match_pct = candidate['match_percentage']

            # Build response data (matches existing contract)
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

            # Categorize based on match percentage
            if match_pct == 100.0:
                # Fully makeable (100% match)
                fully_makeable.append(recipe_data)
            else:
                # Partially makeable (80-99% match)
                recipe_data['missing_ingredient_names'] = candidate['missing_items']
                partially_makeable.append(recipe_data)

            # Early exit if we have enough in both categories
            if len(fully_makeable) >= limit and len(partially_makeable) >= limit:
                break

        # ✅ STEP 4: Final sorting
        # Repository already sorted by match %, but we re-sort by prep time within categories
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
        """
        Process receipt items with LLM-enhanced normalizer
        This is the main method for receipt scanner integration

        Args:
            user_id: User ID
            receipt_items: Raw items from receipt scanner
                Example: [{"item_name": "Onion", "quantity": 2, "unit": "kg"}]
            auto_add_threshold: Confidence threshold for auto-adding (default: 0.75)

        Returns:
            {
                "auto_added": List of auto-added items,
                "needs_confirmation": List of items needing review
            }
        """
        try:
            # Use LLM-enhanced normalizer's batch processing for pre-extracted items
            normalized_results = await self.normalizer.process_extracted_items(receipt_items)

            # Categorize by confidence
            auto_added = []
            needs_confirmation = []

            for result in normalized_results:
                # Check if normalization was successful
                if not result.get('success'):
                    # Failed normalization - add to needs_confirmation
                    needs_confirmation.append(result)
                    logger.info(f"Failed to normalize: {result.get('error', 'Unknown error')}")
                    continue

                # Extract normalized data from Dict
                item_id = result['item_id']
                item_name = result['item_name']
                quantity_grams = result['quantity_grams']
                confidence = result.get('confidence', 0.0)

                logger.info(f"Normalized: {item_name} ({quantity_grams}g, confidence: {confidence:.2f})")

                # Route based on confidence threshold
                if confidence >= auto_add_threshold:
                    # High confidence - auto-add to inventory
                    try:
                        inventory_item = await self._add_to_inventory(
                            user_id=user_id,
                            item_id=item_id,
                            quantity_grams=quantity_grams,
                            expiry_days=None,  # None = auto-assign based on category
                            source="receipt"
                        )
                        auto_added.append(result)
                        logger.info(f"Auto-added: {item_name} ({quantity_grams}g)")
                    except Exception as e:
                        logger.error(f"Failed to add {item_name} to inventory: {str(e)}")
                        needs_confirmation.append(result)
                else:
                    # Low confidence - needs user confirmation
                    needs_confirmation.append(result)
                    logger.info(f"Needs confirmation: {item_name} (confidence: {confidence:.2f})")

            # ✅ COMMIT TRANSACTION - Save all auto-added items
            self.db.commit()
            logger.info(f"✅ Transaction committed - {len(auto_added)} items saved to inventory")

            return {
                "auto_added": auto_added,
                "needs_confirmation": needs_confirmation
            }

        except Exception as e:
            # ✅ ROLLBACK on error
            self.db.rollback()
            logger.error(f"❌ Transaction rolled back due to error: {str(e)}")
            logger.error(f"Error processing receipt items: {str(e)}")
            raise

    async def delete_inventory_item(self, user_id: int, inventory_id: int) -> bool:
        """
        Delete an inventory item.

        Handles transaction management (commit/rollback).

        Args:
            user_id: User ID (for ownership validation)
            inventory_id: Inventory item ID to delete

        Returns:
            True if deleted, False if not found or unauthorized

        Raises:
            Exception: If database operation fails
        """
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
