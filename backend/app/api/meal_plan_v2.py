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
from app.models.database import User
from app.dependencies import (
    get_meal_plan_orchestrator,
    get_constraint_builder_service,
    get_grocery_service,
    get_meal_plan_service_v2,
    get_current_user
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
    Generate a new optimized meal plan using clean architecture.

    Uses Orchestrator → Service → Repository pattern.
    Orchestrator now fetches meal_windows internally via repository.
    """
    try:
        # Build optimization constraints using service
        # Uses UserProfileRepository internally (no more direct DB queries)
        constraints = await constraint_builder.build_constraints(current_user.id)

        # Generate plan using orchestrator
        # Orchestrator fetches meal_windows internally
        result = await orchestrator.generate_weekly_meal_plan(
            user_id=current_user.id,
            start_date=request.start_date or datetime.now(),
            constraints=constraints,
            current_inventory=None  # TODO: Get from inventory service
        )

        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_v2.get("/current/with-status")
async def get_current_meal_plan_with_status_v2(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    current_user: User = Depends(get_current_user)
):
    """
    Get user's current active meal plan with meal log status enriched.
    Adds 'status' field to each meal indicating if it's logged/pending/skipped.

    REFACTORED: Business logic moved to MealPlanServiceV2.get_active_meal_plan_with_status()
    API layer is now thin - just calls service and returns result.
    """
    return await meal_plan_service.get_active_meal_plan_with_status(current_user.id)


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
        grocery_list = await grocery_service.calculate_for_plan(
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
