# Recipe Pipeline Fixes - Implementation Plan

**Based on User Feedback - 2025-01-26**

---

## Your Answers Summary

1. ✅ **All database fields must be populated** - Use professional, concise prompts (no bloating)
2. ✅ **Auto-calculate meal times & difficulty** - User wants to see the logic before approving
3. ✅ **Follow exact flow from `ai_assisted_item_seeding.py`** - Don't rewrite, reuse the pattern (includes parsed nutrition to LLM)
4. ✅ **Keep ONE time field only** - Don't split prep/cook, keep it simple
5. ✅ **No status field** - Recipe model doesn't have it, don't add it unnecessarily

---

## Fix Plan

### PRIORITY 1: Critical Database Schema Fixes

#### Fix 1.1: Recipe Model Field Names
**File**: `recipe_pipeline.py` line 292-340

**Current (WRONG)**:
```python
recipe = Recipe(
    name=recipe_struct.name,  # ❌
    cuisine_tags=[recipe_struct.cuisine],  # ❌
    prep_time_minutes=recipe_struct.prep_time_minutes,  # ❌
    recipe_embedding=embedding_str,  # ❌
    status='testing'  # ❌
)
```

**Fixed**:
```python
# Derive fields from recipe data
meal_times = _determine_meal_times(
    recipe_struct.calories,
    recipe_struct.protein_g,
    recipe_struct.carbs_g
)
difficulty = _determine_difficulty(
    len(recipe_struct.ingredients),
    len(recipe_struct.instructions),
    recipe_struct.prep_time_minutes
)
tags = _derive_tags(recipe_struct)

recipe = Recipe(
    title=recipe_struct.name,  # ✅ Correct field name
    description=f"A delicious {recipe_struct.cuisine} recipe perfect for {goal_type}",
    goals=[goal_type],
    tags=tags,  # Derived
    dietary_tags=recipe_struct.dietary_tags,
    suitable_meal_times=meal_times,  # Derived
    instructions=recipe_struct.instructions,  # Keep as list!
    cuisine=recipe_struct.cuisine,  # ✅ Single string
    prep_time_min=recipe_struct.prep_time_minutes,  # ✅ Correct field name
    cook_time_min=None,  # Don't split, keep simple
    difficulty_level=difficulty,  # Derived
    servings=recipe_struct.servings,
    macros_per_serving={...},
    meal_prep_notes=None,  # Optional, can be NULL
    chef_tips=None,  # Optional, can be NULL
    embedding=embedding_str,  # ✅ Correct field name
    source='llm_generated',
    external_id=None
)
```

#### Fix 1.2: RecipeIngredient Field Name
**File**: `recipe_pipeline.py` line 360

**Current**: `original_ingredient=...`
**Fixed**: `original_ingredient_text=...`

#### Fix 1.3: Instructions Format
**File**: `recipe_pipeline.py` line 312-316

**Current**: Joins into string
**Fixed**: Keep as list (Recipe model expects JSON list)

```python
# BEFORE (wrong)
instructions = "\n".join([f"{i+1}. {step}" for i, step in enumerate(recipe_struct.instructions)])

# AFTER (correct)
instructions = recipe_struct.instructions  # Keep as list
```

#### Fix 1.4: Pydantic to Dict Conversion
**File**: `recipe_pipeline.py` line 206

**Current**: Passes Pydantic models
**Fixed**: Convert to dicts first

```python
# Convert Pydantic models to dicts
ingredients_as_dicts = [
    {
        "food_name": ing.food_name,
        "quantity_grams": ing.quantity_grams,
        "preparation": ing.preparation
    }
    for ing in recipe_struct.ingredients
]

matched_ingredients = await self.processor.process_recipe_ingredients(ingredients_as_dicts)
```

#### Fix 1.5: Deduplication SQL Fields
**File**: `llm_recipe_generator.py` line 178-190

**Current**: Uses `name`, `cuisine_tags`, `recipe_embedding`
**Fixed**: Use `title`, `cuisine`, `embedding`

```python
similar = self.db.execute("""
    SELECT id, title, cuisine,
           1 - (embedding <=> :embedding::vector) as similarity
    FROM recipes
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> :embedding::vector
    LIMIT 1
""", {"embedding": embedding_str}).fetchone()
```

---

### PRIORITY 2: Field Derivation Functions

