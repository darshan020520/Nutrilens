# Migration Execution Guardrails

## Purpose
This document serves as the **SINGLE SOURCE OF TRUTH** for executing the NutriLens backend restructuring. Every migration action MUST follow these guardrails to prevent hallucinations, rewrites, and deviations from the documented strategy.

---

## ⚠️ CRITICAL RULES - NEVER VIOLATE THESE

### Rule 1: NO REWRITING - ONLY RESTRUCTURING
```
❌ WRONG: Rewriting logic
def create_meal_plan(...):
    # New logic! Different validation!
    plans = get_all_plans(user_id)
    for p in plans:
        if has_overlap(p, start, end):  # Different check!
            raise ValueError("Overlap")

✅ CORRECT: Extract and move (preserve exact logic)
# OLD LOCATION: app/services/meal_plan_service.py
def create_meal_plan(db, user_id, start_date, end_date, name):
    existing = db.query(MealPlan).filter(
        MealPlan.user_id == user_id,
        MealPlan.start_date < end_date,
        MealPlan.end_date > start_date
    ).first()
    if existing:
        raise ValueError("Meal plans cannot overlap")
    # ... rest of exact same logic

# NEW LOCATION: domain/meal_plan/use_cases/create_meal_plan.py
# COPY-PASTE the exact same logic, then refactor structure only
```

**Verification Step**: Before moving code, run `diff` between old and new to ensure ZERO logic changes.

---

### Rule 2: BEHAVIOR INVENTORY REQUIRED BEFORE ANY MIGRATION
Before migrating ANY component, you MUST create a behavior inventory file:

**Template Location**: `MIGRATION_TRACKING_STRATEGY.md` Section 2.1

**Mandatory Steps**:
1. Create `docs/migration/behavior_inventories/[component_name]_inventory.md`
2. Document ALL public methods with:
   - Method signature
   - Called by (file:line)
   - Parameters with types
   - Return value with type
   - Side effects (database writes, external API calls, events)
   - Business rules
   - Edge cases
   - Error conditions
3. Extract test cases that validate current behavior
4. Get approval before proceeding

**Example**:
```markdown
# Component: MealPlanService - Behavior Inventory

## Public Method: create_meal_plan

**Signature**: `create_meal_plan(db: Session, user_id: str, start_date: date, end_date: date, name: str) -> dict`

**Called By**:
- `app/api/meal_plan.py:45` (POST /api/meal-plans)

**Parameters**:
- `db`: SQLAlchemy session (dependency injected)
- `user_id`: User UUID as string
- `start_date`: Plan start date
- `end_date`: Plan end date (must be after start_date)
- `name`: Plan name (max 100 chars)

**Returns**:
```python
{
    "id": "uuid-string",
    "user_id": "uuid-string",
    "start_date": "2025-01-01",
    "end_date": "2025-01-07",
    "name": "Weekly Plan",
    "created_at": "2025-01-01T10:00:00Z"
}
```

**Side Effects**:
1. Inserts row in `meal_plans` table
2. Publishes `meal_plan.created` event to event bus
3. Logs creation at INFO level

**Business Rules**:
1. Start date must be before end date
2. Cannot overlap with existing active plans for same user
3. Name cannot be empty or whitespace-only
4. User must exist in database

**Edge Cases**:
- If dates are equal → raises ValueError("Start date must be before end date")
- If overlapping plan exists → raises ValueError("Meal plans cannot overlap")
- If user doesn't exist → SQLAlchemy raises NoResultFound

**Current Tests**:
- `tests/services/test_meal_plan_service.py::test_create_meal_plan_success`
- `tests/services/test_meal_plan_service.py::test_create_meal_plan_overlap_fails`
- `tests/services/test_meal_plan_service.py::test_create_meal_plan_invalid_dates`
```

---

### Rule 3: DEPENDENCY GRAPH REQUIRED BEFORE MIGRATION
Before migrating ANY component, you MUST generate and verify dependencies:

**Tool**: `tools/generate_dependency_graph.py` (to be created)

