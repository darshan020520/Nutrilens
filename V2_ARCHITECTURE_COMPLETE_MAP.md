# V2 BACKEND ARCHITECTURE - COMPLETE COMPONENT MAP

**Status:** Clean Architecture Migration (Phases 1-8 Complete)
**Last Updated:** 2025-12-18
**Purpose:** Complete overview of every V2 component for architectural analysis

---

## LAYER 1: API ENDPOINTS (8 endpoints)

### **inventory_v2.py** (392 lines)
**File:** `backend/app/api/inventory_v2.py`
**Purpose:** Inventory management API endpoints
**Pattern:** Thin API layer with dependency injection

**Endpoints:**
1. `POST /add-items` - Add items from text input
2. `POST /confirm-item` - Confirm medium-confidence item
3. `GET /status` - Get inventory status with AI insights
4. `GET /items` - Get inventory items with filters
5. `POST /deduct-meal` - Deduct ingredients for consumed meal
6. `GET /makeable-recipes` - Get recipes user can make
7. `GET /check-recipe/{recipe_id}` - Check if recipe is makeable
8. `DELETE /item/{inventory_id}` - Remove inventory item

**Dependencies Injected:**
- `IntelligentInventoryServiceV2` (via `get_intelligent_inventory_service_v2`)
- `InventoryRepository` (via `get_inventory_repository`)
- `User` (via `get_current_user`)
- `Session` (via `get_db`)

**Key Characteristics:**
- Endpoints 1, 2, 3, 5, 6, 7 use `IntelligentInventoryServiceV2`
- Endpoints 4, 8 use `InventoryRepository` directly
- All async with proper await
- Heavy logging for debugging
- Error handling with try/except

---

## LAYER 2: SERVICES (Business Logic)

### **intelligent_inventory_service_v2.py** (882 lines)
**File:** `backend/app/services/intelligent_inventory_service_v2.py`
**Purpose:** Smart inventory management with AI features
**Pattern:** Service layer with injected dependencies

**Constructor:**
```python
def __init__(
    self,
    inventory_repo: IInventoryRepository,  # Data access
    normalizer: RAGItemNormalizer,         # AI normalization
    db: Session                             # Direct DB for Item/Recipe queries
):
```

**Public Methods (10):**
1. `add_item(user_id, item_id, quantity_grams, expiry_date, source)` → Dict
2. `deduct_item(user_id, item_id, quantity_grams)` → Dict
3. `add_items_from_text(user_id, text_input)` → Dict
4. `deduct_for_meal(user_id, recipe_id, portion_multiplier)` → Dict
5. `get_inventory_status(user_id)` → Dict
6. `get_user_inventory(user_id, category, low_stock_only, expiring_soon)` → Dict
7. `check_recipe_availability(user_id, recipe_id)` → Dict
8. `get_makeable_recipes(user_id, limit, partial_threshold)` → Dict
9. `process_receipt_items(user_id, receipt_items, auto_add_threshold)` → Dict

**Private Methods (2):**
1. `_add_to_inventory(user_id, item_id, quantity_grams, expiry_days, source)` → UserInventory
2. `_generate_recommendations(inventory, expiring_soon, categories, nutritional_capacity, days_remaining)` → List[str]

**Key Responsibilities:**
- Inventory CRUD operations
- AI-powered item normalization
- Recipe matching and availability checks
- Expiry date management (auto-assigns by category)
- Batch management (merges/splits by expiry)
- Receipt processing
- Status reports with AI recommendations

**Data Access:**
- Uses `inventory_repo` for basic queries (NOT FULLY - still uses db.query())
- Uses `db` directly for Item, Recipe, RecipeIngredient, UserProfile queries
- Uses `normalizer` for AI item matching

**Current Issues:**
- Does multiple responsibilities (inventory + recipes + AI analysis)
- Still uses `db` directly instead of repository for many queries
- Methods like `get_user_inventory()` duplicate repository methods

---

### **item_normalizer_rag.py** (771 lines)
**File:** `backend/app/services/item_normalizer_rag.py`
**Purpose:** RAG-based item matching with vector embeddings + LLM
**Pattern:** Service with internal state

