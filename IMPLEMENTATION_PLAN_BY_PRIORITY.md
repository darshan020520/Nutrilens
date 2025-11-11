# Implementation Plan: AI vs Non-AI Breakdown by Priority

## Your Priorities (In Order)

1. **Items Seeding** - Get comprehensive, high-quality items database
2. **Recipe Seeding** - Populate recipes with proper ingredient matching
3. **Vector Embedding Enhancement for Normalizer** - Improve receipt/input matching accuracy
4. **Auto-Addition of Items** - Found from recipe and receipt normalizer
5. **Semantic Search Implementation** - Make search actually useful

---

## PRIORITY 1: Items Seeding

### Goal
Populate database with 500-1000 high-quality food items with accurate nutritional data.

### AI Usage Breakdown

| Step | What We Do | AI Used? | Tool/Method |
|------|------------|----------|-------------|
| **1. Get item list** | Search USDA FDC for common foods | ❌ **NO AI** | USDA FDC REST API |
| **2. Get nutrition data** | Fetch authoritative nutritional values | ❌ **NO AI** | USDA FDC API (lab-tested data) |
| **3. Normalize names** | Convert "Chicken, broilers or fryers..." → "chicken_breast" | ❌ **NO AI** | Python regex + rules |
| **4. Generate embeddings** | Create semantic vectors for each item | ✅ **YES - AI** | OpenAI text-embedding-3-small |
| **5. Store in database** | Save to PostgreSQL | ❌ **NO AI** | SQLAlchemy |

### Implementation

```python
# backend/scripts/seed_items_from_fdc.py

class ItemSeeder:
    def __init__(self):
        self.fdc = FDCService(settings.fdc_api_key)        # ❌ NO AI - REST API
        self.embedder = EmbeddingService(settings.openai_api_key)  # ✅ AI - OpenAI
        self.db = SessionLocal()

    async def seed_category(self, category: str, search_terms: List[str]):
        """
        Seed items for a category (e.g., vegetables, proteins)
        """
        print(f"🌱 Seeding category: {category}")

        all_items = []
        for term in search_terms:
            # Step 1 & 2: Search USDA FDC (NO AI)
            foods = await self.fdc.search_foods(term, page_size=20)

            for food in foods:
                # Get detailed nutrition (NO AI - government database)
                details = await self.fdc.get_food_details(food["fdcId"])
                nutrients = self.fdc.extract_nutrients(details)

                # Step 3: Normalize name (NO AI - rule-based)
                canonical_name = self._normalize_name(food["description"])
                # "Chicken, broilers or fryers, breast, meat only, cooked"
                # → "chicken_breast"

                # Check if already exists
                existing = self.db.query(Item).filter_by(
                    canonical_name=canonical_name
                ).first()
                if existing:
                    continue

                # Step 4: Generate embedding (YES AI - OpenAI)
                embedding_text = f"{food['description']} {category}"
                embedding = await self.embedder.get_embedding(embedding_text)
                # Returns: [0.234, -0.891, 0.456, ..., 0.123] (1536 numbers)

                # Step 5: Create item (NO AI - database insert)
                item = Item(
                    canonical_name=canonical_name,
                    display_name=food["description"],
                    embedding=embedding,  # Store AI-generated vector
                    fdc_id=food["fdcId"],
                    source="usda_fdc",
                    category=category,
                    calories=nutrients["calories"],
                    protein=nutrients["protein"],
                    carbs=nutrients["carbs"],
                    fat=nutrients["fat"],
                    fiber=nutrients.get("fiber"),
                    # All nutrition from USDA (NO AI)
                )

                all_items.append(item)
                print(f"  ✅ {canonical_name} (FDC: {food['fdcId']})")

        # Bulk insert
        self.db.bulk_save_objects(all_items)
        self.db.commit()
        print(f"✅ Seeded {len(all_items)} items in {category}")

    def _normalize_name(self, description: str) -> str:
        """
        Convert USDA FDC description to canonical name
        NO AI - Rule-based transformation
        """
        name = description.lower()

        # Remove USDA-specific suffixes
        name = re.sub(r',.*', '', name)  # Remove everything after first comma

        # Common patterns
        name = name.replace("broilers or fryers", "")
        name = name.replace("raw", "").replace("cooked", "")

        # Convert spaces to underscores
        name = re.sub(r'\s+', '_', name.strip())

        return name

# Usage
async def main():
    seeder = ItemSeeder()

    # Define seeding strategy
    categories = {
        "protein": [
            "chicken", "beef", "pork", "fish", "salmon", "tuna",
            "eggs", "tofu", "tempeh", "seitan"
        ],
        "vegetable": [
            "broccoli", "spinach", "kale", "lettuce", "cucumber",
            "tomato", "carrot", "celery", "bell pepper", "onion",
            "garlic", "ginger", "mushroom", "zucchini", "eggplant",
            "cabbage", "cauliflower", "asparagus", "green beans"
        ],
        "fruit": [
            "apple", "banana", "orange", "strawberry", "blueberry",
            "grape", "mango", "pineapple", "watermelon", "kiwi"
        ],
        "grain": [
            "rice", "pasta", "bread", "oats", "quinoa", "noodles",
            "couscous", "bulgur", "barley", "wheat"
        ],
        "dairy": [
            "milk", "cheese", "yogurt", "butter", "cream", "paneer"
        ],
        "legume": [
            "beans", "lentils", "chickpeas", "peas", "dal", "black beans"
        ],
        "nuts_seeds": [
            "almonds", "walnuts", "cashews", "peanuts", "chia seeds",
            "flax seeds", "sunflower seeds", "pumpkin seeds"
        ],
        "oils_fats": [
            "olive oil", "coconut oil", "butter", "ghee", "avocado oil"
        ],
    }

    for category, search_terms in categories.items():
        await seeder.seed_category(category, search_terms)

    print(f"\n🎉 Item seeding complete!")
```

