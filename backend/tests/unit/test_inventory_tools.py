"""
Test for Tracking Agent Inventory Tools
Tests: update_inventory(), check_expiring_items(), 
       calculate_inventory_status(), generate_restock_list()
"""

import sys
import os
from datetime import datetime, date, timedelta
import asyncio
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, UserProfile, UserGoal, UserInventory, Item, Recipe, RecipeIngredient
from app.agents.tracking_agent import TrackingAgent
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data for inventory tracking"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_inventory_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Create profile
        profile = UserProfile(
            user_id=user.id,
            name="Inventory Tester",
            age=35,
            height_cm=180.0,
            weight_kg=80.0,
            sex="male",
            activity_level="VERY_ACTIVE",
            bmr=1850.0,
            tdee=3219.0,
            goal_calories=3419.0
        )
        db.add(profile)
        
        # Create goal
        goal = UserGoal(
            user_id=user.id,
            goal_type="MUSCLE_GAIN",
            target_weight=85.0,
            macro_targets={"protein": 0.35, "carbs": 0.45, "fat": 0.2},
            is_active=True
        )
        db.add(goal)
        db.flush()
        
        # Get or create items
        items_data = [
            ("chicken breast", "protein", {"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6}),
            ("rice", "grains", {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}),
            ("broccoli", "vegetables", {"calories": 34, "protein_g": 2.8, "carbs_g": 7, "fat_g": 0.4}),
            ("eggs", "protein", {"calories": 155, "protein_g": 13, "carbs_g": 1.1, "fat_g": 11}),
            ("milk", "dairy", {"calories": 42, "protein_g": 3.4, "carbs_g": 5, "fat_g": 1})
        ]
        
        items = []
        for name, category, nutrition in items_data:
            item = db.query(Item).filter(Item.canonical_name == name).first()
            if not item:
                item = Item(
                    canonical_name=name,
                    category=category,
                    unit="g",
                    nutrition_per_100g=nutrition
                )
                db.add(item)
                db.flush()
            items.append(item)
        
        today = datetime.utcnow()
        
        # Create inventory with different scenarios
        # 1. Normal stock item (chicken)
        inv1 = UserInventory(
            user_id=user.id,
            item_id=items[0].id,
            quantity_grams=1000.0,  # Good stock
            purchase_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=5),
            source="manual"
        )
        db.add(inv1)
        
        # 2. Low stock item (rice - 15%)
        inv2 = UserInventory(
            user_id=user.id,
            item_id=items[1].id,
            quantity_grams=150.0,  # Low stock
            purchase_date=today - timedelta(days=5),
            expiry_date=today + timedelta(days=15),
            source="manual"
        )
        db.add(inv2)
        
        # 3. Expiring tomorrow (broccoli)
        inv3 = UserInventory(
            user_id=user.id,
            item_id=items[2].id,
            quantity_grams=300.0,
            purchase_date=today - timedelta(days=3),
            expiry_date=today + timedelta(days=1),  # Expires tomorrow
            source="manual"
        )
        db.add(inv3)
        
        # 4. Expiring in 3 days (eggs)
        inv4 = UserInventory(
            user_id=user.id,
            item_id=items[3].id,
            quantity_grams=600.0,
            purchase_date=today - timedelta(days=4),
            expiry_date=today + timedelta(days=3),  # Expires in 3 days
            source="manual"
        )
        db.add(inv4)
        
        # 5. Out of stock scenario - no milk in inventory
        
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}")
        print(f"   Items: Chicken {items[0].id}, Rice {items[1].id}, Broccoli {items[2].id}")
        print(f"   Eggs {items[3].id}, Milk {items[4].id} (not in inventory)")
        print(f"   Inventory: Normal stock, Low stock, Expiring tomorrow, Expiring in 3 days")
        
        return {
            "user_id": user.id,
            "item_chicken": items[0].id,
            "item_rice": items[1].id,
            "item_broccoli": items[2].id,
            "item_eggs": items[3].id,
            "item_milk": items[4].id,
            "inv_chicken": inv1.id,
            "inv_rice": inv2.id,
            "inv_broccoli": inv3.id,
            "inv_eggs": inv4.id,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_update_inventory(test_data):
    """Test update_inventory() - batch inventory updates"""
    
    print("\n" + "="*60)
    print("Testing: update_inventory()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Add items to inventory
    print("\n[Test 1] Add items to inventory")
    db1 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db1, test_data["user_id"])
        
                updates = [
                    {
                        "item_id": test_data["item_chicken"],
                        "quantity": 500.0,
                        "operation": "add",
                        "expiry_date": (datetime.utcnow() + timedelta(days=7)).isoformat()
                    }
                ]
        
                result = asyncio.run(tracking_agent.update_inventory(updates))
        
                is_success = result.get("success", False)
                print_result("Returns success=True", is_success,
                            f"Error: {result.get('error', 'None')}")
        
                if is_success:
                    items_updated = result.get("items_updated", 0)
                    print_result("items_updated = 1", items_updated == 1,
                                f"Updated: {items_updated}")
            
                    items_failed = result.get("items_failed", 0)
                    print_result("items_failed = 0", items_failed == 0,
                                f"Failed: {items_failed}")
            
                    has_results = "results" in result
                    print_result("Has results array", has_results)
            
                    has_recommendations = "recommendations" in result
                    print_result("Has recommendations", has_recommendations)
                    
                    # Verify WebSocket was called
                    print_result("WebSocket broadcast called", mock_ws.broadcast_to_user.called,
                                f"Call count: {mock_ws.broadcast_to_user.call_count}")
        
        db1.commit()
    finally:
        db1.close()
    
    # TEST 2: Deduct items from inventory
    print("\n[Test 2] Deduct items from inventory")
    db2 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db2, test_data["user_id"])
        
                updates = [
                    {
                        "item_id": test_data["item_chicken"],
                        "quantity": 200.0,
                        "operation": "deduct"
                    }
                ]
        
                result = asyncio.run(tracking_agent.update_inventory(updates))
        
                is_success = result.get("success", False)
                print_result("Deduct operation works", is_success)
        
                if is_success:
                    operation = result.get("operation")
                    is_deduct = operation == "deduct"
                    print_result("Operation is 'deduct'", is_deduct,
                                f"Operation: {operation}")
        
        db2.commit()
    finally:
        db2.close()
    
    # TEST 3: Bulk update (multiple items)
    print("\n[Test 3] Bulk update multiple items")
    db3 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db3, test_data["user_id"])
        
                updates = [
                    {
                        "item_id": test_data["item_rice"],
                        "quantity": 1000.0,
                        "operation": "add",
                        "expiry_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
                    },
                    {
                        "item_id": test_data["item_eggs"],
                        "quantity": 100.0,
                        "operation": "deduct"
                    },
                    {
                        "item_id": test_data["item_broccoli"],
                        "quantity": 200.0,
                        "operation": "add",
                        "expiry_date": (datetime.utcnow() + timedelta(days=5)).isoformat()
                    }
                ]
        
                result = asyncio.run(tracking_agent.update_inventory(updates))
        
                is_success = result.get("success", False)
                print_result("Bulk update succeeds", is_success)
        
                if is_success:
                    items_updated = result.get("items_updated", 0)
                    processed_all = items_updated == 3
                    print_result("All 3 items processed", processed_all,
                                f"Updated: {items_updated}/3")
        
        db3.commit()
    finally:
        db3.close()
    
    # TEST 4: Handle partial failures
    print("\n[Test 4] Handle partial failures")
    db4 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db4, test_data["user_id"])
        
                updates = [
                    {
                        "item_id": test_data["item_chicken"],
                        "quantity": 100.0,
                        "operation": "add"
                    },
                    {
                        "item_id": 999999,  # Invalid item
                        "quantity": 100.0,
                        "operation": "add"
                    }
                ]
        
                result = asyncio.run(tracking_agent.update_inventory(updates))
        
                # Should still report some success
                has_results = len(result.get("results", [])) > 0
                print_result("Processes valid items", has_results)
        
                has_failures = len(result.get("failures", [])) > 0
                print_result("Tracks failed items", has_failures,
                            f"Failures: {len(result.get('failures', []))}")
        
        db4.commit()
    finally:
        db4.close()
    
    # TEST 5: Validate operations
    print("\n[Test 5] Validate operation types")
    db5 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db5, test_data["user_id"])
        
                # Invalid operation
                updates = [
                    {
                        "item_id": test_data["item_chicken"],
                        "quantity": 100.0,
                        "operation": "invalid_op"
                    }
                ]
        
                result = asyncio.run(tracking_agent.update_inventory(updates))
        
                # Should handle gracefully
                has_error = not result.get("success", True) or len(result.get("failures", [])) > 0
                print_result("Rejects invalid operation", has_error)
    finally:
        db5.close()

