from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional, Dict
from pydantic import BaseModel
import logging

from app.models.database import User
from app.repositories.recipe_repository import RecipeRepository
from app.dependencies import get_recipe_repository, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recipes/v2", tags=["recipes-v2"])


class RecipeResponse(BaseModel):
    """Recipe summary response"""
    id: int
    title: str
    description: Optional[str]
    goals: List[str]
    tags: List[str]
    dietary_tags: List[str]
    suitable_meal_times: List[str]
    cuisine: Optional[str]
    prep_time_min: Optional[int]
    cook_time_min: Optional[int]
    difficulty_level: Optional[str]
    servings: int
    macros_per_serving: Dict
    instructions: List[str]
    meal_prep_notes: Optional[str]
    chef_tips: Optional[str]
    image_url: Optional[str] = None

    class Config:
        orm_mode = True


class IngredientResponse(BaseModel):
    """Ingredient in recipe"""
    item_id: int
    item_name: str
    quantity_grams: float
    is_optional: bool
    preparation_notes: Optional[str]


class RecipeDetailResponse(BaseModel):
    """Detailed recipe with ingredients"""
    id: int
    title: str
    description: Optional[str]
    goals: List[str]
    tags: List[str]
    dietary_tags: List[str]
    suitable_meal_times: List[str]
    cuisine: Optional[str]
    prep_time_min: Optional[int]
    cook_time_min: Optional[int]
    difficulty_level: Optional[str]
    servings: int
    macros_per_serving: Dict
    instructions: List[str]
    meal_prep_notes: Optional[str]
    chef_tips: Optional[str]
    image_url: Optional[str] = None
    ingredients: List[IngredientResponse]

    class Config:
        orm_mode = True


@router.get("/", response_model=List[RecipeResponse])
async def search_recipes(
    goal: Optional[str] = Query(None, description="Filter by goal"),
    dietary_type: Optional[str] = Query(None, description="Filter by dietary type"),
    meal_time: Optional[str] = Query(None, description="Filter by meal time"),
    max_prep_time: Optional[int] = Query(None, description="Maximum prep time in minutes"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    recipe_repo: RecipeRepository = Depends(get_recipe_repository)
):
    try:
        logger.info(f"GET /recipes/v2/ - Filters: goal={goal}, dietary={dietary_type}, meal_time={meal_time}")

        recipes = await recipe_repo.search(
            goal=goal,
            dietary_type=dietary_type,
            meal_time=meal_time,
            max_prep_time=max_prep_time,
            cuisine=cuisine,
            search_term=search,
            limit=limit,
            offset=offset
        )

        recipe_list = []
        for recipe in recipes:
            recipe_dict = {
                "id": recipe.id,
                "title": recipe.title,
                "description": recipe.description,
                "goals": recipe.goals or [],
                "tags": recipe.tags or [],
                "dietary_tags": recipe.dietary_tags or [],
                "suitable_meal_times": recipe.suitable_meal_times or [],
                "cuisine": recipe.cuisine,
                "prep_time_min": recipe.prep_time_min,
                "cook_time_min": recipe.cook_time_min,
                "difficulty_level": recipe.difficulty_level,
                "servings": recipe.servings,
                "macros_per_serving": recipe.macros_per_serving or {},
                "instructions": recipe.instructions or [],
                "meal_prep_notes": recipe.meal_prep_notes,
                "chef_tips": recipe.chef_tips,
                "image_url": recipe.image_url
            }
            recipe_list.append(recipe_dict)

        return recipe_list

    except Exception as e:
        logger.error(f"Error searching recipes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search recipes: {str(e)}"
        )


@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe(
    recipe_id: int,
    recipe_repo: RecipeRepository = Depends(get_recipe_repository)
):
    try:
        logger.info(f"GET /recipes/v2/{recipe_id}")

        result = await recipe_repo.get_with_ingredients(recipe_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipe not found"
            )

        recipe = result["recipe"]
        ingredients = result["ingredients"]

        return {
            "id": recipe.id,
            "title": recipe.title,
            "description": recipe.description,
            "goals": recipe.goals or [],
            "tags": recipe.tags or [],
            "dietary_tags": recipe.dietary_tags or [],
            "suitable_meal_times": recipe.suitable_meal_times or [],
            "cuisine": recipe.cuisine,
            "prep_time_min": recipe.prep_time_min,
            "cook_time_min": recipe.cook_time_min,
            "difficulty_level": recipe.difficulty_level,
            "servings": recipe.servings,
            "macros_per_serving": recipe.macros_per_serving or {},
            "instructions": recipe.instructions or [],
            "meal_prep_notes": recipe.meal_prep_notes,
            "chef_tips": recipe.chef_tips,
            "image_url": recipe.image_url,
            "ingredients": ingredients
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recipe {recipe_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recipe: {str(e)}"
        )