### Where AI is Used

✅ **AI Component**: Generating embeddings for semantic search
- Input: "chicken breast protein"
- Output: Vector [0.234, -0.891, ..., 0.123]
- Model: OpenAI text-embedding-3-small
- Cost: ~$0.0001 for 1000 items (negligible)

### Where AI is NOT Used

❌ **NO AI**: Everything else
- USDA FDC API calls (REST API)
- Nutritional data (government lab-tested values)
- Name normalization (regex rules)
- Database operations (SQL)

### Output

**500-1000 items with**:
- ✅ Accurate nutrition from USDA
- ✅ AI-generated embeddings for semantic search
- ✅ Proper categorization
- ✅ FDC IDs for traceability

---

## PRIORITY 2: Recipe Seeding

### Goal
Populate database with 100-200 recipes with proper ingredient matching to items.

### AI Usage Breakdown

| Step | What We Do | AI Used? | Tool/Method |
|------|------------|----------|-------------|
| **1. Get recipe data** | Fetch from Spoonacular API | ❌ **NO AI** | Spoonacular REST API |
| **2. Parse ingredients** | Extract food name from "2 cups diced cucumber" | 🟡 **HYBRID** | Regex + LLM fallback |
| **3. Match to items** | Find item in DB using vector similarity | ✅ **YES - AI** | Vector search on embeddings |
| **4. Verify match** | If uncertain, ask LLM to confirm | ✅ **YES - AI** | GPT-4o-mini |
| **5. Create missing items** | If item doesn't exist, auto-create | ✅ **YES - AI** | GPT-4o-mini |
| **6. Generate recipe embedding** | For semantic recipe search | ✅ **YES - AI** | OpenAI embeddings |
| **7. Store recipe** | Save to database | ❌ **NO AI** | SQLAlchemy |

### Implementation

```python
# backend/scripts/seed_recipes.py

class RecipeSeeder:
    def __init__(self):
        self.db = SessionLocal()
        self.spoonacular = SpoonacularService(settings.spoonacular_api_key)  # ❌ NO AI
        self.embedder = EmbeddingService(settings.openai_api_key)  # ✅ AI
        self.matcher = IngredientMatcher(self.db, self.embedder)  # ✅ AI (vector search)
        self.llm_creator = LLMItemCreator(settings.openai_api_key, self.db)  # ✅ AI

    async def seed_recipes(self, cuisines: List[str], recipes_per_cuisine: int = 20):
        """Seed recipes from Spoonacular with intelligent ingredient matching"""

        for cuisine in cuisines:
            print(f"\n🍳 Seeding {cuisine} recipes...")

            # Step 1: Get recipes from Spoonacular (NO AI - REST API)
            recipes_data = await self.spoonacular.search_recipes(
                cuisine=cuisine,
                number=recipes_per_cuisine
            )

            for recipe_data in recipes_data:
                # Step 6: Generate recipe embedding (AI - for semantic search later)
                recipe_embedding = await self.embedder.get_embedding(
                    f"{recipe_data['title']} {cuisine} {' '.join(recipe_data.get('dishTypes', []))}"
                )

                # Create recipe record
                recipe = Recipe(
                    title=recipe_data["title"],
                    description=recipe_data.get("summary", ""),
                    cuisine_type=cuisine,
                    prep_time_min=recipe_data.get("preparationMinutes", 0),
                    cook_time_min=recipe_data.get("cookingMinutes", 0),
                    servings=recipe_data.get("servings", 4),
                    embedding=recipe_embedding,  # Store AI-generated vector
                    source="spoonacular",
                    external_id=str(recipe_data["id"])
                )
                self.db.add(recipe)
                self.db.flush()

                # Process ingredients with AI-powered matching
                print(f"  📝 {recipe.title}")
                for ingredient in recipe_data.get("extendedIngredients", []):
                    ingredient_text = ingredient["original"]
                    # Example: "2 cups diced cucumber"

                    # Step 2-5: Parse, match, verify, create (AI components)
                    matched_item, confidence = await self.matcher.match_ingredient(
                        ingredient_text
                    )

                    # Create recipe-ingredient link
                    recipe_ingredient = RecipeIngredient(
                        recipe_id=recipe.id,
                        item_id=matched_item.id,
                        quantity_grams=self._convert_to_grams(
                            ingredient.get("amount", 0),
                            ingredient.get("unit", "grams")
                        ),
                        original_ingredient_text=ingredient_text,
                        normalized_confidence=confidence
                    )
                    self.db.add(recipe_ingredient)

                    print(f"    ✅ {ingredient_text} → {matched_item.canonical_name} ({confidence:.2f})")

                self.db.commit()


class IngredientMatcher:
    """Match recipe ingredients to items using AI-powered vector search"""

    def __init__(self, db: Session, embedder: EmbeddingService):
        self.db = db
        self.embedder = embedder
        self.llm_creator = LLMItemCreator(settings.openai_api_key, db, embedder)

    async def match_ingredient(self, ingredient_text: str) -> Tuple[Item, float]:
        """
        Match recipe ingredient to item in database

        Args:
            ingredient_text: "2 cups diced cucumber"

        Returns:
            (matched_item, confidence_score)
        """

        # Step 2: Parse ingredient (HYBRID - Regex first, LLM fallback)
        parsed = await self._parse_ingredient(ingredient_text)
        # Result: {"food": "cucumber", "quantity": 2, "unit": "cups", "prep": "diced"}

        food_name = parsed["food"]

        # Step 3: Vector search (AI - semantic similarity)
        query_embedding = await self.embedder.get_embedding(food_name)

        # Search items using vector similarity
        results = self.db.execute(text("""
            SELECT id, canonical_name, display_name,
                   1 - (embedding <=> :query_embedding::vector) as similarity
            FROM items
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_embedding::vector
            LIMIT 5
        """), {"query_embedding": str(query_embedding)}).fetchall()

        if not results:
            # Step 5: No items exist - create with LLM (AI)
            print(f"    🆕 Creating missing item: {food_name}")
            new_item = await self.llm_creator.create_missing_item(food_name)
            return (new_item, 0.95)

        best_match = results[0]

        # Step 4: High confidence match (AI-based vector similarity)
        if best_match.similarity > 0.85:
            item = self.db.query(Item).get(best_match.id)
            return (item, best_match.similarity)

        # Step 4: Medium confidence - verify with LLM (AI)
        if 0.60 <= best_match.similarity < 0.85:
            verified_item = await self._llm_verify_match(food_name, results[:3])
            if verified_item:
                return (verified_item, 0.90)

        # Step 5: Low confidence - create new item (AI)
        print(f"    ⚠️  Low confidence ({best_match.similarity:.2f}), creating: {food_name}")
        new_item = await self.llm_creator.create_missing_item(food_name)
        return (new_item, 0.95)

    async def _parse_ingredient(self, text: str) -> Dict:
        """
        Parse ingredient text
        HYBRID: Regex patterns first, LLM fallback for complex cases
        """

        # Try regex patterns first (NO AI - fast and free)
        simple_pattern = r'^(\d+\.?\d*)\s+(\w+)\s+(.+)$'
        match = re.match(simple_pattern, text.lower())

        if match:
            quantity, unit, food = match.groups()
            # Remove preparation words
            food = re.sub(r'\b(fresh|frozen|chopped|diced|sliced|minced)\b', '', food).strip()
            return {
                "quantity": float(quantity),
                "unit": unit,
                "food": food,
                "prep": []
            }

        # Complex case - use LLM (AI)
        prompt = f"""Parse this ingredient: "{text}"

Return JSON:
{{
  "food": "main ingredient name",
  "quantity": number,
  "unit": "grams/cups/pieces/etc",
  "prep": ["preparation methods"]
}}"""

        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    async def _llm_verify_match(self, ingredient: str, candidates: List) -> Optional[Item]:
        """
        Use LLM to verify if top candidate is correct match
        AI: GPT-4o-mini reasoning
        """
        candidate_names = [c.canonical_name for c in candidates]

        prompt = f"""Does the ingredient "{ingredient}" match any of these items?

Items:
{json.dumps(candidate_names, indent=2)}

Return the best match or null if none match.
JSON only: {{"match": "item_name" or null}}"""

        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        if result["match"]:
            return self.db.query(Item).filter_by(
                canonical_name=result["match"]
            ).first()

        return None


# Usage
async def main():
    seeder = RecipeSeeder()

    cuisines = [
        "Italian", "Mexican", "Indian", "Chinese", "Japanese",
        "Mediterranean", "Thai", "American", "French", "Greek"
    ]

    await seeder.seed_recipes(cuisines, recipes_per_cuisine=20)
    # Total: 10 cuisines × 20 recipes = 200 recipes
```