def test_check_expiring_items(test_data):
    """Test check_expiring_items() - find items near expiry"""
    
    print("\n" + "="*60)
    print("Testing: check_expiring_items()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Find expiring items
    print("\n[Test 1] Find items expiring within 3 days")
    db1 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db1, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.check_expiring_items())
        
                is_success = result.get("success", False)
                print_result("Returns success=True", is_success)
        
                if is_success:
                    has_expiring = "expiring_items" in result
                    print_result("Has expiring_items array", has_expiring)
            
                    if has_expiring:
                        expiring_items = result["expiring_items"]
                        has_items = len(expiring_items) >= 2  # Should find broccoli and eggs
                        print_result("Found expiring items", has_items,
                                    f"Count: {len(expiring_items)}")
                
                        # Check priority levels
                        priorities = [item.get("priority") for item in expiring_items]
                        has_urgent = "urgent" in priorities
                        print_result("Has URGENT priority item", has_urgent,
                                    "For item expiring tomorrow")
                
                        has_high = "high" in priorities
                        print_result("Has HIGH priority item", has_high,
                                    "For item expiring in 3 days")
            
                    has_summary = "summary" in result
                    print_result("Has summary", has_summary)
    finally:
        db1.close()
    
    # TEST 2: Check item structure
    print("\n[Test 2] Expiring item contains required info")
    db2 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db2, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.check_expiring_items())
        
                if result.get("success") and result.get("expiring_items"):
                    first_item = result["expiring_items"][0]
            
                    has_item_name = "item_name" in first_item
                    print_result("Has item_name", has_item_name,
                                f"Name: {first_item.get('item_name')}")
            
                    has_days = "days_until_expiry" in first_item
                    print_result("Has days_until_expiry", has_days,
                                f"Days: {first_item.get('days_until_expiry')}")
            
                    has_priority = "priority" in first_item
                    print_result("Has priority", has_priority,
                                f"Priority: {first_item.get('priority')}")
            
                    has_quantity = "quantity" in first_item
                    print_result("Has quantity", has_quantity,
                                f"Qty: {first_item.get('quantity')}")
            
                    has_expiry_date = "expiry_date" in first_item
                    print_result("Has expiry_date", has_expiry_date)
    finally:
        db2.close()
    
    # TEST 3: Recipe suggestions for expiring items
    print("\n[Test 3] Recipe suggestions included")
    db3 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db3, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.check_expiring_items())
        
                if result.get("success") and result.get("expiring_items"):
                    # Check if any item has recipe suggestions
                    has_recipes = any(
                        "recipe_suggestions" in item 
                        for item in result["expiring_items"]
                    )
                    print_result("Some items have recipe_suggestions", has_recipes)
    finally:
        db3.close()

