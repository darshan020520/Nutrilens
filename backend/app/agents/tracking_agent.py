# backend/app/agents/tracking_agent.py
"""
Tracking Agent for NutriLens AI
Handles meal logging, inventory tracking, and consumption patterns
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from dataclasses import dataclass, asdict

from langchain.agents import Tool
from langchain.memory import ConversationBufferMemory
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.database import (
    User, UserInventory, MealLog, Recipe, RecipeIngredient,
    Item, ReceiptUpload, AgentInteraction
)
from app.services.inventory_service import InventoryService
from app.services.item_normalizer import ItemNormalizer
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
        return asdict(self)
    
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
        self.inventory_service = InventoryService(db)
        self.normalizer = ItemNormalizer(db)
        self.memory = ConversationBufferMemory()
        self.state = self._initialize_state()
        self.tools = self._create_tools()
        
    def _initialize_state(self) -> TrackingState:
        """Initialize tracking state"""
        # Get today's consumption
        today = datetime.utcnow().date()
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == self.user_id,
                func.date(MealLog.planned_datetime) == today
            )
        ).all()
        
        daily_consumption = {
            "date": today.isoformat(),
            "meals_logged": len([m for m in meal_logs if m.consumed_datetime]),
            "meals_skipped": len([m for m in meal_logs if m.was_skipped]),
            "total_calories": 0,
            "total_macros": {"protein_g": 0, "carbs_g": 0, "fat_g": 0}
        }
        
        # Calculate consumed macros
        for log in meal_logs:
            if log.consumed_datetime and log.recipe:
                macros = log.recipe.macros_per_serving or {}
                multiplier = log.portion_multiplier or 1.0
                daily_consumption["total_calories"] += macros.get("calories", 0) * multiplier
                daily_consumption["total_macros"]["protein_g"] += macros.get("protein_g", 0) * multiplier
                daily_consumption["total_macros"]["carbs_g"] += macros.get("carbs_g", 0) * multiplier
                daily_consumption["total_macros"]["fat_g"] += macros.get("fat_g", 0) * multiplier
        
        # Get current inventory
        inventory_items = self.inventory_service.get_user_inventory(self.user_id)
        
        # Check for alerts
        alerts = []
        for item in inventory_items:
            # Check expiry
            if item.get("expiry_date"):
                expiry = datetime.fromisoformat(item["expiry_date"])
                if expiry <= datetime.utcnow() + timedelta(days=2):
                    alerts.append({
                        "type": TrackingEventType.EXPIRY_ALERT,
                        "item": item["name"],
                        "expiry_date": item["expiry_date"],
                        "message": f"{item['name']} expires on {expiry.date()}"
                    })
            
            # Check low stock
            if item.get("quantity_grams", 0) < 100:  # Less than 100g
                alerts.append({
                    "type": TrackingEventType.LOW_STOCK_ALERT,
                    "item": item["name"],
                    "quantity": item.get("quantity_grams", 0),
                    "message": f"Low stock: {item['name']} ({item.get('quantity_grams', 0)}g remaining)"
                    })
        
        return TrackingState(
            user_id=self.user_id,
            daily_consumption=daily_consumption,
            current_inventory=inventory_items,
            pending_updates=[],
            sync_status={"last_sync": datetime.utcnow(), "status": "synced"},
            last_sync=datetime.utcnow(),
            alerts=alerts,
            consumption_patterns=self._analyze_patterns()
        )
    
    def _analyze_patterns(self) -> Dict[str, Any]:
        """Analyze consumption patterns"""
        # Get last 7 days of meal logs
        week_ago = datetime.utcnow() - timedelta(days=7)
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == self.user_id,
                MealLog.planned_datetime >= week_ago
            )
        ).all()
        
        patterns = {
            "meal_timing": {},
            "skip_frequency": {},
            "portion_adjustments": [],
            "favorite_recipes": {},
            "meal_compliance_rate": 0
        }
        
        if not meal_logs:
            return patterns
        
        # Analyze timing
        for log in meal_logs:
            if log.consumed_datetime:
                hour = log.consumed_datetime.hour
                meal_type = log.meal_type
                if meal_type not in patterns["meal_timing"]:
                    patterns["meal_timing"][meal_type] = []
                patterns["meal_timing"][meal_type].append(hour)
        
        # Calculate average timing
        for meal_type, hours in patterns["meal_timing"].items():
            if hours:
                patterns["meal_timing"][meal_type] = sum(hours) / len(hours)
        
        # Skip frequency by meal type
        for log in meal_logs:
            meal_type = log.meal_type
            if meal_type not in patterns["skip_frequency"]:
                patterns["skip_frequency"][meal_type] = {"total": 0, "skipped": 0}
            patterns["skip_frequency"][meal_type]["total"] += 1
            if log.was_skipped:
                patterns["skip_frequency"][meal_type]["skipped"] += 1
        
        # Calculate skip rates
        for meal_type, data in patterns["skip_frequency"].items():
            if data["total"] > 0:
                data["rate"] = data["skipped"] / data["total"]
        
        # Portion adjustments
        portions = [log.portion_multiplier for log in meal_logs 
                   if log.portion_multiplier and log.portion_multiplier != 1.0]
        if portions:
            patterns["portion_adjustments"] = {
                "average": sum(portions) / len(portions),
                "trend": "increasing" if portions[-1] > portions[0] else "decreasing"
            }
        
        # Favorite recipes
        recipe_counts = {}
        for log in meal_logs:
            if log.recipe_id and log.consumed_datetime:
                recipe_counts[log.recipe_id] = recipe_counts.get(log.recipe_id, 0) + 1
        
        # Get top 5 recipes
        top_recipes = sorted(recipe_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for recipe_id, count in top_recipes:
            recipe = self.db.query(Recipe).filter(Recipe.id == recipe_id).first()
            if recipe:
                patterns["favorite_recipes"][recipe.title] = count
        
        # Compliance rate
        total_planned = len(meal_logs)
        total_consumed = len([log for log in meal_logs if log.consumed_datetime])
        if total_planned > 0:
            patterns["meal_compliance_rate"] = (total_consumed / total_planned) * 100
        
        return patterns
    
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
            
            # Update receipt with parsed items
            receipt.parsed_items = parsed_items
            receipt.processing_status = "completed"
            receipt.processed_at = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "items_found": len(parsed_items),
                "parsed_items": parsed_items
            }
            
        except Exception as e:
            logger.error(f"Error processing OCR: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def normalize_ocr_items(self, ocr_items: List[Dict]) -> Dict[str, Any]:
        """Normalize OCR items to database items"""
        try:
            normalized_items = []
            unmatched_items = []
            
            for ocr_item in ocr_items:
                result = self.normalizer.normalize_item(
                    ocr_item.get("name", ""),
                    quantity=ocr_item.get("quantity"),
                    unit=ocr_item.get("unit")
                )
                
                if result["match_found"]:
                    normalized_items.append({
                        "original": ocr_item["name"],
                        "matched_item": result["matched_item"],
                        "confidence": result["confidence"],
                        "quantity_grams": result["quantity_grams"]
                    })
                else:
                    unmatched_items.append(ocr_item["name"])
            
            return {
                "success": True,
                "normalized_count": len(normalized_items),
                "unmatched_count": len(unmatched_items),
                "normalized_items": normalized_items,
                "unmatched_items": unmatched_items
            }
            
        except Exception as e:
            logger.error(f"Error normalizing items: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def update_inventory(self, updates: List[Dict], operation: str = "add") -> Dict[str, Any]:
        """Update inventory with add or deduct operations"""
        try:
            results = []
            
            for update in updates:
                item_id = update.get("item_id")
                quantity = update.get("quantity_grams", 0)
                
                if operation == "add":
                    result = self.inventory_service.add_item(
                        user_id=self.user_id,
                        item_id=item_id,
                        quantity_grams=quantity,
                        expiry_date=update.get("expiry_date"),
                        source="tracking"
                    )
                else:  # deduct
                    result = self.inventory_service.deduct_item(
                        user_id=self.user_id,
                        item_id=item_id,
                        quantity_grams=quantity
                    )
                
                results.append(result)
            
            # Update state
            self.state.current_inventory = self.inventory_service.get_user_inventory(self.user_id)
            self.state.last_sync = datetime.utcnow()
            
            return {
                "success": True,
                "operation": operation,
                "items_updated": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error updating inventory: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def log_meal_consumption(self, meal_log_id: int, portion_multiplier: float = 1.0) -> Dict[str, Any]:
        """Log meal consumption and auto-deduct ingredients"""
        try:
            # Get meal log
            meal_log = self.db.query(MealLog).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == self.user_id
                )
            ).first()
            
            if not meal_log:
                return {"success": False, "error": "Meal log not found"}
            
            if meal_log.consumed_datetime:
                return {"success": False, "error": "Meal already logged"}
            
            # Update meal log
            meal_log.consumed_datetime = datetime.utcnow()
            meal_log.portion_multiplier = portion_multiplier
            meal_log.was_skipped = False
            
            # Deduct ingredients from inventory if recipe exists
            deducted_items = []
            if meal_log.recipe:
                ingredients = self.db.query(RecipeIngredient).filter(
                    RecipeIngredient.recipe_id == meal_log.recipe_id
                ).all()
                
                for ingredient in ingredients:
                    quantity_to_deduct = ingredient.quantity_grams * portion_multiplier
                    result = self.inventory_service.deduct_item(
                        user_id=self.user_id,
                        item_id=ingredient.item_id,
                        quantity_grams=quantity_to_deduct
                    )
                    
                    if result["success"]:
                        item = self.db.query(Item).filter(Item.id == ingredient.item_id).first()
                        deducted_items.append({
                            "item": item.canonical_name if item else "Unknown",
                            "quantity": quantity_to_deduct,
                            "remaining": result.get("remaining_quantity", 0)
                        })
            
            self.db.commit()
            
            # Update state
            self.state.daily_consumption["meals_logged"] += 1
            if meal_log.recipe and meal_log.recipe.macros_per_serving:
                macros = meal_log.recipe.macros_per_serving
                self.state.daily_consumption["total_calories"] += macros.get("calories", 0) * portion_multiplier
                self.state.daily_consumption["total_macros"]["protein_g"] += macros.get("protein_g", 0) * portion_multiplier
                self.state.daily_consumption["total_macros"]["carbs_g"] += macros.get("carbs_g", 0) * portion_multiplier
                self.state.daily_consumption["total_macros"]["fat_g"] += macros.get("fat_g", 0) * portion_multiplier
            
            # Log tracking event
            self._log_event(TrackingEventType.MEAL_LOGGED, {
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if meal_log.recipe else "External",
                "portion": portion_multiplier,
                "deducted_items": deducted_items
            })
            
            return {
                "success": True,
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if meal_log.recipe else "External meal",
                "consumed_at": meal_log.consumed_datetime.isoformat(),
                "deducted_items": deducted_items,
                "daily_totals": self.state.daily_consumption
            }
            
        except Exception as e:
            logger.error(f"Error logging meal: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def track_skipped_meals(self, meal_log_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """Track skipped meals"""
        try:
            meal_log = self.db.query(MealLog).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == self.user_id
                )
            ).first()
            
            if not meal_log:
                return {"success": False, "error": "Meal log not found"}
            
            meal_log.was_skipped = True
            meal_log.skip_reason = reason
            meal_log.consumed_datetime = None
            self.db.commit()
            
            # Update state
            self.state.daily_consumption["meals_skipped"] += 1
            
            # Log event
            self._log_event(TrackingEventType.MEAL_SKIPPED, {
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if meal_log.recipe else "Unknown",
                "reason": reason
            })
            
            return {
                "success": True,
                "meal_type": meal_log.meal_type,
                "reason": reason,
                "pattern_analysis": self._analyze_skip_pattern(meal_log.meal_type)
            }
            
        except Exception as e:
            logger.error(f"Error tracking skipped meal: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def check_expiring_items(self) -> Dict[str, Any]:
        """Check for items nearing expiry"""
        try:
            expiry_threshold = datetime.utcnow() + timedelta(days=3)
            
            inventory_items = self.db.query(UserInventory).filter(
                and_(
                    UserInventory.user_id == self.user_id,
                    UserInventory.quantity_grams > 0,
                    UserInventory.expiry_date <= expiry_threshold
                )
            ).all()
            
            expiring_items = []
            for inv_item in inventory_items:
                item = self.db.query(Item).filter(Item.id == inv_item.item_id).first()
                if item:
                    days_until_expiry = (inv_item.expiry_date - datetime.utcnow()).days
                    expiring_items.append({
                        "item": item.canonical_name,
                        "quantity": inv_item.quantity_grams,
                        "expiry_date": inv_item.expiry_date.isoformat(),
                        "days_until_expiry": days_until_expiry,
                        "priority": "high" if days_until_expiry <= 1 else "medium"
                    })
            
            # Update alerts in state
            for item in expiring_items:
                alert = {
                    "type": TrackingEventType.EXPIRY_ALERT,
                    "item": item["item"],
                    "expiry_date": item["expiry_date"],
                    "priority": item["priority"],
                    "message": f"{item['item']} expires in {item['days_until_expiry']} days"
                }
                if alert not in self.state.alerts:
                    self.state.alerts.append(alert)
            
            return {
                "success": True,
                "expiring_count": len(expiring_items),
                "expiring_items": expiring_items,
                "recommendations": self._generate_expiry_recommendations(expiring_items)
            }
            
        except Exception as e:
            logger.error(f"Error checking expiring items: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def calculate_inventory_status(self) -> Dict[str, Any]:
        """Calculate overall inventory status percentage"""
        try:
            # Get user's typical weekly consumption
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= week_ago,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()
            
            # Calculate required items for next 7 days
            required_items = {}
            for log in recent_logs:
                ingredients = self.db.query(RecipeIngredient).filter(
                    RecipeIngredient.recipe_id == log.recipe_id
                ).all()
                
                for ingredient in ingredients:
                    item_id = ingredient.item_id
                    required_items[item_id] = required_items.get(item_id, 0) + ingredient.quantity_grams
            
            # Calculate average weekly requirement
            if required_items:
                for item_id in required_items:
                    required_items[item_id] = required_items[item_id] * 1.2  # 20% buffer
            
            # Compare with current inventory
            inventory_status = {
                "overall_percentage": 0,
                "category_breakdown": {},
                "critical_items": [],
                "well_stocked": [],
                "recommendations": []
            }
            
            total_score = 0
            item_count = 0
            
            for item_id, required_qty in required_items.items():
                inv_item = self.db.query(UserInventory).filter(
                    and_(
                        UserInventory.user_id == self.user_id,
                        UserInventory.item_id == item_id
                    )
                ).first()
                
                current_qty = inv_item.quantity_grams if inv_item else 0
                percentage = min((current_qty / required_qty) * 100, 100) if required_qty > 0 else 0
                
                item = self.db.query(Item).filter(Item.id == item_id).first()
                if item:
                    item_info = {
                        "name": item.canonical_name,
                        "category": item.category,
                        "required": required_qty,
                        "available": current_qty,
                        "percentage": percentage
                    }
                    
                    if percentage < 20:
                        inventory_status["critical_items"].append(item_info)
                    elif percentage >= 80:
                        inventory_status["well_stocked"].append(item_info)
                    
                    # Category breakdown
                    category = item.category or "other"
                    if category not in inventory_status["category_breakdown"]:
                        inventory_status["category_breakdown"][category] = {
                            "total_items": 0,
                            "average_percentage": 0,
                            "scores": []
                        }
                    
                    inventory_status["category_breakdown"][category]["total_items"] += 1
                    inventory_status["category_breakdown"][category]["scores"].append(percentage)
                    
                    total_score += percentage
                    item_count += 1
            
            # Calculate overall percentage
            if item_count > 0:
                inventory_status["overall_percentage"] = total_score / item_count
            
            # Calculate category averages
            for category, data in inventory_status["category_breakdown"].items():
                if data["scores"]:
                    data["average_percentage"] = sum(data["scores"]) / len(data["scores"])
                del data["scores"]  # Remove raw scores from response
            
            # Generate recommendations
            if inventory_status["overall_percentage"] < 30:
                inventory_status["recommendations"].append("Critical: Immediate grocery shopping required")
            elif inventory_status["overall_percentage"] < 50:
                inventory_status["recommendations"].append("Low inventory: Plan grocery shopping within 2 days")
            elif inventory_status["overall_percentage"] < 70:
                inventory_status["recommendations"].append("Moderate inventory: Consider restocking staples")
            else:
                inventory_status["recommendations"].append("Good inventory levels maintained")
            
            return {
                "success": True,
                **inventory_status
            }
            
        except Exception as e:
            logger.error(f"Error calculating inventory status: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def generate_restock_list(self) -> Dict[str, Any]:
        """Generate list of items needing restock"""
        try:
            # Get frequently used items from last 2 weeks
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)
            recent_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == self.user_id,
                    MealLog.consumed_datetime >= two_weeks_ago,
                    MealLog.recipe_id.isnot(None)
                )
            ).all()
            
            # Calculate item usage frequency and quantities
            item_usage = {}
            for log in recent_logs:
                ingredients = self.db.query(RecipeIngredient).filter(
                    RecipeIngredient.recipe_id == log.recipe_id
                ).all()
                
                for ingredient in ingredients:
                    if ingredient.item_id not in item_usage:
                        item_usage[ingredient.item_id] = {
                            "total_used": 0,
                            "usage_count": 0,
                            "recipes": set()
                        }
                    
                    item_usage[ingredient.item_id]["total_used"] += ingredient.quantity_grams
                    item_usage[ingredient.item_id]["usage_count"] += 1
                    item_usage[ingredient.item_id]["recipes"].add(log.recipe_id)
            
            # Generate restock list
            restock_list = {
                "urgent": [],  # < 20% stock
                "soon": [],    # < 50% stock
                "optional": [] # < 70% stock
            }
            
            for item_id, usage_data in item_usage.items():
                # Calculate weekly requirement
                weekly_requirement = (usage_data["total_used"] / 2) * 1.2  # 20% buffer
                
                # Check current inventory
                inv_item = self.db.query(UserInventory).filter(
                    and_(
                        UserInventory.user_id == self.user_id,
                        UserInventory.item_id == item_id
                    )
                ).first()
                
                current_qty = inv_item.quantity_grams if inv_item else 0
                stock_percentage = (current_qty / weekly_requirement * 100) if weekly_requirement > 0 else 0
                
                item = self.db.query(Item).filter(Item.id == item_id).first()
                if item:
                    restock_info = {
                        "item": item.canonical_name,
                        "category": item.category,
                        "current_stock": current_qty,
                        "weekly_requirement": round(weekly_requirement, 0),
                        "suggested_quantity": round(max(weekly_requirement * 2 - current_qty, 0), 0),
                        "usage_frequency": usage_data["usage_count"],
                        "stock_percentage": round(stock_percentage, 1)
                    }
                    
                    if stock_percentage < 20:
                        restock_list["urgent"].append(restock_info)
                    elif stock_percentage < 50:
                        restock_list["soon"].append(restock_info)
                    elif stock_percentage < 70 and item.is_staple:
                        restock_list["optional"].append(restock_info)
            
            # Sort each category by stock percentage
            for category in restock_list:
                restock_list[category].sort(key=lambda x: x["stock_percentage"])
            
            # Generate shopping list summary
            total_items = (len(restock_list["urgent"]) + 
                          len(restock_list["soon"]) + 
                          len(restock_list["optional"]))
            
            return {
                "success": True,
                "total_items": total_items,
                "urgent_count": len(restock_list["urgent"]),
                "restock_list": restock_list,
                "estimated_cost": self._estimate_cost(restock_list),
                "shopping_strategy": self._generate_shopping_strategy(restock_list)
            }
            
        except Exception as e:
            logger.error(f"Error generating restock list: {str(e)}")
            return {"success": False, "error": str(e)}
    
    # Helper methods
    def _parse_ocr_text(self, ocr_text: str) -> List[Dict]:
        """Parse OCR text to extract items"""
        import re
        
        parsed_items = []
        lines = ocr_text.split('\n')
        
        # Common patterns for grocery items
        patterns = [
            r'(\d+\.?\d*)\s*(kg|g|l|ml|pcs?|pack|bunch)\s+(.+)',
            r'(.+?)\s+(\d+\.?\d*)\s*(kg|g|l|ml|pcs?|pack|bunch)',
            r'(.+?)\s+-\s+(\d+\.?\d*)\s*(kg|g|l|ml)',
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        if groups[0].replace('.', '').isdigit():
                            # Pattern: quantity unit item
                            parsed_items.append({
                                "name": groups[2].strip(),
                                "quantity": float(groups[0]),
                                "unit": groups[1].lower()
                            })
                        else:
                            # Pattern: item quantity unit
                            parsed_items.append({
                                "name": groups[0].strip(),
                                "quantity": float(groups[1]),
                                "unit": groups[2].lower()
                            })
                    break
        
        return parsed_items
    
    def _analyze_skip_pattern(self, meal_type: str) -> Dict[str, Any]:
        """Analyze skip patterns for a meal type"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == self.user_id,
                MealLog.meal_type == meal_type,
                MealLog.planned_datetime >= week_ago
            )
        ).all()
        
        if not meal_logs:
            return {"pattern": "No data available"}
        
        total = len(meal_logs)
        skipped = len([log for log in meal_logs if log.was_skipped])
        skip_rate = (skipped / total) * 100 if total > 0 else 0
        
        # Get skip reasons
        reasons = {}
        for log in meal_logs:
            if log.was_skipped and log.skip_reason:
                reasons[log.skip_reason] = reasons.get(log.skip_reason, 0) + 1
        
        return {
            "meal_type": meal_type,
            "skip_rate": round(skip_rate, 1),
            "total_planned": total,
            "total_skipped": skipped,
            "common_reasons": reasons,
            "recommendation": self._get_skip_recommendation(skip_rate, meal_type)
        }
    
    def _get_skip_recommendation(self, skip_rate: float, meal_type: str) -> str:
        """Get recommendation based on skip rate"""
        if skip_rate > 50:
            return f"High skip rate for {meal_type}. Consider adjusting meal timing or recipes."
        elif skip_rate > 30:
            return f"Moderate skip rate for {meal_type}. Review if portions are too large."
        else:
            return f"Good adherence for {meal_type}. Keep it up!"
    
    def _generate_expiry_recommendations(self, expiring_items: List[Dict]) -> List[str]:
        """Generate recommendations for expiring items"""
        recommendations = []
        
        for item in expiring_items:
            if item["priority"] == "high":
                recommendations.append(f"Use {item['item']} today - expires tomorrow!")
            elif item["days_until_expiry"] <= 2:
                recommendations.append(f"Plan meals with {item['item']} in next 2 days")
        
        if len(expiring_items) > 3:
            recommendations.append("Consider meal prep to use expiring items")
        
        return recommendations
    
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
    
    def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Execute tracking task"""
        tool_mapping = {
            "process_receipt": self.process_receipt_ocr,
            "normalize_items": self.normalize_ocr_items,
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