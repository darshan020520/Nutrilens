# Phase 2: Tracking Endpoints - Full Refactoring Execution Plan

**Date**: 2025-11-25
**Approach**: **FULL REPOSITORY PATTERN REFACTORING**
**Principle**: Build solid, reusable foundations for future phases
**No Shortcuts**: Complete extraction of all business logic and data access

---

## 🎯 Core Principle: Full Refactoring for Solid Foundations

**User Requirement**:
> "I want full refactoring. Please make sure we lay solid foundations for the used services such that in later refactorings where these services and repositories are used we can leverage the work of refactoring that we have done."

**Our Commitment**:
- ✅ **Complete separation of concerns** (API → Orchestrator → Service → Repository → Database)
- ✅ **Zero shortcuts** - No "keeping agent as is"
- ✅ **Full extraction** - All business logic moved to services
- ✅ **Reusable components** - Services and repos designed for Phase 3+
- ✅ **Clean architecture** - Strict adherence to SOLID principles
- ✅ **Future-proof** - Later phases can build on this foundation

---

## 📋 Phase 2 Scope Reminder

### 9 Active Endpoints to Migrate

**Core Meal Tracking (3)**:
1. `POST /tracking/log-meal` - Log meal consumption with inventory deduction
2. `POST /tracking/skip-meal` - Mark meal as skipped with reason
3. `GET /tracking/today` - Get today's consumption summary

**External Meal Logging (2)**:
4. `POST /tracking/estimate-external-meal` - LLM-based nutrition estimation
5. `POST /tracking/log-external-meal` - Log restaurant/external meal

**Consumption History (1)**:
6. `GET /tracking/history` - Historical consumption data (1-90 days)

**Inventory Management (3)**:
7. `GET /tracking/inventory-status` - Current inventory analytics
8. `GET /tracking/expiring-items` - Items expiring soon with recipes
9. `GET /tracking/restock-list` - Shopping recommendations

---

## 🏗️ Architecture: Complete Layered Design

### Current State (Phase 1)
```
API Endpoints
    ↓
TrackingAgent (1977 lines) ← MONOLITHIC, needs full refactoring
    ↓
Direct DB Access + Service Calls
```

**Problems**:
- ❌ Mixed concerns (business logic + data access)
- ❌ Hard to test
- ❌ Cannot reuse logic
- ❌ Violates Single Responsibility Principle

### Target State (Phase 2)
```
API Endpoints (tracking_v2.py)
    ↓
Orchestrators (coordinate workflows)
    ↓
Services (business logic)
    ↓
Repositories (data access)
    ↓
Database Models
```

**Benefits**:
- ✅ Clear separation of concerns
- ✅ Each layer has single responsibility
- ✅ Highly testable (mock each layer)
- ✅ Reusable across endpoints
- ✅ Easy to extend in future phases

---

## 📦 Components to Build (Complete List)

### Layer 1: Repositories (Data Access Only)

#### 1. TrackingRepository
**File**: `backend/app/repositories/tracking_repository.py`
**Interface**: `backend/app/repositories/interfaces/tracking_repository.py`
**Responsibility**: ALL meal log and tracking data access
**LOC**: ~400 lines