**Mandatory Steps**:
1. Run: `python tools/generate_dependency_graph.py --component [component_name]`
2. Review `docs/migration/dependency_graphs/[component_name]_deps.json`
3. Identify all incoming dependencies (who calls this?)
4. Identify all outgoing dependencies (what does this call?)
5. Document migration order to avoid breaking dependencies

**Example Output**:
```json
{
  "component": "app/services/meal_plan_service.py",
  "imports": [
    "app/models/meal_plan.py",
    "app/core/mongodb.py",
    "app/core/events.py"
  ],
  "imported_by": [
    "app/api/meal_plan.py",
    "app/services/notification_service.py"
  ],
  "calls": {
    "db.query": ["app/models/meal_plan.py:MealPlan"],
    "event_bus.publish": ["app/core/events.py:EventBus.publish"]
  },
  "called_by": {
    "create_meal_plan": [
      "app/api/meal_plan.py:45",
      "tests/services/test_meal_plan_service.py:23"
    ]
  }
}
```

**Verification**: If dependency graph shows incoming dependencies from components not yet migrated, STOP and migrate those first OR create adapter pattern.

---

### Rule 4: MIGRATION WAVE ORDER - STRICT SEQUENCE

**Reference**: `MIGRATION_TRACKING_STRATEGY.md` Section 4.2

You MUST migrate in this exact order:

```
Wave 1: Value Objects (No dependencies)
├── domain/user/value_objects.py (Email, Password, BMI, TDEE)
├── domain/meal_plan/value_objects.py (DateRange, CalorieTarget)
├── domain/inventory/value_objects.py (Quantity, ExpiryDate)
└── domain/recipe/value_objects.py (ServingSize, NutritionInfo)

Wave 2: Domain Models (Depend on value objects only)
├── domain/user/models.py (User, UserProfile)
├── domain/meal_plan/models.py (MealPlan)
├── domain/inventory/models.py (InventoryItem)
└── domain/recipe/models.py (Recipe)

Wave 3: Repository Interfaces (Depend on domain models)
├── domain/user/repositories.py (IUserRepository)
├── domain/meal_plan/repositories.py (IMealPlanRepository)
├── domain/inventory/repositories.py (IInventoryRepository)
└── domain/recipe/repositories.py (IRecipeRepository)

Wave 4: Repository Implementations (Depend on interfaces + SQLAlchemy)
├── infrastructure/persistence/user_repository.py
├── infrastructure/persistence/meal_plan_repository.py
├── infrastructure/persistence/inventory_repository.py
└── infrastructure/persistence/recipe_repository.py

Wave 5: Use Cases (Depend on repository interfaces)
├── application/use_cases/user/create_user.py
├── application/use_cases/meal_plan/create_meal_plan.py
├── application/use_cases/inventory/add_item.py
└── application/use_cases/recipe/search_recipes.py

Wave 6: Application Services (Depend on use cases)
├── application/services/user_service.py
├── application/services/meal_plan_service.py
├── application/services/inventory_service.py
└── application/services/recipe_service.py

Wave 7: API Layer (Depends on application services)
├── app/api/auth.py
├── app/api/meal_plan.py
├── app/api/inventory.py
└── app/api/recipes.py

Wave 8: LangGraph Split (Special - file split only, no logic changes)
├── infrastructure/ai/langgraph/state.py
├── infrastructure/ai/langgraph/graph_builder.py
├── infrastructure/ai/langgraph/nodes/*.py
├── infrastructure/ai/langgraph/tools/*.py
└── infrastructure/ai/langgraph/prompts/*.py
```

**Rule**: You CANNOT start Wave N+1 until Wave N is 100% complete and validated.

---

### Rule 5: VALIDATION CHECKLIST - MANDATORY AFTER EACH COMPONENT

After migrating each component, you MUST complete this checklist:

**Reference**: `RESTRUCTURING_MASTER_PLAN.md` Component sections "Validation Tests"

