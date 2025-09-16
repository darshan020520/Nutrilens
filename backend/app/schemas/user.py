from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict
from datetime import datetime, time
from enum import Enum

class GoalType(str, Enum):
    MUSCLE_GAIN = "muscle_gain"
    FAT_LOSS = "fat_loss"
    BODY_RECOMP = "body_recomp"
    WEIGHT_TRAINING = "weight_training"
    ENDURANCE = "endurance"
    GENERAL_HEALTH = "general_health"

class PathType(str, Enum):
    IF_16_8 = "if_16_8"
    IF_18_6 = "if_18_6"
    OMAD = "omad"
    TRADITIONAL = "traditional"
    BODYBUILDER = "bodybuilder"

class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    MODERATELY_ACTIVE = "moderately_active"
    VERY_ACTIVE = "very_active"
    EXTRA_ACTIVE = "extra_active"

class DietaryType(str, Enum):
    VEGETARIAN = "vegetarian"
    NON_VEGETARIAN = "non_vegetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"

# User Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    
    @validator('password')
    def validate_password(cls, v):
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Profile Schemas
class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=13, le=100)
    height_cm: float = Field(..., ge=100, le=250)
    weight_kg: float = Field(..., ge=30, le=300)
    sex: str = Field(..., pattern="^(male|female)$")
    activity_level: ActivityLevel
    medical_conditions: Optional[List[str]] = []

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    activity_level: Optional[ActivityLevel] = None
    medical_conditions: Optional[List[str]] = None

class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    age: int
    height_cm: float
    weight_kg: float
    sex: str
    activity_level: str
    medical_conditions: List[str]
    bmr: Optional[float]
    tdee: Optional[float]
    goal_calories: Optional[float]
    
    class Config:
        from_attributes = True

# Goal Schemas
class GoalCreate(BaseModel):
    goal_type: GoalType
    target_weight: Optional[float] = None
    target_date: Optional[datetime] = None
    target_body_fat_percentage: Optional[float] = Field(None, ge=5, le=50)
    macro_targets: Dict[str, float] = Field(
        default={"protein": 0.3, "carbs": 0.45, "fat": 0.25}
    )
    
    @validator('macro_targets')
    def validate_macros(cls, v):
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):  # Allow for floating point errors
            raise ValueError(f'Macro targets must sum to 1.0, got {total}')
        return v

# Path Schemas
class MealWindow(BaseModel):
    meal: str
    start_time: time
    end_time: time

class PathSelection(BaseModel):
    path_type: PathType
    custom_windows: Optional[List[MealWindow]] = None
    
    @validator('custom_windows')
    def validate_windows(cls, v, values):
        if values.get('path_type') == PathType.IF_16_8:
            # Validate 16:8 window
            pass
        return v

# Preference Schemas
class PreferenceCreate(BaseModel):
    dietary_type: DietaryType
    allergies: List[str] = []
    disliked_ingredients: List[str] = []
    cuisine_preferences: List[str] = []
    max_prep_time_weekday: int = Field(30, ge=10, le=120)
    max_prep_time_weekend: int = Field(60, ge=10, le=180)

# Onboarding Response
class OnboardingTargets(BaseModel):
    bmr: float
    tdee: float
    goal_calories: float
    macro_targets: Dict[str, float]
    meal_windows: List[MealWindow]
    meals_per_day: int