# Migration Tracking Strategy

## 1. Component Behavior Documentation

### Strategy: Document Before Migrate

**For EVERY component before migration:**

#### Step 1: Behavior Inventory Template

```markdown
# Component: [Name] - Behavior Inventory

## File Location
- Current: `app/services/meal_plan_service.py`
- New: `app/application/services/meal_plan_service.py` + `app/domain/meal_planning/use_cases/`

## Public Methods (What external code calls)
1. `create_meal_plan(user_id, start_date, end_date, name)`
   - **Called by**: `api/meal_plan.py:45`
   - **Parameters**: user_id (str), start_date (date), end_date (date), name (str)
   - **Returns**: MealPlan dict
   - **Side effects**:
     - Creates row in `meal_plans` table
     - May raise `HTTPException(400)` if overlapping plan exists
   - **Business rules**:
     - Start date must be before end date
     - Cannot overlap with existing active plans
     - Max 1 active plan per user

2. `optimize_meal_plan(meal_plan_id, preferences)`
   - **Called by**: `api/meal_plan.py:78`, `workers/optimization_job.py:23`
   - **Parameters**: meal_plan_id (str), preferences (dict)
   - **Returns**: OptimizedPlan dict
   - **Side effects**:
     - Updates `planned_meals` table
     - Calls `llm_recipe_generator.generate_recipe()`
   - **Business rules**:
     - Must respect dietary restrictions
     - Must meet calorie targets

... (document ALL methods)

## Private Methods (Internal helpers)
1. `_validate_dates(start, end)`
2. `_check_overlaps(user_id, start, end)`
... (document ALL private methods)

## Dependencies (What this component calls)
### Database Tables
- `meal_plans` (read, write)
- `planned_meals` (read, write)
- `recipes` (read)
- `user_profiles` (read)

### External Services
- `llm_recipe_generator.generate_recipe()` - Used in `optimize_meal_plan()`
- `fdc_service.get_nutrition()` - Used in `_calculate_nutrition()`

### Other Services
- `recipe_service.search_recipes()` - Used in `optimize_meal_plan()`
- `inventory_service.check_availability()` - Used in `optimize_meal_plan()`

## Database Queries
```python
# Query 1: Check for overlapping plans
db.query(MealPlan).filter(
    MealPlan.user_id == user_id,
    MealPlan.is_active == True,
    MealPlan.start_date <= end_date,
    MealPlan.end_date >= start_date
).first()

# Query 2: Get planned meals
db.query(PlannedMeal).filter(
    PlannedMeal.meal_plan_id == meal_plan_id
).all()
```

## Edge Cases / Special Behavior
1. If optimization fails, falls back to simple recipe selection
2. If no recipes found, returns empty meal plan (doesn't fail)
3. Caches recipe search results for 5 minutes (uses Redis)
4. Background job calls `optimize_meal_plan()` asynchronously

## Tests That Cover This
- `tests/services/test_meal_plan_service.py::test_create_meal_plan`
- `tests/services/test_meal_plan_service.py::test_overlapping_plans`
- `tests/integration/test_meal_plan_flow.py`

## Known Bugs / Issues
- TODO: optimization sometimes times out (>30s)
- FIXME: doesn't handle deleted recipes gracefully

## Migration Checklist
- [ ] All public methods documented
- [ ] All dependencies identified
- [ ] All database queries documented
- [ ] All edge cases noted
- [ ] Tests identified
- [ ] New implementation preserves ALL behavior
- [ ] New tests written
- [ ] Old tests updated
- [ ] Integration tests pass
```

#### Step 2: Automated Behavior Extraction

**Tool to extract behavior automatically:**

