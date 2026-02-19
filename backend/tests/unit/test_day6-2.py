# backend/tests/test_day6_simple.py
"""
Simple Python test script for Day 6 components
Uses existing database with real data for realistic testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, date
import json
import asyncio
import traceback
from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker

# Import Day 6 components
from app.models.database import (
    User, UserProfile, UserGoal, UserPath, UserPreference,
    MealLog, Recipe, RecipeIngredient, Item, UserInventory, 
    ReceiptUpload, AgentInteraction
)
from app.agents.tracking_agent import TrackingAgent, TrackingState
from app.services.consumption_services import ConsumptionService
from app.services.inventory_service import IntelligentInventoryService
from app.services.item_normalizer import IntelligentItemNormalizer
from app.core.config import settings

# Use your actual database
DATABASE_URL = settings.database_url  # Your actual database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "errors": []
}

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

def assert_equal(actual, expected, message):
    """Simple assertion helper"""
    if actual != expected:
        error_msg = f"ASSERTION FAILED: {message}\nExpected: {expected}\nActual: {actual}"
        print(f"❌ {error_msg}")
        test_results["failed"].append(error_msg)
        return False
    else:
        print(f"✅ {message}")
        test_results["passed"].append(message)
        return True

def assert_true(condition, message):
    """Assert condition is true"""
    if not condition:
        print(f"❌ ASSERTION FAILED: {message}")
        test_results["failed"].append(message)
        return False
    else:
        print(f"✅ {message}")
        test_results["passed"].append(message)
        return True

def assert_in(item, container, message):
    """Assert item in container"""
    if item not in container:
        print(f"❌ ASSERTION FAILED: {message}\n{item} not in {container}")
        test_results["failed"].append(message)
        return False
    else:
        print(f"✅ {message}")
        test_results["passed"].append(message)
        return True

# ==================== SETUP TEST DATA ====================

def setup_test_user(db):
    """Get or create a test user with complete profile"""
    print("\n📋 Setting up test user...")
    
    # Check if test user exists
    test_user = db.query(User).filter(User.email == "test_day6@example.com").first()
    
    if not test_user:
        # Create new test user
        test_user = User(
            email="test_day6@example.com",
            hashed_password="test_password_hash",
            is_active=True
        )
        db.add(test_user)
        db.commit()
        
        # Create profile
        profile = UserProfile(
            user_id=test_user.id,
            name="Day6 Test User",
            age=30,
            height_cm=175,
            weight_kg=70,
            sex="male",
            activity_level="moderately_active",
            bmr=1650,
            tdee=2550,
            goal_calories=2800  # Muscle gain goal
        )
        db.add(profile)
        
        # Create goal
        goal = UserGoal(
            user_id=test_user.id,
            goal_type="muscle_gain",
            target_weight=75,
            macro_targets={"protein": 0.3, "carbs": 0.45, "fat": 0.25}
        )
        db.add(goal)
        
        # Create preferences
        preferences = UserPreference(
            user_id=test_user.id,
            dietary_type="non_vegetarian",
            allergies=[],
            disliked_ingredients=["olives"],
            cuisine_preferences=["indian", "continental"]
        )
        db.add(preferences)
        
        db.commit()
        print(f"✅ Created new test user: {test_user.email} (ID: {test_user.id})")
    else:
        print(f"✅ Using existing test user: {test_user.email} (ID: {test_user.id})")
    
    return test_user

def setup_test_inventory(db, user_id):
    """Setup realistic inventory for testing"""
    print("\n📦 Setting up test inventory...")
    
    # Get common items from database
    chicken = db.query(Item).filter(Item.canonical_name == "chicken_breast").first()
    rice = db.query(Item).filter(Item.canonical_name == "rice").first()
    broccoli = db.query(Item).filter(Item.canonical_name == "broccoli").first()
    
    if not chicken:
        print("⚠️ Warning: No chicken_breast item found in database")
        return []
    
    # Check if inventory already exists
    existing = db.query(UserInventory).filter(UserInventory.user_id == user_id).first()
    
    if not existing:
        # Create inventory items
        inventory_items = []
        
        if chicken:
            inv1 = UserInventory(
                user_id=user_id,
                item_id=chicken.id,
                quantity_grams=500,
                purchase_date=datetime.utcnow(),
                expiry_date=datetime.utcnow() + timedelta(days=5),
                source="manual"
            )
            db.add(inv1)
            inventory_items.append(inv1)
        
        if rice:
            inv2 = UserInventory(
                user_id=user_id,
                item_id=rice.id,
                quantity_grams=2000,
                purchase_date=datetime.utcnow(),
                expiry_date=datetime.utcnow() + timedelta(days=60),
                source="manual"
            )
            db.add(inv2)
            inventory_items.append(inv2)
        
        if broccoli:
            inv3 = UserInventory(
                user_id=user_id,
                item_id=broccoli.id,
                quantity_grams=100,  # Low stock for testing
                purchase_date=datetime.utcnow() - timedelta(days=5),
                expiry_date=datetime.utcnow() + timedelta(days=2),  # Expiring soon
                source="manual"
            )
            db.add(inv3)
            inventory_items.append(inv3)
        
        db.commit()
        print(f"✅ Created {len(inventory_items)} inventory items")
        return inventory_items
    else:
        inventory = db.query(UserInventory).filter(UserInventory.user_id == user_id).all()
        print(f"✅ Found {len(inventory)} existing inventory items")
        return inventory

def setup_test_meal_plan(db, user_id):
    """Create today's meal plan for testing"""
    print("\n🍽️ Setting up test meal plan...")
    
    today = datetime.combine(date.today(), datetime.min.time())
    
    # Get a recipe from database
    recipe = db.query(Recipe).first()
    
    if not recipe:
        print("⚠️ Warning: No recipes found in database")
        return []
    
    # Check if today's meals already exist
    existing_meals = db.query(MealLog).filter(
        and_(
            MealLog.user_id == user_id,
            func.date(MealLog.planned_datetime) == date.today()
        )
    ).all()
    
    if not existing_meals:
        # Create today's meal plan
        meals = [
            MealLog(
                user_id=user_id,
                recipe_id=recipe.id,
                meal_type="breakfast",
                planned_datetime=today.replace(hour=8),
                portion_multiplier=1.0
            ),
            MealLog(
                user_id=user_id,
                recipe_id=recipe.id,
                meal_type="lunch",
                planned_datetime=today.replace(hour=13),
                portion_multiplier=1.0
            ),
            MealLog(
                user_id=user_id,
                recipe_id=recipe.id,
                meal_type="dinner",
                planned_datetime=today.replace(hour=19),
                portion_multiplier=1.0
            )
        ]
        
        for meal in meals:
            db.add(meal)
        
        db.commit()
        print(f"✅ Created {len(meals)} meals for today")
        return meals
    else:
        print(f"✅ Found {len(existing_meals)} existing meals for today")
        return existing_meals

