# LLM Recipe Generation System - Final Design

**Key Principles**:
1. LLM generates recipe WITH nutrition estimate (accounting for cooking)
2. recipe_ingredients table is for **inventory tracking only**
3. Trust LLM's nutrition (it knows cooking affects calories)
4. Validate nutrition is reasonable (macros add up, realistic ranges)

---

## Complete Flow

```
1. LLM Generates Recipe (Structured Output)
   - Name, ingredients, instructions
   - Nutrition PER SERVING (accounting for cooking methods)
   ↓
2. Parse Each Ingredient
   - "500g chicken breast" → {food_name: "chicken_breast", quantity_grams: 500}
   ↓
3. For Each Ingredient:
   ├─ Check if exists in items table
   │  ├─ YES → Use existing item_id ✓
   │  └─ NO → Auto-seed using existing IntelligentSeeder
   │     ├─ Search FDC
   │     ├─ LLM selects best match
   │     ├─ Parse nutrition
   │     ├─ Generate embedding
   │     └─ Insert into items table
   ↓
4. Populate recipe_ingredients Table
   - All item_ids now guaranteed to exist
   - Purpose: Track which ingredients used → Deduct from inventory
   - NOT used for nutrition calculation
   ↓
5. Validate LLM's Nutrition Estimate
   - Check macros add up (protein×4 + carbs×4 + fat×9 ≈ calories ±5%)
   - Check values in realistic ranges (500-2000 cal, 20-200g protein, etc.)
   - If invalid → Regenerate recipe
   ↓
6. Store Recipe with LLM's Nutrition
   - macros_per_serving = LLM's estimate (accounts for cooking)
   - status = 'testing'
   - Optimizer will use this nutrition for meal planning
```

---

## Why LLM Nutrition is Better Than Sum of Ingredients

### Example: Fried Chicken

**Raw Ingredients**:
- 500g chicken breast: 165 cal/100g × 5 = 825 cal
- 50ml oil: 884 cal/100g × 0.5 = 442 cal
- **Ingredient sum**: 1267 cal

**Actual Cooked Recipe**:
- Oil absorption: Only ~30% absorbed = 133 cal
- Water loss: Chicken loses 20% weight in cooking
- **Actual**: ~958 cal (LLM estimates this correctly!)

### Example: Boiled Rice

**Raw Ingredients**:
- 100g dry rice: 370 cal

**Actual Cooked Recipe**:
- Rice absorbs water, triples in weight
- **Per serving (300g cooked)**: Still 370 cal but split across 3 servings
- LLM accounts for this, raw sum doesn't

---

## Structured Recipe Generation

