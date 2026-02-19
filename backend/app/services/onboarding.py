from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference
from app.schemas.user import GoalType, PathType, ActivityLevel
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository
import math

class OnboardingService:

    def __init__(self, onboarding_repo: IOnboardingRepository):
        self.onboarding_repo = onboarding_repo
    
    ACTIVITY_MULTIPLIERS = {
        ActivityLevel.SEDENTARY: 1.2,
        ActivityLevel.LIGHTLY_ACTIVE: 1.375,
        ActivityLevel.MODERATELY_ACTIVE: 1.55,
        ActivityLevel.VERY_ACTIVE: 1.725,
        ActivityLevel.EXTRA_ACTIVE: 1.9
    }
    
    GOAL_ADJUSTMENTS = {
        GoalType.MUSCLE_GAIN: 500,
        GoalType.FAT_LOSS: -500,
        GoalType.BODY_RECOMP: 0,
        GoalType.WEIGHT_TRAINING: 300,
        GoalType.ENDURANCE: 200,
        GoalType.GENERAL_HEALTH: 0
    }
    
    DEFAULT_MACROS = {
        GoalType.MUSCLE_GAIN: {"protein": 0.30, "carbs": 0.45, "fat": 0.25},
        GoalType.FAT_LOSS: {"protein": 0.35, "carbs": 0.35, "fat": 0.30},
        GoalType.BODY_RECOMP: {"protein": 0.35, "carbs": 0.40, "fat": 0.25},
        GoalType.WEIGHT_TRAINING: {"protein": 0.30, "carbs": 0.50, "fat": 0.20},
        GoalType.ENDURANCE: {"protein": 0.20, "carbs": 0.55, "fat": 0.25},
        GoalType.GENERAL_HEALTH: {"protein": 0.25, "carbs": 0.45, "fat": 0.30}
    }
   

    MEAL_WINDOWS = {
       PathType.IF_16_8: [
           {"meal": "lunch", "start_time": "12:00", "end_time": "13:00"},
           {"meal": "snack", "start_time": "15:00", "end_time": "15:30"},
           {"meal": "dinner", "start_time": "19:00", "end_time": "20:00"}
       ],
       PathType.IF_18_6: [
           {"meal": "lunch", "start_time": "14:00", "end_time": "15:00"},
           {"meal": "dinner", "start_time": "19:00", "end_time": "20:00"}
       ],
       PathType.OMAD: [
           {"meal": "dinner", "start_time": "18:00", "end_time": "19:00"}
       ],
       PathType.TRADITIONAL: [
           {"meal": "breakfast", "start_time": "07:00", "end_time": "09:00"},
           {"meal": "lunch", "start_time": "12:00", "end_time": "14:00"},
           {"meal": "snack", "start_time": "16:00", "end_time": "17:00"},
           {"meal": "dinner", "start_time": "19:00", "end_time": "21:00"}
       ],
       PathType.BODYBUILDER: [
           {"meal": "meal1", "start_time": "06:00", "end_time": "07:00"},
           {"meal": "meal2", "start_time": "09:00", "end_time": "10:00"},
           {"meal": "meal3", "start_time": "12:00", "end_time": "13:00"},
           {"meal": "meal4", "start_time": "15:00", "end_time": "16:00"},
           {"meal": "meal5", "start_time": "18:00", "end_time": "19:00"},
           {"meal": "meal6", "start_time": "21:00", "end_time": "22:00"}
       ]
   }
   
    @staticmethod
    def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
       bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
       if sex == "male":
           bmr += 5
       else:
           bmr -= 161
       return round(bmr, 2)
   
    @staticmethod
    def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
       """Calculate Total Daily Energy Expenditure"""
       multiplier = OnboardingService.ACTIVITY_MULTIPLIERS[activity_level]
       return round(bmr * multiplier, 2)
   
    @staticmethod
    def calculate_goal_calories(tdee: float, goal_type: GoalType) -> float:
       """Calculate daily calorie target based on goal"""
       adjustment = OnboardingService.GOAL_ADJUSTMENTS[goal_type]
       return round(tdee + adjustment, 2)
   
    @staticmethod
    def get_macro_targets(goal_type: GoalType) -> Dict[str, float]:
       """Get macro nutrient targets based on goal"""
       return OnboardingService.DEFAULT_MACROS[goal_type]
   
    @staticmethod
    def get_meal_windows(path_type: PathType) -> List[Dict]:
       """Get meal timing windows based on path"""
       return OnboardingService.MEAL_WINDOWS[path_type]
   
    @staticmethod
    def get_meals_per_day(path_type: PathType) -> int:
       """Get number of meals per day based on path"""
       return len(OnboardingService.MEAL_WINDOWS[path_type])
   
    def complete_profile(self, user_id: int, profile_data: dict) -> UserProfile:

       bmr = self.calculate_bmr(
           profile_data['weight_kg'],
           profile_data['height_cm'],
           profile_data['age'],
           profile_data['sex']
       )

       # Calculate TDEE (business logic - stays in service)
       tdee = self.calculate_tdee(bmr, profile_data['activity_level'])

       # Add calculated values to profile data
       profile_data['bmr'] = bmr
       profile_data['tdee'] = tdee

       # Create or update profile using injected repository
       profile = self.onboarding_repo.create_or_update_profile(user_id, profile_data)

       return profile
   
    def set_user_goal(self, user_id: int, goal_data: dict) -> UserGoal:

       profile = self.onboarding_repo.get_profile(user_id)
       if not profile:
           raise ValueError("Profile must be completed first")

       goal_calories = self.calculate_goal_calories(
           profile.tdee,
           goal_data['goal_type']
       )

       self.onboarding_repo.update_profile_goal_calories(user_id, goal_calories)

       if 'macro_targets' not in goal_data:
           goal_data['macro_targets'] = self.get_macro_targets(goal_data['goal_type'])

       goal = self.onboarding_repo.create_or_update_goal(user_id, goal_data)

       return goal
   
    def set_user_path(self, user_id: int, path_data: dict) -> UserPath:

       meal_windows = path_data.get('custom_windows') or self.get_meal_windows(path_data['path_type'])
       meals_per_day = len(meal_windows)

       # Create or update path using injected repository
       path = self.onboarding_repo.create_or_update_path(user_id, path_data['path_type'], meal_windows, meals_per_day)

       return path
   
    def set_user_preferences(self, user_id: int, pref_data: dict) -> UserPreference:

       preferences = self.onboarding_repo.create_or_update_preferences(user_id, pref_data)

       return preferences
   
    async def get_calculated_targets(self, user_id: int) -> dict:

       profile = self.onboarding_repo.get_profile(user_id)
       goal = self.onboarding_repo.get_goal(user_id)
       path = self.onboarding_repo.get_path(user_id)

       if not all([profile, goal, path]):
           raise ValueError("Onboarding incomplete")

       return {
           "bmr": profile.bmr,
           "tdee": profile.tdee,
           "goal_calories": profile.goal_calories,
           "macro_targets": goal.macro_targets,
           "meal_windows": path.meal_windows,
           "meals_per_day": path.meals_per_day
       }


    def complete_basic_info(self, user_id: int, profile_data: dict, onboarding_started_at: Optional[datetime]) -> UserProfile:

        profile = self.complete_profile(user_id, profile_data)

        step_updates = {
            "onboarding_started_at": onboarding_started_at or datetime.utcnow(),
            "basic_info_completed": True,
            "onboarding_current_step": 2
        }
        self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)

        return profile

    def complete_goal_selection(self, user_id: int, goal_data: dict) -> UserGoal:

        goal = self.set_user_goal(user_id, goal_data)

        # Update onboarding tracking
        step_updates = {
            "goal_selection_completed": True,
            "onboarding_current_step": 3
        }
        self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)

        return goal

    def complete_path_selection(self, user_id: int, path_data: dict) -> UserPath:

        path = self.set_user_path(user_id, path_data)

        # Update onboarding tracking
        step_updates = {
            "path_selection_completed": True,
            "onboarding_current_step": 4
        }
        self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)

        return path

    def complete_preferences(self, user_id: int, pref_data: dict) -> UserPreference:

        preferences = self.set_user_preferences(user_id, pref_data)

        step_updates = {
            "preferences_completed": True,
            "onboarding_completed": True,
            "onboarding_completed_at": datetime.utcnow()
        }
        self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)

        return preferences

    async def get_goal_progress(self, user_id: int, current_streak: int) -> Dict[str, Any]:

        try:
            # Get user profile and goal from repository
            user_profile = self.onboarding_repo.get_profile(user_id)
            user_goal = self.onboarding_repo.get_goal(user_id)

            # Extract data with defaults
            current_weight = user_profile.weight_kg if user_profile else 70.0
            target_weight = getattr(user_goal, 'target_weight', None) if user_goal else None
            if target_weight is None:
                target_weight = current_weight
            goal_type = user_goal.goal_type if user_goal else "maintain_weight"

            # Calculate weight change
            weight_change = target_weight - current_weight

            # Calculate progress percentage based on goal type
            if goal_type in ["lose_weight", "LOSE_WEIGHT", "fat_loss", "FAT_LOSS"]:
                starting_weight = getattr(user_goal, 'starting_weight', current_weight) if user_goal else current_weight
                total_to_lose = starting_weight - target_weight
                already_lost = starting_weight - current_weight
                progress_pct = (already_lost / total_to_lose * 100) if total_to_lose > 0 else 0
            elif goal_type in ["gain_weight", "GAIN_WEIGHT", "muscle_gain", "MUSCLE_GAIN"]:
                starting_weight = getattr(user_goal, 'starting_weight', current_weight) if user_goal else current_weight
                total_to_gain = target_weight - starting_weight
                already_gained = current_weight - starting_weight
                progress_pct = (already_gained / total_to_gain * 100) if total_to_gain > 0 else 0
            else:
                # Maintain weight
                progress_pct = 100.0 if abs(current_weight - target_weight) < 2 else 0

            return {
                "goal_type": goal_type,
                "current_weight": round(current_weight, 1),
                "target_weight": round(target_weight, 1),
                "weight_change": round(weight_change, 1),
                "current_streak": current_streak,
                "goal_progress_percentage": round(max(0, min(100, progress_pct)), 1)
            }

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting goal progress: {str(e)}")
            # Return defaults on error
            return {
                "goal_type": "maintain_weight",
                "current_weight": 70.0,
                "target_weight": 70.0,
                "weight_change": 0.0,
                "current_streak": current_streak,
                "goal_progress_percentage": 0.0
            }