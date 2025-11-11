"""
Enrich Existing Items Script
=============================

This script takes existing manual items and enriches them using the EXACT same
flow as ai_assisted_item_seeding.py (Steps 2-4):
- FDC Search
- LLM Enrichment
- Embedding Generation
- Save to JSON for review

Usage:
    python scripts/enrich_existing_items.py
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_assisted_item_seeding import IntelligentSeeder
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """
    Read cleaned list of canonical names and process through enrichment pipeline
    """
    logger.info("="*80)
    logger.info("ENRICH EXISTING ITEMS WORKFLOW")
    logger.info("="*80)

    # Read cleaned canonical names
    cleaned_file = "data/items_to_enrich_cleaned.txt"

    if not os.path.exists(cleaned_file):
        logger.error(f"File not found: {cleaned_file}")
        logger.error("Please create this file with one canonical_name per line")
        return

    with open(cleaned_file, 'r') as f:
        candidates = [line.strip() for line in f if line.strip()]

    logger.info(f"Found {len(candidates)} items to enrich")
    logger.info(f"Sample items: {candidates[:10]}")

    # Initialize seeder
    seeder = IntelligentSeeder(debug=False)

    try:
        # Step 2: Search FDC (reuse existing method)
        logger.info("\nStep 2: Searching USDA FDC for nutrition data...")
        fdc_results = await seeder.fetch_fdc_options_for_candidates(candidates)

        # Step 3: LLM enrichment (reuse existing method)
        logger.info("\nStep 3: Using LLM to select best matches...")
        enriched_items = await seeder.enrich_candidates_with_llm(fdc_results)

        if not enriched_items:
            logger.error("No items enriched. Exiting.")
            return

        # Step 4: Generate embeddings and save JSON
        logger.info("\nStep 4: Generating embeddings and saving JSON...")
        await seeder.create_review_json(
            enriched_items,
            output_path="backend/data/items_to_enrich_final.json"
        )

        logger.info("="*80)
        logger.info("✅ ENRICHMENT COMPLETE")
        logger.info("="*80)
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("1. Review: backend/data/items_to_enrich_final.json")
        logger.info("2. Delete duplicates from database:")
        logger.info("   See backend/data/items_to_delete.sql")
        logger.info("3. Import enriched items:")
        logger.info("   python scripts/ai_assisted_item_seeding.py import --file backend/data/items_to_enrich_final.json")

        # Generate SQL to delete old items
        delete_sql = "-- SQL to delete old duplicate items\n\n"
        delete_sql += "DELETE FROM items WHERE id IN (\n"

        # We'll delete all the duplicates we found (keeping the enriched ones)
        # This will be based on the IDs from the original query you provided
        delete_sql += "  -- Add IDs of items to delete here after review\n"
        delete_sql += "  -- Example: 1, 2, 3, 4, 5\n"
        delete_sql += ");\n"

        with open("backend/data/items_to_delete.sql", 'w') as f:
            f.write(delete_sql)

        logger.info("\nGenerated SQL template: backend/data/items_to_delete.sql")

    except Exception as e:
        logger.error(f"Enrichment failed: {e}", exc_info=True)
        raise
    finally:
        seeder.close()


if __name__ == "__main__":
    asyncio.run(main())
