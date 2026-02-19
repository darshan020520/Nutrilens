# Phase 1: Recipe Fetching Strategy - Final Design

**Date**: 2025-10-22
**Philosophy**: Use Spoonacular ONLY for recipe data source, everything else is our innovation

---

## Spoonacular Usage - Minimal & Strategic

### What We USE Spoonacular For

**ONLY Recipe Data Source** ✅
- Complex Recipe Search with constraints (their core strength)
- Recipe metadata (title, instructions, image, servings, prep time)
- Raw ingredient text lists
- Basic nutrition per serving (for validation)

**That's it!** Everything else is our innovation.

---

## What We Build with LLMs

### 1. Ingredient Parsing (LLM)

**Input**: Raw ingredient text from Spoonacular
```
"2 cups diced cucumber"
"1 lb boneless chicken breast"
"3 tbsp extra virgin olive oil"
```

**LLM Parsing**:
```python
async def parse_ingredient_with_llm(ingredient_text: str) -> dict:
    """Use LLM to parse ingredient into structured format"""

    prompt = f"""
    Parse this ingredient into structured format:

    "{ingredient_text}"

    Extract:
    - quantity (numeric value)
    - unit (cups, tbsp, lb, etc. or "whole" if none)
    - food_name (canonical ingredient name)
    - preparation (diced, chopped, minced, etc.)
    - modifiers (boneless, extra virgin, etc.)

    Return JSON:
    {{
        "quantity": <number>,
        "unit": "<unit or 'whole'>",
        "food_name": "<canonical name>",
        "preparation": "<method or null>",
        "modifiers": ["<list of modifiers>"]
    }}
    """

    response = await llm.complete(prompt)
    return json.loads(response)

# Example outputs:
# "2 cups diced cucumber" →
# {
#   "quantity": 2,
#   "unit": "cups",
#   "food_name": "cucumber",
#   "preparation": "diced",
#   "modifiers": []
# }

# "1 lb boneless chicken breast" →
# {
#   "quantity": 1,
#   "unit": "lb",
#   "food_name": "chicken breast",
#   "preparation": null,
#   "modifiers": ["boneless"]
# }
```

**Cost**: ~50-100 tokens per ingredient = $0.0001-0.0003 each
**Accuracy**: High (LLMs are trained on recipe data)

### 2. Unit Conversion (LLM)

**Input**: Parsed ingredient + need grams conversion

**LLM Conversion**:
```python
async def convert_to_grams_with_llm(
    quantity: float,
    unit: str,
    food_name: str
) -> float:
    """Use LLM to convert any unit to grams"""

    prompt = f"""
    Convert this ingredient measurement to grams:

    - Quantity: {quantity}
    - Unit: {unit}
    - Ingredient: {food_name}

    Consider:
    - Ingredient density (flour is different from water)
    - Standard conversions (1 cup = 240ml for liquids)
    - Food-specific volumes (1 cup flour ≈ 120g, 1 cup water ≈ 240g)

    Return JSON:
    {{
        "grams": <number>,
        "reasoning": "<brief explanation>",
        "confidence": <0.0-1.0>
    }}
    """

    response = await llm.complete(prompt)
    result = json.loads(response)
    return result

# Example:
# convert_to_grams_with_llm(2, "cups", "cucumber") →
# {
#   "grams": 280,
#   "reasoning": "1 cup diced cucumber ≈ 140g",
#   "confidence": 0.95
# }

# convert_to_grams_with_llm(1, "lb", "chicken breast") →
# {
#   "grams": 454,
#   "reasoning": "1 pound = 454 grams",
#   "confidence": 1.0
# }
```

**Cost**: ~100-150 tokens per conversion = $0.0002-0.0004 each
**Accuracy**: High (LLMs know ingredient densities)

