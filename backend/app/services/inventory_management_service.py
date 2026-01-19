"""
Inventory Management Service - Business logic for inventory operations.

This service handles:
- Comprehensive inventory status calculation
- Expiring items detection with consumption pattern analysis
- Restock list generation with smart recommendations
- Bulk inventory updates (add, deduct, set quantities)
- Inventory analytics and insights

Extracted from: backend/app/agents/tracking_agent.py:682-1311
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.models.database import MealLog, UserInventory, Item, Recipe, RecipeIngredient, User
from app.repositories.interfaces import IInventoryRepository, ITrackingRepository
from app.services.item_normalizer import IntelligentItemNormalizer
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class InventoryManagementService:
    """
    Service for managing inventory operations and analytics.

    Provides comprehensive inventory management including:
    - Status calculations with consumption pattern analysis
    - Expiry detection with smart filtering (date-based and consumption-based)
    - Restock recommendations combining upcoming meals and historical patterns
    - Bulk update operations with item normalization
    """

    def __init__(
        self,
        inventory_repo: IInventoryRepository,
        tracking_repo: ITrackingRepository,
        db: Session
    ):
        """
        Initialize InventoryManagementService with required repositories.

        Args:
            inventory_repo: Repository for inventory data access
            tracking_repo: Repository for meal log data access
            db: Database session (for complex queries not in repositories)
        """
        self.inventory_repo = inventory_repo
        self.tracking_repo = tracking_repo
        self.db = db

    async def calculate_inventory_status(self, user_id: int) -> Dict[str, Any]:
        """
        Calculate comprehensive inventory status with optimization.

        This method:
        1. Analyzes last 14 days of consumption patterns
        2. Calculates weekly requirements with 20% buffer
        3. Compares current stock vs requirements
        4. Categorizes items (critical, well-stocked)
        5. Generates actionable recommendations

        Source: backend/app/agents/tracking_agent.py:917-1098

        Args:
            user_id: User ID

        Returns:
            Dict: {
                "success": True,
                "overall_percentage": 65.5,
                "category_breakdown": {
                    "protein": {"average_percentage": 45.0, "total_items": 5, ...},
                    "vegetables": {"average_percentage": 80.0, "total_items": 8, ...}
                },
                "critical_items": [{"id": 123, "name": "Chicken", "percentage": 15.0, ...}],
                "well_stocked": [{"id": 456, "name": "Rice", "percentage": 95.0, ...}],
                "recommendations": ["Critical: Immediate grocery shopping required", ...],
                "total_items_tracked": 25,
                "items_in_stock": 18
            }
        """
        try:
            # Get user's consumption patterns (last 14 days for better average)
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)

            recent_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime >= two_weeks_ago,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()

            # Calculate required items for next 7 days based on consumption
            required_items = {}
            consumption_frequency = {}

            for log in recent_logs:
                try:
                    if not log.recipe:
                        continue

                    # Get recipe ingredients
                    ingredients = self.db.query(RecipeIngredient).options(
                        joinedload(RecipeIngredient.item)
                    ).filter(
                        RecipeIngredient.recipe_id == log.recipe_id
                    ).all()

                    portion_multiplier = log.portion_multiplier or 1.0

                    for ingredient in ingredients:
                        if not ingredient.item:
                            continue

                        item_id = ingredient.item_id
                        quantity = ingredient.quantity_grams * portion_multiplier

                        required_items[item_id] = required_items.get(item_id, 0) + quantity
                        consumption_frequency[item_id] = consumption_frequency.get(item_id, 0) + 1

                except Exception as e:
                    logger.warning(f"Error processing meal log {log.id} for inventory status: {str(e)}")
                    continue

            # Calculate weekly requirement with buffer
            days_of_data = min(14, len(set(log.consumed_datetime.date() for log in recent_logs if log.consumed_datetime)))
            if days_of_data == 0:
                days_of_data = 1  # Prevent division by zero

            weekly_multiplier = 7 / days_of_data

            for item_id in required_items:
                required_items[item_id] = required_items[item_id] * weekly_multiplier * 1.2  # 20% buffer

            # Get current inventory
            inventory_items = await self.inventory_repo.get_all_for_user(user_id, include_zero_quantity=False)

            current_inventory = {}
            for inv_item in inventory_items:
                if hasattr(inv_item, 'item') and inv_item.item:
                    current_inventory[inv_item.item_id] = inv_item.quantity_grams

            # Calculate status
            inventory_status = {
                "overall_percentage": 0,
                "category_breakdown": {},
                "critical_items": [],
                "low_stock_items": [],  # Added for v1 compatibility
                "well_stocked": [],
                "recommendations": [],
                "total_items_tracked": len(required_items),
                "items_in_stock": len(current_inventory)
            }

            if not required_items:
                inventory_status["recommendations"].append("No consumption data available for analysis")
                return {"success": True, **inventory_status}

            total_score = 0
            item_count = 0
            category_stats = {}

            for item_id, required_qty in required_items.items():
                try:
                    item = self.db.query(Item).filter(Item.id == item_id).first()
                    if not item:
                        continue

                    current_qty = current_inventory.get(item_id, 0)
                    percentage = min((current_qty / required_qty) * 100, 100) if required_qty > 0 else 100

                    item_info = {
                        "id": item_id,
                        "name": item.canonical_name,
                        "category": item.category or "other",
                        "required_weekly": round(required_qty, 1),
                        "available": round(current_qty, 1),
                        "percentage": round(percentage, 1),
                        "usage_frequency": consumption_frequency.get(item_id, 0),
                        "days_supply": round((current_qty / (required_qty / 7)), 1) if required_qty > 0 else 999
                    }

                    # Categorize items
                    if percentage < 20:
                        inventory_status["critical_items"].append(item_info)
                    elif 20 <= percentage < 50:
                        inventory_status["low_stock_items"].append(item_info)
                    elif percentage >= 80:
                        inventory_status["well_stocked"].append(item_info)

                    # Category breakdown
                    category = item.category or "other"
                    if category not in category_stats:
                        category_stats[category] = {"scores": [], "items": 0, "critical": 0}

                    category_stats[category]["scores"].append(percentage)
                    category_stats[category]["items"] += 1
                    if percentage < 20:
                        category_stats[category]["critical"] += 1

                    total_score += percentage
                    item_count += 1

                except Exception as e:
                    logger.warning(f"Error processing item {item_id} for status calculation: {str(e)}")
                    continue

            # Calculate overall percentage
            if item_count > 0:
                inventory_status["overall_percentage"] = round(total_score / item_count, 1)

            # Calculate category averages
            for category, stats in category_stats.items():
                if stats["scores"]:
                    avg_pct = sum(stats["scores"]) / len(stats["scores"])
                    inventory_status["category_breakdown"][category] = {
                        "average_percentage": round(avg_pct, 1),
                        "total_items": stats["items"],
                        "critical_items": stats["critical"],
                        "status": "critical" if stats["critical"] > stats["items"] * 0.5 else "low" if avg_pct < 50 else "good"
                    }

            # Generate recommendations
            overall_pct = inventory_status["overall_percentage"]
            if overall_pct < 30:
                inventory_status["recommendations"].append("Critical: Immediate grocery shopping required")
                inventory_status["recommendations"].append("Focus on protein and staple ingredients first")
            elif overall_pct < 50:
                inventory_status["recommendations"].append("Low inventory: Plan grocery shopping within 2 days")
            elif overall_pct < 70:
                inventory_status["recommendations"].append("Moderate inventory: Consider restocking staples")
            else:
                inventory_status["recommendations"].append("Good inventory levels maintained")

            # Add category-specific recommendations
            for category, data in inventory_status["category_breakdown"].items():
                if data["critical_items"] > 0:
                    inventory_status["recommendations"].append(
                        f"Urgent: Restock {category} items ({data['critical_items']} critical)"
                    )

            logger.info(f"Inventory status calculated for user {user_id}: {overall_pct}% overall")
            return {"success": True, **inventory_status}

        except Exception as e:
            logger.error(f"Error calculating inventory status: {str(e)}")
            return {"success": False, "error": f"Failed to calculate inventory status: {str(e)}"}

    async def check_expiring_items(
        self,
        user_id: int,
        filter_mode: str = "both",
        days_threshold: int = 3
    ) -> Dict[str, Any]:
        """
        Check for items nearing expiry with comprehensive validation.

        Three filter modes:
        1. date_only: Check expiry based on date alone
        2. consumption_only: Check if item won't be consumed before expiry (smart filtering)
        3. both: Combine date + consumption pattern filtering (default)

        Source: backend/app/agents/tracking_agent.py:682-821

        Args:
            user_id: User ID
            filter_mode: 'date_only', 'consumption_only', or 'both'
            days_threshold: Number of days ahead to check for expiry (default: 3)

        Returns:
            Dict: {
                "success": True,
                "expiring_count": 5,
                "expiring_items": [
                    {
                        "inventory_id": 123,
                        "item_name": "Milk",
                        "quantity_grams": 1000.0,
                        "expiry_date": "2025-11-28",
                        "days_remaining": 2,
                        "priority": "high",
                        "category": "dairy"
                    },
                    ...
                ],
                "recommendations": ["Use milk before Nov 28", ...],
                "recipe_suggestions": [...],
                "summary": {"urgent": 2, "high": 2, "medium": 1}
            }
        """
        try:
            expiry_threshold = datetime.utcnow() + timedelta(days=days_threshold)

            # Base query for all inventory items with expiry dates
            base_query = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.expiry_date.isnot(None)
                )
            )

            # Apply date filter based on mode
            if filter_mode in ["date_only", "both"]:
                inventory_items = base_query.filter(
                    UserInventory.expiry_date <= expiry_threshold
                ).all()
            else:
                # For consumption_only, get all items to check consumption patterns
                inventory_items = base_query.all()

            # Get upcoming meal plans if consumption filtering is needed
            upcoming_meals_by_item = {}
            if filter_mode in ["consumption_only", "both"]:
                upcoming_meals_by_item = await self._get_upcoming_consumption_patterns(
                    user_id, expiry_threshold
                )

            expiring_items = []

            for inv_item in inventory_items:
                try:
                    if not inv_item.item:
                        logger.warning(f"Inventory item {inv_item.id} missing item reference")
                        continue

                    if not inv_item.expiry_date:
                        continue

                    days_until_expiry = (inv_item.expiry_date - datetime.utcnow()).days

                    # Show items expiring soon OR already expired within last 30 days
                    expired_lookback_days = 30
                    if days_until_expiry < -expired_lookback_days:
                        continue  # Skip items expired more than 30 days ago

                    # Apply consumption pattern filter
                    if filter_mode == "consumption_only":
                        # Only include if item WON'T be consumed before expiry
                        item_id = inv_item.item.id
                        will_be_consumed = self._will_be_consumed_before_expiry(
                            item_id,
                            inv_item.expiry_date,
                            inv_item.quantity_grams,
                            upcoming_meals_by_item
                        )
                        if will_be_consumed:
                            continue  # Skip items that will be consumed

                    elif filter_mode == "both":
                        # Include if expires soon AND won't be consumed
                        item_id = inv_item.item.id
                        will_be_consumed = self._will_be_consumed_before_expiry(
                            item_id,
                            inv_item.expiry_date,
                            inv_item.quantity_grams,
                            upcoming_meals_by_item
                        )
                        # Only flag as expiring if it won't be used
                        if will_be_consumed:
                            continue

                    expiring_items.append({
                        "inventory_id": inv_item.id,
                        "item_id": inv_item.item.id,
                        "item_name": inv_item.item.canonical_name,
                        "quantity_grams": float(inv_item.quantity_grams),
                        "expiry_date": inv_item.expiry_date.isoformat(),
                        "days_remaining": days_until_expiry,
                        "priority": "urgent" if days_until_expiry <= 1 else "high" if days_until_expiry <= 2 else "medium",
                        "category": inv_item.item.category or "other",
                        "recipe_suggestions": []  # To be populated by recipe suggester
                    })

                except Exception as e:
                    logger.warning(f"Error processing inventory item {inv_item.id}: {str(e)}")
                    continue

            # Sort by urgency (expired first, then by days)
            expiring_items.sort(key=lambda x: (x["days_remaining"], x["item_name"]))

            urgent_items = [item for item in expiring_items if item["priority"] == "urgent"]
            if urgent_items:
                logger.info(f"Found {len(urgent_items)} urgent expiring items for user {user_id}")

            return {
                "success": True,
                "expiring_count": len(expiring_items),
                "expiring_items": expiring_items,
                "recommendations": self._generate_expiry_recommendations(expiring_items),
                "recipe_suggestions": [],  # Placeholder for future LLM-based recipe suggestions
                "summary": {
                    "urgent": len([i for i in expiring_items if i["priority"] == "urgent"]),
                    "high": len([i for i in expiring_items if i["priority"] == "high"]),
                    "medium": len([i for i in expiring_items if i["priority"] == "medium"])
                }
            }

        except Exception as e:
            logger.error(f"Error checking expiring items: {str(e)}")
            return {"success": False, "error": f"Failed to check expiring items: {str(e)}"}

    async def generate_restock_list(self, user_id: int) -> Dict[str, Any]:
        """
        Generate intelligent restock list combining upcoming meal needs and historical patterns.

        This method:
        1. Analyzes upcoming planned meals (next 7 days) - PRIORITY DATA
        2. Analyzes historical consumption (last 30 days) - TREND DATA
        3. Compares with current inventory
        4. Generates prioritized restock recommendations
        5. Identifies bulk buying opportunities

        Source: backend/app/agents/tracking_agent.py:1100-1311

        Args:
            user_id: User ID

        Returns:
            Dict: {
                "success": True,
                "total_items": 15,
                "urgent_count": 5,
                "soon_count": 6,
                "routine_count": 4,
                "bulk_opportunities": 2,
                "restock_list": {
                    "urgent": [...],  # Can't cook planned meals OR critically low stock
                    "soon": [...],    # < 50% of recommended stock
                    "routine": [...], # < 70% stock for frequently used items
                    "bulk_opportunities": [...]
                },
                "estimated_cost": 125.50,
                "shopping_strategy": [...],
                "analysis_period": "14 days of consumption data"
            }
        """
        try:
            # STEP 1: Get upcoming planned meals (next 7 days) - PRIORITY DATA
            seven_days_from_now = datetime.utcnow() + timedelta(days=7)
            upcoming_items = await self._get_upcoming_consumption_patterns(user_id, seven_days_from_now)

            # STEP 2: Get historical consumption data (last 30 days) - TREND DATA
            two_weeks_ago = datetime.utcnow() - timedelta(days=30)

            recent_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe).joinedload(Recipe.ingredients).joinedload(RecipeIngredient.item)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime >= two_weeks_ago,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()

            # Calculate historical item usage patterns
            item_usage = {}
            recipe_count = {}

            for log in recent_logs:
                if not log.recipe:
                    continue

                recipe_count[log.recipe_id] = recipe_count.get(log.recipe_id, 0) + 1

                try:
                    ingredients = log.recipe.ingredients
                    portion_multiplier = log.portion_multiplier or 1.0

                    for ingredient in ingredients:
                        if not ingredient.item:
                            continue

                        item_id = ingredient.item_id
                        quantity = ingredient.quantity_grams * portion_multiplier

                        if item_id not in item_usage:
                            item_usage[item_id] = {
                                "total_used": 0,
                                "usage_count": 0,
                                "recipes": set(),
                                "avg_per_use": 0
                            }

                        item_usage[item_id]["total_used"] += quantity
                        item_usage[item_id]["usage_count"] += 1
                        item_usage[item_id]["recipes"].add(log.recipe_id)

                except Exception as e:
                    logger.warning(f"Error processing recipe ingredients for restock: {str(e)}")
                    continue

            # Calculate averages
            for item_id, usage_data in item_usage.items():
                if usage_data["usage_count"] > 0:
                    usage_data["avg_per_use"] = usage_data["total_used"] / usage_data["usage_count"]

            # STEP 3: Get current inventory
            current_inventory = {}
            inventory_items = await self.inventory_repo.get_all_for_user(user_id, include_zero_quantity=True)

            for inv_item in inventory_items:
                if hasattr(inv_item, 'item') and inv_item.item:
                    current_inventory[inv_item.item_id] = {
                        "quantity": inv_item.quantity_grams,
                        "expiry": inv_item.expiry_date
                    }

            # Generate restock list
            restock_list = {
                "urgent": [],     # Can't cook planned meals OR critically low stock
                "soon": [],       # < 50% of recommended stock
                "routine": [],    # < 70% stock for frequently used items
                "bulk_opportunities": []
            }

            # Calculate weekly multiplier from historical data
            days_of_data = len(set(log.consumed_datetime.date() for log in recent_logs if log.consumed_datetime))
            weekly_multiplier = (7 / days_of_data) if days_of_data > 0 else 0

            # STEP 4: Combine all items from both upcoming meals and historical usage
            all_items = set(upcoming_items.keys()) | set(item_usage.keys())

            for item_id in all_items:
                try:
                    item = self.db.query(Item).filter(Item.id == item_id).first()
                    if not item:
                        continue

                    current_stock = current_inventory.get(item_id, {}).get("quantity", 0)

                    # Calculate upcoming requirement (next 7 days planned meals)
                    upcoming_requirement = sum(
                        use["quantity_needed"] for use in upcoming_items.get(item_id, [])
                    )

                    # Calculate historical weekly requirement (with 20% buffer)
                    historical_weekly = 0
                    usage_data = item_usage.get(item_id, {})
                    usage_count = usage_data.get("usage_count", 0)

                    if usage_data and weekly_multiplier > 0:
                        historical_weekly = usage_data["total_used"] * weekly_multiplier * 1.2

                    # Smart recommendation: prioritize upcoming needs, but consider historical patterns
                    recommended_stock = max(upcoming_requirement, historical_weekly)

                    # Calculate shortage
                    shortage = max(recommended_stock - current_stock, 0)

                    # Skip if no shortage and not needed for upcoming meals
                    if shortage == 0 and upcoming_requirement == 0:
                        continue

                    # Calculate stock metrics
                    stock_percentage = (current_stock / recommended_stock * 100) if recommended_stock > 0 else 100
                    days_supply = (current_stock / (recommended_stock / 7)) if recommended_stock > 0 else 0

                    restock_info = {
                        "item_id": item_id,
                        "item_name": item.canonical_name,
                        "category": item.category or "other",
                        "current_quantity": round(current_stock, 1),
                        "recommended_quantity": round(shortage, 1),
                        "priority": "",  # Will be set below
                        "usage_frequency": usage_count,
                        "days_until_depleted": int(days_supply) if days_supply > 0 else 0
                    }

                    # Check for expiry urgency
                    inventory_item = current_inventory.get(item_id, {})
                    if inventory_item.get("expiry"):
                        try:
                            expiry_date = inventory_item["expiry"]
                            if isinstance(expiry_date, str):
                                expiry_date = datetime.fromisoformat(expiry_date)
                            days_to_expiry = (expiry_date - datetime.utcnow()).days
                            restock_info["days_to_expiry"] = days_to_expiry

                            if days_to_expiry <= 3:
                                restock_info["expiry_urgency"] = "urgent"
                            elif days_to_expiry <= 7:
                                restock_info["expiry_urgency"] = "soon"
                        except Exception as e:
                            logger.warning(f"Error processing expiry for item {item_id}: {str(e)}")

                    # PRIORITY LOGIC: Prioritize upcoming meal needs
                    if current_stock < upcoming_requirement:
                        # Can't cook planned meals - URGENT
                        restock_info["priority"] = "urgent"
                        restock_list["urgent"].append(restock_info)
                    elif stock_percentage < 20 or restock_info.get("expiry_urgency") == "urgent":
                        # Critically low stock - URGENT
                        restock_info["priority"] = "urgent"
                        restock_list["urgent"].append(restock_info)
                    elif stock_percentage < 50 or restock_info.get("expiry_urgency") == "soon":
                        # Low stock - SOON
                        restock_info["priority"] = "soon"
                        restock_list["soon"].append(restock_info)
                    elif stock_percentage < 70 and usage_count >= 3:
                        # Frequently used, medium stock - ROUTINE
                        restock_info["priority"] = "routine"
                        restock_list["routine"].append(restock_info)

                    # Check for bulk buying opportunities
                    if usage_data and usage_count >= 5 and len(usage_data.get("recipes", [])) >= 3:
                        if item.category in ["grains", "protein", "spices"]:
                            restock_list["bulk_opportunities"].append({
                                **restock_info,
                                "bulk_suggestion": f"Buy {round(recommended_stock * 4, 1)}g (1 month supply)",
                                "bulk_reason": f"Used in {len(usage_data['recipes'])} recipes, {usage_count} times"
                            })

                except Exception as e:
                    logger.warning(f"Error processing item {item_id} for restock list: {str(e)}")
                    continue

            # Sort each category by priority
            restock_list["urgent"].sort(key=lambda x: (x["days_until_depleted"], -x["usage_frequency"]))
            restock_list["soon"].sort(key=lambda x: (x["days_until_depleted"], -x["usage_frequency"]))
            restock_list["routine"].sort(key=lambda x: (-x["usage_frequency"], x["days_until_depleted"]))

            # Calculate summary
            total_items = sum(len(restock_list[category]) for category in ["urgent", "soon", "routine"])
            estimated_cost = self._estimate_cost(restock_list)
            shopping_strategy = self._generate_shopping_strategy(restock_list)

            logger.info(f"Restock list generated for user {user_id}: {total_items} items")

            return {
                "success": True,
                "total_items": total_items,
                "urgent_count": len(restock_list["urgent"]),
                "soon_count": len(restock_list["soon"]),
                "routine_count": len(restock_list["routine"]),
                "bulk_opportunities": len(restock_list["bulk_opportunities"]),
                "restock_list": restock_list,
                "estimated_cost": estimated_cost,
                "shopping_strategy": shopping_strategy,
                "analysis_period": f"{days_of_data} days of consumption data"
            }

        except Exception as e:
            logger.error(f"Error generating restock list: {str(e)}")
            return {"success": False, "error": f"Failed to generate restock list: {str(e)}"}

    # ===== Private Helper Methods =====

    async def _get_upcoming_consumption_patterns(
        self,
        user_id: int,
        until_date: datetime
    ) -> Dict[int, List[Dict]]:
        """
        Get upcoming meal plans and aggregate by item_id.

        Source: backend/app/agents/tracking_agent.py:823-872

        Args:
            user_id: User ID
            until_date: End date for upcoming meals

        Returns:
            Dict[int, List[Dict]]: {item_id: [{"planned_date": datetime, "quantity_needed": float}, ...]}
        """
        try:
            # Query upcoming planned meals
            upcoming_meals = self.db.query(MealLog).options(
                joinedload(MealLog.recipe).joinedload(Recipe.ingredients).joinedload(RecipeIngredient.item)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime <= until_date,
                    MealLog.planned_datetime >= datetime.utcnow(),
                    MealLog.consumed_datetime.is_(None),  # Not yet consumed
                    MealLog.was_skipped == False,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()

            consumption_patterns = {}

            for meal in upcoming_meals:
                if not meal.recipe:
                    continue

                try:
                    ingredients = meal.recipe.ingredients
                    portion_multiplier = meal.portion_multiplier or 1.0

                    for ingredient in ingredients:
                        if not ingredient.item:
                            continue

                        item_id = ingredient.item_id
                        quantity_needed = ingredient.quantity_grams * portion_multiplier

                        if item_id not in consumption_patterns:
                            consumption_patterns[item_id] = []

                        consumption_patterns[item_id].append({
                            "planned_date": meal.planned_datetime,
                            "quantity_needed": quantity_needed,
                            "meal_type": meal.meal_type,
                            "recipe_name": meal.recipe.title
                        })

                except Exception as e:
                    logger.warning(f"Error processing meal {meal.id} for consumption patterns: {str(e)}")
                    continue

            return consumption_patterns

        except Exception as e:
            logger.error(f"Error getting consumption patterns: {str(e)}")
            return {}

    def _will_be_consumed_before_expiry(
        self,
        item_id: int,
        expiry_date: datetime,
        available_quantity: float,
        consumption_patterns: Dict[int, List[Dict]]
    ) -> bool:
        """
        Determine if an item will be fully consumed before expiry.

        Source: backend/app/agents/tracking_agent.py:874-915

        Args:
            item_id: Item ID
            expiry_date: Expiry date
            available_quantity: Available quantity in grams
            consumption_patterns: Upcoming consumption patterns

        Returns:
            bool: True if item will be consumed, False if it will expire unused
        """
        if item_id not in consumption_patterns:
            # No upcoming meals planned with this item
            return False

        planned_uses = consumption_patterns[item_id]

        # Filter only uses before expiry
        uses_before_expiry = [
            use for use in planned_uses
            if use["planned_date"] <= expiry_date
        ]

        if not uses_before_expiry:
            return False

        # Calculate total quantity needed before expiry
        total_needed = sum(use["quantity_needed"] for use in uses_before_expiry)

        # Item will be consumed if planned usage >= 80% of available quantity
        # (80% threshold accounts for typical cooking variations)
        consumption_threshold = 0.8
        will_consume = total_needed >= (available_quantity * consumption_threshold)

        logger.debug(
            f"Item {item_id}: {total_needed}g needed vs {available_quantity}g available "
            f"before expiry - will_consume: {will_consume}"
        )

        return will_consume

    def _generate_expiry_recommendations(self, expiring_items: List[Dict]) -> List[str]:
        """Generate actionable recommendations for expiring items."""
        recommendations = []

        urgent_count = len([i for i in expiring_items if i["priority"] == "urgent"])
        high_count = len([i for i in expiring_items if i["priority"] == "high"])

        if urgent_count > 0:
            urgent_names = [i["item_name"] for i in expiring_items if i["priority"] == "urgent"][:3]
            recommendations.append(f"URGENT: Use {', '.join(urgent_names)} immediately (expiring within 1 day)")

        if high_count > 0:
            high_names = [i["item_name"] for i in expiring_items if i["priority"] == "high"][:3]
            recommendations.append(f"Use {', '.join(high_names)} within 2-3 days")

        if len(expiring_items) > 5:
            recommendations.append(f"Total {len(expiring_items)} items expiring soon - plan meals accordingly")

        return recommendations

    def _estimate_cost(self, restock_list: Dict) -> Optional[float]:
        """Estimate total cost for restock list (placeholder)."""
        # Placeholder - would integrate with pricing API in production
        return None

    def _generate_shopping_strategy(self, restock_list: Dict) -> List[str]:
        """Generate shopping strategy recommendations."""
        strategy = []

        urgent_count = len(restock_list["urgent"])
        soon_count = len(restock_list["soon"])
        bulk_count = len(restock_list["bulk_opportunities"])

        if urgent_count > 0:
            strategy.append(f"Priority: Buy {urgent_count} urgent items immediately")

        if soon_count > 0:
            strategy.append(f"Plan shopping for {soon_count} items within 2-3 days")

        if bulk_count > 0:
            strategy.append(f"Consider bulk buying {bulk_count} frequently used items for savings")

        if urgent_count + soon_count > 10:
            strategy.append("Large shopping trip recommended - consider online delivery")
        elif urgent_count + soon_count > 0:
            strategy.append("Quick grocery run for essential items")

        return strategy