### Where AI is Used

✅ **AI Components**:
1. **Vector search** - Find similar items using embeddings
2. **LLM verification** - Confirm ambiguous matches
3. **LLM item creation** - Auto-create missing items
4. **Recipe embeddings** - For semantic recipe search

### Where AI is NOT Used

❌ **NO AI**:
- Spoonacular API calls (REST API)
- Simple regex parsing (fast, free)
- Database operations (SQL)

### Output

**100-200 recipes with**:
- ✅ All ingredients matched to items (via AI vector search)
- ✅ Missing items auto-created (via AI)
- ✅ Recipe embeddings for semantic search
- ✅ High confidence ingredient matching

---

## PRIORITY 3: Vector Embedding Enhancement for Normalizer

### Goal
Improve receipt/input matching accuracy from 60% to 90%+ using vector embeddings.

### AI Usage Breakdown

| Step | What We Do | AI Used? | Tool/Method |
|------|------------|----------|-------------|
| **1. Exact match check** | Check if input exactly matches canonical_name | ❌ **NO AI** | String equality |
| **2. Alias check** | Check if input in aliases array | ❌ **NO AI** | Array membership |
| **3. Vector search** | Find semantically similar items | ✅ **YES - AI** | Cosine similarity on embeddings |
| **4. LLM verification** | If uncertain, ask LLM to confirm | ✅ **YES - AI** | GPT-4o-mini |
| **5. Auto-create item** | If no match, create new item | ✅ **YES - AI** | GPT-4o-mini |

### Implementation

