# Context Builder - Thin Wrapper Design

## Problem: Avoid Duplication

The current `_initialize_state()` in nutrition_agent.py **queries database directly**:
```python
profile = self.db.query(UserProfile).filter_by(user_id=self.user_id).first()
goal = self.db.query(UserGoal).filter_by(user_id=self.user_id, is_active=True).first()
```

❌ This is duplication - other services already do this!

## Solution: Pure Delegation Pattern

Context Builder should be **100% delegation**, **0% implementation**.

```python
class UserContext:
    """
    THIN WRAPPER - Only calls existing services, implements NOTHING

    Purpose: Gather data in one place for LLM context

    Rules:
    1. NO database queries
    2. NO calculations
    3. NO business logic
    4. ONLY service calls
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

        # Inject existing services
        from app.services.consumption_services import ConsumptionService
        from app.services.inventory_service import IntelligentInventoryService
        from app.services.onboarding import OnboardingService
        from app.agents.planning_agent import PlanningAgent

        self.consumption_service = ConsumptionService(db)
        self.inventory_service = IntelligentInventoryService(db)
        self.onboarding_service = OnboardingService(db)
        self.planning_agent = PlanningAgent(db, user_id)

    def build_context(self) -> Dict:
        """
        Build complete context by ONLY calling existing services

        No database queries, no calculations - pure delegation
        """

        return {
            "targets": self._get_targets(),           # ← Calls OnboardingService
            "today": self._get_today(),               # ← Calls ConsumptionService
            "week": self._get_weekly(),               # ← Calls ConsumptionService
            "inventory": self._get_inventory(),       # ← Calls InventoryService
            "upcoming": self._get_upcoming_meals()    # ← Calls PlanningAgent or ConsumptionService
        }

    def _get_targets(self) -> Dict:
        """
        ✅ CORRECT: Delegate to OnboardingService
        """
        result = self.onboarding_service.get_calculated_targets(self.user_id)

        # Just format, don't calculate
        return {
            "calories": result.get("calories", 0),
            "protein_g": result.get("protein_g", 0),
            "carbs_g": result.get("carbs_g", 0),
            "fat_g": result.get("fat_g", 0)
        }

    def _get_today(self) -> Dict:
        """
        ✅ CORRECT: Delegate to ConsumptionService
        """
        summary = self.consumption_service.get_today_summary(self.user_id)

        # Just format, don't calculate
        return {
            "calories": summary.get("total_calories", 0),
            "protein_g": summary.get("total_macros", {}).get("protein_g", 0),
            "meals_consumed": summary.get("meals_consumed", 0),
            "meals_pending": summary.get("meals_pending", 0),
            "compliance_rate": summary.get("compliance_rate", 0)
        }

    def _get_weekly(self) -> Dict:
        """
        ✅ CORRECT: Delegate to ConsumptionService
        """
        analytics = self.consumption_service.generate_consumption_analytics(
            self.user_id,
            days=7
        )

        # Just format, don't calculate
        return {
            "avg_calories": analytics.get("avg_daily_calories", 0),
            "compliance_rate": analytics.get("avg_compliance", 0),
            "favorite_meals": analytics.get("favorite_recipes", [])[:3]
        }

    def _get_inventory(self) -> Dict:
        """
        ✅ CORRECT: Delegate to InventoryService
        """
        status = self.inventory_service.get_inventory_status(self.user_id)

        # Just format, don't calculate
        return {
            "total_items": status.get("total_items", 0),
            "expiring_soon": status.get("expiring_count", 0),
            "low_stock": status.get("low_stock_count", 0)
        }
```

## What Services Already Exist?

### ✅ ConsumptionService (consumption_services.py)
**What it provides**:
- `get_today_summary(user_id)` → Daily consumption, remaining, targets
- `generate_consumption_analytics(user_id, days)` → Weekly stats, patterns
- `get_consumption_history(user_id, days)` → Historical data

**We should use**: ALL of the above - don't reimplement!

### ✅ InventoryService (inventory_service.py)
**What it provides**:
- `get_inventory_status(user_id)` → Total items, expiring, low stock
- `get_makeable_recipes(user_id, limit)` → Recipes user can make
- `check_recipe_availability(user_id, recipe_id)` → Can make specific recipe?

**We should use**: ALL of the above - don't reimplement!

### ✅ OnboardingService (onboarding.py)
**What it provides**:
- `get_calculated_targets(user_id)` → Daily calorie/macro targets
- `calculate_bmr()` → Basal metabolic rate
- `calculate_tdee()` → Total daily energy expenditure

**We should use**: `get_calculated_targets()` - don't recalculate!

### ✅ PlanningAgent (planning_agent.py)
**What it provides**:
- `select_recipes_for_goal(goal, meal_type, count)` → Goal-aligned recipes
- `generate_weekly_meal_plan(user_id, start_date)` → Full meal plan
- `find_recipe_alternatives(recipe_id, count)` → Alternative recipes

**We should use**: `select_recipes_for_goal()` - don't reimplement scoring!

### ✅ FDC Service (fdc_service.py)
**What it provides**:
- `search_food(query)` → Look up food nutrition from USDA database
- `get_food_details(fdc_id)` → Detailed nutrition info

**We should use**: For food lookups in what-if scenarios

## What Do We Actually Need to Build?

### 1. Context Builder (NEW - but thin wrapper)
**Purpose**: Gather data from all services in one place
**Implementation**: Pure delegation, no logic
**Lines of code**: ~100-150 lines

### 2. Intelligence Router (NEW)
**Purpose**: Decide rule-based vs LLM
**Implementation**: Pattern matching for intent classification
**Lines of code**: ~200-300 lines

### 3. LLM Service Wrapper (NEW)
**Purpose**: Call Claude/GPT APIs
**Implementation**: HTTP client with retry logic
**Lines of code**: ~150-200 lines

### 4. Chat API Endpoint (NEW)
**Purpose**: Expose chatbot functionality
**Implementation**: FastAPI endpoint
**Lines of code**: ~50-100 lines

### 5. Enhanced Suggest Meal Endpoint (MODIFY EXISTING)
**Purpose**: Add AI suggestions option
**Implementation**: Add optional LLM call to existing endpoint
**Lines of code**: ~50-100 lines added

## Total New Code: ~500-750 lines

Compare to: **0 lines of duplicate logic**

## Key Principle

> **Every line of code must answer: "Is this already done by an existing service?"**
>
> If yes → Use that service
> If no → Only then implement

## Implementation Priority

### Phase 1: Minimal Context Builder (This Week)
```python
class UserContext:
    def build_context(self):
        return {
            "today": self.consumption_service.get_today_summary(self.user_id),
            "week": self.consumption_service.generate_consumption_analytics(self.user_id, 7),
            "inventory": self.inventory_service.get_inventory_status(self.user_id),
            "targets": self.onboarding_service.get_calculated_targets(self.user_id)
        }
```

**That's it! Just 4 service calls.**

### Phase 2: Add Intelligence Router (Next Week)
Simple pattern matching to route queries.

### Phase 3: Add LLM Integration (Week 3)
Claude API wrapper.

### Phase 4: Add Chat Endpoint (Week 3)
Expose via API.

## Questions to Ask Before Writing Code

1. **Does ConsumptionService already do this?** → Use it
2. **Does InventoryService already do this?** → Use it
3. **Does PlanningAgent already do this?** → Use it
4. **Does OnboardingService already do this?** → Use it
5. **Is this a new AI capability?** → Only then implement

## Next Step

Should I implement the **thin Context Builder** now?

It will be **~100 lines** that just calls existing services and formats the response.

No database queries, no calculations, no duplication.
