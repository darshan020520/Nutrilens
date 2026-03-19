"""
Pydantic models for AI-powered recommendations.

Used by LLMOrchestrator as response_model for recommendation prompts.
"""

from typing import List, Optional
from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    """Generic AI recommendation response."""
    recommendations: List[str]


class AIRecipeIngredient(BaseModel):
    """Ingredient with quantity for an AI-generated recipe."""
    name: str          # canonical_name of the item (e.g. "chicken_breast")
    quantity_grams: float


class AIRecipeSuggestion(BaseModel):
    """A single AI-generated recipe suggestion — rich enough to seed into the DB."""
    name: str
    description: str
    cuisine: str = "general"
    ingredients: List[AIRecipeIngredient]
    instructions: List[str]
    estimated_prep_time_min: int
    estimated_calories: int
    estimated_protein_g: int
    estimated_carbs_g: int = 0
    estimated_fat_g: int = 0
    difficulty: str               # easy / medium / hard
    suitable_meal_times: List[str] = ["lunch", "dinner"]
    goals: List[str] = ["general_health"]
    dietary_tags: List[str] = []


class AIRecipeResponse(BaseModel):
    """Response model for AI creative recipes."""
    recipes: List[AIRecipeSuggestion]