**Methods** (20+ methods):
```python
class ITrackingRepository(IRepository[MealLog]):
    """Interface for tracking data access"""

    # === MEAL LOG CRUD ===
    def get_by_id(self, meal_log_id: int, user_id: int) -> Optional[MealLog]
    def get_all_for_user(self, user_id: int) -> List[MealLog]
    def create(self, meal_log: MealLog) -> MealLog
    def update(self, meal_log: MealLog) -> MealLog
    def delete(self, meal_log_id: int, user_id: int) -> bool

    # === DATE-BASED QUERIES ===
    def get_by_date(self, user_id: int, date: date) -> List[MealLog]
    def get_by_date_range(self, user_id: int, start: date, end: date) -> List[MealLog]
    def get_todays_meals(self, user_id: int) -> List[MealLog]
    def get_upcoming_meals(self, user_id: int, days: int) -> List[MealLog]

    # === STATUS-BASED QUERIES ===
    def get_consumed_meals(self, user_id: int, start: date, end: date) -> List[MealLog]
    def get_skipped_meals(self, user_id: int, start: date, end: date) -> List[MealLog]
    def get_pending_meals(self, user_id: int, date: date) -> List[MealLog]
    def get_external_meals(self, user_id: int, start: date, end: date) -> List[MealLog]

    # === MEAL LOGGING OPERATIONS ===
    def mark_as_consumed(
        self,
        meal_log_id: int,
        user_id: int,
        consumed_at: datetime,
        portion_multiplier: float,
        notes: Optional[str]
    ) -> MealLog

    def mark_as_skipped(
        self,
        meal_log_id: int,
        user_id: int,
        reason: Optional[str]
    ) -> MealLog

    def create_external_meal_log(
        self,
        user_id: int,
        meal_type: str,
        consumed_at: datetime,
        external_meal_data: dict,
        notes: Optional[str]
    ) -> MealLog

    def replace_planned_with_external(
        self,
        meal_log_id: int,
        user_id: int,
        consumed_at: datetime,
        external_meal_data: dict,
        notes: Optional[str]
    ) -> MealLog

    # === ANALYTICS QUERIES ===
    def count_meals_by_status(
        self,
        user_id: int,
        start: date,
        end: date
    ) -> dict  # {"consumed": 15, "skipped": 3, "pending": 2}

    def get_adherence_rate(
        self,
        user_id: int,
        days: int
    ) -> float  # 0.0 to 1.0

    def get_meal_timing_patterns(
        self,
        user_id: int,
        days: int
    ) -> List[dict]  # Average consumption times per meal type

    def get_skip_frequency_by_meal_type(
        self,
        user_id: int,
        days: int
    ) -> dict  # {"breakfast": 0.1, "lunch": 0.05, ...}
```

#### 2. InventoryRepository
**File**: `backend/app/repositories/inventory_repository.py`
**Interface**: `backend/app/repositories/interfaces/inventory_repository.py`
**Responsibility**: ALL inventory data access
**LOC**: ~350 lines

**Methods** (18+ methods):
```python
class IInventoryRepository(IRepository[UserInventory]):
    """Interface for inventory data access"""

    # === INVENTORY CRUD ===
    def get_by_id(self, inventory_id: int, user_id: int) -> Optional[UserInventory]
    def get_all_for_user(self, user_id: int) -> List[UserInventory]
    def get_by_item_id(self, user_id: int, item_id: int) -> Optional[UserInventory]
    def create(self, inventory: UserInventory) -> UserInventory
    def update(self, inventory: UserInventory) -> UserInventory
    def delete(self, inventory_id: int, user_id: int) -> bool

    # === QUANTITY OPERATIONS ===
    def add_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date]
    ) -> UserInventory

    def deduct_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float
    ) -> UserInventory

    def set_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity_grams: float,
        expiry_date: Optional[date]
    ) -> UserInventory

    def bulk_deduct(
        self,
        user_id: int,
        deductions: List[dict]  # [{"item_id": 1, "quantity": 100}, ...]
    ) -> List[dict]  # Returns success/failure for each

    # === RECIPE INGREDIENT DEDUCTIONS ===
    def deduct_recipe_ingredients(
        self,
        user_id: int,
        recipe: Recipe,
        portion_multiplier: float
    ) -> List[dict]  # Detailed deduction results

    # === ANALYTICS QUERIES ===
    def get_expiring_items(
        self,
        user_id: int,
        days_threshold: int
    ) -> List[UserInventory]

    def get_low_stock_items(
        self,
        user_id: int,
        threshold_percentage: float = 0.2
    ) -> List[UserInventory]

    def get_out_of_stock_items(
        self,
        user_id: int
    ) -> List[UserInventory]

    def get_overstocked_items(
        self,
        user_id: int,
        threshold_days: int = 14
    ) -> List[UserInventory]

    def get_inventory_by_category(
        self,
        user_id: int
    ) -> dict  # {"protein": [...], "vegetables": [...], ...}

    def get_total_inventory_value(
        self,
        user_id: int
    ) -> float  # Estimated total value

    def calculate_stock_percentage(
        self,
        user_id: int
    ) -> float  # Overall stock level 0-100%
```

#### 3. ConsumptionAnalyticsRepository (NEW)
**File**: `backend/app/repositories/consumption_analytics_repository.py`
**Interface**: `backend/app/repositories/interfaces/consumption_analytics_repository.py`
**Responsibility**: Complex analytics queries for consumption patterns
**LOC**: ~200 lines

