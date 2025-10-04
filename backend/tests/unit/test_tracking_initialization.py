"""
Test for Tracking Agent Initialization and Alert Generation
Tests: Agent state initialization and intelligent alert generation
"""

import sys
import os
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, UserProfile, UserGoal, UserInventory, Item, MealLog, Recipe
from app.agents.tracking_agent import TrackingAgent
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data for tracking agent"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_tracking_init_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Create profile
        profile = UserProfile(
            user_id=user.id,
            name="Test Tracker",
            age=30,
            height_cm=175.0,
            weight_kg=75.0,
            sex="male",
            activity_level="MODERATELY_ACTIVE",
            bmr=1700.0,
            tdee=2635.0,
            goal_calories=2835.0
        )
        db.add(profile)
        
        # Create goal
        goal = UserGoal(
            user_id=user.id,
            goal_type="MUSCLE_GAIN",
            target_weight=80.0,
            macro_targets={"protein": 0.3, "carbs": 0.45, "fat": 0.25},
            is_active=True
        )
        db.add(goal)
        db.flush()
        
        # Get or create items
        item1 = db.query(Item).filter(Item.canonical_name == "chicken breast").first()
        if not item1:
            item1 = Item(
                canonical_name="chicken breast",
                category="protein",
                unit="g",
                nutrition_per_100g={"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6}
            )
            db.add(item1)
            db.flush()
        
        item2 = db.query(Item).filter(Item.canonical_name == "rice").first()
        if not item2:
            item2 = Item(
                canonical_name="rice",
                category="grains",
                unit="g",
                nutrition_per_100g={"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3}
            )
            db.add(item2)
            db.flush()
        
        item3 = db.query(Item).filter(Item.canonical_name == "milk").first()
        if not item3:
            item3 = Item(
                canonical_name="milk",
                category="dairy",
                unit="ml",
                nutrition_per_100g={"calories": 42, "protein_g": 3.4, "carbs_g": 5, "fat_g": 1}
            )
            db.add(item3)
            db.flush()
        
        # Create inventory with different expiry dates
        today = datetime.utcnow()
        
        # Item expiring tomorrow (URGENT)
        inv1 = UserInventory(
            user_id=user.id,
            item_id=item1.id,
            quantity_grams=500.0,
            purchase_date=today - timedelta(days=5),
            expiry_date=today + timedelta(days=1),  # Expires tomorrow
            source="manual"
        )
        db.add(inv1)
        
        # Item expiring in 3 days (HIGH priority)
        inv2 = UserInventory(
            user_id=user.id,
            item_id=item2.id,
            quantity_grams=2000.0,
            purchase_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=3),  # Expires in 3 days
            source="manual"
        )
        db.add(inv2)
        
        # Item expiring in 7 days (NORMAL priority)
        inv3 = UserInventory(
            user_id=user.id,
            item_id=item3.id,
            quantity_grams=1000.0,
            purchase_date=today,
            expiry_date=today + timedelta(days=7),  # Expires in 7 days
            source="manual"
        )
        db.add(inv3)
        
        # Get a recipe for meal log
        recipe = db.query(Recipe).first()
        if not recipe:
            print("❌ ERROR: No recipes in database")
            db.close()
            return None
        
        # Create a consumed meal for today
        meal_log = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="breakfast",
            planned_datetime=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=8),
            consumed_datetime=datetime.utcnow(),
            portion_multiplier=1.0
        )
        db.add(meal_log)
        
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}, Items {item1.id}, {item2.id}, {item3.id}")
        print(f"   Inventory: {inv1.id} (expires tomorrow), {inv2.id} (expires in 3 days), {inv3.id} (expires in 7 days)")
        
        return {
            "user_id": user.id,
            "item1_id": item1.id,
            "item2_id": item2.id,
            "item3_id": item3.id,
            "inv1_id": inv1.id,
            "inv2_id": inv2.id,
            "inv3_id": inv3.id,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_tracking_agent_initialization(test_data):
    """Test tracking agent initializes with correct state"""
    
    print("\n" + "="*60)
    print("Testing: Tracking Agent Initialization")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks
                mock_ws.broadcast_to_user = Mock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                # Initialize tracking agent
                tracking_agent = TrackingAgent(db, test_data["user_id"])
        
                # Get agent state
                state = tracking_agent.get_state()
        
                # TEST 1: State contains required fields
                print("\n[Test 1] State structure is correct")
        
                has_daily_consumption = "daily_consumption" in state
                print_result("Has daily_consumption", has_daily_consumption)
        
                has_current_inventory = "current_inventory" in state
                print_result("Has current_inventory", has_current_inventory)
        
                has_alerts = "alerts" in state
                print_result("Has alerts", has_alerts)
        
                has_patterns = "consumption_patterns" in state
                print_result("Has patterns", has_patterns)
        
                # TEST 2: Daily consumption initialized
                print("\n[Test 2] Daily consumption initialized from consumption service")
        
                if has_daily_consumption:
                    daily = state["daily_consumption"]
                    has_meals_consumed = "meals_logged" in daily
                    print_result("Has meals_logged", has_meals_consumed,
                                f"Count: {daily.get('meals_logged', 0)}")
            
                    has_calories = "total_calories" in daily
                    print_result("Has calories", has_calories,
                                f"Calories: {daily.get('total_calories', 0)}")
            
                    has_macros = "total_macros" in daily
                    print_result("Has macros", has_macros, 
                                 f"Calories: {daily.get('total_macros', 0)}")
        
                # TEST 3: Current inventory initialized
                print("\n[Test 3] Current inventory loaded")
        
                if has_current_inventory:
                    inventory = state["current_inventory"]
                    inventory_count = len(inventory)
                    has_inventory = inventory_count >= 3
                    print_result("Has inventory items", has_inventory,
                                f"Count: {inventory_count}")
            
                    # Check if our test items are in inventory
                    has_item1 = str(test_data["item1_id"]) in inventory
                    print_result("Has chicken breast in inventory", has_item1)
            
                    has_item2 = str(test_data["item2_id"]) in inventory
                    print_result("Has rice in inventory", has_item2)
        
                # TEST 4: Alerts generated
                print("\n[Test 4] Intelligent alerts generated")
        
                if has_alerts:
                    alerts = state["alerts"]
                    has_expiry_alerts = "expiring_items" in alerts
                    print_result("Has expiring_items alerts", has_alerts)
            
                    if has_expiry_alerts:
                        expiring = alerts["expiring_items"]
                        alert_count = len(expiring)
                        has_alerts_generated = alert_count > 0
                        print_result("Alerts were generated", has_alerts_generated,
                                    f"Alert count: {alert_count}")
                
                        # Check priority levels
                        if has_alerts_generated:
                            priorities = [alert.get("priority") for alert in expiring]
                            has_urgent = "urgent" in priorities
                            has_high = "high" in priorities
                    
                            print_result("Has URGENT priority alert", has_urgent,
                                        "For item expiring tomorrow")
                            print_result("Has HIGH priority alert", has_high,
                                        "For item expiring in 3 days")
    
    finally:
        db.close()

def test_intelligent_alerts(test_data):
    """Test intelligent alert generation with priority levels"""
    
    print("\n" + "="*60)
    print("Testing: Intelligent Alert Generation")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, test_data["user_id"])
        
        # Get state
        state = tracking_agent.get_state()
        
        print("\n[Alerts by Priority]")
        
        expiring_items = state.get("alerts", [])
        
        # Create a dictionary to group alerts by priority
        alerts_by_priority = {"urgent": [], "high": [], "normal": []}
        
        for alert in expiring_items:
            priority = alert.get("priority", "normal")  # default to normal if missing
            if priority in alerts_by_priority:
                alerts_by_priority[priority].append(alert)
            else:
                alerts_by_priority["normal"].append(alert)  # fallback
        
        # Print grouped alerts
        for priority in ["urgent", "high", "normal"]:
            items = alerts_by_priority[priority]
            print(f"\nPriority: {priority.upper()} ({len(items)} alerts)")
            for a in items:
                print(f" - Item: {a.get('item')}, Days until expiry: {a.get('days_until_expiry')}, Message: {a.get('message')}")
        
    finally:
        db.close()


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
        db.query(MealLog).filter(MealLog.user_id == test_data["user_id"]).delete()
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
    print("TRACKING AGENT: INITIALIZATION & ALERT GENERATION TESTS")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_tracking_agent_initialization(test_data)
        test_intelligent_alerts(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")