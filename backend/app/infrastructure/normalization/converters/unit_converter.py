"""Unit Converter - Converts quantities to grams"""
from typing import Dict, Optional
import logging
from app.core.llm_orchestrator import LLMOrchestrator
from app.schemas.normaliser import ConvertToGramsResult

logger = logging.getLogger(__name__)


class UnitConverter:

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

        self.orchestrator = llm_orchestrator

    def _try_standard_conversion(self, quantity: float, unit: str) -> Optional[float]:

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


        if not unit or unit.lower() in ("null", "none", ""):
            unit = "piece"
            logger.debug(f"Empty/null unit detected, treating as 'piece' for {item_name}")

        grams = self._try_standard_conversion(quantity, unit)
        if grams is not None:
            logger.debug(f"Standard conversion: {quantity} {unit} = {grams}g")
            return {
                "grams": grams,
                "confidence": 1.0,
                "method": "standard"
            }

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
