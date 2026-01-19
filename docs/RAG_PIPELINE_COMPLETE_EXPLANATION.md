# RAG Pipeline - Complete Explanation for NutriLens

**Date**: 2025-11-25
**Purpose**: Comprehensive explanation of RAG, embeddings, and how NutriLens uses them
**Requested By**: User

---

## 📚 Part 1: How RAG Pipelines Work (General)

### What is RAG?

**RAG = Retrieval-Augmented Generation**

A technique that enhances Large Language Models (LLMs like GPT-4, Claude) by giving them access to **external knowledge** at query time.

---

### The Problem RAG Solves

**Without RAG** (Standard LLM):
```
User: "What's the recipe for Chicken Tikka Masala in our database?"
LLM: "I don't have access to your database. Here's a general recipe..." ❌
❌ LLM only knows training data (cut-off date: Jan 2024)
❌ Cannot access your private data
❌ Hallucinates when it doesn't know
```

**With RAG**:
```
User: "What's the recipe for Chicken Tikka Masala in our database?"

System:
  Step 1: Search YOUR database for relevant recipes
  Step 2: Find "Chicken Tikka Masala" recipe (with actual data!)
  Step 3: Give LLM the ACTUAL recipe data as context

LLM: "Based on YOUR database, here's the Chicken Tikka Masala recipe:
      Ingredients: chicken, yogurt, tomatoes, spices
      Calories: 450 per serving
      Instructions: Marinate chicken..." ✅

✅ LLM gets accurate, up-to-date data from YOUR system
✅ No hallucinations
✅ Can access private/recent data
```

---

### The Complete RAG Pipeline (5 Steps)

```
┌──────────────────────────────────────────────────────────────────┐
│                        RAG PIPELINE                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INDEXING PHASE (Done Once, Offline)                            │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Documents → Chunks → Embeddings → Vector Database   │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  QUERY PHASE (Done Every Time User Asks)                        │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Query → Embedding → Search → Retrieve → Generate    │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

Let me explain each step with concrete examples:

---

## STEP 1: INDEXING PHASE (One-Time Setup)

**Goal**: Convert your documents into a searchable format

### Process Flow

```
Original Documents (Your Knowledge Base)
    ↓
Split into Chunks (smaller pieces)
    ↓
Convert Each Chunk to Embedding (Vector)
    ↓
Store in Vector Database
```

### Concrete Example

```python
# ORIGINAL DOCUMENT
document = """
Chicken Tikka Masala Recipe
Ingredients: chicken, yogurt, tomatoes, garam masala, cream
Instructions: Marinate chicken in yogurt for 2 hours.
Grill until charred. Make sauce with tomatoes and spices.
Nutrition: 450 calories per serving, 30g protein, 15g fat, 25g carbs
"""

# STEP 1A: Split into Chunks
chunks = [
    "Chicken Tikka Masala Recipe. Ingredients: chicken, yogurt, tomatoes, garam masala, cream",
    "Instructions: Marinate chicken in yogurt for 2 hours. Grill until charred. Make sauce with tomatoes and spices.",
    "Nutrition: 450 calories per serving, 30g protein, 15g fat, 25g carbs"
]

# STEP 1B: Convert to Embeddings (vectors)
# OpenAI's text-embedding-3-small creates 1536 numbers for each chunk
embedding_1 = [0.234, -0.123, 0.456, -0.789, ..., 0.901]  # 1536 numbers!
embedding_2 = [0.123, -0.234, 0.567, -0.890, ..., 0.123]
embedding_3 = [0.345, -0.456, 0.678, -0.901, ..., 0.234]