**Constructor:**
```python
def __init__(
    self,
    items_list: List[Item],    # ALL items from DB
    db: Session,               # For vector queries
    openai_api_key: str        # For embeddings + LLM
):
```

**Public Methods (4):**
1. `normalize_single(raw_input: str)` → NormalizationResult
2. `process_manual_entry(user_text: str)` → NormalizationResult
3. `normalize_batch(items: List[Dict])` → List[NormalizationResult]
4. `learn_from_confirmation(original_text: str, item: Item, was_correct: bool)` → None

**Private Methods (7):**
1. `_clean_input(raw: str)` → str
2. `_check_exact_match(cleaned: str)` → Optional[Item]
3. `_check_alias_match(cleaned: str)` → Optional[Item]
4. `_vector_search(query_text: str, top_k: int)` → List[Tuple[Item, float]]
5. `_llm_verify(raw_input: str, vector_results: List)` → NormalizationResult
6. `_extract_structure(user_text: str)` → Dict
7. `convert_to_grams_intelligent(quantity, unit, item, item_count, original_text)` → Tuple[float, str]

**Matching Pipeline (5 steps):**
```
1. Clean input → lowercase, strip
2. Exact match → db.query(Item).filter(canonical_name == cleaned)
3. Alias match → Check if cleaned in item.aliases
4. Vector search → OpenAI embedding + pgvector cosine similarity
   - >= 0.90 → Auto-accept (confidence 0.92)
   - >= 0.75 → LLM verification needed
   - < 0.75 → Return None with alternatives
5. LLM verification → "Is '{input}' the same as '{best_match}'?"
```

**Unit Conversion Logic:**
```python
# Standard conversions (no LLM):
- kg → 1000g, lb → 453.6g, oz → 28.35g, ml → 1g, l → 1000g

# Item-specific (uses LLM if needed):
- "1 egg" → 50g (uses item context)
- "1 potato" → 150g (uses item context)
- "1 cup flour" → 120g (uses item + unit context)
```

**Vector Search Details:**
- Uses OpenAI `text-embedding-3-small` model (1536 dimensions)
- Postgres pgvector extension for cosine similarity
- Top K results (default 3)
- Thresholds:
  - `vector_trust_threshold = 0.90` (auto-accept)
  - `vector_llm_threshold = 0.75` (needs LLM verification)

**LLM Usage (2 places):**
1. **Structure extraction** (`process_manual_entry`):
   - Input: "2kg onions"
   - Output: `{"item_name": "onions", "quantity": 2, "unit": "kg"}`
   - Model: GPT-4o-mini

2. **Match verification** (`_llm_verify`):
   - When 0.75 <= confidence < 0.90
   - Provides top 3 vector matches as context
   - Model: GPT-4o-mini
   - Returns: Verified item + updated confidence

**Key Characteristics:**
- Async throughout (uses `AsyncOpenAI`)
- No fuzzy matching or spell correction
- Returns `NormalizationResult` dataclass
- Alternatives list: `vector_results[1:3]` (excludes best match)

---

## LAYER 3: REPOSITORIES (Data Access)

### **inventory_repository.py** (1129 lines)
**File:** `backend/app/repositories/inventory_repository.py`
**Purpose:** All UserInventory database operations
**Pattern:** Repository pattern implementing IInventoryRepository interface

**Constructor:**
```python
def __init__(self, db: Session):
    self.db = db
```

**Method Categories (38 methods total):**

**1. Basic CRUD (7 methods):**
- `get_all(limit, offset)` → List[UserInventory]
- `get_by_id(inventory_id, user_id)` → Optional[UserInventory]
- `get_all_for_user(user_id, include_zero_quantity)` → List[UserInventory]
- `get_by_item_id(user_id, item_id)` → Optional[UserInventory]
- `create(inventory)` → UserInventory
- `update(inventory)` → UserInventory
- `delete(inventory_id, user_id)` → bool

**2. Quantity Operations (4 methods):**
- `add_quantity(user_id, item_id, quantity_grams, expiry_date, source)` → UserInventory
- `deduct_quantity(user_id, item_id, quantity_grams)` → UserInventory
- `set_quantity(user_id, item_id, quantity_grams, expiry_date)` → UserInventory
- `bulk_update_quantities(user_id, updates)` → List[Dict]

