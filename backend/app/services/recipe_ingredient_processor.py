"""
Recipe Ingredient Processor
===========================

Matches recipe ingredients to items database and auto-seeds missing ones.

Follows EXACT pattern from backend/scripts/ai_assisted_item_seeding.py:
1. Search FDC (sync)
2. Parse nutrition for each match
3. LLM selects best match (WITH parsed nutrition)
4. Generate embedding
5. Create Item
"""

import logging
import json
from typing import List, Dict, Optional, Tuple
from sqlalchemy import text, cast, String, func
from sqlalchemy.orm import Session
from openai import OpenAI

from app.models.database import Item
from app.services.fdc_service import FDCService
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)


class RecipeIngredientProcessor:
    """
    Match recipe ingredients to items table, auto-seed missing ones

    Flow (exact pattern from ai_assisted_item_seeding.py):
    1. Try exact match (canonical_name)
    2. Try alias match
    3. Try vector similarity search (>0.90)
    4. If not found → Auto-seed from FDC
    """

    def __init__(self, db: Session):
        self.db = db
        self.fdc_service = FDCService()
        self.embedder = EmbeddingService(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )
        self.openai_client = OpenAI(api_key=settings.openai_api_key)

    async def process_recipe_ingredients(
        self,
        recipe_ingredients: List[Dict]
    ) -> List[Dict]:
        """
        For each ingredient:
        1. Try to find in items table
        2. If not found, auto-seed using FDC + LLM
        3. Return matched items with item_ids

        Args:
            recipe_ingredients: List of dicts from RecipeStructured.ingredients
                [
                    {
                        "food_name": "chicken_breast",
                        "quantity_grams": 500,
                        "preparation": "grilled"
                    },
                    ...
                ]

        Returns:
            [
                {
                    "food_name": "chicken_breast",
                    "quantity_grams": 500,
                    "preparation": "grilled",
                    "item_id": 123,  # From items table
                    "nutrition_per_100g": {...},
                    "confidence": 0.95,
                    "was_created": False,
                    "match_method": "exact" | "alias" | "vector" | "created"
                },
                ...
            ]
        """

        matched_ingredients = []

        for ing_dict in recipe_ingredients:
            food_name = ing_dict.get('food_name')
            quantity_grams = ing_dict.get('quantity_grams')
            preparation = ing_dict.get('preparation')

            logger.info(f"Processing ingredient: {food_name} ({quantity_grams}g)")

            # Step 1: Try to find existing item
            existing_item, match_method = await self._find_existing_item(food_name)

            if existing_item:
                # Found! Use existing item
                matched_ingredients.append({
                    "food_name": food_name,
                    "quantity_grams": quantity_grams,
                    "preparation": preparation,
                    "item_id": existing_item.id,
                    "nutrition_per_100g": existing_item.nutrition_per_100g,
                    "confidence": 1.0 if match_method in ['exact', 'alias'] else 0.95,
                    "was_created": False,
                    "match_method": match_method
                })
                logger.info(f"  ✓ Found existing: {existing_item.canonical_name} (id={existing_item.id}, method={match_method})")

            else:
                # Not found - auto-seed it!
                logger.warning(f"  ⚠ Missing ingredient: {food_name} - auto-seeding...")

                try:
                    new_item = await self._auto_seed_ingredient(food_name)

                    matched_ingredients.append({
                        "food_name": food_name,
                        "quantity_grams": quantity_grams,
                        "preparation": preparation,
                        "item_id": new_item.id,
                        "nutrition_per_100g": new_item.nutrition_per_100g,
                        "confidence": getattr(new_item, 'confidence', 0.85),
                        "was_created": True,
                        "match_method": "created"
                    })
                    logger.info(f"  ✓ Auto-seeded: {new_item.canonical_name} (id={new_item.id})")

                except Exception as e:
                    # Skip ingredient if auto-seeding fails (same behavior as item seeder)
                    logger.warning(f"  ⚠ Skipping {food_name}: Could not auto-seed ({e})")
                    continue  # Don't fail entire recipe for one bad ingredient

        logger.info(f"Processed {len(matched_ingredients)} ingredients successfully")

        return matched_ingredients

    async def _find_existing_item(self, food_name: str) -> Tuple[Optional[Item], Optional[str]]:
        """
        Search items table using multiple methods

        Returns: (Item or None, match_method or None)
        """

        normalized_name = food_name.lower().replace(' ', '_')

        # Method 1: Exact canonical_name match (case-insensitive)
        exact = self.db.query(Item).filter(
            func.lower(Item.canonical_name) == normalized_name
        ).first()

        if exact:
            return exact, "exact"

        # Method 2: Alias match (same pattern as Recipe.goals query in codebase)
        alias_match = self.db.query(Item).filter(
            cast(Item.aliases, String).contains(normalized_name)
        ).first()

        if alias_match:
            return alias_match, "alias"

        # Method 3: Vector similarity search
        try:
            embedding = await self.embedder.get_embedding(food_name)
            embedding_str = self.embedder.embedding_to_db_string(embedding)

            # Note: Space before ::vector is required for SQLAlchemy parameter binding
            # See: https://github.com/sqlalchemy/sqlalchemy/issues/3644
            result = self.db.execute(text("""
                SELECT id, canonical_name,
                       1 - (embedding::vector(1536) <=> :embedding ::vector(1536)) as similarity
                FROM items
                WHERE embedding IS NOT NULL
                ORDER BY embedding::vector(1536) <=> :embedding ::vector(1536)
                LIMIT 1
            """), {"embedding": embedding_str}).mappings().fetchone()

            if result and result['similarity'] > 0.90:
                item = self.db.query(Item).get(result['id'])
                logger.info(f"  Vector match: {result['canonical_name']} (similarity={result['similarity']:.2f})")
                return item, "vector"

        except Exception as e:
            logger.warning(f"Vector search failed for {food_name}: {e}")

        return None, None

    async def _auto_seed_ingredient(self, food_name: str) -> Item:
        """
        Auto-seed missing ingredient - EXACT pattern from ai_assisted_item_seeding.py

        Pattern (lines 261-369):
        1. Search FDC (SYNC call)
        2. Parse nutrition for each match BEFORE sending to LLM
        3. LLM selects best match (WITH parsed nutrition)
        4. Generate embedding
        5. Create Item
        """

        # Step 1: Search FDC (async)
        search_query = food_name.replace('_', ' ')
        logger.info(f"    Searching FDC for: {search_query}")

        fdc_matches = await self.fdc_service.search_food(search_query)

        if not fdc_matches:
            raise ValueError(f"No FDC matches found for: {food_name}")

        # Take top 3 matches
        top_3 = fdc_matches[:3]
        logger.info(f"    Found {len(top_3)} FDC matches")

        # Step 2: Parse nutrition for each match (BEFORE LLM!)
        # This is the critical pattern from ai_assisted_item_seeding.py line 263-272
        simplified_matches = []
        for match in top_3:
            parsed_nutrition = self.fdc_service._parse_fdc_nutrients(match)

            simplified_matches.append({
                "description": match.get("description", ""),
                "fdcId": match.get("fdcId", ""),
                "dataType": match.get("dataType", ""),
                "nutrition": parsed_nutrition,  # LLM needs this to evaluate quality!
            })

        # Step 3: LLM selects best match (with nutrition data)
        enrichment = await self._llm_select_best_fdc_match(food_name, simplified_matches)

        if enrichment['best_fdc_index'] == -1:
            raise ValueError(f"LLM couldn't find good match for: {food_name}")

        # Get the selected FDC match
        best_match = top_3[enrichment['best_fdc_index']]

        # Step 4: Parse nutrition from selected match
        nutrition = self.fdc_service._parse_fdc_nutrients(best_match)

        # Step 5: Generate embedding
        embedding_text = f"{food_name} {enrichment['category']}"
        embedding = await self.embedder.get_embedding(embedding_text)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        # Step 6: Create Item (exact pattern from ai_assisted_item_seeding.py line 523-535)
        new_item = Item(
            canonical_name=food_name,
            aliases=enrichment.get('aliases', []),
            category=enrichment['category'],
            unit="g",
            fdc_id=str(best_match.get('fdcId', '')),
            nutrition_per_100g=nutrition,
            is_staple=False,
            embedding=embedding_str,
            embedding_model="text-embedding-3-small",
            embedding_version=1,
            source="usda_fdc"
        )

        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)

        logger.info(f"    Created new item: {new_item.canonical_name} (id={new_item.id})")

        return new_item

    async def _llm_select_best_fdc_match(
        self,
        food_name: str,
        simplified_matches: List[Dict]
    ) -> Dict:
        """
        LLM selects best FDC match - EXACT pattern from ai_assisted_item_seeding.py lines 283-327

        Critical: simplified_matches already has parsed nutrition!
        """

        # Pattern from ai_assisted_item_seeding.py - professional, concise
        prompt = f"""Select the best FDC match for: "{food_name}"

FDC OPTIONS (with parsed nutrition):
{json.dumps(simplified_matches, indent=2)}

Evaluate which match has the most REALISTIC and COMPLETE nutrition profile.

Examples:
- Vegetables should have fiber (>0)
- Chicken breast should have minimal carbs
- Oils should have 0 protein/carbs

SELECT WHERE:
1. Nutrition values make sense for this food
2. Description best matches (prefer "raw" over processed)
3. Data appears complete

Return JSON only:
{{
    "best_fdc_index": 0,
    "canonical_name": "{food_name}",
    "category": "proteins|vegetables|grains|oils|fruits|dairy|legumes|nuts_seeds|spices|beverages|other",
    "aliases": ["alias1", "alias2"],
    "confidence": 0.95
}}

If no suitable match (confidence <0.6), set best_fdc_index to -1.
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",  # Same as item seeder
            messages=[
                {"role": "system", "content": "You are a nutrition database expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        content = response.choices[0].message.content.strip()

        # Clean markdown if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content)


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def test_processor():
    """Test the ingredient processor"""
    from app.models.database import SessionLocal

    db = SessionLocal()
    processor = RecipeIngredientProcessor(db)

    # Test ingredients from a recipe
    test_ingredients = [
        {
            "food_name": "chicken_breast",
            "quantity_grams": 500,
            "preparation": "grilled"
        },
        {
            "food_name": "olive_oil",
            "quantity_grams": 15,
            "preparation": None
        },
        {
            "food_name": "quinoa",  # Might not exist in DB
            "quantity_grams": 80,
            "preparation": None
        }
    ]

    print("\n" + "="*80)
    print("TESTING RECIPE INGREDIENT PROCESSOR")
    print("="*80)

    try:
        matched = await processor.process_recipe_ingredients(test_ingredients)

        print(f"\n✓ Successfully processed {len(matched)} ingredients\n")

        for ing in matched:
            status = "🆕 CREATED" if ing['was_created'] else f"✓ FOUND ({ing['match_method']})"
            print(f"{status}: {ing['food_name']}")
            print(f"  Item ID: {ing['item_id']}")
            print(f"  Quantity: {ing['quantity_grams']}g")
            print(f"  Confidence: {ing['confidence']:.2f}")
            print(f"  Nutrition (per 100g): {ing['nutrition_per_100g']['calories']} cal, "
                  f"{ing['nutrition_per_100g']['protein_g']}g protein")
            print()

    finally:
        processor.close()
        db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_processor())