```python
from pydantic import BaseModel, Field
from typing import List, Literal
from openai import AsyncOpenAI

class RecipeIngredientStructured(BaseModel):
    """Ingredient with quantity in grams"""
    food_name: str = Field(
        description="Canonical name: lowercase, singular, underscores (e.g. 'chicken_breast')"
    )
    quantity_grams: float = Field(ge=1, le=5000)
    preparation: str | None = Field(
        description="diced, chopped, raw, cooked, etc."
    )

class RecipeNutritionEstimate(BaseModel):
    """
    LLM's nutrition estimate PER SERVING

    IMPORTANT: This accounts for cooking methods!
    - Frying adds oil calories
    - Boiling causes water absorption
    - Roasting causes moisture loss
    """
    calories: float = Field(ge=50, le=2000)
    protein_g: float = Field(ge=0, le=200)
    carbs_g: float = Field(ge=0, le=300)
    fat_g: float = Field(ge=0, le=150)
    fiber_g: float = Field(ge=0, le=50)

class RecipeStructured(BaseModel):
    """Complete recipe with LLM's nutrition estimate"""
    name: str = Field(min_length=10, max_length=100)
    cuisine: str
    dietary_tags: List[Literal["vegetarian", "vegan", "high-protein", "low-carb", "gluten-free"]]
    servings: int = Field(ge=1, le=8)
    prep_time_minutes: int = Field(ge=10, le=120)

    ingredients: List[RecipeIngredientStructured] = Field(min_items=4, max_items=15)
    instructions: List[str] = Field(min_items=3, max_items=12)

    # LLM's nutrition estimate (accounting for cooking)
    nutrition_per_serving: RecipeNutritionEstimate

    # What we asked for (for validation)
    target_calories: float
    target_protein_g: float
    target_carbs_g: float
    target_fat_g: float


class StructuredRecipeGenerator:
    """Generate recipes with OpenAI Structured Outputs"""

    async def generate_recipe(
        self,
        goal_type: str,
        target_calories: float,
        target_protein: float,
        target_carbs: float,
        target_fat: float,
        cuisine: str = "mediterranean",
        dietary_restrictions: List[str] = []
    ) -> RecipeStructured:
        """
        Generate recipe using OpenAI Structured Outputs

        Returns: GUARANTEED valid RecipeStructured object
        """

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = f"""
Create a {cuisine} recipe for {goal_type} goal that meets these nutrition targets:

NUTRITION TARGETS (per serving):
- Calories: {target_calories} kcal
- Protein: {target_protein}g
- Carbs: {target_carbs}g
- Fat: {target_fat}g

CRITICAL REQUIREMENTS:
1. Use REAL, commonly available ingredients
2. Provide ALL quantities in GRAMS (convert cups/tbsp to grams)
3. Use canonical names: lowercase, singular, underscores
   Examples: "chicken_breast", "olive_oil", "brown_rice", "bell_pepper"
4. Provide ACCURATE nutrition estimate that accounts for:
   - Cooking method effects (frying adds oil, boiling adds water weight)
   - Ingredient losses (fat rendering, water evaporation)
   - Realistic portion sizes
5. Your nutrition estimate should be per serving of COOKED food

DIETARY RESTRICTIONS: {", ".join(dietary_restrictions) if dietary_restrictions else "None"}

Generate a delicious, practical recipe athletes would actually cook.
"""

        response = await client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            response_format=RecipeStructured,
            temperature=0.8
        )

        recipe = response.choices[0].message.parsed
        return recipe
```

---

## Nutrition Validation (Not Calculation!)

```python
class RecipeNutritionValidator:
    """Validate LLM's nutrition estimate is reasonable"""

    def validate_nutrition(
        self,
        nutrition: RecipeNutritionEstimate,
        target: dict,
        tolerance: float = 0.15  # ±15% acceptable
    ) -> tuple[bool, List[str]]:
        """
        Validate nutrition is:
        1. Close to target (±15%)
        2. Macros add up to calories
        3. Values in realistic ranges

        Returns: (is_valid, list_of_issues)
        """

        issues = []

        # Check 1: Macros add up to calories
        calculated_calories = (
            nutrition.protein_g * 4 +
            nutrition.carbs_g * 4 +
            nutrition.fat_g * 9
        )

        calorie_variance = abs(calculated_calories - nutrition.calories) / nutrition.calories

        if calorie_variance > 0.05:  # Allow 5% variance
            issues.append(
                f"Macro math doesn't add up: "
                f"stated={nutrition.calories} cal, "
                f"calculated={calculated_calories:.0f} cal "
                f"(variance={calorie_variance*100:.1f}%)"
            )

        # Check 2: Close to target
        nutrients_to_check = ['calories', 'protein_g', 'carbs_g', 'fat_g']

        for nutrient in nutrients_to_check:
            actual = getattr(nutrition, nutrient)
            target_value = target.get(nutrient, 0)

            if target_value > 0:
                variance = abs(actual - target_value) / target_value

                if variance > tolerance:
                    issues.append(
                        f"{nutrient}: actual={actual:.1f}, "
                        f"target={target_value:.1f} "
                        f"(variance={variance*100:.1f}%)"
                    )

        # Check 3: Realistic ranges
        if not (200 <= nutrition.calories <= 2000):
            issues.append(f"Unrealistic calories: {nutrition.calories}")

        if not (5 <= nutrition.protein_g <= 200):
            issues.append(f"Unrealistic protein: {nutrition.protein_g}g")

        is_valid = len(issues) == 0

        return is_valid, issues
```

