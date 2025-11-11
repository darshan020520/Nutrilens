# backend/app/schemas/tracking.py
"""
Complete Pydantic schemas for Tracking API
Handles meal logging, inventory updates, and consumption analytics
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


# ===== ENUMS =====

class MealType(str, Enum):
    """Meal type enumeration"""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    MEAL_4 = "meal_4"
    MEAL_5 = "meal_5"


class InventoryOperation(str, Enum):
    """Inventory update operation types"""
    ADD = "add"
    DEDUCT = "deduct"
    SET = "set"


# ===== REQUEST SCHEMAS =====

class LogMealRequest(BaseModel):
    """Request schema for logging a meal"""
    meal_log_id: int = Field(..., gt=0, description="ID of the planned meal log")
    portion_multiplier: float = Field(
        1.0, 
        gt=0, 
        le=5.0, 
        description="Multiplier for portion size (0.5 = half, 2.0 = double)"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes about the meal")


class SkipMealRequest(BaseModel):
    """Request schema for skipping a meal"""
    meal_log_id: int = Field(..., gt=0, description="ID of the planned meal log")
    reason: Optional[str] = Field(
        None, 
        max_length=255, 
        description="Reason for skipping (optional)"
    )


class InventoryUpdateItem(BaseModel):
    """Single inventory item update"""
    item_name: str = Field(..., min_length=1, max_length=200, description="Name of the item")
    quantity_grams: float = Field(..., gt=0, description="Quantity in grams")
    operation: InventoryOperation = Field(default=InventoryOperation.ADD)
    expiry_date: Optional[datetime] = Field(None, description="Optional expiry date")
    
    @validator('item_name')
    def validate_item_name(cls, v):
        """Ensure item name is properly formatted"""
        return v.strip().lower()


class BulkInventoryUpdateRequest(BaseModel):
    """Request schema for bulk inventory updates"""
    items: List[InventoryUpdateItem] = Field(
        ..., 
        min_items=1, 
        max_items=100,
        description="List of items to update"
    )


class ManualFoodEntryRequest(BaseModel):
    """Request schema for manual food entry (off-plan)"""
    food_name: str = Field(..., min_length=1, max_length=200)
    quantity: str = Field(..., description="Quantity with unit (e.g., '200g', '1 cup')")
    meal_type: MealType
    consumed_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="When the food was consumed"
    )
    notes: Optional[str] = Field(None, max_length=500)


# ===== RESPONSE SCHEMAS =====

class MacroNutrients(BaseModel):
    """Macro nutrients response"""
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: Optional[float] = 0
    
    class Config:
        from_attributes = True


class InventoryChangeItem(BaseModel):
    """Single inventory change item"""
    item_name: str
    old_quantity: float
    new_quantity: float
    unit: str = "g"


class InsightItem(BaseModel):
    """Single insight item"""
    type: str  # achievement, recommendation, warning, tip
    message: str
    priority: str = "normal"  # low, normal, high, urgent


class RecommendationItem(BaseModel):
    """Single recommendation item"""
    type: str  # recipe, timing, macro_adjustment
    title: str
    description: str
    action_url: Optional[str] = None


class LogMealResponse(BaseModel):
    """Response schema for meal logging"""
    success: bool
    meal_type: str
    recipe_name: str
    consumed_at: datetime
    macros_consumed: MacroNutrients
    portion_multiplier: float
    deducted_items: List[InventoryChangeItem]
    daily_totals: Dict[str, Any]
    remaining_targets: Dict[str, float]
    insights: List[InsightItem]
    recommendations: List[RecommendationItem]


class SkipMealResponse(BaseModel):
    """Response schema for skipping a meal"""
    success: bool
    meal_type: str
    recipe_name: str
    skip_reason: Optional[str]
    adherence_impact: Dict[str, Any]
    updated_adherence_rate: float


class TodaySummaryResponse(BaseModel):
    """Response schema for today's summary"""
    date: str
    meals_planned: int
    meals_consumed: int
    meals_skipped: int
    total_calories: float
    total_macros: MacroNutrients
    target_calories: float
    target_macros: MacroNutrients
    remaining_calories: float
    remaining_macros: MacroNutrients
    compliance_rate: float
    meal_details: List[Dict[str, Any]]


class ConsumptionHistoryResponse(BaseModel):
    """Response schema aligned with frontend expectations"""
    period: Dict[str, Any]          
    statistics: Dict[str, Any]     
    history: List[Dict[str, Any]]  
    trends: Dict[str, Any] = {}    


class ConsumptionPattern(BaseModel):
    """Consumption pattern details"""
    meal_type: str
    average_time: str
    frequency: int
    skip_rate: float


class ConsumptionPatternsResponse(BaseModel):
    """Response schema for consumption patterns"""
    analysis_period_days: int
    meal_timing_patterns: List[ConsumptionPattern]
    skip_frequency: Dict[str, float]
    portion_preferences: Dict[str, float]
    adherence_by_day: Dict[str, float]
    adherence_by_meal: Dict[str, float]
    insights: List[str]
    recommendations: List[str]


class InventoryItemStatus(BaseModel):
    """Single inventory item status"""
    item_id: int
    item_name: str
    category: str
    quantity_grams: float
    percentage_of_optimal: float
    status: str  # optimal, low, critical, overstocked
    expiry_date: Optional[str]
    days_until_expiry: Optional[int]