**Methods**:
```python
class IConsumptionAnalyticsRepository(ABC):
    """Interface for consumption analytics queries"""

    def get_daily_totals(
        self,
        user_id: int,
        start: date,
        end: date
    ) -> List[dict]  # Daily calorie and macro totals

    def get_consumption_trends(
        self,
        user_id: int,
        days: int
    ) -> dict  # Trend analysis (increasing/decreasing)

    def get_meal_completion_stats(
        self,
        user_id: int,
        days: int
    ) -> dict  # Completion rates by meal type

    def get_portion_size_preferences(
        self,
        user_id: int,
        days: int
    ) -> dict  # Average portion multipliers

    def get_adherence_by_day_of_week(
        self,
        user_id: int,
        weeks: int
    ) -> dict  # {"Monday": 0.95, "Tuesday": 0.88, ...}

    def get_most_skipped_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[dict]  # Recipes with high skip rates
```

---

### Layer 2: Services (Business Logic Only)

#### 1. MealTrackingService
**File**: `backend/app/services/meal_tracking_service.py`
**Responsibility**: Business logic for meal logging, skipping, and daily summaries
**LOC**: ~500 lines

**Dependencies**:
- TrackingRepository (data access)
- InventoryRepository (for ingredient deductions)
- ConsumptionAnalyticsRepository (for summaries)
- NotificationService (for alerts)

**Methods** (extracted from TrackingAgent):
```python
class MealTrackingService:
    """Business logic for meal tracking"""

    def __init__(
        self,
        tracking_repo: ITrackingRepository,
        inventory_repo: IInventoryRepository,
        analytics_repo: IConsumptionAnalyticsRepository,
        notification_service: NotificationService
    ):
        self.tracking_repo = tracking_repo
        self.inventory_repo = inventory_repo
        self.analytics_repo = analytics_repo
        self.notification_service = notification_service

    # === CORE MEAL TRACKING ===
    def log_meal(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float,
        notes: Optional[str]
    ) -> dict:
        """
        Log meal consumption with automatic inventory deduction

        Returns:
        {
            "success": True,
            "meal_type": "lunch",
            "recipe": "Chicken Salad",
            "consumed_at": "2025-11-25T12:30:00",
            "macros_consumed": {...},
            "deducted_items": [...],
            "daily_totals": {...},
            "insights": [...],
            "recommendations": [...]
        }
        """

    def skip_meal(
        self,
        user_id: int,
        meal_log_id: int,
        reason: Optional[str]
    ) -> dict:
        """
        Mark meal as skipped with adherence analysis

        Returns:
        {
            "success": True,
            "meal_type": "breakfast",
            "recipe_name": "Oatmeal",
            "adherence_impact": {...},
            "updated_adherence_rate": 0.85,
            "insights": [...],
            "recommendations": [...]
        }
        """

    def get_today_summary(self, user_id: int) -> dict:
        """Get comprehensive today's summary"""

    def get_consumption_history(
        self,
        user_id: int,
        days: int,
        include_details: bool = True
    ) -> dict:
        """Get historical consumption with statistics"""

    # === VALIDATION ===
    def validate_meal_log_access(
        self,
        user_id: int,
        meal_log_id: int
    ) -> MealLog:
        """Validate user owns meal log and it's not already logged"""

    def can_log_meal(self, meal_log: MealLog) -> Tuple[bool, Optional[str]]:
        """Check if meal can be logged (not already consumed/skipped)"""

    def can_skip_meal(self, meal_log: MealLog) -> Tuple[bool, Optional[str]]:
        """Check if meal can be skipped (not already consumed/skipped)"""

    # === ANALYTICS ===
    def calculate_daily_totals(self, user_id: int, date: date) -> dict:
        """Calculate totals for specific date"""

    def calculate_adherence_rate(self, user_id: int, days: int) -> float:
        """Calculate adherence rate over period"""

    def analyze_skip_patterns(self, user_id: int, days: int) -> dict:
        """Analyze skipping patterns"""

    # === INSIGHTS & RECOMMENDATIONS ===
    def generate_meal_insights(
        self,
        user_id: int,
        meal_log: MealLog,
        daily_totals: dict
    ) -> List[str]:
        """Generate insights after meal logging"""

    def generate_skip_insights(
        self,
        user_id: int,
        meal_log: MealLog,
        adherence_rate: float
    ) -> List[str]:
        """Generate insights after meal skip"""

    def generate_adherence_recommendations(
        self,
        user_id: int,
        adherence_rate: float,
        skip_patterns: dict
    ) -> List[str]:
        """Generate recommendations to improve adherence"""
```