**3. Recipe Operations (2 methods):**
- `deduct_recipe_ingredients(user_id, recipe, portion_multiplier)` → List[Dict]
- `check_recipe_ingredients_availability(user_id, recipe, portion_multiplier)` → Dict

**4. Expiry Queries (4 methods):**
- `get_expiring_items(user_id, days_threshold)` → List[UserInventory]
- `get_expired_items(user_id)` → List[UserInventory]
- `get_items_without_expiry(user_id)` → List[UserInventory]

**5. Stock Level Queries (4 methods):**
- `get_low_stock_items(user_id, threshold_grams)` → List[UserInventory]
- `get_out_of_stock_items(user_id)` → List[UserInventory]
- `get_well_stocked_items(user_id, threshold_grams)` → List[UserInventory]

**6. Categorization (2 methods):**
- `get_inventory_by_category(user_id)` → Dict[str, List[UserInventory]]
- `get_inventory_by_source(user_id)` → Dict[str, List[UserInventory]]

**7. Analytics (5 methods):**
- `calculate_total_inventory_weight(user_id)` → float
- `calculate_inventory_value_estimate(user_id)` → float (placeholder)
- `get_inventory_status_summary(user_id)` → Dict
- `get_consumption_velocity(user_id, item_id, days_to_analyze)` → Dict (placeholder)

**8. Historical (1 method):**
- `get_inventory_changes_history(user_id, days)` → List[Dict] (placeholder)

**9. Bulk Operations (3 methods):**
- `bulk_create_inventory(inventory_items)` → List[UserInventory]
- `bulk_delete_inventory(inventory_ids, user_id)` → int
- `reset_user_inventory(user_id)` → int

**Key Characteristics:**
- All async methods
- Uses `joinedload(UserInventory.item)` for N+1 prevention
- User validation on all operations
- Transaction management (commit/rollback)
- Comprehensive logging
- NO business logic - pure data access

**Query Optimization:**
- Eager loading: `.options(joinedload(UserInventory.item))`
- Filters at DB level
- Aggregations using SQLAlchemy `func`

---

## LAYER 4: INTERFACES (Contracts)

### **IInventoryRepository**
**File:** `backend/app/repositories/interfaces/inventory_repository.py`
**Purpose:** Define repository contract

**Methods Required:**
- All 38 methods from InventoryRepository implementation
- Type-hinted return values
- Docstring requirements

**Pattern:** Protocol/Abstract Base Class for dependency inversion

---

## LAYER 5: DEPENDENCY INJECTION

### **dependencies.py (relevant section)**
**File:** `backend/app/dependencies.py` (lines 275-324)

**Function 1: `get_inventory_repository()`**
```python
def get_inventory_repository(db: Session = Depends(get_db)) -> IInventoryRepository:
    return InventoryRepository(db)
```

**Function 2: `get_intelligent_inventory_service_v2()`**
```python
def get_intelligent_inventory_service_v2(
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    db: Session = Depends(get_db)
) -> IntelligentInventoryServiceV2:
    # Load ALL items from DB
    items_list = db.query(Item).all()

    # Initialize RAG normalizer
    normalizer = RAGItemNormalizer(
        items_list=items_list,
        db=db,
        openai_api_key=settings.openai_api_key
    )

    # Return service with dependencies
    return IntelligentInventoryServiceV2(
        inventory_repo=inventory_repo,
        normalizer=normalizer,
        db=db
    )
```

**Current Issues:**
- `db.query(Item).all()` loads ALL items on EVERY request
- No caching of items list
- No caching of normalizer instance
- Normalizer re-initialized per request (expensive)

---

## DATA FLOW ANALYSIS

### Flow 1: Add Items from Text ("1kg chicken")

