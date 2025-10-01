from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class NutritionInfo(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: Optional[float] = 0
    sugar_g: Optional[float] = 0
    sodium_mg: Optional[float] = 0

class InventoryItem(BaseModel):
    item_id: int
    canonical_name: str
    quantity_grams: float = Field(..., gt=0)
    expiry_date: Optional[datetime] = None

class InventoryUpdate(BaseModel):
    item_id: int
    quantity_grams: float
    operation: str = Field(..., pattern=r"^(add|subtract|set)$")

class MealEntry(BaseModel):
    recipe_id: int
    recipe_title: str
    meal_type: str
    servings: float = Field(1.0, gt=0)
    nutrition: NutritionInfo
    ingredients_used: Dict[str, float]
    scheduled_time: datetime

class DayPlan(BaseModel):
    date: str
    meals: List[MealEntry]
    total_nutrition: NutritionInfo
    macro_percentages: Dict[str, float]

class WeekPlan(BaseModel):
    week_start: datetime
    days: List[DayPlan]
    shopping_list: List[Dict[str, float]]
    pantry_usage_percentage: float

class MealLogCreate(BaseModel):
    recipe_id: Optional[int] = None
    meal_type: str
    consumed_datetime: datetime
    portion_multiplier: float = 1.0
    notes: Optional[str] = None
    external_meal: Optional[Dict] = None  # For eating out

class MealPlanResponse(BaseModel):
    id: int
    week_start_date: datetime
    plan_data: Dict
    grocery_list: List[Dict]
    total_calories: float
    avg_macros: Dict[str, float]
    is_active: bool
    
    class Config:
        orm_mode = True

# Add these schemas to the existing file

class RecipeIngredientResponse(BaseModel):
    item_id: int
    item_name: str
    quantity_grams: float
    is_optional: bool = False
    preparation_notes: Optional[str] = None
    
    class Config:
        orm_mode = True

class RecipeResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    goals: List[str]
    tags: List[str]
    dietary_tags: List[str]
    suitable_meal_times: List[str]
    cuisine: Optional[str]
    prep_time_min: Optional[int]
    cook_time_min: Optional[int]
    difficulty_level: Optional[str]
    servings: int
    macros_per_serving: Dict
    instructions: List[str]
    meal_prep_notes: Optional[str]
    chef_tips: Optional[str]
    
    class Config:
        from_attributes = True

class RecipeSearchParams(BaseModel):
    goal: Optional[str] = None
    dietary_type: Optional[str] = None
    meal_time: Optional[str] = None
    max_prep_time: Optional[int] = None
    cuisine: Optional[str] = None
    search: Optional[str] = None