#### 2. ExternalMealService
**File**: `backend/app/services/external_meal_service.py`
**Responsibility**: Business logic for external meal estimation and logging
**LOC**: ~300 lines

**Dependencies**:
- TrackingRepository (data access)
- LLM Nutrition Estimator (external service)

**Methods**:
```python
class ExternalMealService:
    """Business logic for external meal handling"""

    def estimate_nutrition(
        self,
        dish_name: str,
        portion_size: str,
        restaurant_name: Optional[str] = None,
        cuisine_type: Optional[str] = None
    ) -> dict:
        """Use LLM to estimate nutrition for external meal"""

    def log_external_meal(
        self,
        user_id: int,
        meal_data: dict,
        meal_log_id_to_replace: Optional[int] = None,
        meal_type: Optional[str] = None,
        notes: Optional[str] = None
    ) -> dict:
        """Log external meal (replace planned or add new)"""

    def get_remaining_meals_for_adjustment(
        self,
        user_id: int,
        date: date
    ) -> List[dict]:
        """Get remaining meals that could be adjusted"""

    def generate_post_external_meal_insights(
        self,
        user_id: int,
        logged_meal: MealLog,
        daily_totals: dict,
        target_calories: int
    ) -> dict:
        """Generate insights after logging external meal"""
```

#### 3. InventoryManagementService
**File**: `backend/app/services/inventory_management_service.py`
**Responsibility**: Business logic for inventory analytics and recommendations
**LOC**: ~400 lines

**Dependencies**:
- InventoryRepository (data access)
- TrackingRepository (for consumption patterns)
- RecipeRepository (for recipe suggestions)

**Methods**:
```python
class InventoryManagementService:
    """Business logic for inventory management"""

    def get_inventory_status(self, user_id: int) -> dict:
        """Get comprehensive inventory status with analytics"""

    def get_expiring_items_with_recipes(
        self,
        user_id: int,
        days: int,
        filter_mode: str = "both"
    ) -> dict:
        """
        Get expiring items with intelligent filtering and recipe suggestions

        Filter modes:
        - date_only: Just check expiry dates
        - consumption_only: Check if will be consumed before expiry
        - both: Combine both filters
        """

    def generate_restock_list(self, user_id: int) -> dict:
        """Generate intelligent shopping list with priorities"""

    def calculate_stock_level(self, user_id: int) -> float:
        """Calculate overall stock level percentage"""

    def analyze_consumption_vs_stock(
        self,
        user_id: int,
        item_id: int,
        days_to_analyze: int = 14
    ) -> dict:
        """Analyze if item will be consumed before expiry"""

    def suggest_recipes_for_ingredients(
        self,
        user_id: int,
        item_ids: List[int],
        max_recipes: int = 5
    ) -> List[dict]:
        """Suggest recipes that use expiring ingredients"""

    def categorize_inventory_by_priority(
        self,
        user_id: int
    ) -> dict:
        """Categorize items: urgent, high, medium, low"""

    def generate_inventory_recommendations(
        self,
        user_id: int,
        inventory_status: dict
    ) -> List[str]:
        """Generate actionable inventory recommendations"""
```

#### 4. ConsumptionService (REFACTOR EXISTING)
**File**: `backend/app/services/consumption_services.py` (already exists)
**Action**: Refactor to use new repositories instead of direct DB access
**LOC**: ~300 lines (existing, needs refactoring)

**Refactoring**:
- Replace all direct DB queries with repository calls
- Keep existing method signatures (for backward compatibility)
- Add new methods as needed

---

### Layer 3: Orchestrators (Workflow Coordination)

#### 1. MealLoggingOrchestrator
**File**: `backend/app/orchestrators/meal_logging_orchestrator.py`
**Responsibility**: Coordinate complex meal logging workflows with events
**LOC**: ~200 lines

**Dependencies**:
- MealTrackingService
- InventoryManagementService
- EventPublisher