```markdown
## Component Migration Validation Checklist

Component: _______________
Date: _______________
Migrated By: _______________

### 1. Behavior Preservation
- [ ] All public methods exist with same signatures
- [ ] All test cases pass (existing tests, zero modifications)
- [ ] Snapshot tests match exactly (input/output pairs)
- [ ] Manual testing of API endpoints returns identical responses

### 2. Dependency Integrity
- [ ] All incoming dependencies still work (nothing broken)
- [ ] All outgoing dependencies resolved correctly
- [ ] No circular dependencies introduced
- [ ] Import paths updated in all dependent files

### 3. Code Quality (Structure Only, NOT Logic)
- [ ] Follows Single Responsibility Principle
- [ ] Dependencies point inward (Clean Architecture)
- [ ] No business logic in infrastructure layer
- [ ] No infrastructure dependencies in domain layer

### 4. Documentation
- [ ] Behavior inventory complete
- [ ] Dependency graph generated
- [ ] Migration notes documented
- [ ] Rollback plan documented

### 5. Rollback Readiness
- [ ] Old code preserved (commented with "# DEPRECATED - Remove after Wave X validation")
- [ ] Feature flag exists to switch between old/new (if applicable)
- [ ] Can revert to old implementation in < 5 minutes

### 6. Performance
- [ ] No performance regression (measure latency before/after)
- [ ] Database query count unchanged
- [ ] No new N+1 queries introduced

### 7. Security
- [ ] No SQL injection vulnerabilities introduced
- [ ] No authentication/authorization bypassed
- [ ] No sensitive data exposed in logs
```

**Enforcement**: If ANY checkbox is unchecked, migration is INCOMPLETE. Do not proceed.

---

## 🛠️ PRE-MIGRATION CHECKLIST

Before starting ANY component migration:

```markdown
### Step 1: Read the Plan
- [ ] Read `RESTRUCTURING_MASTER_PLAN.md` Component section
- [ ] Read `MIGRATION_TRACKING_STRATEGY.md` relevant sections
- [ ] Read this guardrails document (you are here)

### Step 2: Understand Current State
- [ ] Read the component's source code file(s)
- [ ] Read all tests for the component
- [ ] Run tests to confirm they pass (baseline)
- [ ] Identify all public methods/functions
- [ ] Identify all dependencies (imports, calls)

### Step 3: Create Artifacts
- [ ] Create behavior inventory (docs/migration/behavior_inventories/)
- [ ] Generate dependency graph (tools/generate_dependency_graph.py)
- [ ] Create migration tracking document (docs/migration/components/[name].md)

### Step 4: Plan the Migration
- [ ] Identify target directory structure
- [ ] Identify which wave this component belongs to
- [ ] Verify all dependencies from earlier waves are complete
- [ ] Write step-by-step migration plan

### Step 5: Get Approval
- [ ] Show behavior inventory to user
- [ ] Show dependency graph to user
- [ ] Show migration plan to user
- [ ] Get explicit approval before proceeding
```

---

## 📋 MIGRATION EXECUTION PROMPT TEMPLATE

When migrating a component, use this exact prompt structure:

