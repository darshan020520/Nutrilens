# NutriLens - Component-by-Component Restructuring Master Plan

**Version**: 1.0
**Date**: 2025-11-24
**Status**: Planning Phase

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current System Analysis](#2-current-system-analysis)
3. [Design Principles & Patterns](#3-design-principles--patterns)
4. [Component Restructuring Plans](#4-component-restructuring-plans)
   - [Component 1: Domain Models](#component-1-domain-models)
   - [Component 2: Repository Pattern](#component-2-repository-pattern)
   - [Component 3: Use Cases](#component-3-use-cases)
   - [Component 4: Application Services](#component-4-application-services)
   - [Component 5: API Layer](#component-5-api-layer)
   - [Component 6: LangGraph AI Agent](#component-6-langgraph-ai-agent)
   - [Component 7: External Services](#component-7-external-services)
   - [Component 8: Infrastructure](#component-8-infrastructure)
5. [Migration Timeline](#5-migration-timeline)

---

## 1. Overview

### 1.1 Purpose

This document provides a **complete, step-by-step restructuring plan** for the NutriLens backend. Each component is analyzed independently with:

- **Current State**: What exists today
- **Problems**: Why it needs to change
- **Design Principles**: What patterns/principles we'll apply
- **Target State**: What we want to achieve
- **Dependencies**: What depends on this component
- **Impact Analysis**: How changes affect other components
- **Migration Steps**: Exact steps to restructure
- **Validation**: How to verify the restructuring worked

### 1.2 Goals

1. **Separation of Concerns**: Clear boundaries between layers
2. **Testability**: Each component can be tested in isolation
3. **Maintainability**: Easy to understand, modify, and extend
4. **Scalability**: Support future growth without major rewrites
5. **Flexibility**: Easy to swap implementations (e.g., change database)

### 1.3 Non-Goals

- **We are NOT changing functionality**: All features work the same from user perspective
- **We are NOT rewriting code**: We're reorganizing and refactoring existing code
- **We are NOT optimizing performance** (unless structure enables it)

---

## 2. Current System Analysis

### 2.1 Current Directory Structure

```
backend/app/
├── agents/               # AI agent layer (LangGraph)
│   ├── graph_instance.py            # Singleton compiled graph
│   ├── nutrition_graph.py           # 845 lines - graph + nodes + tools + prompts
│   ├── nutrition_context.py         # Context loading
│   ├── nutrition_intelligence.py    # Tool implementations
│   ├── nutrition_agent.py           # OLD (deprecated?)
│   ├── nutrition_agent_helper.py    # OLD (deprecated?)
│   ├── planning_agent.py
│   ├── tracking_agent.py
│   └── ne_tracking.py
│
├── api/                  # API endpoints (FastAPI routers)
│   ├── auth.py
│   ├── onboarding.py
│   ├── recipes.py
│   ├── inventory.py
│   ├── meal_plan.py
│   ├── tracking.py
│   ├── dashboard.py
│   ├── notifications.py
│   ├── websocket.py
│   ├── receipt.py
│   ├── orchestrator.py              # Deprecated?
│   └── nutrition_chat.py
│
├── core/                 # Core configuration
│   ├── config.py
│   ├── events.py
│   ├── mongodb.py
│   └── database.py (missing - should exist)
│
├── models/               # Database models
│   └── database.py                  # ALL SQLAlchemy models in ONE file
│
├── schemas/              # Pydantic schemas
│   ├── user.py
│   ├── nutrition.py
│   ├── tracking.py
│   ├── meal_plan.py
│   └── optimizer.py
│
├── services/             # Business logic (mixed with infrastructure)
│   ├── auth.py
│   ├── consumption_services.py
│   ├── inventory_service.py
│   ├── meal_plan_service.py
│   ├── notification_service.py
│   ├── notification_scheduler.py
│   ├── recipe_service.py
│   ├── websocket_manager.py
│   ├── llm_client.py
│   ├── llm_recipe_generator.py
│   ├── llm_nutrition_estimator.py
│   ├── item_normalizer_rag.py
│   ├── embedding_service.py
│   ├── fdc_service.py
│   ├── education_service.py
│   ├── final_meal_optimizer.py
│   ├── genetic_optimizer.py
│   └── data_seeder.py
│
└── workers/              # Background workers
```

### 2.2 Key Problems

#### Problem 1: **No Clear Separation of Concerns**
- **Issue**: Business logic mixed with database access, API handling, and external services
- **Example**: `services/consumption_services.py` contains:
  - Business logic (calculating macros)
  - Database queries (SQLAlchemy)
  - External API calls (FDC lookup)
  - All in the same file/class

#### Problem 2: **Fat Models, Anemic Domain**
- **Issue**: `models/database.py` contains only data structures (SQLAlchemy ORM models)
- **Problem**: No business logic in domain models (anemic domain anti-pattern)
- **Result**: All logic scattered across services

#### Problem 3: **Tight Coupling**
- **Issue**: Services directly depend on SQLAlchemy models
- **Problem**: Can't test business logic without database
- **Problem**: Can't swap database implementation

#### Problem 4: **Giant Files**
- **Issue**: `nutrition_graph.py` is 845 lines (graph structure + nodes + tools + prompts all in one file)
- **Issue**: `models/database.py` contains ALL tables
- **Problem**: Hard to navigate, understand, modify

#### Problem 5: **No Abstraction Layers**
- **Issue**: API handlers directly call services, services directly query database
- **Problem**: Can't reuse business logic across different entry points (API, CLI, background jobs)

#### Problem 6: **Unclear Dependencies**
- **Issue**: Circular imports (e.g., agents importing services, services importing agents)
- **Problem**: Hard to understand what depends on what

---

## 3. Design Principles & Patterns

### 3.1 Clean Architecture (Uncle Bob)

**Core Idea**: Dependencies point INWARD toward business logic

```
┌─────────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                      │
│  (API Handlers, CLI, Background Jobs)                   │
│  - Thin layer                                           │
│  - Handle HTTP, validation, serialization              │
│  - NO business logic                                    │
└────────────────────┬────────────────────────────────────┘
                     │ depends on
┌────────────────────▼────────────────────────────────────┐
│                 APPLICATION LAYER                        │
│  (Application Services)                                 │
│  - Orchestrate use cases                                │
│  - Coordinate between domains                           │
│  - Convert DTOs ↔ Domain models                         │
│  - NO business logic (delegate to domain)               │
└────────────────────┬────────────────────────────────────┘
                     │ depends on
┌────────────────────▼────────────────────────────────────┐
│                   DOMAIN LAYER                           │
│  (Business Logic - Framework Agnostic)                  │
│  - Domain models (rich models with behavior)            │
│  - Use cases (single business operations)               │
│  - Repository interfaces (abstract)                     │
│  - NO dependencies on frameworks                        │
└────────────────────▲────────────────────────────────────┘
                     │ implements
┌────────────────────┴────────────────────────────────────┐
│                INFRASTRUCTURE LAYER                      │
│  (Implementation Details)                               │
│  - Repository implementations (SQLAlchemy)              │
│  - External API clients (OpenAI, FDC)                   │
│  - File system, network, databases                      │
│  - Depends on domain (implements interfaces)            │
└─────────────────────────────────────────────────────────┘
```

**Benefits**:
- Business logic independent of frameworks
- Easy to test (mock dependencies)
- Easy to swap implementations (e.g., Postgres → MongoDB)
- Clear dependency flow

---

### 3.2 Repository Pattern

**Problem**: Services directly query database using SQLAlchemy

**Solution**: Abstract data access behind repository interface

```python
# BEFORE (services directly use SQLAlchemy)
class ConsumptionService:
    def log_consumption(self, db: Session, user_id: str, item_id: str):
        # Business logic mixed with database access
        item = db.query(Item).filter(Item.id == item_id).first()
        log = ConsumptionLog(user_id=user_id, item_id=item_id, ...)
        db.add(log)
        db.commit()

# AFTER (service uses repository abstraction)
class LogConsumption:  # Use case
    def __init__(self, repo: ConsumptionRepository):
        self.repo = repo

    async def execute(self, log: ConsumptionLog) -> ConsumptionLog:
        # Pure business logic
        log.validate()
        log.calculate_macros()
        return await self.repo.save(log)
```

**Benefits**:
- Business logic doesn't know about SQLAlchemy
- Easy to test (mock repository)
- Easy to swap database

---

### 3.3 Use Case Pattern

**Problem**: Services do too much (multiple responsibilities)

**Solution**: One use case class per business operation

```python
# BEFORE (fat service)
class MealPlanService:
    def create_meal_plan(self, ...): ...
    def optimize_meal_plan(self, ...): ...
    def get_meal_plan(self, ...): ...
    def delete_meal_plan(self, ...): ...
    # 500 lines of code

# AFTER (one use case per operation)
class CreateMealPlan:
    def execute(self, ...): ...

class OptimizeMealPlan:
    def execute(self, ...): ...

class GetMealPlan:
    def execute(self, ...): ...
```

**Benefits**:
- Single Responsibility Principle
- Easy to test individual operations
- Easy to understand what each class does

---

### 3.4 Dependency Inversion Principle (DIP)

**Problem**: High-level modules depend on low-level modules

```python
# BEFORE (direct dependency on SQLAlchemy)
class ConsumptionService:
    def __init__(self, db: Session):  # Depends on SQLAlchemy
        self.db = db

# AFTER (depends on abstraction)
class LogConsumption:
    def __init__(self, repo: ConsumptionRepository):  # Depends on interface
        self.repo = repo
```

**Benefits**:
- High-level logic independent of low-level details
- Easy to swap implementations

---

### 3.5 Domain-Driven Design (DDD)

**Organize by Domain, Not Layer**:

```
# BEFORE (organized by layer)
models/
  database.py (all models together)

# AFTER (organized by domain)
domain/
  user/
    models.py
    repository.py
    use_cases.py
  nutrition/
    models.py
    repository.py
    use_cases.py
```

**Benefits**:
- Related code grouped together
- Easy to understand domain boundaries
- Easy to work on one feature without touching others

---

## 4. Component Restructuring Plans

---

## Component 1: Domain Models

### Current State

**Location**: `app/models/database.py`

**Structure**:
```python
# ALL models in ONE file
class User(Base):
    __tablename__ = "users"
    # anemic model - only data, no behavior

class Item(Base):
    __tablename__ = "items"
    # anemic model - only data, no behavior

class ConsumptionLog(Base):
    __tablename__ = "consumption_logs"
    # anemic model - only data, no behavior

# ... 20+ more models
```

**Problems**:
1. **Anemic Domain Anti-pattern**: Models have no behavior, only getters/setters
2. **Giant File**: All models in one file (~1000+ lines)
3. **Tight Coupling to SQLAlchemy**: Business logic depends on ORM
4. **No Validation**: Validation scattered across services
5. **No Business Rules**: Business rules not enforced at model level

---

### Design Principles Applied

1. **Rich Domain Model**: Models contain business logic and validation
2. **Framework Independence**: Domain models are pure Python (no SQLAlchemy)
3. **Single Responsibility**: Each model in its own file
4. **Value Objects**: Immutable objects for concepts like Email, Money, Quantity

---

### Target State

**New Structure**:
```
domain/
├── user/
│   ├── models.py                # User, UserProfile (rich models)
│   ├── value_objects.py         # Email, Password, BMI, TDEE
│   └── exceptions.py            # Domain exceptions
│
├── nutrition/
│   ├── models.py                # ConsumptionLog, DailyStats, NutritionTarget
│   ├── value_objects.py         # Calories, Macros, Quantity
│   ├── calculators.py           # TDEE calculator, macro calculator
│   └── exceptions.py
│
├── inventory/
│   ├── models.py                # Item, InventoryEntry, StockAlert
│   ├── value_objects.py         # ExpirationDate, StockLevel
│   └── exceptions.py
│
├── recipes/
│   ├── models.py                # Recipe, RecipeIngredient, RecipeNutrition
│   ├── value_objects.py         # CookingTime, Difficulty, Servings
│   └── exceptions.py
│
└── meal_planning/
    ├── models.py                # MealPlan, PlannedMeal, ShoppingList
    ├── value_objects.py         # MealType, WeekSchedule
    └── exceptions.py
```

**Example**: Rich Domain Model

```python
# domain/nutrition/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from domain.nutrition.value_objects import Calories, Macros, Quantity
from domain.nutrition.exceptions import InvalidConsumptionLogError

@dataclass
class ConsumptionLog:
    """
    Rich domain model for consumption log.

    Contains business logic and validation.
    Framework-agnostic (no SQLAlchemy).
    """
    id: Optional[str]  # UUID as string
    user_id: str
    item_id: str
    quantity: Quantity
    consumed_at: datetime
    meal_type: Optional[str] = None

    # Calculated fields (lazy-loaded)
    _macros: Optional[Macros] = None

    def calculate_macros(self, item_nutrition: dict) -> None:
        """
        Calculate macros based on quantity and item nutrition.

        Business Rule: Macros = (item nutrition / serving size) * quantity
        """
        multiplier = self.quantity.amount / item_nutrition['serving_size']
        self._macros = Macros(
            calories=Calories(item_nutrition['calories'] * multiplier),
            protein=item_nutrition['protein'] * multiplier,
            carbs=item_nutrition['carbs'] * multiplier,
            fats=item_nutrition['fats'] * multiplier
        )

    @property
    def macros(self) -> Optional[Macros]:
        """Get calculated macros."""
        return self._macros

    def validate(self) -> None:
        """
        Validate business rules.

        Business Rules:
        1. Quantity must be positive
        2. User ID must exist
        3. Consumed time can't be in future
        4. Meal type must be valid
        """
        if self.quantity.amount <= 0:
            raise InvalidConsumptionLogError("Quantity must be positive")

        if not self.user_id:
            raise InvalidConsumptionLogError("User ID is required")

        if self.consumed_at > datetime.now():
            raise InvalidConsumptionLogError("Cannot log future consumption")

        valid_meal_types = ['breakfast', 'lunch', 'dinner', 'snack', None]
        if self.meal_type not in valid_meal_types:
            raise InvalidConsumptionLogError(f"Invalid meal type: {self.meal_type}")

    def is_breakfast(self) -> bool:
        """Check if this is a breakfast log."""
        return self.meal_type == 'breakfast'

    def is_high_calorie(self, threshold: int = 500) -> bool:
        """Check if this log is high-calorie."""
        if not self._macros:
            raise ValueError("Macros not calculated yet")
        return self._macros.calories.value > threshold

# domain/nutrition/value_objects.py
from dataclasses import dataclass

@dataclass(frozen=True)  # Immutable
class Calories:
    """Value object for calories."""
    value: float

    def __post_init__(self):
        if self.value < 0:
            raise ValueError("Calories cannot be negative")

    def __add__(self, other: 'Calories') -> 'Calories':
        return Calories(self.value + other.value)

    def __str__(self) -> str:
        return f"{self.value:.1f} kcal"

@dataclass(frozen=True)
class Macros:
    """Value object for macronutrients."""
    calories: Calories
    protein: float  # grams
    carbs: float    # grams
    fats: float     # grams

    def __post_init__(self):
        if self.protein < 0 or self.carbs < 0 or self.fats < 0:
            raise ValueError("Macros cannot be negative")

    def __add__(self, other: 'Macros') -> 'Macros':
        return Macros(
            calories=self.calories + other.calories,
            protein=self.protein + other.protein,
            carbs=self.carbs + other.carbs,
            fats=self.fats + other.fats
        )

    def meets_target(self, target: 'Macros', tolerance: float = 0.1) -> bool:
        """Check if macros meet target within tolerance."""
        return (
            abs(self.protein - target.protein) <= target.protein * tolerance and
            abs(self.carbs - target.carbs) <= target.carbs * tolerance and
            abs(self.fats - target.fats) <= target.fats * tolerance
        )

@dataclass(frozen=True)
class Quantity:
    """Value object for quantity with unit."""
    amount: float
    unit: str  # 'g', 'ml', 'piece', etc.

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("Quantity must be positive")
        if not self.unit:
            raise ValueError("Unit is required")

    def to_grams(self) -> float:
        """Convert to grams (if possible)."""
        conversion = {
            'g': 1,
            'kg': 1000,
            'mg': 0.001,
            'ml': 1,  # Assume 1ml = 1g for liquids
            'l': 1000,
        }
        if self.unit not in conversion:
            raise ValueError(f"Cannot convert {self.unit} to grams")
        return self.amount * conversion[self.unit]
```

---

### Dependencies

**Who depends on current models?**
1. **Services**: All services import from `models.database`
2. **API handlers**: Import models for type hints
3. **Database migrations**: Alembic references table names
4. **Tests**: Tests use models directly

**Impact**:
- HIGH impact - this is the foundation
- Must update ALL files that import models
- Requires careful migration strategy

---

### Impact Analysis

**Breaking Changes**:
1. Import paths change: `from app.models.database import User` → `from app.domain.user.models import User`
2. SQLAlchemy models moved to infrastructure layer
3. Business logic moves from services to domain models

**Migration Complexity**: HIGH
- Need to update 50+ files
- Need to create repository abstractions BEFORE migrating

---

### Migration Steps

#### Step 1: Create Domain Model Structure (Parallel)

```bash
# Create new directories
mkdir -p app/domain/user
mkdir -p app/domain/nutrition
mkdir -p app/domain/inventory
mkdir -p app/domain/recipes
mkdir -p app/domain/meal_planning
mkdir -p app/domain/notifications
```

#### Step 2: Extract User Domain Model

**File**: `app/domain/user/models.py`

```python
"""
User domain models - pure business logic, no SQLAlchemy.

Design Principles:
- Rich domain model (behavior + data)
- Framework-agnostic (pure Python)
- Validation at model level
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from domain.user.value_objects import Email, Password, BMI, TDEE
from domain.user.exceptions import InvalidUserProfileError

@dataclass
class User:
    """User aggregate root."""
    id: Optional[str]  # UUID as string
    email: Email
    password_hash: str  # Already hashed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def change_email(self, new_email: Email) -> None:
        """Change user email."""
        self.email = new_email
        self.updated_at = datetime.now()

    def validate(self) -> None:
        """Validate user."""
        if not self.email:
            raise ValueError("Email is required")

@dataclass
class UserProfile:
    """User profile with nutrition goals."""
    id: Optional[str]
    user_id: str
    name: Optional[str]
    age: Optional[int]
    gender: Optional[str]
    height_cm: Optional[float]
    weight_kg: Optional[float]
    activity_level: str  # 'sedentary', 'light', 'moderate', 'active', 'very_active'
    goal_type: str  # 'weight_loss', 'muscle_gain', 'maintenance'
    dietary_restrictions: List[str] = field(default_factory=list)

    # Nutrition targets
    target_calories: Optional[int] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fats: Optional[float] = None

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def calculate_bmi(self) -> Optional[BMI]:
        """Calculate BMI if height and weight available."""
        if self.height_cm and self.weight_kg:
            return BMI.calculate(self.weight_kg, self.height_cm)
        return None

    def calculate_tdee(self) -> Optional[TDEE]:
        """
        Calculate Total Daily Energy Expenditure.

        Business Rule: TDEE = BMR * Activity Multiplier
        """
        if not all([self.age, self.gender, self.height_cm, self.weight_kg]):
            return None

        return TDEE.calculate(
            age=self.age,
            gender=self.gender,
            height_cm=self.height_cm,
            weight_kg=self.weight_kg,
            activity_level=self.activity_level
        )

    def set_calorie_target(self, tdee: TDEE) -> None:
        """
        Set calorie target based on goal.

        Business Rules:
        - Weight loss: TDEE - 500 (1 lb/week loss)
        - Muscle gain: TDEE + 300
        - Maintenance: TDEE
        """
        if self.goal_type == 'weight_loss':
            self.target_calories = int(tdee.value - 500)
        elif self.goal_type == 'muscle_gain':
            self.target_calories = int(tdee.value + 300)
        else:  # maintenance
            self.target_calories = int(tdee.value)

        self.updated_at = datetime.now()

    def set_macro_targets(self) -> None:
        """
        Set macro targets based on goal.

        Business Rules:
        - Weight loss: 40% protein, 30% carbs, 30% fats
        - Muscle gain: 30% protein, 40% carbs, 30% fats
        - Maintenance: 25% protein, 45% carbs, 30% fats
        """
        if not self.target_calories:
            raise InvalidUserProfileError("Calorie target must be set first")

        if self.goal_type == 'weight_loss':
            self.target_protein = (self.target_calories * 0.40) / 4  # 4 cal/g
            self.target_carbs = (self.target_calories * 0.30) / 4
            self.target_fats = (self.target_calories * 0.30) / 9  # 9 cal/g
        elif self.goal_type == 'muscle_gain':
            self.target_protein = (self.target_calories * 0.30) / 4
            self.target_carbs = (self.target_calories * 0.40) / 4
            self.target_fats = (self.target_calories * 0.30) / 9
        else:  # maintenance
            self.target_protein = (self.target_calories * 0.25) / 4
            self.target_carbs = (self.target_calories * 0.45) / 4
            self.target_fats = (self.target_calories * 0.30) / 9

        self.updated_at = datetime.now()

    def validate(self) -> None:
        """Validate profile."""
        if self.age and (self.age < 0 or self.age > 150):
            raise InvalidUserProfileError("Invalid age")

        if self.height_cm and (self.height_cm < 50 or self.height_cm > 300):
            raise InvalidUserProfileError("Invalid height")

        if self.weight_kg and (self.weight_kg < 20 or self.weight_kg > 500):
            raise InvalidUserProfileError("Invalid weight")

        valid_activity_levels = ['sedentary', 'light', 'moderate', 'active', 'very_active']
        if self.activity_level not in valid_activity_levels:
            raise InvalidUserProfileError(f"Invalid activity level: {self.activity_level}")

        valid_goals = ['weight_loss', 'muscle_gain', 'maintenance']
        if self.goal_type not in valid_goals:
            raise InvalidUserProfileError(f"Invalid goal type: {self.goal_type}")
```

**File**: `app/domain/user/value_objects.py`

```python
"""User domain value objects."""

from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Email:
    """Value object for email address."""
    value: str

    def __post_init__(self):
        if not self._is_valid(self.value):
            raise ValueError(f"Invalid email: {self.value}")

    @staticmethod
    def _is_valid(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def __str__(self) -> str:
        return self.value

@dataclass(frozen=True)
class BMI:
    """Value object for Body Mass Index."""
    value: float

    def __post_init__(self):
        if self.value < 10 or self.value > 100:
            raise ValueError(f"Invalid BMI: {self.value}")

    @classmethod
    def calculate(cls, weight_kg: float, height_cm: float) -> 'BMI':
        """Calculate BMI from weight and height."""
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)
        return cls(bmi)

    def category(self) -> str:
        """Get BMI category."""
        if self.value < 18.5:
            return "Underweight"
        elif self.value < 25:
            return "Normal weight"
        elif self.value < 30:
            return "Overweight"
        else:
            return "Obese"

    def __str__(self) -> str:
        return f"{self.value:.1f} ({self.category()})"

@dataclass(frozen=True)
class TDEE:
    """Value object for Total Daily Energy Expenditure."""
    value: float  # calories per day

    @classmethod
    def calculate(cls, age: int, gender: str, height_cm: float, weight_kg: float, activity_level: str) -> 'TDEE':
        """
        Calculate TDEE using Mifflin-St Jeor equation.

        BMR = (10 × weight in kg) + (6.25 × height in cm) - (5 × age in years) + s
        where s = +5 for males, -161 for females

        TDEE = BMR × Activity Multiplier
        """
        # Calculate BMR
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
        if gender.lower() == 'male':
            bmr += 5
        else:
            bmr -= 161

        # Activity multipliers
        activity_multipliers = {
            'sedentary': 1.2,
            'light': 1.375,
            'moderate': 1.55,
            'active': 1.725,
            'very_active': 1.9
        }

        multiplier = activity_multipliers.get(activity_level, 1.2)
        tdee = bmr * multiplier

        return cls(tdee)

    def __str__(self) -> str:
        return f"{int(self.value)} kcal/day"
```

**File**: `app/domain/user/exceptions.py`

```python
"""User domain exceptions."""

class UserDomainError(Exception):
    """Base exception for user domain."""
    pass

class InvalidUserProfileError(UserDomainError):
    """Raised when user profile is invalid."""
    pass

class UserNotFoundError(UserDomainError):
    """Raised when user is not found."""
    pass
```

#### Step 3: Keep Old Models (Backwards Compatibility)

**DO NOT DELETE** `app/models/database.py` yet!

**Reason**: We need a gradual migration. Services will continue using old models until we migrate them one by one.

#### Step 4: Create Mapper (Convert between Domain and ORM)

**File**: `app/infrastructure/persistence/sqlalchemy/mappers/user_mapper.py`

```python
"""
Mapper between domain models and SQLAlchemy ORM models.

This allows domain models to stay pure Python while still
persisting to database via SQLAlchemy.
"""

from domain.user.models import User, UserProfile
from domain.user.value_objects import Email
from infrastructure.persistence.sqlalchemy.models import UserModel, UserProfileModel

class UserMapper:
    """Map between User domain model and UserModel ORM model."""

    @staticmethod
    def to_domain(orm_model: UserModel) -> User:
        """Convert ORM model to domain model."""
        return User(
            id=str(orm_model.id),
            email=Email(orm_model.email),
            password_hash=orm_model.password_hash,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at
        )

    @staticmethod
    def to_orm(domain_model: User) -> UserModel:
        """Convert domain model to ORM model."""
        return UserModel(
            id=domain_model.id,
            email=str(domain_model.email),
            password_hash=domain_model.password_hash,
            created_at=domain_model.created_at,
            updated_at=domain_model.updated_at
        )

class UserProfileMapper:
    """Map between UserProfile domain model and UserProfileModel ORM model."""

    @staticmethod
    def to_domain(orm_model: UserProfileModel) -> UserProfile:
        """Convert ORM model to domain model."""
        return UserProfile(
            id=str(orm_model.id),
            user_id=str(orm_model.user_id),
            name=orm_model.name,
            age=orm_model.age,
            gender=orm_model.gender,
            height_cm=orm_model.height_cm,
            weight_kg=orm_model.weight_kg,
            activity_level=orm_model.activity_level,
            goal_type=orm_model.goal_type,
            dietary_restrictions=orm_model.dietary_restrictions or [],
            target_calories=orm_model.target_calories,
            target_protein=orm_model.target_protein,
            target_carbs=orm_model.target_carbs,
            target_fats=orm_model.target_fats,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at
        )

    @staticmethod
    def to_orm(domain_model: UserProfile) -> UserProfileModel:
        """Convert domain model to ORM model."""
        return UserProfileModel(
            id=domain_model.id,
            user_id=domain_model.user_id,
            name=domain_model.name,
            age=domain_model.age,
            gender=domain_model.gender,
            height_cm=domain_model.height_cm,
            weight_kg=domain_model.weight_kg,
            activity_level=domain_model.activity_level,
            goal_type=domain_model.goal_type,
            dietary_restrictions=domain_model.dietary_restrictions,
            target_calories=domain_model.target_calories,
            target_protein=domain_model.target_protein,
            target_carbs=domain_model.target_carbs,
            target_fats=domain_model.target_fats,
            created_at=domain_model.created_at,
            updated_at=domain_model.updated_at
        )
```

#### Step 5: Validation

**Test 1**: Import new domain models
```python
# Test in Python REPL
from app.domain.user.models import User, UserProfile
from app.domain.user.value_objects import Email, BMI, TDEE

# Create user
email = Email("[email protected]")
user = User(id=None, email=email, password_hash="hashed")
print(user)

# Create profile
profile = UserProfile(
    id=None,
    user_id="123",
    age=30,
    gender="male",
    height_cm=180,
    weight_kg=80,
    activity_level="moderate",
    goal_type="weight_loss"
)

# Calculate BMI
bmi = profile.calculate_bmi()
print(bmi)  # Should print "24.7 (Normal weight)"

# Calculate TDEE
tdee = profile.calculate_tdee()
print(tdee)  # Should print "~2400 kcal/day"

# Set targets
profile.set_calorie_target(tdee)
profile.set_macro_targets()
print(profile.target_calories)  # Should be TDEE - 500
```

**Test 2**: Old models still work
```python
from app.models.database import User as OldUser
# Should still work - no breaking changes yet
```

---

### Rollback Plan

If migration fails:
1. Delete new `domain/` directory
2. Old `models/database.py` still exists
3. No changes to existing code
4. Zero downtime

---

### Documentation

**Update**:
- [ ] Add docstrings to all domain models
- [ ] Create `domain/README.md` explaining structure
- [ ] Update architecture diagrams

---

## Component 2: Repository Pattern

### Current State

**Location**: Database access scattered across services

**Structure**:
```python
# services/consumption_services.py
def log_consumption(db: Session, user_id: str, item_id: str, quantity: float):
    # Direct SQLAlchemy queries mixed with business logic
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")

    # Calculate macros (business logic)
    multiplier = quantity / item.serving_size
    calories = item.calories * multiplier

    # Save to database
    log = ConsumptionLog(
        user_id=user_id,
        item_id=item_id,
        quantity=quantity,
        calories=calories,
        ...
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
```

**Problems**:
1. **Tight Coupling**: Business logic directly depends on SQLAlchemy
2. **Hard to Test**: Can't test business logic without database
3. **Hard to Swap**: Can't change from Postgres to MongoDB without rewriting services
4. **No Abstraction**: Every service writes its own queries
5. **Duplication**: Same queries repeated across services

---

### Design Principles Applied

1. **Repository Pattern**: Abstract data access behind interface
2. **Dependency Inversion**: Depend on abstraction, not concrete implementation
3. **Single Responsibility**: Repository handles ONLY data access
4. **Interface Segregation**: One repository per aggregate root

---

### Target State

**New Structure**:
```
domain/
└── nutrition/
    └── repository.py          # Abstract repository interface

infrastructure/
└── persistence/
    └── sqlalchemy/
        ├── models.py          # SQLAlchemy ORM models
        └── repositories/
            └── nutrition_repository.py  # Concrete implementation
```

**Example**: Repository Interface (Domain)

```python
# domain/nutrition/repository.py
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from domain.nutrition.models import ConsumptionLog, DailyStats

class NutritionRepository(ABC):
    """
    Repository interface for nutrition domain.

    Design Principle: Dependency Inversion
    - Domain defines interface
    - Infrastructure implements interface
    - Business logic depends on interface, not implementation
    """

    @abstractmethod
    async def save_consumption_log(self, log: ConsumptionLog) -> ConsumptionLog:
        """
        Save consumption log to storage.

        Args:
            log: Domain model (not ORM model)

        Returns:
            Saved log with generated ID
        """
        pass

    @abstractmethod
    async def get_consumption_log(self, log_id: str) -> Optional[ConsumptionLog]:
        """Get consumption log by ID."""
        pass

    @abstractmethod
    async def get_logs_for_date(self, user_id: str, date: date) -> List[ConsumptionLog]:
        """Get all consumption logs for a specific date."""
        pass

    @abstractmethod
    async def get_logs_for_date_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> List[ConsumptionLog]:
        """Get logs within date range."""
        pass

    @abstractmethod
    async def delete_consumption_log(self, log_id: str) -> None:
        """Delete consumption log."""
        pass

    @abstractmethod
    async def get_daily_stats(self, user_id: str, date: date) -> DailyStats:
        """
        Calculate daily nutrition statistics.

        Business Rule: Aggregate all logs for the day
        """
        pass
```

**Example**: Concrete Implementation (Infrastructure)

```python
# infrastructure/persistence/sqlalchemy/repositories/nutrition_repository.py
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from domain.nutrition.repository import NutritionRepository
from domain.nutrition.models import ConsumptionLog, DailyStats
from infrastructure.persistence.sqlalchemy.models import ConsumptionLogModel
from infrastructure.persistence.sqlalchemy.mappers.nutrition_mapper import ConsumptionLogMapper

class SQLAlchemyNutritionRepository(NutritionRepository):
    """
    SQLAlchemy implementation of NutritionRepository.

    Design Principle: Dependency Inversion
    - Implements domain interface
    - Contains all SQLAlchemy-specific logic
    - Converts between domain models and ORM models using mapper
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    async def save_consumption_log(self, log: ConsumptionLog) -> ConsumptionLog:
        """Save consumption log to PostgreSQL."""
        # Convert domain model to ORM model
        db_log = ConsumptionLogMapper.to_orm(log)

        self.db.add(db_log)
        await self.db.commit()
        await self.db.refresh(db_log)

        # Convert back to domain model
        return ConsumptionLogMapper.to_domain(db_log)

    async def get_consumption_log(self, log_id: str) -> Optional[ConsumptionLog]:
        """Get consumption log by ID."""
        db_log = await self.db.query(ConsumptionLogModel).filter(
            ConsumptionLogModel.id == log_id
        ).first()

        if not db_log:
            return None

        return ConsumptionLogMapper.to_domain(db_log)

    async def get_logs_for_date(self, user_id: str, date: date) -> List[ConsumptionLog]:
        """Get all logs for specific date."""
        db_logs = await self.db.query(ConsumptionLogModel).filter(
            ConsumptionLogModel.user_id == user_id,
            func.date(ConsumptionLogModel.consumed_at) == date
        ).order_by(ConsumptionLogModel.consumed_at).all()

        return [ConsumptionLogMapper.to_domain(db_log) for db_log in db_logs]

    async def get_logs_for_date_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> List[ConsumptionLog]:
        """Get logs within date range."""
        db_logs = await self.db.query(ConsumptionLogModel).filter(
            ConsumptionLogModel.user_id == user_id,
            func.date(ConsumptionLogModel.consumed_at) >= start_date,
            func.date(ConsumptionLogModel.consumed_at) <= end_date
        ).order_by(ConsumptionLogModel.consumed_at).all()

        return [ConsumptionLogMapper.to_domain(db_log) for db_log in db_logs]

    async def delete_consumption_log(self, log_id: str) -> None:
        """Delete consumption log."""
        await self.db.query(ConsumptionLogModel).filter(
            ConsumptionLogModel.id == log_id
        ).delete()
        await self.db.commit()

    async def get_daily_stats(self, user_id: str, date: date) -> DailyStats:
        """Calculate daily statistics by aggregating logs."""
        # Get all logs for the day
        logs = await self.get_logs_for_date(user_id, date)

        # Aggregate using database query for efficiency
        result = await self.db.query(
            func.sum(ConsumptionLogModel.calories).label('total_calories'),
            func.sum(ConsumptionLogModel.protein).label('total_protein'),
            func.sum(ConsumptionLogModel.carbs).label('total_carbs'),
            func.sum(ConsumptionLogModel.fats).label('total_fats'),
            func.count(ConsumptionLogModel.id).label('total_logs')
        ).filter(
            ConsumptionLogModel.user_id == user_id,
            func.date(ConsumptionLogModel.consumed_at) == date
        ).first()

        return DailyStats(
            user_id=user_id,
            date=date,
            total_calories=result.total_calories or 0.0,
            total_protein=result.total_protein or 0.0,
            total_carbs=result.total_carbs or 0.0,
            total_fats=result.total_fats or 0.0,
            total_logs=result.total_logs or 0
        )
```

---

### Dependencies

**Who will use repositories?**
1. **Use Cases**: Use cases will depend on repository interfaces
2. **Application Services**: Services orchestrate use cases (which use repositories)
3. **Tests**: Can mock repositories for unit tests

**Impact**:
- MEDIUM impact
- Must create repository interfaces for all domains
- Must migrate existing services to use repositories

---

### Impact Analysis

**Breaking Changes**:
1. Services no longer receive `Session` directly
2. Services depend on repository interfaces, not concrete implementations
3. All database queries move to repository implementations

**Migration Complexity**: MEDIUM
- Can migrate domain by domain
- Old services continue working during migration

---

### Migration Steps

#### Step 1: Create Repository Interfaces

Create repository interfaces for all domains:

```bash
# Create repository files
touch app/domain/user/repository.py
touch app/domain/nutrition/repository.py
touch app/domain/inventory/repository.py
touch app/domain/recipes/repository.py
touch app/domain/meal_planning/repository.py
touch app/domain/notifications/repository.py
```

#### Step 2: Create Concrete Implementations

```bash
# Create concrete repository implementations
mkdir -p app/infrastructure/persistence/sqlalchemy/repositories
touch app/infrastructure/persistence/sqlalchemy/repositories/user_repository.py
touch app/infrastructure/persistence/sqlalchemy/repositories/nutrition_repository.py
touch app/infrastructure/persistence/sqlalchemy/repositories/inventory_repository.py
touch app/infrastructure/persistence/sqlalchemy/repositories/recipe_repository.py
touch app/infrastructure/persistence/sqlalchemy/repositories/meal_plan_repository.py
touch app/infrastructure/persistence/sqlalchemy/repositories/notification_repository.py
```

#### Step 3: Create Mappers

```bash
# Create mappers (convert domain ↔ ORM)
mkdir -p app/infrastructure/persistence/sqlalchemy/mappers
touch app/infrastructure/persistence/sqlalchemy/mappers/user_mapper.py
touch app/infrastructure/persistence/sqlalchemy/mappers/nutrition_mapper.py
touch app/infrastructure/persistence/sqlalchemy/mappers/inventory_mapper.py
touch app/infrastructure/persistence/sqlalchemy/mappers/recipe_mapper.py
touch app/infrastructure/persistence/sqlalchemy/mappers/meal_plan_mapper.py
touch app/infrastructure/persistence/sqlalchemy/mappers/notification_mapper.py
```

#### Step 4: Implement One Repository (Example)

Start with smallest domain as proof of concept.

#### Step 5: Update Dependency Injection

Create FastAPI dependency that provides repositories:

```python
# core/dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session
from core.database import get_db
from domain.nutrition.repository import NutritionRepository
from infrastructure.persistence.sqlalchemy.repositories.nutrition_repository import SQLAlchemyNutritionRepository

def get_nutrition_repository(
    db: Session = Depends(get_db)
) -> NutritionRepository:
    """Provide NutritionRepository dependency."""
    return SQLAlchemyNutritionRepository(db)
```

#### Step 6: Validation

**Test 1**: Repository works correctly
```python
# Test repository
async def test_save_consumption_log():
    repo = SQLAlchemyNutritionRepository(db_session)

    log = ConsumptionLog(
        id=None,
        user_id="123",
        item_id="456",
        quantity=Quantity(100, 'g'),
        consumed_at=datetime.now()
    )

    saved_log = await repo.save_consumption_log(log)
    assert saved_log.id is not None
```

**Test 2**: Can mock repository for unit tests
```python
from unittest.mock import Mock

# Mock repository
mock_repo = Mock(spec=NutritionRepository)
mock_repo.save_consumption_log.return_value = ConsumptionLog(...)

# Test use case with mocked repository
use_case = LogConsumption(mock_repo)
result = await use_case.execute(log)
```

---

### Rollback Plan

If migration fails:
1. Keep old services working
2. Remove repository implementations
3. Continue using direct SQLAlchemy queries

---

## Component 3: Use Cases

### Current State

**Location**: Business logic scattered across services

**Structure**:
```python
# services/meal_plan_service.py
class MealPlanService:
    def __init__(self, db: Session):
        self.db = db

    # 20+ methods mixed together
    def create_meal_plan(self, ...): ...
    def optimize_meal_plan(self, ...): ...
    def get_meal_plan(self, ...): ...
    def update_meal_plan(self, ...): ...
    def delete_meal_plan(self, ...): ...
    def add_meal_to_plan(self, ...): ...
    def remove_meal_from_plan(self, ...): ...
    def generate_shopping_list(self, ...): ...
    # ... 500+ lines of code
```

**Problems**:
1. **God Classes**: Services do too much (violate SRP)
2. **Hard to Test**: Can't test individual operations in isolation
3. **Hard to Understand**: 500+ line files with mixed responsibilities
4. **Hard to Reuse**: Can't reuse single operation without entire service
5. **Unclear Dependencies**: What does each operation actually need?

---

### Design Principles Applied

1. **Single Responsibility Principle (SRP)**: One use case = one business operation
2. **Use Case Pattern**: Encapsulate single business operation
3. **Command Pattern**: Use case is like a command with `execute()` method
4. **Dependency Injection**: Use cases receive dependencies via constructor

---

### Target State

**New Structure**:
```
domain/
└── meal_planning/
    └── use_cases/
        ├── create_meal_plan.py
        ├── optimize_meal_plan.py
        ├── get_meal_plan.py
        ├── update_meal_plan.py
        ├── delete_meal_plan.py
        ├── add_meal_to_plan.py
        ├── remove_meal_from_plan.py
        └── generate_shopping_list.py
```

**Example**: Use Case Implementation

```python
# domain/meal_planning/use_cases/create_meal_plan.py
from dataclasses import dataclass
from datetime import date
from domain.meal_planning.models import MealPlan
from domain.meal_planning.repository import MealPlanRepository
from domain.meal_planning.exceptions import InvalidMealPlanError

@dataclass
class CreateMealPlanInput:
    """Input for CreateMealPlan use case."""
    user_id: str
    name: str
    start_date: date
    end_date: date

class CreateMealPlan:
    """
    Use Case: Create a new meal plan.

    Business Rules:
    1. Start date must be before end date
    2. End date must be at least 1 day after start
    3. User can only have one active meal plan at a time
    4. Date range can't overlap with existing active plans

    Design Principle: Single Responsibility
    - This class does ONE thing: create meal plan
    - All validation and business rules in one place
    - Easy to test, easy to understand
    """

    def __init__(self, meal_plan_repo: MealPlanRepository):
        """
        Constructor injection of dependencies.

        Args:
            meal_plan_repo: Repository interface (not concrete implementation)
        """
        self.meal_plan_repo = meal_plan_repo

    async def execute(self, input: CreateMealPlanInput) -> MealPlan:
        """
        Execute use case.

        Returns:
            Created meal plan

        Raises:
            InvalidMealPlanError: If validation fails
        """
        # Validate business rules
        self._validate_dates(input.start_date, input.end_date)

        # Check for overlapping active plans
        await self._check_no_overlapping_plans(input.user_id, input.start_date, input.end_date)

        # Create meal plan domain model
        meal_plan = MealPlan(
            id=None,  # Will be generated by repository
            user_id=input.user_id,
            name=input.name,
            start_date=input.start_date,
            end_date=input.end_date,
            is_active=True,
            created_at=datetime.now()
        )

        # Validate domain model
        meal_plan.validate()

        # Save via repository
        saved_plan = await self.meal_plan_repo.save(meal_plan)

        return saved_plan

    def _validate_dates(self, start: date, end: date) -> None:
        """Validate date range."""
        if start >= end:
            raise InvalidMealPlanError("Start date must be before end date")

        if (end - start).days < 1:
            raise InvalidMealPlanError("Meal plan must be at least 1 day long")

        if start < date.today():
            raise InvalidMealPlanError("Cannot create meal plan for past dates")

    async def _check_no_overlapping_plans(
        self,
        user_id: str,
        start: date,
        end: date
    ) -> None:
        """Check for overlapping active meal plans."""
        existing_plans = await self.meal_plan_repo.get_active_plans_in_range(
            user_id, start, end
        )

        if existing_plans:
            raise InvalidMealPlanError(
                f"You already have an active meal plan from "
                f"{existing_plans[0].start_date} to {existing_plans[0].end_date}"
            )
```

**Example**: Another Use Case

```python
# domain/nutrition/use_cases/log_consumption.py
from dataclasses import dataclass
from datetime import datetime
from domain.nutrition.models import ConsumptionLog
from domain.nutrition.repository import NutritionRepository
from domain.nutrition.value_objects import Quantity
from domain.inventory.repository import InventoryRepository
from domain.nutrition.exceptions import ItemNotFoundError

@dataclass
class LogConsumptionInput:
    """Input for LogConsumption use case."""
    user_id: str
    item_id: str
    quantity: float
    unit: str
    meal_type: str
    consumed_at: datetime

class LogConsumption:
    """
    Use Case: Log food consumption.

    Business Rules:
    1. Item must exist in user's inventory
    2. Quantity must be positive
    3. Macros calculated based on item nutrition
    4. Can't log future consumption

    Design Principle: Single Responsibility
    - This class does ONE thing: log consumption
    """

    def __init__(
        self,
        nutrition_repo: NutritionRepository,
        inventory_repo: InventoryRepository
    ):
        """Constructor injection of dependencies."""
        self.nutrition_repo = nutrition_repo
        self.inventory_repo = inventory_repo

    async def execute(self, input: LogConsumptionInput) -> ConsumptionLog:
        """Execute use case."""
        # Get item from inventory (validates item exists)
        item = await self.inventory_repo.get_item(input.item_id)
        if not item:
            raise ItemNotFoundError(f"Item {input.item_id} not found")

        # Create consumption log domain model
        log = ConsumptionLog(
            id=None,
            user_id=input.user_id,
            item_id=input.item_id,
            quantity=Quantity(input.quantity, input.unit),
            consumed_at=input.consumed_at,
            meal_type=input.meal_type
        )

        # Validate business rules
        log.validate()

        # Calculate macros
        item_nutrition = {
            'calories': item.calories,
            'protein': item.protein,
            'carbs': item.carbs,
            'fats': item.fats,
            'serving_size': item.serving_size
        }
        log.calculate_macros(item_nutrition)

        # Save via repository
        saved_log = await self.nutrition_repo.save_consumption_log(log)

        return saved_log
```

---

### Dependencies

**Who will use use cases?**
1. **Application Services**: Orchestrate multiple use cases
2. **API Handlers**: Can call use cases directly for simple operations
3. **Background Jobs**: Can execute use cases
4. **CLI Commands**: Can execute use cases

**Impact**:
- HIGH impact - this is where business logic lives
- Must extract logic from services into use cases
- Services become thin orchestration layer

---

### Impact Analysis

**Breaking Changes**:
1. Services no longer contain business logic
2. Business logic moves to use cases
3. Services orchestrate use cases

**Migration Complexity**: HIGH
- Need to extract logic from fat services
- Need to identify all business operations
- Need to define clear boundaries

---

### Migration Steps

#### Step 1: Identify All Use Cases

List all business operations across all domains:

**Nutrition Domain**:
- LogConsumption
- GetDailyStats
- GetWeeklyStats
- GetNutritionProgress
- UpdateConsumptionLog
- DeleteConsumptionLog

**Meal Planning Domain**:
- CreateMealPlan
- OptimizeMealPlan
- GetMealPlan
- UpdateMealPlan
- DeleteMealPlan
- AddMealToPlan
- RemoveMealFromPlan
- GenerateShoppingList

**Inventory Domain**:
- AddItem
- UpdateItem
- DeleteItem
- GetLowStockItems
- CheckExpiringSoon
- NormalizeItem

**Recipe Domain**:
- SearchRecipes
- GenerateRecipe
- SaveRecipe
- GetRecipe
- AddToFavorites

#### Step 2: Create Use Case Structure

```bash
# Create use case directories
mkdir -p app/domain/user/use_cases
mkdir -p app/domain/nutrition/use_cases
mkdir -p app/domain/inventory/use_cases
mkdir -p app/domain/recipes/use_cases
mkdir -p app/domain/meal_planning/use_cases
mkdir -p app/domain/notifications/use_cases
```

#### Step 3: Extract One Use Case (Example)

Start with simplest use case as proof of concept.

Extract `GetDailyStats` from `consumption_services.py`:

**Before**:
```python
# services/consumption_services.py
def get_daily_stats(db: Session, user_id: str, date: date):
    # 50 lines of mixed logic
    ...
```

**After**:
```python
# domain/nutrition/use_cases/get_daily_stats.py
class GetDailyStats:
    def __init__(self, repo: NutritionRepository):
        self.repo = repo

    async def execute(self, user_id: str, date: date) -> DailyStats:
        return await self.repo.get_daily_stats(user_id, date)
```

#### Step 4: Validation

**Test 1**: Use case works independently
```python
async def test_get_daily_stats():
    # Mock repository
    mock_repo = Mock(spec=NutritionRepository)
    mock_repo.get_daily_stats.return_value = DailyStats(...)

    # Test use case
    use_case = GetDailyStats(mock_repo)
    result = await use_case.execute("user123", date.today())

    assert result.total_calories == 2000
    mock_repo.get_daily_stats.assert_called_once()
```

**Test 2**: Use case validates business rules
```python
async def test_log_consumption_validates_quantity():
    repo = Mock()
    use_case = LogConsumption(repo, Mock())

    input = LogConsumptionInput(
        user_id="123",
        item_id="456",
        quantity=-10,  # Invalid!
        unit="g",
        meal_type="breakfast",
        consumed_at=datetime.now()
    )

    with pytest.raises(InvalidConsumptionLogError):
        await use_case.execute(input)
```

---

### Rollback Plan

If migration fails:
1. Keep old services working
2. Remove use case files
3. Continue using fat services

---

## Component 4: Application Services

### Current State

**Location**: `app/services/`

**Structure**:
```python
# services/meal_plan_service.py
class MealPlanService:
    # Fat service with mixed responsibilities
    def __init__(self, db: Session):
        self.db = db

    # Database queries
    # Business logic
    # External API calls
    # All mixed together
    def create_optimized_meal_plan(self, user_id: str, ...):
        # 200 lines of code doing everything
        ...
```

**Problems**:
1. **God Classes**: Services do everything
2. **Mixed Responsibilities**: Business logic + orchestration + data access
3. **Hard to Test**: Tightly coupled to database
4. **Hard to Understand**: 500+ line files

---

### Design Principles Applied

1. **Orchestration Layer**: Services orchestrate use cases, don't contain business logic
2. **Single Responsibility**: Services handle cross-domain workflows only
3. **Thin Services**: Minimal logic, delegate to use cases
4. **DTO Conversion**: Convert between API DTOs and domain models

---

### Target State

**New Structure**:
```
application/
└── services/
    ├── auth_service.py
    ├── nutrition_service.py
    ├── inventory_service.py
    ├── recipe_service.py
    ├── meal_plan_service.py
    └── notification_service.py
```

**Example**: Thin Application Service

```python
# application/services/meal_plan_service.py
from domain.meal_planning.use_cases.create_meal_plan import CreateMealPlan, CreateMealPlanInput
from domain.meal_planning.use_cases.optimize_meal_plan import OptimizeMealPlan
from domain.meal_planning.use_cases.generate_shopping_list import GenerateShoppingList
from domain.meal_planning.repository import MealPlanRepository
from domain.recipes.repository import RecipeRepository
from domain.inventory.repository import InventoryRepository

class MealPlanService:
    """
    Application service for meal planning.

    Design Principle: Orchestration Layer
    - Does NOT contain business logic
    - Orchestrates use cases
    - Handles cross-domain workflows
    - Converts DTOs ↔ Domain models

    Thin service (~100 lines instead of 500+)
    """

    def __init__(
        self,
        meal_plan_repo: MealPlanRepository,
        recipe_repo: RecipeRepository,
        inventory_repo: InventoryRepository
    ):
        # Initialize use cases
        self.create_meal_plan_uc = CreateMealPlan(meal_plan_repo)
        self.optimize_meal_plan_uc = OptimizeMealPlan(
            meal_plan_repo, recipe_repo, inventory_repo
        )
        self.generate_shopping_list_uc = GenerateShoppingList(
            meal_plan_repo, inventory_repo
        )

    async def create_and_optimize_meal_plan(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        preferences: dict
    ) -> dict:
        """
        Orchestrate multi-step workflow: create + optimize meal plan.

        This is a cross-domain workflow that requires:
        1. Create meal plan
        2. Optimize with recipes
        3. Generate shopping list

        Application service orchestrates, use cases execute.
        """
        # Step 1: Create meal plan (delegate to use case)
        create_input = CreateMealPlanInput(
            user_id=user_id,
            name=f"Meal Plan {start_date}",
            start_date=start_date,
            end_date=end_date
        )
        meal_plan = await self.create_meal_plan_uc.execute(create_input)

        # Step 2: Optimize meal plan (delegate to use case)
        optimized_plan = await self.optimize_meal_plan_uc.execute(
            meal_plan.id, preferences
        )

        # Step 3: Generate shopping list (delegate to use case)
        shopping_list = await self.generate_shopping_list_uc.execute(meal_plan.id)

        # Step 4: Return combined result (DTO conversion)
        return {
            'meal_plan': self._to_dto(optimized_plan),
            'shopping_list': self._shopping_list_to_dto(shopping_list)
        }

    async def create_meal_plan(self, user_id: str, ...) -> dict:
        """Simple operation - delegate to single use case."""
        input = CreateMealPlanInput(...)
        meal_plan = await self.create_meal_plan_uc.execute(input)
        return self._to_dto(meal_plan)

    def _to_dto(self, meal_plan: MealPlan) -> dict:
        """Convert domain model to DTO."""
        return {
            'id': meal_plan.id,
            'name': meal_plan.name,
            'start_date': meal_plan.start_date.isoformat(),
            'end_date': meal_plan.end_date.isoformat(),
            'is_active': meal_plan.is_active
        }
```

**Key Differences**:

| Before (Fat Service) | After (Thin Service) |
|---------------------|---------------------|
| 500+ lines | ~100 lines |
| Contains business logic | Orchestrates use cases |
| Mixed responsibilities | Single responsibility (orchestration) |
| Hard to test | Easy to test |
| Directly queries database | Uses repositories via use cases |

---

### Dependencies

**Who will use application services?**
1. **API Handlers**: Call services for operations
2. **Background Jobs**: Call services for scheduled tasks
3. **WebSocket Handlers**: Call services for real-time updates

**What do services depend on?**
1. **Use Cases**: Services orchestrate use cases
2. **Repositories**: Injected into use cases
3. **DTOs**: Convert between API and domain

**Impact**:
- MEDIUM impact
- Existing API handlers continue working
- Services become thinner, easier to maintain

---

### Migration Steps

#### Step 1: Create Application Service Structure

```bash
mkdir -p app/application/services
touch app/application/services/auth_service.py
touch app/application/services/nutrition_service.py
touch app/application/services/inventory_service.py
touch app/application/services/recipe_service.py
touch app/application/services/meal_plan_service.py
touch app/application/services/notification_service.py
```

#### Step 2: Extract One Service (Example)

Refactor `MealPlanService` to be thin orchestration layer.

#### Step 3: Update Dependency Injection

```python
# core/dependencies.py
from application.services.meal_plan_service import MealPlanService

def get_meal_plan_service(
    meal_plan_repo: MealPlanRepository = Depends(get_meal_plan_repository),
    recipe_repo: RecipeRepository = Depends(get_recipe_repository),
    inventory_repo: InventoryRepository = Depends(get_inventory_repository)
) -> MealPlanService:
    """Provide MealPlanService dependency."""
    return MealPlanService(meal_plan_repo, recipe_repo, inventory_repo)
```

#### Step 4: Validation

**Test 1**: Service orchestrates correctly
```python
async def test_create_and_optimize_meal_plan():
    # Mock repositories
    meal_plan_repo = Mock()
    recipe_repo = Mock()
    inventory_repo = Mock()

    # Create service
    service = MealPlanService(meal_plan_repo, recipe_repo, inventory_repo)

    # Execute
    result = await service.create_and_optimize_meal_plan(...)

    # Verify orchestration
    assert result['meal_plan']['id'] is not None
    assert result['shopping_list'] is not None
```

---

## Component 5: API Layer (Presentation)

### Current State

**Location**: `app/api/`

**Structure**:
```python
# api/meal_plan.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()

@router.post("/meal-plans")
async def create_meal_plan(
    request: CreateMealPlanRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    # Fat handler - contains business logic

    # Validate input
    if request.start_date >= request.end_date:
        raise HTTPException(400, "Invalid dates")

    # Check for overlaps (business logic!)
    existing = db.query(MealPlan).filter(...).first()
    if existing:
        raise HTTPException(400, "Overlapping meal plan")

    # Create meal plan (business logic!)
    meal_plan = MealPlan(
        user_id=user_id,
        name=request.name,
        start_date=request.start_date,
        end_date=request.end_date
    )

    # Optimize meal plan (business logic!)
    recipes = db.query(Recipe).filter(...).all()
    # ... 100 lines of optimization logic

    # Generate shopping list (business logic!)
    # ... 50 lines of shopping list logic

    db.add(meal_plan)
    db.commit()
    db.refresh(meal_plan)

    return meal_plan
```

**Problems**:
1. **Fat Handlers**: API handlers contain business logic
2. **Tight Coupling**: Directly use SQLAlchemy models
3. **Hard to Test**: Can't test business logic without HTTP
4. **Poor Separation**: HTTP concerns mixed with business logic
5. **No Reusability**: Logic can't be reused in CLI, background jobs, etc.

---

### Design Principles Applied

1. **Thin Controllers**: Handlers only handle HTTP concerns
2. **Dependency Injection**: Inject services, not database sessions
3. **Single Responsibility**: Handler = HTTP request/response only
4. **DTO Pattern**: Request/response schemas separate from domain models

---

### Target State

**New Structure**:
```
presentation/
├── api/
│   └── v1/
│       ├── auth.py
│       ├── users.py
│       ├── nutrition.py
│       ├── inventory.py
│       ├── recipes.py
│       ├── meal_plans.py
│       ├── notifications.py
│       ├── chat.py
│       └── websocket.py
│
└── schemas/
    ├── requests/
    │   ├── meal_plan_requests.py
    │   ├── nutrition_requests.py
    │   └── ...
    └── responses/
        ├── meal_plan_responses.py
        ├── nutrition_responses.py
        └── ...
```

**Example**: Thin API Handler

```python
# presentation/api/v1/meal_plans.py
from fastapi import APIRouter, Depends, HTTPException, status
from application.services.meal_plan_service import MealPlanService
from presentation.schemas.requests.meal_plan_requests import CreateMealPlanRequest
from presentation.schemas.responses.meal_plan_responses import MealPlanResponse
from core.dependencies import get_meal_plan_service, get_current_user_id

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])

@router.post(
    "",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new meal plan"
)
async def create_meal_plan(
    request: CreateMealPlanRequest,
    user_id: str = Depends(get_current_user_id),
    meal_plan_service: MealPlanService = Depends(get_meal_plan_service)
):
    """
    Create a new meal plan for the authenticated user.

    Thin handler - only HTTP concerns:
    1. Extract user_id from JWT
    2. Validate request (Pydantic does this automatically)
    3. Call service
    4. Handle domain exceptions → HTTP errors
    5. Return response

    NO business logic here!
    """
    try:
        # Delegate to service (all business logic there)
        meal_plan = await meal_plan_service.create_meal_plan(
            user_id=user_id,
            name=request.name,
            start_date=request.start_date,
            end_date=request.end_date
        )

        # Convert to response DTO
        return MealPlanResponse.from_dict(meal_plan)

    except InvalidMealPlanError as e:
        # Convert domain exception to HTTP error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error creating meal plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create meal plan"
        )


@router.get("/{meal_plan_id}", response_model=MealPlanResponse)
async def get_meal_plan(
    meal_plan_id: str,
    user_id: str = Depends(get_current_user_id),
    meal_plan_service: MealPlanService = Depends(get_meal_plan_service)
):
    """Get meal plan by ID."""
    try:
        meal_plan = await meal_plan_service.get_meal_plan(meal_plan_id, user_id)

        if not meal_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal plan {meal_plan_id} not found"
            )

        return MealPlanResponse.from_dict(meal_plan)

    except Exception as e:
        logger.error(f"Error getting meal plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get meal plan"
        )


@router.post("/optimized", response_model=dict)
async def create_and_optimize_meal_plan(
    request: CreateOptimizedMealPlanRequest,
    user_id: str = Depends(get_current_user_id),
    meal_plan_service: MealPlanService = Depends(get_meal_plan_service)
):
    """
    Create and optimize meal plan (complex workflow).

    Handler is still thin - delegates complex workflow to service.
    """
    try:
        result = await meal_plan_service.create_and_optimize_meal_plan(
            user_id=user_id,
            start_date=request.start_date,
            end_date=request.end_date,
            preferences=request.preferences
        )

        return result

    except InvalidMealPlanError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

**Example**: Request/Response Schemas

```python
# presentation/schemas/requests/meal_plan_requests.py
from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional

class CreateMealPlanRequest(BaseModel):
    """
    Request schema for creating meal plan.

    Design Principle: DTO (Data Transfer Object)
    - Separate from domain models
    - HTTP validation concerns (Pydantic)
    - Can evolve independently from domain
    """
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: date = Field(..., description="End date (YYYY-MM-DD)")

    @validator('end_date')
    def end_date_after_start(cls, v, values):
        """Validate end date is after start date."""
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "My Meal Plan",
                "start_date": "2025-11-25",
                "end_date": "2025-12-01"
            }
        }


class CreateOptimizedMealPlanRequest(BaseModel):
    """Request for creating optimized meal plan."""
    start_date: date
    end_date: date
    preferences: dict = Field(default_factory=dict)


# presentation/schemas/responses/meal_plan_responses.py
from pydantic import BaseModel
from datetime import date
from typing import Optional

class MealPlanResponse(BaseModel):
    """
    Response schema for meal plan.

    Design Principle: DTO
    - Expose only what API consumers need
    - Hide internal implementation details
    - Versioned (can change without breaking domain)
    """
    id: str
    user_id: str
    name: str
    start_date: date
    end_date: date
    is_active: bool
    created_at: str  # ISO format

    @classmethod
    def from_dict(cls, data: dict) -> 'MealPlanResponse':
        """Convert service DTO to response schema."""
        return cls(**data)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user123",
                "name": "My Meal Plan",
                "start_date": "2025-11-25",
                "end_date": "2025-12-01",
                "is_active": True,
                "created_at": "2025-11-24T10:00:00Z"
            }
        }
```

**Key Differences**:

| Before (Fat Handler) | After (Thin Handler) |
|---------------------|---------------------|
| 300+ lines per endpoint | ~30 lines per endpoint |
| Contains business logic | Only HTTP concerns |
| Directly queries database | Calls services |
| Hard to test | Easy to test |
| Can't reuse logic | Logic in services (reusable) |

---

### Dependencies

**Who will use API handlers?**
1. **HTTP clients**: Frontend, mobile apps, external APIs

**What do handlers depend on?**
1. **Application Services**: Delegate all business operations
2. **Request/Response Schemas**: Pydantic models for validation
3. **Dependencies**: Auth, pagination, etc.

**Impact**:
- MEDIUM impact
- Existing endpoints continue working
- Handlers become thinner

---

### Impact Analysis

**Breaking Changes**:
1. Import paths change (if external clients import from API modules)
2. Response formats might change (if we improve DTOs)

**Migration Complexity**: MEDIUM
- Can migrate endpoint by endpoint
- Old endpoints continue working during migration

---

### Migration Steps

#### Step 1: Create Presentation Layer Structure

```bash
# Create directories
mkdir -p app/presentation/api/v1
mkdir -p app/presentation/schemas/requests
mkdir -p app/presentation/schemas/responses

# Move existing routers to v1
# (Keep old ones in app/api/ for backwards compatibility during migration)
```

#### Step 2: Create Request/Response Schemas

```bash
# Create schema files
touch app/presentation/schemas/requests/meal_plan_requests.py
touch app/presentation/schemas/requests/nutrition_requests.py
touch app/presentation/schemas/responses/meal_plan_responses.py
touch app/presentation/schemas/responses/nutrition_responses.py
```

#### Step 3: Refactor One Endpoint (Example)

**Before**:
```python
# api/meal_plan.py
@router.post("/meal-plans")
async def create_meal_plan(request: dict, db: Session = Depends(get_db)):
    # 100 lines of business logic
    ...
```

**After**:
```python
# presentation/api/v1/meal_plans.py
@router.post("")
async def create_meal_plan(
    request: CreateMealPlanRequest,
    service: MealPlanService = Depends(get_meal_plan_service)
):
    # 20 lines - only HTTP concerns
    meal_plan = await service.create_meal_plan(...)
    return MealPlanResponse.from_dict(meal_plan)
```

#### Step 4: Update main.py

```python
# main.py
from presentation.api.v1 import (
    meal_plans as meal_plans_v1,
    nutrition as nutrition_v1,
    ...
)

# Include v1 routers
app.include_router(meal_plans_v1.router, prefix="/api/v1")
app.include_router(nutrition_v1.router, prefix="/api/v1")

# Keep old routers for backwards compatibility
app.include_router(meal_plan.router, prefix="/api")  # deprecated
```

#### Step 5: Validation

**Test 1**: Endpoint works correctly
```python
from fastapi.testclient import TestClient

def test_create_meal_plan():
    client = TestClient(app)

    response = client.post(
        "/api/v1/meal-plans",
        json={
            "name": "Test Plan",
            "start_date": "2025-11-25",
            "end_date": "2025-12-01"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Test Plan"
```

**Test 2**: Validation works
```python
def test_create_meal_plan_invalid_dates():
    response = client.post(
        "/api/v1/meal-plans",
        json={
            "name": "Test",
            "start_date": "2025-12-01",
            "end_date": "2025-11-25"  # Invalid - before start
        }
    )

    assert response.status_code == 422  # Validation error
```

---

### Rollback Plan

If migration fails:
1. Keep old `/api/` endpoints
2. Remove new `/api/v1/` endpoints
3. Continue using fat handlers

---

## Component 6: LangGraph AI Agent

### Current State

**Location**: `app/agents/nutrition_graph.py`

**Structure**:
```python
# nutrition_graph.py - 845 LINES!
# Everything in one giant file:
# - State definition
# - Node implementations (5 nodes)
# - Tool implementations (7 tools)
# - System prompts (multiple prompts)
# - Graph structure
# - Routing logic
```

**Problems**:
1. **Giant File**: 845 lines - impossible to navigate
2. **Mixed Concerns**: Graph structure + nodes + tools + prompts all mixed
3. **Hard to Test**: Can't test nodes or tools independently
4. **Hard to Understand**: What does this file do? Everything!
5. **Hard to Modify**: Changes require scrolling through entire file

---

### Design Principles Applied

1. **Single Responsibility**: One file = one concern
2. **Separation of Concerns**: Graph structure ≠ node implementation ≠ tool implementation
3. **Modularity**: Each node/tool in separate file
4. **Testability**: Each component independently testable

---

### Target State

**New Structure**:
```
infrastructure/
└── ai/
    └── langgraph/
        ├── graph_instance.py        # Singleton (unchanged)
        ├── graph_builder.py          # NEW: Graph structure only
        ├── state.py                  # NEW: State definition
        │
        ├── nodes/                    # NEW: Node implementations
        │   ├── __init__.py
        │   ├── load_context_node.py
        │   ├── classify_intent_node.py
        │   ├── trim_messages_node.py
        │   ├── generate_response_node.py
        │   └── routing.py            # Conditional routing logic
        │
        ├── tools/                    # NEW: Tool implementations
        │   ├── __init__.py
        │   ├── get_nutrition_stats.py
        │   ├── simulate_food_addition.py
        │   ├── suggest_meals.py
        │   ├── get_meal_plan.py
        │   ├── check_inventory.py
        │   ├── search_recipes.py
        │   └── get_makeable_recipes.py
        │
        └── prompts/                  # NEW: Prompt templates
            ├── system_prompt.py
            └── intent_classifier_prompt.py
```

**Example**: State Definition (Separate File)

```python
# infrastructure/ai/langgraph/state.py
from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any
import operator
from langchain_core.messages import BaseMessage

class NutritionState(TypedDict):
    """
    LangGraph state for nutrition chatbot.

    Design Principle: Separation of Concerns
    - State definition in separate file
    - Clear documentation of each field
    - Type hints for better IDE support
    """
    # Messages (automatically appended)
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Trimmed messages for LLM (not persisted)
    llm_input_messages: Optional[Sequence[BaseMessage]]

    # User context (minimal - refreshed each turn)
    user_context: Dict[str, Any]

    # Intent classification
    intent: Optional[str]
    confidence: float
    entities: Dict[str, Any]

    # Session tracking
    session_id: Optional[str]
```

**Example**: Node Implementation (Separate File)

```python
# infrastructure/ai/langgraph/nodes/load_context_node.py
from typing import Dict, Any
from infrastructure.ai.langgraph.state import NutritionState
from app.agents.nutrition_context import load_minimal_user_context
import logging

logger = logging.getLogger(__name__)

async def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node 1: Load minimal user context.

    Design Principle: Single Responsibility
    - This node does ONE thing: load context
    - ~50 lines instead of part of 845-line file
    - Easy to test independently
    - Easy to understand

    Returns:
        Dict with user_context
    """
    # Extract user_id from latest human message
    messages = state.get("messages", [])
    user_message = next(
        (msg for msg in reversed(messages) if isinstance(msg, HumanMessage)),
        None
    )

    if not user_message:
        logger.warning("[load_context_node] No user message found")
        return {"user_context": {}}

    # Extract user_id from metadata
    user_id = user_message.additional_kwargs.get("user_id")
    if not user_id:
        logger.error("[load_context_node] No user_id in message metadata")
        return {"user_context": {}}

    # Load minimal context
    try:
        context = await load_minimal_user_context(user_id)
        logger.info(f"[load_context_node] Loaded context for user {user_id}")
        return {"user_context": context}
    except Exception as e:
        logger.error(f"[load_context_node] Error: {e}")
        return {"user_context": {}}
```

**Example**: Tool Implementation (Separate File)

```python
# infrastructure/ai/langgraph/tools/get_nutrition_stats.py
from langchain_core.tools import tool
from datetime import date
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@tool
async def get_nutrition_stats(
    user_id: str,
    date_str: Optional[str] = None
) -> dict:
    """
    Get nutrition statistics for a specific date.

    Design Principle: Single Responsibility
    - This tool does ONE thing: get nutrition stats
    - ~100 lines instead of part of 845-line file
    - Easy to test independently
    - Clear, focused implementation

    Args:
        user_id: User ID
        date_str: Date (YYYY-MM-DD) or None for today

    Returns:
        Dict with nutrition statistics
    """
    try:
        # Parse date
        if date_str:
            target_date = date.fromisoformat(date_str)
        else:
            target_date = date.today()

        logger.info(f"[get_nutrition_stats] User {user_id}, date {target_date}")

        # Create own DB session (stateless tool)
        from app.core.database import SessionLocal
        from domain.nutrition.use_cases.get_daily_stats import GetDailyStats
        from infrastructure.persistence.sqlalchemy.repositories.nutrition_repository import SQLAlchemyNutritionRepository

        db = SessionLocal()
        try:
            # Use domain layer (not direct queries!)
            repo = SQLAlchemyNutritionRepository(db)
            use_case = GetDailyStats(repo)

            stats = await use_case.execute(user_id, target_date)

            return {
                "date": str(target_date),
                "total_calories": stats.total_calories,
                "total_protein": stats.total_protein,
                "total_carbs": stats.total_carbs,
                "total_fats": stats.total_fats,
                "total_logs": stats.total_logs
            }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"[get_nutrition_stats] Error: {e}")
        return {"error": str(e)}
```

**Example**: Graph Builder (Separate File)

```python
# infrastructure/ai/langgraph/graph_builder.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from infrastructure.ai.langgraph.state import NutritionState
from infrastructure.ai.langgraph.nodes.load_context_node import load_context_node
from infrastructure.ai.langgraph.nodes.classify_intent_node import classify_intent_node
from infrastructure.ai.langgraph.nodes.trim_messages_node import trim_messages_node
from infrastructure.ai.langgraph.nodes.generate_response_node import generate_response_node
from infrastructure.ai.langgraph.nodes.routing import should_use_tools
from infrastructure.ai.langgraph.tools import create_nutrition_tools_v2
import logging

logger = logging.getLogger(__name__)

def create_nutrition_graph_structure() -> StateGraph:
    """
    Create LangGraph structure for nutrition chatbot.

    Design Principle: Separation of Concerns
    - This file ONLY defines graph structure
    - Nodes implemented in separate files
    - Tools implemented in separate files
    - ~50 lines instead of 845 lines
    - Easy to visualize graph flow

    Returns:
        StateGraph (not compiled)
    """
    # Create tools
    tools = create_nutrition_tools_v2()

    # Create graph
    workflow = StateGraph(NutritionState)

    # Add nodes (all stateless)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("trim_messages", trim_messages_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("tools", ToolNode(tools))

    # Define flow
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "classify_intent")
    workflow.add_edge("classify_intent", "trim_messages")
    workflow.add_edge("trim_messages", "generate_response")

    # Conditional edge: tools or end
    workflow.add_conditional_edges(
        "generate_response",
        should_use_tools,
        {
            "tools": "tools",
            "end": END
        }
    )

    # After tools, loop back to trim_messages
    workflow.add_edge("tools", "trim_messages")

    logger.info("[GraphBuilder] Graph structure created")

    return workflow
```

**Example**: Prompts (Separate File)

```python
# infrastructure/ai/langgraph/prompts/system_prompt.py

def build_system_prompt(context: dict, session_id: str) -> str:
    """
    Build minimal system prompt for nutrition chatbot.

    Design Principle: Separation of Concerns
    - Prompts in separate file
    - Easy to modify without touching graph logic
    - Easy to A/B test different prompts
    - Easy to version control prompt changes

    Args:
        context: User context dict
        session_id: Session ID

    Returns:
        System prompt string
    """
    return f"""You are a nutrition AI assistant. Today is {context['current_date']} at {context['current_time']}.

User {context['user_id']} | Goal: {context['goal_type']} | Activity: {context['activity_level']}
{f"Restrictions: {', '.join(context['dietary_restrictions'])}" if context['dietary_restrictions'] else ""}

Use available tools to fetch current data when needed. Always pass user_id={context['user_id']}.
Be helpful and conversational.

Session: {session_id}
"""
```

**Key Differences**:

| Before (Monolith) | After (Modular) |
|------------------|-----------------|
| 1 file, 845 lines | 15+ files, ~50 lines each |
| Everything mixed | Clear separation |
| Hard to test | Easy to test |
| Hard to navigate | Easy to find code |
| Hard to modify | Easy to modify |

---

### Dependencies

**Who depends on LangGraph?**
1. **nutrition_chat.py**: API endpoint calls compiled graph
2. **graph_instance.py**: Compiles graph at startup

**Impact**:
- LOW impact
- graph_instance.py continues working (just imports from new location)
- API endpoint unchanged

---

### Impact Analysis

**Breaking Changes**:
- Import paths change (internal only)
- No external API changes

**Migration Complexity**: LOW
- Can split file incrementally
- Old file continues working during migration

---

### Migration Steps

#### Step 1: Create Module Structure

```bash
# Create directories
mkdir -p app/infrastructure/ai/langgraph/nodes
mkdir -p app/infrastructure/ai/langgraph/tools
mkdir -p app/infrastructure/ai/langgraph/prompts

# Create __init__.py files
touch app/infrastructure/ai/langgraph/nodes/__init__.py
touch app/infrastructure/ai/langgraph/tools/__init__.py
touch app/infrastructure/ai/langgraph/prompts/__init__.py
```

#### Step 2: Extract State Definition

```bash
# Create state.py
touch app/infrastructure/ai/langgraph/state.py
```

Copy `NutritionState` from `nutrition_graph.py` to `state.py`.

#### Step 3: Extract Nodes (One by One)

```bash
# Extract each node to separate file
touch app/infrastructure/ai/langgraph/nodes/load_context_node.py
touch app/infrastructure/ai/langgraph/nodes/classify_intent_node.py
touch app/infrastructure/ai/langgraph/nodes/trim_messages_node.py
touch app/infrastructure/ai/langgraph/nodes/generate_response_node.py
touch app/infrastructure/ai/langgraph/nodes/routing.py
```

#### Step 4: Extract Tools (One by One)

```bash
# Extract each tool to separate file
touch app/infrastructure/ai/langgraph/tools/get_nutrition_stats.py
touch app/infrastructure/ai/langgraph/tools/simulate_food_addition.py
touch app/infrastructure/ai/langgraph/tools/suggest_meals.py
touch app/infrastructure/ai/langgraph/tools/get_meal_plan.py
touch app/infrastructure/ai/langgraph/tools/check_inventory.py
touch app/infrastructure/ai/langgraph/tools/search_recipes.py
touch app/infrastructure/ai/langgraph/tools/get_makeable_recipes.py
```

#### Step 5: Extract Prompts

```bash
# Extract prompts
touch app/infrastructure/ai/langgraph/prompts/system_prompt.py
touch app/infrastructure/ai/langgraph/prompts/intent_classifier_prompt.py
```

#### Step 6: Create Graph Builder

```bash
# Create graph builder
touch app/infrastructure/ai/langgraph/graph_builder.py
```

#### Step 7: Update graph_instance.py

```python
# graph_instance.py (update import)
# OLD:
from app.agents.nutrition_graph import create_nutrition_graph_structure

# NEW:
from app.infrastructure.ai.langgraph.graph_builder import create_nutrition_graph_structure
```

#### Step 8: Validation

**Test 1**: Graph compiles successfully
```python
from infrastructure.ai.langgraph.graph_builder import create_nutrition_graph_structure

workflow = create_nutrition_graph_structure()
compiled_graph = workflow.compile()

# Should compile without errors
assert compiled_graph is not None
```

**Test 2**: Individual nodes work
```python
from infrastructure.ai.langgraph.nodes.load_context_node import load_context_node

# Test node independently
state = {"messages": [...]}
result = await load_context_node(state)

assert "user_context" in result
```

**Test 3**: Individual tools work
```python
from infrastructure.ai.langgraph.tools.get_nutrition_stats import get_nutrition_stats

# Test tool independently
result = await get_nutrition_stats(user_id="123", date_str="2025-11-24")

assert "total_calories" in result
```

---

### Rollback Plan

If migration fails:
1. Keep old `nutrition_graph.py`
2. Remove new modular structure
3. Revert `graph_instance.py` import

---

## Component 7: External Services

### Current State

**Location**: `app/services/` (mixed with business services)

**Structure**:
```python
# services/llm_client.py
# services/llm_recipe_generator.py
# services/llm_nutrition_estimator.py
# services/item_normalizer_rag.py
# services/embedding_service.py
# services/fdc_service.py
```

**Problems**:
1. **Mixed Location**: External services mixed with business services
2. **No Clear Boundary**: Hard to tell which services are internal vs external
3. **Tight Coupling**: Business logic directly calls external APIs
4. **Hard to Mock**: Can't easily mock external services for testing
5. **No Fallback**: If external API fails, entire operation fails

---

### Design Principles Applied

1. **Port/Adapter Pattern**: Abstract external services behind interface
2. **Dependency Inversion**: Business logic depends on interface, not concrete API
3. **Separation of Concerns**: External services in infrastructure layer
4. **Circuit Breaker**: Handle failures gracefully

---

### Target State

**New Structure**:
```
infrastructure/
└── external_services/
    ├── openai/
    │   ├── client.py
    │   ├── chat_service.py
    │   ├── embedding_service.py
    │   └── recipe_generator.py
    │
    ├── fdc/
    │   ├── client.py
    │   └── nutrition_lookup.py
    │
    └── receipt_scanner/
        ├── client.py
        └── processor.py
```

**Example**: OpenAI Service

```python
# infrastructure/external_services/openai/client.py
from openai import AsyncOpenAI
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class OpenAIClient:
    """
    OpenAI API client wrapper.

    Design Principle: Port/Adapter
    - Wraps external API
    - Handles authentication
    - Handles retries and errors
    - Can be mocked for testing
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def chat_completion(
        self,
        messages: list,
        model: str = "gpt-4",
        temperature: float = 0.7,
        **kwargs
    ) -> dict:
        """Call chat completion API with error handling."""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                **kwargs
            )
            return response.model_dump()
        except Exception as e:
            logger.error(f"[OpenAI] Chat completion failed: {e}")
            raise

    async def create_embedding(self, text: str, model: str = "text-embedding-3-small") -> list:
        """Create embedding vector."""
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"[OpenAI] Embedding failed: {e}")
            raise
```

---

### Migration Steps

#### Step 1: Create Structure

```bash
mkdir -p app/infrastructure/external_services/openai
mkdir -p app/infrastructure/external_services/fdc
mkdir -p app/infrastructure/external_services/receipt_scanner
```

#### Step 2: Move External Services

Move and refactor external service files.

---

## Component 8: Infrastructure (Database, Cache, Messaging)

### Current State

**Location**: Scattered across `app/core/` and `app/services/`

**Structure**:
```
app/core/
├── database.py (SQLAlchemy setup)
├── mongodb.py (MongoDB setup)
└── config.py (Settings)

app/services/
├── websocket_manager.py (WebSocket + Redis)
└── notification_scheduler.py (Background jobs)
```

**Problems**:
1. **Mixed Concerns**: Infrastructure mixed with business code
2. **No Clear Organization**: Hard to find infrastructure code
3. **Tight Coupling**: Business code directly uses infrastructure

---

### Design Principles Applied

1. **Infrastructure Layer**: All infrastructure in one place
2. **Configuration Management**: Centralized settings
3. **Dependency Injection**: Infrastructure injected into business code

---

### Target State

**New Structure**:
```
infrastructure/
├── persistence/
│   ├── sqlalchemy/
│   │   ├── models.py
│   │   ├── session.py
│   │   ├── repositories/
│   │   └── mappers/
│   │
│   └── mongodb/
│       ├── client.py
│       └── collections.py
│
├── messaging/
│   ├── websocket_manager.py
│   └── redis_pubsub.py
│
└── caching/
    └── redis_cache.py
```

---

## 5. Migration Timeline

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create domain model structure
- [ ] Create repository interfaces
- [ ] Create concrete repository implementations
- [ ] Create mappers
- [ ] Validate with unit tests

### Phase 2: Use Cases (Weeks 3-4)
- [ ] Identify all use cases
- [ ] Extract use cases from services
- [ ] Write unit tests for use cases
- [ ] Validate business logic

### Phase 3: Application Services (Week 5)
- [ ] Create thin application services
- [ ] Refactor existing services
- [ ] Update dependency injection

### Phase 4: API Layer (Week 6)
- [ ] Refactor API handlers to be thin
- [ ] Update request/response schemas
- [ ] Integration tests

### Phase 5: LangGraph (Week 7)
- [ ] Split nutrition_graph.py into smaller files
- [ ] Extract nodes to separate files
- [ ] Extract tools to separate files
- [ ] Extract prompts

### Phase 6: Cleanup & Documentation (Week 8)
- [ ] Remove old code
- [ ] Update documentation
- [ ] Final testing
- [ ] Deploy to staging
