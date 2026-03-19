import logging
from typing import Optional, List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, cast, String, func, case, and_, or_
from collections import defaultdict

from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.models.database import Recipe, RecipeIngredient, Item, UserPreference, UserGoal

logger = logging.getLogger(__name__)


class RecipeRepository(IRecipeRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, recipe_id: int) -> Optional[Recipe]:
        result = await self.db.execute(select(Recipe).where(Recipe.id == recipe_id))
        return result.scalars().first()

    async def get_ingredients_by_recipe_id(self, recipe_id: int) -> List[RecipeIngredient]:
        result = await self.db.execute(
            select(RecipeIngredient)
            .options(joinedload(RecipeIngredient.item))
            .where(RecipeIngredient.recipe_id == recipe_id)
        )
        return result.unique().scalars().all()

    async def get_makeable_recipe_candidates(
        self,
        user_item_quantities: Dict[int, float],
        min_match_pct: float = 80.0,
        limit: int = 30
    ) -> List[Dict]:

        if not user_item_quantities:
            return []

        user_item_ids = set(user_item_quantities.keys())

        # Pre-filter: only load recipes that have at least one matching required ingredient
        # This avoids a full table scan when the user has a small inventory
        matching_recipe_ids_subq = (
            select(RecipeIngredient.recipe_id)
            .where(
                RecipeIngredient.item_id.in_(user_item_ids),
                RecipeIngredient.is_optional == False,
            )
            .distinct()
            .scalar_subquery()
        )

        result = await self.db.execute(
            select(Recipe)
            .options(joinedload(Recipe.ingredients).joinedload(RecipeIngredient.item))
            .where(Recipe.id.in_(matching_recipe_ids_subq))
        )
        all_recipes = result.unique().scalars().all()

        results = []

        for recipe in all_recipes:
            required_ingredients = [ing for ing in recipe.ingredients if not ing.is_optional]

            if not required_ingredients:
                continue

            available_items = []
            missing_items = []

            for ingredient in required_ingredients:
                user_qty = user_item_quantities.get(ingredient.item_id, 0)
                item_name = ingredient.item.canonical_name if ingredient.item else "Unknown"

                if user_qty >= ingredient.quantity_grams:
                    available_items.append(item_name)
                else:
                    missing_items.append(item_name)

            total_count = len(required_ingredients)
            available_count = len(available_items)
            match_pct = (available_count / total_count * 100) if total_count > 0 else 0

            if match_pct >= min_match_pct:
                results.append({
                    'recipe': recipe,
                    'match_percentage': round(match_pct, 1),
                    'available_count': available_count,
                    'total_count': total_count,
                    'available_items': available_items,
                    'missing_items': missing_items
                })

        results.sort(key=lambda x: (-x['match_percentage'], x['recipe'].prep_time_min or 999))
        return results[:limit]

    async def get_alternatives(
        self,
        original_recipe: Recipe,
        user_preferences: Optional[UserPreference],
        user_goal: Optional[UserGoal],
        count: int
    ) -> List[dict]:

        try:
            preferences = user_preferences
            goal = user_goal

            target_cal = original_recipe.macros_per_serving['calories']

            stmt = select(Recipe).where(Recipe.id != original_recipe.id)

            if preferences and preferences.dietary_type:
                dietary_tag = preferences.dietary_type.value
                stmt = stmt.where(cast(Recipe.dietary_tags, String).contains(dietary_tag))

            result = await self.db.execute(stmt)
            all_recipes = result.unique().scalars().all()

            min_cal = target_cal * 0.7
            max_cal = target_cal * 1.3
            original_meal_times = set(original_recipe.suitable_meal_times or [])

            candidates = []
            for recipe in all_recipes:
                calories = recipe.macros_per_serving.get('calories', 0)
                if not (min_cal <= calories <= max_cal):
                    continue

                recipe_meal_times = set(recipe.suitable_meal_times or [])
                if not (original_meal_times & recipe_meal_times):
                    continue

                candidates.append(recipe)

            if not candidates:
                logger.info(f"No alternative candidates found for recipe {original_recipe.id}")
                return []

            scored = []
            orig_macros = original_recipe.macros_per_serving

            for recipe in candidates:
                macros = recipe.macros_per_serving

                cal_diff = abs(macros['calories'] - orig_macros['calories']) / orig_macros['calories']
                protein_diff = abs(macros['protein_g'] - orig_macros['protein_g']) / max(orig_macros['protein_g'], 1)
                carbs_diff = abs(macros['carbs_g'] - orig_macros['carbs_g']) / max(orig_macros['carbs_g'], 1)
                fat_diff = abs(macros['fat_g'] - orig_macros['fat_g']) / max(orig_macros['fat_g'], 1)

                macro_similarity = 1 - (
                    cal_diff * 0.4 +
                    protein_diff * 0.35 +
                    carbs_diff * 0.15 +
                    fat_diff * 0.1
                )

                goal_bonus = 0
                if goal and recipe.goals:
                    if goal.goal_type.value in recipe.goals:
                        goal_bonus = 0.2

                total_score = macro_similarity + goal_bonus

                scored.append({
                    'recipe': {
                        'id': recipe.id,
                        'title': recipe.title,
                        'description': recipe.description,
                        'suitable_meal_times': recipe.suitable_meal_times or [],
                        'macros_per_serving': recipe.macros_per_serving,
                        'prep_time_min': recipe.prep_time_min or 0,
                        'cook_time_min': recipe.cook_time_min or 0,
                        'servings': recipe.servings or 1,
                        'goals': recipe.goals or [],
                        'dietary_tags': recipe.dietary_tags or [],
                        'image_url': recipe.image_url
                    },
                    'similarity_score': round(total_score, 3),
                    'calorie_difference': round(macros['calories'] - orig_macros['calories'], 1),
                    'protein_difference': round(macros['protein_g'] - orig_macros['protein_g'], 1),
                    'carbs_difference': round(macros['carbs_g'] - orig_macros['carbs_g'], 1),
                    'fat_difference': round(macros['fat_g'] - orig_macros['fat_g'], 1),
                    'suitable_for_swap': True
                })

            scored.sort(key=lambda x: x['similarity_score'], reverse=True)
            return scored[:count]

        except Exception as e:
            logger.error(f"Error finding alternatives for recipe {original_recipe.id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    async def search(
        self,
        goal: Optional[str] = None,
        dietary_type: Optional[str] = None,
        meal_time: Optional[str] = None,
        max_prep_time: Optional[int] = None,
        cuisine: Optional[str] = None,
        search_term: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Recipe]:

        stmt = select(Recipe)

        if goal:
            stmt = stmt.where(cast(Recipe.goals, String).contains(goal))

        if dietary_type:
            stmt = stmt.where(cast(Recipe.dietary_tags, String).contains(dietary_type))

        if meal_time:
            stmt = stmt.where(cast(Recipe.suitable_meal_times, String).contains(meal_time))

        if max_prep_time:
            stmt = stmt.where(Recipe.prep_time_min <= max_prep_time)

        if cuisine:
            stmt = stmt.where(Recipe.cuisine == cuisine)

        if search_term:
            search_pattern = f"%{search_term}%"
            stmt = stmt.where(
                or_(
                    Recipe.title.ilike(search_pattern),
                    Recipe.description.ilike(search_pattern)
                )
            )

        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def get_with_ingredients(self, recipe_id: int) -> Optional[dict]:
        recipe = await self.get_by_id(recipe_id)
        if not recipe:
            return None

        result = await self.db.execute(
            select(RecipeIngredient, Item)
            .join(Item, RecipeIngredient.item_id == Item.id)
            .where(RecipeIngredient.recipe_id == recipe_id)
        )
        rows = result.all()

        ingredient_list = []
        for recipe_ing, item in rows:
            ingredient_list.append({
                "item_id": item.id,
                "item_name": item.canonical_name,
                "quantity_grams": recipe_ing.quantity_grams,
                "is_optional": recipe_ing.is_optional,
                "preparation_notes": recipe_ing.preparation_notes
            })

        return {
            "recipe": recipe,
            "ingredients": ingredient_list
        }

    async def count_all_recipes(self) -> int:
        result = await self.db.execute(select(func.count(Recipe.id)))
        return result.scalar()

    async def get_filtered_recipes(
        self,
        goal_type: Optional[str] = None,
        dietary_type: Optional[str] = None,
        exclude_allergens: Optional[List[str]] = None,
        max_prep_time: Optional[int] = None
    ) -> List[Recipe]:
        stmt = select(Recipe)

        if goal_type:
            stmt = stmt.where(cast(Recipe.goals, String).contains(goal_type))

        if dietary_type:
            if dietary_type == 'vegetarian':
                stmt = stmt.where(cast(Recipe.dietary_tags, String).contains('vegetarian'))
            elif dietary_type == 'vegan':
                stmt = stmt.where(cast(Recipe.dietary_tags, String).contains('vegan'))

        if max_prep_time is not None:
            stmt = stmt.where((Recipe.prep_time_min + Recipe.cook_time_min) <= max_prep_time)

        result = await self.db.execute(stmt)
        return result.unique().scalars().all()

    async def get_ingredients_for_recipes(self, recipe_ids: List[int]) -> Dict[int, List[RecipeIngredient]]:
        if not recipe_ids:
            return {}

        result = await self.db.execute(
            select(RecipeIngredient)
            .options(joinedload(RecipeIngredient.item))
            .where(RecipeIngredient.recipe_id.in_(recipe_ids))
        )
        ingredients = result.unique().scalars().all()

        result_dict = defaultdict(list)
        for ing in ingredients:
            result_dict[ing.recipe_id].append(ing)

        return dict(result_dict)

    async def get_titles_and_embeddings(self) -> List[Tuple[str, Optional[str]]]:
        result = await self.db.execute(select(Recipe.title, Recipe.embedding))
        return [(r.title, r.embedding) for r in result.all()]

    async def create_recipe(self, recipe: Recipe) -> Recipe:
        self.db.add(recipe)
        await self.db.flush()
        return recipe

    async def add_recipe_ingredient(self, recipe_ingredient: RecipeIngredient) -> None:
        self.db.add(recipe_ingredient)

    async def get_items_by_canonical_names(self, names: List[str]) -> Dict[str, Item]:
        result = await self.db.execute(
            select(Item).where(Item.canonical_name.in_(names))
        )
        items = result.unique().scalars().all()
        return {item.canonical_name: item for item in items}
