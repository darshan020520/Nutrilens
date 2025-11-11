# backend/app/api/meal_plans.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from app.models.database import get_db
from app.services.auth import get_current_user_dependency as get_current_user
from app.models.database import User
from app.services.meal_plan_service import MealPlanService
from app.agents.planning_agent import PlanningAgent
from app.schemas.meal_plan import (
    MealPlanCreate,
    MealPlanResponse,
    MealPlanUpdate,
    MealSwapRequest,
    MealLogCreate,
    GeneratePlanRequest,
    AlternativesResponse,
    GroceryListResponse,
    EatingOutRequest
)

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])

@router.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: GeneratePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    
):
    """
    Generate a new optimized meal plan using AI agent
    """
    try:
        # Initialize planning agent
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        print("generating new meal plan")
        print("current user id", current_user.id)
        
        # Generate plan
        result = agent.generate_weekly_meal_plan(
            user_id=current_user.id,
            start_date=request.start_date or datetime.now(),
            preferences=request.preferences
        )
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/current")
async def get_current_meal_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's current active meal plan for this week.
    Returns 200 with has_plan=False if no plan exists.
    """
    service = MealPlanService(db)
    plan = service.get_active_meal_plan(current_user.id)

    if not plan:
        # Return empty state instead of 404 for better UX
        from datetime import datetime, timedelta
        today = datetime.now().date()
        days_since_monday = today.weekday()
        current_week_start = today - timedelta(days=days_since_monday)

        return {
            "id": None,
            "has_plan": False,
            "week_start_date": current_week_start.isoformat(),
            "plan_data": None,
            "message": "No meal plan found for this week. Generate a new plan to get started!"
        }

    return plan

@router.get("/current/with-status")
async def get_current_meal_plan_with_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's current active meal plan with meal log status enriched.
    Adds 'status' field to each meal indicating if it's logged/pending/skipped.
    """
    from app.models.database import MealLog
    from sqlalchemy import and_, func

    service = MealPlanService(db)
    plan = service.get_active_meal_plan(current_user.id)

    if not plan:
        today = datetime.now().date()
        days_since_monday = today.weekday()
        current_week_start = today - timedelta(days=days_since_monday)

        return {
            "id": None,
            "has_plan": False,
            "week_start_date": current_week_start.isoformat(),
            "plan_data": None,
            "message": "No meal plan found for this week. Generate a new plan to get started!"
        }

    # Get meal logs for status mapping
    # Normalize week_start to midnight to include all meals on the first day
    week_start = plan.week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    meal_logs = db.query(MealLog).filter(
        and_(
            MealLog.user_id == current_user.id,
            MealLog.meal_plan_id == plan.id,  # Only get logs for this specific meal plan
            MealLog.planned_datetime >= week_start,
            MealLog.planned_datetime < week_end
        )
    ).all()

    # Create status lookup map
    status_map = {}
    for log in meal_logs:
        key = f"{log.planned_datetime.date()}_{log.meal_type}"
        if log.consumed_datetime:
            status_map[key] = "logged"
            print(f"DEBUG LOG: {log.id} - {key} - consumed_datetime={log.consumed_datetime} -> LOGGED")
        elif log.was_skipped:
            status_map[key] = "skipped"
            print(f"DEBUG LOG: {log.id} - {key} - was_skipped=True -> SKIPPED")
        else:
            status_map[key] = "pending"
            print(f"DEBUG LOG: {log.id} - {key} - consumed={log.consumed_datetime}, skipped={log.was_skipped} -> PENDING")

    print(f"DEBUG: Status map created with {len(status_map)} entries:")
    print(f"DEBUG: Status map: {status_map}")

    # Enrich plan_data with status
    enriched_plan_data = {}
    plan_data = plan.plan_data.get('week_plan', plan.plan_data)  # Handle both structures

    for day_index in range(7):
        day_key = f"day_{day_index}"
        day_data = plan_data.get(day_key)

        if not day_data:
            continue

        day_date = week_start + timedelta(days=day_index)
        enriched_meals = {}

        for meal_type, meal_recipe in day_data.get('meals', {}).items():
            if not meal_recipe:
                enriched_meals[meal_type] = None
                continue

            # Get status from logs
            status_key = f"{day_date.date()}_{meal_type}"
            status = status_map.get(status_key, "pending")
            print(f"DEBUG: Looking for key '{status_key}', found status: '{status}'")

            # Add status to meal data
            enriched_meal = {**meal_recipe, "status": status}
            enriched_meals[meal_type] = enriched_meal

        enriched_plan_data[day_key] = {
            **day_data,
            "meals": enriched_meals
        }

    # Return plan with enriched data
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "week_start_date": plan.week_start_date.isoformat(),
        "plan_data": enriched_plan_data,
        "grocery_list": plan.grocery_list,
        "total_calories": plan.total_calories,
        "avg_macros": plan.avg_macros,
        "is_active": plan.is_active,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "has_plan": True
    }

