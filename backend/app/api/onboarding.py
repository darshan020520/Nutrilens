from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.database import get_db, User
from app.schemas.user import (
    ProfileCreate, ProfileResponse,
    GoalCreate, PathSelection, PreferenceCreate,
    OnboardingTargets
)
from app.services.onboarding import OnboardingService
from app.services.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

onboarding_service = OnboardingService()

def get_current_user_from_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency to get current user"""
    user = get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return user

@router.post("/basic-info", response_model=ProfileResponse)
def submit_basic_info(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Submit basic user information"""
    profile = onboarding_service.complete_profile(
        db, 
        current_user.id, 
        profile_data.dict()
    )
    return profile

@router.post("/goal-selection")
def select_goal(
    goal_data: GoalCreate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Select fitness goal"""
    goal = onboarding_service.set_user_goal(
        db,
        current_user.id,
        goal_data.dict()
    )
    return {
        "message": "Goal set successfully",
        "goal_type": goal.goal_type,
        "macro_targets": goal.macro_targets
    }

@router.post("/path-selection")
def select_path(
    path_data: PathSelection,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Select eating path/strategy"""
    path = onboarding_service.set_user_path(
        db,
        current_user.id,
        path_data.dict()
    )
    return {
        "message": "Path set successfully",
        "path_type": path.path_type,
        "meals_per_day": path.meals_per_day,
        "meal_windows": path.meal_windows
    }

@router.post("/preferences")
def set_preferences(
    pref_data: PreferenceCreate,
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Set dietary preferences"""
    preferences = onboarding_service.set_user_preferences(
        db,
        current_user.id,
        pref_data.dict()
    )
    return {
        "message": "Preferences set successfully",
        "dietary_type": preferences.dietary_type,
        "allergies": preferences.allergies
    }

@router.get("/calculated-targets", response_model=OnboardingTargets)
def get_calculated_targets(
    current_user: User = Depends(get_current_user_from_token),
    db: Session = Depends(get_db)
):
    """Get calculated nutritional targets after onboarding"""
    try:
        targets = onboarding_service.get_calculated_targets(db, current_user.id)
        return targets
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )