"""
LLM Recipe Generator with Structured Outputs
============================================

Uses OpenAI's Structured Outputs to generate recipes with guaranteed format.
Generates recipes with nutrition estimates that account for cooking methods.
Includes deduplication using vector embeddings.
"""

import logging
from typing import List, Optional, Literal, Tuple
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.database import Recipe
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS (Guaranteed Structure)
# ============================================================================

class RecipeIngredientStructured(BaseModel):
    """
    Ingredient with quantity in grams

    LLM must provide:
    - Canonical food name (lowercase, singular, underscores)
    - Quantity in grams (for accuracy)
    - Optional preparation method
    """
    food_name: str = Field(
        description="Canonical ingredient name: lowercase, singular, underscores (e.g. 'chicken_breast', 'olive_oil')"
    )
    quantity_grams: float = Field(
        ge=1,
        le=5000,
        description="Quantity in grams. Convert from other units (1 cup rice ≈ 185g, 1 tbsp oil ≈ 15ml, etc.)"
    )
    preparation: Optional[str] = Field(
        default=None,
        description="Preparation method: diced, chopped, minced, sliced, raw, cooked, etc."
    )


class RecipeStructured(BaseModel):
    """
    Complete recipe with guaranteed structure - LLM generates ALL fields
    """
    name: str = Field(
        min_length=10,
        max_length=100,
        description="Descriptive recipe name"
    )
    description: str = Field(
        min_length=20,
        max_length=300,
        description="Brief description of the recipe"
    )
    cuisine: str = Field(
        description="Cuisine type: mediterranean, italian, indian, mexican, asian, american, etc."
    )
    dietary_tags: List[Literal["vegetarian", "vegan", "high-protein", "low-carb", "gluten-free", "dairy-free"]] = Field(
        default_factory=list,
        description="Dietary classifications"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Recipe tags like 'quick', 'high_protein', 'meal_prep_friendly'"
    )
    suitable_meal_times: List[Literal["breakfast", "lunch", "dinner", "snack"]] = Field(
        min_items=4,
        max_items=4,
        description="This recipe is versatile and suitable for any meal time including snacks"
    )
    difficulty_level: Literal["easy", "medium", "hard"] = Field(
        description="Recipe difficulty level"
    )
    servings: int = Field(
        ge=1,
        le=8,
        description="Number of servings this recipe makes"
    )
    prep_time_minutes: int = Field(
        ge=10,
        le=120,
        description="Total preparation and cooking time in minutes"
    )

    ingredients: List[RecipeIngredientStructured] = Field(
        min_items=4,
        max_items=15,
        description="All ingredients with quantities in grams"
    )

    instructions: List[str] = Field(
        min_items=3,
        max_items=12,
        description="Step-by-step cooking instructions"
    )

    # Nutrition per serving (flattened to avoid allOf schema issue)
    calories: float = Field(
        ge=50,
        le=2000,
        description="Total calories per serving after cooking"
    )
    protein_g: float = Field(
        ge=0,
        le=200,
        description="Protein in grams per serving"
    )
    carbs_g: float = Field(
        ge=0,
        le=300,
        description="Carbohydrates in grams per serving"
    )
    fat_g: float = Field(
        ge=0,
        le=150,
        description="Fat in grams per serving"
    )
    fiber_g: float = Field(
        ge=0,
        le=50,
        description="Fiber in grams per serving"
    )

    # Metadata for validation
    target_calories: float = Field(
        description="Target calories this recipe was designed for"
    )
    target_protein_g: float = Field(
        description="Target protein this recipe was designed for"
    )
    target_carbs_g: float = Field(
        description="Target carbs this recipe was designed for"
    )
    target_fat_g: float = Field(
        description="Target fat this recipe was designed for"
    )


# ============================================================================
# RECIPE DEDUPLICATOR
# ============================================================================

class RecipeDeduplicator:
    """
    Check if recipe already exists using vector similarity

    Prevents duplicate recipes by comparing:
    - Recipe name
    - Main ingredients
    - Cuisine type
    """

    def __init__(self, db: Session):
        self.db = db
        self.embedder = EmbeddingService(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )

    async def is_duplicate(
        self,
        recipe: RecipeStructured,
        similarity_threshold: float = 0.90
    ) -> Tuple[bool, Optional[Recipe]]:
        """
        Check if recipe is too similar to existing recipes

        Args:
            recipe: New recipe to check
            similarity_threshold: Cosine similarity threshold (0.90 = 90% similar)

        Returns:
            (is_duplicate, existing_recipe_if_duplicate)
        """

        # Create embedding text from recipe
        recipe_text = self._create_recipe_text(recipe)

        # Generate embedding
        embedding = await self.embedder.get_embedding(recipe_text)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        # Search for similar recipes using vector similarity
        # Note: Space before ::vector is required for SQLAlchemy parameter binding
        # See: https://github.com/sqlalchemy/sqlalchemy/issues/3644
        result = self.db.execute(text("""
            SELECT
                id,
                title,
                cuisine,
                1 - (embedding::vector(1536) <=> :embedding ::vector(1536)) as similarity
            FROM recipes
            WHERE embedding IS NOT NULL
            ORDER BY embedding::vector(1536) <=> :embedding ::vector(1536)
            LIMIT 1
        """), {
            "embedding": embedding_str
        }).mappings().fetchone()

        if result and result['similarity'] >= similarity_threshold:
            logger.warning(
                f"Duplicate detected! New: '{recipe.name}' is {result['similarity']*100:.1f}% similar to "
                f"existing recipe ID={result['id']} '{result['title']}'"
            )

            existing_recipe = self.db.query(Recipe).get(result['id'])
            return True, existing_recipe

        return False, None

    def _create_recipe_text(self, recipe: RecipeStructured) -> str:
        """
        Create text representation for embedding

        Combines:
        - Recipe name (most important)
        - Cuisine type
        - Main ingredients (first 5)
        """

        # Get main ingredients (first 5, assumed to be primary)
        main_ingredients = " ".join([
            ing.food_name
            for ing in recipe.ingredients[:5]
        ])

        recipe_text = f"{recipe.name} {recipe.cuisine} {main_ingredients}"

        return recipe_text


