"""
LLM Recipe Generation Pipeline
===============================

Complete end-to-end recipe generation flow:
1. Generate recipe with LLM (structured outputs)
2. Validate nutrition is reasonable
3. Match/auto-seed ingredients
4. Store in database (recipes + recipe_ingredients)

Reuses:
- StructuredRecipeGenerator (LLM generation + deduplication)
- RecipeIngredientProcessor (ingredient matching + auto-seeding)
- EmbeddingService (vector embeddings for deduplication)
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.database import Recipe, RecipeIngredient
from app.services.llm_recipe_generator import StructuredRecipeGenerator, RecipeStructured
from app.services.recipe_ingredient_processor import RecipeIngredientProcessor
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMRecipeGenerationPipeline:
    """
    Complete recipe generation pipeline

    Flow:
    1. Generate recipe with LLM (with deduplication)
    2. Validate nutrition is reasonable
    3. Match/auto-seed ingredients
    4. Create Recipe + RecipeIngredient records
    """

    def __init__(self, db: Session):
        self.db = db
        self.generator = StructuredRecipeGenerator(db=db)
        self.processor = RecipeIngredientProcessor(db)
        self.embedder = EmbeddingService(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )

    async def generate_validated_recipe(
        self,
        goal_type: str,
        target_macros: Dict[str, float],
        cuisine: str = "mediterranean",
        dietary_restrictions: List[str] = None
    ) -> Dict:
        """
        Generate complete recipe with all database records

        Args:
            goal_type: muscle_gain, fat_loss, body_recomp, endurance, weight_training
            target_macros: {'calories': 1000, 'protein': 75, 'carbs': 115, 'fat': 30}
            cuisine: mediterranean, italian, indian, mexican, asian, american, etc.
            dietary_restrictions: ['vegetarian', 'vegan', 'high-protein', 'low-carb', 'gluten-free', 'dairy-free']

        Returns:
        {
            'recipe': Recipe object,
            'recipe_ingredients': [RecipeIngredient objects],
            'ingredients_created': 2,  # Number of auto-seeded items
            'ingredients_matched': 3   # Number of existing items used
        }
        """

        dietary_restrictions = dietary_restrictions or []

        logger.info(f"\n{'='*80}")
        logger.info(f"RECIPE GENERATION")
        logger.info(f"{'='*80}")
        logger.info(f"Goal: {goal_type}")
        logger.info(f"Target: {target_macros['calories']:.0f} cal, "
                   f"{target_macros['protein']:.1f}g protein, "
                   f"{target_macros['carbs']:.1f}g carbs, "
                   f"{target_macros['fat']:.1f}g fat")
        logger.info(f"Cuisine: {cuisine}")

        # Step 1: Generate recipe with LLM (includes deduplication)
        logger.info("\nStep 1: Generating recipe with LLM...")
        recipe_struct = await self.generator.generate_recipe(
            goal_type=goal_type,
            target_calories=target_macros['calories'],
            target_protein=target_macros['protein'],
            target_carbs=target_macros['carbs'],
            target_fat=target_macros['fat'],
            cuisine=cuisine,
            dietary_restrictions=dietary_restrictions,
            check_duplicates=True,
            max_retries=3
        )

        logger.info(f"✓ Generated: {recipe_struct.name}")
        logger.info(f"  LLM Nutrition: {recipe_struct.calories:.0f} cal, "
                   f"{recipe_struct.protein_g:.1f}g protein, "
                   f"{recipe_struct.carbs_g:.1f}g carbs, "
                   f"{recipe_struct.fat_g:.1f}g fat")
        logger.info(f"  Ingredients: {len(recipe_struct.ingredients)}")

        # Step 2: Process ingredients (match + auto-seed)
        logger.info("\nStep 2: Processing ingredients...")

        # Convert Pydantic models to dicts
        ingredients_as_dicts = [
            {
                "food_name": ing.food_name,
                "quantity_grams": ing.quantity_grams,
                "preparation": ing.preparation
            }
            for ing in recipe_struct.ingredients
        ]

        matched_ingredients = await self.processor.process_recipe_ingredients(
            ingredients_as_dicts
        )

        ingredients_created = sum(1 for ing in matched_ingredients if ing['was_created'])
        ingredients_matched = len(matched_ingredients) - ingredients_created

        logger.info(f"✓ Processed {len(matched_ingredients)} ingredients:")
        logger.info(f"  - {ingredients_matched} matched to existing items")
        logger.info(f"  - {ingredients_created} auto-seeded from FDC")

        # Step 3: Create database records (with transaction)
        logger.info("\nStep 3: Creating database records...")

        try:
            # Create recipe record (no commit yet)
            recipe_record = await self._create_recipe_record(
                recipe_struct,
                goal_type
            )
            self.db.add(recipe_record)
            self.db.flush()  # Get ID without committing

            # Create recipe ingredient records
            recipe_ingredient_records = self._create_recipe_ingredient_records(
                recipe_record.id,
                matched_ingredients
            )

            # Commit everything together
            self.db.commit()
            self.db.refresh(recipe_record)

            logger.info(f"✓ Created recipe ID={recipe_record.id}")
            logger.info(f"✓ Created {len(recipe_ingredient_records)} recipe_ingredient records")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise

        logger.info(f"\n{'='*80}")
        logger.info(f"SUCCESS! Recipe generated")
        logger.info(f"{'='*80}\n")

        return {
            'recipe': recipe_record,
            'recipe_ingredients': recipe_ingredient_records,
            'ingredients_created': ingredients_created,
            'ingredients_matched': ingredients_matched,
            'llm_nutrition': {
                'calories': recipe_struct.calories,
                'protein_g': recipe_struct.protein_g,
                'carbs_g': recipe_struct.carbs_g,
                'fat_g': recipe_struct.fat_g,
                'fiber_g': recipe_struct.fiber_g
            }
        }

    async def _create_recipe_record(
        self,
        recipe_struct: RecipeStructured,
        goal_type: str
    ) -> Recipe:
        """
        Create Recipe record with LLM's nutrition estimate

        IMPORTANT: Use LLM's nutrition (accounts for cooking), not calculated!
        """

        # Generate embedding for deduplication/search
        recipe_text = f"{recipe_struct.name} {recipe_struct.cuisine} " + \
                      " ".join([ing.food_name for ing in recipe_struct.ingredients[:5]])
        embedding = await self.embedder.get_embedding(recipe_text)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        # Convert LLM's nutrition to dict
        nutrition_dict = {
            'calories': recipe_struct.calories,
            'protein_g': recipe_struct.protein_g,
            'carbs_g': recipe_struct.carbs_g,
            'fat_g': recipe_struct.fat_g,
            'fiber_g': recipe_struct.fiber_g,
        }

        # Create Recipe with correct field names
        recipe = Recipe(
            title=recipe_struct.name,  # ✅ Correct: 'title' not 'name'
            description=recipe_struct.description,  # ✅ LLM generated
            goals=[goal_type],
            tags=recipe_struct.tags,  # ✅ LLM generated
            dietary_tags=recipe_struct.dietary_tags,
            suitable_meal_times=recipe_struct.suitable_meal_times,  # ✅ LLM generated
            instructions=recipe_struct.instructions,  # ✅ Keep as list (JSON)
            cuisine=recipe_struct.cuisine,  # ✅ Correct: single string
            prep_time_min=recipe_struct.prep_time_minutes,  # ✅ Correct: 'prep_time_min'
            cook_time_min=0,  # LLM provides total time in prep_time_min, so cook_time is 0
            difficulty_level=recipe_struct.difficulty_level,  # ✅ LLM generated
            servings=recipe_struct.servings,
            macros_per_serving=nutrition_dict,  # LLM's estimate (accounts for cooking!)
            meal_prep_notes=None,  # Optional
            chef_tips=None,  # Optional
            embedding=embedding_str,  # ✅ Correct: 'embedding' not 'recipe_embedding'
            source='llm_generated',
            external_id=None
        )

        return recipe

    def _create_recipe_ingredient_records(
        self,
        recipe_id: int,
        matched_ingredients: List[Dict]
    ) -> List[RecipeIngredient]:
        """
        Create RecipeIngredient records

        Purpose: Track which ingredients used for inventory deduction
        NOT used for nutrition calculation!
        """

        records = []

        for ing in matched_ingredients:
            record = RecipeIngredient(
                recipe_id=recipe_id,
                item_id=ing['item_id'],
                quantity_grams=ing['quantity_grams'],
                original_ingredient_text=f"{ing['quantity_grams']}g {ing['food_name']}",  # ✅ Correct field name
                normalized_confidence=ing['confidence'],
                preparation_notes=ing.get('preparation'),
                is_optional=False
            )

            self.db.add(record)
            records.append(record)

        return records

    def close(self):
        """Clean up resources"""
        if hasattr(self.processor, 'close'):
            self.processor.close()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def test_pipeline():
    """Test complete recipe generation pipeline"""
    from app.models.database import SessionLocal

    db = SessionLocal()
    pipeline = LLMRecipeGenerationPipeline(db)

    # Test: MUSCLE_GAIN recipe (like optimizer would request)
    target_macros = {
        'calories': 1000,
        'protein': 75,
        'carbs': 115,
        'fat': 30
    }

    print("\n" + "="*80)
    print("TESTING COMPLETE RECIPE GENERATION PIPELINE")
    print("="*80)

    try:
        result = await pipeline.generate_validated_recipe(
            goal_type="muscle_gain",
            target_macros=target_macros,
            cuisine="mediterranean",
            dietary_restrictions=["high-protein"]
        )

        print("\n" + "="*80)
        print("PIPELINE RESULT")
        print("="*80)
        print(f"\nRecipe ID: {result['recipe'].id}")
        print(f"Name: {result['recipe'].title}")

        print(f"\nIngredients Processing:")
        print(f"  - {result['ingredients_matched']} matched to existing items")
        print(f"  - {result['ingredients_created']} auto-seeded from FDC")

        print(f"\nLLM Nutrition (per serving):")
        print(f"  Calories: {result['llm_nutrition']['calories']:.0f} kcal")
        print(f"  Protein: {result['llm_nutrition']['protein_g']:.1f}g")
        print(f"  Carbs: {result['llm_nutrition']['carbs_g']:.1f}g")
        print(f"  Fat: {result['llm_nutrition']['fat_g']:.1f}g")
        print(f"  Fiber: {result['llm_nutrition']['fiber_g']:.1f}g")

        print(f"\nRecipe Ingredients ({len(result['recipe_ingredients'])}):")
        for ri in result['recipe_ingredients'][:5]:  # Show first 5
            print(f"  - {ri.original_ingredient} (item_id={ri.item_id}, confidence={ri.normalized_confidence:.2f})")

        if len(result['recipe_ingredients']) > 5:
            print(f"  ... and {len(result['recipe_ingredients']) - 5} more")

        print("\n✓ Pipeline completed successfully!")
        print("="*80)

    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        pipeline.close()
        db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_pipeline())