#### Function 1: Determine Meal Times
```python
def _determine_meal_times(calories: float, protein_g: float, carbs_g: float) -> List[str]:
    """
    Auto-determine suitable meal times based on macros

    Logic:
    - High carbs (>80g) + moderate cal (>400) → breakfast/lunch
    - High protein (>35g) → lunch/dinner
    - Light (<350 cal) → snack
    """
    meal_times = []

    # High carbs + moderate calories → good for breakfast/lunch
    if carbs_g > 80 and calories > 400:
        meal_times.extend(["breakfast", "lunch"])

    # High protein → good for lunch/dinner
    if protein_g > 35:
        meal_times.extend(["lunch", "dinner"])

    # Light meal → snack
    if calories < 350:
        meal_times.append("snack")

    # Default if nothing matched
    if not meal_times:
        meal_times = ["lunch", "dinner"]

    # Remove duplicates, maintain order
    seen = set()
    return [x for x in meal_times if not (x in seen or seen.add(x))]
```

#### Function 2: Determine Difficulty
```python
def _determine_difficulty(num_ingredients: int, num_steps: int, total_time_min: int) -> str:
    """
    Calculate difficulty based on recipe complexity

    Scoring:
    - Ingredients: ≤5 (0 pts), 6-10 (1 pt), >10 (2 pts)
    - Steps: ≤4 (0 pts), 5-8 (1 pt), >8 (2 pts)
    - Time: ≤30 min (0 pts), 31-60 (1 pt), >60 (2 pts)

    Final: 0-2 = easy, 3-4 = medium, 5-6 = hard
    """
    score = 0

    # Ingredient complexity
    if num_ingredients <= 5:
        score += 0
    elif num_ingredients <= 10:
        score += 1
    else:
        score += 2

    # Step complexity
    if num_steps <= 4:
        score += 0
    elif num_steps <= 8:
        score += 1
    else:
        score += 2

    # Time complexity
    if total_time_min <= 30:
        score += 0
    elif total_time_min <= 60:
        score += 1
    else:
        score += 2

    # Determine difficulty level
    if score <= 2:
        return "easy"
    elif score <= 4:
        return "medium"
    else:
        return "hard"
```

#### Function 3: Derive Tags
```python
def _derive_tags(recipe_struct: RecipeStructured) -> List[str]:
    """
    Auto-generate tags from recipe properties

    Tags:
    - "quick" if prep_time < 30
    - "complex" if >10 ingredients
    - Copy from dietary_tags (vegetarian, vegan, etc.)
    """
    tags = []

    # Time-based tags
    if recipe_struct.prep_time_minutes < 30:
        tags.append("quick")

    # Complexity tags
    if len(recipe_struct.ingredients) > 10:
        tags.append("complex")
    elif len(recipe_struct.ingredients) <= 5:
        tags.append("simple")

    # Copy dietary tags
    for dietary_tag in recipe_struct.dietary_tags:
        tags.append(dietary_tag)

    # Protein-based tags
    if recipe_struct.protein_g > 40:
        tags.append("high_protein")

    return list(set(tags))  # Remove duplicates
```

---

### PRIORITY 3: Follow Exact Item Seeding Pattern

#### Current Problem in `recipe_ingredient_processor.py`

I was trying to wrap `IntelligentSeeder` incorrectly. Instead, I need to **follow the exact pattern** from `ai_assisted_item_seeding.py`:

**Key Pattern** (lines 261-273):
```python
# For each FDC match, parse nutrition FIRST
simplified_matches = []
for match in fdc_matches:
    # Parse nutrition from this match
    parsed_nutrition = self.fdc_service._parse_fdc_nutrients(match)

    simplified_matches.append({
        "description": match.get("description", ""),
        "fdcId": match.get("fdcId", ""),
        "dataType": match.get("dataType", ""),
        "nutrition": parsed_nutrition,  # 🔥 Include parsed nutrition for LLM!
    })

# Then send to LLM for selection
```

**Fixed Implementation**:

