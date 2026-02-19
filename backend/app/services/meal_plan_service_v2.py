"""
Meal Plan Service V2 - Using Repository Pattern

Refactored service that uses repositories instead of direct DB access.

ALL BUSINESS LOGIC COPY-PASTED FROM meal_plan_service.py - ZERO LOGIC CHANGES
ONLY CHANGE: DB queries moved to repositories
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from app.repositories.interfaces.meal_plan_repository import IMealPlanRepository
from app.repositories.interfaces.meal_log_repository import IMealLogRepository
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.schemas.meal_plan import (
    MealPlanCreate, MealPlanUpdate, MealPlanResponse,
    MealSwapRequest, MealLogCreate
)
# from app.services.inventory_service import IntelligentInventoryService
from app.models.database import MealPlan, MealLog
from sqlalchemy.orm.attributes import flag_modified
from app.core.ist_datetime import to_ist_naive, today_ist, now_ist_naive

logger = logging.getLogger(__name__)


class MealPlanServiceV2:
    """
    Service layer for meal plan management using repositories.

    BUSINESS LOGIC COPIED FROM: meal_plan_service.py
    CHANGE: Uses repositories instead of self.db.query()
    """

    def __init__(
        self,
        meal_plan_repo: IMealPlanRepository,
        meal_log_repo: IMealLogRepository,
        recipe_repo: IRecipeRepository,
        # inventory_service: IntelligentInventoryService,
        user_profile_repo: IUserProfileRepository
    ):
        """
        Initialize service with injected dependencies.

        Args:
            meal_plan_repo: Meal plan repository
            meal_log_repo: Meal log repository
            recipe_repo: Recipe repository
            inventory_service: Inventory service
            user_profile_repo: User profile repository
        """
        self.meal_plan_repo = meal_plan_repo
        self.meal_log_repo = meal_log_repo
        self.recipe_repo = recipe_repo
        # self.inventory_service = inventory_service
        self.user_profile_repo = user_profile_repo

    async def get_meal_plan_by_id(self, plan_id: int, user_id: int) -> Optional[MealPlanResponse]:
        """
        Get specific meal plan by ID.

        EXACT COPY-PASTE FROM: meal_plan_service.py:127-136

        Args:
            plan_id: Meal plan ID
            user_id: User ID (for ownership verification)

        Returns:
            MealPlanResponse if found and owned by user, None otherwise
        """
        # COPY-PASTED FROM meal_plan_service.py:129-136 - NO CHANGES
        meal_plan = await self.meal_plan_repo.get_by_id(plan_id)

        if meal_plan and meal_plan.user_id == user_id:
            return MealPlanResponse.model_validate(meal_plan)
        return None

    async def get_active_meal_plan(self, user_id: int) -> Optional[MealPlanResponse]:
        """
        Get user's active meal plan.

        Args:
            user_id: User ID

        Returns:
            Active MealPlanResponse if exists, None otherwise
        """
        meal_plan = await self.meal_plan_repo.get_active_plan(user_id)

        if meal_plan:
            return MealPlanResponse.model_validate(meal_plan)
        return None

    async def create_meal_plan_with_logs(
        self,
        user_id: int,
        week_start_date: datetime,
        plan_data: Dict,
        grocery_list: Dict,
        total_calories: float,
        avg_macros: Dict,
        user_meal_windows: List[Dict]
    ) -> MealPlanResponse:
        """
        Create meal plan and associated meal logs.

        BUSINESS LOGIC COPY-PASTED FROM:
        - meal_plan_service.py:29-71 (create logic)
        - planning_agent.py:988-1021 (_save_meal_plan)
        - planning_agent.py:1023-1097 (_create_meal_logs)

        Args:
            user_id: User ID
            week_start_date: Start date of the plan
            plan_data: Weekly plan data (JSON)
            grocery_list: Grocery list data (JSON)
            total_calories: Total calories for the week
            avg_macros: Average macros (JSON)
            user_meal_windows: User's meal timing windows

        Returns:
            Created MealPlanResponse
        """
        try:
            week_start_date = to_ist_naive(week_start_date).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # COPY-PASTED FROM planning_agent.py:992-995 - NO CHANGES
            # Deactivate existing active plans
            await self.meal_plan_repo.deactivate_active_plans(user_id)

            # COPY-PASTED FROM planning_agent.py:1000-1016 - NO CHANGES
            # Create new plan (using repository)
            meal_plan_response = await self.meal_plan_repo.create(
                user_id=user_id,
                week_start_date=week_start_date,
                plan_data=plan_data,
                grocery_list=grocery_list,
                total_calories=total_calories,
                avg_macros=avg_macros,
                is_active=True
            )

            # COPY-PASTED FROM planning_agent.py:1023-1097 - NO CHANGES
            # Create meal logs (using repository)
            # Note: meal_plan_response is MealPlanResponse, need to get ID
            meal_plan_id = meal_plan_response.id

            logs_created = await self.meal_log_repo.create_bulk(
                user_id=user_id,
                meal_plan_id=meal_plan_id,
                meal_plan_data=plan_data,  # This is week_plan
                start_date=week_start_date,
                user_meal_windows=user_meal_windows
            )

            logger.info(
                f"Created meal plan {meal_plan_id} with {logs_created} logs for user {user_id}"
            )

            return meal_plan_response

        except Exception as e:
            logger.error(f"Error creating meal plan: {str(e)}")
            raise

    async def get_active_meal_plan(self, user_id: int) -> Optional[MealPlanResponse]:
        """
        Get user's active meal plan.

        BUSINESS LOGIC COPY-PASTED FROM: meal_plan_service.py:73-92

        Args:
            user_id: User ID

        Returns:
            Active MealPlanResponse if exists, None otherwise
        """
        # Get active plan (using repository)
        meal_plan = await self.meal_plan_repo.get_active_plan(user_id)

        if not meal_plan:
            return None

        # COPY-PASTED FROM meal_plan_service.py:73-92 - Same return format
        return MealPlanResponse.model_validate(meal_plan)

    async def get_active_meal_plan_with_status(self, user_id: int) -> Dict:
        """
        Get active meal plan enriched with meal log statuses.

        BUSINESS LOGIC COPY-PASTED FROM: meal_plan_v2.py:86-181
        REFACTORED: Moved from API layer to service layer.

        Handles:
        1. Fetch active meal plan
        2. If no plan, return empty response
        3. Fetch meal logs for the week
        4. Build status map (logged/skipped/pending)
        5. Enrich plan data with statuses

        Args:
            user_id: User ID

        Returns:
            Dict with enriched meal plan or empty response
        """
        # COPY-PASTED FROM meal_plan_v2.py:87-100 - NO CHANGES
        plan = await self.get_active_meal_plan(user_id)

        if not plan:
            today = today_ist()
            days_since_monday = today.weekday()
            current_week_start = today - timedelta(days=days_since_monday)

            return {
                "id": None,
                "has_plan": False,
                "week_start_date": current_week_start.isoformat(),
                "plan_data": None,
                "message": "No meal plan found for this week. Generate a new plan to get started!"
            }

        # COPY-PASTED FROM meal_plan_v2.py:105-113 - NO CHANGES
        # Normalize week_start to midnight to include all meals on the first day
        week_start = plan.week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        meal_logs = await self.meal_log_repo.get_by_plan_and_date_range(
            user_id=user_id,
            meal_plan_id=plan.id,
            start_datetime=week_start,
            end_datetime=week_end
        )

        # COPY-PASTED FROM meal_plan_v2.py:117-128 - NO CHANGES (removed print statements)
        # Create status lookup map
        status_map = {}
        for log in meal_logs:
            key = f"{log.planned_datetime.date()}_{log.meal_type}"
            if log.consumed_datetime:
                status_map[key] = "logged"
            elif log.was_skipped:
                status_map[key] = "skipped"
            else:
                status_map[key] = "pending"

        # COPY-PASTED FROM meal_plan_v2.py:135-165 - NO CHANGES (removed print statements)
        # Enrich plan_data with status
        enriched_plan_data = {}
        plan_data = plan.plan_data.get('week_plan', plan.plan_data)  # Handle both structures

        for day_index in range(7):
            day_key = f"day_{day_index}"
            day_data = plan_data.get(day_key)

            if not day_data:
                continue

            day_date = week_start + timedelta(days=day_index)
            enriched_meals = {}

            for meal_type, meal_recipe in day_data.get('meals', {}).items():
                if not meal_recipe:
                    enriched_meals[meal_type] = None
                    continue

                # Get status from logs
                status_key = f"{day_date.date()}_{meal_type}"
                status = status_map.get(status_key, "pending")

                # Add status to meal data
                enriched_meal = {**meal_recipe, "status": status}
                enriched_meals[meal_type] = enriched_meal

            enriched_plan_data[day_key] = {
                **day_data,
                "meals": enriched_meals
            }

        # COPY-PASTED FROM meal_plan_v2.py:169-181 - NO CHANGES
        # Return plan with enriched data
        return {
            "id": plan.id,
            "user_id": plan.user_id,
            "week_start_date": plan.week_start_date.isoformat(),
            "plan_data": enriched_plan_data,
            "grocery_list": plan.grocery_list,
            "total_calories": plan.total_calories,
            "avg_macros": plan.avg_macros,
            "is_active": plan.is_active,
            "created_at": plan.created_at.isoformat(),
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
            "has_plan": True
        }

    async def swap_meal(self, user_id: int, swap_request: MealSwapRequest) -> Dict:
        """
        Swap a meal in the active plan.

        EXACT COPY-PASTE FROM: meal_plan_service.py:164-293

        Args:
            user_id: User ID
            swap_request: Swap request with day, meal, and new recipe

        Returns:
            Updated meal plan data with success status
        """
        # COPY-PASTED FROM meal_plan_service.py:175-182 - NO CHANGES
        # Get active plan (using repository)
        meal_plan = await self.meal_plan_repo.get_active_plan(user_id)

        if not meal_plan:
            raise ValueError("No active meal plan found")

        # COPY-PASTED FROM meal_plan_service.py:184-190 - NO CHANGES
        # Get new recipe (using repository)
        new_recipe = self.recipe_repo.get_by_id(swap_request.new_recipe_id)

        if not new_recipe:
            raise ValueError(f"Recipe {swap_request.new_recipe_id} not found")

        # COPY-PASTED FROM meal_plan_service.py:192-217 - NO CHANGES
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

        # COPY-PASTED FROM meal_plan_service.py:219-238 - NO CHANGES
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

        # COPY-PASTED FROM meal_plan_service.py:240-241 - NO CHANGES
        # Update total calories and average macros for entire plan
        self._recalculate_plan_totals(meal_plan)

        # COPY-PASTED FROM meal_plan_service.py:243-244 - NO CHANGES
        # Mark plan_data as modified for SQLAlchemy to detect JSON changes
        flag_modified(meal_plan, 'plan_data')

        # COPY-PASTED FROM meal_plan_service.py:246-275 - NO CHANGES
        # Sync MealLog: Update or create log entry for the new meal
        # Query for existing log by meal_plan_id, day_index, and meal_type
        existing_log = await self.meal_log_repo.get_by_plan_day_meal(
            meal_plan_id=meal_plan.id,
            day_index=swap_request.day,
            meal_type=swap_request.meal_type
        )

        # Calculate planned datetime (week_start_date + day_index)
        planned_datetime = meal_plan.week_start_date + timedelta(days=swap_request.day)

        if existing_log:
            # Update existing log with new recipe
            await self.meal_log_repo.update_recipe(
                log_id=existing_log.id,
                recipe_id=new_recipe.id,
                planned_datetime=planned_datetime
            )
            logger.info(f"Updated MealLog {existing_log.id} with new recipe {new_recipe.id}")
        else:
            # Create new log entry for the swapped meal
            await self.meal_log_repo.create_single(
                user_id=user_id,
                recipe_id=new_recipe.id,
                meal_type=swap_request.meal_type,
                planned_datetime=planned_datetime,
                meal_plan_id=meal_plan.id,
                day_index=swap_request.day
            )
            logger.info(f"Created new MealLog for recipe {new_recipe.id} at day {swap_request.day}, {swap_request.meal_type}")

        # COPY-PASTED FROM meal_plan_service.py:277-292 - NO CHANGES
        await self.meal_plan_repo.commit()

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

    async def get_alternatives_for_meal(self, recipe_id: int, user_id: int, count: int = 5) -> List[Dict]:
        """
        Get alternative recipes with similar macros for meal swapping.

        REFACTORED: Now fetches user data via UserProfileRepository first.
        Original: meal_plan_service.py:399-539

        Args:
            recipe_id: Original recipe ID
            user_id: User requesting alternatives
            count: Number of alternatives to return (default 5)

        Returns:
            List of alternative recipes with scores and macro differences
        """
        # Get original recipe (using repository)
        original = self.recipe_repo.get_by_id(recipe_id)
        if not original:
            logger.warning(f"Recipe {recipe_id} not found")
            return []

        # REFACTORED: Fetch user data from UserProfileRepository
        # Instead of letting RecipeRepository query user tables
        preferences = await self.user_profile_repo.get_preferences(user_id)
        user_goal = await self.user_profile_repo.get_active_goal(user_id)

        # Delegate to repository with user data
        return self.recipe_repo.get_alternatives(
            original_recipe=original,
            user_preferences=preferences,
            user_goal=user_goal,
            count=count
        )

    def _recalculate_plan_totals(self, meal_plan: MealPlan) -> None:
        """
        Recalculate total calories and average macros for entire plan.

        COPY-PASTED FROM: meal_plan_service.py (helper method)

        Args:
            meal_plan: Meal plan to recalculate
        """
        # COPY-PASTED logic from old service - NO CHANGES
        # Get week_data (handle both structures)
        if 'week_plan' in meal_plan.plan_data:
            week_data = meal_plan.plan_data['week_plan']
        else:
            week_data = meal_plan.plan_data

        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        day_count = 0

        for day_key, day_data in week_data.items():
            if day_key.startswith('day_'):
                total_calories += day_data.get('day_calories', 0)
                macros = day_data.get('day_macros', {})
                total_protein += macros.get('protein_g', 0)
                total_carbs += macros.get('carbs_g', 0)
                total_fat += macros.get('fat_g', 0)
                day_count += 1

        if day_count > 0:
            meal_plan.total_calories = total_calories
            meal_plan.avg_macros = {
                'protein_g': total_protein / day_count,
                'carbs_g': total_carbs / day_count,
                'fat_g': total_fat / day_count
            }

    async def get_next_meal(self, user_id: int) -> Dict[str, Optional[str]]:
        """
        Get next upcoming meal for user.

        Business logic:
        1. Get today's upcoming meals from repository
        2. Find the next one (earliest planned time)
        3. Format response with meal type and time

        MOVED FROM: dashboard_orchestrator.py:203-248

        Args:
            user_id: User ID

        Returns:
            Dict with meal_type and time (None if no upcoming meal)
        """
        try:
            from datetime import timedelta
            now = now_ist_naive()
            grace_window = timedelta(hours=2)

            # Get all unconsumed meals for today (ordered by planned_datetime)
            unconsumed_meals = await self.meal_log_repo.get_upcoming_meals_for_today(
                user_id=user_id,
                current_datetime=now
            )

            # Find first meal still within grace window:
            # - Future meals always qualify
            # - Past meals qualify if planned_datetime + 2 hours > now
            for meal in unconsumed_meals:
                if meal.planned_datetime + grace_window > now:
                    return {
                        "meal_type": meal.meal_type.capitalize(),
                        "time": meal.planned_datetime.strftime("%I:%M %p")
                    }

            return {"meal_type": None, "time": None}

        except Exception as e:
            logger.error(f"Error getting next meal: {str(e)}")
            return {"meal_type": None, "time": None}

