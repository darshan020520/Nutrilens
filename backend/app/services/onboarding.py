from typing import Dict, List, Optional
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference
from app.schemas.user import GoalType, PathType, ActivityLevel
from sqlalchemy.orm import Session
from app.repositories.onboarding_repository import OnboardingRepository
import math

class OnboardingService:
    """Service for user onboarding and nutritional calculations"""
    
    # Activity level multipliers for TDEE calculation
    ACTIVITY_MULTIPLIERS = {
        ActivityLevel.SEDENTARY: 1.2,
        ActivityLevel.LIGHTLY_ACTIVE: 1.375,
        ActivityLevel.MODERATELY_ACTIVE: 1.55,
        ActivityLevel.VERY_ACTIVE: 1.725,
        ActivityLevel.EXTRA_ACTIVE: 1.9
    }
    
    # Goal-based calorie adjustments
    GOAL_ADJUSTMENTS = {
        GoalType.MUSCLE_GAIN: 500,  # Surplus
        GoalType.FAT_LOSS: -500,    # Deficit
        GoalType.BODY_RECOMP: 0,    # Maintenance
        GoalType.WEIGHT_TRAINING: 300,  # Slight surplus
        GoalType.ENDURANCE: 200,    # Slight surplus
        GoalType.GENERAL_HEALTH: 0  # Maintenance
    }
    
    # Default macro splits by goal
    DEFAULT_MACROS = {
        GoalType.MUSCLE_GAIN: {"protein": 0.30, "carbs": 0.45, "fat": 0.25},
        GoalType.FAT_LOSS: {"protein": 0.35, "carbs": 0.35, "fat": 0.30},
        GoalType.BODY_RECOMP: {"protein": 0.35, "carbs": 0.40, "fat": 0.25},
        GoalType.WEIGHT_TRAINING: {"protein": 0.30, "carbs": 0.50, "fat": 0.20},
        GoalType.ENDURANCE: {"protein": 0.20, "carbs": 0.55, "fat": 0.25},
        GoalType.GENERAL_HEALTH: {"protein": 0.25, "carbs": 0.45, "fat": 0.30}
    }
   
   # Meal windows by path
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
       """
       Calculate Basal Metabolic Rate using Mifflin-St Jeor Formula
       Men: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) + 5
       Women: BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age(years) - 161
       """
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
   
    def complete_profile(self, db: Session, user_id: int, profile_data: dict) -> UserProfile:
       """Complete user profile with calculations"""
       repo = OnboardingRepository(db)

       # Calculate BMR (business logic - stays in service)
       bmr = self.calculate_bmr(
           profile_data['weight_kg'],
           profile_data['height_cm'],
           profile_data['age'],
           profile_data['sex']
       )

       # Calculate TDEE (business logic - stays in service)
       tdee = self.calculate_tdee(bmr, profile_data['activity_level'])
       print("tdee", tdee)

       # Add calculated values to profile data
       profile_data['bmr'] = bmr
       profile_data['tdee'] = tdee

       # Create or update profile using repository
       profile = repo.create_or_update_profile(user_id, profile_data)

       print("profile", profile.tdee)

       return profile
   
    def set_user_goal(self, db: Session, user_id: int, goal_data: dict) -> UserGoal:
       """Set user goal with macro targets"""
       repo = OnboardingRepository(db)

       # Get user profile for TDEE using repository
       profile = repo.get_profile(user_id)
       if not profile:
           raise ValueError("Profile must be completed first")

       # Calculate goal calories (business logic - stays in service)
       goal_calories = self.calculate_goal_calories(
           profile.tdee,
           goal_data['goal_type']
       )

       # Update profile with goal calories using repository
       repo.update_profile_goal_calories(user_id, goal_calories)

       # Get default macros if not provided (business logic - stays in service)
       if 'macro_targets' not in goal_data:
           goal_data['macro_targets'] = self.get_macro_targets(goal_data['goal_type'])

       # Create or update goal using repository
       goal = repo.create_or_update_goal(user_id, goal_data)

       return goal
   
    def set_user_path(self, db: Session, user_id: int, path_data: dict) -> UserPath:
       """Set user eating path with meal windows"""
       repo = OnboardingRepository(db)

       # Get meal windows (business logic - stays in service)
       meal_windows = path_data.get('custom_windows') or self.get_meal_windows(path_data['path_type'])
       meals_per_day = len(meal_windows)

       # Create or update path using repository
       path = repo.create_or_update_path(user_id, path_data['path_type'], meal_windows, meals_per_day)

       return path
   
    def set_user_preferences(self, db: Session, user_id: int, pref_data: dict) -> UserPreference:
       """Set user dietary preferences"""
       repo = OnboardingRepository(db)

       # Create or update preferences using repository
       preferences = repo.create_or_update_preferences(user_id, pref_data)

       return preferences
   
    def get_calculated_targets(self, db: Session, user_id: int) -> dict:
       """Get all calculated nutritional targets for user"""
       repo = OnboardingRepository(db)

       # Get all onboarding data using repository
       profile = repo.get_profile(user_id)
       goal = repo.get_goal(user_id)
       path = repo.get_path(user_id)

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