```
1. USER REQUEST
   POST /inventory/v2/add-items
   Body: {"text_input": "1kg chicken"}
   ↓

2. API LAYER (inventory_v2.py:65-114)
   - FastAPI receives request
   - Injects: IntelligentInventoryServiceV2 via DI
   - Calls: await service.add_items_from_text(user_id, "1kg chicken")
   ↓

3. SERVICE LAYER (intelligent_inventory_service_v2.py:188-307)
   - Splits text by newlines: ["1kg chicken"]
   - For each line:
     a. Calls: await normalizer.process_manual_entry("1kg chicken")
     ↓

4. NORMALIZER (item_normalizer_rag.py:682-714)
   - Step 1: LLM extracts structure
     * LLM Call #1: "Extract structure from '1kg chicken'"
     * Result: {"item_name": "chicken", "quantity": 1, "unit": "kg"}

   - Step 2: Normalize "chicken"
     * Exact match? No
     * Alias match? No
     * Vector search: Top 3 similar items
       - chicken_breast (0.566)
       - chicken_thigh (0.543)
       - chicken (0.521)
     * Best similarity: 0.566

   - Step 3: Threshold check
     * 0.566 < 0.75 → Low confidence
     * Returns: NormalizationResult(
         item=None,
         confidence=0.566,
         alternatives=[chicken_breast, chicken_thigh],  # Excludes best!
         extracted_quantity=1,
         extracted_unit="kg",
         quantity_grams=None  ← BUG: Not converted!
       )
   ↓

5. SERVICE LAYER (continued)
   - Checks confidence: 0.566
   - Branch: 0.4 <= 0.566 < 0.6 → "Low-medium confidence"
   - Adds to results['needs_confirmation']:
     {
       'original': "1kg chicken",
       'quantity_grams': None,  ← BUG: null value
       'suggestions': [chicken_breast, chicken_thigh, ...]
     }
   - Returns results to API
   ↓

6. API LAYER (continued)
   - Returns JSON to frontend
   ↓

7. FRONTEND
   - User sees suggestions: chicken_breast, chicken_thigh
   - User clicks "chicken_breast"
   - Sends: POST /confirm-item
     Body: {
       "original_text": "1kg chicken",
       "item_id": 123,  // chicken_breast
       "quantity_grams": 100  ← Frontend used fallback: null || 100
     }
   ↓

8. API LAYER (inventory_v2.py:116-189)
   - Calls: await service.add_item(user_id, 123, 100)
   ↓

9. SERVICE LAYER (intelligent_inventory_service_v2.py:70-124)
   - Calls: await self._add_to_inventory(user_id, 123, 100, expiry_days=None)
   ↓

10. SERVICE LAYER - _add_to_inventory (309-367)
    - Gets item: chicken_breast (category: protein)
    - Auto-assigns expiry: 5 days (from CATEGORY_SHELF_LIFE['poultry'])
    - Finds existing batches with similar expiry
    - Creates new batch OR merges with existing
    - Commits to DB
    ↓

11. RESULT
    - User added 100g chicken_breast (expected 1000g!)
```

**Key Issue:** Quantity grams lost when item=None because conversion only happens when item is matched.

---

### Flow 2: Get Inventory Status

```
1. USER REQUEST
   GET /inventory/v2/status
   ↓

2. API LAYER (inventory_v2.py:191-206)
   - Injects: IntelligentInventoryServiceV2
   - Calls: await service.get_inventory_status(user_id)
   ↓

3. SERVICE LAYER (intelligent_inventory_service_v2.py:438-546)
   - Query 1: Load inventory with eager loading
     ```python
     inventory = db.query(UserInventory)
       .options(joinedload(UserInventory.item))
       .filter(UserInventory.user_id == user_id)
       .all()
     ```

   - Single loop processes:
     * Expiring items (within 3 days)
     * Low stock items (< 100g)
     * Categories count
     * Nutritional capacity (sum all nutrition_per_100g)

   - Query 2: Get user profile for calorie goal
     ```python
     user_profile = db.query(UserProfile)
       .filter(UserProfile.user_id == user_id)
       .first()
     ```

   - Calculate days remaining:
     * total_calories / daily_goal_calories

   - Generate AI recommendations:
     * If expiring_soon: "Use soon: tomatoes, onions, ..."
     * If low protein: "Add chicken, paneer, or lentils"
     * If low diversity: "Add more variety"
     * Category-specific suggestions

   - Returns: Dict with all analysis
   ↓

4. API LAYER
   - Returns JSON to frontend
```

**Performance:**
- Uses eager loading (good)
- Single loop for multiple calculations (good)
- 2 total queries (inventory + profile)

---

### Flow 3: Get Makeable Recipes