```python
# tools/extract_component_behavior.py
"""
Automated tool to extract component behavior.

Usage:
    python tools/extract_component_behavior.py app/services/meal_plan_service.py
"""

import ast
import re
from pathlib import Path

class ComponentAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.public_methods = []
        self.private_methods = []
        self.imports = []
        self.database_queries = []

    def visit_FunctionDef(self, node):
        """Extract all method definitions."""
        method_info = {
            'name': node.name,
            'params': [arg.arg for arg in node.args.args],
            'docstring': ast.get_docstring(node),
            'line_number': node.lineno
        }

        if node.name.startswith('_'):
            self.private_methods.append(method_info)
        else:
            self.public_methods.append(method_info)

        self.generic_visit(node)

    def visit_Import(self, node):
        """Extract imports."""
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_Call(self, node):
        """Extract database queries and external calls."""
        call_str = ast.unparse(node)

        # Detect database queries
        if 'db.query' in call_str or '.filter' in call_str:
            self.database_queries.append({
                'query': call_str,
                'line': node.lineno
            })

        self.generic_visit(node)

def analyze_component(file_path: str) -> dict:
    """Analyze a component and extract behavior."""
    with open(file_path) as f:
        tree = ast.parse(f.read())

    analyzer = ComponentAnalyzer()
    analyzer.visit(tree)

    return {
        'public_methods': analyzer.public_methods,
        'private_methods': analyzer.private_methods,
        'imports': analyzer.imports,
        'database_queries': analyzer.database_queries
    }

def find_callers(method_name: str, codebase_path: str) -> list:
    """Find all files that call this method."""
    callers = []

    for file_path in Path(codebase_path).rglob("*.py"):
        with open(file_path) as f:
            content = f.read()
            if f'.{method_name}(' in content:
                # Find line numbers
                for i, line in enumerate(content.split('\n'), 1):
                    if f'.{method_name}(' in line:
                        callers.append({
                            'file': str(file_path),
                            'line': i,
                            'code': line.strip()
                        })

    return callers

# Generate report
if __name__ == '__main__':
    import sys
    file_path = sys.argv[1]

    analysis = analyze_component(file_path)

    print("# Behavior Analysis Report\n")
    print(f"## File: {file_path}\n")

    print("## Public Methods:")
    for method in analysis['public_methods']:
        print(f"- `{method['name']}` (line {method['line_number']})")

        # Find who calls this
        callers = find_callers(method['name'], 'app/')
        if callers:
            print(f"  - Called by:")
            for caller in callers[:5]:  # Show first 5
                print(f"    - {caller['file']}:{caller['line']}")

    print("\n## Database Queries:")
    for query in analysis['database_queries']:
        print(f"- Line {query['line']}: `{query['query']}`")
```

#### Step 3: Side-by-Side Comparison During Migration

**Create a comparison checklist:**

```python
# tools/migration_validator.py
"""
Validate that new implementation preserves old behavior.

Usage:
    python tools/migration_validator.py \
        --old app/services/meal_plan_service.py \
        --new app/application/services/meal_plan_service.py \
        --domain app/domain/meal_planning/use_cases/
"""

def validate_migration(old_path, new_path, domain_path):
    """Validate migration preserves behavior."""

    old_analysis = analyze_component(old_path)
    new_analysis = analyze_component(new_path)
    domain_analysis = analyze_component(domain_path)

    # Check 1: All public methods exist
    old_methods = {m['name'] for m in old_analysis['public_methods']}
    new_methods = {m['name'] for m in new_analysis['public_methods']}

    missing_methods = old_methods - new_methods
    if missing_methods:
        print(f"❌ Missing methods: {missing_methods}")
        return False

    # Check 2: All database queries preserved
    old_tables = extract_table_names(old_analysis['database_queries'])
    new_tables = extract_table_names(new_analysis['database_queries'])

    if old_tables != new_tables:
        print(f"⚠️  Database tables changed:")
        print(f"   Old: {old_tables}")
        print(f"   New: {new_tables}")

    # Check 3: All dependencies preserved
    old_deps = extract_dependencies(old_analysis['imports'])
    new_deps = extract_dependencies(new_analysis['imports'])

    missing_deps = old_deps - new_deps
    if missing_deps:
        print(f"❌ Missing dependencies: {missing_deps}")
        return False

    print("✅ Migration validation passed")
    return True
```

---

## 2. Tracking Dependencies (Preventing Broken References)

### Problem
How do we ensure we don't miss or break any dependencies?

### Solution: **Dependency Graph + Automated Checks**

#### Step 1: Generate Dependency Graph

