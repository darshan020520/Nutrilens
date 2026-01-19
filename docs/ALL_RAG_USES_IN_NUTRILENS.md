# All RAG & Embeddings Usage in NutriLens

**Date**: 2025-11-25
**Purpose**: Complete overview of where and how RAG/embeddings are used across the entire project
**Requested By**: User

---

## 📊 Executive Summary

NutriLens uses **RAG (Retrieval-Augmented Generation) with embeddings** in **5 main areas**:

| # | Use Case | RAG Used? | Embeddings? | LLM Used? | Purpose |
|---|----------|-----------|-------------|-----------|---------|
| 1 | **Receipt Scanning** | ✅ YES | ✅ YES | ✅ YES | Match scanned items to database |
| 2 | **Item Seeding** | ✅ YES | ✅ YES | ✅ YES | Bulk add items from USDA database |
| 3 | **Recipe Generation** | ✅ YES | ✅ YES | ✅ YES | Generate recipes, match ingredients |
| 4 | **Manual Inventory Add** | ✅ YES | ✅ YES | ✅ YES | Parse user text, match items |
| 5 | **Nutrition Chatbot** | ❌ NO RAG | ❌ NO | ✅ YES (Tools) | Conversational agent with tools |

**Key Insight**: RAG is used for **semantic search/matching**, not for conversational chat!

---

## 🏗️ Infrastructure (Shared Across All Use Cases)

### 1. Embedding Service

**File**: `backend/app/services/embedding_service.py`

**What it does**: Converts text to 1536-dimensional vectors

```python
class EmbeddingService:
    """Generate embeddings using OpenAI"""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model  # text-embedding-3-small
        self.dimension = 1536

    async def get_embedding(self, text: str) -> List[float]:
        """
        Convert text to 1536 numbers

        Args:
            text: "chicken breast protein"

        Returns:
            [0.234, -0.123, ..., 0.901]  # 1536 floats
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=text.lower().strip()
        )
        return response.data[0].embedding

    async def get_embeddings_batch(self, texts: List[str], batch_size=100):
        """Process multiple texts efficiently"""
        # Batches of 100 per API call
        ...
```

**Used By**: All 4 RAG use cases

**Cost**: $0.00002 per 1K tokens (extremely cheap!)

---

### 2. Database Schema (pgvector)

**Migration**: `alembic/versions/6e8f2a4b9c3d_add_vector_embeddings_to_items_and_recipes.py`

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Items table with embeddings
ALTER TABLE items ADD COLUMN embedding TEXT;  -- Stores JSON array
ALTER TABLE items ADD COLUMN embedding_model VARCHAR(50);
ALTER TABLE items ADD COLUMN embedding_version INTEGER;

-- Recipes table with embeddings
ALTER TABLE recipes ADD COLUMN embedding TEXT;

-- Fast similarity search with HNSW index
CREATE INDEX items_embedding_idx
ON items USING hnsw ((embedding::vector(1536)) vector_cosine_ops);

CREATE INDEX recipes_embedding_idx
ON recipes USING hnsw ((embedding::vector(1536)) vector_cosine_ops);
```

**Key Points**:
- **pgvector**: PostgreSQL extension for vector operations
- **HNSW**: Hierarchical Navigable Small World (fast approximate search)
- **Cosine distance**: `<=>` operator for similarity
- Embeddings stored as TEXT (JSON), cast to vector(1536) for queries

---

### 3. Vector Similarity Search (Standard Query)

**Pattern used in all 4 RAG cases**:

```python
# Generate query embedding
query_embedding = await embedder.get_embedding("herb mint")
embedding_str = embedder.embedding_to_db_string(query_embedding)

# Vector similarity search
result = db.execute(text("""
    SELECT
        id,
        canonical_name,
        1 - (embedding::vector(1536) <=> :embedding::vector(1536)) as similarity
    FROM items
    WHERE embedding IS NOT NULL
    ORDER BY embedding::vector(1536) <=> :embedding::vector(1536)
    LIMIT 3
"""), {"embedding": embedding_str, "top_k": 3})
```

**What this does**:
- Compare query embedding with all stored embeddings
- `<=>` = cosine distance (0 = identical, 2 = opposite)
- `1 - distance` = similarity (1 = identical, 0 = opposite)
- `ORDER BY distance` = closest matches first

---

## 🎯 Use Case 1: Receipt Scanning (RAG Item Matching)

**User Flow**: User uploads receipt photo → Extract items → Match to database

**Files**:
- `backend/app/api/receipt.py` - API endpoint
- `backend/app/services/item_normalizer_rag.py` - RAG pipeline
- `backend/app/services/inventory_service.py` - Orchestrates flow

### Complete Flow

```
User uploads receipt
    ↓