```python
# backend/app/services/item_normalizer.py (UPDATED)

class VectorEnhancedNormalizer:
    """
    Enhanced normalizer using vector embeddings for semantic matching
    """

    def __init__(self, db: Session, embedder: EmbeddingService, llm_creator: LLMItemCreator):
        self.db = db
        self.embedder = embedder
        self.llm_creator = llm_creator

        # Cache all items for fast lookups (NO AI)
        self.items_cache = self._build_cache()

    def _build_cache(self) -> Dict:
        """Build in-memory cache for fast exact/alias matching (NO AI)"""
        items = self.db.query(Item).all()

        cache = {
            "by_name": {},      # canonical_name → Item
            "by_alias": {},     # alias → Item
        }

        for item in items:
            cache["by_name"][item.canonical_name] = item
            for alias in item.aliases or []:
                cache["by_alias"][alias.lower()] = item

        return cache

    async def normalize(self, item_name: str, quantity: float = None, unit: str = None) -> NormalizeResult:
        """
        Normalize item with cascading fallbacks

        Args:
            item_name: "herb mint" or "Celery" or "japanese pumpkin"
            quantity: 100
            unit: "grams"

        Returns:
            NormalizeResult with matched item and confidence
        """

        item_name_lower = item_name.lower().strip()

        # ========================================
        # STEP 1: Exact match (NO AI - fastest)
        # ========================================
        if item_name_lower in self.items_cache["by_name"]:
            print(f"✅ Exact match: {item_name} → {item_name_lower}")
            return NormalizeResult(
                item=self.items_cache["by_name"][item_name_lower],
                confidence=1.0,
                matched_on="exact",
                quantity_grams=self._convert_to_grams(quantity, unit)
            )

        # ========================================
        # STEP 2: Alias match (NO AI - fast)
        # ========================================
        if item_name_lower in self.items_cache["by_alias"]:
            matched_item = self.items_cache["by_alias"][item_name_lower]
            print(f"✅ Alias match: {item_name} → {matched_item.canonical_name}")
            return NormalizeResult(
                item=matched_item,
                confidence=0.98,
                matched_on="alias",
                quantity_grams=self._convert_to_grams(quantity, unit)
            )

        # ========================================
        # STEP 3: Vector search (AI - semantic)
        # ========================================
        print(f"🔍 Vector search for: {item_name}")
        query_embedding = await self.embedder.get_embedding(item_name_lower)

        results = self.db.execute(text("""
            SELECT id, canonical_name, display_name,
                   1 - (embedding <=> :query_embedding::vector) as similarity
            FROM items
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_embedding::vector
            LIMIT 5
        """), {"query_embedding": str(query_embedding)}).fetchall()

        if not results:
            # No items in database - create new (AI)
            print(f"🆕 No items exist, creating: {item_name}")
            new_item = await self.llm_creator.create_missing_item(item_name)
            return NormalizeResult(
                item=new_item,
                confidence=0.95,
                matched_on="llm_created",
                quantity_grams=self._convert_to_grams(quantity, unit)
            )

        best_match = results[0]
        print(f"   Top match: {best_match.canonical_name} ({best_match.similarity:.2f})")

        # High confidence vector match (AI-based similarity)
        if best_match.similarity > 0.85:
            item = self.db.query(Item).get(best_match.id)
            print(f"✅ High confidence vector match: {item_name} → {item.canonical_name}")
            return NormalizeResult(
                item=item,
                confidence=best_match.similarity,
                matched_on="vector_high",
                quantity_grams=self._convert_to_grams(quantity, unit)
            )

        # ========================================
        # STEP 4: LLM verification (AI - reasoning)
        # ========================================
        if 0.60 <= best_match.similarity < 0.85:
            print(f"🤔 Medium confidence, verifying with LLM...")
            verified_item = await self._llm_verify(item_name, results[:3])

            if verified_item:
                print(f"✅ LLM verified: {item_name} → {verified_item.canonical_name}")
                return NormalizeResult(
                    item=verified_item,
                    confidence=0.90,
                    matched_on="vector_llm_verified",
                    quantity_grams=self._convert_to_grams(quantity, unit)
                )

        # ========================================
        # STEP 5: Auto-create missing item (AI)
        # ========================================
        print(f"🆕 Low confidence ({best_match.similarity:.2f}), creating: {item_name}")
        new_item = await self.llm_creator.create_missing_item(item_name)
        return NormalizeResult(
            item=new_item,
            confidence=0.95,
            matched_on="llm_created",
            quantity_grams=self._convert_to_grams(quantity, unit)
        )

    async def normalize_batch(self, items: List[Dict]) -> List[NormalizeResult]:
        """
        Batch normalize items (for receipt scanning)
        Optimized: Group LLM calls to reduce API requests
        """
        results = []
        llm_batch = []

        for item in items:
            item_name = item.get("item_name", "")

            # Try fast paths first (NO AI)
            result = await self.normalize(
                item_name,
                item.get("quantity"),
                item.get("unit")
            )

            results.append(result)

        return results

    async def _llm_verify(self, item_name: str, candidates: List) -> Optional[Item]:
        """
        Ask LLM to verify if candidate is correct match
        AI: GPT-4o-mini reasoning
        """
        candidate_info = [
            f"- {c.canonical_name} (similarity: {c.similarity:.2f})"
            for c in candidates
        ]

        prompt = f"""Does the item "{item_name}" match any of these?

{chr(10).join(candidate_info)}

Consider:
- Semantic similarity
- Common food names
- Possible typos

Return JSON: {{"match": "canonical_name" or null, "reason": "brief explanation"}}"""

        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        if result["match"]:
            print(f"   LLM reason: {result['reason']}")
            return self.db.query(Item).filter_by(
                canonical_name=result["match"]
            ).first()

        return None

    def _convert_to_grams(self, quantity: float, unit: str) -> float:
        """Convert quantity to grams (NO AI - rule-based)"""
        if not quantity or not unit:
            return 0.0

        unit = unit.lower()

        # Standard conversions
        conversions = {
            "kg": 1000,
            "g": 1,
            "grams": 1,
            "lb": 453.592,
            "oz": 28.3495,
            # Volume to mass (approximate)
            "cup": 240,   # ~240g for water-like liquids
            "ml": 1,      # ~1g for water
            "l": 1000,
            "tbsp": 15,
            "tsp": 5,
        }

        return quantity * conversions.get(unit, 1)


# Update inventory service to use new normalizer
class IntelligentInventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.embedder = EmbeddingService(settings.openai_api_key)
        self.llm_creator = LLMItemCreator(settings.openai_api_key, db, self.embedder)
        self.normalizer = VectorEnhancedNormalizer(db, self.embedder, self.llm_creator)

    async def process_receipt_items(
        self,
        user_id: int,
        receipt_items: List[Dict],
        auto_add_threshold: float = 0.75
    ) -> Dict:
        """Process receipt items with vector-enhanced normalizer"""

        # Use AI-enhanced normalizer
        normalized_results = await self.normalizer.normalize_batch(receipt_items)

        auto_added = []
        needs_confirmation = []

        for result in normalized_results:
            if result.confidence >= auto_add_threshold and result.item:
                # Auto-add to inventory
                self._add_to_inventory(user_id, result)
                auto_added.append({
                    "item_name": result.item.canonical_name,
                    "confidence": result.confidence,
                    "matched_on": result.matched_on
                })
            else:
                needs_confirmation.append({
                    "item_name": result.item.canonical_name if result.item else "unknown",
                    "confidence": result.confidence,
                    "matched_on": result.matched_on
                })

        return {
            "auto_added": auto_added,
            "needs_confirmation": needs_confirmation
        }
```

