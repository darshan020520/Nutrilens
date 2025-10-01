"""
Focused test for get_consumption_history() function only
"""

import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, Recipe, MealLog
from app.services.consumption_services import ConsumptionService
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data with historical meals"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_history_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Get recipe
        recipe = db.query(Recipe).first()
        if not recipe:
            print("❌ ERROR: No recipes in database")
            db.close()
            return None
        
        # Create meals for past 10 days
        meal_logs = []
        for days_ago in range(10):
            past_date = date.today() - timedelta(days=days_ago)
            
            # Create 3 meals per day (2 consumed, 1 skipped)
            for meal_num, (meal_type, consumed) in enumerate([
                ("breakfast", True),
                ("lunch", True),
                ("dinner", False)  # Skipped
            ]):
                planned_time = datetime.combine(past_date, datetime.min.time()) + timedelta(hours=8 + (meal_num * 4))
                
                meal_log = MealLog(
                    user_id=user.id,
                    recipe_id=recipe.id,
                    meal_type=meal_type,
                    planned_datetime=planned_time,
                    consumed_datetime=planned_time + timedelta(minutes=30) if consumed else None,
                    was_skipped=not consumed,
                    skip_reason="Not hungry" if not consumed else None,
                    portion_multiplier=1.0
                )
                db.add(meal_log)
                meal_logs.append(meal_log)
        
        db.flush()
        db.commit()
        
        print(f"✅ Setup: User {user.id}, {len(meal_logs)} meals across 10 days")
        
        return {
            "user_id": user.id,
            "meal_logs": meal_logs,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_get_consumption_history(test_data):
    """Test get_consumption_history() function"""
    
    print("\n" + "="*60)
    print("Testing: get_consumption_history()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Get 7-day history
    print("\n[Test 1] Get 7-day history")
    db1 = SessionLocal()
    service1 = ConsumptionService(db1)
    
    result = service1.get_consumption_history(
        user_id=test_data["user_id"],
        days=7,
        include_details=True
    )
    print("Get 7-day history", result)
    db1.close()
    
    # Validate structure
    is_success = result.get("success", False)
    print_result("Returns success=True", is_success,
                f"Error: {result.get('error', 'None')}" if not is_success else "")
    
    if is_success:
        has_user_id = "user_id" in result
        print_result("Has user_id", has_user_id)
        
        has_period = "period_days" in result
        print_result("Has period_days", has_period)
        
        period_correct = result.get("period_days") == 7
        print_result("period_days = 7", period_correct,
                    f"Got {result.get('period_days')}")
        
        has_history = "history" in result
        print_result("Has history key", has_history)
        
        if has_history:
            history = result["history"]
            history_count = len(history)
            has_data = history_count > 0
            print_result("History has data", has_data,
                        f"Found {history_count} days")
            
            # Check first day structure
            if history_count > 0:
                first_day_key = list(history.keys())[0]
                first_day = history[first_day_key]
                
                has_planned = "planned" in first_day
                print_result("Day has 'planned' count", has_planned)
                
                has_consumed = "consumed" in first_day
                print_result("Day has 'consumed' count", has_consumed)
                
                has_skipped = "skipped" in first_day
                print_result("Day has 'skipped' count", has_skipped)
                
                has_calories = "calories" in first_day
                print_result("Day has 'calories'", has_calories)
    
    # TEST 2: Get 30-day history
    print("\n[Test 2] Get 30-day history")
    db2 = SessionLocal()
    service2 = ConsumptionService(db2)
    
    result_30 = service2.get_consumption_history(
        user_id=test_data["user_id"],
        days=30,
        include_details=False
    )
    print("Get result_30 history", result_30)
    db2.close()
    
    is_success = result_30.get("success", False)
    print_result("30-day query succeeds", is_success)
    
    if is_success:
        period_30 = result_30.get("period_days") == 30
        print_result("period_days = 30", period_30,
                    f"Got {result_30.get('period_days')}")
    
    # TEST 3: include_details flag
    print("\n[Test 3] include_details flag works")
    db3 = SessionLocal()
    service3 = ConsumptionService(db3)
    
    result_with_details = service3.get_consumption_history(
        user_id=test_data["user_id"],
        days=7,
        include_details=True
    )

    print("result_with_details", result_with_details)
    
    result_without_details = service3.get_consumption_history(
        user_id=test_data["user_id"],
        days=7,
        include_details=False
    )

    print("result_without_details", result_without_details)

    db3.close()
    
    if result_with_details.get("success") and result_without_details.get("success"):
        # With details should have meals array
        with_has_meals = False
        if result_with_details.get("history"):
            first_day = list(result_with_details["history"].values())[0]
            with_has_meals = "meals" in first_day and first_day["meals"] is not None
        
        print_result("With details has meals array", with_has_meals)
        
        # Without details should NOT have meals
        without_no_meals = True
        if result_without_details.get("history"):
            first_day = list(result_without_details["history"].values())[0]
            without_no_meals = "meals" not in first_day or first_day["meals"] is None
        
        print_result("Without details has no meals", without_no_meals)
    
    # TEST 4: Statistics
    print("\n[Test 4] Statistics calculation")
    if result.get("success") and "statistics" in result:
        stats = result["statistics"]
        
        has_total_planned = "total_meals_planned" in stats
        print_result("Has total_meals_planned", has_total_planned)
        
        has_total_consumed = "total_meals_consumed" in stats
        print_result("Has total_meals_consumed", has_total_consumed)
        
        has_compliance = "overall_compliance" in stats
        print_result("Has overall_compliance", has_compliance)
        
        if has_compliance:
            compliance = stats["overall_compliance"]
            # Should be about 66.7% (2 consumed out of 3 per day)
            compliance_reasonable = 60 <= compliance <= 75
            print_result("Compliance is reasonable", compliance_reasonable,
                        f"Got {compliance}%")

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
    print("FOCUSED TEST: get_consumption_history() ONLY")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_get_consumption_history(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")