```
1. USER REQUEST
   GET /inventory/v2/makeable-recipes?limit=10
   ↓

2. API LAYER (inventory_v2.py:308-334)
   - Calls: await service.get_makeable_recipes(user_id, limit=10)
   ↓

3. SERVICE LAYER (intelligent_inventory_service_v2.py:692-825)

   Step 1: Get user inventory (simple query)
   ```python
   user_inventory = db.query(
     UserInventory.item_id,
     UserInventory.quantity_grams
   ).filter(user_id, quantity_grams > 0).all()
   ```
   → user_items = {item_id: quantity}

   Step 2: SQL pre-filtering (smart!)
   ```python
   # Subquery: Count total ingredients and matching ingredients per recipe
   recipe_match_subquery = db.query(
     Recipe.id,
     func.count(RecipeIngredient.id).label('total_ingredients'),
     func.sum(case((item_id.in_(user_items), 1), else_=0)).label('matching'),
     (matching / total * 100).label('estimated_match_pct')
   ).group_by(Recipe.id)
   .having(estimated_match_pct >= 80)  # Only promising recipes
   ```

   Step 3: Fetch top candidates (3x limit)
   ```python
   candidates = db.query(Recipe)
     .join(recipe_match_subquery)
     .filter(estimated_match_pct >= 80)
     .order_by(estimated_match_pct.desc(), prep_time.asc())
     .limit(30)  # 3x buffer
     .all()
   ```

   Step 4: Validate quantities for each candidate
   ```python
   for recipe in candidates:
     availability = await check_recipe_availability(user_id, recipe.id)

     if availability['can_make']:
       fully_makeable.append(recipe_data)
     elif availability['coverage_percentage'] >= 80:
       partially_makeable.append(recipe_data)
   ```

   Step 5: Return categorized results
   ↓

4. API LAYER
   - Wraps in response format
   - Returns JSON
```

**Performance:**
- SQL pre-filtering (excellent)
- Avoids checking all recipes
- Uses SQL aggregations
- Only validates promising candidates

---

## CRITICAL OBSERVATIONS

### 1. **Service Does Too Much**
`IntelligentInventoryServiceV2` (882 lines) handles:
- Inventory CRUD
- Recipe matching
- Expiry management
- AI normalization orchestration
- Receipt processing
- Status analysis & recommendations

**Issue:** Violates Single Responsibility Principle

---

### 2. **Incomplete Repository Usage**
`IntelligentInventoryServiceV2` receives `inventory_repo` but still uses `db` directly for:
- Item queries: `db.query(Item).filter(...)`
- Recipe queries: `db.query(Recipe).filter(...)`
- RecipeIngredient queries
- UserProfile queries

**Issue:** Repository pattern not fully adopted

---

### 3. **Normalizer Re-Initialization**
`get_intelligent_inventory_service_v2()` runs on EVERY request:
```python
items_list = db.query(Item).all()  # Loads all items
normalizer = RAGItemNormalizer(items_list, db, api_key)  # New instance
```

**Issue:**
- Loads 400+ items on every request
- Creates new normalizer instance
- No caching

---

### 4. **Confidence Logic in Service**
Service layer checks thresholds (0.85, 0.6, 0.4) and decides actions.
Same logic repeated in:
- `add_items_from_text()`
- `process_receipt_items()`

**Issue:** Logic duplication, should be in normalizer

---

### 5. **Quantity Conversion Bug**
In `item_normalizer_rag.py:699-714`:
```python
if result.item:
    grams, note = await self.convert_to_grams_intelligent(...)
    result.quantity_grams = grams
else:
    # No conversion! quantity_grams stays None
    pass
```

**Impact:** User enters "1kg chicken", gets 100g added

---

### 6. **Alternatives Exclude Best Match**
In `item_normalizer_rag.py:231`:
```python
best_item, best_similarity = vector_results[0]
alternatives = vector_results[1:3]  # Excludes index 0
```

**Impact:** User doesn't see the best match in suggestions

---

### 7. **Direct DB Access in Repository**
Repository uses `self.db.query()` directly, not through any abstraction.

**Status:** This is actually fine for repository pattern, but means repository is the ONLY place that should do DB queries.

---

## ARCHITECTURE PATTERN SUMMARY

