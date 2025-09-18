# backend/tests/test_day6_complete.py
"""
Complete test suite for Day 6 components:
- Tracking Agent (8 tools)
- Consumption Service 
- Tracking API endpoints
- WebSocket functionality
- Notification Service
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, List, Any

# Import all Day 6 components
from app.agents.tracking_agent import TrackingAgent, TrackingState, TrackingEventType
from app.services.consumption_services import ConsumptionService
from app.services.inventory_service import IntelligentInventoryService
from app.services.notification_service import NotificationService
from app.api.tracking import router as tracking_router
from app.api.websocket_tracking import ConnectionManager, RealTimeTracker
from app.models.database import Base, User, UserProfile, UserGoal, MealLog, Recipe, RecipeIngredient, Item, UserInventory, ReceiptUpload

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_day6.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

@pytest.fixture
def db_session():
    """Create a test database session"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def test_user(db_session: Session):
    """Create a test user with profile and goals"""
    user = User(
        id=1,
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    
    profile = UserProfile(
        user_id=1,
        name="Test User",
        age=30,
        height_cm=175,
        weight_kg=70,
        sex="male",
        bmr=1650,
        tdee=2475,
        goal_calories=2475
    )
    db_session.add(profile)
    
    goal = UserGoal(
        user_id=1,
        goal_type="muscle_gain",
        macro_targets={"protein": 0.3, "carbs": 0.45, "fat": 0.25}
    )
    db_session.add(goal)
    
    db_session.commit()
    return user

@pytest.fixture
def test_recipes(db_session: Session):
    """Create test recipes with ingredients"""
    # Create items first
    items = [
        Item(id=1, canonical_name="chicken_breast", category="protein", 
             nutrition_per_100g={"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6}),
        Item(id=2, canonical_name="rice", category="grains",
             nutrition_per_100g={"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}),
        Item(id=3, canonical_name="broccoli", category="vegetables",
             nutrition_per_100g={"calories": 34, "protein_g": 2.8, "carbs_g": 7, "fat_g": 0.4})
    ]
    
    for item in items:
        db_session.add(item)
    
    # Create recipe
    recipe = Recipe(
        id=1,
        title="Chicken Rice Bowl",
        description="Healthy protein bowl",
        goals=["muscle_gain", "fat_loss"],
        suitable_meal_times=["lunch", "dinner"],
        macros_per_serving={
            "calories": 450,
            "protein_g": 45,
            "carbs_g": 40,
            "fat_g": 10,
            "fiber_g": 5
        },
        prep_time_min=15,
        cook_time_min=20
    )
    db_session.add(recipe)
    
    # Add ingredients to recipe
    ingredients = [
        RecipeIngredient(recipe_id=1, item_id=1, quantity_grams=150),
        RecipeIngredient(recipe_id=1, item_id=2, quantity_grams=100),
        RecipeIngredient(recipe_id=1, item_id=3, quantity_grams=100)
    ]
    
    for ing in ingredients:
        db_session.add(ing)
    
    db_session.commit()
    return [recipe]

@pytest.fixture
def test_meal_logs(db_session: Session, test_user, test_recipes):
    """Create test meal logs"""
    today = datetime.combine(date.today(), datetime.min.time())
    
    meal_logs = [
        MealLog(
            id=1,
            user_id=test_user.id,
            recipe_id=test_recipes[0].id,
            meal_type="lunch",
            planned_datetime=today.replace(hour=12, minute=30),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        ),
        MealLog(
            id=2,
            user_id=test_user.id,
            recipe_id=test_recipes[0].id,
            meal_type="dinner",
            planned_datetime=today.replace(hour=19, minute=0),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
    ]
    
    for log in meal_logs:
        db_session.add(log)
    
    db_session.commit()
    return meal_logs

@pytest.fixture
def test_inventory(db_session: Session, test_user):
    """Create test inventory items"""
    inventory = [
        UserInventory(
            user_id=test_user.id,
            item_id=1,
            quantity_grams=500,
            purchase_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=5)
        ),
        UserInventory(
            user_id=test_user.id,
            item_id=2,
            quantity_grams=1000,
            purchase_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=30)
        ),
        UserInventory(
            user_id=test_user.id,
            item_id=3,
            quantity_grams=50,  # Low stock
            purchase_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=2)  # Expiring soon
        )
    ]
    
    for item in inventory:
        db_session.add(item)
    
    db_session.commit()
    return inventory

# ==================== TRACKING AGENT TESTS ====================

class TestTrackingAgent:
    """Test suite for Tracking Agent and its 8 tools"""
    
    def test_tracking_agent_initialization(self, db_session, test_user):
        """Test agent initialization creates proper state"""
        agent = TrackingAgent(db_session, test_user.id)
        
        assert agent.user_id == test_user.id
        assert isinstance(agent.state, TrackingState)
        assert len(agent.tools) == 8
        assert agent.state.user_id == test_user.id
        assert isinstance(agent.state.current_inventory, list)
        assert isinstance(agent.state.alerts, list)
    
    def test_process_receipt_ocr(self, db_session, test_user):
        """Test Tool 1: Process receipt OCR"""
        # Create a receipt with OCR text
        receipt = ReceiptUpload(
            id=1,
            user_id=test_user.id,
            file_url="s3://receipts/test.jpg",
            ocr_raw_text="""
                BIG BAZAAR ANDHERI WEST
                17/09/2025  5:34 PM
                1. Whole Wheat Flour 10kg 520.00
                2. Amul Gold Milk 1L 60.00
                3. Chicken Breast 700g 180.00
                TOTAL 1931.00
                Thank you for shopping!
            """,
            processing_status="pending"
        )
        db_session.add(receipt)
        db_session.commit()
        
        agent = TrackingAgent(db_session, test_user.id)
        result = agent.process_receipt_ocr(receipt.id)

        print("result", result)
        
        assert result["success"] == True
        assert result["items_found"] > 0
        assert len(result["parsed_items"]) == 3
        assert any("tomatoes" in str(item).lower() for item in result["parsed_items"])
        
        # Check receipt was updated
        updated_receipt = db_session.query(ReceiptUpload).filter_by(id=1).first()
        assert updated_receipt.processing_status == "completed"
        assert updated_receipt.parsed_items is not None
    
    def test_normalize_ocr_items(self, db_session, test_user):
        """Test Tool 2: Normalize OCR items to database items"""
        agent = TrackingAgent(db_session, test_user.id)
        
        ocr_items = """
        10kg whole wheat flour
        1L amul gold milk
        700g chicken breast
        """
        
        result = agent.normalize_ocr_items(ocr_items)
        
        assert result["success"] == True
        assert result["normalized_count"] >= 1  # At least chicken should match
        assert result["unmatched_count"] >= 1  # unknown_item should not match
        assert len(result["normalized_items"]) > 0
        assert "chicken" in str(result["normalized_items"]).lower()
    
    def test_update_inventory_add(self, db_session, test_user, test_inventory):
        """Test Tool 3: Update inventory - Add operation"""
        agent = TrackingAgent(db_session, test_user.id)
        
        updates = [
            {"item_id": 1, "quantity_grams": 200, "expiry_date": None},
            {"item_id": 2, "quantity_grams": 500, "expiry_date": None}
        ]
        
        result = agent.update_inventory(updates, operation="add")
        
        assert result["success"] == True
        assert result["operation"] == "add"
        assert result["items_updated"] == 2
        
        # Verify inventory was actually updated
        chicken_inv = db_session.query(UserInventory).filter_by(
            user_id=test_user.id, item_id=1
        ).first()
        assert chicken_inv.quantity_grams == 700  # 500 + 200
    
    def test_update_inventory_deduct(self, db_session, test_user, test_inventory):
        """Test Tool 3: Update inventory - Deduct operation"""
        agent = TrackingAgent(db_session, test_user.id)
        
        updates = [
            {"item_id": 1, "quantity_grams": 150}
        ]
        
        result = agent.update_inventory(updates, operation="deduct")
        
        assert result["success"] == True
        assert result["operation"] == "deduct"
        
        # Verify inventory was deducted
        chicken_inv = db_session.query(UserInventory).filter_by(
            user_id=test_user.id, item_id=1
        ).first()
        assert chicken_inv.quantity_grams == 350  # 500 - 150
    
    def test_log_meal_consumption(self, db_session, test_user, test_meal_logs, test_inventory):
        """Test Tool 4: Log meal consumption with auto-deduction"""
        agent = TrackingAgent(db_session, test_user.id)
        
        # Log lunch consumption
        result = agent.log_meal_consumption(
            meal_log_id=test_meal_logs[0].id,
            portion_multiplier=1.0
        )
        
        assert result["success"] == True
        assert result["meal_type"] == "lunch"
        assert result["recipe"] == "Chicken Rice Bowl"
        assert len(result["deducted_items"]) == 3  # 3 ingredients
        
        # Verify meal was logged
        meal = db_session.query(MealLog).filter_by(id=test_meal_logs[0].id).first()
        assert meal.consumed_datetime is not None
        assert meal.portion_multiplier == 1.0
        
        # Verify inventory was deducted
        chicken_inv = db_session.query(UserInventory).filter_by(
            user_id=test_user.id, item_id=1
        ).first()
        assert chicken_inv.quantity_grams == 350  # 500 - 150 (recipe amount)
        
        # Verify daily totals updated
        assert result["daily_totals"]["total_calories"] == 450
        assert result["daily_totals"]["total_macros"]["protein_g"] == 45
    
    def test_track_skipped_meals(self, db_session, test_user, test_meal_logs):
        """Test Tool 5: Track skipped meals"""
        agent = TrackingAgent(db_session, test_user.id)
        
        result = agent.track_skipped_meals(
            meal_log_id=test_meal_logs[0].id,
            reason="Not hungry"
        )
        
        assert result["success"] == True
        assert result["meal_type"] == "lunch"
        assert result["reason"] == "Not hungry"
        assert "pattern_analysis" in result
        
        # Verify meal was marked as skipped
        meal = db_session.query(MealLog).filter_by(id=test_meal_logs[0].id).first()
        assert meal.was_skipped == True
        assert meal.skip_reason == "Not hungry"
        assert meal.consumed_datetime is None
    
    def test_check_expiring_items(self, db_session, test_user, test_inventory):
        """Test Tool 6: Check for expiring items"""
        agent = TrackingAgent(db_session, test_user.id)
        
        result = agent.check_expiring_items()
        
        assert result["success"] == True
        assert result["expiring_count"] >= 1  # Broccoli expires in 2 days
        assert len(result["expiring_items"]) >= 1
        
        # Check that broccoli is in expiring items
        expiring_names = [item["item"] for item in result["expiring_items"]]
        assert "broccoli" in expiring_names
        
        # Check recommendations are generated
        assert len(result["recommendations"]) > 0
        assert any("broccoli" in rec for rec in result["recommendations"])
    
    def test_calculate_inventory_status(self, db_session, test_user, test_inventory, test_meal_logs):
        """Test Tool 7: Calculate inventory status percentage"""
        agent = TrackingAgent(db_session, test_user.id)
        
        result = agent.calculate_inventory_status()
        
        assert result["success"] == True
        assert "overall_percentage" in result
        assert isinstance(result["overall_percentage"], (int, float))
        assert 0 <= result["overall_percentage"] <= 100
        
        # Check critical items (broccoli has only 50g)
        assert len(result["critical_items"]) >= 1
        critical_names = [item["name"] for item in result["critical_items"]]
        assert "broccoli" in critical_names
        
        # Check recommendations
        assert len(result["recommendations"]) > 0
    
    def test_generate_restock_list(self, db_session, test_user, test_inventory, test_meal_logs):
        """Test Tool 8: Generate restock list"""
        # First consume some meals to create usage history
        agent = TrackingAgent(db_session, test_user.id)
        agent.log_meal_consumption(test_meal_logs[0].id, 1.0)
        
        result = agent.generate_restock_list()
        
        assert result["success"] == True
        assert "restock_list" in result
        assert "urgent" in result["restock_list"]
        assert "soon" in result["restock_list"]
        assert "optional" in result["restock_list"]
        
        # Broccoli should be urgent (low stock)
        if result["restock_list"]["urgent"]:
            urgent_items = [item["item"] for item in result["restock_list"]["urgent"]]
            assert "broccoli" in urgent_items
        
        # Check shopping strategy
        assert len(result["shopping_strategy"]) > 0
        assert "estimated_cost" in result
        assert result["estimated_cost"] >= 0

# ==================== CONSUMPTION SERVICE TESTS ====================

class TestConsumptionService:
    """Test suite for Consumption Service"""
    
    def test_log_meal(self, db_session, test_user, test_meal_logs, test_inventory):
        """Test meal logging with inventory deduction"""
        service = ConsumptionService(db_session)
        
        result = service.log_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            portion_multiplier=1.5,
            notes="Extra hungry today"
        )
        
        assert result["success"] == True
        assert result["meal_type"] == "lunch"
        assert result["portion"] == 1.5
        assert result["macros_consumed"]["calories"] == 450 * 1.5  # 675
        
        # Check ingredients were deducted
        assert len(result["ingredients_deducted"]) == 3
        
        # Verify database changes
        meal = db_session.query(MealLog).filter_by(id=test_meal_logs[0].id).first()
        assert meal.consumed_datetime is not None
        assert meal.notes == "Extra hungry today"
        assert meal.portion_multiplier == 1.5
    
    def test_skip_meal(self, db_session, test_user, test_meal_logs):
        """Test meal skipping with analysis"""
        service = ConsumptionService(db_session)
        
        result = service.skip_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            reason="Meeting ran late"
        )
        
        assert result["success"] == True
        assert result["reason"] == "Meeting ran late"
        assert "skip_analysis" in result
        assert "adjusted_targets" in result
        assert "recommendation" in result
        
        # Verify meal marked as skipped
        meal = db_session.query(MealLog).filter_by(id=test_meal_logs[0].id).first()
        assert meal.was_skipped == True
        assert meal.skip_reason == "Meeting ran late"
    
    def test_update_portion(self, db_session, test_user, test_meal_logs, test_inventory):
        """Test portion update after consumption"""
        service = ConsumptionService(db_session)
        
        # First log the meal
        service.log_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            portion_multiplier=1.0
        )
        
        # Then update portion
        result = service.update_portion(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            new_portion_multiplier=0.75
        )
        
        assert result["success"] == True
        assert result["old_portion"] == 1.0
        assert result["new_portion"] == 0.75
        assert result["adjustment"] == -0.25
        
        # Verify portion was updated
        meal = db_session.query(MealLog).filter_by(id=test_meal_logs[0].id).first()
        assert meal.portion_multiplier == 0.75
    
    def test_get_today_summary(self, db_session, test_user, test_meal_logs):
        """Test getting today's consumption summary"""
        service = ConsumptionService(db_session)
        
        # Log one meal first
        service.log_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            portion_multiplier=1.0
        )
        
        result = service.get_today_summary(test_user.id)
        
        assert result["success"] == True
        assert result["meals_planned"] == 2
        assert result["meals_consumed"] == 1
        assert result["meals_pending"] == 1
        assert result["total_calories"] == 450
        assert result["compliance_rate"] == 50.0
        
        # Check meal details
        assert len(result["meals"]) == 2
        lunch = next(m for m in result["meals"] if m["meal_type"] == "lunch")
        assert lunch["status"] == "consumed"
        assert lunch["portion"] == 1.0
    
    def test_get_consumption_history(self, db_session, test_user, test_meal_logs):
        """Test getting consumption history"""
        service = ConsumptionService(db_session)
        
        # Log meals
        service.log_meal(test_user.id, test_meal_logs[0].id, 1.0)
        service.skip_meal(test_user.id, test_meal_logs[1].id, "Not hungry")
        
        result = service.get_consumption_history(
            user_id=test_user.id,
            days=7,
            include_details=True
        )
        
        assert result["success"] == True
        assert "history" in result
        assert "statistics" in result
        
        today = date.today().isoformat()
        assert today in result["history"]
        assert result["history"][today]["consumed"] == 1
        assert result["history"][today]["skipped"] == 1
        assert result["history"][today]["calories"] == 450
        
        # Check statistics
        stats = result["statistics"]
        assert stats["total_meals_consumed"] == 1
        assert stats["total_meals_skipped"] == 1
        assert stats["overall_compliance"] == 50.0
    
    def test_get_meal_patterns(self, db_session, test_user, test_meal_logs):
        """Test meal pattern analysis"""
        service = ConsumptionService(db_session)
        
        # Create some history
        for i in range(5):
            meal = MealLog(
                user_id=test_user.id,
                recipe_id=test_meal_logs[0].recipe_id,
                meal_type="lunch",
                planned_datetime=datetime.utcnow() - timedelta(days=i),
                consumed_datetime=datetime.utcnow() - timedelta(days=i, hours=1) if i % 2 == 0 else None,
                was_skipped=True if i % 2 == 1 else False,
                portion_multiplier=1.2 if i % 2 == 0 else 1.0
            )
            db_session.add(meal)
        db_session.commit()
        
        result = service.get_meal_patterns(test_user.id)
        
        assert result["success"] == True
        assert "patterns" in result
        
        patterns = result["patterns"]
        assert "meal_timing" in patterns
        assert "skip_patterns" in patterns
        assert "portion_patterns" in patterns
        assert "favorite_recipes" in patterns
        
        # Check skip patterns
        if "lunch" in patterns["skip_patterns"]:
            lunch_skip = patterns["skip_patterns"]["lunch"]
            assert "skip_rate" in lunch_skip
            assert lunch_skip["skip_rate"] > 0
        
        # Check insights
        assert "insights" in result
        assert len(result["insights"]) > 0