# STEP 1C: Store in Vector Database
vector_db.add(
    text="Chicken Tikka Masala Recipe. Ingredients: ...",
    embedding=embedding_1
)
vector_db.add(
    text="Instructions: Marinate chicken...",
    embedding=embedding_2
)
vector_db.add(
    text="Nutrition: 450 calories...",
    embedding=embedding_3
)
```

**Why chunks?**
- LLMs have context limits (can't process entire books)
- Smaller chunks = more precise retrieval
- Each chunk should be self-contained (complete thought)

**Typical Chunk Sizes**:
- Small: 200-500 characters (paragraphs)
- Medium: 500-1000 characters (sections)
- Large: 1000-2000 characters (pages)

---

## STEP 2: QUERY (User Asks a Question)

```
User: "How many calories in Chicken Tikka Masala?"
```

This triggers the retrieval process (Steps 3-5).

---

## STEP 3: EMBEDDING (Convert Query to Vector)

**Goal**: Convert user's question into **same format** as stored documents

```python
query = "How many calories in Chicken Tikka Masala?"

# Convert to embedding using SAME model as indexing
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
query_embedding = embedding_model.embed(query)

# Result: List of 1536 numbers
query_embedding = [0.345, -0.234, 0.567, -0.901, ..., 0.123]
```

**CRITICAL**: Must use **EXACT SAME embedding model** for indexing and querying!
- Indexing: text-embedding-3-small
- Querying: text-embedding-3-small ✅
- Mixing models = broken search ❌

---

## STEP 4: SEARCH (Find Similar Documents)

**Goal**: Find chunks that are **semantically similar** to the query

**How?** Calculate **cosine similarity** between query embedding and all stored embeddings

```python
# Vector database does this automatically
similar_chunks = vector_db.similarity_search(
    query_embedding=query_embedding,
    top_k=3  # Return top 3 most similar
)

# Results (ranked by similarity):
# Rank 1: "Nutrition: 450 calories per serving, 30g protein..." (similarity: 0.92)
# Rank 2: "Chicken Tikka Masala Recipe. Ingredients: chicken..." (similarity: 0.78)
# Rank 3: "Instructions: Marinate chicken in yogurt..." (similarity: 0.65)
```

**Similarity Score**:
- 1.0 = Identical
- 0.9-0.99 = Very similar
- 0.7-0.89 = Similar
- 0.5-0.69 = Somewhat related
- < 0.5 = Not very related

**Why Rank 1 wins?**
- User asked "How many calories"
- Chunk contains "450 calories per serving"
- Semantic match: both about nutrition numbers!

---

## STEP 5: GENERATE (LLM Creates Answer)

**Goal**: Use retrieved chunks as **context** for LLM to generate accurate answer

```python
# Build prompt with retrieved context
prompt = f"""
You are a nutrition assistant. Answer the user's question using ONLY the provided context.

Context:
{similar_chunks[0].text}
{similar_chunks[1].text}
{similar_chunks[2].text}

User Question: {user_query}

Answer (based on context):
"""

# Send to LLM
llm = ChatOpenAI(model="gpt-4o")
answer = llm.generate(prompt)

# Output:
# "Based on the nutrition data, Chicken Tikka Masala contains 450 calories per serving,
#  with 30g protein, 15g fat, and 25g carbs."
```

**Key Benefit**: LLM now has **relevant context** from YOUR database!
- No hallucination
- Accurate data
- Up-to-date information
- Private data accessible

---

## 🔢 Part 2: The Role of Embeddings (Deep Dive)

### What Are Embeddings?

**Simple Definition**: A way to represent text as a list of numbers (vector) that captures **meaning**.

### Visual Example (2D Simplified)

```
Real embeddings are 1536 dimensions, but let's visualize in 2D:

     Y-axis (Animal-ness)
       │
   cat ●──● dog
       │   │
       │   ● puppy
       │   │
───────┼───┴────────────── X-axis (Size)
       │
       │     ● car
       │   ● truck
       │