```markdown
# Migrating Component: [COMPONENT_NAME]

## 1. Current State Analysis

**File(s)**:
- [List all files involved]

**Public API**:
- [List all public methods/functions]

**Dependencies**:
- Imports: [List]
- Called by: [List]

**Test Coverage**:
- [List test files]
- [Number of tests]: X tests

## 2. Behavior Inventory Reference

**Document**: `docs/migration/behavior_inventories/[component]_inventory.md`

**Key Behaviors to Preserve**:
1. [Behavior 1 with reference to line numbers]
2. [Behavior 2 with reference to line numbers]
3. ...

## 3. Target Architecture

**Wave**: Wave X (from migration order)

**Target Directory Structure**:
```
domain/[domain]/
├── models.py          # Domain models
├── value_objects.py   # Value objects
├── repositories.py    # Repository interfaces
└── exceptions.py      # Domain exceptions
```

**Design Principles Applied**:
1. [Principle 1 - e.g., Single Responsibility]
2. [Principle 2 - e.g., Dependency Inversion]
3. ...

## 4. Migration Steps (Copy-Paste Strategy)

### Step 4.1: Create Target Files
- [ ] Create `domain/[domain]/models.py`
- [ ] Create `domain/[domain]/value_objects.py`
- [ ] ...

### Step 4.2: Extract Value Objects (If applicable)
- [ ] Copy-paste value object logic from old file
- [ ] Move to `domain/[domain]/value_objects.py`
- [ ] Run diff to verify zero logic changes
- [ ] Update imports in old file (temporary)

### Step 4.3: Extract Domain Models
- [ ] Copy-paste model class from old file
- [ ] Move to `domain/[domain]/models.py`
- [ ] Replace SQLAlchemy-specific code with domain code
- [ ] Run diff to verify business logic unchanged
- [ ] Update imports in old file (temporary)

### Step 4.4: Extract Repository Interface
- [ ] Create abstract interface in `domain/[domain]/repositories.py`
- [ ] Define methods matching current service methods
- [ ] Zero implementation - just signatures

### Step 4.5: Create Repository Implementation
- [ ] Create `infrastructure/persistence/[domain]_repository.py`
- [ ] Copy-paste data access logic from old service
- [ ] Implement repository interface
- [ ] Run diff to verify SQL queries unchanged

### Step 4.6: Update Dependencies
- [ ] Update imports in all files that used old component
- [ ] Use find-and-replace for import paths
- [ ] Verify no broken imports (run type checker)

### Step 4.7: Run Tests
- [ ] Run all tests for this component
- [ ] Verify 100% pass rate (same as before migration)
- [ ] Run integration tests
- [ ] Run end-to-end tests (if applicable)

### Step 4.8: Deprecate Old Code
- [ ] Comment old file with "# DEPRECATED - Remove after Wave X validation"
- [ ] Do NOT delete yet (keep for rollback)
- [ ] Document deprecation in migration notes

## 5. Validation

**Checklist**: See "Rule 5: Validation Checklist" above

**Test Results**:
- [ ] Unit tests: X/X passed
- [ ] Integration tests: X/X passed
- [ ] Snapshot tests: MATCH
- [ ] Performance: No regression

**Diff Check**:
```bash
# Compare old vs new behavior
python tools/compare_behavior.py --old app/services/[name].py --new domain/[domain]/
```

## 6. Rollback Plan

**If migration fails**:
1. Revert imports to point to old file
2. Uncomment old code
3. Delete new files (if needed)
4. Run tests to verify rollback success

**Rollback Time**: < 5 minutes

## 7. Documentation

**Migration Notes**: `docs/migration/components/[component].md`

**Contents**:
- What was migrated
- What changed (structure only)
- What stayed the same (logic)
- Dependencies updated
- Test results
- Known issues (if any)
```

---

## 🚨 HALLUCINATION PREVENTION CHECKLIST

Before making ANY code change, ask yourself:

1. **Am I rewriting logic?**
   - If YES → STOP. Use extract method pattern instead.

2. **Did I create a behavior inventory?**
   - If NO → STOP. Create it first.

3. **Did I generate a dependency graph?**
   - If NO → STOP. Generate it first.

4. **Am I following the wave order?**
   - If NO → STOP. Migrate dependencies first.

5. **Did I run a diff to verify zero logic changes?**
   - If NO → STOP. Run diff before proceeding.

6. **Are all tests passing?**
   - If NO → STOP. Fix tests before proceeding.

7. **Did I document the migration?**
   - If NO → STOP. Document before proceeding.

8. **Can I rollback in < 5 minutes?**
   - If NO → STOP. Preserve old code first.

---

## 🎯 SUCCESS CRITERIA

A component migration is considered SUCCESSFUL only if:

1. ✅ All existing tests pass (100% pass rate)
2. ✅ Snapshot tests match exactly
3. ✅ API responses identical (byte-for-byte if possible)
4. ✅ Performance unchanged (±5% tolerance)
5. ✅ No new bugs introduced
6. ✅ All dependencies resolved
7. ✅ Behavior inventory complete
8. ✅ Dependency graph generated
9. ✅ Migration documented
10. ✅ Rollback plan tested

