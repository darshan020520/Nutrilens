"""Structure Extractor - Parses item text into structured format"""
from typing import Dict, Optional
import logging
from app.infrastructure.normalization.interfaces import ILLMAdapter

logger = logging.getLogger(__name__)


class StructureExtractor:
    """
    Extracts structured data from item text

    Responsibilities:
    - Parse "2 apples" -> {quantity: 2, unit: "whole", item: "apples"}
    - Use LLM for complex parsing
    - Handle various input formats
    """

    # Hardcoded prompt (will move to DB via PromptRepository)
    EXTRACTION_PROMPT = """Extract the quantity, unit, and item name from this text.

Text: {text}

Examples:
- "2 apples" -> quantity: 2, unit: "whole", item: "apples"
- "500g chicken" -> quantity: 500, unit: "grams", item: "chicken"
- "1 cup rice" -> quantity: 1, unit: "cup", item: "rice"

Extract the components."""

    def __init__(self, llm_adapter: ILLMAdapter):
        """
        Args:
            llm_adapter: ILLMAdapter for LLM calls
        """
        self.llm_adapter = llm_adapter

    async def extract(self, text: str) -> Optional[Dict]:
        """
        Extract structure from text

        Args:
            text: Item text (e.g., "2 apples")

        Returns:
            Dict with {quantity, unit, item_text} or None
        """
        # TODO: Implement regex parsing for simple cases
        # For now, use LLM for all extractions

        prompt = self.EXTRACTION_PROMPT.format(text=text)

        functions = [{
            "name": "extract_structure",
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "item_text": {"type": "string"}
                },
                "required": ["quantity", "unit", "item_text"]
            }
        }]

        result = await self.llm_adapter.call_llm_with_function(
            prompt=prompt,
            functions=functions,
            function_name="extract_structure"
        )

        if result:
            logger.debug(f"Extracted: '{text}' -> {result}")

        return result