```

**Observations**:
- Animals cluster together (semantic similarity)
- Vehicles cluster together (semantic similarity)
- "cat" and "dog" are close (both small animals)
- "car" and "truck" are close (both vehicles)
- "cat" and "car" are far apart (different meanings)

### Actual Embeddings (Text Examples)

```
Text: "cat"         → Embedding: [0.2, 0.8, -0.1, ..., 0.5]  (1536 numbers)
Text: "dog"         → Embedding: [0.3, 0.7, -0.2, ..., 0.6]  (similar to cat!)
Text: "puppy"       → Embedding: [0.25, 0.75, -0.15, ..., 0.55] (even closer to dog!)
Text: "car"         → Embedding: [-0.5, -0.3, 0.9, ..., -0.2] (completely different!)
```

**Why?** Machine learning models (BERT, GPT, etc.) learn to represent words with similar meanings as similar vectors!

---

### How Similarity is Calculated

**Cosine Similarity** (most common in RAG):

```python
import numpy as np

# Two embeddings
vec1 = [0.2, 0.8, -0.1]  # "cat"
vec2 = [0.3, 0.7, -0.2]  # "dog"
vec3 = [-0.5, -0.3, 0.9]  # "car"

# Cosine similarity formula (angle between vectors)
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

similarity_cat_dog = cosine_similarity(vec1, vec2)  # Result: 0.99 (very similar!)
similarity_cat_car = cosine_similarity(vec1, vec3)  # Result: -0.45 (opposite!)
```

**Interpretation**:
- 1.0 = Identical
- 0.9-0.99 = Very similar (synonyms, related concepts)
- 0.7-0.89 = Similar (same domain)
- 0.5-0.69 = Somewhat related
- < 0.5 = Not very related
- Negative = Opposite meanings

---

### Why Embeddings Capture Meaning

**Example 1: Synonyms**
```
"car" → [0.5, -0.3, 0.8, ...]
"automobile" → [0.52, -0.28, 0.79, ...]  (similarity: 0.98)
```
Even though different words, embeddings are nearly identical!

**Example 2: Context Understanding**
```
"bank" (river) → [0.2, 0.8, -0.5, ...]
"bank" (money) → [0.7, -0.2, 0.3, ...]  (similarity: 0.45)
```
Same word, different meaning → different embeddings!

**Example 3: Semantic Relationships**
```
"king" - "man" + "woman" ≈ "queen"
```
Embeddings capture relationships: "royalty male" - "male" + "female" = "royalty female"!

---

### Types of Embeddings

**1. Word Embeddings** (Old, not used in RAG)
- Word2Vec (2013), GloVe (2014)
- Each word = one fixed vector
- Problem: "bank" always same vector (can't distinguish meanings)

**2. Sentence Embeddings** (Used in RAG) ✅
- BERT (2018), Sentence-BERT (2019), OpenAI Ada (2022)
- Entire sentence/paragraph = one vector
- Context-aware: "bank" in "river bank" vs "bank account" = different vectors
- This is what we use!

**3. Specialized Embeddings**
- Code embeddings (for code search)
- Multilingual embeddings (works across languages)
- Domain-specific (medical, legal, nutrition)

---

### Why Embeddings Are Essential for RAG

**Problem**: How do you search documents by **meaning**, not just keywords?

**Without Embeddings** (Keyword Search):
```
Query: "How many calories?"
Traditional Search: Look for documents containing exact words "calories"
Issue: Misses "nutritional value", "energy content", "kcal", etc.
```

**With Embeddings** (Semantic Search):
```
Query: "How many calories?"
Embedding: [0.234, -0.123, 0.456, ...]

Search: Find embeddings with high cosine similarity

