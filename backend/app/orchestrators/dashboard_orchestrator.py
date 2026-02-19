from typing import Dict, Any
import logging

from app.services.consumption_service_v2 import ConsumptionServiceV2
from app.services.inventory_management_service import InventoryManagementService
from app.services.meal_plan_service_v2 import MealPlanServiceV2
from app.services.onboarding import OnboardingService
from app.repositories.activity_repository import ActivityRepository
from app.orchestrators.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)


class DashboardOrchestrator(BaseOrchestrator):

    def __init__(
        self,
        consumption_service: ConsumptionServiceV2,
        inventory_service: InventoryManagementService,
        meal_plan_service: MealPlanServiceV2,
        onboarding_service: OnboardingService,
        activity_repo: ActivityRepository
    ):

        super().__init__(event_publisher=None)  
        self.consumption = consumption_service
        self.inventory = inventory_service
        self.meal_plan = meal_plan_service
        self.onboarding = onboarding_service
        self.activity_repo = activity_repo

    async def get_dashboard_summary(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        try:
            today_summary = await self.consumption.get_today_summary(user_id)

            next_meal_info = await self.meal_plan.get_next_meal(user_id)

            meals_card = {
                "meals_planned": today_summary.get("meals_planned", 0),
                "meals_consumed": today_summary.get("meals_consumed", 0),
                "meals_skipped": today_summary.get("meals_skipped", 0),
                "next_meal": next_meal_info["meal_type"],
                "next_meal_time": next_meal_info["time"]
            }

            total_macros = {
                "protein_g": today_summary.get("total_protein_g", 0),
                "carbs_g": today_summary.get("total_carbs_g", 0),
                "fat_g": today_summary.get("total_fat_g", 0),
            }
            targets = {
                "calories": today_summary.get("target_calories", 2000),
                "protein_g": today_summary.get("target_protein_g", 150),
                "carbs_g": today_summary.get("target_carbs_g", 200),
                "fat_g": today_summary.get("target_fat_g", 67),
            }

            macros_card = {
                "calories_consumed": round(today_summary.get("total_calories", 0), 1),
                "calories_target": round(targets.get("calories", 2000), 1),
                "calories_percentage": self._safe_percentage(
                    today_summary.get("total_calories", 0),
                    targets.get("calories", 2000)
                ),
                "protein_consumed": round(total_macros.get("protein_g", 0), 1),
                "protein_target": round(targets.get("protein_g", 150), 1),
                "protein_percentage": self._safe_percentage(
                    total_macros.get("protein_g", 0),
                    targets.get("protein_g", 150)
                ),
                "carbs_consumed": round(total_macros.get("carbs_g", 0), 1),
                "carbs_target": round(targets.get("carbs_g", 200), 1),
                "carbs_percentage": self._safe_percentage(
                    total_macros.get("carbs_g", 0),
                    targets.get("carbs_g", 200)
                ),
                "fat_consumed": round(total_macros.get("fat_g", 0), 1),
                "fat_target": round(targets.get("fat_g", 67), 1),
                "fat_percentage": self._safe_percentage(
                    total_macros.get("fat_g", 0),
                    targets.get("fat_g", 67)
                )
            }

            inventory_status = await self.inventory.calculate_inventory_status(user_id)

            inventory_card = {
                "expiring_soon_count": len(inventory_status.get("expiring_soon", [])),
                "low_stock_count": len(inventory_status.get("low_stock_items", [])),
                "out_of_stock_count": inventory_status.get("out_of_stock_count", 0),
                "total_items": inventory_status.get("total_items", 0)
            }


            current_streak = await self.consumption.calculate_streak(user_id)

            goal_data = await self.onboarding.get_goal_progress(user_id, current_streak)

            return {
                "meals_card": meals_card,
                "macros_card": macros_card,
                "inventory_card": inventory_card,
                "goal_card": goal_data
            }

        except Exception as e:
            logger.error(f"Error generating dashboard summary: {str(e)}")
            raise

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:

        try:
            activities = await self.activity_repo.get_recent_activity(
                user_id=user_id,
                limit=limit
            )

            return {
                "activities": activities,
                "total_count": len(activities)
            }

        except Exception as e:
            logger.error(f"Error fetching recent activity: {str(e)}")
            raise

    # ===== HELPER METHODS =====

    @staticmethod
    def _safe_percentage(consumed: float, target: float) -> float:
        """
        Calculate percentage safely (handle division by zero).

        EXTRACTED FROM: dashboard.py:193-194

        Args:
            consumed: Consumed amount
            target: Target amount

        Returns:
            Percentage (0-100+) rounded to 1 decimal
        """
        return round((consumed / target * 100), 1) if target > 0 else 0