**If ANY criterion fails → Migration is INCOMPLETE**

---

## 📚 REFERENCE DOCUMENTS

**Primary References**:
1. `RESTRUCTURING_MASTER_PLAN.md` - Component-by-component plans
2. `MIGRATION_TRACKING_STRATEGY.md` - Migration safety strategy
3. This document (`MIGRATION_EXECUTION_GUARDRAILS.md`) - Execution rules

**Secondary References**:
- `PRODUCTION_FIXES_ANALYSIS.md` - Production issues to avoid
- `ARCHITECTURE_ANALYSIS_OUR_VS_PRODUCTION.md` - Current architecture

---

## 🔄 PARALLEL RUNNING STRATEGY

**Reference**: `MIGRATION_TRACKING_STRATEGY.md` Section 3.4

For critical components, use parallel running:

```python
# Example: Feature flag for gradual migration
from app.core.config import settings

def create_meal_plan(db, user_id, start_date, end_date, name):
    if settings.USE_NEW_MEAL_PLAN_SERVICE:
        # New implementation (domain/use case pattern)
        from domain.meal_plan.use_cases import CreateMealPlan
        use_case = CreateMealPlan(meal_plan_repository)
        return use_case.execute(user_id, start_date, end_date, name)
    else:
        # Old implementation (fat service)
        return _legacy_create_meal_plan(db, user_id, start_date, end_date, name)
```

**When to Use**:
- User-facing APIs
- Critical business operations
- High-traffic endpoints

**When NOT to Use**:
- Internal utilities
- Low-risk components
- Already well-tested components

---

## 🛑 STOPPING CONDITIONS

**STOP immediately if**:

1. Tests start failing unexpectedly
2. Dependency graph shows circular dependencies
3. You're tempted to "fix" or "improve" logic during migration
4. You can't explain how the old code worked
5. Behavior inventory is incomplete
6. User hasn't approved the migration plan
7. You're not following the wave order
8. Performance degrades by more than 5%
9. You introduce a security vulnerability
10. You can't rollback in < 5 minutes

**When stopped, DO NOT proceed**. Ask the user for guidance.

---

## ✅ MIGRATION APPROVAL TEMPLATE

Before starting ANY component migration, send this to the user:

```markdown
## Migration Approval Request: [COMPONENT_NAME]

### Summary
I'm ready to migrate `[component_name]` from `[old_path]` to `[new_path]`.

### Behavior Inventory
- **Public Methods**: X methods documented
- **Test Coverage**: Y tests exist
- **Dependencies**: Z incoming, W outgoing

**Document**: `docs/migration/behavior_inventories/[component]_inventory.md`

### Dependency Graph
- **Imports**: [List]
- **Imported By**: [List]
- **Migration Wave**: Wave X

**Document**: `docs/migration/dependency_graphs/[component]_deps.json`

### Migration Strategy
1. Extract value objects → domain/[domain]/value_objects.py
2. Extract domain model → domain/[domain]/models.py
3. Create repository interface → domain/[domain]/repositories.py
4. Implement repository → infrastructure/persistence/[domain]_repository.py
5. Update imports in [N] dependent files
6. Run tests (expect 100% pass rate)
7. Deprecate old code (keep for rollback)

### Validation Plan
- [ ] All existing tests pass
- [ ] Snapshot tests match
- [ ] Manual API testing
- [ ] Performance check
- [ ] Rollback test

### Estimated Time
- Migration: [X] minutes
- Testing: [Y] minutes
- Documentation: [Z] minutes
- **Total**: [X+Y+Z] minutes

### Risk Assessment
- **Risk Level**: [Low/Medium/High]
- **Rollback Time**: < 5 minutes
- **Dependencies**: [List any blockers]

### Approval Required
Please approve before I proceed:
- [ ] Behavior inventory is complete
- [ ] Dependency graph is accurate
- [ ] Migration strategy makes sense
- [ ] Validation plan is sufficient

**Approve?** (Yes/No)
```

---

## 🎓 LEARNING FROM PRODUCTION FIXES