```python
class RecipeIngredientProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.fdc_service = FDCService()
        self.embedder = EmbeddingService(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )
        self.openai_client = OpenAI(api_key=settings.openai_api_key)

    async def _auto_seed_ingredient(self, food_name: str) -> Item:
        """
        Auto-seed missing ingredient using EXACT pattern from ai_assisted_item_seeding.py

        Steps:
        1. Search FDC (sync call, no await)
        2. Parse nutrition for each match
        3. LLM selects best match (WITH parsed nutrition)
        4. Generate embedding
        5. Create Item
        """

        # Step 1: Search FDC (SYNC, no await!)
        search_query = food_name.replace('_', ' ')
        logger.info(f"    Searching FDC for: {search_query}")

        fdc_matches = self.fdc_service.search_food(search_query)  # ✅ SYNC call

        if not fdc_matches:
            raise ValueError(f"No FDC matches found for: {food_name}")

        # Take top 3 matches
        top_3 = fdc_matches[:3]

        # Step 2: Parse nutrition for each match (BEFORE sending to LLM!)
        simplified_matches = []
        for match in top_3:
            parsed_nutrition = self.fdc_service._parse_fdc_nutrients(match)

            simplified_matches.append({
                "description": match.get("description", ""),
                "fdcId": match.get("fdcId", ""),
                "dataType": match.get("dataType", ""),
                "nutrition": parsed_nutrition,  # 🔥 Critical: LLM needs this!
            })

        # Step 3: LLM selects best match (with nutrition data)
        enrichment = await self._llm_select_best_fdc_match(food_name, simplified_matches)

        if enrichment['best_fdc_index'] == -1:
            raise ValueError(f"LLM couldn't find good match for: {food_name}")

        # Get the selected FDC match
        best_match = top_3[enrichment['best_fdc_index']]

        # Step 4: Parse nutrition again (final selected match)
        nutrition = self.fdc_service._parse_fdc_nutrients(best_match)

        # Step 5: Generate embedding
        embedding_text = f"{food_name} {enrichment['category']}"
        embedding = await self.embedder.get_embedding(embedding_text)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        # Step 6: Create Item (EXACT pattern from item seeder)
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
            source="usda_fdc",
            confidence=enrichment['confidence']
        )

        self.db.add(new_item)
        self.db.commit()
        self.db.refresh(new_item)

        return new_item

    async def _llm_select_best_fdc_match(
        self,
        food_name: str,
        simplified_matches: List[Dict]
    ) -> Dict:
        """
        LLM selects best FDC match - PROFESSIONAL PROMPT (no bloat)

        Matches pattern from ai_assisted_item_seeding.py lines 283-327
        """

        prompt = f"""Select the best FDC match for: "{food_name}"

FDC OPTIONS (with parsed nutrition):
{json.dumps(simplified_matches, indent=2)}

Criteria:
1. Nutrition values match expected profile (use your knowledge)
2. Description best matches ingredient (prefer "raw" over processed)
3. Data is complete (not missing expected nutrients)

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
            model="gpt-4o-mini",
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
```

---

### PRIORITY 4: Transaction Handling

**File**: `recipe_pipeline.py` line 233-243

**Current**: Commits recipe before creating ingredients (can leave orphans)

**Fixed**:
```python
try:
    # Step 1: Generate recipe struct
    recipe_struct = await self.generator.generate_recipe(...)

    # Step 2: Validate nutrition
    is_valid, issues = self.validator.validate_nutrition(recipe_struct)
    if not is_valid:
        continue  # Retry

    # Step 3: Process ingredients
    matched_ingredients = await self.processor.process_recipe_ingredients(ingredients_as_dicts)

    # Step 4: Create recipe record (NO COMMIT yet!)
    recipe_record = self._create_recipe_record(recipe_struct, goal_type)  # Make this sync
    self.db.add(recipe_record)
    self.db.flush()  # Get ID without committing

    # Step 5: Create recipe ingredient records
    for ing in matched_ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe_id=recipe_record.id,
            item_id=ing['item_id'],
            quantity_grams=ing['quantity_grams'],
            original_ingredient_text=f"{ing['quantity_grams']}g {ing['food_name']}",
            normalized_confidence=ing['confidence'],
            preparation_notes=ing.get('preparation'),
            is_optional=False
        )
        self.db.add(recipe_ingredient)

    # Step 6: Commit everything together
    self.db.commit()
    self.db.refresh(recipe_record)

    return {...}

except Exception as e:
    self.db.rollback()
    logger.error(f"Failed to create recipe: {e}")
    raise
```

---

## Summary of Changes

### Files to Modify:

1. **`llm_recipe_generator.py`**:
   - Fix deduplication SQL (line 178-190)
   - Use `title`, `cuisine`, `embedding` instead of wrong field names

2. **`recipe_ingredient_processor.py`**:
   - Remove `IntelligentSeeder` wrapper
   - Implement exact pattern from `ai_assisted_item_seeding.py`
   - Parse nutrition BEFORE sending to LLM
   - Remove all `await` from FDCService calls (it's sync!)

3. **`recipe_pipeline.py`**:
   - Fix all Recipe field names
   - Add derivation functions for meal_times, difficulty, tags
   - Fix instructions format (keep as list)
   - Fix Pydantic→dict conversion
   - Fix RecipeIngredient field name
   - Add proper transaction handling
   - Remove `status` field completely

---

## Testing Plan

### Test 1: Single Recipe Generation
```bash
cd backend
python -m test_llm_recipe_generator  # Should still work
```

### Test 2: Database Insert
```python
# Test with actual database
# Verify all fields populated correctly
# Check no NULL fields that shouldn't be NULL
```

### Test 3: Ingredient Processing
```python
# Test auto-seeding
# Verify it follows exact pattern
# Check parsed nutrition is sent to LLM
```

---

**Ready to implement these fixes. Should I proceed?**