@router.get("/{plan_id}", response_model=MealPlanResponse)
async def get_meal_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific meal plan by ID
    """
    service = MealPlanService(db)
    plan = service.get_meal_plan_by_id(plan_id, current_user.id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    
    return plan

@router.put("/{plan_id}/adjust")
async def adjust_meal_plan(
    plan_id: int,
    updates: MealPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update/adjust existing meal plan
    """
    try:
        service = MealPlanService(db)
        updated_plan = service.update_meal_plan(plan_id, current_user.id, updates)
        return updated_plan
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{recipe_id}/alternatives", response_model=List[Dict])
async def get_recipe_alternatives(
    recipe_id: int,
    count: int = Query(5, ge=1, le=10, description="Number of alternatives to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get alternative recipes with similar macros and compatible meal times.
    Uses PlanningAgent which delegates to MealPlanService for consistency.
    """
    try:
        # Initialize agent with user context
        from app.agents.planning_agent import AgentContext
        context = AgentContext(
            user_id=current_user.id,
            active_meal_plan=None,
            inventory={},
            user_profile=None,
            user_goal=None,
            preferences=None
        )

        agent = PlanningAgent(db, context=context)
        alternatives = agent.find_recipe_alternatives(recipe_id, count)

        if not alternatives:
            raise HTTPException(status_code=404, detail="No alternative recipes found")

        return alternatives

    except HTTPException:
        # re-raise custom HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alternatives: {str(e)}")

@router.post("/{plan_id}/swap-meal")
async def swap_meal(
    plan_id: int,
    swap_request: MealSwapRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Swap a meal in the plan with a different recipe
    """
    try:
        service = MealPlanService(db)
        result = service.swap_meal(current_user.id, swap_request)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{plan_id}/alternatives/{recipe_id}", response_model=List[AlternativesResponse])
async def get_meal_alternatives(
    plan_id: int,
    recipe_id: int,
    count: int = Query(5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get alternative recipes with similar macros for meal swapping

    Filters by:
    - Meal time compatibility
    - Calorie range (±30%)
    - User's dietary restrictions

    Scores by:
    - Macro similarity (calories, protein, carbs, fat)
    - Goal alignment bonus
    """
    service = MealPlanService(db)
    alternatives = service.get_alternatives_for_meal(recipe_id, current_user.id, count)
    return alternatives

@router.get("/{plan_id}/grocery-list", response_model=GroceryListResponse)
async def get_grocery_list(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregated grocery list for meal plan
    """
    try:
        # Get meal plan
        service = MealPlanService(db)
        plan = service.get_meal_plan_by_id(plan_id, current_user.id)
        
        if not plan:
            raise HTTPException(status_code=404, detail="Meal plan not found")
        
        # Calculate grocery list using agent
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        grocery_list = agent.calculate_grocery_list(plan.dict()['plan_data'], db_session=db, user_id=current_user.id)
        return grocery_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/log-meal")
async def log_meal_consumption(
    meal_log: MealLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log meal consumption and update inventory
    """
    try:
        service = MealPlanService(db)
        result = service.log_meal_consumption(current_user.id, meal_log)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/meals")
async def get_meal_history(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's meal consumption history
    """
    service = MealPlanService(db)
    history = service.get_meal_history(current_user.id, days)
    return {"history": history, "days": days, "total_meals": len(history)}

@router.post("/eating-out")
async def adjust_for_eating_out(
    payload: EatingOutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Suggest adjusted meals when eating out (agent function).
    Returns suggestions only; does not modify the DB.
    """
    try:
        # Initialize agent with user context
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        
        # Call agent function to get suggested adjustments
        suggestions = agent.adjust_plan_for_eating_out(
            day=payload.day,
            meal=payload.meal_type,
            restaurant_calories=payload.external_calories
        )
        return suggestions

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/meal-prep-suggestions")
async def get_meal_prep_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get meal prep suggestions for active plan
    """
    try:
        # Get active plan
        service = MealPlanService(db)
        plan = service.get_active_meal_plan(current_user.id)
        
        if not plan:
            raise HTTPException(status_code=404, detail="No active meal plan")
        
        # Get suggestions from agent
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        suggestions = agent.suggest_meal_prep(plan.dict()['plan_data'])
        
        return suggestions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk-cooking-suggestions")
async def get_bulk_cooking_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get bulk cooking suggestions for efficiency
    """
    try:
        # Get active plan
        service = MealPlanService(db)
        plan = service.get_active_meal_plan(current_user.id)
        
        if not plan:
            raise HTTPException(status_code=404, detail="No active meal plan")
        
        # Get suggestions from agent
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        suggestions = agent.bulk_cooking_suggestions(plan.dict())
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shopping/reminders")
async def get_shopping_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get smart shopping reminders
    """
    try:
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        reminders = agent.generate_shopping_reminders()
        
        return {"reminders": reminders}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/optimize-inventory")
async def optimize_for_inventory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recipes that prioritize expiring inventory items
    """
    try:
        agent = PlanningAgent(db)
        await agent.initialize_context(current_user.id)
        result = agent.optimize_inventory_usage()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))