**Methods**:
```python
class MealLoggingOrchestrator(BaseOrchestrator):
    """Orchestrate meal logging workflows"""

    async def log_meal_with_inventory_update(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float,
        notes: Optional[str]
    ) -> dict:
        """
        Complete meal logging workflow:
        1. Validate meal log
        2. Mark meal as consumed
        3. Deduct ingredients from inventory
        4. Update daily totals
        5. Generate insights and recommendations
        6. Publish MealLoggedEvent
        7. Check for achievements (if system exists)
        8. Send notifications (if applicable)
        """

    async def skip_meal_with_analytics(
        self,
        user_id: int,
        meal_log_id: int,
        reason: Optional[str]
    ) -> dict:
        """
        Complete meal skip workflow:
        1. Validate meal log
        2. Mark meal as skipped
        3. Update adherence statistics
        4. Analyze skip patterns
        5. Generate insights and recommendations
        6. Publish MealSkippedEvent
        """

    async def log_external_meal_with_adjustments(
        self,
        user_id: int,
        meal_data: dict,
        meal_log_id_to_replace: Optional[int] = None
    ) -> dict:
        """
        Complete external meal logging workflow:
        1. Estimate or use provided nutrition
        2. Replace planned meal OR create new
        3. Update daily totals
        4. Get remaining meals for potential adjustment
        5. Generate insights
        6. Publish ExternalMealLoggedEvent
        """
```

#### 2. InventoryAnalyticsOrchestrator (Optional)
**File**: `backend/app/orchestrators/inventory_analytics_orchestrator.py`
**Responsibility**: Coordinate complex inventory analytics
**LOC**: ~150 lines

**Note**: Only create if complexity warrants it. Simple inventory queries can go directly to service.

---

### Layer 4: API Endpoints (Thin Controllers)

#### tracking_v2.py
**File**: `backend/app/api/tracking_v2.py`
**Responsibility**: HTTP request/response handling ONLY
**LOC**: ~800 lines (9 endpoints)

**Pattern for EACH endpoint**:
```python
@router.post("/log-meal", response_model=LogMealResponse)
async def log_meal_v2(
    request: LogMealRequest,
    orchestrator: MealLoggingOrchestrator = Depends(get_meal_logging_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """
    Log a meal consumption - V2 with full repository pattern

    Source: backend/app/api/tracking.py:120-205
    """
    try:
        # 1. Call orchestrator (all business logic there)
        result = await orchestrator.log_meal_with_inventory_update(
            user_id=current_user.id,
            meal_log_id=request.meal_log_id,
            portion_multiplier=request.portion_multiplier,
            notes=request.notes
        )

        # 2. Map to response schema
        response = LogMealResponse(
            success=result["success"],
            meal_type=result["meal_type"],
            recipe_name=result["recipe"],
            consumed_at=result["consumed_at"],
            macros_consumed=MacroNutrients(**result["macros_consumed"]),
            # ... rest of mapping
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging meal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Key Points**:
- ✅ **Thin controllers** - No business logic
- ✅ **Dependency injection** - Orchestrators injected
- ✅ **Error handling** - Consistent across all endpoints
- ✅ **Source comments** - Traceability to original code
- ✅ **Schema mapping** - Clean request/response models

---

## 🔄 Migration Workflow

### Step 1: Repository Interfaces (Day 1)
**Files to Create**:
1. `backend/app/repositories/interfaces/tracking_repository.py`
2. `backend/app/repositories/interfaces/inventory_repository.py`
3. `backend/app/repositories/interfaces/consumption_analytics_repository.py`

**Work**:
- Define all interface methods with type hints
- Add comprehensive docstrings
- Follow IRepository<T> pattern from Phase 1
- **NO IMPLEMENTATION** - Just interfaces

**Success Criteria**:
- ✅ All method signatures defined
- ✅ Type hints complete
- ✅ Docstrings explain purpose
- ✅ Follows existing repository interface pattern

---

### Step 2: Repository Implementations (Day 2-3)
**Files to Create**:
1. `backend/app/repositories/tracking_repository.py` (~400 lines)
2. `backend/app/repositories/inventory_repository.py` (~350 lines)
3. `backend/app/repositories/consumption_analytics_repository.py` (~200 lines)

**Work for EACH repository**:
- Implement ALL interface methods
- Use SQLAlchemy for queries
- Add comprehensive error handling
- Include logging for debugging
- **COPY QUERIES FROM TrackingAgent** - Extract and refactor

**Query Extraction Process**:
1. Find query in TrackingAgent
2. Extract to repository method
3. Add error handling
4. Add logging
5. Add source comment

**Example**:
```python
# From TrackingAgent line 627-680
def mark_as_skipped(
    self,
    meal_log_id: int,
    user_id: int,
    reason: Optional[str]
) -> MealLog:
    """
    Mark meal log as skipped

    Source: backend/app/agents/tracking_agent.py:627-680
    """
    try:
        meal_log = self.db.query(MealLog).filter(
            MealLog.id == meal_log_id,
            MealLog.user_id == user_id
        ).first()

        if not meal_log:
            raise ValueError(f"Meal log {meal_log_id} not found")

        meal_log.was_skipped = True
        meal_log.skip_reason = reason
        meal_log.skip_datetime = datetime.utcnow()

        self.db.commit()
        self.db.refresh(meal_log)

        logger.info(f"Marked meal log {meal_log_id} as skipped")
        return meal_log

    except Exception as e:
        self.db.rollback()
        logger.error(f"Error marking meal as skipped: {e}")
        raise
