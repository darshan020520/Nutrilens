from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from app.models.database import get_db, Recipe, RecipeIngredient, Item
from sqlalchemy import and_, or_, func, cast, String
from pydantic import BaseModel

router = APIRouter(prefix="/recipes", tags=["Recipes"])

# Response model for recipes
class RecipeResponse(BaseModel):
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
    
    class Config:
        orm_mode = True

@router.get("/")
def get_recipes(
    goal: Optional[str] = Query(None, description="Filter by goal"),
    dietary_type: Optional[str] = Query(None, description="Filter by dietary type"),
    meal_time: Optional[str] = Query(None, description="Filter by meal time"),
    max_prep_time: Optional[int] = Query(None, description="Maximum prep time in minutes"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get recipes with filters"""
    query = db.query(Recipe)
    
    # Apply filters
    if goal:
        # For JSON arrays in PostgreSQL
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
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Recipe.title.ilike(search_term),
                Recipe.description.ilike(search_term)
            )
        )
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    recipes = query.offset(offset).limit(limit).all()
    
    # Convert to response format
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
            "chef_tips": recipe.chef_tips
        }
        recipe_list.append(recipe_dict)
    
    return recipe_list

@router.get("/stats/summary")
def get_recipe_stats(db: Session = Depends(get_db)):
    """Get recipe database statistics"""
    total_recipes = db.query(Recipe).count()
    total_items = db.query(Item).count()
    
    # Count by goal (using JSON cast for PostgreSQL)
    goals_stats = {}
    for goal in ['muscle_gain', 'fat_loss', 'body_recomp', 'general_health', 'endurance', 'weight_training']:
        count = db.query(Recipe).filter(
            cast(Recipe.goals, String).contains(goal)
        ).count()
        goals_stats[goal] = count
    
    # Count by meal time
    meal_time_stats = {}
    for meal in ['breakfast', 'lunch', 'dinner', 'snack']:
        count = db.query(Recipe).filter(
            cast(Recipe.suitable_meal_times, String).contains(meal)
        ).count()
        meal_time_stats[meal] = count
    
    # Count by dietary type
    dietary_stats = {}
    for diet in ['vegetarian', 'non_vegetarian', 'vegan']:
        count = db.query(Recipe).filter(
            cast(Recipe.dietary_tags, String).contains(diet)
        ).count()
        dietary_stats[diet] = count
    
    # Count by cuisine
    cuisine_stats = {}
    cuisines = db.query(Recipe.cuisine).distinct().all()
    for (cuisine,) in cuisines:
        if cuisine:
            count = db.query(Recipe).filter(Recipe.cuisine == cuisine).count()
            cuisine_stats[cuisine] = count
    
    return {
        "total_recipes": total_recipes,
        "total_items": total_items,
        "by_goal": goals_stats,
        "by_meal_time": meal_time_stats,
        "by_dietary_type": dietary_stats,
        "by_cuisine": cuisine_stats
    }

@router.get("/{recipe_id}")
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Get a specific recipe by ID"""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    # Get ingredients with item names
    ingredients = db.query(
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
        "ingredients": ingredient_list
    }

@router.get("/goals/{goal_type}")
def get_recipes_by_goal(
    goal_type: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recipes for a specific goal"""
    recipes = db.query(Recipe).filter(
        cast(Recipe.goals, String).contains(goal_type)
    ).limit(limit).all()
    
    recipe_list = []
    for recipe in recipes:
        recipe_list.append({
            "id": recipe.id,
            "title": recipe.title,
            "description": recipe.description,
            "prep_time_min": recipe.prep_time_min,
            "macros_per_serving": recipe.macros_per_serving or {}
        })
    
    return {
        "goal": goal_type,
        "count": len(recipes),
        "recipes": recipe_list
    }

@router.get("/meal-time/{meal_type}")
def get_recipes_by_meal_time(
    meal_type: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recipes suitable for a specific meal time"""
    recipes = db.query(Recipe).filter(
        cast(Recipe.suitable_meal_times, String).contains(meal_type)
    ).limit(limit).all()
    
    recipe_list = []
    for recipe in recipes:
        recipe_list.append({
            "id": recipe.id,
            "title": recipe.title,
            "description": recipe.description,
            "prep_time_min": recipe.prep_time_min,
            "macros_per_serving": recipe.macros_per_serving or {}
        })
    
    return {
        "meal_time": meal_type,
        "count": len(recipes),
        "recipes": recipe_list
    }

@router.get("/search/semantic")
async def semantic_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Semantic search for recipes (placeholder for vector search)
    Currently does text search, will be enhanced with embeddings later
    """
    search_term = f"%{query}%"
    recipes = db.query(Recipe).filter(
        or_(
            Recipe.title.ilike(search_term),
            Recipe.description.ilike(search_term),
            cast(Recipe.tags, String).ilike(search_term)
        )
    ).limit(limit).all()
    
    recipe_list = []
    for recipe in recipes:
        recipe_list.append({
            "id": recipe.id,
            "title": recipe.title,
            "description": recipe.description,
            "tags": recipe.tags or [],
            "macros_per_serving": recipe.macros_per_serving or {}
        })
    
    return {
        "query": query,
        "count": len(recipes),
        "recipes": recipe_list
    }