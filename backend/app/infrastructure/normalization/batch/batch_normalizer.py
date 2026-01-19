"""Batch Normalizer - Processes multiple items in one pass"""
from typing import List, Dict
import logging
from app.infrastructure.normalization.chain.matcher_chain import MatcherChain
from app.infrastructure.normalization.converters.unit_converter import UnitConverter
from app.core.llm_orchestrator import LLMOrchestrator
from app.schemas.normaliser import ExtractStructureResult

logger = logging.getLogger(__name__)


class BatchNormalizer:
    """
    Processes multiple items efficiently with batching.

    Responsibilities:
    - Extract structures for all lines (batch LLM call)
    - Match all items using chain
    - Convert all units to grams
    - Return normalized results

    Key Optimization:
    - Single batch for structure extraction
    - Reduces LLM calls from O(N*4) to O(1) or O(2)
    """

    def __init__(
        self,
        llm_orchestrator: LLMOrchestrator,
        matcher_chain: MatcherChain,
        unit_converter: UnitConverter
    ):
        """
        Args:
            llm_orchestrator: LLMOrchestrator for batch structure extraction
            matcher_chain: MatcherChain instance
            unit_converter: UnitConverter instance
        """
        self.orchestrator = llm_orchestrator
        self.matcher = matcher_chain
        self.converter = unit_converter

    async def process_batch(self, lines: List[str], user_id: int) -> List[Dict]:
        """
        Process multiple lines in batch.

        Args:
            lines: List of item text lines
            user_id: User ID for token budget tracking

        Returns:
            List of normalized results
        """
        # BATCH STRUCTURE EXTRACTION - Single LLM call for all lines
        items_list = '\n'.join([f'"{line}"' for line in lines])

        logger.info(f"Batch extracting structures for {len(lines)} lines...")

        # Call orchestrator with batch extraction prompt
        structures_result = await self.orchestrator.run(
            user_id=user_id,
            slug="extract_batch_structures",
            variables={"items_list": items_list},
            response_model=List[ExtractStructureResult]
        )

        # Convert Pydantic models to dicts
        structures = [
            {"quantity": s.quantity, "unit": s.unit, "item_text": s.item_text}
            for s in structures_result
        ] if structures_result else []

        # Ensure we have same number of structures as lines (pad with None if needed)
        while len(structures) < len(lines):
            structures.append(None)

        logger.info(f"Extracted {len([s for s in structures if s])} / {len(lines)} structures")

        # Delegate to shared processing logic
        return await self._process_structures(structures, user_id=user_id, input_lines=lines)

    async def process_extracted_items(
        self,
        extracted_items: List[Dict],
        user_id: int
    ) -> List[Dict]:
        """
        Process items that are already extracted (e.g., from receipt scanner).

        Skips the extraction step - structure already provided by OCR.

        Args:
            extracted_items: Pre-extracted items from external source
                Format: [{"item_name": "Onion", "quantity": 2, "unit": "kg"}]
            user_id: User ID for token budget tracking

        Returns:
            List of normalized results (same format as process_batch)
        """
        logger.info(f"Processing {len(extracted_items)} pre-extracted items (skipping extraction)...")

        # Convert external format to internal structure format
        structures = [
            {
                "item_text": item.get("item_name", ""),
                "quantity": item.get("quantity", 0),
                "unit": item.get("unit", "")
            }
            for item in extracted_items
        ]

        # Delegate to matching + conversion logic
        return await self._process_structures(structures, user_id=user_id, input_lines=None)

    async def _process_structures(
        self,
        structures: List[Dict],
        user_id: int,
        input_lines: List[str] = None
    ) -> List[Dict]:
        """
        Core processing logic: Match items and convert units.

        Args:
            structures: List of extracted structures
                [{"quantity": N, "unit": "X", "item_text": "Y"}, ...]
            user_id: User ID for token budget tracking
            input_lines: Optional original input lines for error reporting

        Returns:
            List of normalized results
        """
        results = []
        input_lines = input_lines or [None] * len(structures)

        # Process each structure
        for idx, (structure, line) in enumerate(zip(structures, input_lines)):
            if not structure:
                results.append({
                    "success": False,
                    "error": "Could not extract structure",
                    "input": line
                })
                continue

            # Step 2: Match item (passes user_id through chain)
            match_result = await self.matcher.match(structure["item_text"], user_id=user_id)

            # Handle unknown item (5-tuple)
            if match_result and len(match_result) == 5:
                _, item_name, strategy, confidence, category = match_result

                results.append({
                    "success": False,
                    "error": "unknown_item_detected",
                    "unknown_item": {
                        "normalized_name": item_name,
                        "category": category,
                        "confidence": confidence
                    },
                    "input": line,
                    "extracted": structure
                })
                continue

            # No match
            if not match_result:
                results.append({
                    "success": False,
                    "error": "Could not match item",
                    "input": line,
                    "extracted": structure
                })
                continue

            # Normal match (4-tuple)
            item_id, item_name, strategy, match_confidence = match_result

            # Step 3: Convert to grams
            conversion = await self.converter.convert_to_grams(
                quantity=structure["quantity"],
                unit=structure["unit"],
                item_name=item_name,
                user_id=user_id
            )

            results.append({
                "success": True,
                "item_id": item_id,
                "item_name": item_name,
                "quantity_grams": conversion["grams"],
                "original_quantity": structure["quantity"],
                "original_unit": structure["unit"],
                "match_strategy": strategy,
                "match_confidence": match_confidence,
                "confidence": match_confidence,
                "conversion_method": conversion["method"],
                "conversion_confidence": conversion["confidence"],
                "input": line
            })

        return results