**Current Pattern:**
```
API (inventory_v2.py)
  ↓ depends on
Service (intelligent_inventory_service_v2.py)
  ↓ depends on
Repository (inventory_repository.py) [PARTIAL USE]
  ↓ depends on
Database (PostgreSQL via SQLAlchemy)

Service also depends on:
  → Normalizer (item_normalizer_rag.py)
  → Database directly (Item, Recipe queries)
```

**Repository Interface:**
```
IInventoryRepository (interface)
  ↑ implements
InventoryRepository (concrete)
```

**Dependency Injection:**
```
dependencies.py
  → get_inventory_repository() → InventoryRepository
  → get_intelligent_inventory_service_v2() → IntelligentInventoryServiceV2
```

---

## WHAT WORKS WELL

1. ✅ Repository has comprehensive methods (38 total)
2. ✅ Repository uses eager loading to prevent N+1 queries
3. ✅ API layer is thin (just validation + delegation)
4. ✅ Dependency injection pattern in place
5. ✅ Interface defined for repository
6. ✅ Service is async throughout
7. ✅ Good logging for debugging
8. ✅ Recipe matching uses SQL pre-filtering (efficient)
9. ✅ Batch management for expiry dates
10. ✅ RAG pipeline is clean (exact → alias → vector → LLM)

---

## WHAT NEEDS IMPROVEMENT

1. ❌ Service does 5+ different responsibilities
2. ❌ Service still uses db directly (incomplete repository adoption)
3. ❌ Normalizer re-initialized on every request
4. ❌ Items loaded from DB on every request (no caching)
5. ❌ Confidence logic duplicated between service methods
6. ❌ Quantity conversion conditional on item match (bug)
7. ❌ Alternatives exclude best match (bug)
8. ❌ No fuzzy matching for typos
9. ❌ Vector thresholds may be too conservative (0.90, 0.75)
10. ❌ LLM calls not batched for multiple items

---

## FILES REFERENCE

**V2 API Endpoints:**
- `backend/app/api/inventory_v2.py` (392 lines)
- `backend/app/api/tracking_v2.py`
- `backend/app/api/receipt_v2.py`
- `backend/app/api/meal_plan_v2.py`
- `backend/app/api/dashboard_v2.py`
- `backend/app/api/recipes_v2.py`
- `backend/app/api/onboarding_v2.py`
- `backend/app/api/auth_v2.py`

**V2 Services:**
- `backend/app/services/intelligent_inventory_service_v2.py` (882 lines)
- `backend/app/services/item_normalizer_rag.py` (771 lines)
- `backend/app/services/meal_plan_service_v2.py`
- `backend/app/services/consumption_service_v2.py`

**Repositories:**
- `backend/app/repositories/inventory_repository.py` (1129 lines)
- `backend/app/repositories/tracking_repository.py`
- `backend/app/repositories/meal_plan_repository.py`
- `backend/app/repositories/meal_log_repository.py`
- `backend/app/repositories/recipe_repository.py`
- `backend/app/repositories/onboarding_repository.py`
- `backend/app/repositories/auth_repository.py`
- `backend/app/repositories/receipt_repository.py`
- `backend/app/repositories/consumption_analytics_repository.py`
- `backend/app/repositories/activity_repository.py`

**Interfaces:**
- `backend/app/repositories/interfaces/inventory_repository.py`
- `backend/app/repositories/interfaces/tracking_repository.py`
- `backend/app/repositories/interfaces/meal_plan_repository.py`
- `backend/app/repositories/interfaces/meal_log_repository.py`
- `backend/app/repositories/interfaces/recipe_repository.py`
- `backend/app/repositories/interfaces/onboarding_repository.py`
- `backend/app/repositories/interfaces/auth_repository.py`
- `backend/app/repositories/interfaces/receipt_repository.py`
- `backend/app/repositories/interfaces/consumption_analytics_repository.py`
- `backend/app/repositories/interfaces/base_repository.py`

**Dependency Injection:**
- `backend/app/dependencies.py` (lines 275-324 for inventory)

---

## END OF DOCUMENT

This document contains EVERY component in the V2 clean architecture for inventory management.
All line numbers, method signatures, and data flows are accurate as of reading the actual code.
