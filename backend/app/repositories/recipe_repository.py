import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import cast, String, func, case, and_, or_, Float
from collections import defaultdict

from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.models.database import Recipe, RecipeIngredient, Item, UserPreference, UserGoal

logger = logging.getLogger(__name__)


class RecipeRepository(IRecipeRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, recipe_id: int) -> Optional[Recipe]:
        return self.db.query(Recipe).filter_by(id=recipe_id).first()

    def get_ingredients_by_recipe_id(self, recipe_id: int) -> List[RecipeIngredient]:
        
        return self.db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.item)
        ).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()

    async def get_makeable_recipe_candidates(
        self,
        user_item_quantities: Dict[int, float],
        min_match_pct: float = 80.0,
        limit: int = 30
    ) -> List[Dict]:

        if not user_item_quantities:
            return []

        user_item_ids = set(user_item_quantities.keys())

        recipe_match_subquery = self.db.query(
            Recipe.id.label('recipe_id'),
            func.count(RecipeIngredient.id).label('total_ingredients'),

            func.sum(
                case(
                    (RecipeIngredient.item_id.in_(user_item_ids), 1),
                    else_=0
                )
            ).label('matching_ingredients')

        ).join(
            RecipeIngredient,
            Recipe.id == RecipeIngredient.recipe_id
        ).filter(
            RecipeIngredient.is_optional == False  # Only required ingredients
        ).group_by(
            Recipe.id
        ).having(
            func.count(RecipeIngredient.id) > 0
        ).subquery()


        recipe_candidates = self.db.query(
            Recipe,
            recipe_match_subquery.c.total_ingredients,
            recipe_match_subquery.c.matching_ingredients
        ).join(
            recipe_match_subquery,
            Recipe.id == recipe_match_subquery.c.recipe_id
        ).options(
            # Eager load ingredients + items to prevent N+1 queries
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.item)
        ).limit(limit * 3).all()


        results = []

        for recipe, total_ing, _ in recipe_candidates:
            required_ingredients = [
                ing for ing in recipe.ingredients
                if not ing.is_optional
            ]

            if not required_ingredients:
                continue

            available_items = []
            missing_items = []

            for ingredient in required_ingredients:
                user_qty = user_item_quantities.get(ingredient.item_id, 0)
                item_name = ingredient.item.canonical_name

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

        results.sort(
            key=lambda x: (-x['match_percentage'], x['recipe'].prep_time_min or 999)
        )

        return results[:limit]

    def get_alternatives(
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

            query = self.db.query(Recipe).filter(Recipe.id != original_recipe.id)

            if preferences and preferences.dietary_type:
                dietary_tag = preferences.dietary_type.value
                query = query.filter(
                    cast(Recipe.dietary_tags, String).contains(dietary_tag)
                )

            all_recipes = query.all()

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
                logger.info(f"No alternative candidates found for recipe {original_recipe.id} (filtered {len(all_recipes)} by meal time)")
                return []

            logger.info(f"Found {len(candidates)} candidate alternatives for recipe {original_recipe.id} (from {len(all_recipes)} after calorie filter)")


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
                        'dietary_tags': recipe.dietary_tags or []
                    },
                    'similarity_score': round(total_score, 3),
                    'calorie_difference': round(macros['calories'] - orig_macros['calories'], 1),
                    'protein_difference': round(macros['protein_g'] - orig_macros['protein_g'], 1),
                    'carbs_difference': round(macros['carbs_g'] - orig_macros['carbs_g'], 1),
                    'fat_difference': round(macros['fat_g'] - orig_macros['fat_g'], 1),
                    'suitable_for_swap': True
                })

            scored.sort(key=lambda x: x['similarity_score'], reverse=True)

            logger.info(f"Returning top {count} alternatives with scores: {[s['similarity_score'] for s in scored[:count]]}")

            return scored[:count]

        except Exception as e:
            logger.error(f"Error finding alternatives for recipe {original_recipe.id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def search(
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
        

        query = self.db.query(Recipe)

        # Apply filters
        if goal:
            query = query.filter(
                cast(Recipe.goals, String).contains(goal)
            )

        if dietary_type:
            query = query.filter(
                cast(Recipe.dietary_tags, String).contains(dietary_type)
            )

        if meal_time:
            query = query.filter(
                cast(Recipe.suitable_meal_times, String).contains(meal_time)
            )

        if max_prep_time:
            query = query.filter(Recipe.prep_time_min <= max_prep_time)

        if cuisine:
            query = query.filter(Recipe.cuisine == cuisine)

        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.filter(
                or_(
                    Recipe.title.ilike(search_pattern),
                    Recipe.description.ilike(search_pattern)
                )
            )

        # Apply pagination
        return query.offset(offset).limit(limit).all()

    def get_with_ingredients(self, recipe_id: int) -> Optional[dict]:
        recipe = self.get_by_id(recipe_id)
        if not recipe:
            return None

        # Get ingredients with item names
        ingredients = self.db.query(
            RecipeIngredient, Item
        ).join(
            Item, RecipeIngredient.item_id == Item.id
        ).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()

        ingredient_list = []
        for recipe_ing, item in ingredients:
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
        return self.db.query(Recipe).count()

    async def get_filtered_recipes(
        self,
        goal_type: Optional[str] = None,
        dietary_type: Optional[str] = None,
        exclude_allergens: Optional[List[str]] = None,
        max_prep_time: Optional[int] = None
    ) -> List[Recipe]:
        query = self.db.query(Recipe)

        if goal_type:
            query = query.filter(cast(Recipe.goals, String).contains(goal_type))

        if dietary_type:
            if dietary_type == 'vegetarian':
                query = query.filter(cast(Recipe.dietary_tags, String).contains('vegetarian'))
            elif dietary_type == 'vegan':
                query = query.filter(cast(Recipe.dietary_tags, String).contains('vegan'))


        if exclude_allergens:
            # TODO: Implement allergen filtering when optimizer supports it
            pass

        if max_prep_time is not None:
            query = query.filter(
                (Recipe.prep_time_min + Recipe.cook_time_min) <= max_prep_time
            )

        return query.all()

    async def get_ingredients_for_recipes(self, recipe_ids: List[int]) -> Dict[int, List[RecipeIngredient]]:
        if not recipe_ids:
            return {}

        ingredients = self.db.query(RecipeIngredient).options(
            joinedload(RecipeIngredient.item)
        ).filter(
            RecipeIngredient.recipe_id.in_(recipe_ids)
        ).all()

        result = defaultdict(list)
        for ing in ingredients:
            result[ing.recipe_id].append(ing)

        return dict(result)
