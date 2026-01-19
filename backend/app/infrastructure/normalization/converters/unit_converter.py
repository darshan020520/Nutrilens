"""Unit Converter - Converts quantities to grams"""
from typing import Dict, Optional
import logging
from app.core.llm_orchestrator import LLMOrchestrator
from app.schemas.normaliser import ConvertToGramsResult

logger = logging.getLogger(__name__)


class UnitConverter:
    """
    Converts quantity + unit to grams.

    Responsibilities:
    - Handle standard conversions (g, kg, mg) instantly
    - Use LLM for intelligent conversions (cups, tbsp, pieces, etc.)
    - Return grams + confidence
    """

    # Standard weight conversions (no LLM needed)
    STANDARD_UNITS = {
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
        "kg": 1000.0,
        "kilogram": 1000.0,
        "kilograms": 1000.0,
        "mg": 0.001,
        "milligram": 0.001,
        "milligrams": 0.001,
    }

    def __init__(self, llm_orchestrator: LLMOrchestrator):
        """
        Args:
            llm_orchestrator: LLMOrchestrator for LLM-based conversions
        """
        self.orchestrator = llm_orchestrator

    def _try_standard_conversion(self, quantity: float, unit: str) -> Optional[float]:
        """Try standard unit conversion (no LLM call)."""
        unit_lower = unit.lower().strip()
        if unit_lower in self.STANDARD_UNITS:
            return quantity * self.STANDARD_UNITS[unit_lower]
        return None

    async def convert_to_grams(
        self,
        quantity: float,
        unit: str,
        item_name: str,
        user_id: int
    ) -> Dict:
        """
        Convert quantity + unit to grams.

        Args:
            quantity: Numeric quantity
            unit: Unit string (g, kg, cup, tbsp, piece, etc.)
            item_name: Item name for context-aware conversion
            user_id: User ID for token budget tracking

        Returns:
            {"grams": float, "confidence": float, "method": str}
        """
        # Try standard conversion first (no LLM call)
        grams = self._try_standard_conversion(quantity, unit)
        if grams is not None:
            logger.debug(f"Standard conversion: {quantity} {unit} = {grams}g")
            return {
                "grams": grams,
                "confidence": 1.0,
                "method": "standard"
            }

        # Use LLM for intelligent conversion
        try:
            result = await self.orchestrator.run(
                user_id=user_id,
                slug="convert_to_grams",
                variables={
                    "quantity": str(quantity),
                    "unit": unit,
                    "item_name": item_name
                },
                response_model=ConvertToGramsResult
            )

            logger.debug(
                f"LLM conversion: {quantity} {unit} {item_name} = {result.grams}g "
                f"(confidence: {result.confidence:.3f})"
            )
            return {
                "grams": result.grams,
                "confidence": result.confidence,
                "method": "llm"
            }

        except Exception as e:
            logger.warning(f"Could not convert: {quantity} {unit} {item_name} - {e}")
            return {
                "grams": None,
                "confidence": 0.0,
                "method": "failed"
            }