def test_calculate_inventory_status(test_data):
    """Test calculate_inventory_status() - inventory analytics"""
    
    print("\n" + "="*60)
    print("Testing: calculate_inventory_status()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Get inventory status
    print("\n[Test 1] Calculate inventory status")
    db1 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db1, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.calculate_inventory_status())
        
                is_success = result.get("success", False)
                print_result("Returns success=True", is_success)
        
                if is_success:
                    has_overall = "overall_status" in result
                    print_result("Has overall_status", has_overall)
            
                    has_by_category = "status_by_category" in result
                    print_result("Has status_by_category", has_by_category)
            
                    has_low_stock = "low_stock_items" in result
                    print_result("Has low_stock_items", has_low_stock)
            
                    has_recommendations = "recommendations" in result
                    print_result("Has recommendations", has_recommendations)
    finally:
        db1.close()
    
    # TEST 2: Low stock detection
    print("\n[Test 2] Detects low stock items")
    db2 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db2, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.calculate_inventory_status())
        
                if result.get("success"):
                    low_stock_items = result.get("low_stock_items", [])
                    has_low_stock = len(low_stock_items) > 0
                    print_result("Found low stock items", has_low_stock,
                                f"Count: {len(low_stock_items)}")
            
                    # Rice should be detected as low stock (150g)
                    if low_stock_items:
                        rice_found = any(
                            item.get("item_id") == test_data["item_rice"]
                            for item in low_stock_items
                        )
                        print_result("Rice detected as low stock", rice_found)
    finally:
        db2.close()
    
    # TEST 3: Status by category
    print("\n[Test 3] Breaks down by category")
    db3 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db3, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.calculate_inventory_status())
        
                if result.get("success") and "status_by_category" in result:
                    categories = result["status_by_category"]
            
                    has_categories = len(categories) > 0
                    print_result("Has category breakdown", has_categories,
                                f"Categories: {len(categories)}")
            
                    # Check if percentage is calculated
                    if categories:
                        first_cat = list(categories.values())[0] if categories else {}
                        has_percentage = "percentage" in first_cat
                        print_result("Categories have percentage", has_percentage)
    finally:
        db3.close()

