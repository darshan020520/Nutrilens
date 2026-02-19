import logging
from typing import Dict, List, Any
from collections import defaultdict

from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces.inventory_repository import IInventoryRepository

logger = logging.getLogger(__name__)


class GroceryService:
    def __init__(
        self,
        recipe_repo: IRecipeRepository,
        inventory_repo: IInventoryRepository
    ):
        self.recipe_repo = recipe_repo
        self.inventory_repo = inventory_repo

    async def calculate_for_plan(self, meal_plan: Dict, user_id: int) -> Dict[str, Any]:

        try:
            grocery_list: Dict[int, Dict[str, Any]] = {}
            recipe_ids = [
                recipe["id"]
                for day_data in meal_plan.values()
                for recipe in (day_data.get("meals", {}) or {}).values()
                if recipe and recipe.get("id")
            ]

            if not recipe_ids:
                return {
                    "items": {},
                    "categorized": {},
                    "total_items": 0,
                    "items_to_buy": 0,
                    "estimated_cost": None
                }

            all_ingredients_map = await self.recipe_repo.get_ingredients_for_recipes(recipe_ids)

            recipe_ingredients = [
                ing
                for ingredients in all_ingredients_map.values()
                for ing in ingredients
            ]


            item_ids = list({ri.item_id for ri in recipe_ingredients if ri.item_id})
            inventory_records = await self.inventory_repo.get_by_item_ids(user_id, item_ids)

            inventory_map = {
                item_id: inv.quantity_grams
                for item_id, inv in inventory_records.items()
            }

            for ri in recipe_ingredients:
                if not ri.item_id:
                    continue
                if ri.item_id not in grocery_list:
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

            for item_id, data in grocery_list.items():
                available = inventory_map.get(item_id, 0)
                data["quantity_available"] = available
                data["to_buy"] = max(0, data["quantity_needed"] - available)

            categorized = self._categorize_grocery_list(grocery_list)

            items_str_keys = {str(k): v for k, v in grocery_list.items()}

            estimated_cost = None

            return {
                "items": items_str_keys,
                "categorized": categorized,
                "total_items": len(items_str_keys),
                "items_to_buy": sum(1 for d in grocery_list.values() if d["to_buy"] > 0),
                "estimated_cost": estimated_cost
            }

        except Exception as e:

            logger.exception("Error calculating grocery list")
            return {
                "items": {},
                "categorized": {},
                "total_items": 0,
                "items_to_buy": 0,
                "estimated_cost": None
            }

    def _categorize_grocery_list(self, grocery_list: Dict[int, Dict[str, Any]]) -> Dict[str, List[Dict]]:

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

        mapping = {"fats": "fat"}
        return mapping.get(category.lower(), category.lower())