### Where AI is Used

✅ **AI Components**:
1. **Vector search** (Step 3) - Semantic similarity using embeddings
2. **LLM verification** (Step 4) - Confirm uncertain matches
3. **LLM creation** (Step 5) - Auto-create missing items

### Where AI is NOT Used

❌ **NO AI**:
- Exact matching (string equality)
- Alias matching (array lookup)
- Unit conversion (math formulas)

### Performance Characteristics

| Method | Speed | Cost | Accuracy |
|--------|-------|------|----------|
| Exact match | <1ms | Free | 100% |
| Alias match | <1ms | Free | 100% |
| Vector search | ~50ms | $0.00002/query | 90%+ |
| LLM verify | ~500ms | $0.0003/query | 95%+ |
| LLM create | ~1000ms | $0.0003/item | 90%+ |

**Real-world receipt (20 items)**:
- 15 items: Exact/alias match → 15ms total, FREE ✅
- 3 items: Vector search → 150ms total, $0.00006 ✅
- 2 items: LLM create → 2000ms total, $0.0006 ✅
- **Total: ~2.2 seconds, $0.00066 per receipt** ✅

---

## PRIORITY 4: Auto-Addition of Items

### Goal
Automatically create items found from recipe and receipt normalizer without manual intervention.

### AI Usage Breakdown

| Step | What We Do | AI Used? | Tool/Method |
|------|------------|----------|-------------|
| **1. Detect missing item** | Check if item exists in DB | ❌ **NO AI** | Database query |
| **2. Generate item details** | Create canonical_name, category, nutrition | ✅ **YES - AI** | GPT-4o-mini |
| **3. Generate embedding** | Create vector for new item | ✅ **YES - AI** | OpenAI embeddings |
| **4. Store in database** | Save new item | ❌ **NO AI** | SQLAlchemy |
| **5. Audit/review (optional)** | Flag for human review | ❌ **NO AI** | Database flag |

### Implementation

```python
# backend/app/services/llm_item_creator.py

class LLMItemCreator:
    """
    Auto-create missing food items using LLM
    AI-POWERED: Uses GPT-4o-mini for nutritional estimates
    """

    def __init__(self, api_key: str, db: Session, embedder: EmbeddingService):
        self.client = openai.OpenAI(api_key=api_key)
        self.db = db
        self.embedder = embedder

    async def create_missing_item(
        self,
        item_name: str,
        context: str = "",
        require_review: bool = False
    ) -> Item:
        """
        Create a new item using LLM

        Args:
            item_name: "Japanese Pumpkin" or "Herb Mint"
            context: Optional context (e.g., "Found in grocery receipt")
            require_review: Flag for human review queue

        Returns:
            New Item object
        """

        print(f"🤖 LLM creating item: {item_name}")

        # Step 1: Already know item doesn't exist (NO AI - caller checked)

        # Step 2: Generate item details (AI - GPT-4o-mini)
        prompt = f"""You are a nutrition database expert. Create a food item entry for "{item_name}".

Context: {context if context else "User input from receipt/recipe"}

Provide:
1. canonical_name (lowercase, underscores, concise, e.g., "japanese_pumpkin")
2. display_name (proper capitalization for UI, e.g., "Japanese Pumpkin")
3. category (MUST be one of: protein, vegetable, fruit, grain, dairy, legume, nuts_seeds, oils_fats, spices, beverages)
4. aliases (list of common alternative names)
5. Nutritional values PER 100 GRAMS:
   - calories (kcal)
   - protein (g)
   - carbs (g)
   - fat (g)
   - fiber (g)
   - sugar (g)
   - sodium (mg)

Use USDA-level accuracy. If uncertain, use typical values for similar foods.
For "herb mint", recognize it as regular mint.
For obscure items, make educated estimates based on similar foods.

Return ONLY valid JSON:
{{
  "canonical_name": "japanese_pumpkin",
  "display_name": "Japanese Pumpkin (Kabocha)",
  "category": "vegetable",
  "aliases": ["kabocha", "kabocha squash", "japanese squash"],
  "calories": 34,
  "protein": 1.6,
  "carbs": 8.1,
  "fat": 0.1,
  "fiber": 1.2,
  "sugar": 3.5,
  "sodium": 2
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3  # Lower temperature for consistent nutritional data
        )

        data = json.loads(response.choices[0].message.content)

        print(f"   LLM response: {data['canonical_name']} ({data['category']})")

        # Validate required fields
        required_fields = ["canonical_name", "display_name", "category", "calories", "protein", "carbs", "fat"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"LLM response missing required field: {field}")

        # Step 3: Generate embedding (AI - OpenAI embeddings)
        embedding_text = f"{data['display_name']} {data['category']}"
        if data.get('aliases'):
            embedding_text += f" {' '.join(data['aliases'][:3])}"  # Include top 3 aliases

        embedding = await self.embedder.get_embedding(embedding_text)

        # Step 4: Create item (NO AI - database insert)
        item = Item(
            canonical_name=data["canonical_name"],
            display_name=data.get("display_name", data["canonical_name"]),
            category=data["category"],
            aliases=data.get("aliases", []),
            embedding=embedding,
            source="llm_created",
            nutrition_per_100g={
                "calories": data["calories"],
                "protein_g": data["protein"],
                "carbs_g": data["carbs"],
                "fat_g": data["fat"],
                "fiber_g": data.get("fiber", 0),
                "sugar_g": data.get("sugar", 0),
                "sodium_mg": data.get("sodium", 0),
            },
            fdc_id=None,  # LLM-created items don't have FDC ID
            is_staple=False,
            embedding_model="text-embedding-3-small",
            embedding_version=1,
        )

        # Step 5: Audit trail (NO AI - database flag)
        if require_review:
            # Could add to review queue table
            print(f"   ⚠️  Flagged for review: {item.canonical_name}")

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        print(f"   ✅ Created: {item.canonical_name} (ID: {item.id})")

        return item

    async def create_missing_items_batch(self, item_names: List[str]) -> List[Item]:
        """
        Create multiple items efficiently
        Optimizes LLM calls by batching prompts
        """

        # Create single prompt for multiple items (AI - more efficient)
        prompt = f"""Create food item entries for these items: {', '.join(item_names)}

For EACH item, provide the same fields as before.

Return JSON array:
[
  {{"canonical_name": "...", "display_name": "...", ...}},
  {{"canonical_name": "...", "display_name": "...", ...}}
]"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        items_data = json.loads(response.choices[0].message.content)

        # Generate embeddings in batch (AI - faster)
        embedding_texts = [
            f"{item['display_name']} {item['category']}"
            for item in items_data
        ]
        embeddings = await self.embedder.get_embeddings_batch(embedding_texts)

        # Create all items
        new_items = []
        for item_data, embedding in zip(items_data, embeddings):
            item = Item(
                canonical_name=item_data["canonical_name"],
                embedding=embedding,
                source="llm_created",
                # ... rest of fields
            )
            self.db.add(item)
            new_items.append(item)

        self.db.commit()

        return new_items


# Optional: Review queue for LLM-created items
class ItemReviewQueue:
    """
    Human review system for AI-generated items
    NO AI - Just database tracking
    """

    def __init__(self, db: Session):
        self.db = db

    def get_pending_reviews(self) -> List[Item]:
        """Get items needing review (NO AI)"""
        return self.db.query(Item).filter(
            Item.source == "llm_created",
            Item.reviewed == False
        ).all()

    def approve_item(self, item_id: int, reviewer_notes: str = "") -> Item:
        """Approve LLM-created item (NO AI)"""
        item = self.db.query(Item).get(item_id)
        item.reviewed = True
        item.reviewer_notes = reviewer_notes
        self.db.commit()
        return item

    def reject_item(self, item_id: int, reason: str) -> None:
        """Reject and delete item (NO AI)"""
        item = self.db.query(Item).get(item_id)
        self.db.delete(item)
        self.db.commit()
```