```python
# tools/generate_dependency_graph.py
"""
Generate complete dependency graph of codebase.

Output:
- dependency_graph.json (machine-readable)
- dependency_graph.md (human-readable)
- dependency_graph.png (visual diagram)
"""

import ast
import json
from pathlib import Path
from collections import defaultdict

class DependencyExtractor(ast.NodeVisitor):
    def __init__(self, file_path):
        self.file_path = file_path
        self.imports = []
        self.function_calls = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({
                'type': 'import',
                'module': alias.name,
                'line': node.lineno
            })

    def visit_ImportFrom(self, node):
        self.imports.append({
            'type': 'import_from',
            'module': node.module,
            'names': [alias.name for alias in node.names],
            'line': node.lineno
        })

    def visit_Call(self, node):
        # Extract service/function calls
        if isinstance(node.func, ast.Attribute):
            self.function_calls.append({
                'function': ast.unparse(node.func),
                'line': node.lineno
            })
        self.generic_visit(node)

def build_dependency_graph(root_path: str) -> dict:
    """Build complete dependency graph."""
    graph = defaultdict(lambda: {
        'imports': [],
        'imported_by': [],
        'calls': [],
        'called_by': []
    })

    # Scan all Python files
    for file_path in Path(root_path).rglob("*.py"):
        rel_path = file_path.relative_to(root_path)
        module_name = str(rel_path).replace('/', '.').replace('.py', '')

        with open(file_path) as f:
            try:
                tree = ast.parse(f.read())
                extractor = DependencyExtractor(str(file_path))
                extractor.visit(tree)

                # Record imports
                for imp in extractor.imports:
                    graph[module_name]['imports'].append(imp)
                    graph[imp['module']]['imported_by'].append(module_name)

                # Record function calls
                for call in extractor.function_calls:
                    graph[module_name]['calls'].append(call)

            except SyntaxError:
                print(f"⚠️  Syntax error in {file_path}")

    return dict(graph)

def generate_migration_impact_report(graph: dict, component: str) -> dict:
    """
    Generate impact report for migrating a component.

    Shows:
    - What depends on this component (will break if we change it)
    - What this component depends on (need to migrate or mock)
    """
    component_graph = graph.get(component, {})

    return {
        'component': component,
        'imported_by': component_graph.get('imported_by', []),
        'imports': component_graph.get('imports', []),
        'impact_score': len(component_graph.get('imported_by', [])),
        'complexity_score': len(component_graph.get('imports', []))
    }

# Usage
if __name__ == '__main__':
    graph = build_dependency_graph('app/')

    # Save graph
    with open('dependency_graph.json', 'w') as f:
        json.dump(graph, f, indent=2)

    # Generate impact report for meal_plan_service
    report = generate_migration_impact_report(
        graph,
        'app.services.meal_plan_service'
    )

    print(f"\n📊 Migration Impact Report: {report['component']}")
    print(f"   Files that depend on this: {report['impact_score']}")
    print(f"   Dependencies this has: {report['complexity_score']}")
    print(f"\n   ⚠️  These files will break if we change this:")
    for dep in report['imported_by']:
        print(f"      - {dep}")
```

#### Step 2: Migration Order Strategy

**Migrate in dependency order (bottom-up):**

```markdown
## Migration Order (Based on Dependency Graph)

### Wave 1: No Dependencies (Safe to migrate first)
- `domain/user/value_objects.py` - No dependencies
- `domain/nutrition/value_objects.py` - No dependencies
- `domain/inventory/value_objects.py` - No dependencies

### Wave 2: Domain Models (Depend only on value objects)
- `domain/user/models.py` - Depends on value_objects
- `domain/nutrition/models.py` - Depends on value_objects
- `domain/inventory/models.py` - Depends on value_objects

### Wave 3: Repository Interfaces (Depend on models)
- `domain/user/repository.py` - Depends on models
- `domain/nutrition/repository.py` - Depends on models

### Wave 4: Repository Implementations (Depend on interfaces)
- `infrastructure/persistence/sqlalchemy/repositories/user_repository.py`
- `infrastructure/persistence/sqlalchemy/repositories/nutrition_repository.py`

### Wave 5: Use Cases (Depend on repositories)
- `domain/nutrition/use_cases/get_daily_stats.py` - Simple, no cross-domain deps
- `domain/meal_planning/use_cases/create_meal_plan.py` - Single domain

### Wave 6: Application Services (Depend on use cases)
- `application/services/nutrition_service.py`
- `application/services/meal_plan_service.py`

### Wave 7: API Layer (Depend on services)
- `presentation/api/v1/nutrition.py`
- `presentation/api/v1/meal_plans.py`

### Wave 8: AI/LangGraph (Special - split file)
- `infrastructure/ai/langgraph/state.py`
- `infrastructure/ai/langgraph/nodes/`
- `infrastructure/ai/langgraph/tools/`
```

