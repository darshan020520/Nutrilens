"""
Onboarding API Endpoints V2 - Clean Architecture

Provides user onboarding endpoints using repository pattern.

MIGRATED FROM: onboarding.py
USES: Clean architecture with OnboardingRepository + OnboardingService
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import logging

from app.models.database import get_db, User
from app.schemas.user import (
    ProfileCreate, ProfileResponse,
    GoalCreate, PathSelection, PreferenceCreate,
    OnboardingTargets, BasicInfoResponse
)
from app.services.auth import get_current_user_dependency as get_current_user
from app.services.onboarding import OnboardingService
from app.repositories.onboarding_repository import OnboardingRepository
from app.dependencies import get_onboarding_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding/v2", tags=["onboarding-v2"])

# Singleton onboarding service
onboarding_service = OnboardingService()


# ===== RESPONSE SCHEMAS (IDENTICAL TO V1) =====

class StepResponse(BaseModel):
    """Generic step completion response"""
    success: bool
    data: dict
    message: str
    next_step: Optional[str] = None
    redirect_to: Optional[str] = None

    class Config:
        orm_mode = True


# ===== ENDPOINTS =====

@router.post("/basic-info", response_model=BasicInfoResponse)
async def submit_basic_info(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_user),
    onboarding_repo: OnboardingRepository = Depends(get_onboarding_repository),
    db: Session = Depends(get_db)
):
    """
    Submit basic user information.

    MIGRATED FROM: onboarding.py:27-55

    Uses:
    - OnboardingService for profile creation (with calculations - now uses repo internally)
    - OnboardingRepository for updating user's onboarding tracking fields
    """
    # Complete profile using service (which uses repository internally)
    print("going to create profile")
    profile = onboarding_service.complete_profile(
        db,
        current_user.id,
        profile_data.dict()
    )

    # Update onboarding tracking using repository
    step_updates = {
        "onboarding_started_at": datetime.utcnow() if not current_user.onboarding_started_at else current_user.onboarding_started_at,
        "basic_info_completed": True,
        "onboarding_current_step": 2
    }
    onboarding_repo.update_user_onboarding_step(current_user.id, step_updates)

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
    onboarding_repo: OnboardingRepository = Depends(get_onboarding_repository),
    db: Session = Depends(get_db)
):
    """
    Select fitness goal.

    MIGRATED FROM: onboarding.py:57-95

    Uses:
    - OnboardingService for goal creation (with calculations - now uses repo internally)
    - OnboardingRepository for updating user's onboarding tracking fields
    """
    # Validate prerequisite
    if not current_user.basic_info_completed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PREREQUISITE_NOT_MET",
                "message": "Please complete basic information first",
                "redirect_to": "/onboarding/basic-info"
            }
        )

    # Set goal using service (which uses repository internally)
    goal = onboarding_service.set_user_goal(
        db,
        current_user.id,
        goal_data.dict()
    )

    # Update onboarding tracking using repository
    step_updates = {
        "goal_selection_completed": True,
        "onboarding_current_step": 3
    }
    onboarding_repo.update_user_onboarding_step(current_user.id, step_updates)

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
    onboarding_repo: OnboardingRepository = Depends(get_onboarding_repository),
    db: Session = Depends(get_db)
):
    """
    Select eating path/strategy.

    MIGRATED FROM: onboarding.py:97-136

    Uses:
    - OnboardingService for path creation (now uses repo internally)
    - OnboardingRepository for updating user's onboarding tracking fields
    """
    # Validate prerequisite
    if not current_user.goal_selection_completed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PREREQUISITE_NOT_MET",
                "message": "Please complete goal selection first",
                "redirect_to": "/onboarding/goal-selection"
            }
        )

    # Set path using service (which uses repository internally)
    path = onboarding_service.set_user_path(
        db,
        current_user.id,
        path_data.dict()
    )

    # Update onboarding tracking using repository
    step_updates = {
        "path_selection_completed": True,
        "onboarding_current_step": 4
    }
    onboarding_repo.update_user_onboarding_step(current_user.id, step_updates)

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
    onboarding_repo: OnboardingRepository = Depends(get_onboarding_repository),
    db: Session = Depends(get_db)
):
    """
    Set dietary preferences.

    MIGRATED FROM: onboarding.py:138-177

    Uses:
    - OnboardingService for preferences creation (now uses repo internally)
    - OnboardingRepository for updating user's onboarding tracking fields
    """
    # Validate prerequisite
    if not current_user.path_selection_completed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PREREQUISITE_NOT_MET",
                "message": "Please complete path selection first",
                "redirect_to": "/onboarding/path-selection"
            }
        )

    # Set preferences using service (which uses repository internally)
    preferences = onboarding_service.set_user_preferences(
        db,
        current_user.id,
        pref_data.dict()
    )

    # Complete onboarding using repository
    step_updates = {
        "preferences_completed": True,
        "onboarding_completed": True,
        "onboarding_completed_at": datetime.utcnow()
    }
    onboarding_repo.update_user_onboarding_step(current_user.id, step_updates)

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
    db: Session = Depends(get_db)
):
    """
    Get calculated nutritional targets after onboarding.

    MIGRATED FROM: onboarding.py:179-191

    Uses:
    - OnboardingService for retrieving targets (now uses repo internally)
    """
    try:
        targets = onboarding_service.get_calculated_targets(db, current_user.id)
        return targets
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )