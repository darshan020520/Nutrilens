"""
Grocery Service

Service for grocery list calculation from meal plans.

ALL CODE COPY-PASTED FROM planning_agent.py:265-362, 924-945 - ZERO LOGIC CHANGES
"""

import logging
from typing import Dict, List, Any
from collections import defaultdict

from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces.inventory_repository import IInventoryRepository

logger = logging.getLogger(__name__)


class GroceryService:
    """
    Service for calculating grocery lists from meal plans.

    BUSINESS LOGIC COPY-PASTED FROM: planning_agent.py:265-362
    REFACTORED: Now uses repositories instead of direct DB queries
    """

    def __init__(
        self,
        recipe_repo: IRecipeRepository,
        inventory_repo: IInventoryRepository
    ):
        """
        Initialize grocery service.

        Args:
            recipe_repo: Recipe repository
            inventory_repo: Inventory repository
        """
        self.recipe_repo = recipe_repo
        self.inventory_repo = inventory_repo

    async def calculate_for_plan(self, meal_plan: Dict, user_id: int) -> Dict[str, Any]:
        """
        Build a grocery list from a meal plan.

        REFACTORED: Now uses repositories instead of direct DB queries.
        Original: planning_agent.py:265-362

        Args:
            meal_plan: Meal plan week_plan data
            user_id: User ID

        Returns:
            Grocery list with items, categorization, and quantities
        """
        try:
            # COPY-PASTED FROM planning_agent.py:270 - NO CHANGES
            grocery_list: Dict[int, Dict[str, Any]] = {}

            # COPY-PASTED FROM planning_agent.py:272-278 - NO CHANGES
            # --- Step 1: collect recipe IDs ---
            recipe_ids = [
                recipe["id"]
                for day_data in meal_plan.values()
                for recipe in (day_data.get("meals", {}) or {}).values()
                if recipe and recipe.get("id")
            ]

            # COPY-PASTED FROM planning_agent.py:279-287 - NO CHANGES
            if not recipe_ids:
                # 🔹 Return an EMPTY valid response instead of bare dict
                return {
                    "items": {},
                    "categorized": {},
                    "total_items": 0,
                    "items_to_buy": 0,
                    "estimated_cost": None
                }

            # REFACTORED: Use recipe repository to batch fetch ingredients
            # --- Step 2: fetch recipe ingredients ---
            all_ingredients_map = await self.recipe_repo.get_ingredients_for_recipes(recipe_ids)

            # Flatten to list (original code expects a list)
            recipe_ingredients = [
                ing
                for ingredients in all_ingredients_map.values()
                for ing in ingredients
            ]

            # REFACTORED: No separate Item query needed - items are eager-loaded in RecipeIngredient.item
            # --- Step 3: collect item IDs from ingredients ---
            item_ids = list({ri.item_id for ri in recipe_ingredients if ri.item_id})

            # REFACTORED: Use inventory repository to batch fetch user inventory
            # --- Step 4: user inventory ---
            inventory_records = await self.inventory_repo.get_by_item_ids(user_id, item_ids)

            # Convert to map (item_id -> quantity_grams)
            inventory_map = {
                item_id: inv.quantity_grams
                for item_id, inv in inventory_records.items()
            }

            # COPY-PASTED FROM planning_agent.py:311-328 - NO CHANGES
            # --- Step 5: aggregate ---
            for ri in recipe_ingredients:
                if not ri.item_id:
                    continue
                if ri.item_id not in grocery_list:
                    # REFACTORED: Use eager-loaded item from relationship instead of items_map
                    item = ri.item
                    grocery_list[ri.item_id] = {
                        "item_id": ri.item_id,
                        "item_name": item.canonical_name if item else f"Item {ri.item_id}",
                        "category": self._normalize_category(
                            item.category if item else "other"
                        ),
                        "unit": item.unit if item else "g",
                        "quantity_needed": 0.0,
                        "quantity_available": 0.0,
                        "to_buy": 0.0,
                    }
                grocery_list[ri.item_id]["quantity_needed"] += ri.quantity_grams

            # COPY-PASTED FROM planning_agent.py:330-334 - NO CHANGES
            # --- Step 6: compute to_buy ---
            for item_id, data in grocery_list.items():
                available = inventory_map.get(item_id, 0)
                data["quantity_available"] = available
                data["to_buy"] = max(0, data["quantity_needed"] - available)

            # COPY-PASTED FROM planning_agent.py:336-337 - NO CHANGES
            # --- Step 7: categorize ---
            categorized = self._categorize_grocery_list(grocery_list)

            # COPY-PASTED FROM planning_agent.py:339-340 - NO CHANGES
            # --- Step 8: convert keys to strings for Pydantic ---
            items_str_keys = {str(k): v for k, v in grocery_list.items()}

            # COPY-PASTED FROM planning_agent.py:342-343 - NO CHANGES
            # 🔹 Placeholder for future cost logic
            estimated_cost = None

            # COPY-PASTED FROM planning_agent.py:345-351 - NO CHANGES
            return {
                "items": items_str_keys,
                "categorized": categorized,
                "total_items": len(items_str_keys),
                "items_to_buy": sum(1 for d in grocery_list.values() if d["to_buy"] > 0),
                "estimated_cost": estimated_cost
            }

        except Exception as e:
            # COPY-PASTED FROM planning_agent.py:354-362 - NO CHANGES
            logger.exception("Error calculating grocery list")
            # 🔹 Return valid but empty response instead of bare dict
            return {
                "items": {},
                "categorized": {},
                "total_items": 0,
                "items_to_buy": 0,
                "estimated_cost": None
            }

    def _categorize_grocery_list(self, grocery_list: Dict[int, Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        Categorize grocery list items.

        EXACT COPY-PASTE FROM: planning_agent.py:924-940

        Args:
            grocery_list: Grocery list with item data

        Returns:
            Categorized grocery list
        """
        # COPY-PASTED FROM planning_agent.py:925-940 - NO CHANGES
        categories = defaultdict(list)
        for item_id, data in grocery_list.items():
            if data["to_buy"] > 0:

                cat = self._normalize_category(data.get("category", "other") or "other")

                categories[cat].append({
                    "item_id": item_id,
                    "item_name": data["item_name"],
                    "category": cat,
                    "unit": data["unit"],
                    "quantity_needed": data["quantity_needed"],
                    "quantity_available": data["quantity_available"],
                    "to_buy": data["to_buy"]
                })
        return categories

    def _normalize_category(self, category: str) -> str:
        """
        Normalize category names.

        EXACT COPY-PASTE FROM: planning_agent.py:943-945

        Args:
            category: Category name

        Returns:
            Normalized category name
        """
        # COPY-PASTED FROM planning_agent.py:944-945 - NO CHANGES
        mapping = {"fats": "fat"}  # Extend as needed
        return mapping.get(category.lower(), category.lower())