#### Step 3: Automated Dependency Checker (CI/CD)

```python
# .github/workflows/check_dependencies.py
"""
Run in CI/CD to check for broken dependencies.
"""

def check_import_still_works(old_import: str, new_import: str):
    """Verify old import path still resolves."""
    try:
        exec(f"from {old_import}")
        return True
    except ImportError as e:
        print(f"❌ Broken import: {old_import} -> {e}")
        return False

def validate_all_imports():
    """Validate all imports in codebase."""
    broken = []

    for file in Path('app/').rglob('*.py'):
        with open(file) as f:
            for i, line in enumerate(f, 1):
                if 'from app.' in line or 'import app.' in line:
                    # Try importing
                    try:
                        exec(line)
                    except ImportError as e:
                        broken.append({
                            'file': str(file),
                            'line': i,
                            'import': line.strip(),
                            'error': str(e)
                        })

    if broken:
        print("❌ Found broken imports:")
        for b in broken:
            print(f"   {b['file']}:{b['line']} - {b['import']}")
        return False

    print("✅ All imports valid")
    return True
```

---

## 3. Ensuring We're Restructuring, Not Rewriting

### Problem
How do we prevent accidental logic changes?

### Solution: **Behavior-Preserving Refactoring Strategy**

#### Strategy 1: Extract Method (Don't Rewrite)

**WRONG (Rewriting):**
```python
# OLD CODE
def create_meal_plan(db, user_id, start, end, name):
    # Check overlaps
    existing = db.query(MealPlan).filter(
        MealPlan.user_id == user_id,
        MealPlan.is_active == True,
        MealPlan.start_date <= end,
        MealPlan.end_date >= start
    ).first()

    if existing:
        raise HTTPException(400, "Overlapping plan")

    # Create plan
    plan = MealPlan(user_id=user_id, ...)
    db.add(plan)
    db.commit()
    return plan

# NEW CODE (REWRITTEN - DANGEROUS!)
def create_meal_plan(...):
    # Rewrote the overlap check differently
    plans = get_all_plans(user_id)
    for p in plans:
        if has_overlap(p, start, end):  # New logic!
            raise ValueError("Overlap")  # Different exception!
    ...
```