Microservice extracts items: ["HERB MINT", "RED CAPSICUM", "CHINESE BROCCOLI"]
    ↓
RAG Pipeline for each item:
    ↓
┌──────────────────────────────────────────────────┐
│ ITEM NORMALIZER RAG PIPELINE                     │
├──────────────────────────────────────────────────┤
│                                                  │
│ Step 1: Exact Match (100%)                      │
│   "mint" == "mint" ✅                            │
│                                                  │
│ Step 2: Alias Match (95%)                       │
│   "peppermint" in aliases of "mint" ✅           │
│                                                  │
│ Step 3: Vector Similarity >0.90 (92%)           │
│   "herb mint" → Query embedding                  │
│   → Search database                              │
│   → "mint" (similarity: 0.92) ✅                 │
│   → Auto-match!                                  │
│                                                  │
│ Step 4: Vector 0.75-0.90 + LLM (80%)            │
│   "red capsicum" → Query embedding               │
│   → Search database                              │
│   → "bell_pepper" (similarity: 0.82)             │
│   → Send to LLM:                                 │
│       "Is red capsicum = bell_pepper?"           │
│   → LLM: "Yes! Capsicum = bell pepper" ✅        │
│   → Match with confidence 0.85                   │
│                                                  │
│ Step 5: Vector <0.75 → No Match (0%)            │
│   "japanese pumpkin" → Query embedding           │
│   → Search database                              │
│   → Best: "butternut_squash" (similarity: 0.65)  │
│   → Too low! No auto-match ❌                    │
│   → Send to user for confirmation                │
│                                                  │
└──────────────────────────────────────────────────┘
    ↓
Results:
  - Auto-added: "mint", "bell_pepper"
  - Needs confirmation: "japanese pumpkin"
    ↓
User confirms/rejects
```

### Code Example

**File**: `backend/app/services/item_normalizer_rag.py`

```python
class RAGItemNormalizer:
    async def normalize_single(self, raw_input: str):
        """RAG pipeline for matching items"""

        # Step 1: Exact match
        if cleaned in self.items_cache['by_name']:
            return NormalizationResult(confidence=1.0, matched_on='exact')

        # Step 2: Alias match
        if cleaned in self.items_cache['by_alias']:
            return NormalizationResult(confidence=0.95, matched_on='alias')

        # Step 3: Vector similarity search
        vector_results = await self._vector_search(raw_input, top_k=3)
        best_item, best_similarity = vector_results[0]

        # Step 4a: High similarity → Trust it
        if best_similarity >= 0.90:
            return NormalizationResult(
                item=best_item,
                confidence=0.92,
                matched_on='vector'
            )

        # Step 4b: Medium similarity → LLM verification
        elif best_similarity >= 0.75:
            return await self._llm_verify(raw_input, vector_results)

        # Step 5: Low similarity → No match
        else:
            return NormalizationResult(confidence=0.0, matched_on='none')

    async def _vector_search(self, query_text: str, top_k=3):
        """Vector similarity search"""
        embedding = await self.embedder.get_embedding(query_text)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        result = self.db.execute(text("""
            SELECT id, canonical_name,
                   1 - (embedding::vector(1536) <=> :embedding::vector(1536)) as similarity
            FROM items
            WHERE embedding IS NOT NULL
            ORDER BY embedding::vector(1536) <=> :embedding::vector(1536)
            LIMIT :top_k
        """), {"embedding": embedding_str, "top_k": top_k})

        return [(item, similarity) for row in result]

    async def _llm_verify(self, raw_input: str, vector_results):
        """LLM verification with RAG context"""
        candidates = [
            {"name": item.canonical_name, "similarity": similarity}
            for item, similarity in vector_results[:3]
        ]

        prompt = f"""User scanned: "{raw_input}"
Vector search found: {json.dumps(candidates)}

Is any candidate a correct match?
Rules:
- "Red Capsicum" = "bell_pepper" ✅ (capsicum = bell pepper)
- "Herb Mint" = "mint" ✅ (herb is descriptor)
- "Japanese Pumpkin" ≠ "butternut_squash" ❌ (different vegetables)

JSON: {{"matched": true/false, "item_id": X, "reasoning": "..."}}
"""

        response = await llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        llm_result = json.loads(response.choices[0].message.content)
        return NormalizationResult(
            matched=llm_result["matched"],
            confidence=llm_result.get("confidence", 0.80),
            matched_on='llm_verified'
        )