**Advantages over Spoonacular**:
- ✅ Works for ANY ingredient (not limited to Spoonacular's 5k)
- ✅ Handles unusual units ("a pinch", "to taste", "medium onion")
- ✅ Provides confidence score
- ✅ Explains reasoning (can validate)
- ✅ Cheaper (Spoonacular charges 0.01 points per ingredient)

---

## Complete Workflow - Phase 1

### Step 1: Fetch Recipe from Spoonacular

```python
class SpoonacularClient:
    """Minimal client - ONLY for recipe data source"""

    async def search_recipes_by_constraints(
        self,
        goal_type: GoalType,
        constraints: OptimizationConstraints,
        cuisine: Optional[str] = None,
        number: int = 50
    ) -> List[dict]:
        """Search recipes matching optimizer constraints"""

        cal_per_meal = constraints.daily_calories / constraints.meals_per_day

        params = {
            'apiKey': self.api_key,
            'number': number,

            # Calorie constraints
            'minCalories': int(cal_per_meal * 0.5),
            'maxCalories': int(cal_per_meal * 1.5),

            # Macro constraints
            'minProtein': int(constraints.protein_target * 0.8),
            'maxProtein': int(constraints.protein_target * 1.2),
            'minCarbs': int(constraints.carbs_target * 0.8),
            'maxCarbs': int(constraints.carbs_target * 1.2),

            # User preferences
            'diet': constraints.dietary_tags,
            'intolerances': constraints.allergies,
            'cuisine': cuisine,
            'maxReadyTime': constraints.max_prep_time,
        }

        response = await self.client.get(
            f"{self.base_url}/recipes/complexSearch",
            params=params
        )
        return response.json()['results']

    async def get_recipe_details(self, recipe_id: int) -> dict:
        """Get recipe details - MINIMAL data needed"""

        params = {
            'apiKey': self.api_key,
            # Don't include nutrition - we'll calculate from ingredients
        }

        response = await self.client.get(
            f"{self.base_url}/recipes/{recipe_id}/information",
            params=params
        )

        data = response.json()

        # Extract ONLY what we need
        return {
            'id': data['id'],
            'title': data['title'],
            'image': data.get('image'),
            'servings': data['servings'],
            'ready_in_minutes': data['readyInMinutes'],
            'instructions': self._format_instructions(data.get('analyzedInstructions', [])),
            'cuisines': data.get('cuisines', []),
            'diets': data.get('diets', []),

            # RAW ingredient text - we'll parse with LLM
            'raw_ingredients': [
                ing.get('original', ing.get('name', ''))
                for ing in data.get('extendedIngredients', [])
            ]
        }

    def _format_instructions(self, analyzed_instructions: list) -> str:
        """Convert Spoonacular instructions to simple text"""
        if not analyzed_instructions:
            return ""

        steps = []
        for instruction_set in analyzed_instructions:
            for step in instruction_set.get('steps', []):
                steps.append(f"{step['number']}. {step['step']}")

        return "\n".join(steps)
```

### Step 2: Parse Ingredients with LLM

```python
class LLMIngredientParser:
    """Parse raw ingredient text using LLM"""

    async def parse_batch(self, raw_ingredients: List[str]) -> List[dict]:
        """Parse all ingredients in ONE LLM call"""

        prompt = f"""
        Parse these recipe ingredients into structured format.

        Ingredients:
        {json.dumps(raw_ingredients, indent=2)}

        For each ingredient, extract:
        - quantity (numeric, use 1 if not specified)
        - unit (cups, tbsp, lb, grams, or "whole" if none)
        - food_name (canonical ingredient name - normalize plurals)
        - preparation (diced, chopped, minced, or null)
        - modifiers (boneless, extra virgin, fresh, etc.)

        Return JSON array:
        [
            {{
                "original": "<original text>",
                "quantity": <number>,
                "unit": "<unit>",
                "food_name": "<name>",
                "preparation": "<method or null>",
                "modifiers": ["<list>"],
                "is_optional": <boolean, true if "optional" mentioned>
            }}
        ]

        Examples:
        "2 cups diced cucumber" →
        {{
            "original": "2 cups diced cucumber",
            "quantity": 2,
            "unit": "cups",
            "food_name": "cucumber",
            "preparation": "diced",
            "modifiers": [],
            "is_optional": false
        }}

        "Salt and pepper to taste" →
        {{
            "original": "Salt and pepper to taste",
            "quantity": 1,
            "unit": "pinch",
            "food_name": "salt and pepper",
            "preparation": null,
            "modifiers": ["to taste"],
            "is_optional": true
        }}
        """

        response = await self.llm.complete(prompt)
        return json.loads(response)
```

**Cost**: One LLM call per recipe (8-12 ingredients average)
- ~800-1200 tokens per batch = $0.002-0.003 per recipe

### Step 3: Convert Units with LLM

```python
class LLMUnitConverter:
    """Convert ingredient units to grams using LLM"""

    async def convert_batch(self, parsed_ingredients: List[dict]) -> List[dict]:
        """Convert all ingredients to grams in ONE LLM call"""

        prompt = f"""
        Convert these ingredient measurements to grams.

        Ingredients:
        {json.dumps([{
            "food_name": ing['food_name'],
            "quantity": ing['quantity'],
            "unit": ing['unit'],
            "preparation": ing['preparation']
        } for ing in parsed_ingredients], indent=2)}

        For each ingredient:
        1. Consider ingredient density (flour ≠ water ≠ chicken)
        2. Use standard conversions (1 cup liquid = 240ml, 1 lb = 454g)
        3. Account for preparation (diced vs whole may affect volume)
        4. Mark confidence (1.0 for exact conversions like lb→g, 0.85-0.95 for volume estimates)

        Return JSON array matching input order:
        [
            {{
                "grams": <number>,
                "confidence": <0.0-1.0>,
                "reasoning": "<brief explanation>"
            }}
        ]

        Examples:
        {{"food_name": "cucumber", "quantity": 2, "unit": "cups", "preparation": "diced"}} →
        {{"grams": 280, "confidence": 0.90, "reasoning": "1 cup diced cucumber ≈ 140g"}}

        {{"food_name": "chicken breast", "quantity": 1, "unit": "lb", "preparation": null}} →
        {{"grams": 454, "confidence": 1.0, "reasoning": "1 pound = 454 grams (exact)"}}

        {{"food_name": "salt", "quantity": 1, "unit": "pinch", "preparation": null}} →
        {{"grams": 0.35, "confidence": 0.80, "reasoning": "1 pinch ≈ 0.35g (estimate)"}}
        """

        response = await self.llm.complete(prompt)
        conversions = json.loads(response)

        # Merge conversions back with parsed ingredients
        result = []
        for ing, conv in zip(parsed_ingredients, conversions):
            result.append({
                **ing,
                'grams': conv['grams'],
                'conversion_confidence': conv['confidence'],
                'conversion_reasoning': conv['reasoning']
            })

        return result
```

**Cost**: One LLM call per recipe
- ~1000-1500 tokens per batch = $0.002-0.004 per recipe

---

## Complete Recipe Processing Pipeline

```python
class RecipeFetcher:
    """Complete pipeline for fetching and processing recipes"""

    def __init__(self):
        self.spoonacular = SpoonacularClient()
        self.parser = LLMIngredientParser()
        self.converter = LLMUnitConverter()
        self.matcher = RAGIngredientMatcher()  # From previous design

    async def fetch_and_process_recipe(
        self,
        recipe_id: int,
        goal_type: GoalType
    ) -> dict:
        """
        Fetch recipe from Spoonacular and process with our LLM pipeline

        Returns:
        {
            'recipe_data': {...},
            'processed_ingredients': [{item_id, quantity_grams, confidence, ...}]
        }
        """

        # Step 1: Fetch from Spoonacular (ONLY for recipe data)
        spoonacular_data = await self.spoonacular.get_recipe_details(recipe_id)

        # Step 2: Parse ingredients with LLM
        parsed_ingredients = await self.parser.parse_batch(
            spoonacular_data['raw_ingredients']
        )

        # Step 3: Convert to grams with LLM
        ingredients_with_grams = await self.converter.convert_batch(
            parsed_ingredients
        )

        # Step 4: Match to items in OUR database with RAG
        matched_ingredients = await self.matcher.match_batch(
            ingredients_with_grams
        )

        # Step 5: Return processed data
        return {
            'recipe_data': {
                'name': spoonacular_data['title'],
                'instructions': spoonacular_data['instructions'],
                'servings': spoonacular_data['servings'],
                'prep_time_minutes': spoonacular_data['ready_in_minutes'],
                'image_url': spoonacular_data['image'],
                'cuisine_tags': spoonacular_data['cuisines'],
                'dietary_tags': spoonacular_data['diets'],
                'goals': [goal_type.value],
                'source': 'spoonacular',
                'spoonacular_id': spoonacular_data['id'],
                'status': 'draft'
            },
            'processed_ingredients': matched_ingredients
        }
```

---

## Cost Comparison

### Per Recipe Processing Cost

**Old Approach (Spoonacular for everything)**:
- Recipe fetch: 1 point
- Ingredient parsing: 1 point
- Ingredient info × 10 ingredients: 10 points
- **Total: 12 Spoonacular points** ≈ included in $29/month plan

**New Approach (LLM for parsing/conversion)**:
- Recipe fetch: 1 Spoonacular point
- Ingredient parsing (LLM): $0.002-0.003
- Unit conversion (LLM): $0.002-0.004
- RAG matching (LLM for 20%): $0.01-0.02
- **Total: 1 Spoonacular point + $0.014-0.027 LLM**

### For 500 Recipes

**Old Approach**:
- 500 recipes × 12 points = 6,000 points
- Need Chef plan ($149/month) for 5,000 points/day
- **Cost: $149/month**

**New Approach**:
- 500 recipes × 1 point = 500 points
- Cook plan ($29/month) gives 500 points/day ✅
- LLM: 500 × $0.02 = $10
- **Cost: $29/month + $10 one-time = $39 total**

**Savings**: $149 vs $39 → **74% cheaper!**

---

## Innovation Summary

### What Spoonacular Provides
- ✅ Constraint-based recipe search (their strength)
- ✅ Recipe metadata (title, instructions, image)
- ✅ Raw ingredient text lists

### What We Build with LLMs
- 🚀 Ingredient parsing (structure extraction)
- 🚀 Unit conversion (any unit → grams)
- 🚀 RAG matching (vector search in our database)
- 🚀 Intelligent seeding (FDC + LLM for missing items)
- 🚀 Confidence tracking (know what's reliable)

### Advantages
- ✅ **74% cost reduction** vs full Spoonacular usage
- ✅ **Flexibility**: Works with ANY recipe source (not locked to Spoonacular)
- ✅ **Accuracy**: LLMs trained on recipe data, understand context
- ✅ **Scalability**: LLM cost decreases over time, Spoonacular is fixed
- ✅ **Innovation**: Our RAG matching, our database, our confidence scoring
- ✅ **Learning**: Can improve parsing/conversion prompts based on feedback

---

## Answers to Your Questions (Final)

### Question 1: Random or Constraint-Based Recipe Fetching?

**CONSTRAINT-BASED using Spoonacular Complex Search** ✅

We use Spoonacular's constraint parameters to fetch recipes that match our optimizer requirements:
- Calorie ranges per goal type
- Macro targets (protein, carbs, fat)
- Dietary preferences (vegan, keto, etc.)
- Cuisine filters for variety
- Prep time limits

### Question 2: Ingredient Standardization?

**HYBRID: Spoonacular for recipes, LLM for everything else** ✅

1. **Spoonacular**: Provides raw ingredient text from recipes
2. **LLM Parsing**: Extracts structure (quantity, unit, food, prep)
3. **LLM Conversion**: Converts any unit to grams (understands density)
4. **RAG Matching**: Matches to items in OUR database (vector + LLM)
5. **FDC Seeding**: Creates missing items with FDC + LLM

**Result**: Standardized ingredients in OUR database, not dependent on Spoonacular IDs

---

## Next Steps - Phase 1 Implementation

### Week 1: Infrastructure
- [ ] Get Spoonacular API key ($29/month Cook plan)
- [ ] Implement SpoonacularClient (minimal - ONLY recipe fetching)
- [ ] Implement LLMIngredientParser
- [ ] Implement LLMUnitConverter
- [ ] Test with 5-10 sample recipes

### Success Criteria
- Recipe fetching works with constraints
- LLM parsing accuracy >95%
- LLM conversion accuracy >90%
- Total cost per recipe <$0.03

Ready to start Phase 1?
