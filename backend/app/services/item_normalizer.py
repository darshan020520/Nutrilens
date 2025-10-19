"""
LLM-Enhanced Item Normalizer for Nutrilens
===========================================

Drop-in replacement for Nutrilens item_normalizer.py with:
1. All traditional matching logic (exact, alias, fuzzy, token-based)
2. LLM fallback for low confidence items (<0.85)
3. ONE LLM call that does BOTH matching and unit conversion
4. Lower threshold for LLM results (0.75 vs 0.85 traditional)

NO REDUNDANCY. CLEAN. SIMPLE.
"""

import re
import json
import openai
from typing import List, Tuple, Optional, Dict
from difflib import SequenceMatcher
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

class Item:
    """Item from inventory database"""
    def __init__(self, id, canonical_name, aliases=None, category=None, density_g_per_ml=None):
        self.id = id
        self.canonical_name = canonical_name
        self.aliases = aliases or []
        self.category = category
        self.density_g_per_ml = density_g_per_ml


@dataclass
class NormalizationResult:
    """Result of item normalization with confidence"""
    item: Optional[Item]
    confidence: float
    matched_on: str  # 'exact', 'alias', 'fuzzy', 'partial', 'llm', 'none'
    alternatives: List[Tuple[Item, float]]
    original_input: str
    cleaned_input: str
    extracted_quantity: float
    extracted_unit: str
    quantity_grams: Optional[float] = None
    conversion_note: Optional[str] = None

    def to_dict(self):
        return {
            "item_id": self.item.id if self.item else None,
            "item_name": self.item.canonical_name if self.item else None,
            "quantity": self.extracted_quantity,
            "unit": self.extracted_unit,
            "quantity_grams": self.quantity_grams,
            "confidence": self.confidence,
            "matched_on": self.matched_on,
            "original_input": self.original_input,
        }


# ============================================================================
# MAIN NORMALIZER CLASS
# ============================================================================