```

### Why This is RAG

1. **Retrieval**: Vector search finds similar items from database
2. **Augmented**: LLM gets context (top 3 matches with similarities)
3. **Generation**: LLM generates decision: match or no match

---

## 🎯 Use Case 2: Item Seeding (Bulk Database Population)

**User Flow**: Admin runs script → Generate 500 new items → Review → Import

**File**: `backend/scripts/ai_assisted_item_seeding.py`

### Complete Flow

```
┌──────────────────────────────────────────────────────────────┐
│ AI-ASSISTED ITEM SEEDING WORKFLOW                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Step 1: LLM Generates Candidates                            │
│   ┌────────────────────────────────────────┐               │
│   │ Input: ALL 2000 existing items         │               │
│   │ Prompt: "Suggest 500 NEW items"       │               │
│   │ LLM (GPT-4o): Generates list           │               │
│   │ Output: ["celery", "herb_mint", ...]   │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 2: Search USDA FDC for Each                           │
│   ┌────────────────────────────────────────┐               │
│   │ For "celery":                           │               │
│   │   → FDC API search                      │               │
│   │   → Top 3 matches:                      │               │
│   │       1. "Celery, raw" (1001)           │               │
│   │       2. "Celery, cooked" (1002)        │               │
│   │       3. "Celeriac" (1003)              │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 3: LLM Enrichment (WITH Nutrition)                    │
│   ┌────────────────────────────────────────┐               │
│   │ Input: Candidate + 3 FDC matches       │               │
│   │ IMPORTANT: Include parsed nutrition!   │               │
│   │                                         │               │
│   │ Prompt: "Which match has best data?"   │               │
│   │ LLM evaluates:                          │               │
│   │   - Description match                   │               │
│   │   - Nutrition completeness              │               │
│   │   - Fiber presence (vegetables)         │               │
│   │   - Realistic values                    │               │
│   │                                         │               │
│   │ Output:                                 │               │
│   │   best_fdc_index: 0                     │               │
│   │   canonical_name: "celery"              │               │
│   │   category: "vegetables"                │               │
│   │   aliases: ["celery stalk", ...]        │               │
│   │   confidence: 0.95                      │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 4: Generate Embeddings                                │
│   ┌────────────────────────────────────────┐               │
│   │ For each enriched item:                 │               │
│   │   embedding_text = canonical_name +     │               │
│   │                    display_name +         │               │
│   │                    category +             │               │
│   │                    aliases                │               │
│   │                                         │               │
│   │   embedding = await embedder            │               │
│   │       .get_embedding(embedding_text)    │               │
│   │                                         │               │
│   │   Save to JSON for review               │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 5: Manual Review + Import                             │
│   ┌────────────────────────────────────────┐               │
│   │ Admin reviews JSON file                 │               │
│   │ Removes bad items                       │               │
│   │ Runs import command                     │               │
│   │   → Bulk insert to items table          │               │
│   │   → With embeddings                     │               │
│   └────────────────────────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Code Example

