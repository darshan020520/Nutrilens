from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import List

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
from app.core.ist_datetime import now_ist


router_v2 = APIRouter(prefix="/meal-plans/v2", tags=["meal-plans-v2"])


@router_v2.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan_v2(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    constraint_builder: ConstraintBuilderService = Depends(get_constraint_builder_service),
    current_user: User = Depends(get_current_user)
):
    try:
        constraints = await constraint_builder.build_constraints(current_user.id)

        result = await orchestrator.generate_weekly_meal_plan(
            user_id=current_user.id,
            start_date=request.start_date or now_ist(),
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
    return await meal_plan_service.get_active_meal_plan_with_status(current_user.id)


@router_v2.get("/{plan_id}/grocery-list", response_model=GroceryListResponse)
async def get_grocery_list_v2(
    plan_id: int,
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    grocery_service: GroceryService = Depends(get_grocery_service),
    current_user: User = Depends(get_current_user)
):
    try:
        plan = await meal_plan_service.get_meal_plan_by_id(plan_id, current_user.id)

        if not plan:
            raise HTTPException(status_code=404, detail="Meal plan not found")

        plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan.dict()
        grocery_list = await grocery_service.calculate_for_plan(
            plan_dict['plan_data'],
            current_user.id
        )
        return grocery_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_v2.post("/{plan_id}/swap-meal")
async def swap_meal_v2(
    plan_id: int,
    swap_request: MealSwapRequest,
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    current_user: User = Depends(get_current_user)
):

    try:
        result = await meal_plan_service.swap_meal(current_user.id, swap_request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_v2.get("/{plan_id}/alternatives/{recipe_id}", response_model=List[AlternativesResponse])
async def get_meal_alternatives_v2(
    plan_id: int,
    recipe_id: int,
    count: int = Query(5, ge=1, le=10),
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    current_user: User = Depends(get_current_user)
):

    alternatives = await meal_plan_service.get_alternatives_for_meal(recipe_id, current_user.id, count)
    return alternatives