class IntelligentItemNormalizer:
    """
    Hybrid normalizer: Traditional (fast) + LLM (accurate for edge cases)

    Strategy:
    1. Traditional matching (exact, alias, spelling, fuzzy, token-based)
    2. Items with confidence < 0.85 → ONE LLM call (matching + grams conversion)
    3. LLM threshold: 0.75 (lower because more context-aware)
    """

    def __init__(self, items_list: List[Item], openai_api_key: str = None):
        """Initialize with inventory items"""
        self.items_list = items_list
        self.items_cache = self._build_cache()
        self.brand_patterns = self._load_brand_patterns()
        self.unit_patterns = self._compile_unit_patterns()
        self.common_misspellings = self._load_common_misspellings()

        # Confidence thresholds
        self.traditional_threshold = 0.85  # For fuzzy/traditional matching
        self.llm_threshold = 0.75  # Lower threshold for LLM (smarter)

        # OpenAI setup
        if openai_api_key:
            openai.api_key = openai_api_key

    # ========================================================================
    # CACHE BUILDING
    # ========================================================================

    def _build_cache(self) -> Dict:
        """Build intelligent cache with multiple access patterns"""
        cache = {
            'by_name': {},
            'by_alias': {},
            'by_category': {},
            'by_tokens': {},
            'all_items': self.items_list
        }

        for item in self.items_list:
            cache['by_name'][item.canonical_name.lower()] = item

            for alias in item.aliases:
                cache['by_alias'][alias.lower()] = item

            category = item.category or 'uncategorized'
            if category not in cache['by_category']:
                cache['by_category'][category] = []
            cache['by_category'][category].append(item)

            tokens = item.canonical_name.lower().split('_')
            for token in tokens:
                if token not in cache['by_tokens']:
                    cache['by_tokens'][token] = []
                cache['by_tokens'][token].append(item)

        logger.info(f"Built cache with {len(self.items_list)} items")
        return cache

    def _load_brand_patterns(self) -> List[re.Pattern]:
        """Patterns to identify and remove brand names"""
        brands = [
            r'\b(amul|britannia|maggi|nestle|kellogs|fortune|mdh|everest|patanjali|haldiram)\b',
            r'\b(tata|reliance|fresh|organic|premium|best|quality|supreme)\b',
            r'\b(brand|tm|®|©)\b'
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in brands]

    def _compile_unit_patterns(self) -> Dict[str, re.Pattern]:
        """Compile patterns for extracting quantities and units"""
        return {
            'quantity_unit': re.compile(
                r'(\d+\.?\d*)\s*(kg|g|mg|l|ml|litre|liter|cup|tbsp|tsp|piece|pcs|packet|pack|bunch|dozen)',
                re.IGNORECASE
            ),
            'quantity_only': re.compile(r'^(\d+\.?\d*)\s+'),
            'unit_only': re.compile(r'\b(kg|g|mg|l|ml|litre|liter|cup|tbsp|tsp|piece|pcs)\b', re.IGNORECASE)
        }

    def _load_common_misspellings(self) -> Dict[str, str]:
        """Common misspellings and their corrections"""
        return {
            'chiken': 'chicken', 'chikcen': 'chicken',
            'panner': 'paneer', 'panir': 'paneer',
            'tamato': 'tomato', 'tomoto': 'tomato',
            'onian': 'onion', 'onoin': 'onion',
            'brocoli': 'broccoli', 'broccolli': 'broccoli',
            'spinnach': 'spinach', 'spinich': 'spinach',
            'yoghurt': 'yogurt', 'curd': 'yogurt',
            'dhania': 'coriander', 'pudina': 'mint',
            'capsicum': 'bell_pepper', 'shimla mirch': 'bell_pepper'
        }

    # ========================================================================
    # TRADITIONAL MATCHING (TIER 1)
    # ========================================================================

    def normalize(self, raw_input: str) -> NormalizationResult:
        """
        Traditional normalization (synchronous, no LLM)
        Returns result with confidence score
        """
        quantity, unit, cleaned = self._extract_quantity_and_clean(raw_input)

        # Try exact match (100% confidence)
        if cleaned in self.items_cache['by_name']:
            return NormalizationResult(
                item=self.items_cache['by_name'][cleaned],
                confidence=1.0,
                matched_on='exact',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )

        # Check aliases (95% confidence)
        if cleaned in self.items_cache['by_alias']:
            return NormalizationResult(
                item=self.items_cache['by_alias'][cleaned],
                confidence=0.95,
                matched_on='alias',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )

        # Check common misspellings (90% confidence)
        corrected = self._correct_spelling(cleaned)
        if corrected != cleaned and corrected in self.items_cache['by_name']:
            return NormalizationResult(
                item=self.items_cache['by_name'][corrected],
                confidence=0.9,
                matched_on='spelling_correction',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )

        # Fuzzy matching
        best_matches = self._fuzzy_match_with_context(cleaned)
        if best_matches:
            best_item, best_score = best_matches[0]
            alternatives = best_matches[1:4]

            return NormalizationResult(
                item=best_item if best_score > 0.6 else None,
                confidence=best_score,
                matched_on='fuzzy',
                alternatives=alternatives,
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )

        # Token-based matching
        partial_matches = self._token_based_matching(cleaned)
        if partial_matches:
            best_item, best_score = partial_matches[0]

            return NormalizationResult(
                item=best_item if best_score > 0.5 else None,
                confidence=best_score,
                matched_on='partial',
                alternatives=partial_matches[1:3],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=quantity,
                extracted_unit=unit
            )

        # No match found
        return NormalizationResult(
            item=None,
            confidence=0.0,
            matched_on='none',
            alternatives=[],
            original_input=raw_input,
            cleaned_input=cleaned,
            extracted_quantity=quantity,
            extracted_unit=unit
        )

    def _extract_quantity_and_clean(self, text: str) -> Tuple[float, str, str]:
        """Extract quantity, unit and clean the text"""
        text = text.strip().lower()
        quantity = 1.0
        unit = 'unit'

        # Extract quantity and unit
        match = self.unit_patterns['quantity_unit'].search(text)
        if match:
            quantity = float(match.group(1))
            unit = match.group(2).lower()
            text = self.unit_patterns['quantity_unit'].sub('', text).strip()
        else:
            match = self.unit_patterns['quantity_only'].search(text)
            if match:
                quantity = float(match.group(1))
                text = self.unit_patterns['quantity_only'].sub('', text).strip()

        # Remove brand names
        for brand_pattern in self.brand_patterns:
            text = brand_pattern.sub('', text).strip()

        # Clean up
        text = re.sub(r'[^\w\s]', ' ', text)
        text = ' '.join(text.split())
        text_underscore = text.replace(' ', '_')

        return quantity, unit, text_underscore

    def _correct_spelling(self, text: str) -> str:
        """Correct common misspellings"""
        if text in self.common_misspellings:
            return self.common_misspellings[text]

        words = text.split('_')
        corrected_words = [self.common_misspellings.get(word, word) for word in words]
        return '_'.join(corrected_words)

    def _fuzzy_match_with_context(self, text: str) -> List[Tuple[Item, float]]:
        """Fuzzy matching with context awareness"""
        matches = []

        for item_name, item in self.items_cache['by_name'].items():
            similarity = SequenceMatcher(None, text, item_name).ratio()

            # Boost for category match
            if item.category and any(cat_word in text for cat_word in str(item.category).split('_')):
                similarity += 0.1

            # Check aliases
            for alias in item.aliases:
                alias_similarity = SequenceMatcher(None, text, alias.lower()).ratio()
                similarity = max(similarity, alias_similarity)

            if similarity > 0.6:
                matches.append((item, min(similarity, 0.99)))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def _token_based_matching(self, text: str) -> List[Tuple[Item, float]]:
        """Match based on individual tokens"""
        text_tokens = set(text.split('_'))
        matches = []

        for token in text_tokens:
            if token in self.items_cache['by_tokens']:
                for item in self.items_cache['by_tokens'][token]:
                    item_tokens = set(item.canonical_name.lower().split('_'))
                    intersection = len(text_tokens & item_tokens)
                    union = len(text_tokens | item_tokens)
                    similarity = intersection / union if union > 0 else 0

                    if similarity > 0.3:
                        matches.append((item, similarity))

        unique_matches = {}
        for item, score in matches:
            if item.id not in unique_matches or unique_matches[item.id][1] < score:
                unique_matches[item.id] = (item, score)

        matches = list(unique_matches.values())
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    # ========================================================================
    # LLM-ENHANCED PROCESSING (TIER 2)
    # ========================================================================

    async def normalize_single(self, raw_input: str) -> NormalizationResult:
        """
        Normalize single item with LLM fallback (for WhatsApp, manual entry, etc.)

        Usage:
            result = await normalizer.normalize_single("Onion 500g")

        Returns complete result with item_id and quantity_grams
        """
        # Step 1: Try traditional matching
        result = self.normalize(raw_input)

        # Step 2: Try conversion if matched
        if result.item and result.confidence >= self.traditional_threshold:
            grams = self._convert_to_grams(
                result.extracted_quantity,
                result.extracted_unit,
                result.item
            )

            if grams is not None:
                # Success - done!
                result.quantity_grams = grams
                return result

        # Step 3: Low confidence or unknown unit - use LLM
        if result.confidence < self.traditional_threshold or result.quantity_grams is None:
            # Wrap in list, call batch processor, unwrap
            batch_input = [{
                "item_name": result.original_input,
                "quantity": result.extracted_quantity,
                "unit": result.extracted_unit
            }]

            batch_results = await self.normalize_batch(batch_input)
            return batch_results[0] if batch_results else result

        return result

    async def normalize_batch(self, receipt_items: List[Dict]) -> List[NormalizationResult]:
        """
        Process entire receipt with LLM fallback

        Simple flow:
        1. Try traditional normalize on all items
        2. Collect items with confidence < 0.85
        3. ONE LLM call for all low confidence items (matching + conversion together)
        4. Convert remaining high-confidence items to grams
        """
        print(f"\n{'='*80}")
        print(f"🔍 Processing {len(receipt_items)} items")
        print(f"{'='*80}\n")

        results = []
        low_confidence_items = []

        # Step 1: Traditional matching
        print("📊 STEP 1: Traditional Matching")
        print(f"\n🔍 RAW RECEIPT ITEMS FROM SCANNER:")
        print(json.dumps(receipt_items, indent=2))
        print()

        for idx, item in enumerate(receipt_items, 1):
            item_text = f"{item.get('item_name')} {item.get('quantity', '')}{item.get('unit', '')}"
            result = self.normalize(item_text)

            # Store original receipt data
            result.extracted_quantity = item.get('quantity', result.extracted_quantity)
            result.extracted_unit = item.get('unit', result.extracted_unit)

            # Debug output - show what traditional matching found
            print(f"   {idx}. '{item.get('item_name')}' → ", end='')
            if result.item:
                print(f"[{result.item.canonical_name}] ", end='')
            else:
                print(f"[NO MATCH] ", end='')
            print(f"(method:{result.matched_on}, conf:{result.confidence:.2f}) ", end='')

            if result.confidence >= self.traditional_threshold:
                # High confidence match - try conversion
                if result.item:
                    grams = self._convert_to_grams(
                        result.extracted_quantity,
                        result.extracted_unit,
                        result.item
                    )

                    if grams is not None:
                        # Success - conversion done
                        print(f"✅ {result.item.canonical_name} ({result.confidence:.2f}) → {grams}g")
                        result.quantity_grams = grams
                        results.append(result)
                    else:
                        # Unknown unit - send to LLM for conversion
                        print(f"⚠️  {result.item.canonical_name} ({result.confidence:.2f}) - unknown unit '{result.extracted_unit}', queuing for LLM")
                        low_confidence_items.append((item, result))
                else:
                    results.append(result)
            else:
                # Low confidence match - queue for LLM
                print(f"⚠️  Low confidence ({result.confidence:.2f}) - queuing for LLM")
                low_confidence_items.append((item, result))

        # Step 2: ONE LLM call for all low confidence items
        if low_confidence_items:
            print(f"\n🤖 STEP 2: LLM Batch Processing ({len(low_confidence_items)} items)")
            print(f"\n📤 ITEMS BEING SENT TO LLM:")
            for item, trad_res in low_confidence_items:
                print(f"   - {item.get('item_name')}: traditional_match={trad_res.item.canonical_name if trad_res.item else 'None'}, conf={trad_res.confidence:.2f}")
            print()
            llm_results = await self._llm_batch_process(low_confidence_items)
            results.extend(llm_results)
        else:
            print(f"\n✅ STEP 2: Skipped (all items matched with high confidence)")

        print(f"\n{'='*80}")
        print(f"✅ Complete: {len(results)} items processed")
        print(f"{'='*80}\n")

        return results

    async def _llm_batch_process(self, low_confidence_items: List) -> List[NormalizationResult]:
        """
        ONE LLM call that does EVERYTHING:
        - Item matching to inventory
        - Unit conversion to grams
        - Returns complete results

        No redundancy, no multiple calls.
        """
        # Build inventory context (limit to 100 items for token efficiency)
        inventory_context = self._build_inventory_summary()

        # Prepare items for LLM
        items_to_process = []
        for item, trad_result in low_confidence_items:
            # Check if item is already matched (just needs conversion) or needs matching
            already_matched = trad_result.item and trad_result.confidence >= self.traditional_threshold

            items_to_process.append({
                "receipt_text": item.get('item_name'),
                "quantity": item.get('quantity'),
                "unit": item.get('unit'),
                "already_matched": already_matched,
                "matched_item_id": trad_result.item.id if already_matched else None,
                "matched_item_name": trad_result.item.canonical_name if already_matched else None,
                "traditional_match": {
                    "item_name": trad_result.item.canonical_name if trad_result.item else None,
                    "confidence": trad_result.confidence
                },
                "alternatives": [
                    {"id": alt[0].id, "name": alt[0].canonical_name}
                    for alt in trad_result.alternatives[:3]
                ] if not already_matched else []
            })

        # ONE comprehensive prompt
        prompt = f"""
You are a grocery item assistant with TWO tasks:
1. Match receipt items to inventory (if not already matched)
2. Convert ALL quantities to GRAMS

INVENTORY DATABASE (top 100 items):
{inventory_context}

ITEMS TO PROCESS:
{json.dumps(items_to_process, indent=2)}

INSTRUCTIONS:
For each item:
- If "already_matched": true → Item is already matched, ONLY convert to grams
- If "already_matched": false → Match to inventory AND convert to grams

CONVERSION RULES:
- kg → multiply by 1000
- L/ml → assume 1ml=1g (water density) unless dairy/oil
- piece/pcs → estimate based on item type:
  * Vegetables: onion=150g, tomato=100g, capsicum=120g, carrot=60g
  * Fruits: banana=120g, apple=180g, orange=150g
  * Herbs: mint/coriander bunch=20g
  * Eggs: 50g each
- cup → 240g
- bunch → 200g
- unknown units → estimate reasonably based on context

MATCHING RULES (only for items needing matching):
- "Herb Mint" → "mint" (remove descriptors)
- "Red Capsicum" → "bell_pepper" (capsicum = bell pepper)
- "Loose Bean Shoots" → check for bean_sprouts variants
- Consider Indian names: pyaaz=onion, tamatar=tomato, pudina=mint, etc.

OUTPUT (strict JSON, no markdown):
{{
  "results": [
    {{
      "receipt_text": "Herb Mint",
      "matched_item_id": 7,
      "matched_name": "mint",
      "quantity_grams": 100,
      "confidence": 0.85,
      "reasoning": "Herb is descriptor, matches mint item"
    }}
  ]
}}

If no match found: {{"matched_item_id": null, "quantity_grams": <estimated_grams>, "confidence": 0.0}}
"""

        try:
            print(f"   🤖 Calling OpenAI GPT-4o-mini...")

            # OpenAI v1.0+ syntax
            client = openai.AsyncOpenAI(api_key=openai.api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            text_output = response.choices[0].message.content

            # Parse response
            cleaned = re.sub(r"^```json\s*", "", text_output.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = re.sub(r"^```\s*", "", cleaned)

            llm_response = json.loads(cleaned)
            llm_results_data = llm_response.get("results", [])

            # Convert to NormalizationResult objects
            final_results = []
            for idx, (item, trad_result) in enumerate(low_confidence_items):
                if idx < len(llm_results_data):
                    llm_data = llm_results_data[idx]
                    matched_id = llm_data.get("matched_item_id")

                    if matched_id:
                        # Find matched item
                        matched_item = next(
                            (i for i in self.items_cache['all_items'] if i.id == matched_id),
                            None
                        )

                        if matched_item:
                            # Success!
                            trad_result.item = matched_item
                            trad_result.confidence = llm_data.get("confidence", 0.80)
                            trad_result.matched_on = 'llm'
                            trad_result.quantity_grams = llm_data.get("quantity_grams")
                            trad_result.conversion_note = llm_data.get("reasoning", "LLM matched")

                            print(f"   ✅ {item.get('item_name')} → {matched_item.canonical_name} "
                                  f"({trad_result.confidence:.2f}, {trad_result.quantity_grams}g)")
                        else:
                            print(f"   ⚠️  {item.get('item_name')}: Invalid item_id {matched_id}")
                            trad_result.confidence = 0.3
                    else:
                        # No match found
                        print(f"   ❌ {item.get('item_name')}: No match in inventory")
                        trad_result.confidence = 0.3

                final_results.append(trad_result)

            return final_results

        except Exception as e:
            logger.error(f"LLM batch processing failed: {e}")
            print(f"   ❌ LLM error: {e}")

            # Fallback: return original results with low confidence
            for item, trad_result in low_confidence_items:
                trad_result.confidence = 0.3

            return [result for _, result in low_confidence_items]

    def _build_inventory_summary(self) -> str:
        """Build condensed inventory for LLM (token efficient)"""
        lines = []
        for item in self.items_cache['all_items'][:100]:
            aliases = ', '.join(item.aliases[:2]) if item.aliases else ''
            lines.append(
                f"{item.id}: {item.canonical_name} ({item.category or 'general'}) "
                f"[{aliases}]"
            )
        return '\n'.join(lines)

    # ========================================================================
    # UNIT CONVERSION (SINGLE METHOD)
    # ========================================================================

    def _convert_to_grams(self, quantity: float, unit: str, item: Item) -> Optional[float]:
        """
        Simple conversion for standard units
        Returns None if unit is unknown (signals need for LLM)
        """
        unit_lower = unit.lower().strip()

        # Standard weight units
        if unit_lower in ['kg']:
            return quantity * 1000
        if unit_lower in ['g', 'gram', 'grams']:
            return quantity

        # Standard volume units (need density)
        if unit_lower in ['l', 'litre', 'liter']:
            ml_value = quantity * 1000
            density = item.density_g_per_ml if item.density_g_per_ml else 1.0
            return ml_value * density

        if unit_lower in ['ml', 'milliliter', 'millilitre']:
            density = item.density_g_per_ml if item.density_g_per_ml else 1.0
            return quantity * density

        # Unknown unit - return None to signal "needs LLM"
        logger.info(f"Unknown unit '{unit}' for {item.canonical_name} - will use LLM for conversion")
        return None

    def get_threshold_for_match_type(self, matched_on: str) -> float:
        """
        Different confidence thresholds based on matching method
        LLM gets lower threshold because it's context-aware
        """
        thresholds = {
            'exact': 1.0,
            'alias': 0.95,
            'spelling_correction': 0.90,
            'llm': self.llm_threshold,  # 0.75 - trust LLM more
            'fuzzy': self.traditional_threshold,  # 0.85
            'partial': self.traditional_threshold,
            'none': 1.0
        }
        return thresholds.get(matched_on, self.traditional_threshold)
