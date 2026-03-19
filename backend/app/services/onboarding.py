from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference
from app.schemas.user import GoalType, PathType, ActivityLevel
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository
from pydantic import BaseModel
import math
import logging

logger = logging.getLogger(__name__)


class MacroTargetsAI(BaseModel):
    goal_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    reasoning: str = ""


class OnboardingService:

    def __init__(self, onboarding_repo: IOnboardingRepository, llm_orchestrator=None):
        self.onboarding_repo = onboarding_repo
        self.llm_orchestrator = llm_orchestrator

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

    PROTEIN_G_PER_KG = {
        GoalType.MUSCLE_GAIN:    1.8,
        GoalType.WEIGHT_TRAINING: 1.6,
        GoalType.FAT_LOSS:       2.0,
        GoalType.BODY_RECOMP:    2.0,
        GoalType.ENDURANCE:      1.4,
        GoalType.GENERAL_HEALTH: 1.2,
    }

    FAT_RATIO = {
        GoalType.MUSCLE_GAIN:    0.25,
        GoalType.WEIGHT_TRAINING: 0.20,
        GoalType.FAT_LOSS:       0.30,
        GoalType.BODY_RECOMP:    0.25,
        GoalType.ENDURANCE:      0.25,
        GoalType.GENERAL_HEALTH: 0.30,
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
       multiplier = OnboardingService.ACTIVITY_MULTIPLIERS[activity_level]
       return round(bmr * multiplier, 2)

    @staticmethod
    def calculate_goal_calories(tdee: float, goal_type: GoalType) -> float:
       adjustment = OnboardingService.GOAL_ADJUSTMENTS[goal_type]
       return round(tdee + adjustment, 2)

    @staticmethod
    def calculate_macro_targets_grams(
        goal_type: GoalType,
        weight_kg: float,
        goal_calories: float
    ) -> Dict[str, float]:
        protein_g = round(weight_kg * OnboardingService.PROTEIN_G_PER_KG[goal_type], 1)
        fat_g = round((goal_calories * OnboardingService.FAT_RATIO[goal_type]) / 9, 1)
        remaining = goal_calories - (protein_g * 4) - (fat_g * 9)
        carbs_g = round(max(remaining / 4, 0), 1)
        return {"protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}

    @staticmethod
    def get_meal_windows(path_type: PathType) -> List[Dict]:
       return OnboardingService.MEAL_WINDOWS[path_type]

    @staticmethod
    def get_meals_per_day(path_type: PathType) -> int:
       return len(OnboardingService.MEAL_WINDOWS[path_type])

    async def complete_profile(self, user_id: int, profile_data: dict) -> UserProfile:
       bmr = self.calculate_bmr(
           profile_data['weight_kg'],
           profile_data['height_cm'],
           profile_data['age'],
           profile_data['sex']
       )
       tdee = self.calculate_tdee(bmr, profile_data['activity_level'])
       profile_data['bmr'] = bmr
       profile_data['tdee'] = tdee
       profile = await self.onboarding_repo.create_or_update_profile(user_id, profile_data)
       return profile

    async def _calculate_macro_targets_ai(
        self,
        user_id: int,
        profile,
        goal_type: GoalType
    ) -> MacroTargetsAI:
        bmi = round(profile.weight_kg / ((profile.height_cm / 100) ** 2), 1)
        result: MacroTargetsAI = await self.llm_orchestrator.run(
            user_id=user_id,
            slug="calculate_macro_targets",
            variables={
                "age":            profile.age,
                "sex":            profile.sex,
                "weight_kg":      round(profile.weight_kg, 1),
                "height_cm":      round(profile.height_cm, 1),
                "bmi":            bmi,
                "activity_level": str(profile.activity_level),
                "goal_type":      str(goal_type),
                "tdee":           round(profile.tdee, 0),
            },
            response_model=MacroTargetsAI,
        )
        if result.goal_calories < 800 or result.goal_calories > 8000:
            raise ValueError(f"AI goal_calories={result.goal_calories} out of range")
        if result.protein_g < 30 or result.protein_g > profile.weight_kg * 4:
            raise ValueError(f"AI protein_g={result.protein_g} out of range")
        if result.fat_g < 20:
            raise ValueError(f"AI fat_g={result.fat_g} too low")
        if result.carbs_g < 0:
            raise ValueError(f"AI carbs_g={result.carbs_g} negative")
        macro_cal = result.protein_g * 4 + result.carbs_g * 4 + result.fat_g * 9
        if abs(macro_cal - result.goal_calories) / result.goal_calories > 0.20:
            raise ValueError(
                f"AI macro calories {macro_cal:.0f} don't balance with "
                f"goal_calories {result.goal_calories:.0f}"
            )
        return result

    async def set_user_goal(self, user_id: int, goal_data: dict) -> UserGoal:
       profile = await self.onboarding_repo.get_profile(user_id)
       if not profile:
           raise ValueError("Profile must be completed first")

       ai_result: Optional[MacroTargetsAI] = None
       if self.llm_orchestrator:
           try:
               ai_result = await self._calculate_macro_targets_ai(
                   user_id, profile, goal_data['goal_type']
               )
               logger.info(
                   f"[MacroAI] user={user_id} goal_cal={ai_result.goal_calories:.0f} "
                   f"P={ai_result.protein_g}g C={ai_result.carbs_g}g F={ai_result.fat_g}g | "
                   f"{ai_result.reasoning}"
               )
           except Exception as exc:
               logger.warning(
                   f"[MacroAI] user={user_id} AI failed — falling back to static. Reason: {exc}"
               )

       if ai_result is not None:
           goal_calories = ai_result.goal_calories
           goal_data['macro_targets'] = {
               "protein_g": ai_result.protein_g,
               "carbs_g":   ai_result.carbs_g,
               "fat_g":     ai_result.fat_g,
           }
       else:
           goal_calories = self.calculate_goal_calories(
               profile.tdee, goal_data['goal_type']
           )
           goal_data['macro_targets'] = self.calculate_macro_targets_grams(
               goal_type=goal_data['goal_type'],
               weight_kg=profile.weight_kg,
               goal_calories=goal_calories,
           )

       await self.onboarding_repo.update_profile_goal_calories(user_id, goal_calories)
       goal = await self.onboarding_repo.create_or_update_goal(user_id, goal_data)
       return goal

    async def lock_macro_targets(self, user_id: int, target_data: dict) -> UserGoal:
       goal = await self.onboarding_repo.get_goal(user_id)
       if not goal:
           raise ValueError("Goal must be completed before locking targets")

       goal_calories = float(target_data["goal_calories"])
       macro_targets = {
           "protein_g": float(target_data["protein_g"]),
           "carbs_g": float(target_data["carbs_g"]),
           "fat_g": float(target_data["fat_g"]),
       }

       total_macro_cal = (
           macro_targets["protein_g"] * 4
           + macro_targets["carbs_g"] * 4
           + macro_targets["fat_g"] * 9
       )
       if goal_calories <= 0:
           raise ValueError("Goal calories must be greater than zero")
       if abs(total_macro_cal - goal_calories) / goal_calories > 0.25:
           raise ValueError("Macro calories do not align with goal calories")

       await self.onboarding_repo.update_profile_goal_calories(user_id, goal_calories)
       updated_goal = await self.onboarding_repo.create_or_update_goal(
           user_id,
           {
               "goal_type": goal.goal_type,
               "target_weight": goal.target_weight,
               "target_date": goal.target_date,
               "target_body_fat_percentage": goal.target_body_fat_percentage,
               "macro_targets": macro_targets,
           },
       )
       return updated_goal

    async def set_user_path(self, user_id: int, path_data: dict) -> UserPath:
       meal_windows = path_data.get('custom_windows') or self.get_meal_windows(path_data['path_type'])
       meals_per_day = len(meal_windows)
       path = await self.onboarding_repo.create_or_update_path(user_id, path_data['path_type'], meal_windows, meals_per_day)
       return path

    async def set_user_preferences(self, user_id: int, pref_data: dict) -> UserPreference:
       preferences = await self.onboarding_repo.create_or_update_preferences(user_id, pref_data)
       return preferences

    async def get_calculated_targets(self, user_id: int) -> dict:
       profile = await self.onboarding_repo.get_profile(user_id)
       goal = await self.onboarding_repo.get_goal(user_id)
       path = await self.onboarding_repo.get_path(user_id)

       if not all([profile, goal, path]):
           raise ValueError("Onboarding incomplete")

       mt = goal.macro_targets
       total_macro_cal = (mt["protein_g"] * 4) + (mt["carbs_g"] * 4) + (mt["fat_g"] * 9)
       macro_ratios = {
           "protein": round(mt["protein_g"] * 4 / total_macro_cal, 3),
           "carbs": round(mt["carbs_g"] * 4 / total_macro_cal, 3),
           "fat": round(mt["fat_g"] * 9 / total_macro_cal, 3),
       } if total_macro_cal > 0 else {"protein": 0.3, "carbs": 0.45, "fat": 0.25}

       return {
           "bmr": profile.bmr,
           "tdee": profile.tdee,
           "goal_calories": profile.goal_calories,
           "macro_targets": mt,
           "macro_ratios": macro_ratios,
           "meal_windows": path.meal_windows,
           "meals_per_day": path.meals_per_day
       }

    async def complete_basic_info(self, user_id: int, profile_data: dict, onboarding_started_at: Optional[datetime]) -> UserProfile:
        profile = await self.complete_profile(user_id, profile_data)
        step_updates = {
            "onboarding_started_at": onboarding_started_at or datetime.utcnow(),
            "basic_info_completed": True,
            "onboarding_current_step": 2
        }
        await self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)
        return profile

    async def complete_goal_selection(self, user_id: int, goal_data: dict) -> UserGoal:
        goal = await self.set_user_goal(user_id, goal_data)
        step_updates = {
            "goal_selection_completed": True,
            "onboarding_current_step": 3
        }
        await self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)
        return goal

    async def complete_path_selection(self, user_id: int, path_data: dict) -> UserPath:
        path = await self.set_user_path(user_id, path_data)
        step_updates = {
            "path_selection_completed": True,
            "onboarding_current_step": 4
        }
        await self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)
        return path

    async def complete_preferences(self, user_id: int, pref_data: dict) -> UserPreference:
        preferences = await self.set_user_preferences(user_id, pref_data)
        step_updates = {
            "preferences_completed": True,
            "onboarding_completed": True,
            "onboarding_completed_at": datetime.utcnow()
        }
        await self.onboarding_repo.update_user_onboarding_step(user_id, step_updates)
        return preferences

    async def get_goal_progress(self, user_id: int, current_streak: int) -> Dict[str, Any]:
        try:
            user_profile = await self.onboarding_repo.get_profile(user_id)
            user_goal = await self.onboarding_repo.get_goal(user_id)

            current_weight = user_profile.weight_kg if user_profile else 70.0
            target_weight = getattr(user_goal, 'target_weight', None) if user_goal else None
            if target_weight is None:
                target_weight = current_weight
            goal_type = user_goal.goal_type if user_goal else "maintain_weight"

            weight_change = target_weight - current_weight

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
            logger.error(f"Error getting goal progress: {str(e)}")
            return {
                "goal_type": "maintain_weight",
                "current_weight": 70.0,
                "target_weight": 70.0,
                "weight_change": 0.0,
                "current_streak": current_streak,
                "goal_progress_percentage": 0.0
            }