```python
class IntelligentSeeder:
    """AI-powered item seeding"""

    async def run_full_workflow(self, target_count=500):
        # Step 1: Generate candidates with LLM
        candidates = await self.generate_candidate_items(target_count)
        # ["celery", "herb_mint", "japanese_pumpkin", ...]

        # Step 2: Search FDC for each
        fdc_results = await self.fetch_fdc_options_for_candidates(candidates)
        # {"celery": [fdc_match_1, fdc_match_2, fdc_match_3], ...}

        # Step 3: LLM enrichment
        enriched_items = await self.enrich_candidates_with_llm(fdc_results)
        # [
        #   {
        #     "canonical_name": "celery",
        #     "category": "vegetables",
        #     "nutrition_per_100g": {...},
        #     "confidence": 0.95
        #   }
        # ]

        # Step 4: Generate embeddings and save
        await self.create_review_json(enriched_items)
        # Saves to: backend/data/proposed_items_for_review.json

    async def generate_candidate_items(self, target_count):
        """Step 1: LLM generates NEW items"""
        existing_items = self.db.query(Item.canonical_name).all()  # 2000 items

        prompt = f"""You are a nutrition database curator.
CURRENT DATABASE ({len(existing_items)} items):
{json.dumps(existing_items)}

Suggest {target_count} NEW items NOT in database.
Focus on common grocery items (vegetables, fruits, proteins, grains, dairy).

JSON output: ["celery", "herb_mint", ...]
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        suggested_items = json.loads(response.choices[0].message.content)
        return suggested_items

    async def enrich_candidates_with_llm(self, fdc_results):
        """Step 3: LLM selects best FDC match"""
        batch_data = {}
        for candidate, fdc_matches in fdc_results.items():
            # CRITICAL: Include parsed nutrition
            simplified_matches = []
            for match in fdc_matches:
                parsed_nutrition = self.fdc_service._parse_fdc_nutrients(match)
                simplified_matches.append({
                    "description": match["description"],
                    "fdcId": match["fdcId"],
                    "nutrition": parsed_nutrition  # ← IMPORTANT!
                })
            batch_data[candidate] = simplified_matches

        prompt = f"""Review FDC matches and select ONE with best nutrition data.

BATCH DATA (with parsed nutrition):
{json.dumps(batch_data)}

TASK: Evaluate which match has most COMPLETE and REALISTIC nutrition.

Check:
- Does celery have fiber? (Yes ~1.6g/100g)
- Does chicken have carbs? (No/minimal)
- Does oil have protein? (No)

Output JSON:
{{
    "celery": {{
        "best_fdc_index": 0,  # Index of best match (0-2)
        "canonical_name": "celery",
        "category": "vegetables",
        "aliases": ["celery stalk", "celery stick"],
        "confidence": 0.95
    }}
}}
"""

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        batch_enrichment = json.loads(response.choices[0].message.content)

        # Create enriched items
        enriched_items = []
        for candidate, enrichment in batch_enrichment.items():
            best_fdc_index = enrichment["best_fdc_index"]
            fdc_match = fdc_results[candidate][best_fdc_index]
            nutrition = self.fdc_service._parse_fdc_nutrients(fdc_match)

            enriched_items.append({
                "canonical_name": enrichment["canonical_name"],
                "category": enrichment["category"],
                "aliases": enrichment["aliases"],
                "nutrition_per_100g": nutrition,
                "confidence": enrichment["confidence"]
            })

        return enriched_items

    async def create_review_json(self, enriched_items):
        """Step 4: Generate embeddings"""
        # Build embedding text
        embedding_texts = []
        for item in enriched_items:
            text = " ".join([
                item["canonical_name"],
                item["category"],
                *item["aliases"]
            ])
            embedding_texts.append(text)

        # Batch generate embeddings
        embeddings = await self.embedding_service.get_embeddings_batch(
            embedding_texts,
            batch_size=100
        )

        # Add to items
        for idx, item in enumerate(enriched_items):
            item["embedding"] = embeddings[idx]
            item["embedding_model"] = "text-embedding-3-small"

        # Save JSON for review
        output = {
            "metadata": {"total_items": len(enriched_items)},
            "items": enriched_items
        }

        with open("backend/data/proposed_items_for_review.json", "w") as f:
            json.dump(output, f, indent=2)
```

### Why This Uses RAG

**This is NOT traditional RAG** (no retrieval for generation), but:
- **Embeddings**: Generate embeddings for semantic search LATER
- **LLM**: Enriches data (categories, aliases, confidence)
- **Purpose**: Populate database with searchable embeddings

Once items are in database with embeddings → Used by receipt scanning RAG!

---

## 🎯 Use Case 3: Recipe Generation (RAG for Ingredients)

**User Flow**: System generates recipe → Match ingredients → Auto-seed missing

**Files**:
- `backend/app/services/recipe_pipeline.py` - Main pipeline
- `backend/app/services/llm_recipe_generator.py` - Recipe generation
- `backend/app/services/recipe_ingredient_processor.py` - RAG matching

### Complete Flow