# ==================== API ENDPOINT TESTS ====================

class TestTrackingAPIEndpoints:
    """Test suite for tracking API endpoints"""
    
    @pytest.fixture
    def client(self, db_session):
        """Create test client with dependency override"""
        from app.main import app
        from app.models.database import get_db
        
        def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app)
    
    def test_log_meal_endpoint(self, client, test_user, test_meal_logs, test_inventory):
        """Test POST /tracking/log-meal endpoint"""
        response = client.post(
            "/tracking/log-meal",
            json={
                "meal_log_id": test_meal_logs[0].id,
                "portion_multiplier": 1.0,
                "notes": "Test meal"
            },
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["meal_type"] == "lunch"
        assert data["portion"] == 1.0
    
    def test_skip_meal_endpoint(self, client, test_user, test_meal_logs):
        """Test POST /tracking/skip-meal endpoint"""
        response = client.post(
            "/tracking/skip-meal",
            json={
                "meal_log_id": test_meal_logs[0].id,
                "reason": "Not feeling well"
            },
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["reason"] == "Not feeling well"
    
    def test_today_summary_endpoint(self, client, test_user, test_meal_logs):
        """Test GET /tracking/today endpoint"""
        response = client.get(
            "/tracking/today",
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["meals_planned"] >= 0
        assert "total_calories" in data
        assert "compliance_rate" in data
    
    def test_history_endpoint(self, client, test_user):
        """Test GET /tracking/history endpoint"""
        response = client.get(
            "/tracking/history?days=7&include_details=true",
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "history" in data
        assert "statistics" in data
    
    def test_patterns_endpoint(self, client, test_user):
        """Test GET /tracking/patterns endpoint"""
        response = client.get(
            "/tracking/patterns",
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "patterns" in data
        assert "insights" in data
    
    def test_agent_inventory_status_endpoint(self, client, test_user, test_inventory):
        """Test GET /tracking/agent/inventory-status endpoint"""
        response = client.get(
            "/tracking/agent/inventory-status",
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "overall_percentage" in data
        assert "critical_items" in data
        assert "recommendations" in data
    
    def test_agent_restock_list_endpoint(self, client, test_user, test_inventory):
        """Test GET /tracking/agent/restock-list endpoint"""
        response = client.get(
            "/tracking/agent/restock-list",
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "restock_list" in data
        assert "urgent" in data["restock_list"]
        assert "shopping_strategy" in data
    
    def test_quick_log_endpoint(self, client, test_user, test_meal_logs):
        """Test POST /tracking/real-time/quick-log/{meal_type} endpoint"""
        response = client.post(
            "/tracking/real-time/quick-log/lunch?portion=1.0",
            headers={"Authorization": f"Bearer {self._get_test_token(test_user)}"}
        )
        
        assert response.status_code in [200, 404]  # 404 if no pending lunch
        if response.status_code == 200:
            data = response.json()
            assert data["success"] == True
    
    def _get_test_token(self, user):
        """Generate test JWT token"""
        # In real tests, implement proper JWT generation
        return "test_token"

# ==================== WEBSOCKET TESTS ====================

class TestWebSocketTracking:
    """Test suite for WebSocket real-time tracking"""
    
    @pytest.mark.asyncio
    async def test_connection_manager(self):
        """Test WebSocket connection manager"""
        manager = ConnectionManager()
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        # Test connect
        await manager.connect(mock_websocket, user_id=1)
        assert 1 in manager.active_connections
        assert mock_websocket in manager.active_connections[1]
        
        # Test send message
        await manager.send_json_to_user({"event": "test"}, user_id=1)
        mock_websocket.send_text.assert_called_once()
        
        # Test disconnect
        manager.disconnect(mock_websocket, user_id=1)
        assert 1 not in manager.active_connections
    
    @pytest.mark.asyncio
    async def test_real_time_tracker(self, db_session, test_user, test_meal_logs):
        """Test real-time tracker functionality"""
        tracker = RealTimeTracker(db_session, test_user.id)
        
        # Test get real-time status
        status = await tracker.get_real_time_status()
        
        assert "timestamp" in status
        assert "daily_progress" in status
        assert "inventory" in status
        assert "next_meal" in status
        assert "hydration_reminder" in status
        
        # Test handle meal logged
        update = await tracker.handle_meal_logged(test_meal_logs[0].id)
        
        assert update["event"] == "meal_logged"
        assert "data" in update
        assert update["data"]["meal_log_id"] == test_meal_logs[0].id
        
        # Test handle inventory update
        items = [{"item_id": 1, "quantity": 100}]
        inv_update = await tracker.handle_inventory_update(items)
        
        assert inv_update["event"] == "inventory_updated"
        assert inv_update["data"]["items_updated"] == 1
    
    @pytest.mark.asyncio
    async def test_websocket_message_flow(self, db_session, test_user):
        """Test complete WebSocket message flow"""
        manager = ConnectionManager()
        tracker = RealTimeTracker(db_session, test_user.id)
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        await manager.connect(mock_websocket, test_user.id)
        
        # Test progress update generation
        update = await tracker.generate_progress_update()
        
        assert update["event"] == "progress_update"
        assert "data" in update
        assert update["data"]["daily_progress"] is not None
        
        # Send update through manager
        await manager.send_json_to_user(update, test_user.id)
        mock_websocket.send_text.assert_called()

# ==================== NOTIFICATION SERVICE TESTS ====================

class TestNotificationService:
    """Test suite for Notification Service"""
    
    @pytest.mark.asyncio
    async def test_send_meal_reminder(self, db_session):
        """Test sending meal reminder notification"""
        service = NotificationService(db_session)
        
        result = await service.send_meal_reminder(
            user_id=1,
            meal_type="lunch",
            recipe_name="Chicken Bowl",
            time_until=30
        )
        
        assert result == True
        
        # Check notification was queued
        notification = await service.notification_queue.get()
        assert notification["user_id"] == 1
        assert notification["type"] == "meal_reminder"
        assert "Chicken Bowl" in notification["body"]
        assert notification["priority"] == "high"  # 30 min = high priority
    
    @pytest.mark.asyncio
    async def test_send_inventory_alert(self, db_session):
        """Test sending inventory alerts"""
        service = NotificationService(db_session)
        
        result = await service.send_inventory_alert(
            user_id=1,
            alert_type="low_stock",
            items=["chicken", "rice", "broccoli"]
        )
        
        assert result == True
        
        notification = await service.notification_queue.get()
        assert notification["type"] == "inventory_alert"
        assert "Running low on" in notification["body"]
        assert "chicken" in notification["body"]
    
    @pytest.mark.asyncio
    async def test_send_progress_update(self, db_session):
        """Test sending progress update"""
        service = NotificationService(db_session)
        
        result = await service.send_progress_update(
            user_id=1,
            compliance_rate=85.5,
            calories_consumed=1800,
            calories_remaining=675
        )
        
        assert result == True
        
        notification = await service.notification_queue.get()
        assert notification["type"] == "progress_update"
        assert "85%" in notification["body"]
        assert "1800" in notification["body"]
    
    @pytest.mark.asyncio
    async def test_send_achievement(self, db_session):
        """Test sending achievement notification"""
        service = NotificationService(db_session)
        
        result = await service.send_achievement(
            user_id=1,
            achievement_type="week_streak",
            message="7-day perfect streak!"
        )
        
        assert result == True
        
        notification = await service.notification_queue.get()
        assert notification["type"] == "achievement"
        assert "Achievement Unlocked" in notification["title"]
        assert "7-day perfect streak" in notification["body"]
    
    def test_check_achievements(self, db_session, test_user, test_meal_logs):
        """Test achievement checking logic"""
        service = NotificationService(db_session)
        
        # Create 7 days of perfect meals for streak
        for i in range(7):
            for meal_type in ["breakfast", "lunch", "dinner"]:
                log = MealLog(
                    user_id=test_user.id,
                    recipe_id=test_meal_logs[0].recipe_id,
                    meal_type=meal_type,
                    planned_datetime=datetime.utcnow() - timedelta(days=i, hours=1),
                    consumed_datetime=datetime.utcnow() - timedelta(days=i),
                    portion_multiplier=1.0
                )
                db_session.add(log)
        db_session.commit()
        
        achievements = service.check_achievements(test_user.id)
        
        assert len(achievements) > 0
        assert any(a["type"] == "week_streak" for a in achievements)

# ==================== INTEGRATION TESTS ====================

class TestDay6Integration:
    """End-to-end integration tests for Day 6 components"""
    
    def test_complete_meal_logging_flow(self, db_session, test_user, test_meal_logs, test_inventory):
        """Test complete flow: API → Service → Agent → Database"""
        # 1. User logs meal via consumption service
        service = ConsumptionService(db_session)
        log_result = service.log_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            portion_multiplier=1.0
        )
        
        assert log_result["success"] == True
        
        # 2. Tracking agent processes the event
        agent = TrackingAgent(db_session, test_user.id)
        agent_state = agent.get_state()
        
        assert agent_state["daily_consumption"]["meals_logged"] >= 0
        
        # 3. Check inventory was deducted
        inventory_status = agent.calculate_inventory_status()
        assert inventory_status["success"] == True
        
        # 4. Generate restock list if needed
        restock = agent.generate_restock_list()
        assert restock["success"] == True
        
        # 5. Get consumption patterns
        patterns = service.get_meal_patterns(test_user.id)
        assert patterns["success"] == True
    
    def test_receipt_to_inventory_flow(self, db_session, test_user):
        """Test flow: Receipt upload → OCR → Normalize → Inventory update"""
        # 1. Create receipt with OCR text
        receipt = ReceiptUpload(
            id=2,
            user_id=test_user.id,
            file_url="s3://receipts/test2.jpg",
            ocr_raw_text="500g chicken breast\n1kg rice",
            processing_status="pending"
        )
        db_session.add(receipt)
        db_session.commit()
        
        # 2. Process with tracking agent
        agent = TrackingAgent(db_session, test_user.id)
        ocr_result = agent.process_receipt_ocr(receipt.id)
        
        assert ocr_result["success"] == True
        assert ocr_result["items_found"] == 2
        
        # 3. Normalize items
        normalize_result = agent.normalize_ocr_items(ocr_result["parsed_items"])
        
        assert normalize_result["success"] == True
        
        # 4. Update inventory
        if normalize_result["normalized_items"]:
            updates = [
                {
                    "item_id": item["matched_item"]["id"],
                    "quantity_grams": item["quantity_grams"]
                }
                for item in normalize_result["normalized_items"]
                if "matched_item" in item
            ]
            
            if updates:
                update_result = agent.update_inventory(updates, operation="add")
                assert update_result["success"] == True
    
    def test_skip_meal_and_adjustment_flow(self, db_session, test_user, test_meal_logs):
        """Test flow: Skip meal → Adjust targets → Update recommendations"""
        service = ConsumptionService(db_session)
        
        # 1. Skip lunch
        skip_result = service.skip_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            reason="In meeting"
        )
        
        assert skip_result["success"] == True
        assert "adjusted_targets" in skip_result
        
        # 2. Check adjusted targets for dinner
        if skip_result["adjusted_targets"].get("meal_adjustments"):
            dinner_adjustment = next(
                (m for m in skip_result["adjusted_targets"]["meal_adjustments"] 
                 if m["meal_type"] == "dinner"), 
                None
            )
            if dinner_adjustment:
                assert dinner_adjustment["suggested_portion"] > 1.0  # Should increase
        
        # 3. Get new daily summary
        summary = service.get_today_summary(test_user.id)
        
        assert summary["success"] == True
        assert summary["meals_skipped"] == 1
        assert summary["compliance_rate"] < 100
        
        # 4. Check patterns for skip analysis
        patterns = service.get_meal_patterns(test_user.id)
        
        if "lunch" in patterns["patterns"]["skip_patterns"]:
            assert patterns["patterns"]["skip_patterns"]["lunch"]["skip_rate"] > 0
    
    @pytest.mark.asyncio
    async def test_real_time_update_flow(self, db_session, test_user, test_meal_logs):
        """Test flow: Meal log → WebSocket broadcast → Notification"""
        # 1. Setup WebSocket and notification
        manager = ConnectionManager()
        notification_service = NotificationService(db_session)
        
        mock_websocket = AsyncMock()
        await manager.connect(mock_websocket, test_user.id)
        
        # 2. Log meal
        service = ConsumptionService(db_session)
        result = service.log_meal(
            user_id=test_user.id,
            meal_log_id=test_meal_logs[0].id,
            portion_multiplier=1.0
        )
        
        # 3. Generate real-time update
        tracker = RealTimeTracker(db_session, test_user.id)
        update = await tracker.handle_meal_logged(test_meal_logs[0].id)
        
        # 4. Broadcast update
        await manager.send_json_to_user(update, test_user.id)
        mock_websocket.send_text.assert_called()
        
        # 5. Check for achievements and send notification
        achievements = notification_service.check_achievements(test_user.id)
        
        if achievements:
            await notification_service.send_achievement(
                test_user.id,
                achievements[0]["type"],
                achievements[0]["message"]
            )
            
            # Verify notification queued
            notification = await notification_service.notification_queue.get()
            assert notification["type"] == "achievement"

# ==================== PERFORMANCE TESTS ====================

class TestDay6Performance:
    """Performance tests for Day 6 components"""
    
    def test_tracking_agent_performance(self, db_session, test_user, test_meal_logs):
        """Test tracking agent response times"""
        import time
        
        agent = TrackingAgent(db_session, test_user.id)
        
        # Test inventory status calculation time
        start = time.time()
        result = agent.calculate_inventory_status()
        elapsed = time.time() - start
        
        assert result["success"] == True
        assert elapsed < 1.0  # Should complete in under 1 second
        
        # Test restock list generation time
        start = time.time()
        result = agent.generate_restock_list()
        elapsed = time.time() - start
        
        assert result["success"] == True
        assert elapsed < 2.0  # Should complete in under 2 seconds
    
    def test_consumption_service_performance(self, db_session, test_user):
        """Test consumption service response times"""
        import time
        
        service = ConsumptionService(db_session)
        
        # Test get_today_summary performance
        start = time.time()
        result = service.get_today_summary(test_user.id)
        elapsed = time.time() - start
        
        assert result["success"] == True
        assert elapsed < 0.5  # Should complete in under 500ms
        
        # Test get_meal_patterns performance
        start = time.time()
        result = service.get_meal_patterns(test_user.id)
        elapsed = time.time() - start
        
        assert result["success"] == True
        assert elapsed < 1.0  # Should complete in under 1 second

# ==================== ERROR HANDLING TESTS ====================

class TestDay6ErrorHandling:
    """Test error handling in Day 6 components"""
    
    def test_tracking_agent_invalid_meal_log(self, db_session, test_user):
        """Test tracking agent with invalid meal log ID"""
        agent = TrackingAgent(db_session, test_user.id)
        
        result = agent.log_meal_consumption(
            meal_log_id=99999,  # Non-existent
            portion_multiplier=1.0
        )
        
        assert result["success"] == False
        assert "error" in result or "Meal log not found" in str(result)
    
    def test_consumption_service_invalid_user(self, db_session):
        """Test consumption service with invalid user ID"""
        service = ConsumptionService(db_session)
        
        result = service.get_today_summary(user_id=99999)
        
        # Should handle gracefully
        assert "meals" in result or result["success"] == False
    
    def test_inventory_negative_deduction(self, db_session, test_user, test_inventory):
        """Test inventory deduction with insufficient stock"""
        agent = TrackingAgent(db_session, test_user.id)
        
        # Try to deduct more than available
        updates = [
            {"item_id": 3, "quantity_grams": 100}  # Only 50g available
        ]
        
        result = agent.update_inventory(updates, operation="deduct")
        
        # Should handle gracefully - either succeed with 0 inventory or return error
        assert "success" in result
    
    def test_websocket_connection_drop(self):
        """Test WebSocket connection drop handling"""
        manager = ConnectionManager()
        
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        
        # Simulate connection and drop
        asyncio.run(manager.connect(mock_websocket, user_id=1))
        manager.disconnect(mock_websocket, user_id=1)
        
        # Should handle gracefully
        assert 1 not in manager.active_connections
        
        # Sending to disconnected user should not raise error
        async def test_send():
            await manager.send_json_to_user({"test": "data"}, user_id=1)
        
        # Should complete without error
        asyncio.run(test_send())


# ==================== RUN ALL TESTS ====================

if __name__ == "__main__":
    # Run all tests with detailed output
    pytest.main([
        __file__,
        "-v",  # Verbose
        "-s",  # Show print statements
        "--tb=short",  # Short traceback format
        "--color=yes",  # Colored output
        "-x",  # Stop on first failure
        "--cov=app",  # Coverage report
        "--cov-report=term-missing"  # Show missing lines
    ])