---

## Complete Pipeline

```python
class LLMRecipeGenerationPipeline:
    """End-to-end recipe generation"""

    def __init__(self, db: Session):
        self.db = db
        self.generator = StructuredRecipeGenerator()
        self.processor = RecipeIngredientProcessor(db)  # From previous design
        self.validator = RecipeNutritionValidator()

    async def generate_validated_recipe(
        self,
        goal_type: str,
        target_macros: dict,
        cuisine: str = "mediterranean",
        max_retries: int = 2
    ) -> dict:
        """
        Generate recipe with validation

        Returns:
        {
            'recipe': Recipe object (with LLM's nutrition),
            'recipe_ingredients': [RecipeIngredient objects],
            'validation_passed': True
        }
        """

        for attempt in range(max_retries + 1):
            logger.info(f"Attempt {attempt + 1}/{max_retries + 1}")

            # Step 1: Generate recipe with LLM
            recipe_struct = await self.generator.generate_recipe(
                goal_type=goal_type,
                target_calories=target_macros['calories'],
                target_protein=target_macros['protein'],
                target_carbs=target_macros['carbs'],
                target_fat=target_macros['fat'],
                cuisine=cuisine
            )

            logger.info(f"Generated: {recipe_struct.name}")
            logger.info(f"LLM nutrition: {recipe_struct.nutrition_per_serving.calories} cal, "
                       f"{recipe_struct.nutrition_per_serving.protein_g}g protein")

            # Step 2: Validate LLM's nutrition is reasonable
            is_valid, issues = self.validator.validate_nutrition(
                nutrition=recipe_struct.nutrition_per_serving,
                target=target_macros,
                tolerance=0.15  # ±15%
            )

            if not is_valid:
                logger.warning(f"Validation failed: {issues}")
                if attempt < max_retries:
                    logger.info("Retrying...")
                    continue
                else:
                    raise ValueError(f"Failed validation after {max_retries + 1} attempts: {issues}")

            logger.info("✓ Nutrition validated!")

            # Step 3: Process ingredients (match + auto-seed missing)
            matched_ingredients = await self.processor.process_recipe_ingredients(
                recipe_struct.ingredients
            )

            logger.info(f"✓ Matched {len(matched_ingredients)} ingredients")

            # Step 4: Create database records
            recipe_record = await self._create_recipe_record(
                recipe_struct,
                goal_type
            )

            recipe_ingredient_records = await self._create_recipe_ingredient_records(
                recipe_record.id,
                matched_ingredients
            )

            logger.info(f"✓ Created recipe ID={recipe_record.id}")

            return {
                'recipe': recipe_record,
                'recipe_ingredients': recipe_ingredient_records,
                'validation_passed': True,
                'attempts': attempt + 1,
                'llm_nutrition': recipe_struct.nutrition_per_serving
            }

    async def _create_recipe_record(
        self,
        recipe_struct: RecipeStructured,
        goal_type: str
    ) -> Recipe:
        """Create Recipe with LLM's nutrition estimate"""

        # Generate embedding for deduplication
        embedder = EmbeddingService(api_key=settings.openai_api_key)
        recipe_text = f"{recipe_struct.name} {recipe_struct.cuisine} " + \
                      " ".join([ing.food_name for ing in recipe_struct.ingredients])
        embedding = await embedder.get_embedding(recipe_text)

        # Convert LLM nutrition to dict
        nutrition_dict = {
            'calories': recipe_struct.nutrition_per_serving.calories,
            'protein_g': recipe_struct.nutrition_per_serving.protein_g,
            'carbs_g': recipe_struct.nutrition_per_serving.carbs_g,
            'fat_g': recipe_struct.nutrition_per_serving.fat_g,
            'fiber_g': recipe_struct.nutrition_per_serving.fiber_g,
        }

        recipe = Recipe(
            name=recipe_struct.name,
            cuisine_tags=[recipe_struct.cuisine],
            dietary_tags=recipe_struct.dietary_tags,
            servings=recipe_struct.servings,
            prep_time_minutes=recipe_struct.prep_time_minutes,
            instructions="\n".join([f"{i+1}. {step}" for i, step in enumerate(recipe_struct.instructions)]),
            macros_per_serving=nutrition_dict,  # 🔥 LLM's estimate (accounts for cooking!)
            goals=[goal_type],
            status='testing',
            source='llm_generated',
            recipe_embedding=embedder.embedding_to_db_string(embedding)
        )

        self.db.add(recipe)
        self.db.commit()
        self.db.refresh(recipe)

        return recipe

    async def _create_recipe_ingredient_records(
        self,
        recipe_id: int,
        matched_ingredients: List[dict]
    ) -> List[RecipeIngredient]:
        """
        Create RecipeIngredient records

        Purpose: Track which ingredients used for inventory deduction
        NOT used for nutrition calculation
        """

        records = []

        for ing in matched_ingredients:
            record = RecipeIngredient(
                recipe_id=recipe_id,
                item_id=ing['item_id'],
                quantity_grams=ing['quantity_grams'],
                original_ingredient=f"{ing['quantity_grams']}g {ing['food_name']}",
                normalized_confidence=ing['confidence'],
                preparation_notes=ing.get('preparation'),
                is_optional=False
            )

            self.db.add(record)
            records.append(record)

        self.db.commit()

        return records
```