```

**Success Criteria**:
- ✅ All interface methods implemented
- ✅ All queries extracted from TrackingAgent
- ✅ Error handling on all methods
- ✅ Logging on all operations
- ✅ Source comments for traceability
- ✅ Syntax validation passes

---

### Step 3: Service Layer (Day 4-5)
**Files to Create**:
1. `backend/app/services/meal_tracking_service.py` (~500 lines)
2. `backend/app/services/external_meal_service.py` (~300 lines)
3. `backend/app/services/inventory_management_service.py` (~400 lines)

**Files to Refactor**:
4. `backend/app/services/consumption_services.py` (existing, ~300 lines)

**Work for EACH service**:
- Extract ALL business logic from TrackingAgent
- Use repositories for data access (NO direct DB queries)
- Keep business rules intact (ZERO logic changes)
- Add comprehensive error handling
- Include source comments

**Business Logic Extraction Process**:
1. Identify business logic in TrackingAgent method
2. Extract to service method
3. Replace DB queries with repository calls
4. Keep validation and calculation logic identical
5. Add source comment

**Example**:
```python
# From TrackingAgent.log_meal_consumption() lines 300-450
def log_meal(
    self,
    user_id: int,
    meal_log_id: int,
    portion_multiplier: float,
    notes: Optional[str]
) -> dict:
    """
    Log meal consumption with automatic inventory deduction

    Source: backend/app/agents/tracking_agent.py:300-450
    """
    # 1. Validate (extracted from TrackingAgent:305-320)
    meal_log = self.tracking_repo.get_by_id(meal_log_id, user_id)
    if not meal_log:
        raise ValueError(f"Meal log {meal_log_id} not found")

    can_log, error = self.can_log_meal(meal_log)
    if not can_log:
        raise ValueError(error)

    # 2. Mark as consumed (extracted from TrackingAgent:325-340)
    consumed_at = datetime.utcnow()
    meal_log = self.tracking_repo.mark_as_consumed(
        meal_log_id=meal_log_id,
        user_id=user_id,
        consumed_at=consumed_at,
        portion_multiplier=portion_multiplier,
        notes=notes
    )

    # 3. Deduct ingredients (extracted from TrackingAgent:345-380)
    deducted_items = []
    if meal_log.recipe:
        deducted_items = self.inventory_repo.deduct_recipe_ingredients(
            user_id=user_id,
            recipe=meal_log.recipe,
            portion_multiplier=portion_multiplier
        )

    # 4. Calculate macros (extracted from TrackingAgent:385-400)
    macros_consumed = self._calculate_meal_macros(
        meal_log.recipe,
        portion_multiplier
    )

    # 5. Get daily totals (extracted from TrackingAgent:405-420)
    daily_totals = self.analytics_repo.get_daily_totals(
        user_id=user_id,
        start=consumed_at.date(),
        end=consumed_at.date()
    )[0]

    # 6. Generate insights (extracted from TrackingAgent:425-445)
    insights = self.generate_meal_insights(
        user_id=user_id,
        meal_log=meal_log,
        daily_totals=daily_totals
    )

    # 7. Return structured result (same format as TrackingAgent)
    return {
        "success": True,
        "meal_type": meal_log.meal_type,
        "recipe": meal_log.recipe.title,
        "consumed_at": consumed_at.isoformat(),
        "macros_consumed": macros_consumed,
        "deducted_items": deducted_items,
        "daily_totals": daily_totals,
        "insights": insights,
        "recommendations": self._generate_recommendations(daily_totals)
    }