```
┌──────────────────────────────────────────────────────────────┐
│ RECIPE GENERATION PIPELINE                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Step 1: LLM Generates Recipe (Structured Output)            │
│   ┌────────────────────────────────────────┐               │
│   │ Input: Goal + Target Macros            │               │
│   │   goal: muscle_gain                    │               │
│   │   target: 1000 cal, 75g protein        │               │
│   │                                         │               │
│   │ LLM (GPT-4o with Structured Outputs):  │               │
│   │   {                                     │               │
│   │     "name": "Grilled Chicken Bowl",    │               │
│   │     "ingredients": [                    │               │
│   │       {"food_name": "chicken_breast",   │               │
│   │        "quantity_grams": 500},           │               │
│   │       {"food_name": "brown_rice",       │               │
│   │        "quantity_grams": 200},           │               │
│   │       {"food_name": "olive_oil",        │               │
│   │        "quantity_grams": 15}             │               │
│   │     ],                                  │               │
│   │     "instructions": [...],              │               │
│   │     "nutrition": {                      │               │
│   │       "calories": 1000,                 │               │
│   │       "protein_g": 75                   │               │
│   │     }                                   │               │
│   │   }                                     │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 2: Deduplication Check (Vector Similarity)            │
│   ┌────────────────────────────────────────┐               │
│   │ Query: "Grilled Chicken Bowl"          │               │
│   │   → Generate embedding                  │               │
│   │   → Search recipes table                │               │
│   │   → Check similarity >0.90              │               │
│   │                                         │               │
│   │ If duplicate found:                     │               │
│   │   → Retry with different constraints    │               │
│   │ If unique:                              │               │
│   │   → Proceed ✅                          │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 3: Process Ingredients (RAG + Auto-seed)              │
│   ┌────────────────────────────────────────┐               │
│   │ For each ingredient:                    │               │
│   │                                         │               │
│   │ Ingredient 1: "chicken_breast"          │               │
│   │   → Exact match in items table ✅       │               │
│   │   → Use item_id=45                      │               │
│   │                                         │               │
│   │ Ingredient 2: "brown_rice"              │               │
│   │   → Exact match in items table ✅       │               │
│   │   → Use item_id=112                     │               │
│   │                                         │               │
│   │ Ingredient 3: "saffron"                 │               │
│   │   → NOT in items table ❌               │               │
│   │   → Auto-seed:                          │               │
│   │       1. Search FDC for "saffron"       │               │
│   │       2. LLM selects best match         │               │
│   │       3. Generate embedding             │               │
│   │       4. Create Item record             │               │
│   │   → Use new item_id=2048 ✅             │               │
│   └────────────────────────────────────────┘               │
│                                                              │
│ Step 4: Create Database Records                            │
│   ┌────────────────────────────────────────┐               │
│   │ Create Recipe:                          │               │
│   │   - title: "Grilled Chicken Bowl"       │               │
│   │   - macros: LLM's nutrition             │               │
│   │   - embedding: generated                │               │
│   │   - instructions: [...]                 │               │
│   │                                         │               │
│   │ Create RecipeIngredients:               │               │
│   │   - recipe_id=501                       │               │
│   │   - item_id=45 (chicken_breast)         │               │
│   │   - quantity_grams=500                  │               │
│   │   ...                                   │               │
│   └────────────────────────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Code Example

**Main Pipeline** (`recipe_pipeline.py`):

```python
class LLMRecipeGenerationPipeline:
    async def generate_validated_recipe(
        self,
        goal_type: str,
        target_macros: Dict
    ):
        # Step 1: Generate recipe with LLM
        recipe_struct = await self.generator.generate_recipe(
            goal_type=goal_type,
            target_calories=target_macros['calories'],
            target_protein=target_macros['protein'],
            check_duplicates=True,  # ← Vector similarity check
            max_retries=3
        )

        # Step 2: Process ingredients (match + auto-seed)
        ingredients_as_dicts = [
            {
                "food_name": ing.food_name,
                "quantity_grams": ing.quantity_grams
            }
            for ing in recipe_struct.ingredients
        ]

        matched_ingredients = await self.processor.process_recipe_ingredients(
            ingredients_as_dicts
        )

        # Step 3: Create database records
        recipe_record = await self._create_recipe_record(recipe_struct)
        recipe_ingredient_records = self._create_recipe_ingredient_records(
            recipe_record.id,
            matched_ingredients
        )

        self.db.commit()

        return {
            'recipe': recipe_record,
            'recipe_ingredients': recipe_ingredient_records,
            'ingredients_created': sum(1 for ing in matched_ingredients if ing['was_created'])
        }