# ============================================================================
# RECIPE GENERATOR
# ============================================================================

class StructuredRecipeGenerator:
    """
    Generate recipes using OpenAI Structured Outputs

    Benefits:
    - Zero parsing errors (guaranteed valid JSON)
    - Type safety (Pydantic validation)
    - Clear contracts (model defines structure)
    - Better LLM adherence (structured mode enforces schema)
    - Deduplication check (prevents similar recipes)
    """

    def __init__(self, api_key: Optional[str] = None, db: Optional[Session] = None):
        self.api_key = api_key or settings.openai_api_key
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.db = db
        self.deduplicator = RecipeDeduplicator(db) if db else None

    async def generate_recipe(
        self,
        goal_type: str,
        target_calories: float,
        target_protein: float,
        target_carbs: float,
        target_fat: float,
        cuisine: str = "mediterranean",
        dietary_restrictions: List[str] = None,
        check_duplicates: bool = True,
        max_retries: int = 3
    ) -> RecipeStructured:
        """
        Generate recipe with structured outputs and deduplication

        Args:
            goal_type: muscle_gain, fat_loss, body_recomp, etc.
            target_calories: Target calories per serving
            target_protein: Target protein in grams per serving
            target_carbs: Target carbs in grams per serving
            target_fat: Target fat in grams per serving
            cuisine: Cuisine type (mediterranean, indian, etc.)
            dietary_restrictions: List of restrictions (vegetarian, vegan, etc.)
            check_duplicates: Whether to check for duplicate recipes
            max_retries: Max attempts if duplicates found

        Returns:
            RecipeStructured: Guaranteed valid, unique recipe object

        Raises:
            ValueError: If OpenAI API fails or max retries reached
        """

        dietary_restrictions = dietary_restrictions or []

        for attempt in range(max_retries):
            logger.info(f"Generation attempt {attempt + 1}/{max_retries}")

            prompt = self._build_prompt(
                goal_type=goal_type,
                target_calories=target_calories,
                target_protein=target_protein,
                target_carbs=target_carbs,
                target_fat=target_fat,
                cuisine=cuisine,
                dietary_restrictions=dietary_restrictions,
                attempt=attempt  # Add attempt number to encourage variety
            )

            logger.info(f"Generating {cuisine} recipe for {goal_type} goal")
            logger.info(f"Target: {target_calories} cal, {target_protein}g protein, {target_carbs}g carbs, {target_fat}g fat")

            try:
                response = await self.client.beta.chat.completions.parse(
                    model="gpt-4o-2024-08-06",  # Supports structured outputs
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert chef and nutritionist. Create accurate, delicious recipes with precise nutrition estimates."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format=RecipeStructured,  # 🔥 GUARANTEED STRUCTURE
                    temperature=0.8 + (attempt * 0.1)  # Increase variety on retries
                )

                recipe = response.choices[0].message.parsed

                logger.info(f"✓ Generated recipe: {recipe.name}")
                logger.info(f"  Nutrition: {recipe.calories} cal, "
                           f"{recipe.protein_g}g protein, "
                           f"{recipe.carbs_g}g carbs, "
                           f"{recipe.fat_g}g fat")
                logger.info(f"  Ingredients: {len(recipe.ingredients)}")

                # Check for duplicates
                if check_duplicates and self.deduplicator:
                    is_dup, existing = await self.deduplicator.is_duplicate(recipe)

                    if is_dup:
                        logger.warning(f"Duplicate detected: {recipe.name} similar to {existing.title}")
                        if attempt < max_retries - 1:
                            logger.info("Retrying with more variety...")
                            continue
                        else:
                            raise ValueError(f"Max retries reached. Could not generate unique recipe.")

                return recipe

            except Exception as e:
                logger.error(f"Failed to generate recipe: {e}")
                if attempt < max_retries - 1:
                    logger.info("Retrying...")
                    continue
                else:
                    raise ValueError(f"Recipe generation failed after {max_retries} attempts: {e}")

        raise ValueError(f"Recipe generation failed after {max_retries} attempts")

    def _build_prompt(
        self,
        goal_type: str,
        target_calories: float,
        target_protein: float,
        target_carbs: float,
        target_fat: float,
        cuisine: str,
        dietary_restrictions: List[str],
        attempt: int = 0
    ) -> str:
        """Build comprehensive prompt for recipe generation"""

        variety_note = ""
        if attempt > 0:
            variety_note = f"\n\nIMPORTANT: This is attempt #{attempt + 1}. Generate a DIFFERENT recipe than before. Use different main ingredients and cooking methods."

        return f"""
Create a {cuisine} recipe for {goal_type} fitness goal that meets these nutrition targets:

NUTRITION TARGETS (per serving):
- Calories: {target_calories} kcal (±10% acceptable)
- Protein: {target_protein}g (±10% acceptable)
- Carbs: {target_carbs}g (±10% acceptable)
- Fat: {target_fat}g (±10% acceptable)

CRITICAL REQUIREMENTS:

1. INGREDIENT QUANTITIES (VERY IMPORTANT):
   - Provide ALL quantities in GRAMS
   - Convert other units to grams:
     * 1 cup liquid = 240ml/240g (water/milk)
     * 1 cup rice (dry) = 185g
     * 1 cup flour = 120g
     * 1 tbsp oil = 15ml/13.5g
     * 1 tsp = 5ml
   - For proteins: 500g chicken breast, 200g salmon, etc.
   - For vegetables: 150g tomato, 100g spinach, etc.

2. CANONICAL INGREDIENT NAMES:
   - Use lowercase, singular, underscores
   - Examples: "chicken_breast", "olive_oil", "brown_rice", "bell_pepper"
   - NOT: "Chicken Breasts", "extra virgin olive oil", "Brown Rice"
   - Use generic names: "yogurt" not "Greek Yogurt", "rice" not "Basmati Rice"

3. NUTRITION ACCURACY:
   - Your nutrition estimate MUST account for cooking methods
   - Frying: Oil absorption (typically 20-30% of oil used)
   - Boiling: Water absorption (rice/pasta triples in weight)
   - Roasting: Moisture loss (vegetables lose 10-20% weight)
   - Grilling: Fat renders out (meat loses some calories)
   - Your estimate should be for COOKED, READY-TO-EAT serving

4. MACRO VALIDATION:
   - Ensure: (protein_g × 4) + (carbs_g × 4) + (fat_g × 9) ≈ calories (±5%)
   - If math doesn't work, adjust macros (don't just make up numbers)

5. DIETARY RESTRICTIONS:
   {f"- Must be: {', '.join(dietary_restrictions)}" if dietary_restrictions else "- None"}

6. RECIPE QUALITY:
   - Use real, commonly available ingredients
   - Provide clear, practical cooking instructions
   - Recipe should be something athletes would actually cook
   - Prep time should be realistic (10-60 minutes for most recipes)

CUISINE CONTEXT ({cuisine}):
- Use typical {cuisine} ingredients and cooking methods
- Incorporate characteristic flavors and spices
- Keep authentic to cuisine while hitting nutrition targets
{variety_note}

Generate a delicious, nutritious, practical recipe!
"""


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def test_generator():
    """Test the recipe generator"""

    generator = StructuredRecipeGenerator()

    # Test: MUSCLE_GAIN recipe
    recipe = await generator.generate_recipe(
        goal_type="muscle_gain",
        target_calories=1000,
        target_protein=75,
        target_carbs=115,
        target_fat=30,
        cuisine="mediterranean",
        dietary_restrictions=["high-protein"],
        check_duplicates=False  # No DB in test
    )

    print("\n" + "="*80)
    print("GENERATED RECIPE")
    print("="*80)
    print(f"\nName: {recipe.name}")
    print(f"Cuisine: {recipe.cuisine}")
    print(f"Servings: {recipe.servings}")
    print(f"Prep Time: {recipe.prep_time_minutes} minutes")
    print(f"Tags: {recipe.dietary_tags}")

    print(f"\nNutrition (per serving):")
    print(f"  Calories: {recipe.nutrition_per_serving.calories} kcal")
    print(f"  Protein: {recipe.nutrition_per_serving.protein_g}g")
    print(f"  Carbs: {recipe.nutrition_per_serving.carbs_g}g")
    print(f"  Fat: {recipe.nutrition_per_serving.fat_g}g")
    print(f"  Fiber: {recipe.nutrition_per_serving.fiber_g}g")

    print(f"\nIngredients ({len(recipe.ingredients)}):")
    for ing in recipe.ingredients:
        prep_note = f" ({ing.preparation})" if ing.preparation else ""
        print(f"  - {ing.quantity_grams}g {ing.food_name}{prep_note}")

    print(f"\nInstructions ({len(recipe.instructions)} steps):")
    for i, step in enumerate(recipe.instructions, 1):
        print(f"  {i}. {step}")

    print("\n" + "="*80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_generator())
