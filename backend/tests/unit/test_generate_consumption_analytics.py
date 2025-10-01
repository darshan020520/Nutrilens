"""
Focused test for generate_consumption_analytics() function only
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
    """Create test data with pattern-rich history"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_analytics_{datetime.now().timestamp()}@test.com",
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
        
        # Create meals for past 14 days with patterns
        meal_logs = []
        for days_ago in range(14):
            past_date = date.today() - timedelta(days=days_ago)
            day_of_week = past_date.weekday()  # 0=Monday, 6=Sunday
            
            # Skip more meals on weekends
            skip_dinner = day_of_week >= 5  # Weekend
            
            meals = [
                ("breakfast", 8, False),
                ("lunch", 12, False),
                ("dinner", 19, skip_dinner)
            ]
            
            for meal_type, hour, skip in meals:
                planned_time = datetime.combine(past_date, datetime.min.time()) + timedelta(hours=hour)
                
                meal_log = MealLog(
                    user_id=user.id,
                    recipe_id=recipe.id,
                    meal_type=meal_type,
                    planned_datetime=planned_time,
                    consumed_datetime=planned_time + timedelta(minutes=30) if not skip else None,
                    was_skipped=skip,
                    skip_reason="Weekend plans" if skip else None,
                    portion_multiplier=1.0 if not skip else None
                )
                db.add(meal_log)
                meal_logs.append(meal_log)
        
        db.flush()
        db.commit()
        
        print(f"✅ Setup: User {user.id}, {len(meal_logs)} meals across 14 days")
        
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

def test_generate_consumption_analytics(test_data):
    """Test generate_consumption_analytics() function"""
    
    print("\n" + "="*60)
    print("Testing: generate_consumption_analytics()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Generate 7-day analytics
    print("\n[Test 1] Generate 7-day analytics")
    db1 = SessionLocal()
    service1 = ConsumptionService(db1)
    
    result = service1.generate_consumption_analytics(
        user_id=test_data["user_id"],
        days=7
    )

    print("7-day analytics", result)
    db1.close()
    
    # Validate structure
    is_success = result.get("success", False)
    print_result("Returns success=True", is_success,
                f"Error: {result.get('error', 'None')}" if not is_success else "")
    
    if is_success:
        has_period = "period_days" in result
        print_result("Has period_days", has_period)
        
        period_correct = result.get("period_days") == 7
        print_result("period_days = 7", period_correct,
                    f"Got {result.get('period_days')}")
        
        has_analytics = "analytics" in result
        print_result("Has analytics key", has_analytics)
        
        if has_analytics:
            analytics = result["analytics"]
            analytics_count = len(analytics)
            has_data = analytics_count > 0
            print_result("Analytics has data", has_data,
                        f"Found {analytics_count} analysis types")
            
            # Check for expected analysis types
            print("\n[Expected Analysis Types]")
            
            expected_types = [
                "meal_timing_patterns",
                "skip_frequency",
                "portion_trends",
                "favorite_recipes",
                "daily_compliance",
                "macro_consistency"
            ]
            
            for analysis_type in expected_types:
                has_type = analysis_type in analytics
                print_result(f"Has {analysis_type}", has_type)
    
    # TEST 2: Generate 30-day analytics
    print("\n[Test 2] Generate 30-day analytics")
    db2 = SessionLocal()
    service2 = ConsumptionService(db2)
    
    result_30 = service2.generate_consumption_analytics(
        user_id=test_data["user_id"],
        days=30
    )

    print("30-day analytics", result_30)
    db2.close()
    
    is_success = result_30.get("success", False)
    print_result("30-day analytics succeeds", is_success)
    
    if is_success:
        period_30 = result_30.get("period_days") == 30
        print_result("period_days = 30", period_30,
                    f"Got {result_30.get('period_days')}")
    
    # TEST 3: Empty data case
    print("\n[Test 3] Handle user with no data")
    db3 = SessionLocal()
    service3 = ConsumptionService(db3)
    
    result_empty = service3.generate_consumption_analytics(
        user_id=999999,
        days=7
    )
    db3.close()
    
    is_success = result_empty.get("success", False)
    print_result("Returns success even with no data", is_success)
    
    has_message = "message" in result_empty
    print_result("Has informative message", has_message,
                f"Message: {result_empty.get('message', 'None')}")
    
    # TEST 4: Validate skip frequency analysis
    if result.get("success") and "analytics" in result:
        analytics = result["analytics"]
        
        if "skip_frequency" in analytics:
            print("\n[Test 4] Skip frequency analysis")
            skip_freq = analytics["skip_frequency"]
            
            is_dict = isinstance(skip_freq, dict)
            print_result("skip_frequency is dict", is_dict)
            
            # Based on setup, dinner should have skips on weekends
            if is_dict and "by_meal_type" in skip_freq:
                by_meal = skip_freq["by_meal_type"]
                has_dinner = "dinner" in by_meal
                print_result("Tracks dinner skips", has_dinner)
    
    # TEST 5: Total meals analyzed
    print("\n[Test 5] Total meals analyzed")
    if result.get("success"):
        has_total = "total_meals_analyzed" in result
        print_result("Has total_meals_analyzed", has_total)
        
        if has_total:
            total = result["total_meals_analyzed"]
            # Should have 7 days * 3 meals = 21 meals
            total_reasonable = 15 <= total <= 25
            print_result("Total meals is reasonable", total_reasonable,
                        f"Got {total} meals")

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
    print("FOCUSED TEST: generate_consumption_analytics() ONLY")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_generate_consumption_analytics(test_data)
        cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")