```

**Deduplication Check** (`llm_recipe_generator.py`):

```python
class StructuredRecipeGenerator:
    async def generate_recipe(self, ..., check_duplicates=True):
        # Generate recipe with LLM
        recipe = await self._call_llm(...)

        # Check for duplicates using vector similarity
        if check_duplicates:
            is_duplicate = await self._check_duplicate(recipe.name)
            if is_duplicate:
                logger.warning(f"Duplicate detected: {recipe.name}")
                # Retry with modified constraints
                return await self.generate_recipe(..., max_retries=max_retries-1)

        return recipe

    async def _check_duplicate(self, recipe_name: str) -> bool:
        """Vector similarity search against existing recipes"""
        # Generate embedding for new recipe
        embedding = await self.embedder.get_embedding(recipe_name)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        # Search existing recipes
        result = self.db.execute(text("""
            SELECT title,
                   1 - (embedding::vector(1536) <=> :embedding::vector(1536)) as similarity
            FROM recipes
            WHERE embedding IS NOT NULL
            ORDER BY embedding::vector(1536) <=> :embedding::vector(1536)
            LIMIT 1
        """), {"embedding": embedding_str})

        top_match = result.first()
        if top_match and top_match['similarity'] > 0.90:
            logger.warning(f"Duplicate: '{recipe_name}' ≈ '{top_match['title']}' (sim: {top_match['similarity']:.2f})")
            return True  # Is duplicate

        return False  # Is unique
```

**Ingredient Matching** (`recipe_ingredient_processor.py`):

```python
class RecipeIngredientProcessor:
    async def process_recipe_ingredients(self, recipe_ingredients):
        matched = []

        for ing_dict in recipe_ingredients:
            food_name = ing_dict['food_name']

            # Try to find existing item (exact/alias/vector)
            existing_item, match_method = await self._find_existing_item(food_name)

            if existing_item:
                # Found! Use existing
                matched.append({
                    "food_name": food_name,
                    "item_id": existing_item.id,
                    "was_created": False,
                    "match_method": match_method
                })
            else:
                # Not found → Auto-seed from FDC
                new_item = await self._auto_seed_item(food_name)
                matched.append({
                    "food_name": food_name,
                    "item_id": new_item.id,
                    "was_created": True,
                    "match_method": "created"
                })

        return matched

    async def _find_existing_item(self, food_name: str):
        """Try exact, alias, then vector search"""
        # 1. Exact match
        item = self.db.query(Item).filter(
            Item.canonical_name == food_name.lower()
        ).first()
        if item:
            return item, "exact"

        # 2. Alias match
        item = self.db.query(Item).filter(
            cast(Item.aliases, String).contains(food_name.lower())
        ).first()
        if item:
            return item, "alias"

        # 3. Vector similarity search
        embedding = await self.embedder.get_embedding(food_name)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        result = self.db.execute(text("""
            SELECT id,
                   1 - (embedding::vector(1536) <=> :embedding::vector(1536)) as similarity
            FROM items
            WHERE embedding IS NOT NULL
            ORDER BY embedding::vector(1536) <=> :embedding::vector(1536)
            LIMIT 1
        """), {"embedding": embedding_str})

        top_match = result.first()
        if top_match and top_match['similarity'] > 0.90:
            item = self.db.query(Item).filter(Item.id == top_match['id']).first()
            return item, "vector"

        return None, None

    async def _auto_seed_item(self, food_name: str):
        """Create new item from FDC"""
        # 1. Search FDC
        fdc_matches = await self.fdc_service.search_food(food_name)

        # 2. LLM selects best match
        best_match = await self._llm_select_best_fdc(food_name, fdc_matches[:3])

        # 3. Parse nutrition
        nutrition = self.fdc_service._parse_fdc_nutrients(best_match)

        # 4. Generate embedding
        embedding = await self.embedder.get_embedding(food_name)
        embedding_str = self.embedder.embedding_to_db_string(embedding)

        # 5. Create Item
        new_item = Item(
            canonical_name=food_name.lower(),
            category="other",
            nutrition_per_100g=nutrition,
            embedding=embedding_str,
            embedding_model="text-embedding-3-small",
            source="fdc_auto_seeded"
        )
        self.db.add(new_item)
        self.db.flush()  # Get ID

        return new_item
```

### Why This Uses RAG

1. **Recipe Deduplication**: Vector search prevents duplicate recipes
2. **Ingredient Matching**: Retrieval (vector search) → Augmentation (LLM if needed)
3. **Auto-seeding**: RAG pattern for missing ingredients

---

## 🎯 Use Case 4: Manual Inventory Add (User Input)

**User Flow**: User types "2kg onions" → Parse → Match → Add to inventory

**File**: `backend/app/services/item_normalizer_rag.py`

### Flow

```
User input: "2kg onions"
    ↓
LLM extracts structure:
  {
    "item_name": "onions",
    "quantity": 2,
    "unit": "kg"
  }
    ↓
RAG pipeline for "onions":
  → Exact match? "onion" ✅
  → item_id=45
    ↓
