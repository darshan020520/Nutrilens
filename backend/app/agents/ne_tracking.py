# backend/app/agents/nutrition_agent.py
"""
Production-Ready Nutrition Agent with all 10 tools
Real database operations, no dummy responses
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from collections import defaultdict
import math

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models.database import (
    User, UserProfile, UserGoal, UserPath, UserPreference,
    MealLog, Recipe, RecipeIngredient, Item, UserInventory,
    MealPlan, GoalType, ActivityLevel, PathType
)
from app.services.inventory_service import IntelligentInventoryService

logger = logging.getLogger(__name__)

class MealContext(str, Enum):
    """Context for meal suggestions"""
    PRE_WORKOUT = "pre_workout"
    POST_WORKOUT = "post_workout"
    MORNING = "morning"
    EVENING = "evening"
    LOW_ENERGY = "low_energy"
    HIGH_STRESS = "high_stress"
    QUICK_MEAL = "quick_meal"
    MEAL_PREP = "meal_prep"

@dataclass
class NutritionState:
    """State management for nutrition agent"""
    user_id: int
    profile: Dict[str, Any]
    goals: Dict[str, Any]
    daily_targets: Dict[str, float]
    consumed_today: Dict[str, float]
    remaining_macros: Dict[str, float]
    meal_schedule: List[Dict[str, Any]]
    context: Optional[MealContext] = None

class NutritionAgent:
    """
    Complete Nutrition Agent with all 10 tools
    Production-ready with real database operations
    """
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.inventory_service = IntelligentInventoryService(db)
        self.state = self._initialize_state()
        
    def _initialize_state(self) -> NutritionState:
        """Initialize agent state from database"""
        profile = self.db.query(UserProfile).filter_by(user_id=self.user_id).first()
        goal = self.db.query(UserGoal).filter_by(user_id=self.user_id, is_active=True).first()
        path = self.db.query(UserPath).filter_by(user_id=self.user_id).first()
        
        if not profile:
            raise ValueError(f"User profile not found for user_id: {self.user_id}")
        
        profile_dict = {
            "age": profile.age,
            "weight_kg": profile.weight_kg,
            "height_cm": profile.height_cm,
            "sex": profile.sex,
            "activity_level": profile.activity_level.value if profile.activity_level else "sedentary",
            "bmr": profile.bmr,
            "tdee": profile.tdee,
            "goal_calories": profile.goal_calories
        }
        
        goals_dict = {}
        if goal:
            goals_dict = {
                "goal_type": goal.goal_type.value,
                "target_weight": goal.target_weight,
                "macro_targets": goal.macro_targets or {}
            }
        
        daily_targets = self._calculate_daily_targets(profile, goal)
        consumed_today = self._calculate_consumed_today()
        remaining = {k: daily_targets[k] - consumed_today.get(k, 0) for k in daily_targets}
        
        meal_schedule = path.meal_windows if path else []
        
        return NutritionState(
            user_id=self.user_id,
            profile=profile_dict,
            goals=goals_dict,
            daily_targets=daily_targets,
            consumed_today=consumed_today,
            remaining_macros=remaining,
            meal_schedule=meal_schedule,
            context=self._determine_current_context()
        )
    
    # ============== TOOL 1: BMR/TDEE CALCULATION ==============
    
    def calculate_bmr_tdee(self, weight_kg: Optional[float] = None,
                          height_cm: Optional[float] = None,
                          age: Optional[int] = None,
                          sex: Optional[str] = None,
                          activity_level: Optional[str] = None) -> Dict[str, Any]:
        """Tool 1: Calculate BMR and TDEE based on user parameters"""
        try:
            profile = self.db.query(UserProfile).filter_by(user_id=self.user_id).first()
            if not profile:
                return {"success": False, "error": "User profile not found"}
            
            # Update profile if new values provided
            if weight_kg:
                profile.weight_kg = weight_kg
            if height_cm:
                profile.height_cm = height_cm
            if age:
                profile.age = age
            if sex:
                profile.sex = sex
            if activity_level:
                profile.activity_level = ActivityLevel(activity_level)
            
            # Calculate BMR using Mifflin-St Jeor equation
            if profile.sex == "male":
                bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + 5
            else:
                bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age - 161
            
            # Activity multipliers
            multipliers = {
                "sedentary": 1.2,
                "lightly_active": 1.375,
                "moderately_active": 1.55,
                "very_active": 1.725,
                "extra_active": 1.9
            }
            
            activity = profile.activity_level.value if profile.activity_level else "sedentary"
            tdee = bmr * multipliers.get(activity, 1.2)
            
            # Update profile
            profile.bmr = round(bmr, 0)
            profile.tdee = round(tdee, 0)
            self.db.commit()
            
            # Update state
            self.state.profile["bmr"] = profile.bmr
            self.state.profile["tdee"] = profile.tdee
            
            return {
                "success": True,
                "bmr": profile.bmr,
                "tdee": profile.tdee,
                "activity_multiplier": multipliers.get(activity, 1.2),
                "calculations": {
                    "protein_requirement": round(profile.weight_kg * 1.6, 0),
                    "water_requirement_ml": round(profile.weight_kg * 35, 0),
                    "fiber_requirement_g": 25 if profile.sex == "female" else 38
                }
            }
        except Exception as e:
            logger.error(f"Error calculating BMR/TDEE: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 2: ADJUST CALORIES FOR GOAL ==============
    
    def adjust_calories_for_goal(self, goal_type: Optional[str] = None,
                                custom_adjustment: Optional[int] = None) -> Dict[str, Any]:
        """Tool 2: Adjust calorie targets based on goals"""
        try:
            profile = self.db.query(UserProfile).filter_by(user_id=self.user_id).first()
            goal = self.db.query(UserGoal).filter_by(user_id=self.user_id, is_active=True).first()
            
            if not profile or not profile.tdee:
                return {"success": False, "error": "Calculate BMR/TDEE first"}
            
            target_goal = goal_type or (goal.goal_type.value if goal else "general_health")
            
            adjustments = {
                "muscle_gain": 400,
                "fat_loss": -500,
                "body_recomp": 0,
                "weight_training": 300,
                "endurance": 200,
                "general_health": 0
            }
            
            adjustment = custom_adjustment if custom_adjustment else adjustments.get(target_goal, 0)
            new_calories = profile.tdee + adjustment
            
            # Ensure safe limits
            new_calories = max(profile.bmr * 0.8, min(new_calories, profile.tdee * 1.5))
            
            # Calculate macros
            protein_g = profile.weight_kg * (2.2 if target_goal == "muscle_gain" else 1.6)
            remaining_calories = new_calories - (protein_g * 4)
            
            if target_goal in ["muscle_gain", "weight_training"]:
                carbs_g = (remaining_calories * 0.65) / 4
                fat_g = (remaining_calories * 0.35) / 9
            else:
                carbs_g = (remaining_calories * 0.50) / 4
                fat_g = (remaining_calories * 0.50) / 9
            
            # Update profile and goal
            profile.goal_calories = round(new_calories, 0)
            
            if goal:
                if goal_type:
                    goal.goal_type = GoalType(goal_type)
                goal.macro_targets = {
                    "protein": round((protein_g * 4) / new_calories, 2),
                    "carbs": round((carbs_g * 4) / new_calories, 2),
                    "fat": round((fat_g * 9) / new_calories, 2)
                }
            else:
                # Create new goal
                goal = UserGoal(
                    user_id=self.user_id,
                    goal_type=GoalType(target_goal),
                    macro_targets={
                        "protein": round((protein_g * 4) / new_calories, 2),
                        "carbs": round((carbs_g * 4) / new_calories, 2),
                        "fat": round((fat_g * 9) / new_calories, 2)
                    },
                    is_active=True
                )
                self.db.add(goal)
            
            self.db.commit()
            
            # Update state
            self.state.daily_targets = {
                "calories": round(new_calories, 0),
                "protein_g": round(protein_g, 0),
                "carbs_g": round(carbs_g, 0),
                "fat_g": round(fat_g, 0),
                "fiber_g": 25 if profile.sex == "female" else 38
            }
            
            return {
                "success": True,
                "goal_type": target_goal,
                "new_calories": round(new_calories, 0),
                "adjustment": adjustment,
                "macros": {
                    "protein_g": round(protein_g, 0),
                    "carbs_g": round(carbs_g, 0),
                    "fat_g": round(fat_g, 0)
                }
            }
        except Exception as e:
            logger.error(f"Error adjusting calories: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 3: ANALYZE MEAL MACROS ==============
    
    def analyze_meal_macros(self, recipe_id: int, portion_size: float = 1.0) -> Dict[str, Any]:
        """Tool 3: Analyze nutritional content of meals"""
        try:
            recipe = self.db.query(Recipe).filter_by(id=recipe_id).first()
            if not recipe:
                return {"success": False, "error": "Recipe not found"}
            
            macros = recipe.macros_per_serving or {}
            actual_macros = {k: v * portion_size for k, v in macros.items()}
            
            # Calculate percentages
            total_calories = actual_macros.get("calories", 1)
            protein_cal = actual_macros.get("protein_g", 0) * 4
            carbs_cal = actual_macros.get("carbs_g", 0) * 4
            fat_cal = actual_macros.get("fat_g", 0) * 9
            
            # Compare to meal targets
            meal_targets = {k: v / 3 for k, v in self.state.daily_targets.items()}
            
            comparison = {}
            for macro in ["calories", "protein_g", "carbs_g", "fat_g"]:
                actual = actual_macros.get(macro, 0)
                target = meal_targets.get(macro, 1)
                comparison[macro] = {
                    "actual": round(actual, 1),
                    "target": round(target, 1),
                    "percentage": round((actual / target * 100) if target > 0 else 0, 0)
                }
            
            return {
                "success": True,
                "recipe": recipe.title,
                "portion_size": portion_size,
                "macros": {
                    "calories": round(actual_macros.get("calories", 0), 0),
                    "protein": {
                        "grams": round(actual_macros.get("protein_g", 0), 1),
                        "percentage": round(protein_cal / total_calories * 100, 0)
                    },
                    "carbs": {
                        "grams": round(actual_macros.get("carbs_g", 0), 1),
                        "percentage": round(carbs_cal / total_calories * 100, 0)
                    },
                    "fat": {
                        "grams": round(actual_macros.get("fat_g", 0), 1),
                        "percentage": round(fat_cal / total_calories * 100, 0)
                    }
                },
                "comparison_to_targets": comparison
            }
        except Exception as e:
            logger.error(f"Error analyzing macros: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 4: CHECK DAILY TARGETS ==============
    
    def check_daily_targets(self) -> Dict[str, Any]:
        """Tool 4: Check progress against daily nutritional targets"""
        try:
            self.state.consumed_today = self._calculate_consumed_today()
            
            progress = {}
            for macro in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]:
                target = self.state.daily_targets.get(macro, 0)
                consumed = self.state.consumed_today.get(macro, 0)
                remaining = target - consumed
                
                progress[macro] = {
                    "target": round(target, 1),
                    "consumed": round(consumed, 1),
                    "remaining": round(remaining, 1),
                    "percentage": round((consumed / target * 100) if target > 0 else 0, 0)
                }
            
            # Update state
            self.state.remaining_macros = {k: v["remaining"] for k, v in progress.items()}
            
            # Determine status
            cal_percentage = progress["calories"]["percentage"]
            if cal_percentage < 50:
                status = "behind_schedule"
            elif cal_percentage < 90:
                status = "on_track"
            elif cal_percentage <= 110:
                status = "optimal"
            else:
                status = "exceeded"
            
            # Get meals logged today
            today_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    func.date(MealLog.consumed_datetime) == date.today()
                )
            ).count()
            
            return {
                "success": True,
                "date": date.today().isoformat(),
                "progress": progress,
                "status": status,
                "meals_logged": today_logs,
                "recommendations": self._get_daily_recommendations(progress, status)
            }
        except Exception as e:
            logger.error(f"Error checking daily targets: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 5: SUGGEST NEXT MEAL ==============
    
    def suggest_next_meal(self, meal_type: Optional[str] = None,
                         context: Optional[str] = None) -> Dict[str, Any]:
        """Tool 5: Suggest optimal meals based on current state"""
        try:
            if not meal_type:
                meal_type = self._determine_current_meal_type()
            
            # Calculate remaining meals
            path = self.db.query(UserPath).filter_by(user_id=self.user_id).first()
            meals_per_day = path.meals_per_day if path else 3
            
            today_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    func.date(MealLog.consumed_datetime) == date.today()
                )
            ).count()
            
            meals_remaining = max(1, meals_per_day - today_logs)
            
            # Calculate targets for this meal
            meal_targets = {k: v / meals_remaining for k, v in self.state.remaining_macros.items()}
            
            # Get suitable recipes
            query = self.db.query(Recipe)
            if meal_type:
                query = query.filter(Recipe.suitable_meal_times.contains([meal_type]))
            
            recipes = query.limit(20).all()
            
            # Score recipes
            suggestions = []
            for recipe in recipes:
                if not recipe.macros_per_serving:
                    continue
                
                score = self._score_recipe(recipe, meal_targets, context)
                suggestions.append({
                    "recipe_id": recipe.id,
                    "title": recipe.title,
                    "score": round(score, 1),
                    "macros": recipe.macros_per_serving,
                    "prep_time": recipe.prep_time_min
                })
            
            # Sort by score
            suggestions.sort(key=lambda x: x["score"], reverse=True)
            
            return {
                "success": True,
                "meal_type": meal_type,
                "meal_targets": {k: round(v, 0) for k, v in meal_targets.items()},
                "suggestions": suggestions[:5],
                "meals_remaining": meals_remaining
            }
        except Exception as e:
            logger.error(f"Error suggesting meal: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 6: CALCULATE MEAL TIMING ==============
    
    def calculate_meal_timing(self) -> Dict[str, Any]:
        """Tool 6: Optimize meal timing based on goals and schedule"""
        try:
            path = self.db.query(UserPath).filter_by(user_id=self.user_id).first()
            goal = self.db.query(UserGoal).filter_by(user_id=self.user_id, is_active=True).first()
            
            if not path:
                return {"success": False, "error": "User path not configured"}
            
            meal_windows = path.meal_windows or []
            path_type = path.path_type.value if path.path_type else "traditional"
            
            # Analyze actual meal patterns
            week_ago = datetime.now() - timedelta(days=7)
            recent_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= week_ago
                )
            ).all()
            
            meal_times = defaultdict(list)
            for log in recent_logs:
                hour = log.consumed_datetime.hour
                meal_times[hour].append(log.recipe_id)
            
            # Calculate optimal timing
            optimal_timing = self._calculate_optimal_timing(path_type, goal.goal_type.value if goal else None)
            
            return {
                "success": True,
                "path_type": path_type,
                "current_schedule": meal_windows,
                "meals_per_day": path.meals_per_day,
                "optimal_timing": optimal_timing,
                "actual_patterns": dict(meal_times),
                "recommendations": self._get_timing_recommendations(meal_windows, optimal_timing)
            }
        except Exception as e:
            logger.error(f"Error calculating meal timing: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 7: PROVIDE NUTRITION EDUCATION ==============
    
    def provide_nutrition_education(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """Tool 7: Provide educational content about nutrition"""
        try:
            if not topic:
                topic = self._select_education_topic()
            
            education_content = {
                "protein": {
                    "title": "Understanding Protein",
                    "content": "Protein is essential for muscle repair and growth. Aim for 1.6-2.2g per kg body weight.",
                    "tips": [
                        "Distribute protein across meals",
                        "Include complete protein sources",
                        "Time protein intake around workouts"
                    ]
                },
                "carbs": {
                    "title": "Carbohydrates for Energy",
                    "content": "Carbs are your body's preferred energy source. Choose complex carbs for sustained energy.",
                    "tips": [
                        "Time simple carbs around workouts",
                        "Choose whole grains",
                        "Include fiber-rich sources"
                    ]
                },
                "fats": {
                    "title": "Healthy Fats",
                    "content": "Fats are essential for hormone production and nutrient absorption.",
                    "tips": [
                        "Include omega-3 sources",
                        "Limit saturated fats",
                        "Cook with healthy oils"
                    ]
                },
                "hydration": {
                    "title": "Hydration Basics",
                    "content": "Proper hydration is crucial for performance and health.",
                    "tips": [
                        "Drink 35ml per kg body weight daily",
                        "Increase during exercise",
                        "Monitor urine color"
                    ]
                }
            }
            
            content = education_content.get(topic, education_content["protein"])
            
            return {
                "success": True,
                "topic": topic,
                "content": content,
                "personalized_advice": self._get_personalized_education(topic)
            }
        except Exception as e:
            logger.error(f"Error providing education: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 8: TRACK WEEKLY PROGRESS ==============
    
    def track_weekly_progress(self, weeks: int = 1) -> Dict[str, Any]:
        """Tool 8: Analyze weekly progress and trends"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7 * weeks)
            
            meal_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= start_date
                )
            ).all()
            
            # Calculate weekly totals
            weekly_data = defaultdict(lambda: {
                "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0,
                "meals_logged": 0
            })
            
            for log in meal_logs:
                week_num = (log.consumed_datetime - start_date).days // 7
                if log.recipe and log.recipe.macros_per_serving:
                    macros = log.recipe.macros_per_serving
                    multiplier = log.portion_multiplier or 1.0
                    
                    weekly_data[week_num]["calories"] += macros.get("calories", 0) * multiplier
                    weekly_data[week_num]["protein_g"] += macros.get("protein_g", 0) * multiplier
                    weekly_data[week_num]["carbs_g"] += macros.get("carbs_g", 0) * multiplier
                    weekly_data[week_num]["fat_g"] += macros.get("fat_g", 0) * multiplier
                    weekly_data[week_num]["meals_logged"] += 1
            
            # Calculate averages
            total_calories = sum(w["calories"] for w in weekly_data.values())
            total_protein = sum(w["protein_g"] for w in weekly_data.values())
            total_meals = sum(w["meals_logged"] for w in weekly_data.values())
            
            days_tracked = (end_date - start_date).days
            
            return {
                "success": True,
                "period": f"Last {weeks} week(s)",
                "weekly_breakdown": dict(weekly_data),
                "totals": {
                    "total_calories": round(total_calories, 0),
                    "total_protein": round(total_protein, 0),
                    "total_meals": total_meals,
                    "avg_calories_per_day": round(total_calories / days_tracked, 0) if days_tracked > 0 else 0
                },
                "insights": self._generate_weekly_insights(weekly_data)
            }
        except Exception as e:
            logger.error(f"Error tracking weekly progress: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 9: ADJUST PORTIONS ==============
    
    def adjust_portions(self, recipe_id: int) -> Dict[str, Any]:
        """Tool 9: Personalize portion sizes based on individual needs"""
        try:
            recipe = self.db.query(Recipe).filter_by(id=recipe_id).first()
            if not recipe:
                return {"success": False, "error": "Recipe not found"}
            
            # Get user's historical portions
            recent_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.recipe_id == recipe_id
                )
            ).limit(5).all()
            
            avg_portion = 1.0
            if recent_logs:
                portions = [log.portion_multiplier for log in recent_logs if log.portion_multiplier]
                avg_portion = sum(portions) / len(portions) if portions else 1.0
            
            # Calculate optimal portion based on goals
            profile = self.db.query(UserProfile).filter_by(user_id=self.user_id).first()
            goal = self.db.query(UserGoal).filter_by(user_id=self.user_id, is_active=True).first()
            
            goal_adjustment = 1.0
            if goal:
                if goal.goal_type == GoalType.MUSCLE_GAIN:
                    goal_adjustment = 1.2
                elif goal.goal_type == GoalType.FAT_LOSS:
                    goal_adjustment = 0.8
            
            # Weight-based adjustment
            weight_adjustment = 1.0
            if profile and profile.weight_kg:
                if profile.weight_kg > 80:
                    weight_adjustment = 1.1
                elif profile.weight_kg < 60:
                    weight_adjustment = 0.9
            
            final_portion = avg_portion * goal_adjustment * weight_adjustment
            final_portion = max(0.5, min(2.5, final_portion))  # Limit range
            
            # Calculate adjusted macros
            original_macros = recipe.macros_per_serving or {}
            adjusted_macros = {k: v * final_portion for k, v in original_macros.items()}
            
            return {
                "success": True,
                "recipe": recipe.title,
                "standard_portion": 1.0,
                "personalized_portion": round(final_portion, 2),
                "historical_average": round(avg_portion, 2),
                "adjustments": {
                    "goal_based": round(goal_adjustment, 2),
                    "weight_based": round(weight_adjustment, 2)
                },
                "original_macros": original_macros,
                "adjusted_macros": {k: round(v, 1) for k, v in adjusted_macros.items()}
            }
        except Exception as e:
            logger.error(f"Error adjusting portions: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ============== TOOL 10: GENERATE PROGRESS REPORT ==============
    
    def generate_progress_report(self, period_days: int = 7) -> Dict[str, Any]:
        """Tool 10: Generate comprehensive progress report"""
        try:
            # Get various progress metrics
            daily_progress = self.check_daily_targets()
            weekly_progress = self.track_weekly_progress()
            
            # Calculate adherence
            period_start = datetime.now() - timedelta(days=period_days)
            
            meal_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= period_start
                )
            ).count()
            
            path = self.db.query(UserPath).filter_by(user_id=self.user_id).first()
            expected_meals = (path.meals_per_day if path else 3) * period_days
            adherence_rate = (meal_logs / expected_meals * 100) if expected_meals > 0 else 0
            
            # Check goal progress
            goal = self.db.query(UserGoal).filter_by(user_id=self.user_id, is_active=True).first()
            goal_progress = {
                "type": goal.goal_type.value if goal else "none",
                "on_track": adherence_rate >= 70
            }
            
            # Generate insights
            insights = []
            if adherence_rate < 50:
                insights.append("Low adherence - consider simpler meal planning")
            if daily_progress["progress"]["protein_g"]["percentage"] < 80:
                insights.append("Protein intake below target - add protein-rich snacks")
            if weekly_progress["totals"]["avg_calories_per_day"] < self.state.daily_targets["calories"] * 0.9:
                insights.append("Consistently under calorie target - may affect energy levels")
            
            # Achievements
            achievements = []
            if adherence_rate >= 80:
                achievements.append("Excellent meal logging consistency!")
            if daily_progress["status"] == "optimal":
                achievements.append("Daily targets met!")
            if meal_logs >= 20:
                achievements.append(f"Logged {meal_logs} meals this period!")
            
            return {
                "success": True,
                "report_date": datetime.now().isoformat(),
                "period": f"Last {period_days}