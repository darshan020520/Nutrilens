"""
Focused test for handle_skip_meal() function only
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
    """Create minimal test data"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_skip_{datetime.now().timestamp()}@test.com",
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
        
        # Get recipe
        recipe = db.query(Recipe).first()
        if not recipe:
            print("❌ ERROR: No recipes in database")
            db.close()
            return None
        
        # Create TWO meal logs (one to skip, one already skipped)
        meal_log_1 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="breakfast",
            planned_datetime=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=8),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        db.add(meal_log_1)
        
        meal_log_2 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="lunch",
            planned_datetime=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=12),
            consumed_datetime=None,
            was_skipped=True,  # Already skipped
            skip_reason="Previous test",
            portion_multiplier=1.0
        )
        db.add(meal_log_2)
        
        meal_log_3 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="dinner",
            planned_datetime=datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=19),
            consumed_datetime=datetime.utcnow(),  # Already consumed
            was_skipped=False,
            portion_multiplier=1.0
        )
        db.add(meal_log_3)
        
        db.flush()
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}, MealLogs {meal_log_1.id}, {meal_log_2.id}, {meal_log_3.id}")
        
        return {
            "user_id": user.id,
            "meal_log_to_skip": meal_log_1.id,
            "already_skipped": meal_log_2.id,
            "already_consumed": meal_log_3.id,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_handle_skip_meal(test_data):
    """Test handle_skip_meal() function"""
    
    print("\n" + "="*60)
    print("Testing: handle_skip_meal()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Skip a valid meal
    print("\n[Test 1] Skip a valid meal")
    db1 = SessionLocal()
    service1 = ConsumptionService(db1)
    
    meal_info = {
        "meal_log_id": test_data["meal_log_to_skip"],
        "reason": "Not hungry"
    }
    
    result = service1.handle_skip_meal(
        user_id=test_data["user_id"],
        meal_info=meal_info
    )
    
    # Commit the transaction
    if result.get("success"):
        db1.commit()
    db1.close()
    
    # Validate result
    is_success = result.get("success", False)
    print_result("Returns success=True", is_success)
    
    if is_success:
        has_meal_log_id = "meal_log_id" in result
        print_result("Has meal_log_id in response", has_meal_log_id)
        
        has_meal_type = "meal_type" in result
        print_result("Has meal_type in response", has_meal_type)
        
        has_reason = result.get("reason") == "Not hungry"
        print_result("Reason is correct", has_reason, f"Reason: {result.get('reason')}")
    else:
        print(f"     └─ Error: {result.get('error')}")
    
    # Verify database update
    print("\n[Test 2] Database was actually updated")
    db2 = SessionLocal()
    meal_log = db2.query(MealLog).filter(
        MealLog.id == test_data["meal_log_to_skip"]
    ).first()
    
    was_skipped_set = meal_log and meal_log.was_skipped is True
    print_result("was_skipped = True", was_skipped_set,
                f"Value: {meal_log.was_skipped if meal_log else 'Not found'}")
    
    reason_set = meal_log and meal_log.skip_reason == "Not hungry"
    print_result("skip_reason is correct", reason_set,
                f"Value: {meal_log.skip_reason if meal_log else 'Not found'}")
    
    consumed_is_none = meal_log and meal_log.consumed_datetime is None
    print_result("consumed_datetime is None", consumed_is_none,
                f"Value: {meal_log.consumed_datetime if meal_log else 'Not found'}")
    
    db2.close()
    
    # TEST 3: Try to skip already skipped meal
    print("\n[Test 3] Prevent skipping already skipped meal")
    db3 = SessionLocal()
    service3 = ConsumptionService(db3)
    
    meal_info_dup = {
        "meal_log_id": test_data["already_skipped"],
        "reason": "Test"
    }
    
    result_dup = service3.handle_skip_meal(
        user_id=test_data["user_id"],
        meal_info=meal_info_dup
    )
    db3.close()
    
    is_error = not result_dup.get("success", True)
    print_result("Returns success=False", is_error,
                f"Success: {result_dup.get('success')}")
    
    has_error_msg = "error" in result_dup
    print_result("Has error message", has_error_msg,
                f"Error: {result_dup.get('error', 'None')}")
    
    mentions_skipped = has_error_msg and "skip" in result_dup.get("error", "").lower()
    print_result("Error mentions 'skip'", mentions_skipped)
    
    # TEST 4: Try to skip consumed meal
    print("\n[Test 4] Prevent skipping consumed meal")
    db4 = SessionLocal()
    service4 = ConsumptionService(db4)
    
    meal_info_consumed = {
        "meal_log_id": test_data["already_consumed"],
        "reason": "Test"
    }
    
    result_consumed = service4.handle_skip_meal(
        user_id=test_data["user_id"],
        meal_info=meal_info_consumed
    )
    db4.close()
    
    is_error = not result_consumed.get("success", True)
    print_result("Returns success=False", is_error)
    
    mentions_consumed = "error" in result_consumed and "consum" in result_consumed.get("error", "").lower()
    print_result("Error mentions 'consumed'", mentions_consumed,
                f"Error: {result_consumed.get('error', 'None')}")
    
    # TEST 5: Invalid meal_log_id
    print("\n[Test 5] Handle invalid meal_log_id")
    db5 = SessionLocal()
    service5 = ConsumptionService(db5)
    
    meal_info_invalid = {
        "meal_log_id": 999999,
        "reason": "Test"
    }
    
    result_invalid = service5.handle_skip_meal(
        user_id=test_data["user_id"],
        meal_info=meal_info_invalid
    )
    db5.close()
    
    is_error = not result_invalid.get("success", True)
    print_result("Returns success=False", is_error)
    
    not_found = "error" in result_invalid and "not found" in result_invalid.get("error", "").lower()
    print_result("Error says 'not found'", not_found,
                f"Error: {result_invalid.get('error', 'None')}")
    
    # TEST 6: Missing meal_log_id
    print("\n[Test 6] Handle missing meal_log_id")
    db6 = SessionLocal()
    service6 = ConsumptionService(db6)
    
    meal_info_missing = {
        "reason": "Test"
        # No meal_log_id
    }
    
    result_missing = service6.handle_skip_meal(
        user_id=test_data["user_id"],
        meal_info=meal_info_missing
    )
    db6.close()
    
    is_error = not result_missing.get("success", True)
    print_result("Returns success=False", is_error)
    
    mentions_required = "error" in result_missing and "required" in result_missing.get("error", "").lower()
    print_result("Error mentions 'required'", mentions_required,
                f"Error: {result_missing.get('error', 'None')}")

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
    print("FOCUSED TEST: handle_skip_meal() ONLY")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_handle_skip_meal(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")