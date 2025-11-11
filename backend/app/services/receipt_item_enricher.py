"""
Receipt Item Enricher
=====================

Enriches unmatched receipt items using FDC + LLM pipeline.

Flow:
1. LLM normalizes item name using existing DB items as examples
2. FDC search for normalized name
3. LLM selects best FDC match
4. Returns enriched data for user confirmation
"""

import logging
import json
from typing import List, Dict, Optional
from openai import OpenAI

from app.models.database import Item
from app.services.fdc_service import FDCService

logger = logging.getLogger(__name__)


class ReceiptItemEnricher:
    """
    Enriches receipt items that didn't match existing items database

    Reuses the proven FDC + LLM enrichment pipeline from item seeding
    """

    def __init__(self, openai_api_key: str, existing_items: List[Item]):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.fdc_service = FDCService()
        self.existing_items = existing_items

    async def enrich_batch(self, item_names: List[str]) -> List[Dict]:
        """
        Enrich multiple receipt items in one batch

        Args:
            item_names: List of item names from receipt (e.g., ["Red Capsicum", "Chinese Broccoli"])

        Returns:
            List of enriched item dicts:
            [
                {
                    "original_name": "Red Capsicum",
                    "canonical_name": "bell_pepper",
                    "category": "vegetables",
                    "fdc_id": "123456",
                    "nutrition_per_100g": {...},
                    "confidence": 0.85,
                    "reasoning": "..."
                }
            ]
        """
        logger.info(f"Enriching {len(item_names)} receipt items...")

        enriched_items = []

        for item_name in item_names:
            try:
                enriched = await self.enrich_single(item_name)
                enriched_items.append(enriched)
            except Exception as e:
                logger.error(f"Failed to enrich '{item_name}': {e}")
                # Add failed entry
                enriched_items.append({
                    "original_name": item_name,
                    "canonical_name": None,
                    "category": None,
                    "fdc_id": None,
                    "nutrition_per_100g": None,
                    "confidence": 0.0,
                    "reasoning": f"Enrichment failed: {str(e)}"
                })

        return enriched_items

    async def enrich_single(self, item_name: str) -> Dict:
        """
        Enrich a single receipt item

        Flow:
        1. LLM normalizes name → canonical_name
        2. FDC search for canonical_name
        3. LLM selects best FDC match
        4. Parse nutrition
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Enriching: '{item_name}'")

        # Step 1: LLM normalizes name
        canonical_name = await self._normalize_name_with_llm(item_name)
        logger.info(f"  Canonical name: {canonical_name}")

        # Step 2: FDC search (returns up to 10 results by default)
        fdc_matches = await self.fdc_service.search_food(canonical_name)

        # Limit to top 3 matches
        fdc_matches = fdc_matches[:3] if fdc_matches else []

        if not fdc_matches:
            logger.warning(f"  No FDC matches found for '{canonical_name}'")
            return {
                "original_name": item_name,
                "canonical_name": canonical_name,
                "category": None,
                "fdc_id": None,
                "nutrition_per_100g": None,
                "confidence": 0.3,
                "reasoning": "No matches found in USDA FDC database"
            }

        logger.info(f"  Found {len(fdc_matches)} FDC matches")

        # Step 3: LLM selects best match
        enriched = await self._llm_select_best_match(
            canonical_name=canonical_name,
            original_name=item_name,
            fdc_matches=fdc_matches
        )

        logger.info(f"  Selected: {enriched['canonical_name']} (confidence: {enriched['confidence']})")
        logger.info(f"{'='*80}\n")

        return enriched

    async def _normalize_name_with_llm(self, item_name: str) -> str:
        """
        Use LLM to normalize item name using existing DB items as examples

        Example:
            "Red Capsicum" → "bell_pepper"
            "Chinese Broccoli" → "broccoli"
        """
        # Get top 50 most common items as examples
        example_items = [item.canonical_name for item in self.existing_items[:50]]

        prompt = f"""You are a food item normalizer. Convert the given item name to a standardized canonical name suitable for food databases.

EXISTING ITEMS IN DATABASE (use as examples):
{', '.join(example_items)}

RULES:
1. Use lowercase, underscore-separated format (e.g., "bell_pepper")
2. Remove regional/cultural prefixes (e.g., "Chinese Broccoli" → "broccoli")
3. Use the most common/generic name (e.g., "Red Capsicum" → "bell_pepper")
4. If item matches existing DB item closely, use that exact name
5. Keep it simple and searchable in USDA FDC

INPUT ITEM: "{item_name}"

OUTPUT (single canonical name only, no explanation):"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        canonical_name = response.choices[0].message.content.strip().lower()
        canonical_name = canonical_name.replace(" ", "_").replace("-", "_")

        return canonical_name

    async def _llm_select_best_match(
        self,
        canonical_name: str,
        original_name: str,
        fdc_matches: List[Dict]
    ) -> Dict:
        """
        Use LLM to select best FDC match and extract metadata

        Returns enriched item dict with nutrition, category, etc.
        """
        # Format FDC matches for LLM
        matches_text = ""
        for idx, match in enumerate(fdc_matches):
            matches_text += f"\nMatch {idx}:\n"
            matches_text += f"  Description: {match.get('description', 'N/A')}\n"
            matches_text += f"  FDC ID: {match.get('fdcId', 'N/A')}\n"
            matches_text += f"  Data Type: {match.get('dataType', 'N/A')}\n"
            matches_text += f"  Brand: {match.get('brandOwner', 'Generic')}\n"

        prompt = f"""You are selecting the best USDA FDC food match for a grocery item.

ITEM: "{canonical_name}" (original: "{original_name}")

FDC MATCHES:
{matches_text}

SELECT the best match and provide:
1. Best match index (0, 1, or 2)
2. Category (vegetables, fruits, meat, dairy, grains, etc.)
3. Confidence score (0.0-1.0)
4. Brief reasoning

OUTPUT strict JSON:
{{
    "best_match_index": 0,
    "category": "vegetables",
    "confidence": 0.9,
    "reasoning": "Generic fresh vegetable, no brand"
}}"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Get selected FDC match
        best_idx = result["best_match_index"]
        best_fdc_match = fdc_matches[best_idx]

        # Parse nutrition from selected match
        nutrition = self.fdc_service._parse_fdc_nutrients(best_fdc_match)

        return {
            "original_name": original_name,
            "canonical_name": canonical_name,
            "category": result["category"],
            "fdc_id": str(best_fdc_match.get("fdcId", "")),
            "nutrition_per_100g": nutrition,
            "confidence": result["confidence"],
            "reasoning": result["reasoning"]
        }