### Where AI is Used

✅ **AI Components**:
1. **LLM item generation** - GPT-4o-mini creates item details
2. **Embedding generation** - OpenAI creates vector for new item

### Where AI is NOT Used

❌ **NO AI**:
- Database existence check
- Database insert operations
- Review queue management

### Auto-Creation Examples

**Example 1: Receipt Scanner**
```
Receipt: "Japanese Pumpkin"
→ Not in DB
→ LLM creates:
   {
     "canonical_name": "japanese_pumpkin",
     "category": "vegetable",
     "calories": 34,
     "protein": 1.6,
     ...
   }
→ Item saved with source="llm_created"
→ Available immediately for future receipts
```

**Example 2: Recipe Ingredient**
```
Recipe: "2 cups kabocha squash, diced"
→ "kabocha squash" not in DB
→ LLM creates item
→ Recipe linked to new item
→ Next recipe with kabocha: matches immediately
```

### Quality Control

**Accuracy expectations**:
- Common foods (chicken, rice, apple): ~98% accurate
- Ethnic foods (kabocha, gobo): ~90% accurate
- Processed foods (specific brands): ~85% accurate

**Safety measures**:
1. ✅ LLM uses conservative estimates
2. ✅ All items flagged with source="llm_created"
3. ✅ Optional human review queue
4. ✅ Users can report incorrect data

---

## PRIORITY 5: Semantic Search Implementation

### Goal
Enable powerful, Google-like search for recipes and items that understands intent, not just keywords.

### AI Usage Breakdown

| Step | What We Do | AI Used? | Tool/Method |
|------|------------|----------|-------------|
| **1. Convert query to embedding** | "healthy chicken dinner" → vector | ✅ **YES - AI** | OpenAI embeddings |
| **2. Vector search** | Find similar recipes/items | ✅ **YES - AI** | Cosine similarity |
| **3. Keyword filter (optional)** | Apply category/tag filters | ❌ **NO AI** | SQL WHERE clause |
| **4. Rerank results** | Sort by relevance + metadata | 🟡 **HYBRID** | Vector similarity + rules |
| **5. Return results** | Format for frontend | ❌ **NO AI** | JSON serialization |

### Implementation