def test_generate_restock_list(test_data):
    """Test generate_restock_list() - shopping recommendations"""
    
    print("\n" + "="*60)
    print("Testing: generate_restock_list()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Generate restock list
    print("\n[Test 1] Generate shopping list")
    db1 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db1, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.generate_restock_list())
        
                is_success = result.get("success", False)
                print_result("Returns success=True", is_success)
        
                if is_success:
                    has_restock = "restock_list" in result
                    print_result("Has restock_list", has_restock)
            
                    if has_restock:
                        restock_list = result["restock_list"]
                
                        # Should have priority levels
                        has_urgent = "urgent" in restock_list
                        print_result("Has urgent items", has_urgent)
                
                        has_high = "high" in restock_list
                        print_result("Has high priority items", has_high)
                
                        has_normal = "normal" in restock_list
                        print_result("Has normal priority items", has_normal)
                
                        # Check total items
                        total_items = sum(len(items) for items in restock_list.values())
                        has_items = total_items > 0
                        print_result("Has items to restock", has_items,
                                    f"Total items: {total_items}")
            
                    has_strategy = "shopping_strategy" in result
                    print_result("Has shopping_strategy", has_strategy)
    finally:
        db1.close()
    
    # TEST 2: Priority levels correct
    print("\n[Test 2] Priority levels assigned correctly")
    db2 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db2, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.generate_restock_list())
        
                if result.get("success") and "restock_list" in result:
                    restock_list = result["restock_list"]
            
                    # Milk (out of stock) should be in urgent
                    if "urgent" in restock_list:
                        milk_in_urgent = any(
                            item.get("item_id") == test_data["item_milk"]
                            for item in restock_list["urgent"]
                        )
                        print_result("Out of stock item in URGENT", milk_in_urgent)
            
                    # Rice (low stock) should be in high or urgent
                    if "high" in restock_list or "urgent" in restock_list:
                        rice_found = any(
                            item.get("item_id") == test_data["item_rice"]
                            for priority_items in restock_list.values()
                            for item in priority_items
                        )
                        print_result("Low stock item included", rice_found)
    finally:
        db2.close()
    
    # TEST 3: Item structure
    print("\n[Test 3] Restock items contain required info")
    db3 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db3, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.generate_restock_list())
        
                if result.get("success") and "restock_list" in result:
                    # Get first item from any priority level
                    first_item = None
                    for priority_items in result["restock_list"].values():
                        if priority_items:
                            first_item = priority_items[0]
                            break
            
                    if first_item:
                        has_item_name = "item_name" in first_item
                        print_result("Has item_name", has_item_name,
                                    f"Name: {first_item.get('item_name')}")
                
                        has_current_stock = "current_stock" in first_item
                        print_result("Has current_stock", has_current_stock,
                                    f"Stock: {first_item.get('current_stock')}")
                
                        has_recommended = "recommended_quantity" in first_item
                        print_result("Has recommended_quantity", has_recommended,
                                    f"Qty: {first_item.get('recommended_quantity')}")
                
                        has_reason = "reason" in first_item
                        print_result("Has reason", has_reason,
                                    f"Reason: {first_item.get('reason')}")
    finally:
        db3.close()

def cleanup(test_data):
    """Clean up test data"""
    print("\n" + "="*60)
    print("Cleanup")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        db.query(UserInventory).filter(UserInventory.user_id == test_data["user_id"]).delete()
        db.query(UserGoal).filter(UserGoal.user_id == test_data["user_id"]).delete()
        db.query(UserProfile).filter(UserProfile.user_id == test_data["user_id"]).delete()
        db.query(User).filter(User.id == test_data["user_id"]).delete()
        db.commit()
        print("✅ Cleanup complete")
    except Exception as e:
        db.rollback()
        print(f"⚠️  Cleanup error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("TRACKING AGENT: INVENTORY TOOLS TESTS")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_update_inventory(test_data)
        test_check_expiring_items(test_data)
        test_calculate_inventory_status(test_data)
        test_generate_restock_list(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")