"""
Test AI-Assisted Seeding Workflow

This script runs a small test (10 items by default) to verify everything works.
Enables debug mode for detailed validation.

Usage:
    python scripts/test_seeding_workflow.py
    python scripts/test_seeding_workflow.py --count 15
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.ai_assisted_item_seeding import IntelligentSeeder


async def test_workflow(count=10):
    """Test workflow with debug logging enabled"""
    print("="*80)
    print(f"TESTING AI-ASSISTED SEEDING WORKFLOW ({count} items)")
    print("="*80)
    print()

    # Initialize seeder with DEBUG mode enabled
    seeder = IntelligentSeeder(debug=True)

    try:
        # Step 1: Generate candidates
        print("Step 1: Testing candidate generation...")
        candidates = await seeder.generate_candidate_items(target_count=count)

        if not candidates:
            print("❌ FAILED: No candidates generated")
            return

        print(f"✅ Generated {len(candidates)} candidates:")
        for idx, candidate in enumerate(candidates, 1):
            print(f"   {idx}. {candidate}")
        print()

        # Step 2: FDC search
        print("Step 2: Testing FDC search...")
        fdc_results = await seeder.fetch_fdc_options_for_candidates(candidates)

        matches_found = sum(1 for matches in fdc_results.values() if matches)
        print(f"✅ Found FDC matches for {matches_found}/{len(candidates)} candidates")
        print()

        # Step 3: LLM enrichment
        print("Step 3: Testing LLM enrichment...")
        enriched_items = await seeder.enrich_candidates_with_llm(fdc_results)

        if not enriched_items:
            print("⚠️  WARNING: No items enriched (all skipped)")
            print("Check FDC results above to see what was returned")
            return

        print(f"✅ Enriched {len(enriched_items)} items:")
        for item in enriched_items:
            print(f"   • {item['canonical_name']} (confidence: {item['confidence']:.2f})")
        print()

        # Step 4: Save test output
        print("Step 4: Testing JSON generation...")
        output_path = "backend/data/test_proposed_items.json"
        await seeder.create_review_json(enriched_items, output_path=output_path)

        print(f"✅ Test JSON saved to: {output_path}")
        print()

        print("="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print()
        print("Next steps:")
        print(f"1. Review test output: {output_path}")
        print("2. Check for:")
        print("   - Zero hallucinations (LLM didn't suggest duplicates)")
        print("   - FDC matches are relevant")
        print("   - Skip reasons make sense")
        print("3. If everything looks good, run full workflow:")
        print("   python scripts/ai_assisted_item_seeding.py generate --count 500")

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        seeder.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test AI-Assisted Item Seeding")
    parser.add_argument('--count', type=int, default=10, help='Number of items to test (default: 10)')

    args = parser.parse_args()

    asyncio.run(test_workflow(count=args.count))
