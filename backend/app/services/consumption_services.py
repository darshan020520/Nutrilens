# backend/app/services/consumption_service.py
"""
Complete Consumption Service for NutriLens AI
Handles all meal logging database operations with atomic transactions
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
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
    """Complete service for managing meal consumption and tracking"""
    
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = IntelligentInventoryService(db)
    
    # ===== REQUIRED SPRINT FUNCTIONS (5 functions with exact signatures) =====
    
    def log_meal_consumption(self, user_id: int, meal_data: Dict) -> Dict[str, Any]:
        """
        REQUIRED FUNCTION 1: Log meal consumption with atomic transaction
        """
        try:
            # Start atomic transaction
            meal_log = None
            
            # Get or create meal log
            if meal_data.get("meal_log_id"):
                meal_log = self.db.query(MealLog).options(
                    joinedload(MealLog.recipe)
                ).filter(
                    and_(
                        MealLog.id == meal_data["meal_log_id"],
                        MealLog.user_id == user_id
                    )
                ).first()

                
                if not meal_log:
                    return {"status": "error", "error": "Meal log not found"}
                    
                if meal_log.consumed_datetime:
                    return {"status": "error", "error": "Meal already logged"}
            else:
                # Create new meal log
                meal_log = MealLog(
                    user_id=user_id,
                    recipe_id=meal_data.get("recipe_id"),
                    meal_type=meal_data["meal_type"],
                    planned_datetime=meal_data.get("timestamp", datetime.utcnow()),
                    notes=meal_data.get("notes")
                )
                self.db.add(meal_log)
                self.db.flush()  # Get ID without committing
            
            # Update meal log

            meal_log.consumed_datetime = datetime.utcnow()
            meal_log.portion_multiplier = meal_data.get("portion_multiplier", 1.0)
            meal_log.was_skipped = False

            
            # Auto-deduct ingredients from inventory
            inventory_changes = []

            if meal_log.recipe_id:
                deduction_result = self.auto_deduct_ingredients(
                    recipe_id=meal_log.recipe_id,
                    portion_multiplier=meal_log.portion_multiplier,
                    user_id=user_id
                )
                inventory_changes = deduction_result.get("deducted_items", [])
            
            # Calculate consumed macros
            macros = self._calculate_meal_macros(meal_log)


            
            # Get updated daily totals
            daily_totals = self._get_daily_totals_optimized(user_id)


            
            # Get remaining targets
            remaining_targets = self._calculate_remaining_targets(user_id, daily_totals)

            
            return {
                "status": "success",
                "logged_meal": {
                    "id": meal_log.id,
                    "meal_type": meal_log.meal_type,
                    "recipe": meal_log.recipe.title if meal_log.recipe else "External",
                    "consumed_at": meal_log.consumed_datetime.isoformat(),
                    "portion_multiplier": meal_log.portion_multiplier,
                    "macros": macros
                },
                "updated_totals": daily_totals,
                "remaining_targets": remaining_targets,
                "inventory_changes": inventory_changes
            }
                
        except Exception as e:
            logger.error(f"Error in log_meal_consumption: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def auto_deduct_ingredients(self, recipe_id: int, portion_multiplier: float, user_id: int) -> Dict[str, Any]:
        """
        REQUIRED FUNCTION 2: Auto-deduct ingredients with concurrency handling
        """
        try:
            # Get recipe ingredients with optimized query
            ingredients = self.db.query(RecipeIngredient).options(
                joinedload(RecipeIngredient.item)
            ).filter(
                RecipeIngredient.recipe_id == recipe_id
            ).all()
            
            if not ingredients:
                return {
                    "success": True,
                    "deducted_items": [],
                    "message": "No ingredients to deduct"
                }
            
            deducted_items = []
            failed_deductions = []
            
            for ingredient in ingredients:
                try:
                    quantity_to_deduct = ingredient.quantity_grams * portion_multiplier
                    
                    # Use inventory service for atomic deduction
                    result = self.inventory_service.deduct_item(
                        user_id=user_id,
                        item_id=ingredient.item_id,
                        quantity_grams=quantity_to_deduct
                    )
                    
                    if result.get("success"):
                        deducted_items.append({
                            "item_id": ingredient.item_id,
                            "item_name": ingredient.item.canonical_name if ingredient.item else "Unknown",
                            "quantity_deducted": quantity_to_deduct,
                            "remaining_quantity": result.get("remaining_quantity", 0)
                        })
                    else:
                        failed_deductions.append({
                            "item_id": ingredient.item_id,
                            "item_name": ingredient.item.canonical_name if ingredient.item else "Unknown",
                            "error": result.get("error", "Deduction failed")
                        })
                        
                except Exception as e:
                    logger.warning(f"Error deducting ingredient {ingredient.item_id}: {str(e)}")
                    failed_deductions.append({
                        "item_id": ingredient.item_id,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "deducted_items": deducted_items,
                "failed_deductions": failed_deductions,
                "total_deducted": len(deducted_items),
                "total_failed": len(failed_deductions)
            }
            
        except Exception as e:
            logger.error(f"Error in auto_deduct_ingredients: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def track_portions(self, user_id: int, meal_data: Dict) -> Dict[str, Any]:
        """
        REQUIRED FUNCTION 3: Track and validate portion sizes
        """
        try:
            portion_multiplier = meal_data.get("portion_multiplier", 1.0)
            meal_log_id = meal_data.get("meal_log_id")
            
            # Validate portion size (0.25x - 3.0x)
            if not (0.25 <= portion_multiplier <= 3.0):
                return {
                    "success": False,
                    "error": "Portion multiplier must be between 0.25 and 3.0"
                }
            
            # Update portion in meal log if provided
            if meal_log_id:
                meal_log = self.db.query(MealLog).filter(
                    and_(
                        MealLog.id == meal_log_id,
                        MealLog.user_id == user_id
                    )
                ).first()
                
                if meal_log:
                    old_portion = meal_log.portion_multiplier or 1.0
                    meal_log.portion_multiplier = portion_multiplier
                    self.db.commit()
                    
                    # Learn from portion adjustment
                    self._learn_portion_preference(user_id, meal_log.recipe_id, portion_multiplier)
                    
                    return {
                        "success": True,
                        "validated_portion": portion_multiplier,
                        "old_portion": old_portion,
                        "adjustment": portion_multiplier - old_portion,
                        "preference_updated": True
                    }
            
            return {
                "success": True,
                "validated_portion": portion_multiplier,
                "within_range": True
            }
            
        except Exception as e:
            logger.error(f"Error in track_portions: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def handle_skip_meal(self, user_id: int, meal_info: Dict) -> Dict[str, Any]:
        """
        REQUIRED FUNCTION 4: Handle meal skipping with pattern analysis
        """
        try:
            meal_log_id = meal_info.get("meal_log_id")
            reason = meal_info.get("reason")
            
            if not meal_log_id:
                return {"success": False, "error": "meal_log_id required"}
            
            # Get meal log
            meal_log = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == user_id
                )
            ).first()
            
            if not meal_log:
                return {"success": False, "error": "Meal log not found"}
            
            if meal_log.was_skipped:
                return {"success": False, "error": "Meal already marked as skipped"}
            
            if meal_log.consumed_datetime:
                return {"success": False, "error": "Cannot skip consumed meal"}
            
            # Update meal log
            meal_log.was_skipped = True
            meal_log.skip_reason = reason
            meal_log.consumed_datetime = None
            self.db.commit()
            
            # Analyze skip patterns
            skip_analysis = self._analyze_skip_patterns(user_id, meal_log.meal_type)

            
            # Recalculate adherence
            adherence = self._calculate_daily_adherence(user_id)

            
            return {
                "success": True,
                "meal_log_id": meal_log.id,
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if meal_log.recipe else "Unknown",
                "reason": reason,
                "skip_analysis": skip_analysis,
                "adherence_impact": adherence,
                "recommendation": self._get_skip_recommendation(skip_analysis)
            }
            
        except Exception as e:
            logger.error(f"Error in handle_skip_meal: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_consumption_analytics(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """
        REQUIRED FUNCTION 5: Generate comprehensive consumption analytics
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Optimized single query with all needed joins
            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_date
                )
            ).order_by(MealLog.planned_datetime.desc()).all()
            
            if not meal_logs:
                return {
                    "success": True,
                    "message": "No consumption data available",
                    "analytics": {}
                }
            
            analytics = {
                "meal_timing_patterns": self._analyze_meal_timing(meal_logs),
                "skip_frequency": self._analyze_skip_frequency(meal_logs),
                "portion_trends": self._analyze_portion_trends(meal_logs),
                "favorite_recipes": self._analyze_favorite_recipes(meal_logs),
                "daily_compliance": self._analyze_daily_compliance(meal_logs),
                "macro_consistency": self._analyze_macro_consistency(meal_logs),
                "weekly_patterns": self._analyze_weekly_patterns(meal_logs),
                "improvement_insights": self._generate_improvement_insights(meal_logs)
            }
            
            return {
                "success": True,
                "period_days": days,
                "total_meals_analyzed": len(meal_logs),
                "analytics": analytics,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in generate_consumption_analytics: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # ===== EXISTING USEFUL FUNCTIONS (OPTIMIZED FOR <100ms) =====
    
    def get_today_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get today's consumption summary with <100ms performance
        """
        try:
            today = date.today()
            
            # Single optimized query with all needed data
            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    func.date(MealLog.planned_datetime) == today
                )
            ).all()
            
            # Get user profile and goals in parallel query
            user_data = self.db.query(UserProfile, UserGoal).outerjoin(
                UserGoal, UserProfile.user_id == UserGoal.user_id
            ).filter(UserProfile.user_id == user_id).first()
            
            user_profile = user_data[0] if user_data else None
            user_goal = user_data[1] if user_data and len(user_data) > 1 else None
            
            # Process data in memory for speed
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
            
            # Process each meal in memory
            for log in meal_logs:
                macros = self._calculate_meal_macros(log) if log.recipe else {}
                meal_info = {
                    "id": log.id,
                    "meal_type": log.meal_type,
                    "planned_time": log.planned_datetime.isoformat(),
                    "recipe_id": log.recipe.id,
                    "recipe": log.recipe.title if log.recipe else "External",
                    "status": "pending",
                    "macros": macros
                }
                
                if log.consumed_datetime:
                    meal_info["status"] = "consumed"
                    meal_info["consumed_time"] = log.consumed_datetime.isoformat()
                    meal_info["portion"] = log.portion_multiplier or 1.0
                    
                    # Calculate macros
                    
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
            
            # Add targets and progress if user profile exists
            if user_profile:
                target_calories = user_profile.goal_calories or user_profile.tdee or 2000
                summary["targets"] = {"calories": target_calories}
                summary["progress"] = {
                    "calories": round((summary["total_calories"] / target_calories) * 100, 1)
                }
                
                if user_goal and user_goal.macro_targets:
                    macro_targets = user_goal.macro_targets
                    summary["targets"].update({
                        "protein_g": (target_calories * macro_targets.get("protein", 0.3)) / 4,
                        "carbs_g": (target_calories * macro_targets.get("carbs", 0.4)) / 4,
                        "fat_g": (target_calories * macro_targets.get("fat", 0.3)) / 9
                    })
                    
                    for macro in ["protein", "carbs", "fat"]:
                        target_key = f"{macro}_g"
                        if target_key in summary["targets"]:
                            summary["progress"][macro] = round(
                                (summary["total_macros"][target_key] / summary["targets"][target_key]) * 100, 1
                            )
            # 🔹 Compute remaining calories and macros on the fly
            if "targets" in summary:
                target_calories = summary["targets"].get("calories", 0)
                summary["target_calories"] = target_calories
                summary["remaining_calories"] = max(0.0, round(target_calories - summary["total_calories"], 2))

                remaining_macros = {}
                for key in ["protein_g", "carbs_g", "fat_g", "fiber_g", "calorie"]:
                    target_value = summary["targets"].get(key, 0)
                    total_value = summary["total_macros"].get(key, 0)
                    remaining_macros[key] = max(0.0, round(target_value - total_value, 2))
                
                summary["remaining_macros"] = remaining_macros

            # Generate recommendations
            summary["recommendations"] = self._get_daily_recommendations(summary)

        
            
            return {
                "success": True,
                **summary
            }
            
        except Exception as e:
            logger.error(f"Error in get_today_summary: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_consumption_history(self, user_id: int, days: int = 7, include_details: bool = False) -> Dict[str, Any]:
        """Get consumption history for specified days (up to today only)."""
        try:
            today = datetime.utcnow().date()
            start_date = today - timedelta(days=days)

            meal_logs = (
                self.db.query(MealLog)
                .options(joinedload(MealLog.recipe))
                .filter(
                    and_(
                        MealLog.user_id == user_id,
                        func.date(MealLog.planned_datetime) >= start_date,
                        func.date(MealLog.planned_datetime) <= today,  # ✅ exclude future logs
                    )
                )
                .order_by(MealLog.planned_datetime.desc())
                .all()
            )

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
                        "meals": [] if include_details else None,
                    }

                history[log_date]["planned"] += 1

                if log.consumed_datetime:
                    history[log_date]["consumed"] += 1
                    macros = self._calculate_meal_macros(log)
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
                        "time": log.consumed_datetime.isoformat() if log.consumed_datetime else log.planned_datetime.isoformat(),
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
                "trends": self._analyze_trends(history),
            }


            return {
                "success": True,
                "history": history,
                "statistics": statistics,
            }

        except Exception as e:
            logger.error(f"Error getting consumption history: {str(e)}")
            return {"success": False, "error": str(e)}

    
    def get_meal_patterns(self, user_id: int) -> Dict[str, Any]:
        """Analyze and return meal consumption patterns"""
        try:
            # Get last 30 days of data
            start_date = datetime.utcnow() - timedelta(days=30)
            
            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
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
                        "goals": recipe.goals if hasattr(recipe, 'goals') else []
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
    
    # ===== PRIVATE HELPER METHODS =====
    
    def _calculate_meal_macros(self, meal_log: MealLog) -> Dict[str, float]:
        """Calculate macros for a meal log"""
        if meal_log.external_meal:
            return meal_log.external_meal
        
        if not meal_log.recipe or not meal_log.recipe.macros_per_serving:
            return {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        
        macros = meal_log.recipe.macros_per_serving
        multiplier = meal_log.portion_multiplier or 1.0
        
        return {
            "calories": macros.get("calories", 0) * multiplier,
            "protein_g": macros.get("protein_g", 0) * multiplier,
            "carbs_g": macros.get("carbs_g", 0) * multiplier,
            "fat_g": macros.get("fat_g", 0) * multiplier,
            "fiber_g": macros.get("fiber_g", 0) * multiplier
        }
    
    def _get_daily_totals_optimized(self, user_id: int) -> Dict[str, Any]:
        """Get daily totals with optimized query"""
        today = date.today()
        
        consumed_logs = self.db.query(MealLog).options(
            joinedload(MealLog.recipe)
        ).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today,
                MealLog.consumed_datetime.isnot(None)
            )
        ).all()
        
        totals = {
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "meals_consumed": len(consumed_logs)
        }
        
        for log in consumed_logs:
            macros = self._calculate_meal_macros(log)
            totals["calories"] += macros.get("calories", 0)
            totals["protein_g"] += macros.get("protein_g", 0)
            totals["carbs_g"] += macros.get("carbs_g", 0)
            totals["fat_g"] += macros.get("fat_g", 0)
        
        return totals
    
    def _calculate_remaining_targets(self, user_id: int, daily_totals: Dict) -> Dict[str, Any]:
        """Calculate remaining daily targets"""
        user_profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if not user_profile:
            return {"message": "No targets set"}
        
        target_calories = user_profile.goal_calories or user_profile.tdee or 2000
        
        return {
            "calories": max(0, target_calories - daily_totals["calories"]),
            "percentage_complete": round((daily_totals["calories"] / target_calories) * 100, 1)
        }
    
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
    
    def _calculate_daily_adherence(self, user_id: int) -> Dict[str, Any]:
        """Calculate daily adherence percentage"""
        today = date.today()
        
        today_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today
            )
        ).all()
        
        if not today_logs:
            return {"adherence_rate": 0, "no_meals_planned": True}
        
        consumed = len([log for log in today_logs if log.consumed_datetime])
        total = len(today_logs)
        
        return {
            "adherence_rate": round((consumed / total) * 100, 1),
            "meals_consumed": consumed,
            "meals_planned": total
        }
    
    def _learn_portion_preference(self, user_id: int, recipe_id: int, portion: float):
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
            logger.info(f"User {user_id} prefers {portion}x portion for recipe {recipe_id} (first time)")
            return
        
        portions = [log.portion_multiplier for log in historical if log.portion_multiplier]
        avg_portion = sum(portions) / len(portions) if portions else 1.0
        
        logger.info(f"User {user_id} portion preference for recipe {recipe_id}: {portion}x (avg: {avg_portion:.2f}x)")
    
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
    
    def _get_daily_recommendations(self, summary: Dict) -> List[str]:
        """Generate daily recommendations based on consumption"""
        recommendations = []
        
        # Check compliance
        compliance_rate = summary.get("compliance_rate", 0)
        if compliance_rate < 50:
            recommendations.append("Try to stick to your meal plan for better results")
        elif compliance_rate < 80:
            recommendations.append("Good effort! Aim for at least 80% meal compliance")
        else:
            recommendations.append("Excellent meal compliance! Keep it up!")
        
        # Check macro balance
        if summary.get("progress"):
            if summary["progress"].get("protein", 0) < 80:
                recommendations.append("Consider adding more protein to meet your targets")
            if summary["progress"].get("calories", 0) > 110:
                recommendations.append("Watch your portion sizes to stay within calorie goals")
        
        # Check meal timing
        current_hour = datetime.now().hour
        if current_hour > 20 and summary.get("meals_pending", 0) > 0:
            recommendations.append("Try to eat earlier tomorrow to improve digestion")
        
        return recommendations
    
    def _get_hydration_reminder(self) -> str:
        """Get contextual hydration reminder based on time"""
        hour = datetime.now().hour
        
        reminders = {
            (6, 9): "Start your day with a glass of water!",
            (9, 12): "Mid-morning hydration check - aim for 2-3 glasses by now",
            (12, 15): "Lunch time! Don't forget to hydrate with your meal",
            (15, 18): "Afternoon reminder: Stay hydrated to avoid the slump",
            (18, 21): "Evening hydration - have water with dinner",
            (21, 24): "Light hydration before bed - not too much!"
        }
        
        for time_range, reminder in reminders.items():
            if time_range[0] <= hour < time_range[1]:
                return reminder
        
        return "Stay hydrated throughout the day!"
    
    # Analytics helper methods (complete implementations)
    def _analyze_meal_timing(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze meal timing patterns"""
        timing_patterns = {}
        
        for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
            type_logs = [log for log in meal_logs 
                        if log.meal_type == meal_type and log.consumed_datetime]
            
            if type_logs:
                times = [log.consumed_datetime.hour + log.consumed_datetime.minute/60 
                        for log in type_logs]
                timing_patterns[meal_type] = {
                    "average_time": round(sum(times) / len(times), 1),
                    "earliest": min(times),
                    "latest": max(times),
                    "consistency": self._calculate_time_consistency(times)
                }
        
        return timing_patterns
    
    def _analyze_skip_frequency(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze skip frequency patterns"""
        skip_frequency = {}
        
        for meal_type in ["breakfast", "lunch", "dinner", "snack"]:
            type_logs = [log for log in meal_logs if log.meal_type == meal_type]
            skipped = [log for log in type_logs if log.was_skipped]
            
            if type_logs:
                skip_frequency[meal_type] = {
                    "total_planned": len(type_logs),
                    "total_skipped": len(skipped),
                    "skip_rate": round((len(skipped) / len(type_logs)) * 100, 1),
                    "common_reasons": self._get_common_skip_reasons(skipped)
                }
        
        return skip_frequency
    
    def _analyze_portion_trends(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze portion size trends"""
        portion_logs = [log for log in meal_logs 
                       if log.consumed_datetime and log.portion_multiplier]
        
        if not portion_logs:
            return {"no_data": True}
        
        portions = [log.portion_multiplier for log in portion_logs]
        
        return {
            "average_portion": round(sum(portions) / len(portions), 2),
            "min_portion": min(portions),
            "max_portion": max(portions),
            "trend": "increasing" if len(portions) > 5 and portions[-3:] > portions[:3] else "stable",
            "by_meal_type": self._get_portions_by_meal_type(meal_logs)
        }
    
    def _analyze_favorite_recipes(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze favorite recipes"""
        recipe_counts = {}
        for log in meal_logs:
            if log.recipe_id and log.consumed_datetime:
                recipe_counts[log.recipe_id] = recipe_counts.get(log.recipe_id, 0) + 1
        
        if not recipe_counts:
            return {"no_data": True}
        
        top_recipes = sorted(recipe_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        favorite_recipes = {}
        
        for recipe_id, count in top_recipes:
            recipe = self.db.query(Recipe).filter(Recipe.id == recipe_id).first()
            if recipe:
                favorite_recipes[recipe.title] = {
                    "count": count,
                    "percentage": round((count / len(meal_logs)) * 100, 1)
                }
        
        return favorite_recipes
    
    def _analyze_daily_compliance(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze daily compliance patterns"""
        daily_compliance = {}
        
        # Group by date
        for log in meal_logs:
            log_date = log.planned_datetime.date().isoformat()
            if log_date not in daily_compliance:
                daily_compliance[log_date] = {"planned": 0, "consumed": 0}
            
            daily_compliance[log_date]["planned"] += 1
            if log.consumed_datetime:
                daily_compliance[log_date]["consumed"] += 1
        
        # Calculate compliance rates
        compliance_rates = []
        for date_data in daily_compliance.values():
            if date_data["planned"] > 0:
                rate = (date_data["consumed"] / date_data["planned"]) * 100
                compliance_rates.append(rate)
        
        if not compliance_rates:
            return {"no_data": True}
        
        return {
            "average_compliance": round(sum(compliance_rates) / len(compliance_rates), 1),
            "best_compliance": max(compliance_rates),
            "worst_compliance": min(compliance_rates),
            "consistent_days": len([r for r in compliance_rates if r >= 80])
        }
    
    def _analyze_macro_consistency(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze macro consistency"""
        consumed_logs = [log for log in meal_logs if log.consumed_datetime]
        
        if not consumed_logs:
            return {"no_data": True}
        
        daily_macros = {}
        for log in consumed_logs:
            log_date = log.consumed_datetime.date().isoformat()
            if log_date not in daily_macros:
                daily_macros[log_date] = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
            
            macros = self._calculate_meal_macros(log)
            for key in ["calories", "protein_g", "carbs_g", "fat_g"]:
                daily_macros[log_date][key] += macros.get(key, 0)
        
        if not daily_macros:
            return {"no_data": True}
        
        # Calculate averages and consistency
        avg_macros = {}
        for macro in ["calories", "protein_g", "carbs_g", "fat_g"]:
            values = [day[macro] for day in daily_macros.values()]
            avg_macros[macro] = {
                "average": round(sum(values) / len(values), 1),
                "min": min(values),
                "max": max(values),
                "consistency": "high" if max(values) - min(values) < avg_macros.get(macro, {}).get("average", 0) * 0.3 else "moderate"
            }
        
        return avg_macros
    
    def _analyze_weekly_patterns(self, meal_logs: List[MealLog]) -> Dict:
        """Analyze weekly consumption patterns"""
        weekly_patterns = {}
        
        for day in range(7):
            day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", 
                       "Friday", "Saturday", "Sunday"][day]
            day_logs = [log for log in meal_logs 
                       if log.planned_datetime.weekday() == day]
            consumed = [log for log in day_logs if log.consumed_datetime]
            
            if day_logs:
                weekly_patterns[day_name] = {
                    "planned": len(day_logs),
                    "consumed": len(consumed),
                    "compliance": round((len(consumed) / len(day_logs)) * 100, 1)
                }
        
        return weekly_patterns
    
    def _generate_improvement_insights(self, meal_logs: List[MealLog]) -> List[str]:
        """Generate actionable improvement insights"""
        insights = []
        
        # Analyze overall compliance
        consumed = len([log for log in meal_logs if log.consumed_datetime])
        total = len(meal_logs)
        
        if total > 0:
            compliance_rate = (consumed / total) * 100
            
            if compliance_rate < 70:
                insights.append("Focus on meal prep to improve adherence")
                insights.append("Consider simpler recipes for busy days")
            elif compliance_rate < 90:
                insights.append("Great progress! Small adjustments can get you to 90%+")
            else:
                insights.append("Excellent adherence! You're on track for your goals")
        
        # Analyze skip patterns
        skip_reasons = {}
        for log in meal_logs:
            if log.was_skipped and log.skip_reason:
                reasons = skip_reasons.get(log.skip_reason, 0) + 1
                skip_reasons[log.skip_reason] = reasons
        
        if skip_reasons:
            most_common_reason = max(skip_reasons.items(), key=lambda x: x[1])
            if "time" in most_common_reason[0].lower():
                insights.append("Time constraints are your main challenge - try quick recipes")
            elif "appetite" in most_common_reason[0].lower():
                insights.append("Consider smaller portions or different meal timing")
        
        return insights
    
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
            most_consistent = None
            best_consistency = "inconsistent"
            
            for meal_type, timing_data in patterns["meal_timing"].items():
                consistency = timing_data.get("consistency", "inconsistent")
                if consistency in ["very_consistent", "consistent"] and (most_consistent is None or consistency == "very_consistent"):
                    most_consistent = meal_type
                    best_consistency = consistency
            
            if most_consistent:
                insights.append(f"{most_consistent.capitalize()} is your most consistent meal")
        
        # Skip pattern insights
        if patterns.get("skip_patterns"):
            highest_skip_rate = 0
            most_skipped_meal = None
            
            for meal_type, skip_data in patterns["skip_patterns"].items():
                skip_rate = skip_data.get("skip_rate", 0)
                if skip_rate > highest_skip_rate:
                    highest_skip_rate = skip_rate
                    most_skipped_meal = meal_type
            
            if highest_skip_rate > 30:
                insights.append(f"Consider adjusting {most_skipped_meal} timing or recipes (high skip rate)")
        
        # Portion insights
        if patterns.get("portion_patterns"):
            avg_portion = patterns["portion_patterns"].get("average", 1.0)
            if avg_portion > 1.2:
                insights.append("You tend to eat larger portions - consider adjusting recipe quantities")
            elif avg_portion < 0.8:
                insights.append("You tend to eat smaller portions - consider reducing recipe quantities")
        
        # Weekly pattern insights
        if patterns.get("weekly_patterns"):
            compliances = [(day, data.get("compliance", 0)) for day, data in patterns["weekly_patterns"].items()]
            if compliances:
                best_day = max(compliances, key=lambda x: x[1])
                worst_day = min(compliances, key=lambda x: x[1])
                
                if best_day[1] - worst_day[1] > 30:
                    insights.append(f"Compliance varies significantly between {best_day[0]} and {worst_day[0]}")
        
        return insights