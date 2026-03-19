"""
Meal Logging Orchestrator - Coordinates meal tracking workflows.

This orchestrator handles:
- Coordinating multiple services (MealTracking, External, Inventory, Consumption)
- Complex workflows (log meal → deduct inventory → notifications)
- Event publishing (notifications, WebSocket broadcasts)
- Transaction management across multiple services
- Comprehensive error handling and rollback logic

Architecture:
    API Endpoints (tracking_v2.py)
        ↓
    MealLoggingOrchestrator (coordinates workflows)
        ↓
    Services (business logic)
        ↓
    Repositories (data access)
        ↓
    Database Models
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import asyncio

from app.services.meal_tracking_service import MealTrackingService
from app.services.external_meal_service import ExternalMealService
from app.services.inventory_management_service import InventoryManagementService
from app.services.consumption_service_v2 import ConsumptionServiceV2
from app.infrastructure.events.event_publisher import EventPublisher
from app.core.ist_datetime import today_ist

logger = logging.getLogger(__name__)


class MealLoggingOrchestrator:
    """
    Orchestrates meal logging workflows across multiple services.

    Responsibilities:
    - Coordinate service calls in correct order
    - Handle cross-service transactions
    - Publish events for notifications and real-time updates
    - Aggregate results from multiple services
    - Comprehensive error handling with rollback
    """

    def __init__(
        self,
        meal_tracking_service: MealTrackingService,
        external_meal_service: ExternalMealService,
        inventory_service: InventoryManagementService,
        consumption_service: ConsumptionServiceV2,
        event_publisher: EventPublisher,
        db: AsyncSession
    ):
        """
        Initialize orchestrator with all required services.

        Args:
            meal_tracking_service: Service for meal tracking operations
            external_meal_service: Service for external meal operations
            inventory_service: Service for inventory management
            consumption_service: Service for consumption tracking
            notification_service: Service for sending notifications
            event_publisher: Publisher for real-time events
            db: Database session for transaction management
        """
        self.meal_tracking = meal_tracking_service
        self.external_meal = external_meal_service
        self.inventory = inventory_service
        self.consumption = consumption_service
        self.event_publisher = event_publisher
        self.db = db

    async def log_planned_meal(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float = 1.0,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate logging a planned meal with full workflow.

        Workflow:
        1. Log meal consumption (MealTrackingService)
        2. Auto-deduct ingredients (InventoryManagementService)
        3. Get updated daily summary (ConsumptionServiceV2)
        4. Check inventory status (InventoryManagementService)
        5. Publish events (notifications, WebSocket)
        6. Return comprehensive response

        Args:
            user_id: User ID
            meal_log_id: ID of planned meal to log
            portion_multiplier: Portion size multiplier (default 1.0)
            notes: Optional notes about consumption

        Returns:
            Dict: {
                "success": True,
                "meal_log": {...},
                "inventory_changes": [...],
                "daily_summary": {...},
                "inventory_status": {...},
                "notifications_sent": True
            }

        Raises:
            ValueError: If meal not found or invalid
            Exception: If workflow fails
        """
        try:
            logger.info(f"Starting planned meal logging workflow for user {user_id}, meal {meal_log_id}")

            # Step 1: Log the meal consumption
            meal_result = await self.meal_tracking.log_meal(
                user_id=user_id,
                meal_log_id=meal_log_id,
                portion_multiplier=portion_multiplier,
                notes=notes
            )

            # Step 2: Extract daily summary from meal_result (already fetched by service)
            # Service already called analytics_repo.get_today_summary() at line 113
            daily_summary = meal_result.get("updated_totals", {})

            # Step 3: Publish events for notifications (fire-and-forget for faster response)
            # EventPublisher routes to NotificationObserver which handles all notifications
            # Note: NotificationObserver only uses daily_totals, not inventory_status
            # REMOVED: inventory.calculate_inventory_status() - expensive operation not used anywhere
            # Fire-and-forget: Don't wait for event publishing (runs in background)
            asyncio.create_task(self._publish_meal_logged_events(
                user_id=user_id,
                meal_result=meal_result,
                daily_summary=daily_summary,
                inventory_status={}  # Not used by observer or endpoint response
            ))

            logger.info(f"Planned meal logging workflow completed for user {user_id}")

            return {
                "success": True,
                "meal_log": meal_result.get("logged_meal"),  # Fixed: v1 returns "logged_meal" not "meal_log"
                "inventory_changes": meal_result.get("inventory_changes", []),
                "daily_summary": daily_summary,
                "insights": meal_result.get("insights", []),
                "recommendations": meal_result.get("recommendations", []),
                "notifications_sent": True
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error in planned meal logging workflow: {e}")
            # Rollback handled by individual services
            raise Exception(f"Failed to log planned meal: {str(e)}")

    async def log_external_meal_workflow(
        self,
        user_id: int,
        meal_data: Dict,
        meal_log_id_to_replace: Optional[int] = None,
        meal_type: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate logging an external meal with full workflow.

        Workflow:
        1. Log external meal (ExternalMealService)
        2. Get updated daily summary (ConsumptionServiceV2)
        3. Check inventory status (InventoryManagementService)
        4. Publish events (notifications, WebSocket)
        5. Return comprehensive response with remaining meals

        Args:
            user_id: User ID
            meal_data: External meal data (dish_name, calories, macros, etc.)
            meal_log_id_to_replace: Optional meal to replace
            meal_type: Required if not replacing (breakfast, lunch, dinner, snack)
            notes: Optional notes

        Returns:
            Dict: {
                "success": True,
                "meal_log": {...},
                "daily_summary": {...},
                "remaining_meals": [...],
                "insights": [...],
                "recommendations": [...],
                "notifications_sent": True
            }

        Raises:
            ValueError: If meal data invalid
            Exception: If workflow fails
        """
        try:
            logger.info(f"Starting external meal logging workflow for user {user_id}")

            # Step 1: Log the external meal
            external_result = await self.external_meal.log_external_meal(
                user_id=user_id,
                meal_data=meal_data,
                meal_log_id_to_replace=meal_log_id_to_replace,
                meal_type=meal_type,
                notes=notes
            )

            # Step 2: Extract daily summary from external_result (already fetched by service)
            # Service already called analytics_repo.get_today_summary() at line 221
            daily_summary = external_result.get("updated_daily_totals", {})

            # Step 3: Publish events (fire-and-forget)
            asyncio.create_task(self._publish_external_meal_logged_events(
                user_id=user_id,
                external_result=external_result,
                daily_summary=daily_summary
            ))

            logger.info(f"External meal logging workflow completed for user {user_id}")

            # FIX: Preserve ALL fields from service response (don't lose data)
            # Service returns perfect structure matching OLD API - keep everything
            return {
                "success": True,
                "meal_log_id": external_result["meal_log_id"],
                "meal_type": external_result["meal_type"],
                "dish_name": external_result["dish_name"],
                "restaurant_name": external_result.get("restaurant_name"),
                "consumed_at": external_result["consumed_at"],
                "macros": external_result["macros"],
                "replaced_meal": external_result.get("replaced_meal", False),
                "original_recipe": external_result.get("original_recipe"),
                "updated_daily_totals": daily_summary,
                "remaining_calories": external_result.get("remaining_calories", 0),
                "remaining_meals_today": external_result.get("remaining_meals_today"),
                "insights": external_result.get("insights", []),
                "recommendations": external_result.get("recommendations", []),
                "notifications_sent": True
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error in external meal logging workflow: {e}")
            raise Exception(f"Failed to log external meal: {str(e)}")

    async def skip_meal_workflow(
        self,
        user_id: int,
        meal_log_id: int,
        skip_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate skipping a meal with full workflow.

        Workflow:
        1. Skip meal (MealTrackingService)
        2. Analyze skip patterns (ConsumptionServiceV2)
        3. Get updated daily summary (ConsumptionServiceV2)
        4. Check if restock needed (InventoryManagementService)
        5. Publish events
        6. Send notifications if patterns detected

        Args:
            user_id: User ID
            meal_log_id: ID of meal to skip
            skip_reason: Optional reason for skipping

        Returns:
            Dict: {
                "success": True,
                "meal_log": {...},
                "skip_patterns": {...},
                "daily_summary": {...},
                "recommendations": [...],
                "notifications_sent": True
            }

        Raises:
            ValueError: If meal not found or invalid
            Exception: If workflow fails
        """
        try:
            logger.info(f"Starting skip meal workflow for user {user_id}, meal {meal_log_id}")

            # Step 1: Skip the meal (includes skip patterns analysis)
            skip_result = await self.meal_tracking.skip_meal(
                user_id=user_id,
                meal_log_id=meal_log_id,
                reason=skip_reason  # Fixed: service expects 'reason' not 'skip_reason'
            )

            # Step 2: Extract skip patterns from result (already analyzed by service)
            skip_patterns = skip_result.get("skip_patterns", {})

            # Step 3: Publish events (fire-and-forget)
            asyncio.create_task(self._publish_meal_skipped_events(
                user_id=user_id,
                skip_result=skip_result,
                skip_patterns=skip_patterns
            ))

            logger.info(f"Skip meal workflow completed for user {user_id}")

            return {
                "success": True,
                "meal_log": skip_result,
                "skip_patterns": skip_patterns,
                "recommendations": skip_result.get("recommendations", []),
                "notifications_sent": True
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error in skip meal workflow: {e}")
            raise Exception(f"Failed to skip meal: {str(e)}")

    async def get_daily_overview(
        self,
        user_id: int,
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Orchestrate getting comprehensive daily overview.

        Workflow:
        1. Get today's meals (MealTrackingService)
        2. Get daily summary (ConsumptionServiceV2)
        3. Get inventory status (InventoryManagementService)
        4. Get expiring items (InventoryManagementService)
        5. Aggregate and return

        Args:
            user_id: User ID
            target_date: Optional date (defaults to today)

        Returns:
            Dict: {
                "date": "2025-11-26",
                "meals": [...],
                "daily_summary": {...},
                "inventory_status": {...},
                "expiring_items": [...],
                "recommendations": [...]
            }
        """
        try:
            if not target_date:
                target_date = today_ist()

            logger.info(f"Getting daily overview for user {user_id}, date {target_date}")

            # Step 1: Get today's consumption summary (includes meals data)
            today_summary = await self.consumption.get_today_summary(user_id)

            if not today_summary.get("success"):
                raise ValueError(f"Failed to get today summary: {today_summary.get('error')}")

            # Extract data from consumption result
            daily_summary = {k: v for k, v in today_summary.items() if k != "success"}
            meals = daily_summary.get("meals", [])

            # Step 3: Get expiring items
            expiring_items = await self.inventory.check_expiring_items(
                user_id=user_id,
                filter_mode="both",
                days_threshold=3
            )

            # Step 4: Generate recommendations
            recommendations = self._generate_daily_recommendations(
                daily_summary=daily_summary,
                expiring_items=expiring_items
            )

            return {
                "date": target_date.isoformat(),
                "meals": meals,
                "daily_summary": daily_summary,
                "expiring_items": expiring_items.get("items", []),
                "recommendations": recommendations
            }

        except Exception as e:
            logger.error(f"Error getting daily overview: {e}")
            raise Exception(f"Failed to get daily overview: {str(e)}")

    # ===== Private Helper Methods - Event Publishing =====

    async def _publish_meal_logged_events(
        self,
        user_id: int,
        meal_result: Dict,
        daily_summary: Dict,
        inventory_status: Dict
    ) -> None:
        """Publish events for meal logging (WebSocket, notifications)."""
        try:
            await self.event_publisher.publish(
                event_type="meal_logged",
                data={
                    "user_id": user_id,
                    "meal_log": meal_result.get("logged_meal"),
                    "daily_totals": daily_summary,
                    "inventory_changes": meal_result.get("inventory_changes", []),
                    "inventory_status": inventory_status
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish meal logged events: {e}")

    async def _publish_external_meal_logged_events(
        self,
        user_id: int,
        external_result: Dict,
        daily_summary: Dict
    ) -> None:
        """Publish events for external meal logging."""
        try:
            await self.event_publisher.publish(
                event_type="external_meal_logged",
                data={
                    "user_id": user_id,
                    "meal_data": external_result,
                    "daily_totals": daily_summary
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish external meal logged events: {e}")

    async def _publish_meal_skipped_events(
        self,
        user_id: int,
        skip_result: Dict,
        skip_patterns: Dict
    ) -> None:
        """Publish events for meal skipping."""
        try:
            await self.event_publisher.publish(
                event_type="meal_skipped",
                data={
                    "user_id": user_id,
                    "meal_log_id": skip_result.get("meal_log_id"),
                    "meal_type": skip_result.get("meal_type"),
                    "recipe_name": skip_result.get("recipe_name"),
                    "reason": skip_result.get("reason"),
                    "skip_patterns": skip_patterns
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish meal skipped events: {e}")


    def _generate_daily_recommendations(
        self,
        daily_summary: Dict,
        expiring_items: Dict
    ) -> List[str]:
        """Generate daily recommendations based on all data."""
        recommendations = []

        # Calorie recommendations
        total_calories = daily_summary.get("total_calories", 0)
        target_calories = daily_summary.get("target_calories", 2000)

        if total_calories < target_calories * 0.7:
            remaining = int(target_calories - total_calories)
            recommendations.append(f"You have {remaining} calories remaining - make sure to eat enough!")
        elif total_calories > target_calories * 1.1:
            over = int(total_calories - target_calories)
            recommendations.append(f"You're {over} calories over target - consider lighter meals")

        # Expiring items recommendations
        expiring_count = len(expiring_items.get("items", []))
        if expiring_count > 0:
            recommendations.append(f"Use soon: {expiring_count} items expiring within 3 days")

        return recommendations