class InventoryStatusResponse(BaseModel):
    """Response schema for inventory status"""
    total_items: int
    items_by_category: Dict[str, int]
    overall_stock_level: float  # percentage
    low_stock_items: List[InventoryItemStatus]
    critical_items: List[InventoryItemStatus]
    expiring_soon: List[InventoryItemStatus]
    overstocked_items: List[InventoryItemStatus]
    recommendations: List[str]


class ExpiringItemWithRecipes(BaseModel):
    """Expiring item with recipe suggestions"""
    inventory_id: int  # UserInventory primary key for delete/update operations
    item_id: int
    item_name: str
    quantity_grams: float
    expiry_date: str
    days_remaining: int
    priority: str  # urgent, high, medium
    recipe_suggestions: List[Dict[str, Any]]


class ExpiringItemsResponse(BaseModel):
    """Response schema for expiring items"""
    total_expiring: int
    urgent_count: int  # expires today or expired
    high_priority_count: int  # expires in 1-2 days
    medium_priority_count: int  # expires in 3-7 days
    items: List[ExpiringItemWithRecipes]
    action_recommendations: List[str]


class RestockItem(BaseModel):
    """Single restock item"""
    item_name: str
    category: str
    current_quantity: float
    recommended_quantity: float
    priority: str  # urgent, soon, routine
    usage_frequency: int
    days_until_depleted: Optional[int]


class RestockListResponse(BaseModel):
    """Response schema for restock list"""
    total_items: int
    urgent_items: List[RestockItem]
    soon_items: List[RestockItem]
    routine_items: List[RestockItem]
    estimated_total_cost: Optional[float]
    shopping_strategy: List[str]


class BulkInventoryUpdateResponse(BaseModel):
    """Response schema for bulk inventory update"""
    success: bool
    total_items: int
    successful_updates: int
    failed_updates: int
    updated_items: List[InventoryChangeItem]
    failed_items: List[Dict[str, Any]]
    inventory_recommendations: List[str]
    insights: List[str]


class ManualFoodEntryResponse(BaseModel):
    """Response schema for manual food entry"""
    success: bool
    food_name: str
    normalized_name: str
    quantity_parsed: str
    estimated_macros: MacroNutrients
    confidence_score: float
    meal_type: str
    consumed_at: datetime
    updated_daily_totals: Dict[str, Any]
    recommendations: List[str]


# ===== EXTERNAL MEAL LOGGING SCHEMAS =====

class ExternalMealEstimateRequest(BaseModel):
    """Request schema for getting LLM nutrition estimate"""
    dish_name: str = Field(..., min_length=1, max_length=200, description="Name of the dish")
    portion_size: str = Field(..., min_length=1, max_length=100, description="Portion size (e.g., '1 large plate', '300g')")
    restaurant_name: Optional[str] = Field(None, max_length=200, description="Restaurant name for context")
    cuisine_type: Optional[str] = Field(None, max_length=50, description="Cuisine type (e.g., 'Indian', 'Italian')")


class ExternalMealEstimateResponse(BaseModel):
    """Response schema for nutrition estimate"""
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reasoning: str = Field(..., description="Brief explanation of the estimation")
    dish_name: str
    portion_size: str
    estimation_method: str = Field(..., description="'llm' or 'fallback'")


class LogExternalMealRequest(BaseModel):
    """Request schema for logging an external meal"""
    dish_name: str = Field(..., min_length=1, max_length=200)
    portion_size: str = Field(..., min_length=1, max_length=100)
    restaurant_name: Optional[str] = Field(None, max_length=200)
    cuisine_type: Optional[str] = Field(None, max_length=50)

    # Estimated or user-provided macros
    calories: float = Field(..., gt=0, description="Calories (from estimate or user input)")
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    fiber_g: float = Field(0, ge=0)

    # Meal replacement or addition
    meal_log_id_to_replace: Optional[int] = Field(
        None,
        description="If provided, replaces this planned meal. If None, adds as new meal."
    )
    meal_type: Optional[MealType] = Field(
        None,
        description="Required if meal_log_id_to_replace is None (adding new meal)"
    )

    # Additional context
    notes: Optional[str] = Field(None, max_length=500)
    consumed_at: Optional[datetime] = Field(
        None,
        description="When the meal was consumed (defaults to now)"
    )

    @validator('meal_type')
    def validate_meal_type_requirement(cls, v, values):
        """Ensure meal_type is provided when adding new meal"""
        if values.get('meal_log_id_to_replace') is None and v is None:
            raise ValueError("meal_type is required when not replacing an existing meal")
        return v


class RemainingMealOption(BaseModel):
    """Remaining meal that can be replaced"""
    meal_log_id: int
    meal_type: str
    recipe_name: str
    planned_time: str
    planned_calories: float


class LogExternalMealResponse(BaseModel):
    """Response schema for external meal logging"""
    success: bool
    meal_log_id: int
    meal_type: str
    dish_name: str
    restaurant_name: Optional[str]
    consumed_at: datetime
    macros: MacroNutrients

    # Meal replacement info
    replaced_meal: bool = Field(..., description="True if replaced a planned meal")
    original_recipe: Optional[str] = Field(None, description="Original recipe name if replaced")

    # Updated daily summary
    updated_daily_totals: Dict[str, Any]
    remaining_calories: float

    # Optional: remaining meals for today that could be swapped
    remaining_meals_today: Optional[List[RemainingMealOption]] = None

    # Insights and recommendations
    insights: List[str] = []
    recommendations: List[str] = []