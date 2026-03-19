from typing import List, Dict
import asyncio
import logging
import time
from app.infrastructure.normalization.chain.matcher_chain import MatcherChain
from app.infrastructure.normalization.converters.unit_converter import UnitConverter
from app.core.llm_orchestrator import LLMOrchestrator
from app.schemas.normaliser import ExtractStructureResult

logger = logging.getLogger(__name__)


class BatchNormalizer:

    def __init__(
        self,
        llm_orchestrator: LLMOrchestrator,
        matcher_chain: MatcherChain,
        unit_converter: UnitConverter
    ):

        self.orchestrator = llm_orchestrator
        self.matcher = matcher_chain
        self.converter = unit_converter

    async def process_batch(self, lines: List[str], user_id: int) -> List[Dict]:

        items_list = '\n'.join([f'"{line}"' for line in lines])

        structures_result = await self.orchestrator.run(
            user_id=user_id,
            slug="extract_batch_structures",
            variables={"items_list": items_list},
            response_model=List[ExtractStructureResult]
        )

        structures = [
            {"quantity": s.quantity, "unit": s.unit, "item_text": s.item_text}
            for s in structures_result
        ] if structures_result else []

        print(f"\n=== BATCH NORMALIZER: LLM extracted {len(structures)} structures ===")
        for i, s in enumerate(structures):
            print(f"  [{i}] item_text='{s['item_text']}', qty={s['quantity']}, unit='{s['unit']}'")
        print("=" * 60)

        while len(structures) < len(lines):
            structures.append(None)


        return await self._process_structures(structures, user_id=user_id, input_lines=lines)

    async def process_extracted_items(
        self,
        extracted_items: List[Dict],
        user_id: int
    ) -> List[Dict]:
        structures = [
            {
                "item_text": item.get("item_name", ""),
                "quantity": item.get("quantity", 0),
                "unit": item.get("unit", "")
            }
            for item in extracted_items
        ]


        return await self._process_structures(structures, user_id=user_id, input_lines=None)

    async def _process_structures(
        self,
        structures: List[Dict],
        user_id: int,
        input_lines: List[str] = None
    ) -> List[Dict]:

        # Pre-compute input lines for each structure
        lines = []
        for idx, structure in enumerate(structures):
            if input_lines and idx < len(input_lines):
                lines.append(input_lines[idx])
            elif structure:
                lines.append(f"{structure['quantity']}{structure['unit']} {structure['item_text']}")
            else:
                lines.append(None)

        # Run all match calls concurrently
        match_tasks = [
            self.matcher.match(structure["item_text"], user_id=user_id) if structure else None
            for structure in structures
        ]
        t_match = time.perf_counter()
        match_results = await asyncio.gather(*[t for t in match_tasks if t is not None])
        logger.info("normalizer.match_batch_completed items=%s duration_ms=%.1f", len(match_results), (time.perf_counter() - t_match) * 1000)

        # Re-insert None placeholders for missing structures
        filled_match_results = []
        match_iter = iter(match_results)
        for structure in structures:
            filled_match_results.append(next(match_iter) if structure else None)

        # Process results and run conversions concurrently
        conversion_tasks = []
        conversion_indices = []
        results = []

        for idx, (structure, match_result, line) in enumerate(zip(structures, filled_match_results, lines)):
            if not structure:
                results.append({
                    "success": False,
                    "error": "Could not extract structure",
                    "input": line
                })
                continue

            print(f"\n--- Matching item: '{structure['item_text']}' ---")
            print(f"--- Result: {match_result} ---")

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

            if not match_result:
                results.append({
                    "success": False,
                    "error": "Could not match item",
                    "input": line,
                    "extracted": structure
                })
                continue

            item_id, item_name, strategy, match_confidence = match_result
            conversion_tasks.append(self.converter.convert_to_grams(
                quantity=structure["quantity"],
                unit=structure["unit"],
                item_name=item_name,
                user_id=user_id
            ))
            conversion_indices.append((idx, item_id, item_name, strategy, match_confidence, structure, line))
            results.append(None)  # placeholder

        # Run all conversions concurrently
        t_conv = time.perf_counter()
        conversions = await asyncio.gather(*conversion_tasks)
        logger.info("normalizer.conversion_batch_completed items=%s duration_ms=%.1f", len(conversions), (time.perf_counter() - t_conv) * 1000)

        for (idx, item_id, item_name, strategy, match_confidence, structure, line), conversion in zip(conversion_indices, conversions):
            results[idx] = {
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
            }

        return results
