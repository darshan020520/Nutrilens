# backend/app/services/suggestion_engine.py
"""
Intelligent Suggestion Engine for NutriLens AI
Provides context-aware meal and nutrition suggestions
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
import logging
import numpy as np
from dataclasses import dataclass
from enum import Enum

from app.models.database import (
    User, UserProfile, UserGoal, UserPath, UserPreference,
    MealLog, Recipe, RecipeIngredient, Item, UserInventory,
    MealPlan, GoalType, PathType
)
from app.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)

class SuggestionContext(str, Enum):
    """Context for suggestions"""
    PRE_WORKOUT = "pre_workout"
    POST_WORKOUT = "post_workout"
    MORNING = "morning"
    EVENING = "evening"
    LOW_ENERGY = "low_energy"
    HIGH_STRESS = "high_stress"
    SOCIAL_EVENT = "social_event"
    MEAL_PREP = "meal_prep"

@dataclass
class SuggestionCriteria:
    """Criteria for generating suggestions"""
    user_id: int
    meal_type: Optional[str]
    context: Optional[SuggestionContext]
    remaining_macros: Dict[str, float]
    time_available: int  # minutes
    inventory_items: List[int]
    preferences: Dict[str, Any]
    restrictions: List[str]
    goal_type: str

class IntelligentSuggestionEngine:
    """Engine for generating intelligent meal and nutrition suggestions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = InventoryService(db)
    
    def generate_meal_suggestions(
        self,
        user_id: int,
        meal_type: Optional[str] = None,
        context: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate intelligent meal suggestions based on multiple factors"""
        
        try:
            # Build suggestion criteria
            criteria = self._build_criteria(user_id, meal_type, context)
            
            # Score all eligible recipes
            scored_recipes = self._score_recipes(criteria)
            
            # Get top suggestions
            top_recipes = sorted(scored_recipes, key=lambda x: x['total_score'], reverse=True)[:limit]
            
            # Format suggestions with explanations
            suggestions = []
            for recipe_data in top_recipes:
                suggestion = self._format_suggestion(recipe_data, criteria)
                suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {str(e)}")
            return []
    
    def _build_criteria(self, user_id: int, meal_type: Optional[str], 
                       context: Optional[str]) -> SuggestionCriteria:
        """Build comprehensive criteria for suggestions"""
        
        # Get user data
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        goal = self.db.query(UserGoal).filter(
            UserGoal.user_id == user_id
        ).first()
        
        preferences = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        # Calculate remaining macros for today
        remaining_macros = self._calculate_remaining_macros(user_id)
        
        # Get inventory
        inventory_items = self.inventory_service.get_user_inventory(user_id)
        inventory_ids = [item["item_id"] for item in inventory_items]
        
        # Determine time available
        current_hour = datetime.now().hour
        if context == SuggestionContext.PRE_WORKOUT:
            time_available = 30
        elif current_hour < 9 or current_hour > 20:
            time_available = 15  # Quick meals for early/late
        else:
            time_available = 45  # Normal meal prep time
        
        # Build preferences dict
        pref_dict = {}
        restrictions = []
        
        if preferences:
            pref_dict = {
                "dietary_type": preferences.dietary_type.value if preferences.dietary_type else None,
                "cuisines": preferences.cuisine_preferences or [],
                "max_prep_time": preferences.max_prep_time_weekday if datetime.now().weekday() < 5 
                               else preferences.max_prep_time_weekend
            }
            restrictions = preferences.allergies or []
            restrictions.extend(preferences.disliked_ingredients or [])
        
        # Determine context if not provided
        if not context:
            context = self._determine_context(user_id)
        
        return SuggestionCriteria(
            user_id=user_id,
            meal_type=meal_type or self._determine_meal_type(),
            context=SuggestionContext(context) if context else None,
            remaining_macros=remaining_macros,
            time_available=time_available,
            inventory_items=inventory_ids,
            preferences=pref_dict,
            restrictions=restrictions,
            goal_type=goal.goal_type.value if goal else "general_health"
        )
    
    def _calculate_remaining_macros(self, user_id: int) -> Dict[str, float]:
        """Calculate remaining macros for the day"""
        
        # Get user's daily targets
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        goal = self.db.query(UserGoal).filter(
            UserGoal.user_id == user_id
        ).first()
        
        if not profile:
            return {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 20}
        
        # Daily targets
        daily_calories = profile.goal_calories or profile.tdee or 2000
        weight_kg = profile.weight_kg or 70
        
        if goal and goal.macro_targets:
            protein_target = weight_kg * 1.6  # Default protein
            carbs_target = (daily_calories * goal.macro_targets.get("carbs", 0.4)) / 4
            fat_target = (daily_calories * goal.macro_targets.get("fat", 0.3)) / 9
        else:
            protein_target = weight_kg * 1.2
            carbs_target = daily_calories * 0.4 / 4
            fat_target = daily_calories * 0.3 / 9
        
        # Get consumed today
        today = date.today()
        consumed_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.consumed_datetime) == today
            )
        ).all()
        
        consumed = {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        
        for log in consumed_logs:
            if log.recipe and log.recipe.macros_per_serving:
                macros = log.recipe.macros_per_serving
                multiplier = log.portion_multiplier or 1.0
                
                consumed["calories"] += macros.get("calories", 0) * multiplier
                consumed["protein_g"] += macros.get("protein_g", 0) * multiplier
                consumed["carbs_g"] += macros.get("carbs_g", 0) * multiplier
                consumed["fat_g"] += macros.get("fat_g", 0) * multiplier
        
        # Calculate remaining
        remaining = {
            "calories": max(0, daily_calories - consumed["calories"]),
            "protein_g": max(0, protein_target - consumed["protein_g"]),
            "carbs_g": max(0, carbs_target - consumed["carbs_g"]),
            "fat_g": max(0, fat_target - consumed["fat_g"])
        }
        
        # Get remaining meals count
        pending_meals = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today,
                MealLog.consumed_datetime.is_(None),
                MealLog.was_skipped.is_(False)
            )
        ).count()
        
        # Distribute remaining across meals
        if pending_meals > 0:
            for key in remaining:
                remaining[key] = remaining[key] / pending_meals
        
        return remaining
    
    def _determine_context(self, user_id: int) -> Optional[str]:
        """Determine context based on time and user patterns"""
        
        current_hour = datetime.now().hour
        
        # Check recent activity patterns
        recent_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.consumed_datetime >= datetime.utcnow() - timedelta(hours=4)
            )
        ).all()
        
        # Time-based context
        if 5 <= current_hour < 9:
            return SuggestionContext.MORNING
        elif 20 <= current_hour < 24:
            return SuggestionContext.EVENING
        
        # Check if it's been long since last meal
        if recent_logs:
            last_meal_time = max(log.consumed_datetime for log in recent_logs)
            hours_since_meal = (datetime.utcnow() - last_meal_time).total_seconds() / 3600
            
            if hours_since_meal > 5:
                return SuggestionContext.LOW_ENERGY
        
        return None
    
    def _determine_meal_type(self) -> str:
        """Determine meal type based on current time"""
        
        hour = datetime.now().hour
        
        if 5 <= hour < 10:
            return "breakfast"
        elif 10 <= hour < 11:
            return "snack"
        elif 11 <= hour < 14:
            return "lunch"
        elif 14 <= hour < 17:
            return "snack"
        elif 17 <= hour < 21:
            return "dinner"
        else:
            return "snack"
    
    def _score_recipes(self, criteria: SuggestionCriteria) -> List[Dict[str, Any]]:
        """Score all recipes based on criteria"""
        
        # Get all recipes
        query = self.db.query(Recipe)
        
        # Filter by dietary restrictions
        if criteria.preferences.get("dietary_type"):
            dietary_type = criteria.preferences["dietary_type"]
            if dietary_type == "vegetarian":
                query = query.filter(
                    or_(
                        Recipe.dietary_tags.contains(["vegetarian"]),
                        Recipe.dietary_tags.contains(["vegan"])
                    )
                )
            elif dietary_type == "vegan":
                query = query.filter(Recipe.dietary_tags.contains(["vegan"]))
            elif dietary_type == "non_vegetarian":
                # No filter needed
                pass
        
        # Filter by meal type if specified
        if criteria.meal_type:
            query = query.filter(
                Recipe.suitable_meal_times.contains([criteria.meal_type])
            )
        
        recipes = query.all()
        
        scored_recipes = []
        
        for recipe in recipes:
            # Skip if contains restricted ingredients
            if self._contains_restricted_ingredients(recipe, criteria.restrictions):
                continue
            
            # Calculate scores
            scores = {
                "macro_fit": self._calculate_macro_fit_score(recipe, criteria.remaining_macros),
                "goal_alignment": self._calculate_goal_alignment_score(recipe, criteria.goal_type),
                "inventory_coverage": self._calculate_inventory_score(recipe, criteria.inventory_items),
                "time_appropriateness": self._calculate_time_score(recipe, criteria.time_available),
                "context_relevance": self._calculate_context_score(recipe, criteria.context),
                "preference_match": self._calculate_preference_score(recipe, criteria.preferences),
                "nutritional_quality": self._calculate_quality_score(recipe),
                "variety": self._calculate_variety_score(recipe, criteria.user_id)
            }
            
            # Weight the scores
            weights = {
                "macro_fit": 0.25,
                "goal_alignment": 0.20,
                "inventory_coverage": 0.15,
                "time_appropriateness": 0.10,
                "context_relevance": 0.10,
                "preference_match": 0.10,
                "nutritional_quality": 0.05,
                "variety": 0.05
            }
            
            total_score = sum(scores[k] * weights[k] for k in scores)
            
            scored_recipes.append({
                "recipe": recipe,
                "scores": scores,
                "total_score": total_score
            })
        
        return scored_recipes
    
    def _contains_restricted_ingredients(self, recipe: Recipe, restrictions: List[str]) -> bool:
        """Check if recipe contains restricted ingredients"""
        
        if not restrictions or not recipe.ingredients:
            return False
        
        for ingredient in recipe.ingredients:
            item = self.db.query(Item).filter(Item.id == ingredient.item_id).first()
            
            if item:
                # Check canonical name and aliases
                item_names = [item.canonical_name.lower()]
                if item.aliases:
                    item_names.extend([alias.lower() for alias in item.aliases])
                
                for restriction in restrictions:
                    restriction_lower = restriction.lower()
                    for item_name in item_names:
                        if restriction_lower in item_name or item_name in restriction_lower:
                            return True
        
        return False
    
    def _calculate_macro_fit_score(self, recipe: Recipe, target_macros: Dict[str, float]) -> float:
        """Calculate how well recipe fits macro targets"""
        
        if not recipe.macros_per_serving or not target_macros:
            return 50.0
        
        recipe_macros = recipe.macros_per_serving
        
        # Calculate percentage difference for each macro
        differences = []
        
        for macro in ["calories", "protein_g", "carbs_g", "fat_g"]:
            target = target_macros.get(macro, 0)
            actual = recipe_macros.get(macro, 0)
            
            if target > 0:
                diff_percentage = abs(actual - target) / target * 100
                # Score decreases as difference increases
                score = max(0, 100 - diff_percentage)
                differences.append(score)
        
        return np.mean(differences) if differences else 50.0
    
    def _calculate_goal_alignment_score(self, recipe: Recipe, goal_type: str) -> float:
        """Calculate goal alignment score"""
        
        if not recipe.goals:
            return 50.0
        
        if goal_type in recipe.goals:
            return 100.0
        
        # Partial credit for related goals
        goal_relationships = {
            "muscle_gain": ["weight_training", "body_recomp"],
            "fat_loss": ["body_recomp"],
            "weight_training": ["muscle_gain"],
            "endurance": ["general_health"]
        }
        
        related_goals = goal_relationships.get(goal_type, [])
        
        for related in related_goals:
            if related in recipe.goals:
                return 75.0
        
        return 25.0
    
    def _calculate_inventory_score(self, recipe: Recipe, inventory_items: List[int]) -> float:
        """Calculate inventory coverage score"""
        
        if not recipe.ingredients:
            return 100.0
        
        total_ingredients = len(recipe.ingredients)
        available_count = 0
        
        for ingredient in recipe.ingredients:
            if ingredient.item_id in inventory_items:
                available_count += 1
            elif ingredient.is_optional:
                available_count += 0.5  # Half credit for optional items
        
        return (available_count / total_ingredients * 100) if total_ingredients > 0 else 50.0
    
    def _calculate_time_score(self, recipe: Recipe, time_available: int) -> float:
        """Calculate time appropriateness score"""
        
        if not recipe.prep_time_min:
            return 50.0
        
        total_time = recipe.prep_time_min + (recipe.cook_time_min or 0)
        
        if total_time <= time_available:
            return 100.0
        elif total_time <= time_available * 1.5:
            return 75.0
        elif total_time <= time_available * 2:
            return 50.0
        else:
            return 25.0
    
    def _calculate_context_score(self, recipe: Recipe, context: Optional[SuggestionContext]) -> float:
        """Calculate context relevance score"""
        
        if not context:
            return 50.0
        
        context_preferences = {
            SuggestionContext.PRE_WORKOUT: {
                "tags": ["light", "energizing", "quick"],
                "avoid_tags": ["heavy", "high_fat"],
                "ideal_calories": (200, 400)
            },
            SuggestionContext.POST_WORKOUT: {
                "tags": ["high_protein", "recovery"],
                "avoid_tags": [],
                "ideal_calories": (300, 600)
            },
            SuggestionContext.MORNING: {
                "tags": ["breakfast", "energizing"],
                "avoid_tags": ["heavy"],
                "ideal_calories": (300, 500)
            },
            SuggestionContext.EVENING: {
                "tags": ["light", "comfort"],
                "avoid_tags": ["high_caffeine"],
                "ideal_calories": (400, 600)
            },
            SuggestionContext.LOW_ENERGY: {
                "tags": ["energizing", "balanced"],
                "avoid_tags": ["heavy"],
                "ideal_calories": (400, 500)
            },
            SuggestionContext.MEAL_PREP: {
                "tags": ["meal_prep_friendly", "batch_cooking"],
                "avoid_tags": [],
                "ideal_calories": (350, 550)
            }
        }
        
        prefs = context_preferences.get(context, {})
        score = 50.0
        
        # Check tags
        if recipe.tags and prefs.get("tags"):
            matching_tags = sum(1 for tag in prefs["tags"] if tag in recipe.tags)
            score += matching_tags * 15
        
        if recipe.tags and prefs.get("avoid_tags"):
            bad_tags = sum(1 for tag in prefs["avoid_tags"] if tag in recipe.tags)
            score -= bad_tags * 20
        
        # Check calorie range
        if recipe.macros_per_serving and prefs.get("ideal_calories"):
            calories = recipe.macros_per_serving.get("calories", 0)
            min_cal, max_cal = prefs["ideal_calories"]
            
            if min_cal <= calories <= max_cal:
                score += 20
        
        return min(100, max(0, score))
    
    def _calculate_preference_score(self, recipe: Recipe, preferences: Dict) -> float:
        """Calculate preference match score"""
        
        score = 50.0
        
        # Cuisine preference
        if preferences.get("cuisines") and recipe.cuisine:
            if recipe.cuisine in preferences["cuisines"]:
                score += 30
        
        # Prep time preference
        max_prep = preferences.get("max_prep_time", 60)
        if recipe.prep_time_min and recipe.prep_time_min <= max_prep:
            score += 20
        
        return min(100, score)
    
    def _calculate_quality_score(self, recipe: Recipe) -> float:
        """Calculate nutritional quality score"""
        
        if not recipe.macros_per_serving:
            return 50.0
        
        macros = recipe.macros_per_serving
        score = 50.0
        
        # Protein quality (>20g is good)
        protein = macros.get("protein_g", 0)
        if protein >= 30:
            score += 20
        elif protein >= 20:
            score += 15
        elif protein >= 15:
            score += 10
        
        # Fiber content (>5g is good)
        fiber = macros.get("fiber_g", 0)
        if fiber >= 8:
            score += 15
        elif fiber >= 5:
            score += 10
        elif fiber >= 3:
            score += 5
        
        # Balanced macros (check if no macro is too dominant)
        calories = macros.get("calories", 1)
        if calories > 0:
            protein_cal = protein * 4
            carb_cal = macros.get("carbs_g", 0) * 4
            fat_cal = macros.get("fat_g", 0) * 9
            
            protein_pct = protein_cal / calories
            carb_pct = carb_cal / calories
            fat_pct = fat_cal / calories
            
            # Good balance: protein 20-35%, carbs 35-55%, fat 20-35%
            if 0.20 <= protein_pct <= 0.35 and 0.35 <= carb_pct <= 0.55 and 0.20 <= fat_pct <= 0.35:
                score += 15
        
        return min(100, score)
    
    def _calculate_variety_score(self, recipe: Recipe, user_id: int) -> float:
        """Calculate variety score to avoid repetition"""
        
        # Check recent meals
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        recent_meals = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.recipe_id == recipe.id,
                MealLog.consumed_datetime >= week_ago
            )
        ).count()
        
        if recent_meals == 0:
            return 100.0
        elif recent_meals == 1:
            return 75.0
        elif recent_meals == 2:
            return 50.0
        else:
            return 25.0
    
    def _format_suggestion(self, recipe_data: Dict, criteria: SuggestionCriteria) -> Dict[str, Any]:
        """Format recipe suggestion with explanations"""
        
        recipe = recipe_data["recipe"]
        scores = recipe_data["scores"]
        
        # Generate reasons why this recipe is suggested
        reasons = []
        
        if scores["macro_fit"] > 80:
            reasons.append(f"Excellent macro fit ({scores['macro_fit']:.0f}% match)")
        
        if scores["goal_alignment"] > 75:
            reasons.append(f"Aligned with {criteria.goal_type} goal")
        
        if scores["inventory_coverage"] > 70:
            reasons.append("Most ingredients available")
        
        if scores["context_relevance"] > 70 and criteria.context:
            reasons.append(f"Perfect for {criteria.context.value}")
        
        if scores["nutritional_quality"] > 70:
            reasons.append("High nutritional quality")
        
        # Calculate portion suggestion
        portion_multiplier = 1.0
        if recipe.macros_per_serving and criteria.remaining_macros:
            recipe_calories = recipe.macros_per_serving.get("calories", 1)
            target_calories = criteria.remaining_macros.get("calories", recipe_calories)
            
            if recipe_calories > 0:
                portion_multiplier = target_calories / recipe_calories
                portion_multiplier = max(0.5, min(2.0, portion_multiplier))
        
        return {
            "recipe_id": recipe.id,
            "recipe_name": recipe.title,
            "description": recipe.description,
            "match_score": round(recipe_data["total_score"], 1),
            "reasons": reasons[:3],  # Top 3 reasons
            "macros": recipe.macros_per_serving,
            "adjusted_macros": {
                k: v * portion_multiplier for k, v in recipe.macros_per_serving.items()
            } if recipe.macros_per_serving else None,
            "portion_suggestion": round(portion_multiplier, 2),
            "prep_time": recipe.prep_time_min,
            "difficulty": recipe.difficulty_level,
            "tags": recipe.tags,
            "score_breakdown": {k: round(v, 1) for k, v in scores.items()}
        }