---

## What recipe_ingredients Table is Used For

### ✅ Correct Use Cases:

**1. Inventory Deduction**
```python
# User logs "Grilled Chicken Bowl"
recipe_id = user_meal_log.recipe_id

# Get all ingredients
ingredients = db.query(RecipeIngredient).filter_by(recipe_id=recipe_id).all()

# Deduct from inventory
for ing in ingredients:
    user_inventory.deduct(
        item_id=ing.item_id,
        quantity_grams=ing.quantity_grams
    )
```

**2. Shopping List**
```python
# User selects recipes for the week
for recipe in weekly_plan:
    for ing in recipe.recipe_ingredients:
        shopping_list[ing.item_id] += ing.quantity_grams

# Subtract what user already has
for item_id, needed in shopping_list.items():
    on_hand = inventory.get(item_id)
    to_buy = max(0, needed - on_hand)
```

**3. Ingredient Substitution**
```python
# User allergic to dairy
for ing in recipe.recipe_ingredients:
    if ing.item.category == 'dairy':
        substitute = find_substitute(ing.item_id, allergen='dairy')
        ing.item_id = substitute.id
```

### ❌ NOT Used For:

- Nutrition calculation (use recipe.macros_per_serving from LLM)
- Calorie tracking (use recipe nutrition, not sum of ingredients)
- Meal planning optimization (optimizer uses recipe.macros_per_serving)

---

## Cost Analysis

### Per Recipe

| Step | Cost |
|------|------|
| LLM Generation (gpt-4o structured) | $0.015 |
| Auto-seed missing ingredients (avg 2) | $0.020 |
| Embeddings | $0.001 |
| Validation retries (avg 0.2) | $0.003 |
| **Total** | **$0.039** |

### For 500 Recipes

- 500 × $0.04 = **$20**

---

## Next Steps

Ready to implement:

1. `backend/app/services/llm_recipe_generator.py`
2. `backend/app/services/recipe_ingredient_processor.py`
3. `backend/app/services/recipe_nutrition_validator.py`
4. `test_llm_recipe_generation.py` - Test with 5 recipes

Should I start building the structured recipe generator?
