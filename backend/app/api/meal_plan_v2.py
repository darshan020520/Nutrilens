"""
Meal Plan API V2 - Using New Architecture

New endpoints using Orchestrator → Service → Repository pattern.

Runs SIDE-BY-SIDE with old meal_plan.py endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import Optional, List

from app.schemas.meal_plan import (
    GeneratePlanRequest, MealPlanResponse, GroceryListResponse,
    MealSwapRequest, AlternativesResponse
)
from app.services.auth import get_current_user_dependency as get_current_user
from app.models.database import User
from datetime import timedelta
from app.dependencies import (
    get_meal_plan_orchestrator,
    get_user_meal_windows,
    get_constraint_builder_service,
    get_grocery_service,
    get_meal_plan_service_v2,
    get_meal_log_repository
)
from app.orchestrators.meal_plan_orchestrator import MealPlanOrchestrator
from app.services.constraint_builder_service import ConstraintBuilderService
from app.services.grocery_service import GroceryService
from app.services.meal_plan_service_v2 import MealPlanServiceV2
from app.schemas.meal_plan import GroceryListResponse


router_v2 = APIRouter(prefix="/meal-plans/v2", tags=["meal-plans-v2"])


@router_v2.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan_v2(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    constraint_builder: ConstraintBuilderService = Depends(get_constraint_builder_service),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a new optimized meal plan using new architecture.

    NEW IMPLEMENTATION using Orchestrator → Service → Repository.

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan.py:27-57
    ONLY CHANGE: Uses orchestrator instead of agent
    """
    try:
        # COPY-PASTED FROM meal_plan.py:41-42 - NO CHANGES (kept print statements)
        print("generating new meal plan")
        print("current user id", current_user.id)

        # Get user's meal windows for meal log creation
        # COPY-PASTED FROM planning_agent.py:1034-1035 via dependency
        meal_windows = await get_user_meal_windows(
            user_id=current_user.id,
            current_user=current_user
        )

        # Build optimization constraints using service
        # BUSINESS LOGIC FROM: planning_agent.py:839-884
        constraints = constraint_builder.build_constraints(current_user.id)

        # Generate plan using orchestrator (replaces agent)
        # BUSINESS LOGIC IDENTICAL TO planning_agent.py:161-224
        result = await orchestrator.generate_weekly_meal_plan(
            user_id=current_user.id,
            start_date=request.start_date or datetime.now(),
            constraints=constraints,
            current_inventory=None,  # TODO: Get from inventory service
            user_meal_windows=meal_windows
        )

        # COPY-PASTED FROM meal_plan.py:51-52 - NO CHANGES
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        # COPY-PASTED FROM meal_plan.py:54 - NO CHANGES
        return result

    except Exception as e:
        # COPY-PASTED FROM meal_plan.py:57 - NO CHANGES
        raise HTTPException(status_code=500, detail=str(e))


@router_v2.get("/current/with-status")
async def get_current_meal_plan_with_status_v2(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    meal_log_repo = Depends(get_meal_log_repository),
    current_user: User = Depends(get_current_user)
):
    """
    Get user's current active meal plan with meal log status enriched.
    Adds 'status' field to each meal indicating if it's logged/pending/skipped.

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan.py:88-193
    ARCHITECTURE FIX: Now uses repository instead of direct DB access
    """
    # COPY-PASTED FROM meal_plan.py:100-114 - NO CHANGES
    plan = await meal_plan_service.get_active_meal_plan(current_user.id)

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

    # ARCHITECTURE FIX: Use repository instead of direct DB access
    # Original: meal_plan.py:116-133 (direct db.query)
    # Normalize week_start to midnight to include all meals on the first day
    week_start = plan.week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    meal_logs = await meal_log_repo.get_by_plan_and_date_range(
        user_id=current_user.id,
        meal_plan_id=plan.id,
        start_datetime=week_start,
        end_datetime=week_end
    )

    # COPY-PASTED FROM meal_plan.py:130-145 - NO CHANGES (kept print statements)
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

    # COPY-PASTED FROM meal_plan.py:147-178 - NO CHANGES
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

    # COPY-PASTED FROM meal_plan.py:180-193 - NO CHANGES
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


@router_v2.get("/{plan_id}/grocery-list", response_model=GroceryListResponse)
async def get_grocery_list_v2(
    plan_id: int,
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    grocery_service: GroceryService = Depends(get_grocery_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregated grocery list for meal plan.

    NEW IMPLEMENTATION using GroceryService.

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan.py:314-338
    """
    try:
        # COPY-PASTED FROM meal_plan.py:324-329 - NO CHANGES
        # Get meal plan by ID (FIXED: was using active plan, now uses plan_id parameter)
        plan = await meal_plan_service.get_meal_plan_by_id(plan_id, current_user.id)

        if not plan:
            raise HTTPException(status_code=404, detail="Meal plan not found")

        # COPY-PASTED FROM meal_plan.py:331-335 - NO CHANGES
        # Calculate grocery list using service (was agent, now service)
        plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan.dict()
        grocery_list = grocery_service.calculate_for_plan(
            plan_dict['plan_data'],
            current_user.id
        )
        return grocery_list

    except Exception as e:
        # COPY-PASTED FROM meal_plan.py:337-338 - NO CHANGES
        raise HTTPException(status_code=500, detail=str(e))


@router_v2.post("/{plan_id}/swap-meal")
async def swap_meal_v2(
    plan_id: int,
    swap_request: MealSwapRequest,
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    current_user: User = Depends(get_current_user)
):
    """
    Swap a meal in the plan with a different recipe.

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan.py:270-288
    """
    try:
        # COPY-PASTED FROM meal_plan.py:281-283 - NO CHANGES
        # Now uses new MealPlanServiceV2 with repository pattern
        result = await meal_plan_service.swap_meal(current_user.id, swap_request)
        return result

    except ValueError as e:
        # COPY-PASTED FROM meal_plan.py:285-286 - NO CHANGES
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # COPY-PASTED FROM meal_plan.py:287-288 - NO CHANGES
        raise HTTPException(status_code=500, detail=str(e))


@router_v2.get("/{plan_id}/alternatives/{recipe_id}", response_model=List[AlternativesResponse])
async def get_meal_alternatives_v2(
    plan_id: int,
    recipe_id: int,
    count: int = Query(5, ge=1, le=10),
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    current_user: User = Depends(get_current_user)
):
    """
    Get alternative recipes with similar macros for meal swapping.

    Filters by:
    - Meal time compatibility
    - Calorie range (±30%)
    - User's dietary restrictions

    Scores by:
    - Macro similarity (calories, protein, carbs, fat)
    - Goal alignment bonus

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan.py:290-312
    """
    # COPY-PASTED FROM meal_plan.py:310-312 - NO CHANGES
    # Now uses new MealPlanServiceV2 with repository pattern
    alternatives = await meal_plan_service.get_alternatives_for_meal(recipe_id, current_user.id, count)
    return alternatives


# Helper dependency for meal windows
async def get_user_meal_windows(
    user_id: int,
    current_user: User = Depends(get_current_user)
) -> list:
    """
    Get user's meal timing windows.

    This is a workaround until we properly extract this to a service.
    """
    from app.models.database import get_db, UserPath

    # This is not ideal - we're creating a new DB session
    # TODO: Pass db session properly through dependency chain
    from app.models.database import SessionLocal
    db = SessionLocal()
    try:
        user_path = db.query(UserPath).filter_by(user_id=user_id).first()
        meal_windows = user_path.meal_windows if user_path and user_path.meal_windows else []
        return meal_windows
    finally:
        db.close()
