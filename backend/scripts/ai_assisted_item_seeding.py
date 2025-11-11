"""
AI-Assisted Item Seeding Workflow

This script implements a 5-step intelligent seeding process:
1. Generate candidate items (LLM suggests 500 new items based on ALL existing items)
2. Search FDC for each candidate (get top 3 matches)
3. LLM enrichment (select best match, provide aliases, confidence scores)
4. Generate embeddings and save to JSON for review
5. Import from JSON after manual review

Usage:
    # Step 1-4: Generate seeding data for review
    python ai_assisted_item_seeding.py generate --count 500

    # Step 5: Import after manual review
    python ai_assisted_item_seeding.py import --file backend/data/proposed_items_for_review.json
"""

import asyncio
import json
import sys
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import Item, get_db, SessionLocal
from app.services.fdc_service import FDCService
from app.services.embedding_service import EmbeddingService
from app.core.config import settings
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligentSeeder:
    """
    AI-powered item seeding system that:
    - Uses LLM to suggest common grocery items
    - Searches USDA FDC for nutrition data
    - Uses LLM to select best matches and provide metadata
    - Generates embeddings for semantic search
    - Outputs to JSON for manual review before DB import
    """

    def __init__(self, debug=False):
        self.db = SessionLocal()
        self.fdc_service = FDCService()
        self.embedding_service = EmbeddingService(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        self.existing_items: List[str] = []
        self.existing_categories: List[str] = []
        self.debug = debug  # Enable detailed validation logging

    def close(self):
        """Clean up database connection"""
        self.db.close()

    # ========== STEP 1: Generate Candidate Items ==========

    async def generate_candidate_items(self, target_count: int = 500) -> List[str]:
        """
        Use LLM to suggest common grocery items that don't exist in database yet

        Returns:
            List of canonical names (lowercase_underscore format)
        """
        logger.info("Step 1: Generating candidate items with LLM...")

        # Fetch ALL DISTINCT existing items from database
        existing_items_query = self.db.query(Item.canonical_name).distinct().all()
        self.existing_items = sorted([row.canonical_name for row in existing_items_query])

        # Get existing DISTINCT categories
        categories_query = self.db.query(Item.category).distinct().all()
        self.existing_categories = sorted([row.category for row in categories_query if row.category])

        logger.info(f"Found {len(self.existing_items)} distinct existing items in database")
        logger.info(f"Found {len(self.existing_categories)} distinct categories: {self.existing_categories}")

        if self.debug:
            logger.info(f"Sample existing items (first 20): {self.existing_items[:20]}")

        # Build LLM prompt with ALL existing items
        prompt = f"""You are a nutrition database curator. Your task is to suggest {target_count} common grocery items that are NOT already in our database.

CURRENT DATABASE ({len(self.existing_items)} items):
{json.dumps(self.existing_items, indent=2)}

EXISTING CATEGORIES: {json.dumps(self.existing_categories)}

REQUIREMENTS:
1. Suggest {target_count} NEW items that DON'T exist in the current database
2. Focus on common grocery items people buy regularly (vegetables, fruits, proteins, grains, dairy, etc.)
3. Use canonical naming format: lowercase_underscore (e.g., "sweet_potato", "chicken_thigh", "skim_milk")
4. Cover a diverse range of categories
5. Prioritize items commonly found in grocery stores in India and Western countries
6. Include both raw ingredients AND common packaged items

OUTPUT FORMAT (JSON array of strings):
[
    "celery",
    "herb_mint",
    "japanese_pumpkin",
    "rice_noodles",
    ...
]

Return ONLY the JSON array, no additional text.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # Use latest GPT-4o for best results
                messages=[
                    {"role": "system", "content": "You are a nutrition database expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Some creativity for diverse suggestions
                max_tokens=4000
            )

            # Parse LLM response
            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            suggested_items = json.loads(content)

            if not isinstance(suggested_items, list):
                raise ValueError("LLM response is not a list")

            # Validate: Remove any items that already exist (safety check)
            new_suggestions = []
            existing_normalized = {item.lower().replace(' ', '_') for item in self.existing_items}

            for item in suggested_items:
                normalized = item.lower().replace(' ', '_')
                if normalized not in existing_normalized:
                    new_suggestions.append(normalized)
                else:
                    logger.warning(f"Skipping duplicate suggestion: {normalized}")

            logger.info(f"Generated {len(new_suggestions)} unique candidate items")
            logger.info(f"Sample candidates: {new_suggestions[:10]}")

            return new_suggestions[:target_count]  # Trim to target count

        except Exception as e:
            logger.error(f"Error generating candidates with LLM: {e}")
            raise

    # ========== STEP 2: Search FDC for Candidates ==========

    async def fetch_fdc_options_for_candidates(
        self,
        candidates: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        For each candidate, search FDC and get top 3 matches

        Returns:
            Dict mapping canonical_name -> [fdc_option1, fdc_option2, fdc_option3]
        """
        logger.info(f"Step 2: Searching FDC for {len(candidates)} candidates...")

        fdc_results = {}

        for idx, candidate in enumerate(candidates):
            try:
                # Search FDC with clean name (replace underscores with spaces)
                search_query = candidate.replace('_', ' ')
                logger.info(f"[{idx+1}/{len(candidates)}] Searching FDC for: {search_query}")

                fdc_matches = await self.fdc_service.search_food(search_query)

                # Take top 3 matches
                top_3 = fdc_matches[:3] if fdc_matches else []

                fdc_results[candidate] = top_3

                logger.info(f"  → Found {len(top_3)} FDC matches")

                # Debug: Show FDC match details and save raw data
                if self.debug and top_3:
                    for i, match in enumerate(top_3):
                        logger.info(f"      [{i}] {match.get('description', 'N/A')} (fdcId: {match.get('fdcId', 'N/A')})")

                    # Save complete FDC response to file for inspection
                    debug_file = f"backend/data/debug_fdc_{candidate}.json"
                    os.makedirs("backend/data", exist_ok=True)
                    with open(debug_file, 'w') as f:
                        json.dump(top_3, f, indent=2)
                    logger.info(f"      💾 Saved raw FDC data to: {debug_file}")

                # Small delay to avoid rate limiting
                if idx % 10 == 0 and idx > 0:
                    logger.info(f"Processed {idx}/{len(candidates)}, taking short break...")
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error searching FDC for {candidate}: {e}")
                fdc_results[candidate] = []

        logger.info(f"FDC search complete: {len(fdc_results)} candidates processed")

        return fdc_results

    # ========== STEP 3: LLM Enrichment ==========

    async def enrich_candidates_with_llm(
        self,
        fdc_results: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Use LLM to:
        1. Select best FDC match for each candidate
        2. Provide canonical name, aliases, category
        3. Assign confidence score

        Processes in batches of 20 for token efficiency

        Returns:
            List of enriched item dicts ready for embedding generation
        """
        logger.info("Step 3: Enriching candidates with LLM...")

        # Filter candidates that have at least 1 FDC match
        candidates_with_matches = {
            name: matches
            for name, matches in fdc_results.items()
            if matches
        }

        logger.info(f"Processing {len(candidates_with_matches)} candidates with FDC matches")

        enriched_items = []
        batch_size = 20  # Process 20 items at a time for token efficiency

        candidate_names = list(candidates_with_matches.keys())

        for batch_idx in range(0, len(candidate_names), batch_size):
            batch = candidate_names[batch_idx:batch_idx + batch_size]

            logger.info(f"Processing batch {batch_idx//batch_size + 1}/{(len(candidate_names) + batch_size - 1)//batch_size}")

            # Build batch prompt
            batch_data = {}
            for candidate in batch:
                # Include essential fields + PARSED NUTRITION for LLM to evaluate match quality
                simplified_matches = []
                for match in candidates_with_matches[candidate]:
                    # Parse nutrition from this match
                    parsed_nutrition = self.fdc_service._parse_fdc_nutrients(match)

                    simplified_matches.append({
                        "description": match.get("description", ""),
                        "fdcId": match.get("fdcId", ""),
                        "dataType": match.get("dataType", ""),
                        "nutrition": parsed_nutrition,  # Include parsed nutrition
                    })
                batch_data[candidate] = simplified_matches

            # Debug: Save what we're sending to LLM
            if self.debug:
                debug_file = f"backend/data/debug_llm_input_batch_{batch_idx//batch_size + 1}.json"
                os.makedirs("backend/data", exist_ok=True)
                with open(debug_file, 'w') as f:
                    json.dump(batch_data, f, indent=2)
                logger.info(f"💾 Saved LLM input data to: {debug_file}")

            prompt = f"""You are a nutrition database curator. For each item, review the USDA FDC matches and select the one with the MOST ACCURATE nutrition data.

BATCH DATA:
{json.dumps(batch_data, indent=2)}

IMPORTANT: Each match includes "nutrition" with parsed values (calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg).

YOUR TASK:
Use your knowledge of food nutrition to evaluate which match has the most REALISTIC and COMPLETE nutrition profile for that specific food.

Examples of what to check:
- Does celery have fiber? (Yes, ~1.6g per 100g) → If a match shows fiber_g: 0, that's likely INCOMPLETE data
- Does chicken breast have carbs? (No/minimal) → If showing high carbs, that's wrong
- Do vegetables have fiber? (Usually yes) → Prefer matches where fiber_g > 0
- Do oils have protein/carbs? (No) → It's normal for these to be 0

SELECT THE MATCH WHERE:
1. The nutrition values make sense for that type of food (use your knowledge)
2. The description best matches the item (prefer "raw" over processed)
3. The data appears complete (not missing expected nutrients)

FOR EACH ITEM OUTPUT:
1. **best_fdc_index**: Index (0-2) of match with most accurate/complete nutrition
2. **canonical_name**: lowercase_underscore format
3. **display_name**: Proper capitalized name
4. **category**: proteins, grains, vegetables, fruits, dairy, oils, legumes, nuts_seeds, spices, beverages, snacks, other
5. **aliases**: 3-5 common alternative names
6. **confidence**: 0.0-1.0 (consider both description match AND nutrition accuracy)
   - 0.95-1.0: Perfect description + nutrition makes sense
   - 0.80-0.94: Good match, minor issues
   - 0.60-0.79: Acceptable but some concerns
   - <0.60: Poor (return -1 for best_fdc_index)

OUTPUT (JSON only, no additional text):
{{
    "item_name": {{
        "best_fdc_index": 1,
        "canonical_name": "celery",
        "display_name": "Celery",
        "category": "vegetables",
        "aliases": ["celery stalk", "celery stick", "celery rib"],
        "confidence": 0.95
    }}
}}
"""

            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-2024-08-06",
                    messages=[
                        {"role": "system", "content": "You are a nutrition database expert. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,  # Lower temperature for consistent categorization
                    max_tokens=4000
                )

                # Parse LLM response
                content = response.choices[0].message.content.strip()

                # Remove markdown code blocks if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                batch_enrichment = json.loads(content)

                # Process each enriched item
                for candidate, enrichment in batch_enrichment.items():
                    best_fdc_index = enrichment.get("best_fdc_index", -1)

                    if best_fdc_index == -1:
                        logger.warning(f"Skipping {candidate}: No suitable FDC match (confidence too low)")
                        continue

                    # Get the selected FDC match
                    fdc_match = candidates_with_matches[candidate][best_fdc_index]

                    # DEBUG: Check if foodNutrients is present
                    if self.debug:
                        has_nutrients = 'foodNutrients' in fdc_match
                        nutrient_count = len(fdc_match.get('foodNutrients', [])) if has_nutrients else 0
                        logger.info(f"      FDC match has foodNutrients: {has_nutrients}, count: {nutrient_count}")

                    # Parse nutrition from FDC match
                    nutrition = self.fdc_service._parse_fdc_nutrients(fdc_match)

                    # DEBUG: Check parsed result
                    if self.debug:
                        logger.info(f"      Parsed nutrition: calories={nutrition['calories']}, protein={nutrition['protein_g']}g")

                    # Build enriched item
                    enriched_item = {
                        "canonical_name": enrichment["canonical_name"],
                        "display_name": enrichment.get("display_name", enrichment["canonical_name"].replace('_', ' ').title()),
                        "category": enrichment["category"],
                        "aliases": enrichment.get("aliases", []),
                        "nutrition_per_100g": nutrition,
                        "fdc_id": str(fdc_match.get("fdcId", "")),
                        "source": "usda_fdc",
                        "confidence": enrichment["confidence"],
                        "fdc_description": fdc_match.get("description", ""),
                    }

                    enriched_items.append(enriched_item)
                    logger.info(f"  ✓ {enriched_item['canonical_name']} (confidence: {enriched_item['confidence']:.2f})")

                # Small delay between batches
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error enriching batch {batch_idx//batch_size + 1}: {e}")
                continue

        logger.info(f"Enrichment complete: {len(enriched_items)} items enriched")

        return enriched_items

    # ========== STEP 4: Generate Embeddings and Save JSON ==========

    async def create_review_json(
        self,
        enriched_items: List[Dict],
        output_path: str = "backend/data/proposed_items_for_review.json"
    ):
        """
        Generate embeddings for all items and save to JSON for manual review
        """
        logger.info("Step 4: Generating embeddings and creating review JSON...")

        # Generate embedding text for each item
        embedding_texts = []
        for item in enriched_items:
            # Combine canonical name, display name, category, and aliases for rich embedding
            text_parts = [
                item["canonical_name"],
                item["display_name"],
                item["category"],
            ]
            text_parts.extend(item.get("aliases", []))

            embedding_text = " ".join(text_parts)
            embedding_texts.append(embedding_text)

        logger.info(f"Generating embeddings for {len(embedding_texts)} items...")

        # Generate embeddings in batch (efficient)
        embeddings = await self.embedding_service.get_embeddings_batch(
            embedding_texts,
            batch_size=100
        )

        # Add embeddings to items
        for idx, item in enumerate(enriched_items):
            item["embedding"] = embeddings[idx]
            item["embedding_model"] = "text-embedding-3-small"
            item["embedding_version"] = 1

        # Create output structure
        output_data = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "total_items": len(enriched_items),
                "openai_model": "gpt-4o-2024-08-06",
                "embedding_model": "text-embedding-3-small",
                "existing_items_count": len(self.existing_items),
            },
            "items": enriched_items
        }

        # Save to JSON
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Review JSON saved to: {output_path}")
        logger.info(f"Total items: {len(enriched_items)}")
        logger.info(f"Average confidence: {sum(item['confidence'] for item in enriched_items) / len(enriched_items):.2f}")

        # Print statistics
        high_confidence = sum(1 for item in enriched_items if item['confidence'] >= 0.90)
        medium_confidence = sum(1 for item in enriched_items if 0.70 <= item['confidence'] < 0.90)
        low_confidence = sum(1 for item in enriched_items if item['confidence'] < 0.70)

        logger.info(f"Confidence breakdown:")
        logger.info(f"  High (≥0.90): {high_confidence} items")
        logger.info(f"  Medium (0.70-0.89): {medium_confidence} items")
        logger.info(f"  Low (<0.70): {low_confidence} items")

    # ========== STEP 5: Import from Reviewed JSON ==========

    def import_from_reviewed_json(self, json_path: str, min_confidence: float = 0.70):
        """
        Import items from manually reviewed JSON file into database

        Args:
            json_path: Path to reviewed JSON file
            min_confidence: Minimum confidence threshold (default: 0.70)
        """
        logger.info(f"Step 5: Importing items from {json_path}...")

        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        items_to_import = data["items"]
        logger.info(f"Found {len(items_to_import)} items in JSON")

        # Filter by confidence
        items_to_import = [
            item for item in items_to_import
            if item["confidence"] >= min_confidence
        ]
        logger.info(f"Importing {len(items_to_import)} items with confidence ≥ {min_confidence}")

        # Check for duplicates
        existing_canonical_names = {
            row.canonical_name
            for row in self.db.query(Item.canonical_name).all()
        }

        imported_count = 0
        skipped_count = 0

        for item_data in items_to_import:
            canonical_name = item_data["canonical_name"]

            # Skip if already exists
            if canonical_name in existing_canonical_names:
                logger.warning(f"Skipping duplicate: {canonical_name}")
                skipped_count += 1
                continue

            # Convert embedding list to JSON string for database storage
            embedding_json = self.embedding_service.embedding_to_db_string(
                item_data["embedding"]
            )

            # Create Item instance
            item = Item(
                canonical_name=canonical_name,
                aliases=item_data.get("aliases", []),
                category=item_data["category"],
                unit="g",  # Default to grams
                fdc_id=item_data.get("fdc_id"),
                nutrition_per_100g=item_data["nutrition_per_100g"],
                is_staple=False,  # Can be updated manually later
                embedding=embedding_json,
                embedding_model=item_data.get("embedding_model", "text-embedding-3-small"),
                embedding_version=item_data.get("embedding_version", 1),
                source=item_data.get("source", "usda_fdc")
            )

            self.db.add(item)
            imported_count += 1

            if imported_count % 50 == 0:
                logger.info(f"Progress: {imported_count} items imported...")

        # Commit all changes
        try:
            self.db.commit()
            logger.info(f"✅ Successfully imported {imported_count} items")
            logger.info(f"Skipped {skipped_count} duplicates")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during import: {e}")
            raise

    # ========== Main Workflow ==========

    async def run_full_workflow(self, target_count: int = 500):
        """
        Execute complete workflow: Steps 1-4

        This generates the review JSON but does NOT import to database.
        After manual review, run import_from_reviewed_json() separately.
        """
        logger.info("="*80)
        logger.info("AI-ASSISTED ITEM SEEDING WORKFLOW")
        logger.info("="*80)

        try:
            # Step 1: Generate candidates
            candidates = await self.generate_candidate_items(target_count)

            if not candidates:
                logger.error("No candidates generated. Exiting.")
                return

            # Step 2: Search FDC
            fdc_results = await self.fetch_fdc_options_for_candidates(candidates)

            # Step 3: LLM enrichment
            enriched_items = await self.enrich_candidates_with_llm(fdc_results)

            if not enriched_items:
                logger.error("No items enriched. Exiting.")
                return

            # Step 4: Generate embeddings and save JSON
            await self.create_review_json(enriched_items)

            logger.info("="*80)
            logger.info("✅ WORKFLOW COMPLETE")
            logger.info("="*80)
            logger.info("")
            logger.info("NEXT STEPS:")
            logger.info("1. Review the file: backend/data/proposed_items_for_review.json")
            logger.info("2. Remove any items you don't want to import")
            logger.info("3. Run import command:")
            logger.info("   python ai_assisted_item_seeding.py import --file backend/data/proposed_items_for_review.json")

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            raise
        finally:
            self.close()


# ========== CLI Interface ==========

async def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(description="AI-Assisted Item Seeding")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate seeding data for review')
    generate_parser.add_argument('--count', type=int, default=500, help='Number of items to generate (default: 500)')
    generate_parser.add_argument('--debug', action='store_true', help='Enable detailed debug logging')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import from reviewed JSON')
    import_parser.add_argument('--file', type=str, required=True, help='Path to reviewed JSON file')
    import_parser.add_argument('--min-confidence', type=float, default=0.70, help='Minimum confidence threshold (default: 0.70)')

    args = parser.parse_args()

    if args.command == 'generate':
        seeder = IntelligentSeeder(debug=args.debug if hasattr(args, 'debug') else False)
        await seeder.run_full_workflow(target_count=args.count)

    elif args.command == 'import':
        seeder = IntelligentSeeder()
        try:
            seeder.import_from_reviewed_json(args.file, min_confidence=args.min_confidence)
        finally:
            seeder.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