```

**Success Criteria**:
- ✅ ALL business logic extracted from TrackingAgent
- ✅ Services use ONLY repositories (no direct DB)
- ✅ Logic identical to original (zero changes)
- ✅ Comprehensive error handling
- ✅ Source comments for traceability
- ✅ Syntax validation passes

---

### Step 4: Orchestrator Layer (Day 6)
**Files to Create**:
1. `backend/app/orchestrators/meal_logging_orchestrator.py` (~200 lines)

**Work**:
- Coordinate multi-service workflows
- Add event publishing
- Handle complex coordination logic
- Keep thin (just coordination, no business logic)

**Orchestrator Pattern**:
```python
class MealLoggingOrchestrator(BaseOrchestrator):
    """
    Orchestrate meal logging workflows

    Coordinates: MealTrackingService, InventoryManagementService
    """

    def __init__(
        self,
        meal_tracking_service: MealTrackingService,
        inventory_service: InventoryManagementService,
        event_publisher: EventPublisher
    ):
        super().__init__(event_publisher)
        self.meal_service = meal_tracking_service
        self.inventory_service = inventory_service

    async def log_meal_with_inventory_update(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float,
        notes: Optional[str]
    ) -> dict:
        """Coordinate complete meal logging workflow"""

        # 1. Log meal (service handles business logic)
        result = self.meal_service.log_meal(
            user_id=user_id,
            meal_log_id=meal_log_id,
            portion_multiplier=portion_multiplier,
            notes=notes
        )

        # 2. Publish event (orchestrator responsibility)
        await self.publish_event(
            "MealLoggedEvent",
            {
                "user_id": user_id,
                "meal_log_id": meal_log_id,
                "meal_type": result["meal_type"],
                "recipe": result["recipe"],
                "consumed_at": result["consumed_at"]
            }
        )

        # 3. Check if inventory alerts needed (cross-service coordination)
        inventory_status = self.inventory_service.get_inventory_status(user_id)
        if inventory_status.get("low_stock_items"):
            result["inventory_alerts"] = inventory_status["low_stock_items"]

        return result
```

**Success Criteria**:
- ✅ Orchestrators coordinate services (no business logic)
- ✅ Events published at appropriate points
- ✅ Cross-service coordination handled
- ✅ Thin layer (just coordination)
- ✅ Syntax validation passes

---

### Step 5: Dependency Injection Setup (Day 6)
**File to Update**:
- `backend/app/dependencies.py`

**Work**:
- Add factory functions for all new repositories
- Add factory functions for all new services
- Add factory functions for orchestrators
- Wire up all dependencies correctly

**Example**:
```python
# Repository factories
def get_tracking_repository(db: Session = Depends(get_db)) -> TrackingRepository:
    return TrackingRepository(db)

def get_inventory_repository(db: Session = Depends(get_db)) -> InventoryRepository:
    return InventoryRepository(db)

def get_consumption_analytics_repository(db: Session = Depends(get_db)) -> ConsumptionAnalyticsRepository:
    return ConsumptionAnalyticsRepository(db)

# Service factories
def get_meal_tracking_service(
    tracking_repo: TrackingRepository = Depends(get_tracking_repository),
    inventory_repo: InventoryRepository = Depends(get_inventory_repository),
    analytics_repo: ConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    notification_service: NotificationService = Depends(get_notification_service)
) -> MealTrackingService:
    return MealTrackingService(tracking_repo, inventory_repo, analytics_repo, notification_service)

# ... more service factories ...

# Orchestrator factories
def get_meal_logging_orchestrator(
    meal_service: MealTrackingService = Depends(get_meal_tracking_service),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service),
    event_publisher: EventPublisher = Depends(get_event_publisher)
) -> MealLoggingOrchestrator:
    return MealLoggingOrchestrator(meal_service, inventory_service, event_publisher)