```python
# backend/app/api/search.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from app.services.embedding_service import EmbeddingService

router = APIRouter()

class SemanticSearchService:
    """
    AI-powered semantic search for recipes and items
    """

    def __init__(self, db: Session, embedder: EmbeddingService):
        self.db = db
        self.embedder = embedder

    async def search_recipes(
        self,
        query: str,
        limit: int = 20,
        cuisine: str = None,
        max_prep_time: int = None,
        dietary_tags: List[str] = None
    ) -> List[Dict]:
        """
        Semantic search for recipes

        Examples:
        - "quick healthy dinner" → Returns high-protein, low-prep recipes
        - "comfort food pasta" → Returns Italian pasta dishes
        - "meal prep chicken" → Returns batch-cookable chicken recipes
        """

        print(f"🔍 Semantic search: '{query}'")

        # Step 1: Convert query to embedding (AI - OpenAI)
        query_embedding = await self.embedder.get_embedding(query)

        # Step 2: Vector search (AI - semantic similarity)
        # Step 3: Apply filters (NO AI - SQL filters)

        filters = ["embedding IS NOT NULL"]
        params = {"query_embedding": str(query_embedding), "limit": limit}

        if cuisine:
            filters.append("cuisine = :cuisine")
            params["cuisine"] = cuisine

        if max_prep_time:
            filters.append("prep_time_min <= :max_prep_time")
            params["max_prep_time"] = max_prep_time

        if dietary_tags:
            # Filter recipes that have ANY of the dietary tags
            filters.append("dietary_tags && :dietary_tags")
            params["dietary_tags"] = dietary_tags

        where_clause = " AND ".join(filters)

        # Hybrid search: Vector similarity + metadata filters
        sql = f"""
            SELECT
                id,
                title,
                description,
                cuisine,
                prep_time_min,
                cook_time_min,
                macros_per_serving,
                suitable_meal_times,
                dietary_tags,
                1 - (embedding <=> :query_embedding::vector) as similarity
            FROM recipes
            WHERE {where_clause}
            ORDER BY embedding <=> :query_embedding::vector
            LIMIT :limit
        """

        results = self.db.execute(text(sql), params).fetchall()

        # Step 4: Rerank (HYBRID - AI similarity + manual boosts)
        ranked_results = []
        for row in results:
            recipe = dict(row._mapping)

            # Base score from AI similarity
            score = recipe["similarity"]

            # Boost for exact keyword matches (NO AI)
            query_lower = query.lower()
            if query_lower in recipe["title"].lower():
                score += 0.1
            if query_lower in (recipe["description"] or "").lower():
                score += 0.05

            # Boost for meal time relevance (NO AI - rule-based)
            current_hour = datetime.now().hour
            if 6 <= current_hour < 11 and "breakfast" in recipe["suitable_meal_times"]:
                score += 0.05
            elif 11 <= current_hour < 16 and "lunch" in recipe["suitable_meal_times"]:
                score += 0.05
            elif 16 <= current_hour < 22 and "dinner" in recipe["suitable_meal_times"]:
                score += 0.05

            recipe["final_score"] = score
            ranked_results.append(recipe)

        # Sort by final score
        ranked_results.sort(key=lambda x: x["final_score"], reverse=True)

        # Step 5: Format results (NO AI)
        return ranked_results

    async def search_items(
        self,
        query: str,
        limit: int = 20,
        category: str = None
    ) -> List[Dict]:
        """
        Semantic search for food items

        Examples:
        - "healthy protein" → chicken_breast, tofu, fish
        - "breakfast carbs" → oats, whole_wheat_bread, banana
        - "green vegetables" → spinach, broccoli, kale
        """

        # Step 1: Embedding (AI)
        query_embedding = await self.embedder.get_embedding(query)

        # Step 2-3: Vector search + filters (AI + SQL)
        filters = ["embedding IS NOT NULL"]
        params = {"query_embedding": str(query_embedding), "limit": limit}

        if category:
            filters.append("category = :category")
            params["category"] = category

        where_clause = " AND ".join(filters)

        sql = f"""
            SELECT
                id,
                canonical_name,
                display_name,
                category,
                nutrition_per_100g,
                source,
                1 - (embedding <=> :query_embedding::vector) as similarity
            FROM items
            WHERE {where_clause}
            ORDER BY embedding <=> :query_embedding::vector
            LIMIT :limit
        """

        results = self.db.execute(text(sql), params).fetchall()

        # Step 4: Rerank (HYBRID)
        ranked_results = []
        for row in results:
            item = dict(row._mapping)

            score = item["similarity"]

            # Boost USDA items over LLM-created (reliability)
            if item["source"] == "usda_fdc":
                score += 0.05

            # Boost for category match in query
            if category and item["category"] == category:
                score += 0.1

            item["final_score"] = score
            ranked_results.append(item)

        ranked_results.sort(key=lambda x: x["final_score"], reverse=True)

        return ranked_results

    async def find_similar_recipes(self, recipe_id: int, limit: int = 10) -> List[Dict]:
        """
        Find recipes similar to a given recipe
        AI: Pure vector similarity

        Use case: "Show me recipes similar to this one"
        """

        # Get source recipe embedding
        source_recipe = self.db.query(Recipe).get(recipe_id)
        if not source_recipe or not source_recipe.embedding:
            return []

        # Find similar recipes (AI - vector search)
        sql = """
            SELECT
                id, title, cuisine, macros_per_serving,
                1 - (embedding <=> :source_embedding::vector) as similarity
            FROM recipes
            WHERE id != :recipe_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :source_embedding::vector
            LIMIT :limit
        """

        results = self.db.execute(text(sql), {
            "source_embedding": str(source_recipe.embedding),
            "recipe_id": recipe_id,
            "limit": limit
        }).fetchall()

        return [dict(row._mapping) for row in results]


# API endpoints
@router.get("/search/recipes")
async def search_recipes_endpoint(
    q: str = Query(..., description="Search query"),
    limit: int = 20,
    cuisine: str = None,
    max_prep_time: int = None,
    dietary_tags: List[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Semantic recipe search

    Examples:
    - GET /search/recipes?q=quick healthy dinner
    - GET /search/recipes?q=pasta&cuisine=Italian&max_prep_time=30
    - GET /search/recipes?q=high protein&dietary_tags=vegetarian
    """
    embedder = EmbeddingService(settings.openai_api_key)
    search_service = SemanticSearchService(db, embedder)

    results = await search_service.search_recipes(
        query=q,
        limit=limit,
        cuisine=cuisine,
        max_prep_time=max_prep_time,
        dietary_tags=dietary_tags
    )

    return {
        "query": q,
        "count": len(results),
        "results": results
    }


@router.get("/search/items")
async def search_items_endpoint(
    q: str = Query(..., description="Search query"),
    limit: int = 20,
    category: str = None,
    db: Session = Depends(get_db)
):
    """
    Semantic item search

    Examples:
    - GET /search/items?q=healthy protein
    - GET /search/items?q=green vegetables&category=vegetable
    """
    embedder = EmbeddingService(settings.openai_api_key)
    search_service = SemanticSearchService(db, embedder)

    results = await search_service.search_items(
        query=q,
        limit=limit,
        category=category
    )

    return {
        "query": q,
        "count": len(results),
        "results": results
    }


@router.get("/recipes/{recipe_id}/similar")
async def find_similar_recipes_endpoint(
    recipe_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Find recipes similar to a given recipe"""
    embedder = EmbeddingService(settings.openai_api_key)
    search_service = SemanticSearchService(db, embedder)

    results = await search_service.find_similar_recipes(recipe_id, limit)

    return {
        "recipe_id": recipe_id,
        "similar_recipes": results
    }
```

