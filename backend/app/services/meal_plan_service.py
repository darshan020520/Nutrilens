# backend/app/services/meal_plan_service.py

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

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
            
            logger.info(f"Created meal plan {meal_plan.id} for user {user_id}")
            return MealPlanResponse.from_orm(meal_plan)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating meal plan: {str(e)}")
            raise
    
    def get_active_meal_plan(self, user_id: int) -> Optional[MealPlanResponse]:
        """Get user's active meal plan"""
        meal_plan = self.db.query(MealPlan).filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if meal_plan:
            return MealPlanResponse.from_orm(meal_plan)
        return None
    
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
            Updated meal plan for the day
        """
        try:
            # Get active plan
            meal_plan = self.db.query(MealPlan).filter_by(
                user_id=user_id,
                is_active=True
            ).first()
            
            if not meal_plan:
                raise ValueError("No active meal plan")
            
            # Get new recipe
            new_recipe = self.db.query(Recipe).filter_by(
                id=swap_request.new_recipe_id
            ).first()
            
            if not new_recipe:
                raise ValueError(f"Recipe {swap_request.new_recipe_id} not found")
            
            # Update plan data
            day_key = f"day_{swap_request.day}"
            if day_key not in meal_plan.plan_data['week_plan']:
                raise ValueError(f"Day {swap_request.day} not in plan")
            
            old_recipe = meal_plan.plan_data['week_plan'][day_key]['meals'].get(swap_request.meal_type)
            
            # Swap the meal
            meal_plan.plan_data['week_plan'][day_key]['meals'][swap_request.meal_type] = new_recipe.to_dict()
            
            # Recalculate day totals
            day_calories = 0
            day_protein = 0
            day_carbs = 0
            day_fat = 0
            
            for meal in meal_plan.plan_data['week_plan'][day_key]['meals'].values():
                if meal:
                    macros = meal.get('macros_per_serving', {})
                    day_calories += macros.get('calories', 0)
                    day_protein += macros.get('protein_g', 0)
                    day_carbs += macros.get('carbs_g', 0)
                    day_fat += macros.get('fat_g', 0)
            
            meal_plan.plan_data['week_plan'][day_key]['day_calories'] = day_calories
            meal_plan.plan_data['week_plan'][day_key]['day_macros'] = {
                'protein_g': day_protein,
                'carbs_g': day_carbs,
                'fat_g': day_fat
            }
            
            # Update total calories and average macros
            self._recalculate_plan_totals(meal_plan)
            
            self.db.commit()
            
            logger.info(f"Swapped meal for user {user_id}: day {swap_request.day}, {swap_request.meal_type}")
            
            return {
                'success': True,
                'day': swap_request.day,
                'meal_type': swap_request.meal_type,
                'old_recipe': old_recipe,
                'new_recipe': new_recipe.to_dict(),
                'updated_day_totals': {
                    'calories': day_calories,
                    'protein_g': day_protein,
                    'carbs_g': day_carbs,
                    'fat_g': day_fat
                }
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error swapping meal: {str(e)}")
            raise
    
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
    
    def get_alternatives_for_meal(self, recipe_id: int, count: int = 3) -> List[Dict]:
        """
        Get alternative recipes with similar macros
        
        Args:
            recipe_id: Original recipe ID
            count: Number of alternatives to return
            
        Returns:
            List of alternative recipes
        """
        try:
            # Get original recipe
            original = self.db.query(Recipe).filter_by(id=recipe_id).first()
            if not original:
                return []
            
            # Find recipes with similar calories (±20%)
            target_calories = original.macros_per_serving['calories']
            min_cal = target_calories * 0.8
            max_cal = target_calories * 1.2
            
            # Query similar recipes
            alternatives = self.db.query(Recipe).filter(
                and_(
                    Recipe.id != recipe_id,
                    Recipe.suitable_meal_times.overlap(original.suitable_meal_times)
                )
            ).all()
            
            # Score and filter alternatives
            scored_alternatives = []
            for alt in alternatives:
                alt_calories = alt.macros_per_serving['calories']
                if min_cal <= alt_calories <= max_cal:
                    # Calculate similarity score
                    cal_diff = abs(alt_calories - target_calories) / target_calories
                    protein_diff = abs(
                        alt.macros_per_serving['protein_g'] - 
                        original.macros_per_serving['protein_g']
                    ) / max(original.macros_per_serving['protein_g'], 1)
                    
                    similarity = 1 - (cal_diff * 0.5 + protein_diff * 0.5)
                    
                    scored_alternatives.append({
                        'recipe': alt.to_dict(),
                        'similarity_score': similarity,
                        'calorie_difference': alt_calories - target_calories,
                        'protein_difference': (
                            alt.macros_per_serving['protein_g'] - 
                            original.macros_per_serving['protein_g']
                        )
                    })
            
            # Sort by similarity and return top N
            scored_alternatives.sort(key=lambda x: x['similarity_score'], reverse=True)
            return scored_alternatives[:count]
            
        except Exception as e:
            logger.error(f"Error finding alternatives: {str(e)}")
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
        
        for day_data in meal_plan.plan_data['week_plan'].values():
            for meal in day_data.get('meals', {}).values():
                if meal:
                    macros = meal.get('macros_per_serving', {})
                    total_calories += macros.get('calories', 0)
                    total_protein += macros.get('protein_g', 0)
                    total_carbs += macros.get('carbs_g', 0)
                    total_fat += macros.get('fat_g', 0)
        
        days = len(meal_plan.plan_data['week_plan'])
        
        meal_plan.total_calories = total_calories
        meal_plan.avg_macros = {
            'protein_g': round(total_protein / days, 1) if days > 0 else 0,
            'carbs_g': round(total_carbs / days, 1) if days > 0 else 0,
            'fat_g': round(total_fat / days, 1) if days > 0 else 0
        }