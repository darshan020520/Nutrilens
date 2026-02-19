# tests/conftest.py
"""
Pytest configuration and fixtures for NutriLens AI tests
Provides reusable test fixtures for database, users, meals, etc.
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import redis
from fastapi.testclient import TestClient

from app.models.database import Base, User, UserProfile, UserGoal, UserPath
from app.models.database import Recipe, Item, RecipeIngredient, MealPlan, MealLog
from app.models.database import UserInventory, NotificationPreference
from app.main import app
from app.services.auth import create_access_token, get_password_hash
from app.core.config import settings

# ===== DATABASE FIXTURES =====

@pytest.fixture(scope="function")
def test_db():
    """
    Provide a clean test database for each test
    Uses in-memory SQLite for speed
    """
    # Create in-memory database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create session
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Alias for test_db for clearer test code"""
    return test_db


# ===== USER FIXTURES =====

@pytest.fixture
def test_user(test_db: Session):
    """Create a basic test user"""
    user = User(
        email="testuser@nutrilens.ai",
        hashed_password=get_password_hash("TestPass123"),
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_user_with_profile(test_db: Session, test_user: User):
    """Create a test user with complete profile"""
    profile = UserProfile(
        user_id=test_user.id,
        name="Test User",
        age=30,
        height_cm=175,
        weight_kg=75,
        sex="male",
        activity_level="moderately_active",
        bmr=1750,
        tdee=2500,
        goal_calories=2200,
        medical_conditions=[]
    )
    test_db.add(profile)
    
    # Add goal
    goal = UserGoal(
        user_id=test_user.id,
        goal_type="muscle_gain",
        target_weight=80,
        target_date=datetime.utcnow() + timedelta(days=90),
        macro_targets={"protein": 0.35, "carbs": 0.45, "fat": 0.20}
    )
    test_db.add(goal)
    
    # Add path
    path = UserPath(
        user_id=test_user.id,
        path_type="traditional",
        meals_per_day=3,
        meal_windows=[
            {"meal": "breakfast", "start_time": "07:00", "end_time": "09:00"},
            {"meal": "lunch", "start_time": "12:00", "end_time": "14:00"},
            {"meal": "dinner", "start_time": "18:00", "end_time": "20:00"}
        ]
    )
    test_db.add(path)
    
    # Add notification preferences
    notification_prefs = NotificationPreference(
        user_id=test_user.id,
        enabled_providers=["email"],
        enabled_types=["achievement", "meal_reminder"],
        quiet_hours_start=22,
        quiet_hours_end=7
    )
    test_db.add(notification_prefs)
    
    test_db.commit()
    test_db.refresh(test_user)
    return test_user


@pytest.fixture
def second_test_user(test_db: Session):
    """Create a second test user for multi-user tests"""
    user = User(
        email="testuser2@nutrilens.ai",
        hashed_password=get_password_hash("TestPass123"),
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ===== RECIPE & ITEM FIXTURES =====

@pytest.fixture
def test_items(test_db: Session):
    """Create test food items"""
    items = [
        Item(
            canonical_name="chicken breast",
            category="protein",
            default_unit="g",
            calories_per_100g=165,
            protein_per_100g=31,
            carbs_per_100g=0,
            fat_per_100g=3.6
        ),
        Item(
            canonical_name="brown rice",
            category="grains",
            default_unit="g",
            calories_per_100g=111,
            protein_per_100g=2.6,
            carbs_per_100g=23,
            fat_per_100g=0.9
        ),
        Item(
            canonical_name="broccoli",
            category="vegetables",
            default_unit="g",
            calories_per_100g=34,
            protein_per_100g=2.8,
            carbs_per_100g=7,
            fat_per_100g=0.4
        ),
        Item(
            canonical_name="olive oil",
            category="fats",
            default_unit="ml",
            calories_per_100g=884,
            protein_per_100g=0,
            carbs_per_100g=0,
            fat_per_100g=100
        )
    ]
    
    for item in items:
        test_db.add(item)
    
    test_db.commit()
    
    # Refresh all items
    for item in items:
        test_db.refresh(item)
    
    return {item.canonical_name: item for item in items}


@pytest.fixture
def test_recipe(test_db: Session, test_items: dict):
    """Create a test recipe with ingredients"""
    recipe = Recipe(
        title="Chicken and Rice Bowl",
        description="Healthy protein bowl",
        goals=["muscle_gain", "general_health"],
        tags=["high_protein", "balanced"],
        dietary_tags=["non_vegetarian"],
        suitable_meal_times=["lunch", "dinner"],
        cuisine="international",
        prep_time_min=15,
        cook_time_min=25,
        difficulty_level="easy",
        servings=1,
        macros_per_serving={
            "calories": 450,
            "protein_g": 40,
            "carbs_g": 50,
            "fat_g": 8
        },
        instructions=["Cook rice", "Grill chicken", "Steam broccoli", "Combine"],
        chef_tips="Season chicken well"
    )
    test_db.add(recipe)
    test_db.commit()
    test_db.refresh(recipe)
    
    # Add ingredients
    ingredients = [
        RecipeIngredient(
            recipe_id=recipe.id,
            item_id=test_items["chicken breast"].id,
            quantity_grams=150,
            is_optional=False
        ),
        RecipeIngredient(
            recipe_id=recipe.id,
            item_id=test_items["brown rice"].id,
            quantity_grams=200,
            is_optional=False
        ),
        RecipeIngredient(
            recipe_id=recipe.id,
            item_id=test_items["broccoli"].id,
            quantity_grams=100,
            is_optional=False
        ),
        RecipeIngredient(
            recipe_id=recipe.id,
            item_id=test_items["olive oil"].id,
            quantity_grams=10,
            is_optional=False
        )
    ]
    
    for ingredient in ingredients:
        test_db.add(ingredient)
    
    test_db.commit()
    
    # Refresh recipe with ingredients
    test_db.refresh(recipe)
    
    return recipe


# ===== MEAL PLAN FIXTURES =====

@pytest.fixture
def test_meal_plan(test_db: Session, test_user_with_profile: User, test_recipe: Recipe):
    """Create a test meal plan with meal logs"""
    today = datetime.utcnow()
    week_start = today - timedelta(days=today.weekday())
    
    # Create meal plan
    meal_plan = MealPlan(
        user_id=test_user_with_profile.id,
        week_start_date=week_start,
        plan_data={
            "week_plan": {
                "day_0": {
                    "meals": [
                        {"meal_type": "breakfast", "recipe_id": test_recipe.id},
                        {"meal_type": "lunch", "recipe_id": test_recipe.id},
                        {"meal_type": "dinner", "recipe_id": test_recipe.id}
                    ]
                }
            }
        },
        grocery_list={},
        total_calories=1350,
        avg_macros={"protein_g": 120, "carbs_g": 150, "fat_g": 24},
        is_active=True
    )
    test_db.add(meal_plan)
    test_db.commit()
    test_db.refresh(meal_plan)
    
    # Create meal logs for today
    meal_types = ["breakfast", "lunch", "dinner"]
    meal_times = [
        today.replace(hour=8, minute=0, second=0, microsecond=0),
        today.replace(hour=13, minute=0, second=0, microsecond=0),
        today.replace(hour=19, minute=0, second=0, microsecond=0)
    ]
    
    meal_logs = []
    for meal_type, meal_time in zip(meal_types, meal_times):
        meal_log = MealLog(
            user_id=test_user_with_profile.id,
            recipe_id=test_recipe.id,
            meal_type=meal_type,
            planned_datetime=meal_time,
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        test_db.add(meal_log)
        meal_logs.append(meal_log)
    
    test_db.commit()
    
    # Refresh all
    for log in meal_logs:
        test_db.refresh(log)
    
    return {
        "meal_plan": meal_plan,
        "meal_logs": meal_logs
    }


@pytest.fixture
def consumed_meal_log(test_db: Session, test_meal_plan: dict):
    """Create a meal log that's already been consumed"""
    meal_log = test_meal_plan["meal_logs"][0]
    meal_log.consumed_datetime = datetime.utcnow()
    test_db.commit()
    test_db.refresh(meal_log)
    return meal_log


@pytest.fixture
def skipped_meal_log(test_db: Session, test_meal_plan: dict):
    """Create a meal log that's been skipped"""
    meal_log = test_meal_plan["meal_logs"][1]
    meal_log.was_skipped = True
    meal_log.skip_reason = "Not hungry"
    test_db.commit()
    test_db.refresh(meal_log)
    return meal_log


# ===== INVENTORY FIXTURES =====

@pytest.fixture
def test_inventory(test_db: Session, test_user_with_profile: User, test_items: dict):
    """Create test inventory for user"""
    today = datetime.utcnow()
    
    inventory_items = [
        UserInventory(
            user_id=test_user_with_profile.id,
            item_id=test_items["chicken breast"].id,
            quantity_grams=500,
            purchase_date=today,
            expiry_date=today + timedelta(days=3),
            source="manual"
        ),
        UserInventory(
            user_id=test_user_with_profile.id,
            item_id=test_items["brown rice"].id,
            quantity_grams=1000,
            purchase_date=today,
            expiry_date=today + timedelta(days=30),
            source="manual"
        ),
        UserInventory(
            user_id=test_user_with_profile.id,
            item_id=test_items["broccoli"].id,
            quantity_grams=200,
            purchase_date=today,
            expiry_date=today + timedelta(days=1),  # Expiring soon!
            source="manual"
        )
    ]
    
    for item in inventory_items:
        test_db.add(item)
    
    test_db.commit()
    
    for item in inventory_items:
        test_db.refresh(item)
    
    return inventory_items


# ===== AUTHENTICATION FIXTURES =====

@pytest.fixture
def auth_token(test_user: User):
    """Create a valid JWT token for test user"""
    token = create_access_token(data={"sub": str(test_user.id)})
    return token


@pytest.fixture
def auth_headers(auth_token: str):
    """Create authentication headers"""
    return {"Authorization": f"Bearer {auth_token}"}


# ===== API CLIENT FIXTURES =====

@pytest.fixture
def client():
    """Create test client for API"""
    return TestClient(app)


@pytest.fixture
def authenticated_client(client: TestClient, auth_headers: dict):
    """Create authenticated test client"""
    client.headers.update(auth_headers)
    return client


# ===== REDIS FIXTURES =====

@pytest.fixture
def redis_client():
    """
    Provide Redis client for testing
    Uses test database (DB 15)
    """
    client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=15,  # Use separate DB for tests
        decode_responses=True
    )
    
    # Clear test database before test
    client.flushdb()
    
    yield client
    
    # Clear after test
    client.flushdb()
    client.close()


# ===== ASYNC FIXTURES =====

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===== MOCK FIXTURES =====

@pytest.fixture
def mock_websocket_manager(monkeypatch):
    """Mock WebSocket manager to avoid connection issues in tests"""
    from unittest.mock import AsyncMock, MagicMock
    
    mock_manager = MagicMock()
    mock_manager.broadcast_to_user = AsyncMock(return_value=True)
    mock_manager.is_user_connected = MagicMock(return_value=False)
    
    # Patch the global instance
    monkeypatch.setattr(
        "app.services.websocket_manager.websocket_manager",
        mock_manager
    )
    
    return mock_manager


@pytest.fixture
def mock_notification_service(monkeypatch):
    """Mock notification service for tests"""
    from unittest.mock import AsyncMock, MagicMock
    
    mock_service = MagicMock()
    mock_service.send_achievement = AsyncMock(return_value=True)
    mock_service.send_progress_update = AsyncMock(return_value=True)
    mock_service.send_meal_reminder = AsyncMock(return_value=True)
    mock_service.send_inventory_alert = AsyncMock(return_value=True)
    
    return mock_service


# ===== HELPER FUNCTIONS =====

def create_test_meal_logs_for_days(
    db: Session,
    user_id: int,
    recipe_id: int,
    days: int = 7,
    consume_percentage: float = 0.7
):
    """
    Helper to create meal logs for multiple days
    Used for testing history and analytics
    """
    today = datetime.utcnow()
    meal_logs = []
    
    for day_offset in range(days):
        day = today - timedelta(days=day_offset)
        
        for meal_type, hour in [("breakfast", 8), ("lunch", 13), ("dinner", 19)]:
            meal_time = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            meal_log = MealLog(
                user_id=user_id,
                recipe_id=recipe_id,
                meal_type=meal_type,
                planned_datetime=meal_time,
                consumed_datetime=None,
                was_skipped=False,
                portion_multiplier=1.0
            )
            
            # Consume some meals based on percentage
            import random
            if random.random() < consume_percentage:
                meal_log.consumed_datetime = meal_time + timedelta(minutes=30)
            
            db.add(meal_log)
            meal_logs.append(meal_log)
    
    db.commit()
    
    for log in meal_logs:
        db.refresh(log)
    
    return meal_logs


# ===== PYTEST CONFIGURATION =====

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (services working together)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (complete flows)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "asyncio: Async tests"
    )


# ===== TEST UTILITIES =====

@pytest.fixture
def assert_database_state():
    """Helper fixture for asserting database state"""
    def _assert_state(db: Session, model, filters: dict, expected_count: int = None, expected_values: dict = None):
        query = db.query(model)
        for key, value in filters.items():
            query = query.filter(getattr(model, key) == value)
        
        results = query.all()
        
        if expected_count is not None:
            assert len(results) == expected_count, f"Expected {expected_count} records, got {len(results)}"
        
        if expected_values and results:
            for key, value in expected_values.items():
                assert getattr(results[0], key) == value, f"Expected {key}={value}, got {getattr(results[0], key)}"
        
        return results
    
    return _assert_state