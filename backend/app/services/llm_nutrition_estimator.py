# backend/app/services/llm_nutrition_estimator.py
"""
LLM-based nutrition estimation service for external meals.
Uses OpenAI to estimate macros from dish descriptions.
"""

import json
import logging
from typing import Dict, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMNutritionEstimator:
    """Estimate nutrition information for external meals using LLM"""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def estimate_macros(
        self,
        dish_name: str,
        portion_size: str,
        restaurant_name: Optional[str] = None,
        cuisine_type: Optional[str] = None
    ) -> Dict:
        """
        Estimate nutrition information for a dish using LLM.

        Args:
            dish_name: Name of the dish (e.g., "Chicken Tikka Masala")
            portion_size: Size description (e.g., "1 large plate", "300g")
            restaurant_name: Optional restaurant name for context
            cuisine_type: Optional cuisine type (e.g., "Indian", "Italian")

        Returns:
            Dict with estimated macros and confidence score
        """
        try:
            # Build context-rich prompt
            prompt = self._build_estimation_prompt(
                dish_name, portion_size, restaurant_name, cuisine_type
            )

            # Call OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a nutrition expert. Estimate macro-nutrients for food items "
                            "based on typical restaurant portions and standard recipes. "
                            "Provide realistic estimates with confidence scores. "
                            "Always respond with valid JSON only, no additional text."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )

            # Parse response
            result = json.loads(response.choices[0].message.content)

            # Validate and format response
            return self._format_estimation_result(result, dish_name, portion_size)

        except Exception as e:
            logger.error(f"Error estimating macros with LLM: {str(e)}")
            # Return fallback estimation
            return self._fallback_estimation(dish_name, portion_size)

    def _build_estimation_prompt(
        self,
        dish_name: str,
        portion_size: str,
        restaurant_name: Optional[str],
        cuisine_type: Optional[str]
    ) -> str:
        """Build detailed prompt for LLM estimation"""

        prompt_parts = [
            f"Estimate the nutritional content for: {dish_name}",
            f"Portion size: {portion_size}"
        ]

        if restaurant_name:
            prompt_parts.append(f"Restaurant: {restaurant_name}")

        if cuisine_type:
            prompt_parts.append(f"Cuisine type: {cuisine_type}")

        prompt_parts.extend([
            "",
            "Provide your estimate in the following JSON format:",
            "{",
            '  "calories": <number>,',
            '  "protein_g": <number>,',
            '  "carbs_g": <number>,',
            '  "fat_g": <number>,',
            '  "fiber_g": <number>,',
            '  "confidence": <0.0 to 1.0>,',
            '  "reasoning": "<brief explanation of your estimation>"',
            "}",
            "",
            "Consider typical restaurant portions and cooking methods.",
            "Be realistic about calorie content - restaurant meals are often higher than home-cooked.",
            "Provide confidence score: 0.9+ for common dishes, 0.7-0.9 for less common, 0.5-0.7 for very specific."
        ])

        return "\n".join(prompt_parts)

    def _format_estimation_result(
        self,
        result: Dict,
        dish_name: str,
        portion_size: str
    ) -> Dict:
        """Format and validate LLM estimation result"""

        # Ensure all required fields exist with defaults
        formatted = {
            "calories": float(result.get("calories", 500)),
            "protein_g": float(result.get("protein_g", 25)),
            "carbs_g": float(result.get("carbs_g", 50)),
            "fat_g": float(result.get("fat_g", 20)),
            "fiber_g": float(result.get("fiber_g", 5)),
            "confidence": float(result.get("confidence", 0.7)),
            "reasoning": result.get("reasoning", "Estimated based on typical portions"),
            "dish_name": dish_name,
            "portion_size": portion_size,
            "estimation_method": "llm"
        }

        # Validate ranges
        formatted["calories"] = max(50, min(3000, formatted["calories"]))
        formatted["protein_g"] = max(0, min(200, formatted["protein_g"]))
        formatted["carbs_g"] = max(0, min(300, formatted["carbs_g"]))
        formatted["fat_g"] = max(0, min(150, formatted["fat_g"]))
        formatted["fiber_g"] = max(0, min(50, formatted["fiber_g"]))
        formatted["confidence"] = max(0.0, min(1.0, formatted["confidence"]))

        return formatted

    def _fallback_estimation(self, dish_name: str, portion_size: str) -> Dict:
        """
        Provide fallback estimation if LLM fails.
        Uses conservative average restaurant meal values.
        """
        logger.warning(f"Using fallback estimation for: {dish_name}")

        return {
            "calories": 600.0,
            "protein_g": 30.0,
            "carbs_g": 60.0,
            "fat_g": 20.0,
            "fiber_g": 5.0,
            "confidence": 0.5,
            "reasoning": "Fallback estimation - average restaurant meal",
            "dish_name": dish_name,
            "portion_size": portion_size,
            "estimation_method": "fallback"
        }


def estimate_nutrition_with_llm(
    dish_name: str,
    portion_size: str,
    restaurant_name: Optional[str] = None,
    cuisine_type: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    Convenience function to estimate nutrition with LLM.

    Args:
        dish_name: Name of the dish
        portion_size: Size description
        restaurant_name: Optional restaurant context
        cuisine_type: Optional cuisine type
        api_key: OpenAI API key (will use from settings if not provided)

    Returns:
        Dict with estimated nutrition and confidence
    """
    from app.core.config import settings

    if not api_key:
        api_key = settings.openai_api_key

    estimator = LLMNutritionEstimator(api_key)
    return estimator.estimate_macros(
        dish_name=dish_name,
        portion_size=portion_size,
        restaurant_name=restaurant_name,
        cuisine_type=cuisine_type
    )