Intelligent unit conversion:
  → Standard units? "kg" → 2000g ✅
    ↓
Add to inventory:
  item_id=45, quantity_grams=2000
```

### Code

```python
class RAGItemNormalizer:
    async def process_manual_entry(self, user_text: str):
        """
        Process: "2kg onions", "5 tomatoes", "1 packet rice"
        """
        # Step 1: LLM extracts structure
        structure = await self._extract_structure(user_text)
        # {"item_name": "onions", "quantity": 2, "unit": "kg"}

        # Step 2: RAG pipeline for matching
        result = await self.normalize_single(structure['item_name'])

        # Step 3: Intelligent unit conversion
        if result.item:
            grams, note = await self.convert_to_grams_intelligent(
                quantity=structure['quantity'],
                unit=structure['unit'],
                item=result.item
            )
            result.quantity_grams = grams

        return result

    async def _extract_structure(self, user_text: str):
        """LLM extracts quantity, unit, item_name"""
        prompt = f"""Extract structured data: "{user_text}"

Examples:
- "2kg onions" → {{"item_name": "onions", "quantity": 2, "unit": "kg"}}
- "5 tomatoes" → {{"item_name": "tomatoes", "quantity": 5, "unit": "piece"}}

JSON output:
"""
        response = await llm.chat.completions.create(...)
        return json.loads(response.choices[0].message.content)

    async def convert_to_grams_intelligent(self, quantity, unit, item):
        """
        Smart conversion: standard units instant, unknown units → LLM
        """
        # Tier 1: Already grams
        if unit in ['g', 'gram', 'grams']:
            return quantity, "Already in grams"

        # Tier 2: Standard conversions
        if unit in ['kg', 'kilogram']:
            return quantity * 1000, "Standard kg→g"

        # Tier 3: Unknown units → LLM
        prompt = f"""Convert to grams:
Item: {item.canonical_name}
Quantity: {quantity} {unit}

Estimates:
- onion: 150g each
- tomato: 100g each
- celery bunch: 200g

JSON: {{"total_grams": X, "reasoning": "..."}}
"""
        response = await llm.chat.completions.create(...)
        result = json.loads(response.choices[0].message.content)
        return result['total_grams'], result['reasoning']
```

---

## ❌ Use Case 5: Nutrition Chatbot (NOT RAG!)

**User Flow**: User asks "How much protein today?" → Chatbot answers

**File**: `backend/app/agents/nutrition_graph.py` (LangGraph)

### Why This is NOT RAG

**RAG requires**:
1. ✅ Retrieval (vector search)
2. ✅ Augmentation (add context to LLM)
3. ✅ Generation (LLM answers with context)

**Nutrition Chatbot uses**:
1. ❌ NO vector search
2. ✅ Direct database queries (via Tools)
3. ✅ LLM with tool calling

### Flow

```
User: "How much protein have I consumed today?"
    ↓
LangGraph State Machine:
  Node 1: load_context → Minimal user profile
  Node 2: classify_intent → "STATS"
  Node 3: generate_response → LLM with tools
    ↓
LLM (GPT-4o) decides: "I need to call get_nutrition_stats tool"
    ↓
Tool: get_nutrition_stats(user_id=123, nutrients="protein")
  → Direct SQL query: SELECT * FROM meal_logs WHERE user_id=123 AND date=today
  → Calculate: SUM(protein_g)
  → Return: {"consumed": {"protein_g": 65}, "targets": {"protein_g": 150}}
    ↓
LLM receives tool result
    ↓
LLM: "You've consumed 65g protein out of your 150g target today. You need 85g more!"
```

### This is NOT RAG Because

- **No embeddings**: No vector search
- **No retrieval**: Direct SQL queries via tools
- **No augmentation**: Tools return exact data, not similar documents

### This IS Tool-Based LLM Agent

```python
class NutritionState(TypedDict):
    """Agent state"""
    messages: Sequence[BaseMessage]
    user_context: Dict  # Minimal context (user_id, goal)
    intent: str
    user_id: int

# Tools (direct database access)
@tool
def get_nutrition_stats(user_id: int, nutrients: Optional[str] = None):
    """Get current nutrition for today"""
    db = SessionLocal()
    context = UserContext(db, user_id).build_context(minimal=True)

    consumed = context['today']['consumed']
    targets = context['targets']

    return json.dumps({
        "consumed": consumed,
        "targets": targets
    })

