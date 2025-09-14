# backend/app/schemas/optimizer.py

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
from datetime import datetime

class ConstraintsSchema(BaseModel):
    """Schema for optimization constraints"""
    daily_calories_min: float = Field(ge=1000, le=5000)
    daily_calories_max: float = Field(ge=1000, le=5000)
    daily_protein_min: float = Field(ge=0, le=500)
    daily_carbs_min: float = Field(default=0, ge=0)
    daily_carbs_max: float = Field(default=1000, ge=0)
    daily_fat_min: float = Field(default=0, ge=0)
    daily_fat_max: float = Field(default=200, ge=0)
    daily_fiber_min: float = Field(default=20, ge=0)
    meals_per_day: int = Field(default=3, ge=1, le=6)
    max_recipe_repeat_in_days: int = Field(default=2, ge=1, le=7)
    max_prep_time_minutes: int = Field(default=60, ge=5, le=180)
    dietary_restrictions: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    
    @validator('daily_calories_max')
    def validate_calorie_range(cls, v, values):
        if 'daily_calories_min' in values and v < values['daily_calories_min']:
            raise ValueError('daily_calories_max must be >= daily_calories_min')
        return v
        
class ObjectiveSchema(BaseModel):
    """Schema for optimization objective weights"""
    macro_deviation_weight: float = Field(default=0.4, ge=0, le=1)
    inventory_usage_weight: float = Field(default=0.3, ge=0, le=1)
    recipe_variety_weight: float = Field(default=0.2, ge=0, le=1)
    goal_alignment_weight: float = Field(default=0.1, ge=0, le=1)
    
    @validator('goal_alignment_weight')
    def validate_weights_sum(cls, v, values):
        total = (
            values.get('macro_deviation_weight', 0) +
            values.get('inventory_usage_weight', 0) +
            values.get('recipe_variety_weight', 0) +
            v
        )
        if abs(total - 1.0) > 0.01:  # Allow small floating point errors
            raise ValueError('Weights must sum to 1.0')
        return v
        
class OptimizationRequest(BaseModel):
    """Request schema for meal plan optimization"""
    days: int = Field(default=7, ge=1, le=14)
    constraints: ConstraintsSchema
    objective: ObjectiveSchema = Field(default_factory=ObjectiveSchema)
    use_current_inventory: bool = Field(default=True)
    include_shopping_list: bool = Field(default=True)
    
class RecipeInPlan(BaseModel):
    """Schema for recipe in meal plan"""
    id: int
    title: str
    macros_per_serving: Dict[str, float]
    prep_time_min: int
    cook_time_min: int
    
class DayPlan(BaseModel):
    """Schema for single day meal plan"""
    breakfast: Optional[RecipeInPlan]
    lunch: Optional[RecipeInPlan]
    dinner: Optional[RecipeInPlan]
    snack: Optional[RecipeInPlan]
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    
class OptimizationResponse(BaseModel):
    """Response schema for optimization results"""
    success: bool
    meal_plan: Dict
    optimization_method: str
    generation_time_seconds: float
    constraints_satisfied: bool = True
    warnings: List[str] = Field(default_factory=list)