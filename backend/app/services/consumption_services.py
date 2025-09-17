# backend/app/services/consumption_service.py
"""
Consumption tracking service for NutriLens AI
Handles meal logging, portion tracking, and consumption analytics
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import logging
import json

from app.models.database import (
    User, UserProfile, UserGoal, MealLog, Recipe, 
    RecipeIngredient, Item, UserInventory, MealPlan,
    AgentInteraction
)
from app.services.inventory_service import IntelligentInventoryService
from app.core.config import settings

logger = logging.getLogger(__name__)

class ConsumptionService:
    """Service for managing meal consumption and tracking"""
    
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = IntelligentInventoryService(db)
    
    def log_meal(
        self,
        user_id: int,
        meal_log_id: Optional[int] = None,
        recipe_id: Optional[int] = None,
        meal_type: Optional[str] = None,
        portion_multiplier: float = 1.0,
        notes: Optional[str] = None,
        external_calories: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Log a meal consumption
        Either use existing meal_log_id or create new with recipe_id and meal_type
        """
        try:
            meal_log = None
            
            # Get or create meal log
            if meal_log_id:
                meal_log = self.db.query(MealLog).filter(
                    and_(
                        MealLog.id == meal_log_id,
                        MealLog.user_id == user_id
                    )
                ).first()
                
                if not meal_log:
                    return {
                        "success": False,
                        "error": "Meal log not found"
                    }
            else:
                # Create new meal log for ad-hoc consumption
                if not meal_type:
                    return {
                        "success": False,
                        "error": "Meal type required for new log"
                    }
                
                meal_log = MealLog(
                    user_id=user_id,
                    recipe_id=recipe_id,
                    meal_type=meal_type,
                    planned_datetime=datetime.utcnow(),
                    portion_multiplier=portion_multiplier,
                    notes=notes
                )
                
                if external_calories:
                    meal_log.external_meal = {
                        "calories": external_calories,
                        "logged_at": datetime.utcnow().isoformat()
                    }
                
                self.db.add(meal_log)
            
            # Update meal log
            meal_log.consumed_datetime = datetime.utcnow()
            meal_log.was_skipped = False
            meal_log.portion_multiplier = portion_multiplier
            if notes:
                meal_log.notes = notes
            
            # Auto-deduct ingredients from inventory
            deduction_results = []
            if meal_log.recipe_id:
                deduction_results = self._deduct_ingredients(
                    user_id,
                    meal_log.recipe_id,
                    portion_multiplier
                )
            
            self.db.commit()
            
            # Calculate consumed macros
            consumed_macros = self._calculate_consumed_macros(meal_log)
            
            # Get daily progress
            daily_progress = self._get_daily_progress(user_id)
            
            # Check if user is on track
            adherence_status = self._check_adherence(user_id, daily_progress)
            
            return {
                "success": True,
                "meal_log_id": meal_log.id,
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if meal_log.recipe else "External meal",
                "consumed_at": meal_log.consumed_datetime.isoformat(),
                "portion": portion_multiplier,
                "macros_consumed": consumed_macros,
                "ingredients_deducted": deduction_results,
                "daily_progress": daily_progress,
                "adherence_status": adherence_status
            }
            
        except Exception as e:
            logger.error(f"Error logging meal: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def skip_meal(
        self,
        user_id: int,
        meal_log_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark a meal as skipped"""
        try:
            meal_log = self.db.query(MealLog).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == user_id
                )
            ).first()
            
            if not meal_log:
                return {"success": False, "error": "Meal log not found"}
            
            # Mark as skipped
            meal_log.was_skipped = True
            meal_log.skip_reason = reason
            meal_log.consumed_datetime = None
            self.db.commit()
            
            # Analyze skip patterns
            skip_analysis = self._analyze_skip_patterns(user_id, meal_log.meal_type)
            
            # Get adjusted daily targets
            adjusted_targets = self._adjust_daily_targets(user_id)
            
            return {
                "success": True,
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if meal_log.recipe else None,
                "reason": reason,
                "skip_analysis": skip_analysis,
                "adjusted_targets": adjusted_targets,
                "recommendation": self._get_skip_recommendation(skip_analysis)
            }
            
        except Exception as e:
            logger.error(f"Error skipping meal: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def update_portion(
        self,
        user_id: int,
        meal_log_id: int,
        new_portion_multiplier: float
    ) -> Dict[str, Any]:
        """Update portion size for a consumed meal"""
        try:
            meal_log = self.db.query(MealLog).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime.isnot(None)
                )
            ).first()
            
            if not meal_log:
                return {"success": False, "error": "Consumed meal not found"}
            
            old_multiplier = meal_log.portion_multiplier
            difference = new_portion_multiplier - old_multiplier
            
            # Update portion
            meal_log.portion_multiplier = new_portion_multiplier
            
            # Adjust inventory if needed
            if meal_log.recipe_id and difference != 0:
                if difference > 0:
                    # Deduct additional ingredients
                    self._deduct_ingredients(user_id, meal_log.recipe_id, difference)
                else:
                    # Add back ingredients (negative deduction)
                    self._deduct_ingredients(user_id, meal_log.recipe_id, difference)
            
            self.db.commit()
            
            # Learn from portion adjustment
            portion_learning = self._learn_portion_preference(
                user_id,
                meal_log.recipe_id,
                new_portion_multiplier
            )
            
            return {
                "success": True,
                "meal_log_id": meal_log_id,
                "old_portion": old_multiplier,
                "new_portion": new_portion_multiplier,
                "adjustment": difference,
                "learning": portion_learning
            }
            
        except Exception as e:
            logger.error(f"Error updating portion: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_today_summary(self, user_id: int) -> Dict[str, Any]:
        """Get today's consumption summary"""
        try:
            today = date.today()
            
            # Get all meal logs for today
            meal_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    func.date(MealLog.planned_datetime) == today
                )
            ).all()
            
            summary = {
                "date": today.isoformat(),
                "meals_planned": len(meal_logs),
                "meals_consumed": 0,
                "meals_skipped": 0,
                "meals_pending": 0,
                "total_calories": 0,
                "total_macros": {"protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0},
                "meals": [],
                "compliance_rate": 0,
                "hydration_reminder": self._get_hydration_reminder()
            }
            
            # Process each meal
            for log in meal_logs:
                meal_info = {
                    "id": log.id,
                    "meal_type": log.meal_type,
                    "planned_time": log.planned_datetime.isoformat(),
                    "recipe": log.recipe.title if log.recipe else "External",
                    "status": "pending"
                }
                
                if log.consumed_datetime:
                    meal_info["status"] = "consumed"
                    meal_info["consumed_time"] = log.consumed_datetime.isoformat()
                    meal_info["portion"] = log.portion_multiplier
                    
                    # Add macros
                    macros = self._calculate_consumed_macros(log)
                    meal_info["macros"] = macros
                    
                    summary["meals_consumed"] += 1
                    summary["total_calories"] += macros.get("calories", 0)
                    for key in ["protein_g", "carbs_g", "fat_g", "fiber_g"]:
                        summary["total_macros"][key] += macros.get(key, 0)
                        
                elif log.was_skipped:
                    meal_info["status"] = "skipped"
                    meal_info["skip_reason"] = log.skip_reason
                    summary["meals_skipped"] += 1
                else:
                    summary["meals_pending"] += 1
                
                summary["meals"].append(meal_info)
            
            # Calculate compliance rate
            if summary["meals_planned"] > 0:
                summary["compliance_rate"] = round(
                    (summary["meals_consumed"] / summary["meals_planned"]) * 100, 1
                )
            
            # Get user targets for comparison
            user_profile = self.db.query(UserProfile).filter(
                UserProfile.user_id == user_id
            ).first()
            
            user_goal = self.db.query(UserGoal).filter(
                UserGoal.user_id == user_id
            ).first()
            
            if user_profile and user_goal:
                target_calories = user_profile.goal_calories or user_profile.tdee
                macro_targets = user_goal.macro_targets or {
                    "protein": 0.3,
                    "carbs": 0.4,
                    "fat": 0.3
                }
                
                summary["targets"] = {
                    "calories": target_calories,
                    "protein_g": (target_calories * macro_targets.get("protein", 0.3)) / 4,
                    "carbs_g": (target_calories * macro_targets.get("carbs", 0.4)) / 4,
                    "fat_g": (target_calories * macro_targets.get("fat", 0.3)) / 9
                }
                
                # Calculate progress percentages
                summary["progress"] = {
                    "calories": round((summary["total_calories"] / target_calories) * 100, 1),
                    "protein": round((summary["total_macros"]["protein_g"] / summary["targets"]["protein_g"]) * 100, 1),
                    "carbs": round((summary["total_macros"]["carbs_g"] / summary["targets"]["carbs_g"]) * 100, 1),
                    "fat": round((summary["total_macros"]["fat_g"] / summary["targets"]["fat_g"]) * 100, 1)
                }
            
            # Get recommendations
            summary["recommendations"] = self._get_daily_recommendations(user_id, summary)
            
            return {
                "success": True,
                **summary
            }
            
        except Exception as e:
            logger.error(f"Error getting today's summary: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_consumption_history(
        self,
        user_id: int,
        days: int = 7,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """Get consumption history for specified days"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            meal_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_date
                )
            ).order_by(MealLog.planned_datetime.desc()).all()
            
            # Group by date
            history = {}
            for log in meal_logs:
                log_date = log.planned_datetime.date().isoformat()
                
                if log_date not in history:
                    history[log_date] = {
                        "planned": 0,
                        "consumed": 0,
                        "skipped": 0,
                        "calories": 0,
                        "macros": {"protein_g": 0, "carbs_g": 0, "fat_g": 0},
                        "meals": [] if include_details else None
                    }
                
                history[log_date]["planned"] += 1
                
                if log.consumed_datetime:
                    history[log_date]["consumed"] += 1
                    macros = self._calculate_consumed_macros(log)
                    history[log_date]["calories"] += macros.get("calories", 0)
                    for key in ["protein_g", "carbs_g", "fat_g"]:
                        history[log_date]["macros"][key] += macros.get(key, 0)
                elif log.was_skipped:
                    history[log_date]["skipped"] += 1
                
                if include_details and history[log_date]["meals"] is not None:
                    history[log_date]["meals"].append({
                        "meal_type": log.meal_type,
                        "recipe": log.recipe.title if log.recipe else "External",
                        "status": "consumed" if log.consumed_datetime else ("skipped" if log.was_skipped else "pending"),
                        "time": log.consumed_datetime.isoformat() if log.consumed_datetime else log.planned_datetime.isoformat()
                    })
            
            # Calculate statistics
            total_days = len(history)
            total_planned = sum(day["planned"] for day in history.values())
            total_consumed = sum(day["consumed"] for day in history.values())
            total_skipped = sum(day["skipped"] for day in history.values())
            
            statistics = {
                "period_days": days,
                "active_days": total_days,
                "total_meals_planned": total_planned,
                "total_meals_consumed": total_consumed,
                "total_meals_skipped": total_skipped,
                "overall_compliance": round((total_consumed / total_planned) * 100, 1) if total_planned > 0 else 0,
                "average_daily_calories": round(sum(day["calories"] for day in history.values()) / total_days, 0) if total_days > 0 else 0,
                "trends": self._analyze_trends(history)
            }
            
            return {
                "success": True,
                "history": history,
                "statistics": statistics
            }
            
        except Exception as e:
            logger.error(f"Error getting consumption history: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_meal_patterns(self, user_id: int) -> Dict[str, Any]:
        """Analyze and return meal consumption patterns"""
        try:
            # Get last 30 days of data
            start_date = datetime.utcnow() - timedelta(days=30)
            
            meal_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_date
                )
            ).all()
            
            patterns = {
                "meal_timing": {},
                "skip_patterns": {},
                "portion_patterns": {},
                "favorite_recipes": {},
                "meal_preferences": {},
                "weekly_patterns": {},
                "success_factors": []
            }
            
            # Analyze meal timing
            for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
                type_logs = [log for log in meal_logs 
                            if log.meal_type == meal_type and log.consumed_datetime]
                
                if type_logs:
                    times = [log.consumed_datetime.hour + log.consumed_datetime.minute/60 
                            for log in type_logs]
                    patterns["meal_timing"][meal_type] = {
                        "average_time": round(sum(times) / len(times), 1),
                        "earliest": min(times),
                        "latest": max(times),
                        "consistency": self._calculate_time_consistency(times)
                    }
            
            # Skip patterns
            for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
                type_logs = [log for log in meal_logs if log.meal_type == meal_type]
                skipped = [log for log in type_logs if log.was_skipped]
                
                if type_logs:
                    patterns["skip_patterns"][meal_type] = {
                        "skip_rate": round((len(skipped) / len(type_logs)) * 100, 1),
                        "common_reasons": self._get_common_skip_reasons(skipped),
                        "skip_days": self._get_skip_day_pattern(skipped)
                    }
            
            # Portion patterns
            portion_logs = [log for log in meal_logs 
                          if log.consumed_datetime and log.portion_multiplier]
            
            if portion_logs:
                portions = [log.portion_multiplier for log in portion_logs]
                patterns["portion_patterns"] = {
                    "average": round(sum(portions) / len(portions), 2),
                    "trend": "increasing" if portions[-5:] and sum(portions[-5:])/5 > sum(portions[:5])/5 else "stable",
                    "by_meal_type": self._get_portions_by_meal_type(meal_logs)
                }
            
            # Favorite recipes
            recipe_counts = {}
            for log in meal_logs:
                if log.recipe_id and log.consumed_datetime:
                    recipe_counts[log.recipe_id] = recipe_counts.get(log.recipe_id, 0) + 1
            
            top_recipes = sorted(recipe_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            for recipe_id, count in top_recipes:
                recipe = self.db.query(Recipe).filter(Recipe.id == recipe_id).first()
                if recipe:
                    patterns["favorite_recipes"][recipe.title] = {
                        "count": count,
                        "frequency": f"{count}/{len(meal_logs)*100:.1f}%",
                        "goals": recipe.goals
                    }
            
            # Weekly patterns (by day of week)
            for day in range(7):
                day_logs = [log for log in meal_logs 
                           if log.planned_datetime.weekday() == day]
                consumed = [log for log in day_logs if log.consumed_datetime]
                
                if day_logs:
                    day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", 
                               "Friday", "Saturday", "Sunday"][day]
                    patterns["weekly_patterns"][day_name] = {
                        "compliance": round((len(consumed) / len(day_logs)) * 100, 1),
                        "meal_count": len(day_logs) // 4  # Approximate weeks
                    }
            
            # Success factors
            patterns["success_factors"] = self._identify_success_factors(meal_logs)
            
            return {
                "success": True,
                "patterns": patterns,
                "insights": self._generate_pattern_insights(patterns)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing meal patterns: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # Helper methods
    def _deduct_ingredients(
        self,
        user_id: int,
        recipe_id: int,
        portion_multiplier: float
    ) -> List[Dict]:
        """Deduct recipe ingredients from inventory"""
        deduction_results = []
        
        ingredients = self.db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe_id
        ).all()
        
        for ingredient in ingredients:
            quantity_to_deduct = ingredient.quantity_grams * abs(portion_multiplier)
            
            if portion_multiplier > 0:
                # Normal deduction
                result = self.inventory_service.deduct_item(
                    user_id=user_id,
                    item_id=ingredient.item_id,
                    quantity_grams=quantity_to_deduct
                )
            else:
                # Add back (negative deduction)
                result = self.inventory_service.add_item(
                    user_id=user_id,
                    item_id=ingredient.item_id,
                    quantity_grams=quantity_to_deduct,
                    source="adjustment"
                )
            
            if result["success"]:
                item = self.db.query(Item).filter(Item.id == ingredient.item_id).first()
                deduction_results.append({
                    "item": item.canonical_name if item else "Unknown",
                    "quantity": quantity_to_deduct,
                    "operation": "deducted" if portion_multiplier > 0 else "added",
                    "remaining": result.get("remaining_quantity", 0)
                })
        
        return deduction_results
    
    def _calculate_consumed_macros(self, meal_log: MealLog) -> Dict[str, float]:
        """Calculate macros for consumed meal"""
        if meal_log.external_meal:
            return meal_log.external_meal
        
        if not meal_log.recipe:
            return {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        
        macros = meal_log.recipe.macros_per_serving or {}
        multiplier = meal_log.portion_multiplier or 1.0
        
        return {
            "calories": macros.get("calories", 0) * multiplier,
            "protein_g": macros.get("protein_g", 0) * multiplier,
            "carbs_g": macros.get("carbs_g", 0) * multiplier,
            "fat_g": macros.get("fat_g", 0) * multiplier,
            "fiber_g": macros.get("fiber_g", 0) * multiplier
        }
    
    def _get_daily_progress(self, user_id: int) -> Dict[str, Any]:
        """Get daily consumption progress"""
        today = date.today()
        
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today,
                MealLog.consumed_datetime.isnot(None)
            )
        ).all()
        
        total_calories = 0
        total_macros = {"protein_g": 0, "carbs_g": 0, "fat_g": 0}
        
        for log in meal_logs:
            macros = self._calculate_consumed_macros(log)
            total_calories += macros.get("calories", 0)
            for key in ["protein_g", "carbs_g", "fat_g"]:
                total_macros[key] += macros.get(key, 0)
        
        # Get targets
        user_profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if user_profile:
            target_calories = user_profile.goal_calories or user_profile.tdee or 2000
            remaining_calories = target_calories - total_calories
            
            return {
                "consumed_calories": round(total_calories, 0),
                "target_calories": round(target_calories, 0),
                "remaining_calories": round(remaining_calories, 0),
                "percentage": round((total_calories / target_calories) * 100, 1),
                "macros": total_macros,
                "status": self._get_progress_status(total_calories / target_calories)
            }
        
        return {
            "consumed_calories": round(total_calories, 0),
            "macros": total_macros
        }
    
    def _get_progress_status(self, ratio: float) -> str:
        """Get progress status based on consumption ratio"""
        current_hour = datetime.now().hour
        
        if current_hour < 10:  # Morning
            expected_ratio = 0.25
        elif current_hour < 14:  # Afternoon
            expected_ratio = 0.5
        elif current_hour < 19:  # Evening
            expected_ratio = 0.75
        else:  # Night
            expected_ratio = 0.95
        
        if ratio < expected_ratio - 0.1:
            return "behind_schedule"
        elif ratio > expected_ratio + 0.1:
            return "ahead_schedule"
        else:
            return "on_track"
    
    def _check_adherence(self, user_id: int, daily_progress: Dict) -> Dict[str, Any]:
        """Check adherence to goals"""
        status = daily_progress.get("status", "unknown")
        percentage = daily_progress.get("percentage", 0)
        
        adherence = {
            "status": status,
            "percentage": percentage,
            "message": "",
            "suggestions": []
        }
        
        if status == "behind_schedule":
            adherence["message"] = "You're behind your calorie target for this time of day"
            adherence["suggestions"].append("Consider a nutrient-dense snack")
        elif status == "ahead_schedule":
            adherence["message"] = "You're ahead of your calorie target"
            adherence["suggestions"].append("Consider lighter portions for remaining meals")
        else:
            adherence["message"] = "Great job! You're on track with your goals"
            adherence["suggestions"].append("Keep up the good work!")
        
        return adherence
    
    def _analyze_skip_patterns(self, user_id: int, meal_type: str) -> Dict[str, Any]:
        """Analyze skip patterns for a meal type"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.meal_type == meal_type,
                MealLog.planned_datetime >= week_ago
            )
        ).all()
        
        if not meal_logs:
            return {"no_data": True}
        
        total = len(meal_logs)
        skipped = len([log for log in meal_logs if log.was_skipped])
        
        reasons = {}
        for log in meal_logs:
            if log.was_skipped and log.skip_reason:
                reasons[log.skip_reason] = reasons.get(log.skip_reason, 0) + 1
        
        return {
            "total_planned": total,
            "total_skipped": skipped,
            "skip_rate": round((skipped / total) * 100, 1) if total > 0 else 0,
            "common_reasons": reasons
        }
    
    def _adjust_daily_targets(self, user_id: int) -> Dict[str, Any]:
        """Adjust daily targets based on skipped meals"""
        # Get remaining meals for today
        today = date.today()
        
        remaining_meals = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today,
                MealLog.consumed_datetime.is_(None),
                MealLog.was_skipped.is_(False)
            )
        ).all()
        
        if not remaining_meals:
            return {"no_meals_remaining": True}
        
        # Get consumed calories so far
        daily_progress = self._get_daily_progress(user_id)
        remaining_calories = daily_progress.get("remaining_calories", 0)
        
        if remaining_calories <= 0:
            return {"target_met": True}
        
        # Distribute remaining calories
        calories_per_meal = remaining_calories / len(remaining_meals)
        
        adjusted_targets = {
            "remaining_meals": len(remaining_meals),
            "calories_per_meal": round(calories_per_meal, 0),
            "meal_adjustments": []
        }
        
        for meal in remaining_meals:
            if meal.recipe:
                original_calories = meal.recipe.macros_per_serving.get("calories", 0)
                if original_calories > 0:
                    suggested_portion = calories_per_meal / original_calories
                    adjusted_targets["meal_adjustments"].append({
                        "meal_type": meal.meal_type,
                        "recipe": meal.recipe.title,
                        "suggested_portion": round(suggested_portion, 2)
                    })
        
        return adjusted_targets
    
    def _learn_portion_preference(
        self,
        user_id: int,
        recipe_id: int,
        portion: float
    ) -> Dict[str, Any]:
        """Learn from portion adjustments"""
        # Get historical portions for this recipe
        historical = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.recipe_id == recipe_id,
                MealLog.consumed_datetime.isnot(None)
            )
        ).all()
        
        if not historical:
            return {"learning": "First time consuming this recipe"}
        
        portions = [log.portion_multiplier for log in historical if log.portion_multiplier]
        avg_portion = sum(portions) / len(portions) if portions else 1.0
        
        learning = {
            "historical_average": round(avg_portion, 2),
            "current_portion": portion,
            "trend": "increasing" if portion > avg_portion else "decreasing",
            "recommendation": ""
        }
        
        if abs(portion - 1.0) > 0.3:
            if portion > 1.0:
                learning["recommendation"] = "Consider making this recipe with larger portions by default"
            else:
                learning["recommendation"] = "Consider making this recipe with smaller portions by default"
        
        return learning
    
    def _get_skip_recommendation(self, skip_analysis: Dict) -> str:
        """Generate recommendation based on skip analysis"""
        if skip_analysis.get("no_data"):
            return "Not enough data for recommendations"
        
        skip_rate = skip_analysis.get("skip_rate", 0)
        
        if skip_rate > 50:
            return "High skip rate detected. Consider adjusting meal timing or trying different recipes."
        elif skip_rate > 30:
            return "Moderate skip rate. Review if portion sizes or meal timing need adjustment."
        elif skip_rate > 0:
            return "Good adherence! Minor adjustments might help achieve 100% compliance."
        else:
            return "Perfect adherence! Keep up the excellent work!"
    
    def _get_daily_recommendations(self, user_id: int, summary: Dict) -> List[str]:
        """Generate daily recommendations based on consumption"""
        recommendations = []
        
        # Check compliance
        if summary["compliance_rate"] < 50:
            recommendations.append("Try to stick to your meal plan for better results")
        elif summary["compliance_rate"] < 80:
            recommendations.append("Good effort! Aim for at least 80% meal compliance")
        else:
            recommendations.append("Excellent meal compliance! Keep it up!")
        
        # Check macro balance
        if summary.get("progress"):
            if summary["progress"]["protein"] < 80:
                recommendations.append("Consider adding more protein to meet your targets")
            if summary["progress"]["calories"] > 110:
                recommendations.append("Watch your portion sizes to stay within calorie goals")
        
        # Check meal timing
        current_hour = datetime.now().hour
        if current_hour > 20 and summary["meals_pending"] > 0:
            recommendations.append("Try to eat earlier tomorrow to improve digestion")
        
        return recommendations
    
    def _analyze_trends(self, history: Dict) -> Dict[str, Any]:
        """Analyze consumption trends"""
        if not history:
            return {}
        
        dates = sorted(history.keys())
        recent_dates = dates[-7:] if len(dates) >= 7 else dates
        older_dates = dates[:-7] if len(dates) > 7 else []
        
        trends = {
            "compliance_trend": "stable",
            "calorie_trend": "stable",
            "best_day": "",
            "worst_day": ""
        }
        
        if recent_dates and older_dates:
            recent_compliance = sum(history[d]["consumed"] / history[d]["planned"] 
                                  for d in recent_dates if history[d]["planned"] > 0) / len(recent_dates)
            older_compliance = sum(history[d]["consumed"] / history[d]["planned"] 
                                 for d in older_dates if history[d]["planned"] > 0) / len(older_dates)
            
            if recent_compliance > older_compliance + 0.1:
                trends["compliance_trend"] = "improving"
            elif recent_compliance < older_compliance - 0.1:
                trends["compliance_trend"] = "declining"
        
        # Find best and worst days
        if history:
            compliance_by_day = {d: (data["consumed"] / data["planned"] * 100) if data["planned"] > 0 else 0 
                               for d, data in history.items()}
            trends["best_day"] = max(compliance_by_day, key=compliance_by_day.get)
            trends["worst_day"] = min(compliance_by_day, key=compliance_by_day.get)
        
        return trends
    
    def _calculate_time_consistency(self, times: List[float]) -> str:
        """Calculate how consistent meal times are"""
        if len(times) < 2:
            return "insufficient_data"
        
        # Calculate standard deviation
        mean = sum(times) / len(times)
        variance = sum((t - mean) ** 2 for t in times) / len(times)
        std_dev = variance ** 0.5
        
        if std_dev < 0.5:  # Within 30 minutes
            return "very_consistent"
        elif std_dev < 1.0:  # Within 1 hour
            return "consistent"
        elif std_dev < 2.0:  # Within 2 hours
            return "somewhat_consistent"
        else:
            return "inconsistent"
    
    def _get_common_skip_reasons(self, skipped_logs: List[MealLog]) -> Dict[str, int]:
        """Get common skip reasons"""
        reasons = {}
        for log in skipped_logs:
            if log.skip_reason:
                reasons[log.skip_reason] = reasons.get(log.skip_reason, 0) + 1
        return reasons
    
    def _get_skip_day_pattern(self, skipped_logs: List[MealLog]) -> Dict[str, int]:
        """Get pattern of which days meals are skipped"""
        skip_days = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for log in skipped_logs:
            day_name = days[log.planned_datetime.weekday()]
            skip_days[day_name] = skip_days.get(day_name, 0) + 1
        
        return skip_days
    
    def _get_portions_by_meal_type(self, meal_logs: List[MealLog]) -> Dict[str, float]:
        """Get average portions by meal type"""
        portions_by_type = {}
        
        for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
            type_logs = [log for log in meal_logs 
                        if log.meal_type == meal_type and log.consumed_datetime and log.portion_multiplier]
            
            if type_logs:
                portions = [log.portion_multiplier for log in type_logs]
                portions_by_type[meal_type] = round(sum(portions) / len(portions), 2)
        
        return portions_by_type
    
    def _identify_success_factors(self, meal_logs: List[MealLog]) -> List[str]:
        """Identify factors contributing to success"""
        factors = []
        
        # Calculate compliance by meal type
        meal_compliance = {}
        for meal_type in ["breakfast", "lunch", "dinner"]:
            type_logs = [log for log in meal_logs if log.meal_type == meal_type]
            consumed = [log for log in type_logs if log.consumed_datetime]
            if type_logs:
                compliance = (len(consumed) / len(type_logs)) * 100
                meal_compliance[meal_type] = compliance
        
        # Identify best performing meal
        if meal_compliance:
            best_meal = max(meal_compliance, key=meal_compliance.get)
            if meal_compliance[best_meal] > 80:
                factors.append(f"Strong {best_meal} compliance ({meal_compliance[best_meal]:.0f}%)")
        
        # Check weekend vs weekday
        weekday_logs = [log for log in meal_logs if log.planned_datetime.weekday() < 5]
        weekend_logs = [log for log in meal_logs if log.planned_datetime.weekday() >= 5]
        
        if weekday_logs and weekend_logs:
            weekday_compliance = len([l for l in weekday_logs if l.consumed_datetime]) / len(weekday_logs)
            weekend_compliance = len([l for l in weekend_logs if l.consumed_datetime]) / len(weekend_logs)
            
            if weekday_compliance > weekend_compliance + 0.2:
                factors.append("Better compliance on weekdays")
            elif weekend_compliance > weekday_compliance + 0.2:
                factors.append("Better compliance on weekends")
        
        return factors
    
    def _generate_pattern_insights(self, patterns: Dict) -> List[str]:
        """Generate insights from patterns"""
        insights = []
        
        # Meal timing insights
        if patterns.get("meal_timing"):
            most_consistent = min(patterns["meal_timing"].items(), 
                                 key=lambda x: x[1].get("consistency", "inconsistent"))
            if most_consistent:
                insights.append(f"{most_consistent[0].capitalize()} is your most consistent meal")
        
        # Skip pattern insights
        if patterns.get("skip_patterns"):
            most_skipped = max(patterns["skip_patterns"].items(), 
                              key=lambda x: x[1].get("skip_rate", 0))
            if most_skipped[1]["skip_rate"] > 30:
                insights.append(f"Consider adjusting {most_skipped[0]} timing or recipes")
        
        # Portion insights
        if patterns.get("portion_patterns"):
            avg_portion = patterns["portion_patterns"].get("average", 1.0)
            if avg_portion > 1.2:
                insights.append("You tend to eat larger portions - consider adjusting recipe quantities")
            elif avg_portion < 0.8:
                insights.append("You tend to eat smaller portions - consider reducing recipe quantities")
        
        # Weekly pattern insights
        if patterns.get("weekly_patterns"):
            best_day = max(patterns["weekly_patterns"].items(), 
                          key=lambda x: x[1].get("compliance", 0))
            worst_day = min(patterns["weekly_patterns"].items(), 
                           key=lambda x: x[1].get("compliance", 100))
            
            if best_day[1]["compliance"] - worst_day[1]["compliance"] > 30:
                insights.append(f"Compliance varies significantly between {best_day[0]} and {worst_day[0]}")
        
        return insights
    
    def _get_hydration_reminder(self) -> str:
        """Get contextual hydration reminder"""
        hour = datetime.now().hour
        
        if hour < 10:
            return "Start your day with a glass of water! Aim for 8-10 glasses today."
        elif hour < 14:
            return "Remember to stay hydrated! You should have had 3-4 glasses by now."
        elif hour < 18:
            return "Afternoon hydration check! Aim for 2-3 more glasses before evening."
        else:
            return "Evening hydration: Have a glass of water, but not too close to bedtime."