@tool
def check_inventory(user_id: int, search_term: Optional[str] = None):
    """Check food inventory"""
    db = SessionLocal()
    context = UserContext(db, user_id).build_context(minimal=True)
    return json.dumps(context['inventory_summary'])

# LLM with tools
def generate_response_node(state):
    tools = [get_nutrition_stats, check_inventory, ...]
    llm = ChatOpenAI(model="gpt-4o").bind_tools(tools)

    system_prompt = f"""You are a nutrition assistant.
User {state['user_id']} | Goal: {state['user_context']['goal_type']}
Use tools to fetch data when needed. Pass user_id={state['user_id']}.
"""

    messages = [SystemMessage(content=system_prompt)] + state['messages']
    response = await llm.ainvoke(messages)

    return {"messages": [response]}
```

### RAG vs Tool-Based Comparison

| Feature | RAG | Tool-Based (Chatbot) |
|---------|-----|----------------------|
| **Data Access** | Vector similarity search | Direct SQL queries |
| **Embeddings** | ✅ YES | ❌ NO |
| **Use Case** | "Find similar items" | "Get exact data" |
| **Context** | Top-K documents | Tool return values |
| **Example** | "herb mint" → "mint" | "What's my protein?" → SQL query |

---

## 📊 Summary Table: All RAG Uses

| # | Use Case | RAG? | Embeddings? | LLM? | Vector Search? | Purpose |
|---|----------|------|-------------|------|----------------|---------|
| **1** | Receipt Scanning | ✅ | ✅ | ✅ | ✅ | Match items: "herb mint" → "mint" |
| **2** | Item Seeding | ⚠️ Hybrid | ✅ | ✅ | ❌ | Generate embeddings for future RAG |
| **3** | Recipe Generation | ✅ | ✅ | ✅ | ✅ | Dedup recipes, match ingredients |
| **4** | Manual Inventory | ✅ | ✅ | ✅ | ✅ | Parse input, match items |
| **5** | Nutrition Chatbot | ❌ | ❌ | ✅ | ❌ | Direct queries via tools |

---

## 🔑 Key Takeaways

### When NutriLens Uses RAG

✅ **Semantic Matching**: When need to find "similar" items
  - "herb mint" → "mint"
  - "red capsicum" → "bell_pepper"

✅ **Deduplication**: When need to avoid duplicates
  - "Grilled Chicken Bowl" ≈ "Chicken Bowl Grilled"?

✅ **Fuzzy Search**: When exact match won't work
  - Typos, variants, descriptors

### When NutriLens Uses Direct Queries (Not RAG)

❌ **Exact Data Retrieval**: When need precise numbers
  - "How much protein today?" → SUM(protein_g)
  - "What's my calorie target?" → user_profile.target_calories

❌ **Conversational Context**: When answering questions
  - Nutrition chatbot uses tools, not vector search

### RAG Pipeline Pattern (Used 4 Times)

```
1. Generate embedding for query
2. Vector similarity search (cosine distance)
3. Get top-K matches with similarities
4. If high confidence (>0.90) → Use match
5. If medium (0.75-0.90) → LLM verification
6. If low (<0.75) → Ask user
```

### Infrastructure Used by All

- **Embeddings**: OpenAI text-embedding-3-small (1536D)
- **Vector DB**: PostgreSQL + pgvector
- **Similarity**: Cosine distance (`<=>` operator)
- **Index**: HNSW (fast approximate nearest neighbor)
- **Cost**: $0.02 per 1M tokens (very cheap!)

---

## 📁 File Reference

### Core Services
- `backend/app/services/embedding_service.py` - Generate embeddings
- `backend/app/services/item_normalizer_rag.py` - Receipt RAG pipeline
- `backend/app/services/recipe_pipeline.py` - Recipe generation
- `backend/app/services/recipe_ingredient_processor.py` - Ingredient matching
- `backend/app/services/llm_recipe_generator.py` - Recipe LLM + dedup

### Scripts
- `backend/scripts/ai_assisted_item_seeding.py` - Bulk item seeding

### API Endpoints
- `backend/app/api/receipt.py` - Receipt upload + processing
- `backend/app/api/inventory.py` - Manual inventory add

### Chatbot (Not RAG)
- `backend/app/agents/nutrition_graph.py` - LangGraph agent with tools

### Database
- `alembic/versions/6e8f2a4b9c3d_*.py` - pgvector migration

---

**Document Status**: ✅ COMPLETE
**Last Updated**: 2025-11-25
**Next**: Ready to resume migration work!

