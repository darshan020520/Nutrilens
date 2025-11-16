# backend/app/services/meal_plan_service.py

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import and_, func, cast, String, Float

from app.models.database import MealPlan, MealLog, Recipe, UserInventory
from app.schemas.meal_plan import (
    MealPlanCreate, MealPlanUpdate, MealPlanResponse,
    MealSwapRequest, MealLogCreate
)
from app.services.inventory_service import IntelligentInventoryService

logger = logging.getLogger(__name__)

class MealPlanService:
    """
    Service layer for meal plan management
    Handles CRUD operations, adjustments, and meal logging
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = IntelligentInventoryService(db)
    
    def create_meal_plan(self, user_id: int, plan_data: MealPlanCreate) -> MealPlanResponse:
        """Create a new meal plan"""
        try:
            # Deactivate existing active plans
            self.db.query(MealPlan).filter_by(
                user_id=user_id,
                is_active=True
            ).update({'is_active': False})
            
            # Create new plan
            meal_plan = MealPlan(
                user_id=user_id,
                week_start_date=plan_data.week_start_date,
                plan_data=plan_data.plan_data,
                grocery_list=plan_data.grocery_list,
                total_calories=plan_data.total_calories,
                avg_macros=plan_data.avg_macros,
                is_active=True
            )
            
            self.db.add(meal_plan)
            self.db.commit()
            self.db.refresh(meal_plan)
            # create meal logging 
            for day_key, day_data in meal_plan.plan_data['week_plan'].items():
                for meal_type, meal in day_data['meals'].items():
                    if meal:
                        log_entry = MealLog(
                            user_id=user_id,
                            recipe_id=meal.get('id'),
                            planned_datetime=day_data.get('date') or meal_plan.week_start_date,
                            portion_multiplier=1,
                            status='planned'
                        )
                        self.db.add(log_entry)
            
            logger.info(f"Created meal plan {meal_plan.id} for user {user_id}")
            return MealPlanResponse.from_orm(meal_plan)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating meal plan: {str(e)}")
            raise
    
    def get_active_meal_plan(self, user_id: int) -> Optional[MealPlanResponse]:
        """Get user's active meal plan that is still valid (hasn't expired)"""
        # First, deactivate old plans (plans where all 7 days have passed)
        self.deactivate_old_plans(user_id)

        # Get the active plan - meal plans can start on any day, not just Monday
        # The plan is valid as long as it's marked active and hasn't been deactivated
        meal_plan = self.db.query(MealPlan).filter(
            and_(
                MealPlan.user_id == user_id,
                MealPlan.is_active == True
            )
        ).first()

        if meal_plan:
            return MealPlanResponse.from_orm(meal_plan)
        return None

    def deactivate_old_plans(self, user_id: int) -> int:
        """
        Deactivate meal plans where all 7 days have passed

        Returns:
            Number of plans deactivated
        """
        try:
            # Calculate cutoff date - plans that started 7 days ago or earlier
            # A plan that starts on day X ends on day X+6 (7 days total)
            # So we deactivate plans where week_start_date + 7 days <= today
            today = datetime.now()
            cutoff_date = today - timedelta(days=7)

            # Deactivate plans where week_start_date + 7 days <= today
            # This means all 7 days of the plan have passed
            result = self.db.query(MealPlan).filter(
                and_(
                    MealPlan.user_id == user_id,
                    MealPlan.week_start_date <= cutoff_date,  # Fixed: was <, should be <=
                    MealPlan.is_active == True
                )
            ).update({'is_active': False}, synchronize_session=False)

            self.db.commit()

            if result > 0:
                logger.info(f"Deactivated {result} expired meal plan(s) for user {user_id}")

            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deactivating old plans: {str(e)}")
            return 0
    
    def get_meal_plan_by_id(self, plan_id: int, user_id: int) -> Optional[MealPlanResponse]:
        """Get specific meal plan by ID"""
        meal_plan = self.db.query(MealPlan).filter_by(
            id=plan_id,
            user_id=user_id
        ).first()
        
        if meal_plan:
            return MealPlanResponse.from_orm(meal_plan)
        return None
    
    def update_meal_plan(self, plan_id: int, user_id: int, updates: MealPlanUpdate) -> MealPlanResponse:
        """Update existing meal plan"""
        try:
            meal_plan = self.db.query(MealPlan).filter_by(
                id=plan_id,
                user_id=user_id
            ).first()
            
            if not meal_plan:
                raise ValueError(f"Meal plan {plan_id} not found")
            
            # Update fields
            for field, value in updates.dict(exclude_unset=True).items():
                setattr(meal_plan, field, value)
            
            self.db.commit()
            self.db.refresh(meal_plan)
            
            logger.info(f"Updated meal plan {plan_id}")
            return MealPlanResponse.from_orm(meal_plan)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating meal plan: {str(e)}")
            raise
    
    def swap_meal(self, user_id: int, swap_request: MealSwapRequest) -> Dict:
        """
        Swap a meal in the active plan

        Args:
            user_id: User ID
            swap_request: Swap request with day, meal, and new recipe

        Returns:
            Updated meal plan data with success status
        """
        # Get active plan
        meal_plan = self.db.query(MealPlan).filter_by(
            user_id=user_id,
            is_active=True
        ).first()

        if not meal_plan:
            raise ValueError("No active meal plan found")

        # Get new recipe
        new_recipe = self.db.query(Recipe).filter_by(
            id=swap_request.new_recipe_id
        ).first()

        if not new_recipe:
            raise ValueError(f"Recipe {swap_request.new_recipe_id} not found")

        # Handle both flat and nested week_plan structures
        # Some plans have: plan_data = {day_0: {...}, day_1: {...}}
        # Others have: plan_data = {week_plan: {day_0: {...}, day_1: {...}}}
        day_key = f"day_{swap_request.day}"

        if 'week_plan' in meal_plan.plan_data:
            # Nested structure
            week_data = meal_plan.plan_data['week_plan']
        else:
            # Flat structure (current case)
            week_data = meal_plan.plan_data

        # Validate day exists in plan
        if day_key not in week_data:
            raise ValueError(f"Day {swap_request.day} not in plan")

        # Validate meal type exists for this day
        if swap_request.meal_type not in week_data[day_key].get('meals', {}):
            raise ValueError(f"Meal type '{swap_request.meal_type}' not found for day {swap_request.day}")

        # Store old recipe for logging
        old_recipe = week_data[day_key]['meals'].get(swap_request.meal_type)
        old_recipe_title = old_recipe.get('title', 'N/A') if old_recipe else 'N/A'

        # Swap the meal using to_dict()
        week_data[day_key]['meals'][swap_request.meal_type] = new_recipe.to_dict()

        # Recalculate day totals
        day_calories = 0
        day_protein = 0
        day_carbs = 0
        day_fat = 0

        for meal in week_data[day_key]['meals'].values():
            if meal:
                macros = meal.get('macros_per_serving', {})
                day_calories += macros.get('calories', 0)
                day_protein += macros.get('protein_g', 0)
                day_carbs += macros.get('carbs_g', 0)
                day_fat += macros.get('fat_g', 0)

        week_data[day_key]['day_calories'] = day_calories
        week_data[day_key]['day_macros'] = {
            'protein_g': day_protein,
            'carbs_g': day_carbs,
            'fat_g': day_fat
        }

        # Update total calories and average macros for entire plan
        self._recalculate_plan_totals(meal_plan)

        # Mark plan_data as modified for SQLAlchemy to detect JSON changes
        flag_modified(meal_plan, 'plan_data')

        # Sync MealLog: Update or create log entry for the new meal
        # Query for existing log by meal_plan_id, day_index, and meal_type
        existing_log = self.db.query(MealLog).filter_by(
            meal_plan_id=meal_plan.id,
            day_index=swap_request.day,
            meal_type=swap_request.meal_type
        ).first()

        # Calculate planned datetime (week_start_date + day_index)
        planned_datetime = meal_plan.week_start_date + timedelta(days=swap_request.day)

        if existing_log:
            # Update existing log with new recipe
            existing_log.recipe_id = new_recipe.id
            existing_log.planned_datetime = planned_datetime
            logger.info(f"Updated MealLog {existing_log.id} with new recipe {new_recipe.id}")
        else:
            # Create new log entry for the swapped meal
            new_log = MealLog(
                user_id=user_id,
                recipe_id=new_recipe.id,
                meal_type=swap_request.meal_type,
                planned_datetime=planned_datetime,
                meal_plan_id=meal_plan.id,
                day_index=swap_request.day,
                portion_multiplier=1.0
            )
            self.db.add(new_log)
            logger.info(f"Created new MealLog for recipe {new_recipe.id} at day {swap_request.day}, {swap_request.meal_type}")

        self.db.commit()
        self.db.refresh(meal_plan)

        logger.info(f"Swapped meal for user {user_id}: day {swap_request.day}, "
                    f"{swap_request.meal_type}, old recipe: {old_recipe_title}, "
                    f"new recipe: {new_recipe.title}")

        # Return updated plan data
        return {
            'success': True,
            'day': swap_request.day,
            'meal_type': swap_request.meal_type,
            'new_recipe': new_recipe.to_dict(),
            'day_totals': {
                'calories': day_calories,
                'macros': week_data[day_key]['day_macros']
            }
        }

    def log_meal_consumption(self, user_id: int, meal_log: MealLogCreate) -> Dict:
        """
        Log meal consumption and update inventory
        
        Args:
            user_id: User ID
            meal_log: Meal consumption details
            
        Returns:
            Log confirmation with inventory updates
        """
        try:
            # Get recipe
            recipe = self.db.query(Recipe).filter_by(id=meal_log.recipe_id).first()
            if not recipe:
                raise ValueError(f"Recipe {meal_log.recipe_id} not found")
            
            # Create meal log entry
            log_entry = MealLog(
                user_id=user_id,
                recipe_id=meal_log.recipe_id,
                planned_datetime=meal_log.planned_datetime,
                consumed_datetime=meal_log.consumed_datetime or datetime.now(),
                portion_multiplier=meal_log.portion_multiplier,
                notes=meal_log.notes
            )
            
            self.db.add(log_entry)
            
            # Deduct ingredients from inventory
            inventory_updates = []
            if not meal_log.skip_inventory_update:
                for ingredient in recipe.ingredients:
                    quantity_to_deduct = ingredient['quantity_g'] * meal_log.portion_multiplier
                    
                    updated = self.inventory_service.deduct_item(
                        user_id=user_id,
                        item_id=ingredient['item_id'],
                        quantity=quantity_to_deduct
                    )
                    
                    inventory_updates.append({
                        'item_id': ingredient['item_id'],
                        'quantity_deducted': quantity_to_deduct,
                        'remaining': updated.get('remaining_quantity', 0)
                    })
            
            self.db.commit()
            
            # Calculate consumed macros
            consumed_macros = {
                'calories': recipe.macros_per_serving['calories'] * meal_log.portion_multiplier,
                'protein_g': recipe.macros_per_serving['protein_g'] * meal_log.portion_multiplier,
                'carbs_g': recipe.macros_per_serving['carbs_g'] * meal_log.portion_multiplier,
                'fat_g': recipe.macros_per_serving['fat_g'] * meal_log.portion_multiplier
            }
            
            logger.info(f"Logged meal consumption for user {user_id}: {recipe.title}")
            
            return {
                'success': True,
                'meal_logged': recipe.title,
                'consumed_macros': consumed_macros,
                'inventory_updates': inventory_updates,
                'log_id': log_entry.id
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error logging meal: {str(e)}")
            raise
    
    def get_meal_history(self, user_id: int, days: int = 7) -> List[Dict]:
        """Get user's meal consumption history"""
        since_date = datetime.now() - timedelta(days=days)
        
        logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.consumed_datetime >= since_date
            )
        ).order_by(MealLog.consumed_datetime.desc()).all()
        
        history = []
        for log in logs:
            recipe = self.db.query(Recipe).filter_by(id=log.recipe_id).first()
            if recipe:
                history.append({
                    'log_id': log.id,
                    'recipe': recipe.title,
                    'consumed_at': log.consumed_datetime.isoformat(),
                    'planned_for': log.planned_datetime.isoformat() if log.planned_datetime else None,
                    'portion_multiplier': log.portion_multiplier,
                    'macros': {
                        'calories': recipe.macros_per_serving['calories'] * log.portion_multiplier,
                        'protein_g': recipe.macros_per_serving['protein_g'] * log.portion_multiplier,
                        'carbs_g': recipe.macros_per_serving['carbs_g'] * log.portion_multiplier,
                        'fat_g': recipe.macros_per_serving['fat_g'] * log.portion_multiplier
                    },
                    'notes': log.notes
                })
        
        return history
    
    def get_alternatives_for_meal(self, recipe_id: int, user_id: int, count: int = 5) -> List[Dict]:
        """
        Get alternative recipes - SIMPLIFIED VERSION

        Strategy:
        1. SQL pre-filter: meal time, calories (±30%), dietary restrictions
        2. Simple scoring: macro similarity + goal bonus
        3. Return top N by score

        Args:
            recipe_id: Original recipe ID
            user_id: User requesting alternatives
            count: Number of alternatives to return (default 5)

        Returns:
            List of alternative recipes with scores and macro differences
        """
        try:
            # Get original recipe
            original = self.db.query(Recipe).filter_by(id=recipe_id).first()
            if not original:
                logger.warning(f"Recipe {recipe_id} not found")
                return []

            # Get user preferences and goal
            from app.models.database import UserPreference, UserGoal
            preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
            user_goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()

            # ============================================================
            # STAGE 1: SQL PRE-FILTERING (Hard requirements)
            # ============================================================

            target_cal = original.macros_per_serving['calories']

            # Query all recipes except the current one
            query = self.db.query(Recipe).filter(Recipe.id != recipe_id)

            # Apply dietary type if user has one
            if preferences and preferences.dietary_type:
                dietary_tag = preferences.dietary_type.value
                query = query.filter(
                    cast(Recipe.dietary_tags, String).contains(dietary_tag)
                )

            all_recipes = query.all()

            # Filter in Python (simpler and database-agnostic)
            min_cal = target_cal * 0.7
            max_cal = target_cal * 1.3
            original_meal_times = set(original.suitable_meal_times or [])

            candidates = []
            for recipe in all_recipes:
                # Check calorie range
                calories = recipe.macros_per_serving.get('calories', 0)
                if not (min_cal <= calories <= max_cal):
                    continue

                # Check meal time overlap
                recipe_meal_times = set(recipe.suitable_meal_times or [])
                if not (original_meal_times & recipe_meal_times):
                    continue

                candidates.append(recipe)

            if not candidates:
                logger.info(f"No alternative candidates found for recipe {recipe_id} (filtered {len(all_recipes)} by meal time)")
                return []

            logger.info(f"Found {len(candidates)} candidate alternatives for recipe {recipe_id} (from {len(all_recipes)} after calorie filter)")

            # ============================================================
            # STAGE 2: SIMPLE SCORING (Soft preferences)
            # ============================================================

            scored = []
            orig_macros = original.macros_per_serving

            for recipe in candidates:
                macros = recipe.macros_per_serving

                # Calculate macro differences (as percentages)
                cal_diff = abs(macros['calories'] - orig_macros['calories']) / orig_macros['calories']
                protein_diff = abs(macros['protein_g'] - orig_macros['protein_g']) / max(orig_macros['protein_g'], 1)
                carbs_diff = abs(macros['carbs_g'] - orig_macros['carbs_g']) / max(orig_macros['carbs_g'], 1)
                fat_diff = abs(macros['fat_g'] - orig_macros['fat_g']) / max(orig_macros['fat_g'], 1)

                # Simple similarity score: 1 - weighted_average_difference
                # Lower difference = higher score
                macro_similarity = 1 - (
                    cal_diff * 0.4 +        # Calories most important
                    protein_diff * 0.35 +   # Protein second
                    carbs_diff * 0.15 +     # Carbs third
                    fat_diff * 0.1          # Fat least important
                )

                # Goal bonus: +0.2 if matches user goal, otherwise 0
                goal_bonus = 0
                if user_goal and recipe.goals:
                    if user_goal.goal_type.value in recipe.goals:
                        goal_bonus = 0.2

                # Final score = macro_similarity (0-1) + goal_bonus (0-0.2)
                # Range: 0 to 1.2
                total_score = macro_similarity + goal_bonus

                # Match AlternativesResponse schema from schemas/meal_plan.py
                scored.append({
                    'recipe': {
                        'id': recipe.id,
                        'title': recipe.title,
                        'description': recipe.description,
                        'suitable_meal_times': recipe.suitable_meal_times or [],
                        'macros_per_serving': recipe.macros_per_serving,
                        'prep_time_min': recipe.prep_time_min or 0,
                        'cook_time_min': recipe.cook_time_min or 0,
                        'servings': recipe.servings or 1,
                        'goals': recipe.goals or [],
                        'dietary_tags': recipe.dietary_tags or []
                    },
                    'similarity_score': round(total_score, 3),
                    'calorie_difference': round(macros['calories'] - orig_macros['calories'], 1),
                    'protein_difference': round(macros['protein_g'] - orig_macros['protein_g'], 1),
                    'carbs_difference': round(macros['carbs_g'] - orig_macros['carbs_g'], 1),
                    'fat_difference': round(macros['fat_g'] - orig_macros['fat_g'], 1),
                    'suitable_for_swap': True
                })

            # Sort by score and return top N
            scored.sort(key=lambda x: x['similarity_score'], reverse=True)

            logger.info(f"Returning top {count} alternatives with scores: {[s['similarity_score'] for s in scored[:count]]}")

            return scored[:count]

        except Exception as e:
            logger.error(f"Error finding alternatives for recipe {recipe_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def adjust_for_eating_out(self, user_id: int, day: int, meal_type: str, external_calories: int) -> Dict:
        """
        Adjust meal plan when eating out
        
        Args:
            user_id: User ID
            day: Day of the week (0-6)
            meal_type: Meal being replaced
            external_calories: Estimated calories from external meal
            
        Returns:
            Adjusted meal plan for the day
        """
        try:
            # Get active plan
            meal_plan = self.db.query(MealPlan).filter_by(
                user_id=user_id,
                is_active=True
            ).first()
            
            if not meal_plan:
                raise ValueError("No active meal plan")
            
            day_key = f"day_{day}"
            if day_key not in meal_plan.plan_data['week_plan']:
                raise ValueError(f"Day {day} not in plan")
            
            # Mark meal as external
            meal_plan.plan_data['week_plan'][day_key]['meals'][meal_type] = {
                'title': 'Eating Out',
                'is_external': True,
                'macros_per_serving': {
                    'calories': external_calories,
                    'protein_g': external_calories * 0.3 / 4,  # Rough estimate
                    'carbs_g': external_calories * 0.4 / 4,
                    'fat_g': external_calories * 0.3 / 9
                }
            }
            
            # Recalculate totals
            self._recalculate_plan_totals(meal_plan)
            
            self.db.commit()

            log_entry = self.db.query(MealLog).filter_by(
                user_id=user_id,
                planned_datetime=day_date,
                meal_type=meal_type
            ).first()

            if log_entry:
                log_entry.status = 'eaten_external'
                log_entry.recipe_id = None
                log_entry.portion_multiplier = 1
            else:
                log_entry = MealLog(
                    user_id=user_id,
                    planned_datetime=day_date,
                    meal_type=meal_type,
                    status='eaten_external',
                    portion_multiplier=1
                )
                self.db.add(log_entry)

            
            return {
                'success': True,
                'day': day,
                'meal_type': meal_type,
                'external_calories': external_calories,
                'message': f"Adjusted day {day+1} for eating out"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adjusting for eating out: {str(e)}")
            raise
    
    def _recalculate_plan_totals(self, meal_plan: MealPlan):
        """Recalculate total calories and average macros for plan"""
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0

        # Handle both flat and nested week_plan structures
        if 'week_plan' in meal_plan.plan_data:
            week_data = meal_plan.plan_data['week_plan']
        else:
            week_data = meal_plan.plan_data

        for day_data in week_data.values():
            for meal in day_data.get('meals', {}).values():
                if meal:
                    macros = meal.get('macros_per_serving', {})
                    total_calories += macros.get('calories', 0)
                    total_protein += macros.get('protein_g', 0)
                    total_carbs += macros.get('carbs_g', 0)
                    total_fat += macros.get('fat_g', 0)

        days = len(week_data)

        meal_plan.total_calories = total_calories
        meal_plan.avg_macros = {
            'protein_g': round(total_protein / days, 1) if days > 0 else 0,
            'carbs_g': round(total_carbs / days, 1) if days > 0 else 0,
            'fat_g': round(total_fat / days, 1) if days > 0 else 0
        }