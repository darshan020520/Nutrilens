# backend/app/schemas/meal_plan.py

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    MEAL_4 = "meal_4"
    MEAL_5 = "meal_5"

class MacroNutrients(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: Optional[float] = 0

class RecipeBase(BaseModel):
    id: int
    title: str
    description: Optional[str]
    suitable_meal_times: List[str]
    macros_per_serving: MacroNutrients
    prep_time_min: int
    cook_time_min: int
    servings: int = 1
    goals: Optional[List[str]] = []
    dietary_tags: Optional[List[str]] = []
    
    class Config:
        orm_mode = True

class MealPlanCreate(BaseModel):
    week_start_date: datetime
    plan_data: Dict[str, Any]  # Contains week_plan with day_0, day_1, etc.
    grocery_list: Optional[Dict[str, Any]] = {}
    total_calories: float
    avg_macros: Dict[str, float]
    optimization_method: Optional[str] = "linear_programming"
    
    @validator('plan_data')
    def validate_plan_data(cls, v):
        if 'week_plan' not in v:
            raise ValueError("plan_data must contain 'week_plan'")
        return v

class MealPlanUpdate(BaseModel):
    plan_data: Optional[Dict[str, Any]]
    grocery_list: Optional[Dict[str, Any]]
    total_calories: Optional[float]
    avg_macros: Optional[Dict[str, float]]
    is_active: Optional[bool]

class MealPlanResponse(BaseModel):
    id: int
    user_id: int
    week_start_date: datetime
    plan_data: Dict[str, Any]
    grocery_list:  Optional[Dict[str, Any]] = None 
    total_calories: float
    avg_macros: Dict[str, float]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class MealSwapRequest(BaseModel):
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6)")
    meal_type: MealType
    new_recipe_id: int
    reason: Optional[str] = None

class MealLogCreate(BaseModel):
    recipe_id: int
    planned_datetime: Optional[datetime]
    consumed_datetime: Optional[datetime]
    portion_multiplier: float = 1.0
    was_skipped: bool = False
    skip_reason: Optional[str]
    notes: Optional[str]
    skip_inventory_update: bool = False

class MealLogResponse(BaseModel):
    id: int
    user_id: int
    recipe_id: int
    recipe_title: Optional[str]
    planned_datetime: Optional[datetime]
    consumed_datetime: datetime
    portion_multiplier: float
    was_skipped: bool
    skip_reason: Optional[str]
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True

class GeneratePlanRequest(BaseModel):
    start_date: Optional[datetime] = None
    days: int = Field(7, ge=1, le=14)
    preferences: Optional[Dict[str, Any]] = {}
    use_inventory: bool = True
    optimization_goal: Optional[str] = "balanced"

class AlternativesResponse(BaseModel):
    recipe: RecipeBase
    similarity_score: float
    calorie_difference: float
    protein_difference: float
    suitable_for_swap: bool = True

class GroceryItemDetail(BaseModel):
    item_id: int
    item_name: Optional[str]
    quantity_needed: float
    quantity_available: float
    to_buy: float
    unit: Optional[str] = "grams"
    category: Optional[str]

class GroceryListResponse(BaseModel):
    items: Dict[int, Dict[str, float]]
    categorized: Dict[str, List[GroceryItemDetail]]
    total_items: int
    items_to_buy: int
    estimated_cost: Optional[float]

class MealScheduleItem(BaseModel):
    time: str
    meal_type: str
    recipe: str
    prep_time: int
    calories: float

class DaySchedule(BaseModel):
    date: str
    meals: List[MealScheduleItem]

class ShoppingReminder(BaseModel):
    type: str
    message: str
    priority: str
    item_id: Optional[int]
    quantity_remaining: Optional[float]
    suggested_day: Optional[str]

class BulkCookingSuggestion(BaseModel):
    type: str
    action: str
    recipe: Optional[str]
    servings: Optional[int]
    time_saved: Optional[int]
    storage_tip: Optional[str]
    items: Optional[List[str]]