### Where AI is Used

✅ **AI Components**:
1. **Query embedding** - Convert search text to vector
2. **Vector similarity** - Find semantically similar items/recipes
3. **Semantic understanding** - "quick healthy dinner" matches relevant recipes

### Where AI is NOT Used

❌ **NO AI**:
- SQL filtering (cuisine, prep time, etc.)
- Keyword boosting (exact matches)
- Time-based relevance (breakfast in morning)
- Result formatting

### Semantic Search Examples

**Example 1: Recipe Search**
```
Query: "quick healthy dinner"

Traditional search (keyword):
- Matches: Recipes with "quick" OR "healthy" OR "dinner" in title
- Misses: "Fast nutritious evening meal" (different words, same meaning)

Semantic search (AI):
- Finds: All high-protein, low-prep, dinner recipes
- Matches: "30-Min Grilled Chicken", "Easy Salmon Bowl", "Quick Tofu Stir-Fry"
- Understands: "quick" = fast/easy, "healthy" = nutritious, "dinner" = evening meal
```

**Example 2: Item Search**
```
Query: "breakfast protein"

Traditional search:
- Matches: Items with "breakfast" OR "protein" in name
- Results: Random protein items

Semantic search (AI):
- Understands: Looking for protein-rich foods suitable for breakfast
- Results: eggs, greek_yogurt, protein_powder, turkey_bacon
- Filters out: chicken_breast (dinner protein), protein_bars (snack)
```

**Example 3: Similar Recipes**
```
Input: "Greek Salad" recipe

Semantic search finds similar:
- Mediterranean Quinoa Bowl (0.92 similarity)
- Caprese Salad (0.88 similarity)
- Tabbouleh (0.85 similarity)

Why? All are:
- Fresh, vegetable-based
- Mediterranean cuisine
- Light, healthy
- Similar preparation
```

### Performance

| Search Type | Speed | Cost | Accuracy |
|-------------|-------|------|----------|
| Keyword search | ~10ms | Free | 60% |
| Semantic search | ~50ms | $0.00002/query | 90%+ |
| Similar items | ~30ms | Free* | 95% |

*No embedding needed for similar items (uses existing recipe embedding)

---

## Summary: AI vs Non-AI Usage

### Overall AI Distribution

| Priority | AI Usage | Non-AI Usage | Primary Benefit |
|----------|----------|--------------|-----------------|
| **1. Items Seeding** | 10% (embeddings only) | 90% (USDA API, rules) | ✅ Enables semantic search |
| **2. Recipe Seeding** | 40% (matching, creation) | 60% (Spoonacular API) | ✅ Auto-matches ingredients |
| **3. Normalizer Enhancement** | 30% (vector search, LLM) | 70% (exact/alias matching) | ✅ 90%+ accuracy |
| **4. Auto Item Creation** | 100% (LLM generation) | 0% | ✅ Self-healing database |
| **5. Semantic Search** | 80% (embeddings, similarity) | 20% (filters) | ✅ Google-like search |

### AI Cost Breakdown

**One-time seeding** (1000 items, 200 recipes):
- Item embeddings: $0.0001
- Recipe embeddings: $0.0002
- Recipe matching: $0.05
- **Total: ~$0.05**

**Monthly operational** (1000 users, 1000 receipts):
- Receipt normalizer: $0.002
- LLM item creation: $0.03
- Semantic search: $0.01
- **Total: ~$0.042/month**

**Cost per user**: ~$0.00004/month (negligible)

### When We Use AI

✅ **Use AI when**:
1. Semantic understanding needed ("herb mint" = "mint")
2. Ambiguity exists (is this cucumber or zucchini?)
3. Data missing (create new item)
4. User intent matters ("healthy dinner" search)

❌ **Don't use AI when**:
1. Exact match possible (faster, free)
2. Authoritative data available (USDA > LLM)
3. Simple rules work (unit conversion)
4. Speed critical (caching, exact lookups)

---

## Implementation Timeline

### Week 1: Foundation
- Day 1-2: Database migrations (pgvector, embedding columns)
- Day 3: EmbeddingService, FDCService
- Day 4-5: Item seeding script (Priority 1)
- **Deliverable**: 500-1000 items with embeddings

### Week 2: Recipes & Normalizer
- Day 6-7: Recipe seeding (Priority 2)
- Day 8-9: Vector-enhanced normalizer (Priority 3)
- Day 10: LLM item creator (Priority 4)
- **Deliverable**: 200 recipes, working normalizer

### Week 3: Search & Polish
- Day 11-12: Semantic search (Priority 5)
- Day 13-14: Testing, optimization
- Day 15: Documentation, deployment
- **Deliverable**: Full semantic search, production-ready

---

**This plan makes it crystal clear where AI adds value and where traditional methods are better. Ready to start with Priority 1?**
