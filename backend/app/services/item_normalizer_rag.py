"""
RAG-Based Item Normalizer for Nutrilens
========================================

Clean, reliable matching pipeline:
1. Exact match (100%)
2. Alias match (95%)
3. Vector similarity >0.90 (92%) - Trust semantic search
4. LLM with vector context 0.75-0.90 (80%) - RAG verification
5. No match / needs confirmation

+ Intelligent unit conversion (only LLM when needed)
+ Manual entry support with structure extraction

NO fuzzy matching, NO spelling corrections, NO unreliable heuristics.
"""

import json
import logging
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session
import openai

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
    matched_on: str  # 'exact', 'alias', 'vector', 'llm_verified', 'none'
    alternatives: List[Tuple[Item, float]]
    original_input: str
    cleaned_input: str
    extracted_quantity: float
    extracted_unit: str
    quantity_grams: Optional[float] = None
    conversion_note: Optional[str] = None
    reasoning: Optional[str] = None  # For LLM decisions

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
            "reasoning": self.reasoning,
            "conversion_note": self.conversion_note
        }


# ============================================================================
# RAG-BASED NORMALIZER
# ============================================================================

class RAGItemNormalizer:
    """
    Pure RAG pipeline for item normalization

    Flow:
    1. Exact/Alias (deterministic, instant)
    2. Vector retrieval (semantic, fast)
    3. LLM generation (contextual, as needed)
    4. Intelligent unit conversion (standard → LLM)
    """

    def __init__(
        self,
        items_list: List[Item],
        db: Session,
        openai_api_key: str
    ):
        """
        Initialize RAG normalizer

        Args:
            items_list: List of Item objects from database
            db: SQLAlchemy session for vector queries
            openai_api_key: OpenAI API key for embeddings and LLM
        """
        self.items_list = items_list
        self.db = db
        self.items_cache = self._build_cache()

        # Initialize embedding service
        from app.services.embedding_service import EmbeddingService
        self.embedder = EmbeddingService(
            api_key=openai_api_key,
            model="text-embedding-3-small"
        )

        # OpenAI client for LLM
        openai.api_key = openai_api_key

        # Thresholds
        self.vector_trust_threshold = 0.90  # Trust vector results above this
        self.vector_llm_threshold = 0.75    # Send to LLM below this
        self.auto_add_threshold = 0.75      # Auto-add items above this

        logger.info(f"RAG Normalizer initialized with {len(items_list)} items")

    def _build_cache(self) -> Dict:
        """Build lookup caches for fast exact/alias matching"""
        cache = {
            'by_name': {},
            'by_alias': {},
            'all_items': self.items_list
        }

        for item in self.items_list:
            # Canonical name lookup (case-insensitive)
            cache['by_name'][item.canonical_name.lower()] = item

            # Alias lookup (case-insensitive)
            for alias in item.aliases:
                cache['by_alias'][alias.lower()] = item

        return cache

    def _clean_text(self, text: str) -> str:
        """
        Simple text cleaning
        - Lowercase
        - Replace spaces with underscores
        - Remove special chars
        """
        text = text.strip().lower()
        text = text.replace(' ', '_')
        text = ''.join(c for c in text if c.isalnum() or c == '_')
        return text

    # ========================================================================
    # RAG PIPELINE - ITEM MATCHING
    # ========================================================================

    async def normalize_single(self, raw_input: str) -> NormalizationResult:
        """
        RAG-based normalization for single item

        Pipeline:
        1. Exact match → 100%
        2. Alias match → 95%
        3. Vector similarity >0.90 → 92% (trust it)
        4. Vector similarity 0.75-0.90 → LLM verification
        5. Vector similarity <0.75 → No match

        Args:
            raw_input: e.g., "Herb Mint", "Red Capsicum", "Chinese Broccoli"

        Returns:
            NormalizationResult with matched item and confidence
        """
        logger.info(f"🔍 RAG Normalize: '{raw_input}'")

        # Clean input
        cleaned = self._clean_text(raw_input)
        logger.info(f"   Cleaned: '{cleaned}'")

        # Step 1: Exact match (100%)
        if cleaned in self.items_cache['by_name']:
            item = self.items_cache['by_name'][cleaned]
            logger.info(f"   ✅ EXACT MATCH: {item.canonical_name} (1.00)")
            return NormalizationResult(
                item=item,
                confidence=1.0,
                matched_on='exact',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning="Exact match in database"
            )

        # Step 2: Alias match (95%)
        if cleaned in self.items_cache['by_alias']:
            item = self.items_cache['by_alias'][cleaned]
            logger.info(f"   ✅ ALIAS MATCH: {item.canonical_name} (0.95)")
            return NormalizationResult(
                item=item,
                confidence=0.95,
                matched_on='alias',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning="Matched via alias"
            )

        # Step 3: Vector similarity search (RAG retrieval)
        logger.info(f"   🔍 Vector search...")
        vector_results = await self._vector_search(raw_input, top_k=3)

        if not vector_results:
            logger.info(f"   ❌ NO MATCH")
            return NormalizationResult(
                item=None,
                confidence=0.0,
                matched_on='none',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning="No similar items found"
            )

        best_item, best_similarity = vector_results[0]
        alternatives = vector_results[1:3]

        logger.info(f"   📊 Vector top match: {best_item.canonical_name} ({best_similarity:.3f})")

        # Step 4a: High similarity → Trust it (92%)
        if best_similarity >= self.vector_trust_threshold:
            logger.info(f"   ✅ VECTOR MATCH: {best_item.canonical_name} (0.92)")
            return NormalizationResult(
                item=best_item,
                confidence=0.92,
                matched_on='vector',
                alternatives=alternatives,
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning=f"High vector similarity ({best_similarity:.2f})"
            )

        # Step 4b: Medium similarity → LLM verification (RAG generation)
        elif best_similarity >= self.vector_llm_threshold:
            logger.info(f"   🤖 LLM verification needed ({best_similarity:.3f})")
            return await self._llm_verify(raw_input, vector_results)

        # Step 5: Low similarity → No match
        else:
            logger.info(f"   ❌ Similarity too low ({best_similarity:.3f})")
            return NormalizationResult(
                item=None,
                confidence=best_similarity,
                matched_on='none',
                alternatives=alternatives,
                original_input=raw_input,
                cleaned_input=cleaned,
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning=f"Similarity too low ({best_similarity:.2f})"
            )

    async def _vector_search(
        self,
        query_text: str,
        top_k: int = 3
    ) -> List[Tuple[Item, float]]:
        """
        Vector similarity search using embeddings

        Returns:
            [(Item, similarity_score), ...] sorted by similarity
        """
        try:
            # Generate embedding for input text
            embedding = await self.embedder.get_embedding(query_text)
            embedding_str = self.embedder.embedding_to_db_string(embedding)

            # Vector similarity query (cosine similarity)
            result = self.db.execute(text("""
                SELECT
                    id,
                    canonical_name,
                    1 - (embedding::vector(1536) <=> :embedding ::vector(1536)) as similarity
                FROM items
                WHERE embedding IS NOT NULL
                ORDER BY embedding::vector(1536) <=> :embedding ::vector(1536)
                LIMIT :top_k
            """), {
                "embedding": embedding_str,
                "top_k": top_k
            }).mappings().fetchall()

            # Convert to (Item, similarity) tuples
            matches = []
            for row in result:
                item = next(
                    (i for i in self.items_cache['all_items'] if i.id == row['id']),
                    None
                )
                if item:
                    matches.append((item, row['similarity']))
            print("vector matches", matches)
            return matches

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def _llm_verify(
        self,
        raw_input: str,
        vector_results: List[Tuple[Item, float]]
    ) -> NormalizationResult:
        """
        LLM verification with vector context (RAG generation)

        Args:
            raw_input: User's input text
            vector_results: Top-k vector matches for context

        Returns:
            NormalizationResult with LLM decision
        """
        # Prepare context from vector results
        candidates = []
        for item, similarity in vector_results[:3]:
            candidates.append({
                "id": item.id,
                "name": item.canonical_name,
                "category": item.category,
                "aliases": item.aliases[:3],
                "similarity": round(similarity, 3)
            })

        # LLM prompt with RAG context
        prompt = f"""You are a grocery item matcher. A user scanned: "{raw_input}"

VECTOR SEARCH RESULTS (semantic similarity):
{json.dumps(candidates, indent=2)}

TASK: Determine if any candidate is a correct match.

MATCHING RULES:
- "Herb Mint" → "mint" ✅
- "Red Capsicum" → "bell_pepper" ✅ (capsicum = bell pepper)
- "Chinese Broccoli" → "broccoli" ✅ (similar vegetable)
- "Loose Bean Shoots" → "bean_sprouts" ✅ (bean shoots = sprouts)
- "Japanese Pumpkin" → NO MATCH ❌ (if pumpkin not in candidates)
- Color descriptors can be ignored: "Red Capsicum" = "Yellow Capsicum" = "bell_pepper"

OUTPUT (strict JSON, no markdown):
{{
  "matched": true/false,
  "item_id": <id> or null,
  "confidence": 0.75-0.90,
  "reasoning": "Brief explanation"
}}

If no good match: {{"matched": false, "item_id": null, "confidence": 0.0, "reasoning": "explanation"}}
"""

        try:
            logger.info(f"   🤖 Calling LLM for verification...")

            client = openai.AsyncOpenAI(api_key=openai.api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            # Parse response
            text_output = response.choices[0].message.content.strip()
            text_output = text_output.replace("```json", "").replace("```", "").strip()
            llm_result = json.loads(text_output)

            if llm_result.get("matched") and llm_result.get("item_id"):
                # Find matched item
                matched_item = next(
                    (i for i in self.items_cache['all_items'] if i.id == llm_result["item_id"]),
                    None
                )

                if matched_item:
                    confidence = llm_result.get("confidence", 0.80)
                    reasoning = llm_result.get("reasoning", "LLM verified match")

                    logger.info(f"   ✅ LLM VERIFIED: {matched_item.canonical_name} ({confidence:.2f})")

                    return NormalizationResult(
                        item=matched_item,
                        confidence=confidence,
                        matched_on='llm_verified',
                        alternatives=vector_results[1:3],
                        original_input=raw_input,
                        cleaned_input=self._clean_text(raw_input),
                        extracted_quantity=1.0,
                        extracted_unit='unit',
                        reasoning=reasoning
                    )

            # LLM says no match
            reasoning = llm_result.get("reasoning", "No suitable match")
            logger.info(f"   ❌ LLM: {reasoning}")
            return NormalizationResult(
                item=None,
                confidence=0.0,
                matched_on='none',
                alternatives=vector_results[:3],
                original_input=raw_input,
                cleaned_input=self._clean_text(raw_input),
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning=reasoning
            )

        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            # Fallback to vector result
            best_item, best_similarity = vector_results[0]
            return NormalizationResult(
                item=best_item,
                confidence=best_similarity,
                matched_on='vector',
                alternatives=vector_results[1:3],
                original_input=raw_input,
                cleaned_input=self._clean_text(raw_input),
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning=f"LLM failed, fallback to vector ({best_similarity:.2f})"
            )

    # ========================================================================
    # INTELLIGENT UNIT CONVERSION
    # ========================================================================

    async def convert_to_grams_intelligent(
        self,
        quantity: float,
        unit: str,
        item: Item,
        item_count: int = 1,
        original_text: str = ""
    ) -> Tuple[float, str]:
        """
        Intelligent unit conversion - only use LLM when needed

        Flow:
        1. If already grams → return as-is (instant)
        2. If standard units (kg, ml, L) → standard conversion (instant)
        3. If piece/bunch/packet → LLM estimation (expensive)

        Args:
            quantity: Numeric value (e.g., 615, 1, 2)
            unit: Unit string (e.g., 'g', 'kg', 'piece')
            item: Matched Item object
            item_count: Number of items (e.g., 2 for "2 @ $1.00 Each")
            original_text: Raw text for context

        Returns:
            (total_grams, reasoning)
        """
        unit_lower = unit.lower().strip()

        # TIER 1: Already in grams → NO CONVERSION NEEDED
        if unit_lower in ['g', 'gram', 'grams']:
            total_grams = quantity * item_count
            return total_grams, "Already in grams"

        # TIER 2: Standard units → INSTANT CONVERSION
        if unit_lower in ['kg', 'kilogram', 'kilograms']:
            total_grams = quantity * 1000 * item_count
            return total_grams, "Standard kg→g conversion"

        if unit_lower in ['mg', 'milligram', 'milligrams']:
            total_grams = (quantity / 1000) * item_count
            return total_grams, "Standard mg→g conversion"

        # Volume units (assume density = 1.0 unless specified)
        if unit_lower in ['ml', 'milliliter', 'millilitre']:
            density = item.density_g_per_ml or 1.0
            total_grams = quantity * density * item_count
            return total_grams, f"Volume conversion (density={density})"

        if unit_lower in ['l', 'liter', 'litre']:
            density = item.density_g_per_ml or 1.0
            total_grams = quantity * 1000 * density * item_count
            return total_grams, f"Volume conversion (density={density})"

        # TIER 3: Unknown units (piece, bunch, packet) → LLM
        logger.info(f"   🤖 LLM conversion needed for '{unit}' × {item_count}")

        prompt = f"""Convert to grams:
- Item: {item.canonical_name} ({item.category})
- Quantity: {quantity} {unit}
- Item count: {item_count}
- Raw text: "{original_text}"

Common estimates:
- Vegetables: onion=150g, tomato=100g, carrot=60g, celery bunch=200g
- Leafy vegetables: lettuce=200g, cabbage=500g
- Herbs: mint/coriander bunch=20g, chives bunch=30g
- Broccoli: 1 piece/bunch ≈ 300g
- Bell pepper/capsicum: 1 piece ≈ 120g
- Zucchini: 1 piece ≈ 200g
- Eggs: 50g each
- Noodles packet: check original text for weight

Calculate: {quantity} {unit} × {item_count} items = ? grams

JSON output (strict, no markdown): {{"total_grams": <number>, "reasoning": "<brief explanation>"}}
"""

        try:
            client = openai.AsyncOpenAI(api_key=openai.api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            text = response.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)

            total_grams = result['total_grams']
            reasoning = result['reasoning']
            logger.info(f"   ✅ LLM conversion: {total_grams}g ({reasoning})")

            return total_grams, reasoning

        except Exception as e:
            logger.error(f"LLM conversion failed: {e}")
            # Fallback: reasonable estimate
            fallback_grams = 100 * quantity * item_count
            return fallback_grams, f"LLM failed, using fallback estimate (100g per {unit})"

    # ========================================================================
    # BATCH PROCESSING (RECEIPT SCANNER)
    # ========================================================================

    async def normalize_batch(self, receipt_items: List[Dict]) -> List[NormalizationResult]:
        """
        Process entire receipt using RAG pipeline

        Args:
            receipt_items: From receipt scanner
                [{
                    "item_name": "Herb Mint",
                    "quantity": 1,
                    "unit": "piece",
                    "item_count": 1,
                    "raw_text": "HERB MINT 2.80"
                }, ...]

        Returns:
            List of NormalizationResult objects with quantity_grams filled
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 RAG Processing {len(receipt_items)} items")
        logger.info(f"{'='*80}\n")

        results = []

        for idx, item in enumerate(receipt_items, 1):
            item_name = item.get('item_name', '')
            quantity = item.get('quantity', 1.0)
            unit = item.get('unit', 'unit')
            item_count = item.get('item_count', 1)
            raw_text = item.get('raw_text', '')

            logger.info(f"\n[{idx}/{len(receipt_items)}] {item_name} ({quantity}{unit} × {item_count})")

            # Step 1: RAG pipeline for item matching
            result = await self.normalize_single(item_name)

            # Update with receipt data
            result.extracted_quantity = quantity
            result.extracted_unit = unit

            # Step 2: Intelligent unit conversion
            if result.item:
                grams, conversion_note = await self.convert_to_grams_intelligent(
                    quantity=quantity,
                    unit=unit,
                    item=result.item,
                    item_count=item_count,
                    original_text=raw_text
                )
                result.quantity_grams = grams
                result.conversion_note = conversion_note

                logger.info(f"   ✅ {result.item.canonical_name} ({result.confidence:.2f}) "
                          f"→ {result.quantity_grams}g [{result.matched_on}]")
                logger.info(f"      {conversion_note}")
            else:
                logger.info(f"   ❌ No match ({result.confidence:.2f}) - {result.reasoning}")

            results.append(result)

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ Complete: {len(results)} items processed")
        matched = sum(1 for r in results if r.item)
        logger.info(f"   Matched: {matched}/{len(results)} items")
        logger.info(f"{'='*80}\n")

        return results

    # ========================================================================
    # BACKWARD COMPATIBILITY - SYNC WRAPPER
    # ========================================================================

    def normalize(self, raw_input: str) -> NormalizationResult:
        """
        Synchronous wrapper for backward compatibility with old code

        NOTE: This is a BLOCKING method that calls async functions.
        Only use for legacy endpoints. New code should use async methods.

        Args:
            raw_input: e.g., "2kg onions", "5 tomatoes"

        Returns:
            NormalizationResult (blocking until complete)
        """
        import asyncio

        # Run async process_manual_entry in sync context
        try:
            # Create new event loop for this sync call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.process_manual_entry(raw_input))
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Sync normalize failed: {e}")
            import traceback
            traceback.print_exc()
            # Return failed result
            return NormalizationResult(
                item=None,
                confidence=0.0,
                matched_on='none',
                alternatives=[],
                original_input=raw_input,
                cleaned_input=self._clean_text(raw_input),
                extracted_quantity=1.0,
                extracted_unit='unit',
                reasoning=f"Error: {str(e)}"
            )

    # ========================================================================
    # MANUAL ENTRY SUPPORT
    # ========================================================================

    async def process_manual_entry(self, user_text: str) -> NormalizationResult:
        """
        Process manual item entry: "2kg onions", "5 tomatoes", "1 packet rice"

        Flow:
        1. LLM extracts structure: {item_name, quantity, unit}
        2. Use existing RAG pipeline for matching
        3. Use intelligent convert_to_grams for conversion

        Args:
            user_text: Raw user input like "2kg onions" or "5 tomatoes"

        Returns:
            NormalizationResult with matched item and grams
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"📝 Manual Entry: '{user_text}'")
        logger.info(f"{'='*80}\n")

        # Step 1: LLM extracts structure
        structure = await self._extract_structure(user_text)
        logger.info(f"   📊 Extracted: {json.dumps(structure, indent=2)}")

        # Step 2: RAG pipeline for matching
        result = await self.normalize_single(structure['item_name'])

        # Update with extracted data
        result.extracted_quantity = structure['quantity']
        result.extracted_unit = structure['unit']
        result.original_input = user_text

        # Step 3: Intelligent conversion
        if result.item:
            grams, conversion_note = await self.convert_to_grams_intelligent(
                quantity=structure['quantity'],
                unit=structure['unit'],
                item=result.item,
                item_count=1,
                original_text=user_text
            )
            result.quantity_grams = grams
            result.conversion_note = conversion_note

            logger.info(f"   ✅ Final: {result.item.canonical_name} → {grams}g")
        else:
            logger.info(f"   ❌ No match found")

        return result

    async def _extract_structure(self, user_text: str) -> Dict:
        """
        Extract structure from manual entry using LLM

        Args:
            user_text: "2kg onions", "5 tomatoes", "1 packet rice"

        Returns:
            {"item_name": str, "quantity": float, "unit": str}
        """
        prompt = f"""Extract structured data from user input: "{user_text}"

Examples:
- "2kg onions" → {{"item_name": "onions", "quantity": 2, "unit": "kg"}}
- "5 tomatoes" → {{"item_name": "tomatoes", "quantity": 5, "unit": "piece"}}
- "1 packet rice" → {{"item_name": "rice", "quantity": 1, "unit": "packet"}}
- "500g chicken breast" → {{"item_name": "chicken breast", "quantity": 500, "unit": "g"}}

OUTPUT (strict JSON, no markdown):
{{"item_name": "<food item>", "quantity": <number>, "unit": "<unit>"}}
"""

        try:
            client = openai.AsyncOpenAI(api_key=openai.api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            text = response.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            structure = json.loads(text)
            print("structure", structure)

            return structure

        except Exception as e:
            logger.error(f"Structure extraction failed: {e}")
            # Fallback: return raw text as item_name
            return {
                "item_name": user_text,
                "quantity": 1.0,
                "unit": "unit"
            }

    def learn_from_confirmation(self, original_input: str, confirmed_item: Item, was_correct: bool):
        """
        Stub method for compatibility with inventory service.
        RAG normalizer learns implicitly through vector embeddings and doesn't need explicit learning.
        User confirmations are logged but no action is taken.
        """
        if was_correct:
            logger.info(f"✅ User confirmed: '{original_input}' → '{confirmed_item.canonical_name}' (RAG: no explicit learning needed)")
        else:
            logger.info(f"❌ User rejected: '{original_input}' ≠ '{confirmed_item.canonical_name}' (RAG: no explicit learning needed)")