```

**Success Criteria**:
- ✅ All dependencies wired correctly
- ✅ Follows existing DI pattern from Phase 1
- ✅ No circular dependencies
- ✅ Type hints on all factories

---

### Step 6: API Endpoints Migration (Day 7-8)
**File to Create**:
- `backend/app/api/tracking_v2.py` (~800 lines)

**Work**:
- Create all 9 v2 endpoints
- Thin controllers (just HTTP handling)
- Call orchestrators for all logic
- Map responses to schemas
- Add source comments

**Pattern for EACH endpoint**:
1. Parse request
2. Call orchestrator
3. Map to response schema
4. Handle errors
5. Return response

**Success Criteria**:
- ✅ All 9 endpoints created
- ✅ Thin controllers (no business logic)
- ✅ Orchestrators handle all workflows
- ✅ Source comments added
- ✅ Error handling consistent
- ✅ Syntax validation passes

---

### Step 7: Testing & Verification (Day 9-10)
**Work**:
1. **Syntax Validation** (Day 9 morning)
   - Run `python -m py_compile` on all new files
   - Fix any syntax errors

2. **Import Validation** (Day 9 afternoon)
   - Test all imports work
   - Verify dependency injection works
   - Check no circular dependencies

3. **Behavior Comparison** (Day 10)
   - Create comparison test for each endpoint
   - V1 vs V2 output should match
   - Document any differences

4. **Documentation** (Day 10)
   - Create PHASE_2_COMPLETE.md
   - Create ENDPOINT_JOURNEY_COMPARISON_V2.md
   - Update COMPLETE_MIGRATION_STATUS.md

**Success Criteria**:
- ✅ All syntax valid
- ✅ All imports work
- ✅ V1 and V2 produce same results
- ✅ Documentation complete

---

## 📊 Detailed Component Breakdown

### Total Work Summary

| Component | Files | LOC | Complexity | Days |
|-----------|-------|-----|------------|------|
| **Repository Interfaces** | 3 | ~300 | 🟢 Low | 1 |
| **Repository Implementations** | 3 | ~950 | 🟡 Medium | 2 |
| **Service Layer** | 4 | ~1500 | 🔴 High | 2 |
| **Orchestrator Layer** | 1 | ~200 | 🟡 Medium | 0.5 |
| **Dependency Injection** | 1 | ~100 | 🟢 Low | 0.5 |
| **API Endpoints** | 1 | ~800 | 🟢 Low | 2 |
| **Testing & Documentation** | 2 | ~400 | 🟡 Medium | 2 |
| **TOTAL** | **15** | **~4250** | 🟡 **Medium-High** | **10** |

---

## ✅ Success Criteria (Complete Refactoring)

### Code Quality Metrics

**Architecture**:
- ✅ **Complete separation of concerns** - Each layer has single responsibility
- ✅ **No direct DB access in services** - ALL queries through repositories
- ✅ **No business logic in API layer** - ALL logic in services/orchestrators
- ✅ **Dependency injection everywhere** - No hardcoded dependencies
- ✅ **Events published at appropriate points** - Orchestrators publish events

**Code Traceability**:
- ✅ **Source comments on all methods** - Link back to TrackingAgent
- ✅ **Zero logic changes** - Business rules identical to original
- ✅ **All queries extracted** - Every DB query from agent now in repository
- ✅ **All business logic extracted** - Every calculation now in service

**Testing**:
- ✅ **Syntax validation passes** - All files compile
- ✅ **Import validation passes** - No circular dependencies
- ✅ **Behavior comparison passes** - V1 and V2 produce same outputs
- ✅ **Documentation complete** - All docs updated

**Reusability**:
- ✅ **Repositories reusable** - Other services can use tracking/inventory repos
- ✅ **Services reusable** - Phase 3+ can leverage meal tracking service
- ✅ **Orchestrators extensible** - Easy to add new workflows
- ✅ **Clean interfaces** - Easy to mock for testing

---

## 📝 Next Steps

**Immediate Action**:
Start with Step 1 (Repository Interfaces) - Day 1 work

**Questions Before Starting**:
1. ✅ **User approved full refactoring approach?** (This document)
2. ⏳ **Ready to start with repository interfaces?**
3. ⏳ **Any specific concerns about the 10-day timeline?**

---

**Document Status**: ✅ COMPLETE - Full Refactoring Plan
**Approach**: Complete repository pattern with proper layering
**Estimated Timeline**: 10 days (2 weeks with buffer)
**Prepared By**: Claude Code Migration Assistant
**Review Date**: 2025-11-25