**RIGHT (Restructuring - Extract, Don't Rewrite):**
```python
# STEP 1: Extract methods in OLD file (behavior unchanged)
def create_meal_plan(db, user_id, start, end, name):
    _check_no_overlaps(db, user_id, start, end)  # Extracted
    plan = _create_plan_entity(user_id, start, end, name)  # Extracted
    _save_plan(db, plan)  # Extracted
    return plan

def _check_no_overlaps(db, user_id, start, end):
    # EXACT SAME LOGIC as before, just extracted
    existing = db.query(MealPlan).filter(
        MealPlan.user_id == user_id,
        MealPlan.is_active == True,
        MealPlan.start_date <= end,
        MealPlan.end_date >= start
    ).first()

    if existing:
        raise HTTPException(400, "Overlapping plan")

# STEP 2: Move extracted methods to domain (copy-paste, don't rewrite!)
# domain/meal_planning/use_cases/create_meal_plan.py
class CreateMealPlan:
    async def execute(self, input):
        await self._check_no_overlaps(input.user_id, input.start, input.end)
        # COPIED logic, not rewritten!
```

#### Strategy 2: Automated Behavior Tests

**Create snapshot tests BEFORE migration:**

```python
# tests/migration/test_meal_plan_service_behavior.py
"""
Snapshot tests to ensure behavior doesn't change.

Run BEFORE migration, save outputs.
Run AFTER migration, compare outputs.
"""

import pytest
from app.services.meal_plan_service import MealPlanService

# Save baseline behavior
BASELINE_OUTPUTS = {}

def capture_baseline():
    """Capture behavior of old implementation."""
    service = MealPlanService(db)

    # Test case 1: Normal creation
    result1 = service.create_meal_plan(
        user_id="test123",
        start_date=date(2025, 11, 25),
        end_date=date(2025, 12, 1),
        name="Test Plan"
    )
    BASELINE_OUTPUTS['test_create_normal'] = result1

    # Test case 2: Overlapping plan (should fail)
    with pytest.raises(HTTPException) as exc_info:
        service.create_meal_plan(...)
    BASELINE_OUTPUTS['test_create_overlap_error'] = str(exc_info.value)

    # Save baseline
    with open('baseline_outputs.json', 'w') as f:
        json.dump(BASELINE_OUTPUTS, f)

def test_behavior_unchanged_after_migration():
    """After migration, verify behavior is identical."""
    # Load baseline
    with open('baseline_outputs.json') as f:
        baseline = json.load(f)

    # Run same tests with NEW implementation
    from application.services.meal_plan_service import MealPlanService as NewService

    new_service = NewService(...)
    result1 = new_service.create_meal_plan(...)

    # Compare outputs
    assert result1 == baseline['test_create_normal'], \
        "Behavior changed! Old != New"
```

#### Strategy 3: Parallel Running (Canary Testing)

**Run old and new side-by-side:**

```python
# application/services/meal_plan_service.py
"""
During migration: Run both old and new, compare results.
"""

class MealPlanService:
    def __init__(self, ...):
        self.use_new_implementation = settings.FEATURE_FLAG_NEW_MEAL_PLAN

    async def create_meal_plan(self, ...):
        if self.use_new_implementation:
            # NEW implementation
            result_new = await self._create_meal_plan_new(...)

            # Also run OLD implementation (for comparison)
            result_old = await self._create_meal_plan_old(...)

            # Compare results
            if result_new != result_old:
                logger.error(f"⚠️  Results differ! Old: {result_old}, New: {result_new}")
                # Report to monitoring
                sentry.capture_message("Migration behavior mismatch")

            return result_new
        else:
            # OLD implementation (fallback)
            return await self._create_meal_plan_old(...)
```

---

## 4. Microservices (Receipt Scanner, WhatsApp Agent)

### Problem
How does this plan handle microservices?

### Solution: **Microservices fit into Infrastructure Layer**

```markdown
## Microservices Architecture

### Current State
```
NutriLens/
├── backend/              # Main FastAPI app
├── receipt_scanner/      # Microservice (separate repo?)
└── whatsapp_agent/       # Microservice (separate repo?)
```

### Where They Fit in Clean Architecture

```
infrastructure/
└── external_services/
    ├── receipt_scanner/
    │   ├── client.py              # HTTP client to microservice
    │   ├── dto.py                 # Request/response models
    │   └── processor.py           # Business logic wrapper
    │
    └── whatsapp_agent/
        ├── client.py              # HTTP client to microservice
        ├── webhook_handler.py     # Handle incoming webhooks
        └── message_sender.py      # Send messages
```

### Example: Receipt Scanner Integration

```python
# infrastructure/external_services/receipt_scanner/client.py
"""
Client for Receipt Scanner microservice.

Design Principle: Port/Adapter
- Main app depends on interface, not concrete microservice
- Can swap microservice implementation
- Can mock for testing
"""

from abc import ABC, abstractmethod
from typing import List
import httpx

class ReceiptScannerPort(ABC):
    """Port (interface) for receipt scanning."""

    @abstractmethod
    async def scan_receipt(self, image_bytes: bytes) -> List[dict]:
        """Scan receipt and return items."""
        pass

class ReceiptScannerHTTPClient(ReceiptScannerPort):
    """Adapter: HTTP client to microservice."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def scan_receipt(self, image_bytes: bytes) -> List[dict]:
        """Call microservice via HTTP."""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/scan",
                files={"image": image_bytes},
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()
            return data['items']

        except httpx.HTTPError as e:
            logger.error(f"Receipt scanner failed: {e}")
            # Graceful fallback
            return []

class ReceiptScannerMockClient(ReceiptScannerPort):
    """Mock adapter for testing (no microservice needed)."""

    async def scan_receipt(self, image_bytes: bytes) -> List[dict]:
        """Return mock data."""
        return [
            {"name": "Milk", "quantity": "2L"},
            {"name": "Eggs", "quantity": "12"}
        ]

# Use in domain/use cases
class ProcessReceiptUseCase:
    def __init__(
        self,
        receipt_scanner: ReceiptScannerPort,  # Depend on interface!
        inventory_repo: InventoryRepository
    ):
        self.receipt_scanner = receipt_scanner
        self.inventory_repo = inventory_repo

    async def execute(self, image_bytes: bytes, user_id: str):
        # Scan receipt (via microservice)
        items = await self.receipt_scanner.scan_receipt(image_bytes)

        # Normalize and add to inventory (domain logic)
        for item_data in items:
            item = Item.from_receipt_data(item_data, user_id)
            await self.inventory_repo.save(item)
```

### Benefits of This Approach:
1. **Main app doesn't care** if it's a microservice, local library, or mock
2. **Easy to test**: Use mock client (no microservice needed)
3. **Easy to swap**: Change microservice URL, or replace with different implementation
4. **Failure handling**: If microservice down, can fallback gracefully

---

## 5. Notification Microservice

### Problem
Do we need a separate notification microservice?

### Analysis

#### Option A: Keep Notifications in Main App (Current)
```
✅ Pros:
- Simple (no additional service to deploy)
- Direct database access
- Easier to maintain

❌ Cons:
- Notification logic coupled to main app
- Can't scale independently
- If main app down, notifications down
```

#### Option B: Extract to Microservice
```
✅ Pros:
- Independent scaling
- Can restart without affecting main app
- Clearer separation of concerns

❌ Cons:
- Additional deployment complexity
- Network latency
- Need message queue (RabbitMQ/Kafka)
```

### Recommendation: **Keep in Main App Initially, Design for Extract Later**

**Structure notifications so they CAN be extracted:**

```python
# domain/notifications/
#   - models.py
#   - repository.py
#   - use_cases/
#       - create_notification.py
#       - schedule_notification.py
#       - send_notification.py

# infrastructure/messaging/
#   - notification_sender.py      # Can be extracted to microservice
#   - notification_scheduler.py   # Can be extracted to microservice

# If we extract later:
#   - Change notification_sender to HTTP client
#   - Point to microservice URL
#   - Domain logic unchanged!
```

---

## Summary: Migration Safety Checklist

### Before Migrating ANY Component:

- [ ] **Behavior Inventory**: Document all public methods, dependencies, edge cases
- [ ] **Dependency Analysis**: Run dependency graph tool, identify all callers
- [ ] **Baseline Tests**: Create snapshot tests with current behavior
- [ ] **Migration Order**: Ensure dependencies already migrated
- [ ] **Impact Score**: Know how many files depend on this

### During Migration:

- [ ] **Extract, Don't Rewrite**: Move code, don't change logic
- [ ] **Parallel Running**: Run old + new side-by-side (if critical)
- [ ] **Automated Checks**: CI/CD validates imports still work

### After Migration:

- [ ] **Behavior Tests Pass**: Snapshot tests show identical behavior
- [ ] **Integration Tests Pass**: End-to-end tests pass
- [ ] **Dependency Check**: No broken imports
- [ ] **Performance Test**: Response times unchanged
- [ ] **Canary Deploy**: Deploy to 10% of traffic first

---

**Would you like me to:**
1. Create the automated tools (dependency graph generator, behavior extractor)?
2. Start with a behavior inventory for ONE component (e.g., meal_plan_service)?
3. Update the restructuring plan with this migration tracking strategy?