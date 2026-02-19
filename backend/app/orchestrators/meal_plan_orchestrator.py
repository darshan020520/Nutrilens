import logging
from typing import Dict, Optional, Any
from datetime import datetime

from app.orchestrators.base_orchestrator import BaseOrchestrator
from app.services.meal_plan_service_v2 import MealPlanServiceV2
from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints
from app.services.grocery_service import GroceryService
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.schemas.meal_plan import MealPlanResponse
from app.core.ist_datetime import now_ist, to_ist_naive

logger = logging.getLogger(__name__)


class MealPlanOrchestrator(BaseOrchestrator):

    def __init__(
        self,
        meal_plan_service: MealPlanServiceV2,
        optimizer: MealPlanOptimizer,
        grocery_service: GroceryService,
        user_profile_repo: IUserProfileRepository,
        event_publisher: Optional[Any] = None
    ):

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

        try:
            user_meal_windows = await self.user_profile_repo.get_meal_windows(user_id)

            logger.info(f"Running optimizer for user {user_id}")

            meal_plan = await self.optimizer.optimize(
                user_id=user_id,
                days=7,
                constraints=constraints,
                inventory=current_inventory
            )

            if not meal_plan:
                raise Exception("Optimizer failed to generate plan")

            normalized_start_date = to_ist_naive(start_date).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            meal_plan['user_id'] = user_id
            meal_plan['start_date'] = normalized_start_date.isoformat()
            meal_plan['generated_at'] = now_ist().isoformat()
            meal_plan['constraints'] = constraints.__dict__

            print(
                f"[LP] Orchestrator result: "
                f"method={meal_plan.get('optimization_method')} "
                f"success={meal_plan.get('success')} "
                f"avg_cal={meal_plan.get('avg_daily_calories', 0):.0f} "
                f"avg_protein={meal_plan.get('avg_macros', {}).get('protein_g', 0):.0f}g"
            )

            meal_plan['grocery_list'] = await self.grocery_service.calculate_for_plan(
                meal_plan['week_plan'],
                user_id
            )


            saved_plan = await self.meal_plan_service.create_meal_plan_with_logs(
                user_id=user_id,
                week_start_date=normalized_start_date,
                plan_data=meal_plan['week_plan'],
                grocery_list=meal_plan.get('grocery_list', {}),
                total_calories=meal_plan['total_calories'],
                avg_macros=meal_plan['avg_macros'],
                user_meal_windows=user_meal_windows
            )

            logger.info(f"Successfully generated meal plan for user {user_id}")

            await self.publish_event(
                "meal_plan.generated",
                {
                    "user_id": user_id,
                    "meal_plan_id": saved_plan.id,
                    "generated_at": now_ist().isoformat()
                }
            )

            # Merge optimization_method into the response dict so the API can surface it
            plan_dict = saved_plan.model_dump()
            plan_dict['optimization_method'] = meal_plan.get('optimization_method', 'linear_programming')
            return plan_dict

        except Exception as e:

            logger.error(f"Error generating meal plan: {str(e)}")
            return {"error": str(e)}