# ==================== TRACKING AGENT TESTS ====================

def test_tracking_agent_initialization():
    """Test 1: Tracking Agent Initialization"""
    print_test_header("Tracking Agent Initialization")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        
        # Initialize agent
        agent = TrackingAgent(db, user.id)
        
        # Test state initialization
        assert_equal(agent.user_id, user.id, "Agent user_id matches")
        assert_true(isinstance(agent.state, TrackingState), "State is TrackingState instance")
        assert_equal(len(agent.tools), 8, "Agent has 8 tools")
        assert_true(isinstance(agent.state.current_inventory, list), "Inventory is a list")
        assert_true(isinstance(agent.state.alerts, list), "Alerts is a list")
        
        # Check state details
        print(f"\n📊 Agent State Details:")
        print(f"  - Daily consumption: {agent.state.daily_consumption}")
        print(f"  - Inventory items: {len(agent.state.current_inventory)}")
        print(f"  - Active alerts: {len(agent.state.alerts)}")
        print(f"  - Consumption patterns: {list(agent.state.consumption_patterns.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_meal_consumption_logging():
    """Test 2: Log Meal Consumption with Auto-deduction"""
    print_test_header("Meal Consumption Logging")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        inventory = setup_test_inventory(db, user.id)
        meals = setup_test_meal_plan(db, user.id)
        
        if not meals:
            print("⚠️ No meals to test with")
            return False
        
        # Get lunch meal
        lunch = next((m for m in meals if m.meal_type == "lunch" and not m.consumed_datetime), None)
        
        if not lunch:
            print("⚠️ No unconsumed lunch found")
            return False
        
        print(f"\n🍽️ Logging lunch (Meal ID: {lunch.id}, Recipe: {lunch.recipe.title})")
        
        # Initialize agent and log meal
        agent = TrackingAgent(db, user.id)
        
        # Check inventory before
        inv_before = db.query(UserInventory).filter(UserInventory.user_id == user.id).all()
        print(f"📦 Inventory before: {len(inv_before)} items")
        for item in inv_before[:3]:  # Show first 3
            item_name = db.query(Item).filter(Item.id == item.item_id).first()
            print(f"  - {item_name.canonical_name if item_name else 'Unknown'}: {item.quantity_grams}g")
        
        # Log the meal
        result = agent.log_meal_consumption(lunch.id, portion_multiplier=1.0)
        
        # Test results
        assert_true(result["success"], "Meal logged successfully")
        assert_equal(result["meal_type"], "lunch", "Correct meal type")
        assert_true(len(result.get("deducted_items", [])) > 0, "Items were deducted")
        
        # Check inventory after
        inv_after = db.query(UserInventory).filter(UserInventory.user_id == user.id).all()
        print(f"\n📦 Inventory after deduction:")
        for item in inv_after[:3]:
            item_name = db.query(Item).filter(Item.id == item.item_id).first()
            print(f"  - {item_name.canonical_name if item_name else 'Unknown'}: {item.quantity_grams}g")
        
        # Check meal was marked as consumed
        db.refresh(lunch)
        assert_true(lunch.consumed_datetime is not None, "Meal marked as consumed")
        
        # Check daily totals
        if "daily_totals" in result:
            print(f"\n📈 Daily Progress:")
            print(f"  - Calories: {result['daily_totals'].get('total_calories', 0)}")
            print(f"  - Protein: {result['daily_totals'].get('total_macros', {}).get('protein_g', 0)}g")
            print(f"  - Meals logged: {result['daily_totals'].get('meals_logged', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(traceback.format_exc())
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_inventory_status_calculation():
    """Test 3: Calculate Inventory Status"""
    print_test_header("Inventory Status Calculation")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        inventory = setup_test_inventory(db, user.id)
        
        agent = TrackingAgent(db, user.id)
        result = agent.calculate_inventory_status()
        
        assert_true(result["success"], "Inventory status calculated")
        assert_true("overall_percentage" in result, "Has overall percentage")
        
        print(f"\n📊 Inventory Status:")
        print(f"  - Overall: {result.get('overall_percentage', 0):.1f}%")
        
        if result.get("category_breakdown"):
            print(f"  - Categories:")
            for category, data in result["category_breakdown"].items():
                print(f"    • {category}: {data.get('average_percentage', 0):.1f}%")
        
        if result.get("critical_items"):
            print(f"  - Critical items ({len(result['critical_items'])}):")
            for item in result["critical_items"][:3]:
                print(f"    • {item['name']}: {item['percentage']:.1f}%")
        
        if result.get("recommendations"):
            print(f"  - Recommendations:")
            for rec in result["recommendations"]:
                print(f"    • {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_expiring_items_check():
    """Test 4: Check Expiring Items"""
    print_test_header("Expiring Items Check")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        inventory = setup_test_inventory(db, user.id)
        
        agent = TrackingAgent(db, user.id)
        result = agent.check_expiring_items()
        
        assert_true(result["success"], "Expiring items checked")
        
        print(f"\n⏰ Expiring Items Status:")
        print(f"  - Total expiring: {result.get('expiring_count', 0)}")
        
        if result.get("expiring_items"):
            for item in result["expiring_items"]:
                print(f"  - {item['item']}: expires in {item['days_until_expiry']} days")
                print(f"    Quantity: {item['quantity']}g, Priority: {item['priority']}")
        
        if result.get("recommendations"):
            print(f"\n💡 Recommendations:")
            for rec in result["recommendations"]:
                print(f"  - {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_restock_list_generation():
    """Test 5: Generate Restock List"""
    print_test_header("Restock List Generation")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        inventory = setup_test_inventory(db, user.id)
        
        agent = TrackingAgent(db, user.id)
        result = agent.generate_restock_list()
        
        assert_true(result["success"], "Restock list generated")
        assert_true("restock_list" in result, "Has restock list")
        
        print(f"\n🛒 Restock List:")
        
        for priority in ["urgent", "soon", "optional"]:
            items = result["restock_list"].get(priority, [])
            if items:
                print(f"\n  {priority.upper()} ({len(items)} items):")
                for item in items[:3]:  # Show first 3
                    print(f"    - {item['item']}")
                    print(f"      Current: {item['current_stock']}g")
                    print(f"      Suggested: {item['suggested_quantity']}g")
                    print(f"      Stock: {item['stock_percentage']:.1f}%")
        
        if result.get("shopping_strategy"):
            print(f"\n📋 Shopping Strategy:")
            for strategy in result["shopping_strategy"]:
                print(f"  - {strategy}")
        
        print(f"\n💰 Estimated Cost: ₹{result.get('estimated_cost', 0):.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

# ==================== CONSUMPTION SERVICE TESTS ====================

def test_consumption_today_summary():
    """Test 6: Get Today's Summary"""
    print_test_header("Today's Consumption Summary")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        meals = setup_test_meal_plan(db, user.id)
        
        service = ConsumptionService(db)
        result = service.get_today_summary(user.id)
        
        assert_true(result["success"], "Summary retrieved successfully")
        
        print(f"\n📅 Today's Summary ({result.get('date', 'unknown')}):")
        print(f"  - Meals planned: {result.get('meals_planned', 0)}")
        print(f"  - Meals consumed: {result.get('meals_consumed', 0)}")
        print(f"  - Meals skipped: {result.get('meals_skipped', 0)}")
        print(f"  - Meals pending: {result.get('meals_pending', 0)}")
        print(f"  - Compliance rate: {result.get('compliance_rate', 0):.1f}%")
        
        print(f"\n🔥 Nutrition:")
        print(f"  - Calories: {result.get('total_calories', 0):.0f}")
        macros = result.get('total_macros', {})
        print(f"  - Protein: {macros.get('protein_g', 0):.1f}g")
        print(f"  - Carbs: {macros.get('carbs_g', 0):.1f}g")
        print(f"  - Fat: {macros.get('fat_g', 0):.1f}g")
        
        if result.get("meals"):
            print(f"\n🍽️ Meal Details:")
            for meal in result["meals"]:
                print(f"  - {meal['meal_type'].capitalize()}: {meal['status']}")
                if meal['recipe']:
                    print(f"    Recipe: {meal['recipe']}")
        
        if result.get("recommendations"):
            print(f"\n💡 Recommendations:")
            for rec in result["recommendations"][:3]:
                print(f"  - {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_meal_patterns_analysis():
    """Test 7: Analyze Meal Patterns"""
    print_test_header("Meal Patterns Analysis")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        
        service = ConsumptionService(db)
        result = service.get_meal_patterns(user.id)
        
        assert_true(result["success"], "Patterns analyzed successfully")
        
        patterns = result.get("patterns", {})
        
        print(f"\n⏰ Meal Timing Patterns:")
        for meal_type, timing in patterns.get("meal_timing", {}).items():
            print(f"  - {meal_type}: avg {timing.get('average_time', 0):.1f}:00, {timing.get('consistency', 'unknown')}")
        
        print(f"\n❌ Skip Patterns:")
        for meal_type, data in patterns.get("skip_patterns", {}).items():
            print(f"  - {meal_type}: {data.get('skip_rate', 0):.1f}% skip rate")
        
        if patterns.get("favorite_recipes"):
            print(f"\n⭐ Favorite Recipes:")
            for recipe, count in list(patterns["favorite_recipes"].items())[:5]:
                print(f"  - {recipe}: {count} times")
        
        print(f"\n📊 Overall Compliance: {patterns.get('meal_compliance_rate', 0):.1f}%")
        
        if result.get("insights"):
            print(f"\n💡 Insights:")
            for insight in result["insights"][:3]:
                print(f"  - {insight}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_skip_meal_flow():
    """Test 8: Skip Meal and Adjustments"""
    print_test_header("Skip Meal Flow")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        meals = setup_test_meal_plan(db, user.id)
        
        # Find breakfast to skip
        breakfast = next((m for m in meals if m.meal_type == "breakfast" and not m.was_skipped), None)
        
        if not breakfast:
            print("⚠️ No breakfast to skip")
            return False
        
        service = ConsumptionService(db)
        result = service.skip_meal(
            user_id=user.id,
            meal_log_id=breakfast.id,
            reason="Woke up late"
        )
        
        assert_true(result["success"], "Meal skipped successfully")
        
        print(f"\n⏭️ Skipped {result.get('meal_type', 'meal')}:")
        print(f"  - Reason: {result.get('reason', 'Unknown')}")
        
        if result.get("skip_analysis"):
            analysis = result["skip_analysis"]
            print(f"\n📊 Skip Analysis:")
            print(f"  - Total planned: {analysis.get('total_planned', 0)}")
            print(f"  - Total skipped: {analysis.get('total_skipped', 0)}")
            print(f"  - Skip rate: {analysis.get('skip_rate', 0):.1f}%")
        
        if result.get("adjusted_targets"):
            targets = result["adjusted_targets"]
            if targets.get("meal_adjustments"):
                print(f"\n🎯 Adjusted Targets for Remaining Meals:")
                for adj in targets["meal_adjustments"][:3]:
                    print(f"  - {adj['meal_type']}: {adj['suggested_portion']:.2f}x portion")
        
        print(f"\n💡 Recommendation: {result.get('recommendation', 'None')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

# ==================== INTEGRATION TESTS ====================

def test_complete_meal_flow():
    """Test 9: Complete Meal Logging Flow"""
    print_test_header("Complete Meal Logging Flow")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        inventory = setup_test_inventory(db, user.id)
        meals = setup_test_meal_plan(db, user.id)
        
        print("\n🔄 Testing complete flow: Log → Deduct → Update → Analyze")
        
        # Find dinner to log
        dinner = next((m for m in meals if m.meal_type == "dinner" and not m.consumed_datetime), None)
        
        if not dinner:
            print("⚠️ No unconsumed dinner found")
            return False
        
        # Step 1: Log meal via consumption service
        print("\n1️⃣ Logging meal via ConsumptionService...")
        service = ConsumptionService(db)
        log_result = service.log_meal(
            user_id=user.id,
            meal_log_id=dinner.id,
            portion_multiplier=1.25,  # Larger portion
            notes="Extra hungry after workout"
        )
        
        assert_true(log_result["success"], "Meal logged via service")
        print(f"   Calories: {log_result.get('macros_consumed', {}).get('calories', 0):.0f}")
        
        # Step 2: Check inventory was deducted
        print("\n2️⃣ Checking inventory deduction...")
        agent = TrackingAgent(db, user.id)
        inv_status = agent.calculate_inventory_status()
        print(f"   Overall inventory: {inv_status.get('overall_percentage', 0):.1f}%")
        
        # Step 3: Check daily progress
        print("\n3️⃣ Checking daily progress...")
        summary = service.get_today_summary(user.id)
        print(f"   Meals consumed today: {summary.get('meals_consumed', 0)}")
        print(f"   Total calories: {summary.get('total_calories', 0):.0f}")
        print(f"   Compliance rate: {summary.get('compliance_rate', 0):.1f}%")
        
        # Step 4: Check if restock needed
        print("\n4️⃣ Checking restock needs...")
        restock = agent.generate_restock_list()
        urgent_count = len(restock.get("restock_list", {}).get("urgent", []))
        print(f"   Urgent restock items: {urgent_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

def test_ocr_normalization_fix():
    """Test 10: Fixed OCR to Normalization Flow"""
    print_test_header("OCR Text Parsing and Normalization (Fixed)")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        
        # Create test OCR text
        ocr_text = """
        GROCERY STORE RECEIPT
        2 kg Tomatoes
        1 L Milk
        500g Chicken Breast
        250g Rice
        1 bunch Spinach
        """
        
        print(f"📄 OCR Text:\n{ocr_text}")
        
        # Initialize normalizer
        normalizer = IntelligentItemNormalizer(db)
        
        # Parse OCR text line by line (FIXED approach)
        lines = ocr_text.strip().split('\n')
        normalized_items = []
        
        print("\n🔄 Processing OCR lines:")
        for line in lines:
            line = line.strip()
            if not line or "RECEIPT" in line.upper():
                continue
            
            print(f"\n  Processing: '{line}'")
            
            # The normalizer expects the full text line, not a dict
            # It will extract quantity and unit internally
            result = normalizer.normalize(line)
            print("result", result['item'])
            
            if result["match_found"]:
                print(f"    ✅ Matched: {result['matched_item']['name']}")
                print(f"       Confidence: {result['confidence']:.2f}")
                print(f"       Quantity: {result['quantity_grams']}g")
                normalized_items.append(result)
            else:
                print(f"    ❌ No match found")
                if result.get("suggestions"):
                    print(f"       Suggestions: {', '.join(s['name'] for s in result['suggestions'][:3])}")
        
        print(f"\n📊 Normalization Results:")
        print(f"  - Lines processed: {len([l for l in lines if l.strip() and 'RECEIPT' not in l.upper()])}")
        print(f"  - Items matched: {len(normalized_items)}")
        print(f"  - Success rate: {(len(normalized_items) / max(1, len([l for l in lines if l.strip() and 'RECEIPT' not in l.upper()]))) * 100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(traceback.format_exc())
        test_results["errors"].append(str(e))
        return False
    finally:
        db.close()

# ==================== MAIN TEST RUNNER ====================

def run_all_tests():
    """Run all Day 6 tests"""
    print("\n" + "="*60)
    print(" DAY 6 COMPLETE TEST SUITE ")
    print("="*60)
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # List of all test functions
    tests = [
        ("Tracking Agent Initialization", test_tracking_agent_initialization),
        ("Meal Consumption Logging", test_meal_consumption_logging),
        ("Inventory Status Calculation", test_inventory_status_calculation),
        ("Expiring Items Check", test_expiring_items_check),
        ("Restock List Generation", test_restock_list_generation),
        ("Today's Consumption Summary", test_consumption_today_summary),
        ("Meal Patterns Analysis", test_meal_patterns_analysis),
        ("Skip Meal Flow", test_skip_meal_flow),
        ("Complete Meal Flow", test_complete_meal_flow),
        ("OCR Normalization Fix", test_ocr_normalization_fix)
    ]
    
    # Run each test
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {str(e)}")
            test_results["errors"].append(f"{test_name}: {str(e)}")
    
    # Print summary
    print("\n" + "="*60)
    print(" TEST RESULTS SUMMARY ")
    print("="*60)
    
    total_tests = len(test_results["passed"]) + len(test_results["failed"])
    pass_rate = (len(test_results["passed"]) / max(1, total_tests)) * 100
    
    print(f"\n✅ Passed: {len(test_results['passed'])}")
    print(f"❌ Failed: {len(test_results['failed'])}")
    print(f"⚠️  Errors: {len(test_results['errors'])}")
    print(f"\n📊 Pass Rate: {pass_rate:.1f}%")
    
    if test_results["failed"]:
        print("\n❌ Failed Assertions:")
        for failure in test_results["failed"][:5]:  # Show first 5
            print(f"  - {failure}")
    
    if test_results["errors"]:
        print("\n⚠️ Errors Encountered:")
        for error in test_results["errors"][:5]:  # Show first 5
            print(f"  - {error}")
    
    print(f"\n✅ Testing completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return pass_rate >= 70  # Consider successful if 70% or more tests pass

if __name__ == "__main__":
    # Check database connection first
    print("🔌 Checking database connection...")
    try:
        db = SessionLocal()
        user_count = db.query(User).count()
        recipe_count = db.query(Recipe).count()
        item_count = db.query(Item).count()
        
        print(f"✅ Database connected successfully!")
        print(f"   - Users: {user_count}")
        print(f"   - Recipes: {recipe_count}")
        print(f"   - Items: {item_count}")
        
        if recipe_count == 0:
            print("⚠️ Warning: No recipes in database. Some tests may fail.")
        if item_count == 0:
            print("⚠️ Warning: No items in database. Some tests may fail.")
        
        db.close()
        
        # Run tests
        success = run_all_tests()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Failed to connect to database: {str(e)}")
        print(f"   Make sure your database is running and configured correctly.")
        sys.exit(1)