Finds:
- "450 calories per serving" (similarity: 0.95)
- "Nutritional value: 450 kcal" (similarity: 0.92)
- "Energy content: 450" (similarity: 0.88)
- "Macros: 30g protein, 450 cal" (similarity: 0.85)
```

**Key Benefit**: Finds documents with **similar meaning**, not just exact word matches!

---

### Embedding Models

**Popular Models for RAG**:

| Model | Dimensions | Cost | Quality | Your Project Uses? |
|-------|-----------|------|---------|-------------------|
| OpenAI text-embedding-3-small | 1536 | $0.00002/1K tokens | Excellent | ✅ YES |
| OpenAI text-embedding-ada-002 | 1536 | $0.0001/1K tokens | Excellent | ❌ (older) |
| Sentence-BERT | 384-768 | FREE | Good | ❌ |
| Cohere Embed | 1024 | $0.0001/1K tokens | Excellent | ❌ |

**Why OpenAI text-embedding-3-small?**
- ✅ Cheapest OpenAI model ($0.02 per 1M tokens!)
- ✅ State-of-the-art quality
- ✅ Fast (1536 dimensions is manageable)
- ✅ Consistent with GPT-4o ecosystem

**Critical Rule**: Use **SAME MODEL** for indexing and querying!
- Index with text-embedding-3-small ✅
- Query with text-embedding-3-small ✅
- Index with ada-002, query with 3-small ❌ BROKEN!

---

## 🥗 Part 3: RAG in Your NutriLens Project

Now let's see **exactly** how RAG is implemented in your codebase.

---

### Your RAG Use Case: Item Normalization

**Problem**: Users scan grocery receipts with messy text
```
Receipt says:
- "HERB MINT"
- "RED CAPSICUM"
- "CHINESE BROCCOLI"
- "LOOSE BEAN SHOOTS"

Database has:
- "mint"
- "bell_pepper"
- "broccoli"
- "bean_sprouts"

Challenge: Match "HERB MINT" → "mint" (not exact match!)
```

**Solution**: RAG Pipeline!

---

### Your RAG Architecture

**File**: `backend/app/services/item_normalizer_rag.py`

**Pipeline** (5 steps):

```
Step 1: EXACT MATCH (100% confidence)
   "mint" → "mint" ✅

Step 2: ALIAS MATCH (95% confidence)
   "peppermint" → "mint" ✅ (alias)

Step 3: VECTOR SIMILARITY >0.90 (92% confidence)
   "herb mint" → "mint" ✅ (high similarity)

Step 4: VECTOR SIMILARITY 0.75-0.90 + LLM VERIFICATION (80% confidence)
   "chinese broccoli" → "broccoli" ✅ (LLM says similar)

Step 5: NO MATCH (<0.75 similarity)
   "japanese pumpkin" → No match ❌ (no pumpkin in DB)
```

---

### Your Database Schema (pgvector)

**Migration**: `alembic/versions/6e8f2a4b9c3d_add_vector_embeddings_to_items_and_recipes.py`

```sql
-- Items table with embeddings
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(100),
    embedding TEXT,  -- Stores 1536 numbers as JSON
    embedding_model VARCHAR(50),  -- "text-embedding-3-small"
    embedding_version INTEGER,
    ...
);

-- Recipes table with embeddings
CREATE TABLE recipes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    embedding TEXT,  -- Stores 1536 numbers as JSON
    ...
);

-- Install pgvector extension (enables vector operations)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create HNSW index for fast similarity search (after embeddings populated)
CREATE INDEX items_embedding_idx
ON items USING hnsw ((embedding::vector(1536)) vector_cosine_ops);

CREATE INDEX recipes_embedding_idx
ON recipes USING hnsw ((embedding::vector(1536)) vector_cosine_ops);
```

**Key Points**:
- pgvector = PostgreSQL extension for vector operations
- HNSW = Fast similarity search algorithm (faster than brute-force)
- Embeddings stored as TEXT (JSON) but cast to vector(1536) for queries

---

### Step-by-Step Code Walkthrough

#### INDEXING PHASE (Done Once)

**File**: `backend/app/services/embedding_service.py`

```python
class EmbeddingService:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.dimension = 1536  # text-embedding-3-small dimension

    async def get_embedding(self, text: str) -> List[float]:
        """Convert text to 1536-dimensional vector"""
        if not text or not text.strip():
            return [0.0] * self.dimension  # Zero vector for empty text

        response = self.client.embeddings.create(
            model=self.model,
            input=text.lower().strip()  # Normalize text
        )
        return response.data[0].embedding  # List of 1536 floats

    def embedding_to_db_string(self, embedding: List[float]) -> str:
        """Convert embedding to JSON for database storage"""
        return json.dumps(embedding)
