from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import logging

from app.models.database import User
from app.schemas.user import (
    ProfileCreate,
    GoalCreate, PathSelection, PreferenceCreate,
    OnboardingTargets, BasicInfoResponse, TargetLockCreate
)
from app.services.onboarding import OnboardingService
from app.dependencies import get_onboarding_service, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding/v2", tags=["onboarding-v2"])


class StepResponse(BaseModel):
    success: bool
    data: dict
    message: str
    next_step: Optional[str] = None
    redirect_to: Optional[str] = None

    class Config:
        orm_mode = True


@router.post("/basic-info", response_model=BasicInfoResponse)
async def submit_basic_info(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):

    profile = await onboarding_service.complete_basic_info(
        current_user.id,
        profile_data.dict(),
        current_user.onboarding_started_at
    )

    return {
        "success": True,
        "data": profile,
        "message": "Basic information saved successfully",
        "next_step": "/onboarding/goal-selection"
    }


@router.post("/goal-selection", response_model=StepResponse)
async def select_goal(
    goal_data: GoalCreate,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):

    if not current_user.basic_info_completed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PREREQUISITE_NOT_MET",
                "message": "Please complete basic information first",
                "redirect_to": "/onboarding/basic-info"
            }
        )

    goal = await onboarding_service.complete_goal_selection(
        current_user.id,
        goal_data.dict()
    )

    return StepResponse(
        success=True,
        data={
            "goal_type": goal.goal_type,
            "macro_targets": goal.macro_targets
        },
        message="Goal set successfully",
        next_step="/onboarding/path-selection"
    )


@router.post("/path-selection", response_model=StepResponse)
async def select_path(
    path_data: PathSelection,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):
    if not current_user.goal_selection_completed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PREREQUISITE_NOT_MET",
                "message": "Please complete goal selection first",
                "redirect_to": "/onboarding/goal-selection"
            }
        )


    path = await onboarding_service.complete_path_selection(
        current_user.id,
        path_data.dict()
    )

    return StepResponse(
        success=True,
        data={
            "path_type": path.path_type,
            "meals_per_day": path.meals_per_day,
            "meal_windows": path.meal_windows
        },
        message="Path set successfully",
        next_step="/onboarding/preferences"
    )


@router.post("/preferences", response_model=StepResponse)
async def set_preferences(
    pref_data: PreferenceCreate,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):

    if not current_user.path_selection_completed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PREREQUISITE_NOT_MET",
                "message": "Please complete path selection first",
                "redirect_to": "/onboarding/path-selection"
            }
        )

    preferences = await onboarding_service.complete_preferences(
        current_user.id,
        pref_data.dict()
    )

    return StepResponse(
        success=True,
        data={
            "dietary_type": preferences.dietary_type,
            "allergies": preferences.allergies
        },
        message="Onboarding complete! Welcome to NutriLens AI.",
        redirect_to="/dashboard"
    )


@router.get("/calculated-targets", response_model=OnboardingTargets)
async def get_calculated_targets(
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):
    try:
        targets = await onboarding_service.get_calculated_targets(current_user.id)
        return targets
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/lock-targets", response_model=StepResponse)
async def lock_targets(
    lock_data: TargetLockCreate,
    current_user: User = Depends(get_current_user),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):
    try:
        goal = await onboarding_service.lock_macro_targets(current_user.id, lock_data.dict())
        return StepResponse(
            success=True,
            data={
                "goal_type": goal.goal_type,
                "macro_targets": goal.macro_targets,
                "goal_calories": lock_data.goal_calories,
            },
            message="Targets locked successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
