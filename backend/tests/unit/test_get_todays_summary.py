"""
Focused test for get_today_summary() function only
"""

import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, UserProfile, UserGoal, Recipe, MealLog
from app.services.consumption_services import ConsumptionService
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data with various meal states"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_consumption_user12@test.com",
            hashed_password="Test@123",
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
            goal_calories=2500.0
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
        
        # Get recipe
        recipe = db.query(Recipe).first()
        if not recipe:
            print("❌ ERROR: No recipes in database")
            db.close()
            return None
        
        today = date.today()
        
        # Create 4 meals: 2 consumed, 1 skipped, 1 pending
        meals = [
            {
                "meal_type": "breakfast",
                "time": 8,
                "consumed": True,
                "skipped": False
            },
            {
                "meal_type": "lunch",
                "time": 12,
                "consumed": True,
                "skipped": False
            },
            {
                "meal_type": "snack",
                "time": 16,
                "consumed": False,
                "skipped": True
            },
            {
                "meal_type": "dinner",
                "time": 19,
                "consumed": False,
                "skipped": False
            }
        ]
        
        meal_logs = []
        for meal in meals:
            planned_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=meal["time"])
            
            meal_log = MealLog(
                user_id=user.id,
                recipe_id=recipe.id,
                meal_type=meal["meal_type"],
                planned_datetime=planned_time,
                consumed_datetime=planned_time + timedelta(minutes=30) if meal["consumed"] else None,
                was_skipped=meal["skipped"],
                skip_reason="Not hungry" if meal["skipped"] else None,
                portion_multiplier=1.0
            )
            db.add(meal_log)
            meal_logs.append(meal_log)
        
        db.flush()
        db.commit()
        
        print(f"✅ Setup: User {user.id}, 4 meals (2 consumed, 1 skipped, 1 pending)")
        
        return {
            "user_id": user.id,
            "meal_logs": meal_logs,
            "recipe": recipe,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_get_today_summary(test_data):
    """Test get_today_summary() function"""
    
    print("\n" + "="*60)
    print("Testing: get_today_summary()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Get today's summary
    print("\n[Test 1] Get today's summary")
    db1 = SessionLocal()
    service1 = ConsumptionService(db1)
    
    start_time = datetime.now()
    result = service1.get_today_summary(test_data["user_id"])

    print("result", result)
    end_time = datetime.now()
    duration_ms = (end_time - start_time).total_seconds() * 1000
    
    db1.close()
    
    # Validate structure
    print("\n[Response Structure]")
    
    has_date = "date" in result
    print_result("Has 'date' key", has_date)
    
    has_meals_planned = "meals_planned" in result
    print_result("Has 'meals_planned' key", has_meals_planned)
    
    has_meals_consumed = "meals_consumed" in result
    print_result("Has 'meals_consumed' key", has_meals_consumed)
    
    has_meals_skipped = "meals_skipped" in result
    print_result("Has 'meals_skipped' key", has_meals_skipped)
    
    has_total_calories = "total_calories" in result
    print_result("Has 'total_calories' key", has_total_calories)
    
    has_total_macros = "total_macros" in result
    print_result("Has 'total_macros' key", has_total_macros)
    
    # Validate data accuracy
    print("\n[Data Accuracy]")
    
    meals_planned_correct = result.get("meals_planned") == 4
    print_result("meals_planned = 4", meals_planned_correct,
                f"Got {result.get('meals_planned')}")
    
    meals_consumed_correct = result.get("meals_consumed") == 2
    print_result("meals_consumed = 2", meals_consumed_correct,
                f"Got {result.get('meals_consumed')}")
    
    meals_skipped_correct = result.get("meals_skipped") == 1
    print_result("meals_skipped = 1", meals_skipped_correct,
                f"Got {result.get('meals_skipped')}")
    
    # Check if macros exist
    if has_total_macros:
        macros = result["total_macros"]
        has_protein = "protein_g" in macros
        has_carbs = "carbs_g" in macros
        has_fat = "fat_g" in macros
        
        print_result("total_macros has protein_g", has_protein)
        print_result("total_macros has carbs_g", has_carbs)
        print_result("total_macros has fat_g", has_fat)
    
    # Validate performance
    print("\n[Performance]")
    performance_ok = duration_ms < 100
    print_result("Executes in < 100ms", performance_ok,
                f"Took {duration_ms:.2f}ms")
    
    # TEST 2: Non-existent user
    print("\n[Test 2] Non-existent user returns empty")
    db2 = SessionLocal()
    service2 = ConsumptionService(db2)
    
    result_empty = service2.get_today_summary(999999)
    db2.close()
    
    empty_planned = result_empty.get("meals_planned", 0) == 0
    print_result("meals_planned = 0 for invalid user", empty_planned,
                f"Got {result_empty.get('meals_planned')}")
    
    # TEST 3: Has compliance rate
    print("\n[Test 3] Compliance rate calculation")
    has_compliance = "compliance_rate" in result
    print_result("Has compliance_rate", has_compliance)
    
    if has_compliance:
        # Should be (2 consumed / 4 planned) * 100 = 50%
        expected_rate = 50.0
        actual_rate = result["compliance_rate"]
        rate_correct = abs(actual_rate - expected_rate) < 1.0
        print_result("Compliance rate = 50%", rate_correct,
                    f"Got {actual_rate}%")

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
    print("FOCUSED TEST: get_today_summary() ONLY")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_get_today_summary(test_data)
        #cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")