```

**Usage** (Seeding Script):
```python
# Generate embeddings for all items
embedder = EmbeddingService(api_key=settings.openai_api_key)

for item in items:
    # Generate embedding for item name
    embedding = await embedder.get_embedding(item.canonical_name)

    # Store in database
    item.embedding = embedder.embedding_to_db_string(embedding)
    item.embedding_model = "text-embedding-3-small"
    item.embedding_version = 1
    db.commit()
```

---

#### QUERY PHASE (Every Request)

**File**: `backend/app/services/item_normalizer_rag.py`

##### Step 1-2: Exact/Alias Match (Fast Path)

```python
class RAGItemNormalizer:
    def __init__(self, items_list, db, openai_api_key):
        self.items_cache = self._build_cache()  # Lookup dictionaries
        self.embedder = EmbeddingService(api_key=openai_api_key)
        self.db = db

    def _build_cache(self):
        """Build lookup caches for fast exact/alias matching"""
        cache = {
            'by_name': {},    # {"mint": Item(id=1, name="mint")}
            'by_alias': {},   # {"peppermint": Item(id=1, name="mint")}
        }
        for item in self.items_list:
            cache['by_name'][item.canonical_name.lower()] = item
            for alias in item.aliases:
                cache['by_alias'][alias.lower()] = item
        return cache

    async def normalize_single(self, raw_input: str):
        """RAG pipeline for matching"""
        cleaned = self._clean_text(raw_input)  # "herb_mint"

        # Step 1: Exact match (instant)
        if cleaned in self.items_cache['by_name']:
            return NormalizationResult(
                item=self.items_cache['by_name'][cleaned],
                confidence=1.0,
                matched_on='exact'
            )

        # Step 2: Alias match (instant)
        if cleaned in self.items_cache['by_alias']:
            return NormalizationResult(
                item=self.items_cache['by_alias'][cleaned],
                confidence=0.95,
                matched_on='alias'
            )

        # Step 3: Vector search (RAG retrieval)
        vector_results = await self._vector_search(raw_input, top_k=3)
        ...
```

##### Step 3: Vector Similarity Search

```python
async def _vector_search(self, query_text: str, top_k: int = 3):
    """Vector similarity search using embeddings"""

    # STEP 3A: Generate embedding for query
    embedding = await self.embedder.get_embedding(query_text)
    embedding_str = self.embedder.embedding_to_db_string(embedding)

    # STEP 3B: Similarity query (cosine similarity)
    result = self.db.execute(text("""
        SELECT
            id,
            canonical_name,
            1 - (embedding::vector(1536) <=> :embedding ::vector(1536)) as similarity
        FROM items
        WHERE embedding IS NOT NULL
        ORDER BY embedding::vector(1536) <=> :embedding ::vector(1536)
        LIMIT :top_k
    """), {
        "embedding": embedding_str,
        "top_k": top_k
    }).mappings().fetchall()

    # STEP 3C: Convert to (Item, similarity) tuples
    matches = []
    for row in result:
        item = self._find_item_by_id(row['id'])
        matches.append((item, row['similarity']))

    return matches
    # Returns: [("mint", 0.92), ("peppermint", 0.85), ("spearmint", 0.80)]
```

**Key SQL Operator**: `<=>` (pgvector cosine distance)
- `embedding::vector(1536) <=> :embedding::vector(1536)` = cosine distance
- `1 - distance` = cosine similarity
- Sorted by distance (ascending) = highest similarity first

##### Step 4: High Similarity → Direct Match

```python
best_item, best_similarity = vector_results[0]

# Step 4a: High similarity → Trust it (92%)
if best_similarity >= 0.90:  # self.vector_trust_threshold
    return NormalizationResult(
        item=best_item,
        confidence=0.92,
        matched_on='vector',
        alternatives=vector_results[1:3],
        reasoning=f"High vector similarity ({best_similarity:.2f})"
    )
```

**Example**:
```
Input: "herb mint"
Query Embedding: [0.234, -0.123, ...]
Database Embeddings:
  - "mint": [0.245, -0.118, ...] → Similarity: 0.92 ✅ MATCH!
  - "peppermint": [0.220, -0.130, ...] → Similarity: 0.85