**Reference**: `PRODUCTION_FIXES_ANALYSIS.md`

**Key Lessons to Apply During Migration**:

1. **Message Trimming** (LangGraph):
   - Don't use `pre_model_hook` with StateGraph (doesn't work)
   - Trim directly in nodes
   - Use `end_on=("human", "ai")` to avoid orphaned tool messages

2. **MongoDB Checkpointer**:
   - Always have fallback (stateless mode)
   - Don't crash if MongoDB is unavailable
   - Log warnings clearly

3. **Context Loading**:
   - Don't access fields that might not exist
   - Use `.get()` instead of direct access
   - Provide sensible defaults

**Principle**: If production fixes touched a component, be EXTRA careful during migration.

---

## 📊 MIGRATION PROGRESS TRACKING

Create `docs/migration/PROGRESS.md` to track overall progress:

```markdown
# Migration Progress Tracker

## Overall Status
- **Started**: [Date]
- **Current Wave**: Wave X
- **Components Migrated**: X/Y (Z%)
- **Tests Passing**: 100%
- **Blockers**: [None/List]

## Wave 1: Value Objects (0% → 100%)
- [x] domain/user/value_objects.py (2025-11-24) ✅
- [ ] domain/meal_plan/value_objects.py
- [ ] domain/inventory/value_objects.py
- [ ] domain/recipe/value_objects.py

## Wave 2: Domain Models (0% → 0%)
- [ ] domain/user/models.py
- [ ] domain/meal_plan/models.py
- [ ] domain/inventory/models.py
- [ ] domain/recipe/models.py

... (continue for all waves)

## Validation Status
| Component | Tests Pass | Snapshot Match | Perf Check | Docs Complete |
|-----------|-----------|----------------|-----------|---------------|
| user/value_objects | ✅ | ✅ | ✅ | ✅ |
| meal_plan/value_objects | ❌ | - | - | ⏳ |

## Blockers
1. [None currently]

## Next Steps
1. Complete domain/meal_plan/value_objects.py
2. Run validation checklist
3. Get approval for Wave 2
```

---

## 🔐 FINAL GUARDRAIL

**Before committing ANY migration code**:

1. Read this document
2. Verify you followed ALL rules
3. Complete ALL checklists
4. Run ALL tests
5. Document ALL changes
6. Get user approval

**If you skipped ANY step → DO NOT COMMIT**

---

## 📞 WHEN IN DOUBT

**If you're unsure about ANYTHING**:

1. STOP immediately
2. Re-read the relevant section in this document
3. Re-read `RESTRUCTURING_MASTER_PLAN.md`
4. Re-read `MIGRATION_TRACKING_STRATEGY.md`
5. Ask the user for clarification

**Never guess. Never assume. Always verify.**

---

## 🎯 END-TO-END MIGRATION WORKFLOW

```
1. Read guardrails document (this file)
   ↓
2. Choose next component (follow wave order)
   ↓
3. Create behavior inventory
   ↓
4. Generate dependency graph
   ↓
5. Write migration plan
   ↓
6. Get user approval
   ↓
7. Execute migration (copy-paste strategy)
   ↓
8. Run tests (expect 100% pass)
   ↓
9. Validate (complete checklist)
   ↓
10. Document migration
   ↓
11. Deprecate old code (don't delete)
   ↓
12. Update progress tracker
   ↓
13. Commit to migration branch
   ↓
14. Repeat for next component
```

**Every step is mandatory. Zero shortcuts allowed.**

---

## ✅ FINAL WORDS

This migration is about **RESTRUCTURING, NOT REWRITING**.

- We preserve 100% of business logic
- We only change code organization
- We follow design principles
- We validate relentlessly
- We document everything
- We can rollback anytime

**If you find yourself rewriting logic → YOU'RE DOING IT WRONG**

**If tests fail → YOU'RE DOING IT WRONG**

**If you skip checklists → YOU'RE DOING IT WRONG**

**If you hallucinate improvements → YOU'RE DOING IT WRONG**

**Follow the guardrails. Trust the process. Validate everything.**

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Approved By**: [Pending User Approval]
