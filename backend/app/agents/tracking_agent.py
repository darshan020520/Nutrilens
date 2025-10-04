
# backend/app/agents/tracking_agent.py
"""
Complete Tracking Agent for NutriLens AI - Delegates to Services
Handles coordination, intelligence, and pattern analysis
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from dataclasses import dataclass, asdict

from langchain.agents import Tool
from langchain.memory import ConversationBufferMemory
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from app.models.database import (
    User, UserInventory, MealLog, Recipe, RecipeIngredient,
    Item, ReceiptUpload, AgentInteraction
)
from app.services.inventory_service import IntelligentInventoryService
from app.services.consumption_services import ConsumptionService
from app.services.notification_service import NotificationService, NotificationPriority
from app.services.websocket_manager import websocket_manager
from app.services.item_normalizer import IntelligentItemNormalizer
from app.core.config import settings

logger = logging.getLogger(__name__)

class TrackingEventType(str, Enum):
    MEAL_LOGGED = "meal_logged"
    MEAL_SKIPPED = "meal_skipped"
    INVENTORY_UPDATED = "inventory_updated"
    RECEIPT_PROCESSED = "receipt_processed"
    EXPIRY_ALERT = "expiry_alert"
    LOW_STOCK_ALERT = "low_stock_alert"

@dataclass
class TrackingState:
    """State management for tracking agent"""
    user_id: int
    daily_consumption: Dict[str, Any]
    current_inventory: List[Dict[str, Any]]
    pending_updates: List[Dict[str, Any]]
    sync_status: Dict[str, Any]
    last_sync: datetime
    alerts: List[Dict[str, Any]]
    consumption_patterns: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        # Convert datetime to string
        data['last_sync'] = self.last_sync.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrackingState':
        if isinstance(data.get('last_sync'), str):
            data['last_sync'] = datetime.fromisoformat(data['last_sync'])
        return cls(**data)

class TrackingAgent:
    """Agent for tracking consumption and inventory management"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.inventory_service = IntelligentInventoryService(db)
        self.consumption_service = ConsumptionService(db)  # FIX: Added missing service
        self.notification_service = NotificationService(db)  # FIX: Added notification service
        self.normalizer = IntelligentItemNormalizer(db)
        self.memory = ConversationBufferMemory()
        self.state = self._initialize_state()
        self.tools = self._create_tools()
        
    def _initialize_state(self) -> TrackingState:
        """Initialize tracking state using services"""
        # Use consumption service for optimized daily summary
        today_summary = self.consumption_service.get_today_summary(self.user_id)
        
        daily_consumption = {
            "date": datetime.utcnow().date().isoformat(),
            "meals_logged": today_summary.get("meals_consumed", 0),
            "meals_skipped": today_summary.get("meals_skipped", 0),
            "total_calories": today_summary.get("total_calories", 0),
            "total_macros": today_summary.get("total_macros", {"protein_g": 0, "carbs_g": 0, "fat_g": 0})
        }
        
        # Get current inventory using service
        inventory_result = self.inventory_service.get_user_inventory(self.user_id)
        current_inventory = inventory_result.get('items', [])
        
        # Generate intelligent alerts
        alerts = self._generate_intelligent_alerts(current_inventory)
        
        # Use consumption service for patterns
        patterns_result = self.consumption_service.generate_consumption_analytics(
            user_id=self.user_id, 
            days=7
        )
        consumption_patterns = patterns_result.get("analytics", {})
        
        return TrackingState(
            user_id=self.user_id,
            daily_consumption=daily_consumption,
            current_inventory=current_inventory,
            pending_updates=[],
            sync_status={"last_sync": datetime.utcnow(), "status": "synced"},
            last_sync=datetime.utcnow(),
            alerts=alerts,
            consumption_patterns=consumption_patterns
        )

        
    
    def _generate_intelligent_alerts(self, inventory_items: List[Dict]) -> List[Dict]:
        """Generate intelligent alerts from inventory data"""
        alerts = []
        
        for item in inventory_items:
            # Check expiry with intelligent prioritization
            if item.get("expiry_date"):
                try:
                    expiry = datetime.fromisoformat(item["expiry_date"])
                    days_until_expiry = (expiry - datetime.utcnow()).days
                    
                    if days_until_expiry <= 2:
                        priority = "urgent" if days_until_expiry <= 0 else "high"
                        alerts.append({
                            "type": TrackingEventType.EXPIRY_ALERT,
                            "item": item["item_name"],
                            "expiry_date": item["expiry_date"],
                            "days_until_expiry": days_until_expiry,
                            "priority": priority,
                            "message": f"{item['item_name']} {'expired' if days_until_expiry <= 0 else 'expires soon'}"
                        })
                except (ValueError, TypeError):
                    continue
            
            # Check low stock with intelligent thresholds
            quantity = item.get("quantity_grams", 0)
            if quantity < 100:  # Smart threshold
                alerts.append({
                    "type": TrackingEventType.LOW_STOCK_ALERT,
                    "item": item["item_name"],
                    "quantity": quantity,
                    "priority": "urgent" if quantity < 50 else "medium",
                    "message": f"Low stock: {item['item_name']} ({quantity}g remaining)"
                })
        
        return alerts
    
    def _create_tools(self) -> List[Tool]:
        """Create tracking agent tools"""
        return [
            Tool(
                name="process_receipt_ocr",
                func=self.process_receipt_ocr,
                description="Process OCR results from receipt upload"
            ),
            Tool(
                name="normalize_ocr_items",
                func=self.normalize_ocr_items,
                description="Normalize OCR extracted items to database items"
            ),
            Tool(
                name="update_inventory",
                func=self.update_inventory,
                description="Add or deduct items from inventory"
            ),
            Tool(
                name="log_meal_consumption",
                func=self.log_meal_consumption,
                description="Log that a meal has been consumed"
            ),
            Tool(
                name="track_skipped_meals",
                func=self.track_skipped_meals,
                description="Track meals that were skipped"
            ),
            Tool(
                name="check_expiring_items",
                func=self.check_expiring_items,
                description="Check for items nearing expiry"
            ),
            Tool(
                name="calculate_inventory_status",
                func=self.calculate_inventory_status,
                description="Calculate overall inventory percentage"
            ),
            Tool(
                name="generate_restock_list",
                func=self.generate_restock_list,
                description="Generate list of items needing restock"
            )
        ]
    
    # Tool implementations
    def process_receipt_ocr(self, receipt_id: int) -> Dict[str, Any]:
        """Process OCR results from receipt"""
        try:
            receipt = self.db.query(ReceiptUpload).filter(
                and_(
                    ReceiptUpload.id == receipt_id,
                    ReceiptUpload.user_id == self.user_id
                )
            ).first()
            
            if not receipt:
                return {"success": False, "error": "Receipt not found"}
            
            if not receipt.ocr_raw_text:
                return {"success": False, "error": "No OCR text available"}
            
            # Parse items from OCR text
            parsed_items = self._parse_ocr_text(receipt.ocr_raw_text)

            print("parsed_items", parsed_items)
            
            # Update receipt with parsed items
            receipt.parsed_items = parsed_items
            receipt.processing_status = "completed"
            receipt.processed_at = datetime.utcnow()
            self.db.commit()
            
            self._log_event(TrackingEventType.RECEIPT_PROCESSED, {
                "receipt_id": receipt_id,
                "items_found": len(parsed_items),
                "confidence": "high" if len(parsed_items) > 0 else "low"
            })
            
            return {
                "success": True,
                "items_found": len(parsed_items),
                "parsed_items": parsed_items,
                "recommendations": self._generate_ocr_recommendations(parsed_items)
            }
            
        except Exception as e:
            logger.error(f"Error processing OCR: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def normalize_ocr_items(self, ocr_items: str) -> Dict[str, Any]:
        """Fixed: Normalize OCR items to database items"""
        try:

            if not ocr_items or not isinstance(ocr_items, str):
                return {
                    "success": False,
                    "error": "Invalid or empty OCR items input"
                }
            
            normalized_items = []
            unmatched_items = []
            
            # Split the input text into lines
            lines = ocr_items.strip().split('\n')

            if not lines:
                return {
                    "success": True,
                    "normalized_count": 0,
                    "unmatched_count": 0,
                    "normalized_items": [],
                    "unmatched_items": []
                }
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Use the normalizer
                result = self.normalizer.normalize(line)
                
                if result.item and result.confidence >= 0.6:
                    normalized_items.append({
                        "original": line,
                        "matched_item": {
                            "id": result.item.id,
                            "name": result.item.canonical_name
                        },
                        "confidence": result.confidence,
                        "quantity_grams": self.normalizer.convert_to_grams(
                            result.extracted_quantity,
                            result.extracted_unit,
                            result.item
                        )
                    })
                else:
                    unmatched_items.append(line)
            
            return {
                "success": True,
                "normalized_count": len(normalized_items),
                "unmatched_count": len(unmatched_items),
                "normalized_items": normalized_items,
                "unmatched_items": unmatched_items,
                "recommendations": self._generate_normalization_recommendations(normalized_items, unmatched_items)
            }
            
        except Exception as e:
            logger.error(f"Critical error in normalize_ocr_items: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def update_inventory(self, updates: List[Dict], operation: str = "add") -> Dict[str, Any]:
        """Update inventory with add or deduct operations"""

        if not updates or not isinstance(updates, list):
            return {
                "success": False,
                "error": "Invalid updates input - must be non-empty list"
            }
        
        if operation not in ["add", "deduct"]:
            return {
                "success": False,
                "error": "Operation must be 'add' or 'deduct'"
            }

        results = []
        failed_updates = []
        
        try:
            for i, update in enumerate(updates):
                try:
                    # Validate input
                    if not isinstance(update, dict):
                        failed_updates.append({"index": i, "error": "Update must be a dictionary"})
                        continue

                    item_id = update.get("item_id")
                    quantity = update.get("quantity_grams", 0)

                    if not item_id:
                        failed_updates.append({"index": i, "error": "Missing item_id"})
                        continue

                    if not isinstance(quantity, (int, float)) or quantity <= 0:
                        failed_updates.append({"index": i, "error": "Invalid quantity"})
                        continue

                    # Verify item exists in DB
                    item = self.db.query(Item).filter(Item.id == item_id).first()
                    if not item:
                        failed_updates.append({"index": i, "error": f"Item {item_id} not found"})
                        continue

                    # Perform operation
                    if operation == "add":
                        result = self.inventory_service.add_item(
                            user_id=self.user_id,
                            item_id=item_id,
                            quantity_grams=quantity,
                            expiry_date=update.get("expiry_date"),
                            source="tracking",
                        )
                    else:  # deduct
                        result = self.inventory_service.deduct_item(
                            user_id=self.user_id,
                            item_id=item_id,
                            quantity_grams=quantity,
                        )

                    # Collect results
                    if result.get("success"):
                        results.append({
                            "item_id": item_id,
                            "item_name": item.canonical_name,
                            "operation": operation,
                            "quantity": quantity,
                            "result": result
                        })
                    else:
                        failed_updates.append({"index": i, "error": result.get("error", "Operation failed")})

                except Exception as e:
                    logger.error(f"Error processing update {i}: {str(e)}")
                    failed_updates.append({"index": i, "error": str(e)})

        # Refresh state if successful
            if results:
                try:
                    await websocket_manager.broadcast_to_user(
                        user_id=self.user_id,
                        message={
                            "event_type": "inventory_updated",
                            "data": {
                                "items_changed": [
                                    {
                                        "item_name": item["item_name"],
                                        "old_quantity": item.get("old_quantity", 0),
                                        "new_quantity": item.get("new_quantity", 0),
                                        "operation": item.get("operation", "update")
                                    }
                                    for item in results.get("updated_items", [])
                                ],
                                "successful_updates": results["successful_updates"],
                                "failed_updates": results["failed_updates"],
                                "low_stock_alerts": self._check_low_stock(),
                                "expiring_soon": self._check_expiring_items_quick()
                            },
                            "metadata": {
                                "source": "tracking_agent",
                                "priority": "normal"
                            }
                        }
                    )
                    logger.info(f"Inventory update WebSocket broadcast sent (user {self.user_id})")
                except Exception as e:
                    logger.error(f"Failed to broadcast inventory update: {str(e)}")
                

                self._refresh_inventory_state()
                
                # Log intelligent event
                self._log_event(TrackingEventType.INVENTORY_UPDATED, {
                    "operation": operation,
                    "items_updated": len(results),
                    "success_rate": len(results) / len(updates) * 100
                })

            return {
                "success": len(results) > 0,
                "operation": operation,
                "items_updated": len(results),
                "items_failed": len(failed_updates),
                "results": results,
                "failures": failed_updates,
                "recommendations": self._generate_inventory_recommendations(results, failed_updates),
                "insights": self._generate_inventory_insights(results)
            }

        except Exception as e:
            logger.error(f"Critical error in update_inventory: {str(e)}")
            return {"success": False, "error": f"Inventory update failed: {str(e)}"}
    
    async def log_meal_consumption(self, meal_log_id: int, portion_multiplier: float = 1.0) -> Dict[str, Any]:
        """Tool 4: CHANGED - Delegates to consumption service"""
        try:
            if not isinstance(meal_log_id, int) or meal_log_id <= 0:
                return {"success": False, "error": "Invalid meal_log_id"}
        
            if not isinstance(portion_multiplier, (int, float)) or portion_multiplier <= 0 or portion_multiplier > 5:
                return {"success": False, "error": "Portion multiplier must be between 0 and 5"}
            
            # Delegate to consumption service
            meal_data = {
                "meal_log_id": meal_log_id,
                "portion_multiplier": portion_multiplier,
                "timestamp": datetime.utcnow()
            }
            
            result = self.consumption_service.log_meal_consumption(
                user_id=self.user_id,
                meal_data=meal_data
            )
            
            if result.get("status") == "success":
                # Update agent state
                self._update_consumption_state(result)
                
                # Generate intelligent insights
                insights = self._generate_meal_insights(result)
                
                # Log tracking event
                self._log_event(TrackingEventType.MEAL_LOGGED, {
                    "meal_type": result["logged_meal"]["meal_type"],
                    "recipe": result["logged_meal"]["recipe"],
                    "portion": portion_multiplier
                })

                # FIX: CHECK FOR ACHIEVEMENTS AND SEND NOTIFICATIONS
                achievements = self._check_meal_achievements(result)

                print("achievements", achievements)
                for achievement in achievements:
                    try:
                        await self.notification_service.send_achievement(
                            user_id=self.user_id,
                            achievement_type=achievement["type"],
                            message=achievement["message"],
                            priority=NotificationPriority.NORMAL
                        )
                        logger.info(f"Achievement notification sent: {achievement['message']}")
                    except Exception as e:
                        logger.error(f"Failed to send achievement notification: {str(e)}")
                    
                    try:
                        # Existing notification code
                        await self.notification_service.send_achievement(...)
                        
                        # NEW: WebSocket broadcast for achievement
                        await websocket_manager.broadcast_to_user(
                            user_id=self.user_id,
                            message={
                                "event_type": "achievement",
                                "data": {
                                    "type": achievement["type"],
                                    "title": achievement.get("title", "Achievement Unlocked!"),
                                    "message": achievement["message"],
                                    "icon": achievement.get("icon", "🎉"),
                                    "points": achievement.get("points", 0)
                                },
                                "metadata": {
                                    "source": "tracking_agent",
                                    "priority": "high"
                                }
                            }
                        )
                        logger.info(f"Achievement WebSocket broadcast sent (user {self.user_id})")
                    except Exception as e:
                        logger.error(f"Failed to broadcast achievement: {str(e)}")

                # NEW: SEND PROGRESS UPDATE AFTER MEAL LOGGING
                try:
                    # Get today's summary for progress calculation
                    today_summary = self.consumption_service.get_today_summary(self.user_id)
                    
                    if today_summary.get("success"):
                        await self.notification_service.send_progress_update(
                            user_id=self.user_id,
                            compliance_rate=today_summary.get("compliance_rate", 0),
                            calories_consumed=today_summary.get("total_calories", 0),
                            calories_remaining=result.get("remaining_targets", {}).get("calories", 0),
                            priority=NotificationPriority.LOW
                        )
                        logger.info(f"Progress update sent for user {self.user_id}")


                        await websocket_manager.broadcast_to_user(
                            user_id=self.user_id,
                            message={
                                "event_type": "macro_update",
                                "data": {
                                    "current_totals": today_summary.get("total_macros", {}),
                                    "target_totals": today_summary.get("target_macros", {}),
                                    "remaining_totals": today_summary.get("remaining_macros", {}),
                                    "compliance_rate": today_summary.get("compliance_rate", 0),
                                    "calories_consumed": today_summary.get("total_calories", 0),
                                    "calories_remaining": today_summary.get("remaining_calories", 0)
                                },
                                "metadata": {
                                    "source": "tracking_agent",
                                    "priority": "low"
                                }
                            }
                        )
                        logger.info(f"Progress update WebSocket broadcast sent (user {self.user_id})")
                except Exception as e:
                    logger.error(f"Failed to send progress update: {str(e)}")

                
                try:
                    await websocket_manager.broadcast_to_user(
                        user_id=self.user_id,
                        message={
                            "event_type": "meal_logged",
                            "data": {
                                "meal_type": result["logged_meal"]["meal_type"],
                                "recipe_name": result["logged_meal"]["recipe"],
                                "calories_consumed": result["updated_totals"]["calories"],
                                "macros_consumed": result["updated_totals"]["macros"],
                                "portion_multiplier": portion_multiplier,
                                "daily_totals": {
                                    "calories": result["updated_totals"]["calories"],
                                    "protein_g": result["updated_totals"]["macros"]["protein_g"],
                                    "carbs_g": result["updated_totals"]["macros"]["carbs_g"],
                                    "fat_g": result["updated_totals"]["macros"]["fat_g"],
                                },
                                "remaining_targets": result.get("remaining_targets", {}),
                                "deducted_items": result.get("inventory_changes", [])
                            },
                            "metadata": {
                                "source": "tracking_agent",
                                "priority": "normal"
                            }
                        }
                    )
                    logger.info(f"WebSocket broadcast sent for meal_logged (user {self.user_id})")
                except Exception as e:
                    # Don't fail the meal logging if WebSocket broadcast fails
                    logger.error(f"Failed to broadcast meal_logged event: {str(e)}")
                
                return {
                    "success": True,
                    "meal_type": result["logged_meal"]["meal_type"],
                    "recipe": result["logged_meal"]["recipe"],
                    "consumed_at": result["logged_meal"]["consumed_at"],
                    "deducted_items": result.get("inventory_changes", []),
                    "daily_totals": result.get("updated_totals", {}),
                    "insights": insights,
                    "recommendations": self._generate_post_meal_recommendations(result)
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to log meal")
                }
                
        except Exception as e:
            logger.error(f"Error in log_meal_consumption: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def track_skipped_meals(self, meal_log_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """Tool 5: CHANGED - Delegates to consumption service"""
        try:
            if not isinstance(meal_log_id, int) or meal_log_id <= 0:
                return {"success": False, "error": "Invalid meal_log_id"}
            
            if reason and len(reason) > 255:
                return {"success": False, "error": "Skip reason too long (max 255 characters)"}
            
            # Delegate to consumption service
            meal_info = {
                "meal_log_id": meal_log_id,
                "reason": reason
            }
            
            result = self.consumption_service.handle_skip_meal(
                user_id=self.user_id,
                meal_info=meal_info
            )
            
            if result.get("success"):
                # Update agent state
                self.state.daily_consumption["meals_skipped"] += 1
                
                # Generate intelligent skip analysis
                skip_insights = self._generate_skip_insights(result)
                
                # Log tracking event
                self._log_event(TrackingEventType.MEAL_SKIPPED, {
                    "meal_type": result["meal_type"],
                    "recipe": result["recipe"],
                    "reason": reason
                })
                
                return {
                    "success": True,
                    "meal_log_id": result["meal_log_id"],
                    "meal_type": result["meal_type"],
                    "recipe": result["recipe"],
                    "reason": reason,
                    "pattern_analysis": result.get("skip_analysis", {}),
                    "adherence_impact": result.get("adherence_impact", {}),
                    "recommendation": result.get("recommendation", ""),
                    "insights": skip_insights
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Failed to skip meal")
                }
                
        except Exception as e:
            logger.error(f"Error in track_skipped_meals: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def check_expiring_items(self) -> Dict[str, Any]:
        """Check for items nearing expiry with comprehensive validation"""
        try:
            expiry_threshold = datetime.utcnow() + timedelta(days=3)
            
            # Optimized query with joins
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == self.user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.expiry_date <= expiry_threshold,
                    UserInventory.expiry_date.isnot(None)
                )
            ).all()
            
            expiring_items = []
            
            for inv_item in inventory_items:
                try:
                    if not inv_item.item:
                        logger.warning(f"Inventory item {inv_item.id} missing item reference")
                        continue
                    
                    if not inv_item.expiry_date:
                        continue
                    
                    days_until_expiry = (inv_item.expiry_date - datetime.utcnow()).days
                    
                    # Validate days calculation
                    if days_until_expiry < -7:  # Skip items expired more than a week ago
                        continue
                    
                    expiring_items.append({
                        "item_id": inv_item.item.id,
                        "item": inv_item.item.canonical_name,
                        "quantity": float(inv_item.quantity_grams),
                        "expiry_date": inv_item.expiry_date.isoformat(),
                        "days_until_expiry": days_until_expiry,
                        "priority": "urgent" if days_until_expiry <= 1 else "high" if days_until_expiry <= 2 else "medium",
                        "category": inv_item.item.category or "other"
                    })
                    
                except Exception as e:
                    logger.warning(f"Error processing inventory item {inv_item.id}: {str(e)}")
                    continue
            
            # Sort by urgency (expired first, then by days)
            expiring_items.sort(key=lambda x: (x["days_until_expiry"], x["item"]))

            print("expiring items", expiring_items)

            # FIX: SEND NOTIFICATION FOR URGENT EXPIRING ITEMS
            urgent_items = [item for item in expiring_items if item["priority"] == "urgent"]
            if urgent_items:
                try:
                    await self.notification_service.send_inventory_alert(
                        user_id=self.user_id,
                        alert_type="expiring",
                        items=[item["item"] for item in urgent_items],
                        priority=NotificationPriority.HIGH
                    )
                    logger.info(f"Expiry alert sent for {len(urgent_items)} urgent items")
                except Exception as e:
                    logger.error(f"Failed to send expiry notification: {str(e)}")
            
            # Update alerts in state
            new_alerts = []
            for item in expiring_items:
                alert = {
                    "type": TrackingEventType.EXPIRY_ALERT,
                    "item": item["item"],
                    "expiry_date": item["expiry_date"],
                    "priority": item["priority"],
                    "days_until_expiry": item["days_until_expiry"],
                    "message": f"{item['item']} expires in {item['days_until_expiry']} days" if item['days_until_expiry'] > 0 else f"{item['item']} expired {abs(item['days_until_expiry'])} days ago"
                }
                new_alerts.append(alert)
            
            # Update state alerts (replace expiry alerts)
            self.state.alerts = [alert for alert in self.state.alerts if alert.get("type") != TrackingEventType.EXPIRY_ALERT]
            self.state.alerts.extend(new_alerts)
            
            return {
                "success": True,
                "expiring_count": len(expiring_items),
                "expiring_items": expiring_items,
                "recommendations": self._generate_expiry_recommendations(expiring_items),
                "recipe_suggestions": self._suggest_recipes_for_expiring_items(expiring_items),
                "summary": {
                    "urgent": len([i for i in expiring_items if i["priority"] == "urgent"]),
                    "high": len([i for i in expiring_items if i["priority"] == "high"]),
                    "medium": len([i for i in expiring_items if i["priority"] == "medium"])
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking expiring items: {str(e)}")
            return {"success": False, "error": f"Failed to check expiring items: {str(e)}"}
    
    async def calculate_inventory_status(self) -> Dict[str, Any]:
        """Calculate comprehensive inventory status with optimization"""
        try:
            # Get user's consumption patterns (last 14 days for better average)
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)
            
            recent_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= two_weeks_ago,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()
            
            # Calculate required items for next 7 days based on consumption
            required_items = {}
            consumption_frequency = {}
            
            for log in recent_logs:
                try:
                    if not log.recipe:
                        continue
                    
                    # Get recipe ingredients with optimized query
                    ingredients = self.db.query(RecipeIngredient).options(
                        joinedload(RecipeIngredient.item)
                    ).filter(
                        RecipeIngredient.recipe_id == log.recipe_id
                    ).all()
                    
                    portion_multiplier = log.portion_multiplier or 1.0
                    
                    for ingredient in ingredients:
                        if not ingredient.item:
                            continue
                        
                        item_id = ingredient.item_id
                        quantity = ingredient.quantity_grams * portion_multiplier
                        
                        required_items[item_id] = required_items.get(item_id, 0) + quantity
                        consumption_frequency[item_id] = consumption_frequency.get(item_id, 0) + 1
                        
                except Exception as e:
                    logger.warning(f"Error processing meal log {log.id} for inventory status: {str(e)}")
                    continue
            
            # Calculate weekly requirement with buffer
            days_of_data = min(14, len(set(log.consumed_datetime.date() for log in recent_logs if log.consumed_datetime)))
            if days_of_data == 0:
                days_of_data = 1  # Prevent division by zero
            
            weekly_multiplier = 7 / days_of_data
            
            for item_id in required_items:
                required_items[item_id] = required_items[item_id] * weekly_multiplier * 1.2  # 20% buffer
            
            # Get current inventory with optimization
            current_inventory = {}
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == self.user_id,
                    UserInventory.quantity_grams > 0
                )
            ).all()
            
            for inv_item in inventory_items:
                if inv_item.item:
                    current_inventory[inv_item.item_id] = inv_item.quantity_grams
            
            # Calculate status
            inventory_status = {
                "overall_percentage": 0,
                "category_breakdown": {},
                "critical_items": [],
                "well_stocked": [],
                "recommendations": [],
                "total_items_tracked": len(required_items),
                "items_in_stock": len(current_inventory)
            }
            
            if not required_items:
                inventory_status["recommendations"].append("No consumption data available for analysis")
                return {"success": True, **inventory_status}
            
            total_score = 0
            item_count = 0
            category_stats = {}
            
            for item_id, required_qty in required_items.items():
                try:
                    item = self.db.query(Item).filter(Item.id == item_id).first()
                    if not item:
                        continue
                    
                    current_qty = current_inventory.get(item_id, 0)
                    percentage = min((current_qty / required_qty) * 100, 100) if required_qty > 0 else 100
                    
                    item_info = {
                        "id": item_id,
                        "name": item.canonical_name,
                        "category": item.category or "other",
                        "required_weekly": round(required_qty, 1),
                        "available": round(current_qty, 1),
                        "percentage": round(percentage, 1),
                        "usage_frequency": consumption_frequency.get(item_id, 0),
                        "days_supply": round((current_qty / (required_qty / 7)), 1) if required_qty > 0 else 999
                    }
                    
                    # Categorize items
                    if percentage < 20:
                        inventory_status["critical_items"].append(item_info)
                    elif percentage >= 80:
                        inventory_status["well_stocked"].append(item_info)
                    
                    # Category breakdown
                    category = item.category or "other"
                    if category not in category_stats:
                        category_stats[category] = {"scores": [], "items": 0, "critical": 0}
                    
                    category_stats[category]["scores"].append(percentage)
                    category_stats[category]["items"] += 1
                    if percentage < 20:
                        category_stats[category]["critical"] += 1
                    
                    total_score += percentage
                    item_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing item {item_id} for status calculation: {str(e)}")
                    continue
            
            # Calculate overall percentage
            if item_count > 0:
                inventory_status["overall_percentage"] = round(total_score / item_count, 1)
            
            # Calculate category averages
            for category, stats in category_stats.items():
                if stats["scores"]:
                    inventory_status["category_breakdown"][category] = {
                        "average_percentage": round(sum(stats["scores"]) / len(stats["scores"]), 1),
                        "total_items": stats["items"],
                        "critical_items": stats["critical"],
                        "status": "critical" if stats["critical"] > stats["items"] * 0.5 else "low" if sum(stats["scores"]) / len(stats["scores"]) < 50 else "good"
                    }

            # FIX: SEND NOTIFICATION FOR CRITICAL ITEMS
            critical_item_names = [item["name"] for item in inventory_status["critical_items"]]
            if critical_item_names:
                try:
                    await self.notification_service.send_inventory_alert(
                        user_id=self.user_id,
                        alert_type="low_stock",
                        items=critical_item_names,
                        priority=NotificationPriority.HIGH
                    )
                    logger.info(f"Low stock alert sent for {len(critical_item_names)} critical items")
                except Exception as e:
                    logger.error(f"Failed to send low stock notification: {str(e)}")
            
            # Generate recommendations
            overall_pct = inventory_status["overall_percentage"]
            if overall_pct < 30:
                inventory_status["recommendations"].append("Critical: Immediate grocery shopping required")
                inventory_status["recommendations"].append("Focus on protein and staple ingredients first")
            elif overall_pct < 50:
                inventory_status["recommendations"].append("Low inventory: Plan grocery shopping within 2 days")
            elif overall_pct < 70:
                inventory_status["recommendations"].append("Moderate inventory: Consider restocking staples")
            else:
                inventory_status["recommendations"].append("Good inventory levels maintained")
            
            # Add category-specific recommendations
            for category, data in inventory_status["category_breakdown"].items():
                if data["critical_items"] > 0:
                    inventory_status["recommendations"].append(f"Urgent: Restock {category} items ({data['critical_items']} critical)")
            
            return {"success": True, **inventory_status}
            
        except Exception as e:
            logger.error(f"Error calculating inventory status: {str(e)}")
            return {"success": False, "error": f"Failed to calculate inventory status: {str(e)}"}
    
    def generate_restock_list(self) -> Dict[str, Any]:
        """Generate intelligent restock list with comprehensive analysis"""
        try:
            # Get consumption data from last 14 days
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)
            
            recent_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= two_weeks_ago,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()
            
            # Calculate item usage patterns
            item_usage = {}
            recipe_count = {}
            
            for log in recent_logs:
                if not log.recipe:
                    continue
                
                recipe_count[log.recipe_id] = recipe_count.get(log.recipe_id, 0) + 1
                
                try:
                    ingredients = self.db.query(RecipeIngredient).options(
                        joinedload(RecipeIngredient.item)
                    ).filter(
                        RecipeIngredient.recipe_id == log.recipe_id
                    ).all()
                    
                    portion_multiplier = log.portion_multiplier or 1.0
                    
                    for ingredient in ingredients:
                        if not ingredient.item:
                            continue
                        
                        item_id = ingredient.item_id
                        quantity = ingredient.quantity_grams * portion_multiplier
                        
                        if item_id not in item_usage:
                            item_usage[item_id] = {
                                "total_used": 0,
                                "usage_count": 0,
                                "recipes": set(),
                                "avg_per_use": 0
                            }
                        
                        item_usage[item_id]["total_used"] += quantity
                        item_usage[item_id]["usage_count"] += 1
                        item_usage[item_id]["recipes"].add(log.recipe_id)
                        
                except Exception as e:
                    logger.warning(f"Error processing recipe ingredients for restock: {str(e)}")
                    continue
            
            # Calculate averages
            for item_id, usage_data in item_usage.items():
                if usage_data["usage_count"] > 0:
                    usage_data["avg_per_use"] = usage_data["total_used"] / usage_data["usage_count"]
            
            # Get current inventory
            current_inventory = {}
            inventory_items = self.db.query(UserInventory).options(
                joinedload(UserInventory.item)
            ).filter(
                and_(
                    UserInventory.user_id == self.user_id,
                    UserInventory.quantity_grams > 0
                )
            ).all()
            
            for inv_item in inventory_items:
                if inv_item.item:
                    current_inventory[inv_item.item_id] = {
                        "quantity": inv_item.quantity_grams,
                        "expiry": inv_item.expiry_date
                    }
            
            # Generate restock list
            restock_list = {
                "urgent": [],     # < 20% stock or critical usage
                "soon": [],       # < 50% stock
                "optional": [],   # < 70% stock for frequently used items
                "bulk_opportunities": []  # Items good for bulk buying
            }
            
            days_of_data = len(set(log.consumed_datetime.date() for log in recent_logs if log.consumed_datetime))
            if days_of_data == 0:
                return {
                    "success": True,
                    "message": "No consumption data available for restock analysis",
                    "restock_list": restock_list,
                    "total_items": 0
                }
            
            # Calculate weekly requirements
            weekly_multiplier = 7 / days_of_data
            
            for item_id, usage_data in item_usage.items():
                try:
                    item = self.db.query(Item).filter(Item.id == item_id).first()
                    if not item:
                        continue
                    
                    # Calculate weekly requirement
                    weekly_requirement = usage_data["total_used"] * weekly_multiplier * 1.2  # 20% buffer
                    current_stock = current_inventory.get(item_id, {}).get("quantity", 0)
                    
                    # Calculate stock percentage and days supply
                    stock_percentage = (current_stock / weekly_requirement * 100) if weekly_requirement > 0 else 100
                    days_supply = (current_stock / (weekly_requirement / 7)) if weekly_requirement > 0 else 999
                    
                    # Calculate suggested quantity (2 weeks supply minus current stock)
                    suggested_quantity = max(weekly_requirement * 2 - current_stock, 0)
                    
                    restock_info = {
                        "item_id": item_id,
                        "item": item.canonical_name,
                        "category": item.category or "other",
                        "current_stock": round(current_stock, 1),
                        "weekly_requirement": round(weekly_requirement, 1),
                        "suggested_quantity": round(suggested_quantity, 1),
                        "usage_frequency": usage_data["usage_count"],
                        "recipes_used_in": len(usage_data["recipes"]),
                        "stock_percentage": round(stock_percentage, 1),
                        "days_supply": round(days_supply, 1),
                        "avg_per_use": round(usage_data["avg_per_use"], 1)
                    }
                    
                    # Check for expiry urgency
                    inventory_item = current_inventory.get(item_id, {})
                    if inventory_item.get("expiry"):
                        try:
                            expiry_date = inventory_item["expiry"]
                            if isinstance(expiry_date, str):
                                expiry_date = datetime.fromisoformat(expiry_date)
                            days_to_expiry = (expiry_date - datetime.utcnow()).days
                            restock_info["days_to_expiry"] = days_to_expiry
                            
                            if days_to_expiry <= 3:
                                restock_info["expiry_urgency"] = "urgent"
                            elif days_to_expiry <= 7:
                                restock_info["expiry_urgency"] = "soon"
                        except Exception as e:
                            logger.warning(f"Error processing expiry for item {item_id}: {str(e)}")
                    
                    # Categorize based on stock level and usage
                    if stock_percentage < 20 or restock_info.get("expiry_urgency") == "urgent":
                        restock_list["urgent"].append(restock_info)
                    elif stock_percentage < 50 or restock_info.get("expiry_urgency") == "soon":
                        restock_list["soon"].append(restock_info)
                    elif stock_percentage < 70 and usage_data["usage_count"] >= 3:  # Frequently used
                        restock_list["optional"].append(restock_info)
                    
                    # Check for bulk buying opportunities
                    if (usage_data["usage_count"] >= 5 and 
                        len(usage_data["recipes"]) >= 3 and 
                        item.category in ["grains", "protein", "spices"]):
                        restock_list["bulk_opportunities"].append({
                            **restock_info,
                            "bulk_suggestion": f"Buy {round(weekly_requirement * 4, 1)}g (1 month supply)",
                            "bulk_reason": f"Used in {len(usage_data['recipes'])} recipes, {usage_data['usage_count']} times"
                        })
                    
                except Exception as e:
                    logger.warning(f"Error processing item {item_id} for restock list: {str(e)}")
                    continue
            
            # Sort each category by priority
            restock_list["urgent"].sort(key=lambda x: (x["days_supply"], -x["usage_frequency"]))
            restock_list["soon"].sort(key=lambda x: (x["stock_percentage"], -x["usage_frequency"]))
            restock_list["optional"].sort(key=lambda x: (-x["usage_frequency"], x["stock_percentage"]))
            
            # Calculate summary
            total_items = sum(len(restock_list[category]) for category in ["urgent", "soon", "optional"])
            estimated_cost = self._estimate_cost(restock_list)
            shopping_strategy = self._generate_shopping_strategy(restock_list)
            
            return {
                "success": True,
                "total_items": total_items,
                "urgent_count": len(restock_list["urgent"]),
                "soon_count": len(restock_list["soon"]),
                "optional_count": len(restock_list["optional"]),
                "bulk_opportunities": len(restock_list["bulk_opportunities"]),
                "restock_list": restock_list,
                "estimated_cost": estimated_cost,
                "shopping_strategy": shopping_strategy,
                "analysis_period": f"{days_of_data} days of consumption data"
            }
            
        except Exception as e:
            logger.error(f"Error generating restock list: {str(e)}")
            return {"success": False, "error": f"Failed to generate restock list: {str(e)}"}
        
    

    # NEW HELPER METHOD: Check for meal achievements
    def _check_meal_achievements(self, meal_result: Dict) -> List[Dict]:
        """Check for achievements after meal logging"""
        achievements = []
        
        try:
            # Check for streak achievements
            recent_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= datetime.utcnow() - timedelta(days=7),
                    MealLog.consumed_datetime.isnot(None)
                )
            ).count()
            
            # 7-day streak achievement
            if recent_logs >= 21:  # 3 meals per day for 7 days
                streak_days = recent_logs // 3
                if streak_days == 7:
                    achievements.append({
                        "type": "streak",
                        "message": "7-day meal logging streak! You're building lasting habits!"
                    })
                elif streak_days == 14:
                    achievements.append({
                        "type": "streak",
                        "message": "Amazing! 14-day meal streak - you're on fire!"
                    })
                elif streak_days == 30:
                    achievements.append({
                        "type": "streak",
                        "message": "Incredible! 30-day meal streak - habit mastery achieved!"
                    })
            
            # Daily completion achievement
            today_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    func.date(MealLog.consumed_datetime) == datetime.utcnow().date(),
                    MealLog.consumed_datetime.isnot(None)
                )
            ).count()
            
            if today_logs >= 3:
                achievements.append({
                    "type": "daily_completion",
                    "message": "Perfect day! All meals logged - you're crushing your goals!"
                })
            
            # Nutrition target achievement
            daily_totals = meal_result.get("updated_totals", {})
            if daily_totals.get("protein_g", 0) >= 100:  # Example protein target need to change with actual target
                achievements.append({
                    "type": "nutrition_target",
                    "message": "Protein goal achieved! Great job hitting your nutrition targets!"
                })
            
        except Exception as e:
            logger.warning(f"Error checking achievements: {str(e)}")
        
        return achievements
    
    # Helper methods
    def _parse_ocr_text(self, ocr_text: str) -> list:
        """
        Robust OCR text parser for grocery items.
        Combines advanced error handling and multiple pattern matching.
        Returns a list of strings in the format "<quantity><unit> <item_name>".
        """
        if not ocr_text or not isinstance(ocr_text, str):
            return []

        import re
        parsed_items = []

        # Split lines and strip whitespace
        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

        # Comprehensive list of units
        units = [
            'kg', 'g', 'gram', 'grams', 'kilogram', 'kilograms',
            'l', 'ltr', 'litre', 'litres', 'liter', 'liters',
            'ml', 'millilitre', 'millilitres', 'milliliter', 'milliliters',
            'pcs', 'pc', 'piece', 'pieces', 'pack', 'packs', 'packet', 'packets',
            'bunch', 'bunches', 'dozen', 'box', 'boxes', 'tin', 'tins',
            'bottle', 'bottles', 'jar', 'jars', 'bag', 'bags'
        ]

        # Regex pattern for units
        units_pattern = r'\b(?:' + '|'.join(re.escape(unit) for unit in units) + r')\b'

        for line in lines:
            try:
                # Remove leading numbering like '1. ' or '01. '
                line = re.sub(r'^\d+\.?\s*', '', line)
                # Remove trailing prices like '520.00'
                line = re.sub(r'\s+[\d,]+\.?\d{0,2}$', '', line)
                line = line.strip()
                if not line:
                    continue

                # Pattern 1: quantity + unit + item name
                pattern1 = rf'(\d+(?:\.\d+)?)\s*({units_pattern})\s+(.+)'
                match1 = re.search(pattern1, line, re.IGNORECASE)
                if match1:
                    quantity, unit, name = match1.groups()
                    parsed_items.append(f"{quantity}{unit} {name.strip().lower()}")
                    continue

                # Pattern 2: item name + quantity + unit
                pattern2 = rf'(.+?)\s+(\d+(?:\.\d+)?)\s*({units_pattern})'
                match2 = re.search(pattern2, line, re.IGNORECASE)
                if match2:
                    name, quantity, unit = match2.groups()
                    parsed_items.append(f"{quantity}{unit} {name.strip().lower()}")
                    continue

                # Fallback: just item name (no quantity/unit found)
                if len(line) > 2 and not any(char.isdigit() for char in line[-10:]):
                    parsed_items.append(f"1pc {line.lower()}")

            except Exception as e:
                logger.warning(f"Error parsing OCR line '{line}': {str(e)}")
                continue

        return parsed_items

    def _refresh_inventory_state(self):
        """Refresh inventory state after updates"""
        try:
            inventory_result = self.inventory_service.get_user_inventory(self.user_id)
            self.state.current_inventory = inventory_result.get("items", [])
            self.state.last_sync = datetime.utcnow()
        except Exception as e:
            logger.warning(f"State refresh failed: {str(e)}")

    def _update_consumption_state(self, meal_result: Dict):
        """Update consumption state after meal logging"""
        try:
            logged_meal = meal_result.get("logged_meal", {})
            macros = logged_meal.get("macros", {})
            
            self.state.daily_consumption["meals_logged"] += 1
            self.state.daily_consumption["total_calories"] += macros.get("calories", 0)
            
            for macro in ["protein_g", "carbs_g", "fat_g"]:
                self.state.daily_consumption["total_macros"][macro] += macros.get(macro, 0)
                
        except Exception as e:
            logger.warning(f"Consumption state update failed: {str(e)}")
    
    def _generate_meal_insights(self, meal_result: Dict) -> List[str]:
        """Generate intelligent insights after meal logging"""
        insights = []
        
        try:
            logged_meal = meal_result.get("logged_meal", {})
            portion = logged_meal.get("portion_multiplier", 1.0)
            
            if portion > 1.5:
                insights.append("Large portion detected - consider if you're truly satisfied")
            elif portion < 0.75:
                insights.append("Small portion detected - ensure you're meeting nutrition needs")
            
            # Check timing
            hour = datetime.now().hour
            meal_type = logged_meal.get("meal_type", "")
            
            if meal_type == "breakfast" and hour > 10:
                insights.append("Late breakfast - consider eating earlier for better metabolism")
            elif meal_type == "dinner" and hour > 21:
                insights.append("Late dinner - try to eat 3 hours before bedtime")
                
        except Exception as e:
            logger.warning(f"Insight generation failed: {str(e)}")
        
        return insights
    

    def _generate_skip_insights(self, skip_result: Dict) -> List[str]:
        """Generate intelligent insights after meal skipping"""
        insights = []
        
        try:
            skip_analysis = skip_result.get("skip_analysis", {})
            skip_rate = skip_analysis.get("skip_rate", 0)
            
            if skip_rate > 30:
                insights.append("High skip rate for this meal type - consider meal prep or simpler recipes")
            
            reason = skip_result.get("reason", "")
            if "time" in reason.lower():
                insights.append("Time constraints detected - consider quick meal alternatives")
            elif "appetite" in reason.lower():
                insights.append("Appetite issues - ensure proper hydration and previous meal timing")
                
        except Exception as e:
            logger.warning(f"Skip insight generation failed: {str(e)}")
        
        return insights
    


    def _generate_post_meal_recommendations(self, meal_result: Dict) -> List[str]:
        """Generate recommendations after meal logging"""
        recommendations = []
        
        try:
            remaining_targets = meal_result.get("remaining_targets", {})
            remaining_calories = remaining_targets.get("calories", 0)
            
            if remaining_calories > 800:
                recommendations.append("You have significant calories remaining - don't skip your next meal")
            elif remaining_calories < 200:
                recommendations.append("You're close to your calorie target - choose lighter options for remaining meals")
                
        except Exception as e:
            logger.warning(f"Recommendation generation failed: {str(e)}")
        
        return recommendations
    

    def _generate_ocr_recommendations(self, parsed_items: List[str]) -> List[str]:
        """Generate recommendations for OCR processing"""
        recommendations = []
        
        if len(parsed_items) == 0:
            recommendations.append("No items detected - ensure receipt image is clear and well-lit")
        elif len(parsed_items) < 5:
            recommendations.append("Few items detected - manually add any missing items")
        else:
            recommendations.append("Good OCR detection - review items before adding to inventory")
        
        return recommendations
    

    def _generate_normalization_recommendations(self, normalized: List, unmatched: List) -> List[str]:
        """Generate recommendations for item normalization"""
        recommendations = []
        
        if len(unmatched) > 0:
            recommendations.append(f"{len(unmatched)} items couldn't be matched - add them manually")
        
        if len(normalized) > 0:
            recommendations.append(f"{len(normalized)} items successfully matched - verify quantities")
        
        return recommendations
    

    def _generate_inventory_recommendations(self, results: List, failures: List) -> List[str]:
        """Generate recommendations for inventory updates"""
        recommendations = []
        
        if len(failures) > 0:
            recommendations.append("Some items failed to update - check item names and quantities")
        
        if len(results) > 10:
            recommendations.append("Large inventory update - consider using bulk import feature")
        
        return recommendations
    
    def _generate_inventory_insights(self, results: List) -> List[str]:
        """Generate insights from inventory operations"""
        insights = []
        
        if len(results) > 0:
            total_value = sum(r.get("quantity", 0) for r in results)
            insights.append(f"Updated {len(results)} items totaling {total_value:.0f}g")
        
        return insights
    

    def _generate_expiry_recommendations(self, expiring_items: List[Dict]) -> List[str]:
        """Generate recommendations for expiring items"""
        recommendations = []
        
        for item in expiring_items:
            if item["priority"] == "urgent":
                recommendations.append(f"Use {item['item']} today - expires very soon!")
            elif item["days_until_expiry"] <= 2:
                recommendations.append(f"Plan meals with {item['item']} in next 2 days")
        
        if len(expiring_items) > 3:
            recommendations.append("Consider meal prep to use expiring items")
        
        return recommendations
    
    def _suggest_recipes_for_expiring_items(self, expiring_items: List[Dict]) -> List[str]:
        """Suggest recipes that use expiring items"""
        # This would query recipes that use the expiring ingredients
        suggestions = []
        
        for item in expiring_items[:3]:  # Top 3 expiring items
            suggestions.append(f"Find recipes using {item['item']} to avoid waste")
        
        return suggestions

    
    def _estimate_cost(self, restock_list: Dict) -> float:
        """Estimate cost of restock items"""
        # Simplified cost estimation (would integrate with pricing API)
        estimated_cost = 0
        cost_per_kg = {
            "grains": 50,
            "protein": 200,
            "vegetables": 40,
            "fruits": 60,
            "dairy": 80,
            "spices": 500,
            "other": 100
        }
        
        for priority in restock_list:
            for item in restock_list[priority]:
                category = item.get("category", "other")
                qty_kg = item["suggested_quantity"] / 1000
                estimated_cost += qty_kg * cost_per_kg.get(category, 100)
        
        return round(estimated_cost, 2)
    
    def _generate_shopping_strategy(self, restock_list: Dict) -> List[str]:
        """Generate shopping strategy recommendations"""
        strategy = []
        
        if restock_list["urgent"]:
            strategy.append(f"Shop today for {len(restock_list['urgent'])} urgent items")
        
        if restock_list["soon"]:
            strategy.append(f"Plan shopping within 2-3 days for {len(restock_list['soon'])} items")
        
        # Check for bulk buying opportunities
        bulk_items = [item for priority in restock_list 
                     for item in restock_list[priority] 
                     if item.get("usage_frequency", 0) > 5]
        
        if bulk_items:
            strategy.append(f"Consider bulk buying {len(bulk_items)} frequently used items")
        
        return strategy
    
    def _log_event(self, event_type: TrackingEventType, data: Dict) -> None:
        """Log tracking event"""
        try:
            interaction = AgentInteraction(
                user_id=self.user_id,
                agent_type="tracking",
                interaction_type=event_type.value,
                input_text=json.dumps(data),
                response_text=json.dumps({"event": event_type.value, "timestamp": datetime.utcnow().isoformat()}),
                context_data=data,
                execution_time_ms=0
            )
            self.db.add(interaction)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error logging event: {str(e)}")
    
    def get_state(self) -> Dict:
        """Get current tracking state"""
        return self.state.to_dict()
        
    


    async def schedule_meal_reminders(self) -> Dict[str, Any]:
        """NEW: Schedule meal reminders for upcoming meals"""
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import and_, func
            
            # Get today's upcoming meals (not yet consumed)
            now = datetime.utcnow()
            end_of_day = now.replace(hour=23, minute=59, second=59)
            
            upcoming_meals = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.planned_datetime >= now,
                    MealLog.planned_datetime <= end_of_day,
                    MealLog.consumed_datetime.is_(None),
                    MealLog.was_skipped == False
                )
            ).all()
            
            scheduled_count = 0
            
            for meal in upcoming_meals:
                # Calculate reminder time (30 minutes before)
                reminder_time = meal.planned_datetime - timedelta(minutes=30)
                
                # Only schedule if reminder time is in the future
                if reminder_time > now:
                    try:
                        await self.notification_service.send_meal_reminder(
                            user_id=self.user_id,
                            meal_type=meal.meal_type,
                            recipe_name=meal.recipe.title if meal.recipe else "Your meal",
                            time_until=30,
                            priority=NotificationPriority.NORMAL
                        )
                        scheduled_count += 1
                        logger.info(f"Meal reminder scheduled for {meal.meal_type} at {reminder_time}")
                    except Exception as e:
                        logger.error(f"Failed to schedule meal reminder: {str(e)}")
            
            return {
                "success": True,
                "upcoming_meals": len(upcoming_meals),
                "reminders_scheduled": scheduled_count,
                "message": f"Scheduled {scheduled_count} meal reminders for today"
            }
            
        except Exception as e:
            logger.error(f"Error scheduling meal reminders: {str(e)}")
            return {"success": False, "error": str(e)}
        


    
    def _check_low_stock(self) -> List[Dict]:
        """Quick check for low stock items (for WebSocket broadcast)"""
        try:
            inventory = self.state.current_inventory
            low_stock = []
            
            for item in inventory:
                percentage = item.get("percentage_of_optimal", 100)
                if percentage < 30:
                    low_stock.append({
                        "item_name": item["item_name"],
                        "percentage": percentage,
                        "status": "critical" if percentage < 10 else "low"
                    })
            
            return low_stock
        except Exception as e:
            logger.error(f"Error checking low stock: {str(e)}")
            return []


    def _check_expiring_items_quick(self) -> List[Dict]:
        """Quick check for expiring items (for WebSocket broadcast)"""
        try:
            inventory = self.state.current_inventory
            expiring = []
            
            for item in inventory:
                if item.get("days_until_expiry") is not None:
                    days = item["days_until_expiry"]
                    if days <= 3:
                        expiring.append({
                            "item_name": item["item_name"],
                            "days_remaining": days,
                            "priority": "urgent" if days <= 0 else "high"
                        })
            
            return expiring
        except Exception as e:
            logger.error(f"Error checking expiring items: {str(e)}")
            return []
    
    def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Execute tracking task"""
        tool_mapping = {
            "process_receipt": self.process_receipt_ocr,
            "normalizes": self.normalize_ocr_items,
            "update_inventory": self.update_inventory,
            "log_meal": self.log_meal_consumption,
            "skip_meal": self.track_skipped_meals,
            "check_expiry": self.check_expiring_items,
            "inventory_status": self.calculate_inventory_status,
            "restock_list": self.generate_restock_list
        }
        
        if task in tool_mapping:
            return tool_mapping[task](**kwargs)
        else:
            return {"success": False, "error": f"Unknown task: {task}"}