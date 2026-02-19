"""
Pydantic models for AI-powered recommendations.

Used by LLMOrchestrator as response_model for recommendation prompts.
"""

from typing import List
from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    """Generic AI recommendation response."""
    recommendations: List[str]


class AIRecipeSuggestion(BaseModel):
    """A single AI-generated recipe suggestion."""
    name: str
    description: str
    ingredients_used: List[str]
    estimated_prep_time_min: int
    estimated_calories: int
    estimated_protein_g: int
    difficulty: str  # easy, medium, hard


class AIRecipeResponse(BaseModel):
    """Response model for AI creative recipes."""
    recipes: List[AIRecipeSuggestion]
