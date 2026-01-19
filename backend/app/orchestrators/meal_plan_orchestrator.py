"""
Meal Plan Orchestrator

Coordinates meal plan generation workflow.

ALL LOGIC COPY-PASTED FROM planning_agent.py:generate_weekly_meal_plan - ZERO LOGIC CHANGES
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

from app.orchestrators.base_orchestrator import BaseOrchestrator
from app.services.meal_plan_service_v2 import MealPlanServiceV2
from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints
from app.services.grocery_service import GroceryService
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.schemas.meal_plan import MealPlanResponse

logger = logging.getLogger(__name__)


class MealPlanOrchestrator(BaseOrchestrator):
    """
    Orchestrator for meal plan generation workflow.

    WORKFLOW COPY-PASTED FROM: planning_agent.py:161-224
    """

    def __init__(
        self,
        meal_plan_service: MealPlanServiceV2,
        optimizer: MealPlanOptimizer,
        grocery_service: GroceryService,
        user_profile_repo: IUserProfileRepository,
        event_publisher: Optional[Any] = None
    ):
        """
        Initialize orchestrator.

        Args:
            meal_plan_service: Meal plan service
            optimizer: Meal plan optimizer
            grocery_service: Grocery service
            user_profile_repo: User profile repository
            event_publisher: Optional event publisher
        """
        super().__init__(event_publisher)
        self.meal_plan_service = meal_plan_service
        self.optimizer = optimizer
        self.grocery_service = grocery_service
        self.user_profile_repo = user_profile_repo

    async def generate_weekly_meal_plan(
        self,
        user_id: int,
        start_date: datetime,
        constraints: OptimizationConstraints,
        current_inventory: Optional[Dict[int, float]]
    ) -> Dict:
        """
        Generate complete 7-day meal plan.

        REFACTORED: Now fetches user_meal_windows internally via repository
        Original: planning_agent.py:161-224

        Args:
            user_id: User ID
            start_date: Starting date for the plan
            constraints: Optimization constraints
            current_inventory: User's current inventory

        Returns:
            Generated meal plan with optimization details
        """
        try:
            # REFACTORED: Fetch meal windows from repository instead of receiving as parameter
            user_meal_windows = await self.user_profile_repo.get_meal_windows(user_id)

            # COPY-PASTED FROM planning_agent.py:184 - NO CHANGES
            logger.info(f"Running optimizer for user {user_id}")

            # REFACTORED: Added await since optimizer.optimize() is now async
            meal_plan = await self.optimizer.optimize(
                user_id=user_id,
                days=7,
                constraints=constraints,
                inventory=current_inventory
            )

            # COPY-PASTED FROM planning_agent.py:194-195 - NO CHANGES
            if not meal_plan:
                raise Exception("Optimizer failed to generate plan")

            # COPY-PASTED FROM planning_agent.py:198-201 - NO CHANGES
            # Enhance with metadata
            meal_plan['user_id'] = user_id
            meal_plan['start_date'] = start_date.isoformat()
            meal_plan['generated_at'] = datetime.now().isoformat()
            meal_plan['constraints'] = constraints.__dict__

            # REFACTORED: Added await since calculate_for_plan is now async
            # Calculate grocery list (now using GroceryService)
            meal_plan['grocery_list'] = await self.grocery_service.calculate_for_plan(
                meal_plan['week_plan'],
                user_id
            )

            # COPY-PASTED FROM planning_agent.py:207-210 - NO CHANGES
            # Save to database (now using service)
            saved_plan = await self.meal_plan_service.create_meal_plan_with_logs(
                user_id=user_id,
                week_start_date=datetime.fromisoformat(meal_plan['start_date']),
                plan_data=meal_plan['week_plan'],
                grocery_list=meal_plan.get('grocery_list', {}),
                total_calories=meal_plan['total_calories'],
                avg_macros=meal_plan['avg_macros'],
                user_meal_windows=user_meal_windows
            )

            # COPY-PASTED FROM planning_agent.py:212 - NO CHANGES (kept print for exact match)
            print("saved_plan", saved_plan)

            # COPY-PASTED FROM planning_agent.py:217 - NO CHANGES
            logger.info(f"Successfully generated meal plan for user {user_id}")

            # Publish event (new - event-driven)
            await self.publish_event(
                "meal_plan.generated",
                {
                    "user_id": user_id,
                    "meal_plan_id": saved_plan.id,
                    "generated_at": datetime.now().isoformat()
                }
            )

            # COPY-PASTED FROM planning_agent.py:218 - NO CHANGES
            return saved_plan

        except Exception as e:
            # COPY-PASTED FROM planning_agent.py:221-224 - NO CHANGES
            logger.error(f"Error generating meal plan: {str(e)}")
            return {"error": str(e)}
