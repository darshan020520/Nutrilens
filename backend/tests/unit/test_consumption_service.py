"""
Day 6 Testing - Component 1: Consumption Service
FIXED: Correct function signatures and transaction management

Tests:
1. log_meal_consumption()
2. get_today_summary()
3. get_consumption_history()
4. handle_skip_meal()
5. generate_consumption_analytics()
"""

import sys
import os
from datetime import datetime, timedelta, date
from typing import Dict, Any
import json

# Add backend to path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine, and_, func, text
from sqlalchemy.orm import sessionmaker, Session
from app.models.database import (
    Base, User, UserProfile, UserGoal, UserPath, UserPreference,
    Recipe, RecipeIngredient, Item, MealLog, UserInventory, MealPlan
)
from app.services.consumption_services import ConsumptionService
from app.core.config import settings
def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create minimal test data"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Create profile
        profile = UserProfile(
            user_id=user.id,
            name="Test",
            age=25,
            height_cm=178.0,
            weight_kg=70.0,
            sex="male",
            activity_level="MODERATELY_ACTIVE",
            bmr=1692.5,
            tdee=2623.38,
            goal_calories=3123.38
        )
        db.add(profile)
        
        # Create goal
        goal = UserGoal(
            user_id=user.id,
            goal_type="MUSCLE_GAIN",
            target_weight=85.0,
            macro_targets={"protein": 0.3, "carbs": 0.45, "fat": 0.25},
            is_active=True
        )
        db.add(goal)
        db.flush()
        
        # Get an actual recipe
        recipe = db.query(Recipe).first()
        if not recipe:
            print("❌ ERROR: No recipes in database. Cannot test.")
            db.close()
            return None
        
        # Create meal log
        meal_log = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="breakfast",
            planned_datetime=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=8),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        db.add(meal_log)
        db.flush()
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}, MealLog {meal_log.id}, Recipe {recipe.id}")
        
        return {
            "user_id": user.id,
            "meal_log_id": meal_log.id,
            "recipe_id": recipe.id,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        db.close()
        return None

def test_log_meal_consumption(test_data):
    """Test ONLY log_meal_consumption() function"""
    
    print("\n" + "="*60)
    print("Testing: log_meal_consumption()")
    print("="*60)
    
    # Get fresh session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Basic meal logging
    print("\n[Test 1] Basic meal logging with meal_log_id")
    db1 = SessionLocal()
    service1 = ConsumptionService(db1)
    
    meal_data = {
        "meal_log_id": test_data["meal_log_id"],
        "portion_multiplier": 1.0,
        "timestamp": datetime.utcnow()
    }
    
    result = service1.log_meal_consumption(test_data["user_id"], meal_data)
    if result["status"] == "success":
        db1.commit()
    db1.close()
    
    # Check result
    has_status = "status" in result
    print_result("Returns status key", has_status, f"Keys: {list(result.keys())}")
    
    if has_status:
        is_success = result["status"] == "success"
        print_result("Status is 'success'", is_success, f"Status: {result.get('status')}")
        
        if not is_success:
            print(f"     └─ Error: {result.get('error', 'Unknown')}")
    
    # Verify database update
    print("\n[Test 2] Database was actually updated")
    db2 = SessionLocal()
    meal_log = db2.query(MealLog).filter(MealLog.id == test_data["meal_log_id"]).first()
    
    was_updated = meal_log and meal_log.consumed_datetime is not None
    print_result("consumed_datetime is set", was_updated, 
                f"Value: {meal_log.consumed_datetime if meal_log else 'MealLog not found'}")
    
    portion_correct = meal_log and meal_log.portion_multiplier == 1.0
    print_result("portion_multiplier is correct", portion_correct,
                f"Value: {meal_log.portion_multiplier if meal_log else 'N/A'}")
    
    db2.close()
    
    # TEST 3: Duplicate prevention
    print("\n[Test 3] Prevents duplicate logging")
    db3 = SessionLocal()
    service3 = ConsumptionService(db3)
    
    result_dup = service3.log_meal_consumption(test_data["user_id"], meal_data)
    db3.close()
    
    is_error = result_dup.get("status") == "error"
    print_result("Returns error status", is_error, f"Status: {result_dup.get('status')}")
    
    has_error_msg = "error" in result_dup and "already" in result_dup.get("error", "").lower()
    print_result("Error message mentions 'already'", has_error_msg,
                f"Error: {result_dup.get('error', 'None')}")
    
    # TEST 4: Invalid meal_log_id
    print("\n[Test 4] Handles invalid meal_log_id")
    db4 = SessionLocal()
    service4 = ConsumptionService(db4)
    
    invalid_data = {
        "meal_log_id": 999999,
        "portion_multiplier": 1.0,
        "timestamp": datetime.utcnow()
    }
    
    result_invalid = service4.log_meal_consumption(test_data["user_id"], invalid_data)
    db4.close()
    
    is_error = result_invalid.get("status") == "error"
    print_result("Returns error status", is_error, f"Status: {result_invalid.get('status')}")
    
    has_not_found = "error" in result_invalid and "not found" in result_invalid.get("error", "").lower()
    print_result("Error message says 'not found'", has_not_found,
                f"Error: {result_invalid.get('error', 'None')}")
    
    # TEST 5: Response structure
    if result.get("status") == "success":
        print("\n[Test 5] Response structure validation")
        
        has_logged_meal = "logged_meal" in result
        print_result("Has 'logged_meal' key", has_logged_meal)
        
        has_updated_totals = "updated_totals" in result
        print_result("Has 'updated_totals' key", has_updated_totals)
        
        has_remaining = "remaining_targets" in result
        print_result("Has 'remaining_targets' key", has_remaining)
        
        if has_logged_meal:
            logged = result["logged_meal"]
            has_macros = "macros" in logged
            print_result("logged_meal has macros", has_macros,
                        f"Macros: {logged.get('macros', {})}")

def cleanup(test_data):
    """Clean up test data"""
    print("\n" + "="*60)
    print("Cleanup")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
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
    print("FOCUSED TEST: log_meal_consumption() ONLY")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_log_meal_consumption(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")