```

##### Step 5: Medium Similarity → LLM Verification (RAG Generation)

```python
# Step 4b: Medium similarity (0.75-0.90) → LLM verification
elif best_similarity >= 0.75:  # self.vector_llm_threshold
    return await self._llm_verify(raw_input, vector_results)
```

```python
async def _llm_verify(self, raw_input: str, vector_results):
    """LLM verification with vector context (RAG generation)"""

    # Prepare context from vector results
    candidates = [
        {
            "id": item.id,
            "name": item.canonical_name,
            "category": item.category,
            "similarity": round(similarity, 3)
        }
        for item, similarity in vector_results[:3]
    ]

    # LLM prompt with RAG context
    prompt = f"""You are a grocery item matcher. A user scanned: "{raw_input}"

VECTOR SEARCH RESULTS (semantic similarity):
{json.dumps(candidates, indent=2)}

TASK: Determine if any candidate is a correct match.

MATCHING RULES:
- "Herb Mint" → "mint" ✅
- "Red Capsicum" → "bell_pepper" ✅ (capsicum = bell pepper)
- "Chinese Broccoli" → "broccoli" ✅ (similar vegetable)
- "Japanese Pumpkin" → NO MATCH ❌ (if pumpkin not in candidates)

OUTPUT (strict JSON): {{"matched": true, "item_id": 1, "confidence": 0.85, "reasoning": "explanation"}}
"""

    # Call LLM
    client = openai.AsyncOpenAI(api_key=openai.api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    # Parse LLM response
    llm_result = json.loads(response.choices[0].message.content)

    if llm_result.get("matched"):
        matched_item = self._find_item_by_id(llm_result["item_id"])
        return NormalizationResult(
            item=matched_item,
            confidence=llm_result["confidence"],
            matched_on='llm_verified',
            reasoning=llm_result["reasoning"]
        )
```

**Example Flow**:
```
Input: "red capsicum"
Query Embedding: [0.456, -0.234, ...]
Database Results:
  - "bell_pepper": Similarity 0.82 (medium - needs verification)
  - "red_onion": Similarity 0.75
  - "tomato": Similarity 0.70

LLM Context:
  "Vector found: bell_pepper (0.82), red_onion (0.75), tomato (0.70)"

LLM Reasoning:
  "Red capsicum is another name for red bell pepper. Match: bell_pepper ✅"

Result:
  item="bell_pepper", confidence=0.85, matched_on='llm_verified'
```

---

### Complete Example: Receipt Scanning

**Input**: Grocery receipt
```
HERB MINT           $2.80
RED CAPSICUM        $3.50
CHINESE BROCCOLI    $4.20
```

**Step 1: Extract Items**
```python
receipt_items = [
    {"item_name": "HERB MINT", "quantity": 1, "unit": "piece"},
    {"item_name": "RED CAPSICUM", "quantity": 1, "unit": "piece"},
    {"item_name": "CHINESE BROCCOLI", "quantity": 1, "unit": "bunch"}
]
```

**Step 2: RAG Pipeline for Each Item**

**Item 1: "HERB MINT"**
```
1. Exact match? "herb_mint" not in database ❌
2. Alias match? "herb_mint" not in aliases ❌
3. Vector search...
   - Generate embedding: [0.234, -0.123, ...]
   - Query database:
     * "mint" → Similarity 0.92 ✅
     * "peppermint" → Similarity 0.85
     * "spearmint" → Similarity 0.80
4. Similarity >= 0.90? YES ✅
   → Match: "mint" (confidence: 0.92)
```

**Item 2: "RED CAPSICUM"**
```
1. Exact match? "red_capsicum" not in database ❌
2. Alias match? "red_capsicum" not in aliases ❌
3. Vector search...
   - Generate embedding: [0.456, -0.234, ...]
   - Query database:
     * "bell_pepper" → Similarity 0.82
     * "red_pepper" → Similarity 0.75
     * "chili" → Similarity 0.65
4. Similarity 0.75-0.90? YES → LLM verification
   - LLM: "Red capsicum = bell pepper" ✅
   → Match: "bell_pepper" (confidence: 0.85)
```

**Item 3: "CHINESE BROCCOLI"**
```
1. Exact match? "chinese_broccoli" not in database ❌
2. Alias match? "chinese_broccoli" not in aliases ❌
3. Vector search...
   - Generate embedding: [0.678, -0.345, ...]
   - Query database:
     * "broccoli" → Similarity 0.88
     * "cabbage" → Similarity 0.70
     * "bok_choy" → Similarity 0.68
4. Similarity 0.75-0.90? YES → LLM verification
   - LLM: "Chinese broccoli is similar to regular broccoli" ✅
   → Match: "broccoli" (confidence: 0.83)
```

**Final Result**:
```python
[
    {"item": "mint", "confidence": 0.92, "matched_on": "vector"},
    {"item": "bell_pepper", "confidence": 0.85, "matched_on": "llm_verified"},
    {"item": "broccoli", "confidence": 0.83, "matched_on": "llm_verified"}
]
```

---

## 📊 Summary Comparison

### RAG vs Non-RAG Approaches

| Approach | Example | Pros | Cons |
|----------|---------|------|------|
| **Exact Match** | "mint" = "mint" | ✅ Fast, 100% accurate | ❌ Fails on variants |
| **Fuzzy Match** | "mnt" ≈ "mint" | ✅ Handles typos | ❌ Many false positives |
| **Keyword Search** | "herb" in "herb mint" | ✅ Fast | ❌ Misses semantics |
| **RAG (Your System)** | "herb mint" → "mint" (semantic) | ✅ Semantic understanding<br>✅ Handles variants<br>✅ LLM verification | ⚠️ Requires embeddings<br>⚠️ Slower than exact |

---

## 🎯 Key Takeaways

### What is RAG?
**Retrieval-Augmented Generation**: Give LLMs access to external data at query time

### How Does RAG Work?
1. **Index**: Convert documents to embeddings, store in vector DB
2. **Query**: Convert user question to embedding
3. **Retrieve**: Find similar documents (cosine similarity)
4. **Generate**: LLM answers using retrieved context

### What Are Embeddings?
**Vectors (lists of numbers) that capture meaning**
- "cat" → [0.2, 0.8, ...]
- "dog" → [0.3, 0.7, ...] (close to cat!)
- "car" → [-0.5, -0.3, ...] (far from cat!)

### Why Embeddings?
**Semantic search**: Find documents by meaning, not just keywords
- "calories" → "nutritional value", "kcal", "energy content"

### How Does NutriLens Use RAG?
**Item Normalization** (grocery receipt → database items)
1. Exact/alias match (fast path)
2. Vector similarity search (pgvector + OpenAI embeddings)
3. LLM verification for ambiguous cases (RAG generation)

**Example**:
- "HERB MINT" → "mint" (vector: 0.92 similarity)
- "RED CAPSICUM" → "bell_pepper" (LLM verified: 0.85 confidence)

### Your Tech Stack
- **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- **Vector DB**: PostgreSQL + pgvector extension
- **Similarity**: Cosine similarity (operator: `<=>`)
- **Index**: HNSW (fast approximate nearest neighbor)
- **LLM**: GPT-4o-mini (verification)

---

## 📚 Further Reading

**Official Documentation**:
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [pgvector](https://github.com/pgvector/pgvector)
- [LangChain RAG Tutorial](https://python.langchain.com/docs/tutorials/rag/)

**Your Codebase**:
- `backend/app/services/embedding_service.py` - Embedding generation
- `backend/app/services/item_normalizer_rag.py` - RAG pipeline
- `alembic/versions/6e8f2a4b9c3d_*.py` - Database schema with embeddings

---

**Document Status**: ✅ COMPLETE
**Last Updated**: 2025-11-25
**Next Steps**: Ready to resume migration work

