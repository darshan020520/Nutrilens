# backend/app/api/meal_dashboard.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.models.database import (
    get_db, User, MealPlan, MealLog, Recipe, 
    UserProfile, UserGoal, RecipeIngredient
)
from app.services.auth import get_current_user_dependency as get_current_user

router = APIRouter(prefix="/meal/dashboard", tags=["Meal Dashboard"])
logger = logging.getLogger(__name__)


@router.get("/week")
def get_week_meal_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current week's meal plan with status
    Returns 7 days of meals with logged/pending/skipped status
    """
    try:
        # Get user's active meal plan
        active_plan = db.query(MealPlan).filter(
            and_(
                MealPlan.user_id == current_user.id,
                MealPlan.is_active == True
            )
        ).first()
        
        if not active_plan:
            return {
                "has_plan": False,
                "message": "No active meal plan. Generate one to get started!",
                "days": []
            }
        
        # Parse plan_data - handle both flat and nested structures
        plan_data = active_plan.plan_data
        week_plan = plan_data.get('week_plan', plan_data)  # Support both structures

        # Get all meal logs for this week to determine status
        week_start = active_plan.week_start_date
        week_end = week_start + timedelta(days=7)

        meal_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == current_user.id,
                MealLog.planned_datetime >= week_start,
                MealLog.planned_datetime < week_end
            )
        ).all()

        # Create lookup for meal status
        meal_status_map = {}
        for log in meal_logs:
            key = f"{log.planned_datetime.date()}_{log.meal_type}"
            if log.consumed_datetime:
                meal_status_map[key] = "logged"
            elif log.was_skipped:
                meal_status_map[key] = "skipped"
            else:
                meal_status_map[key] = "pending"

        # Format week data - iterate through day_0 to day_6
        week_meals = []

        for day_index in range(7):
            day_key = f"day_{day_index}"
            day_data = week_plan.get(day_key)

            if not day_data:
                continue

            day_date = week_start + timedelta(days=day_index)
            day_meals = []

            for meal_type, meal_recipe in day_data.get('meals', {}).items():
                if not meal_recipe:
                    continue

                # Get status from meal logs using date + meal_type
                meal_key = f"{day_date.date()}_{meal_type}"
                status = meal_status_map.get(meal_key, "pending")

                day_meals.append({
                    "meal_type": meal_type,
                    "recipe_id": meal_recipe.get('id') or meal_recipe.get('recipe_id'),
                    "recipe_name": meal_recipe.get('title', 'Unknown Recipe'),
                    "macros": meal_recipe.get('macros_per_serving', {}),
                    "status": status
                })

            week_meals.append({
                "date": day_date.date().isoformat(),
                "day_name": day_date.strftime("%A"),
                "meals": day_meals
            })
        
        return {
            "has_plan": True,
            "plan_id": active_plan.id,
            "week_start": week_start.date().isoformat(),
            "week_end": week_end.date().isoformat(),
            "days": week_meals,
            "grocery_list": active_plan.grocery_list
        }
        
    except Exception as e:
        logger.error(f"Error fetching week meal plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/today")
def get_today_meals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get today's meals with real-time macro progress
    Returns today's planned meals and current macro totals
    """
    try:
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Get today's meal logs
        meal_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == current_user.id,
                MealLog.planned_datetime >= today_start,
                MealLog.planned_datetime <= today_end
            )
        ).order_by(MealLog.planned_datetime).all()
        
        # Get user's daily targets
        profile = db.query(UserProfile).filter(
            UserProfile.user_id == current_user.id
        ).first()
        
        goal = db.query(UserGoal).filter(
            UserGoal.user_id == current_user.id,
            UserGoal.is_active == True
        ).first()
        
        target_calories = profile.goal_calories if profile else 2000
        macro_targets = goal.macro_targets if goal else {
            "protein": 0.30,
            "carbs": 0.40,
            "fat": 0.30
        }
        
        # Calculate current totals
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        meals = []
        for log in meal_logs:
            recipe = log.recipe
            if not recipe:
                continue
            
            macros = recipe.macros_per_serving
            portion = log.portion_multiplier or 1.0
            
            meal_calories = macros.get("calories", 0) * portion
            meal_protein = macros.get("protein_g", 0) * portion
            meal_carbs = macros.get("carbs_g", 0) * portion
            meal_fat = macros.get("fat_g", 0) * portion
            
            # Add to totals if consumed
            if log.consumed_datetime:
                total_calories += meal_calories
                total_protein += meal_protein
                total_carbs += meal_carbs
                total_fat += meal_fat
            
            # Determine status
            if log.consumed_datetime:
                status = "logged"
            elif log.was_skipped:
                status = "skipped"
            else:
                status = "pending"
            
            meals.append({
                "meal_log_id": log.id,
                "meal_type": log.meal_type,
                "recipe_id": recipe.id,
                "recipe_name": recipe.title,
                "planned_time": log.planned_datetime.strftime("%H:%M"),
                "consumed_time": log.consumed_datetime.strftime("%H:%M") if log.consumed_datetime else None,
                "status": status,
                "macros": {
                    "calories": round(meal_calories, 1),
                    "protein": round(meal_protein, 1),
                    "carbs": round(meal_carbs, 1),
                    "fat": round(meal_fat, 1)
                },
                "portion": portion
            })
        
        # Calculate targets in grams
        target_protein_g = (target_calories * macro_targets["protein"]) / 4
        target_carbs_g = (target_calories * macro_targets["carbs"]) / 4
        target_fat_g = (target_calories * macro_targets["fat"]) / 9
        
        return {
            "date": today.isoformat(),
            "meals": meals,
            "totals": {
                "calories": round(total_calories, 1),
                "protein": round(total_protein, 1),
                "carbs": round(total_carbs, 1),
                "fat": round(total_fat, 1)
            },
            "targets": {
                "calories": round(target_calories, 1),
                "protein": round(target_protein_g, 1),
                "carbs": round(target_carbs_g, 1),
                "fat": round(target_fat_g, 1)
            },
            "progress": {
                "calories": round((total_calories / target_calories * 100), 1) if target_calories > 0 else 0,
                "protein": round((total_protein / target_protein_g * 100), 1) if target_protein_g > 0 else 0,
                "carbs": round((total_carbs / target_carbs_g * 100), 1) if target_carbs_g > 0 else 0,
                "fat": round((total_fat / target_fat_g * 100), 1) if target_fat_g > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching today's meals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recipes")
def browse_recipes(
    search: Optional[str] = None,
    goal: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_prep_time: Optional[int] = None,
    max_calories: Optional[int] = None,
    sort_by: str = Query("relevance", regex="^(relevance|protein|calories|prep_time)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Browse recipe library with filters
    """
    try:
        query = db.query(Recipe)
        
        # Search filter
        if search:
            query = query.filter(
                Recipe.title.ilike(f"%{search}%")
            )
        
        # Goal filter (assumes recipes have goals JSON array)
        if goal:
            query = query.filter(
                func.json_contains(Recipe.goals, f'"{goal}"')
            )
        
        # Cuisine filter (assumes recipes have cuisine_type field)
        if cuisine:
            query = query.filter(Recipe.cuisine_type == cuisine)
        
        # Prep time filter (assumes recipes have prep_time_minutes field)
        if max_prep_time:
            query = query.filter(Recipe.prep_time_minutes <= max_prep_time)
        
        # Calories filter
        if max_calories:
            # Note: This is a simplified filter, might need adjustment based on your JSON structure
            pass
        
        # Sorting
        if sort_by == "protein":
            # Simplified - you might need to adjust based on JSON structure
            query = query.order_by(desc(Recipe.id))  # Placeholder
        elif sort_by == "calories":
            query = query.order_by(desc(Recipe.id))  # Placeholder
        elif sort_by == "prep_time":
            query = query.order_by(Recipe.prep_time_minutes)
        else:  # relevance
            query = query.order_by(desc(Recipe.id))
        
        # Get total count
        total = query.count()
        
        # Pagination
        recipes = query.offset(offset).limit(limit).all()
        
        return {
            "recipes": [
                {
                    "id": recipe.id,
                    "title": recipe.title,
                    "cuisine_type": recipe.cuisine_type,
                    "prep_time_minutes": recipe.prep_time_minutes,
                    "macros": recipe.macros_per_serving,
                    "goals": recipe.goals,
                    "suitable_meal_times": recipe.suitable_meal_times
                }
                for recipe in recipes
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        }
        
    except Exception as e:
        logger.error(f"Error browsing recipes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
def get_meal_history(
    days: int = Query(7, ge=1, le=90, description="Number of days of history"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get meal logging history with statistics
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get meal logs
        meal_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == current_user.id,
                MealLog.planned_datetime >= start_date,
                MealLog.planned_datetime <= end_date
            )
        ).order_by(desc(MealLog.planned_datetime)).all()
        
        # Calculate statistics
        total_meals = len(meal_logs)
        logged_meals = sum(1 for log in meal_logs if log.consumed_datetime)
        skipped_meals = sum(1 for log in meal_logs if log.was_skipped)
        
        adherence_rate = (logged_meals / total_meals * 100) if total_meals > 0 else 0
        
        # Group by date
        meals_by_date = {}
        for log in meal_logs:
            date_key = log.planned_datetime.date().isoformat()
            if date_key not in meals_by_date:
                meals_by_date[date_key] = []
            
            recipe = log.recipe
            meals_by_date[date_key].append({
                "meal_type": log.meal_type,
                "recipe_name": recipe.title if recipe else "Unknown",
                "status": "logged" if log.consumed_datetime else ("skipped" if log.was_skipped else "pending"),
                "time": log.consumed_datetime.strftime("%H:%M") if log.consumed_datetime else None
            })
        
        return {
            "period": {
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "days": days
            },
            "statistics": {
                "total_meals": total_meals,
                "logged_meals": logged_meals,
                "skipped_meals": skipped_meals,
                "adherence_rate": round(adherence_rate, 1)
            },
            "history": [
                {
                    "date": date,
                    "meals": meals
                }
                for date, meals in sorted(meals_by_date.items(), reverse=True)
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching meal history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))