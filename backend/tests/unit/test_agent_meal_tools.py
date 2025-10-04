"""
Test for Tracking Agent Meal Tools
Tests: log_meal_consumption() and track_skipped_meals()
These tools delegate to consumption service
"""

import sys
import os
from datetime import datetime, date, timedelta
import asyncio
from unittest.mock import Mock, patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, UserProfile, UserGoal, Recipe, MealLog, RecipeIngredient, UserInventory, Item
from app.agents.tracking_agent import TrackingAgent
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data for meal tracking"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_meal_tracking_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Create profile
        profile = UserProfile(
            user_id=user.id,
            name="Meal Tracker",
            age=28,
            height_cm=170.0,
            weight_kg=65.0,
            sex="female",
            activity_level="LIGHTLY_ACTIVE",
            bmr=1400.0,
            tdee=1960.0,
            goal_calories=1760.0
        )
        db.add(profile)
        
        # Create goal
        goal = UserGoal(
            user_id=user.id,
            goal_type="FAT_LOSS",
            target_weight=60.0,
            macro_targets={"protein": 0.3, "carbs": 0.4, "fat": 0.3},
            is_active=True
        )
        db.add(goal)
        db.flush()
        
        # Get a recipe with ingredients
        recipe = db.query(Recipe).first()
        if not recipe:
            print("❌ ERROR: No recipes in database")
            db.close()
            return None
        
        # Get recipe ingredients and create inventory
        ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe.id
        ).limit(3).all()
        
        for ingredient in ingredients:
            # Check if user already has this item
            existing = db.query(UserInventory).filter(
                UserInventory.user_id == user.id,
                UserInventory.item_id == ingredient.item_id
            ).first()
            
            if not existing:
                inventory = UserInventory(
                    user_id=user.id,
                    item_id=ingredient.item_id,
                    quantity_grams=ingredient.quantity_grams * 5,  # 5x the recipe amount
                    purchase_date=datetime.utcnow(),
                    expiry_date=datetime.utcnow() + timedelta(days=10),
                    source="manual"
                )
                db.add(inventory)
        
        # Create meal logs
        today = datetime.combine(date.today(), datetime.min.time())
        
        # Meal to log
        meal_log_1 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="breakfast",
            planned_datetime=today + timedelta(hours=8),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        db.add(meal_log_1)
        
        # Meal to skip
        meal_log_2 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="lunch",
            planned_datetime=today + timedelta(hours=13),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        db.add(meal_log_2)
        
        # Already consumed meal
        meal_log_3 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="snack",
            planned_datetime=today + timedelta(hours=16),
            consumed_datetime=datetime.utcnow(),
            was_skipped=False,
            portion_multiplier=1.0
        )
        db.add(meal_log_3)
        
        # Already skipped meal
        meal_log_4 = MealLog(
            user_id=user.id,
            recipe_id=recipe.id,
            meal_type="dinner",
            planned_datetime=today + timedelta(hours=19),
            consumed_datetime=None,
            was_skipped=True,
            skip_reason="Previous skip",
            portion_multiplier=1.0
        )
        db.add(meal_log_4)
        
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}, Recipe {recipe.id}")
        print(f"   MealLogs: {meal_log_1.id} (to log), {meal_log_2.id} (to skip)")
        print(f"   {meal_log_3.id} (consumed), {meal_log_4.id} (skipped)")
        
        return {
            "user_id": user.id,
            "recipe_id": recipe.id,
            "meal_to_log": meal_log_1.id,
            "meal_to_skip": meal_log_2.id,
            "already_consumed": meal_log_3.id,
            "already_skipped": meal_log_4.id,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_log_meal_consumption(test_data):
    """Test log_meal_consumption() delegates to service"""
    
    print("\n" + "="*60)
    print("Testing: log_meal_consumption()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Log a valid meal
    print("\n[Test 1] Log meal successfully")
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
        
                # Run async function
                result = asyncio.run(tracking_agent.log_meal_consumption(
                    meal_log_id=test_data["meal_to_log"],
                    portion_multiplier=1.0
                ))
        
                is_success = result.get("success", False)
                print_result("Returns success=True", is_success,
                            f"Error: {result.get('error', 'None')}")
        
                if is_success:
                    has_meal_type = "meal_type" in result
                    print_result("Has meal_type", has_meal_type,
                                f"Type: {result.get('meal_type')}")
            
                    has_recipe = "recipe" in result
                    print_result("Has recipe name", has_recipe,
                                f"Recipe: {result.get('recipe')}")
            
                    has_consumed_at = "consumed_at" in result
                    print_result("Has consumed_at timestamp", has_consumed_at)
            
                    has_macros = "macros" in result
                    print_result("Has macros_consumed", has_macros)
            
                    has_insights = "insights" in result
                    print_result("Has insights", has_insights)
            
                    has_recommendations = "recommendations" in result
                    print_result("Has recommendations", has_recommendations)
                    
                    # Verify WebSocket was called
                    print_result("WebSocket broadcast called", mock_ws.broadcast_to_user.called,
                                f"Call count: {mock_ws.broadcast_to_user.call_count}")
        
        db1.commit()
    finally:
        db1.close()
    
    # TEST 2: Verify database was updated
    print("\n[Test 2] Database updated correctly")
    db2 = SessionLocal()
    
    try:
        meal_log = db2.query(MealLog).filter(
            MealLog.id == test_data["meal_to_log"]
        ).first()
        
        consumed_set = meal_log and meal_log.consumed_datetime is not None
        print_result("consumed_datetime is set", consumed_set,
                    f"Time: {meal_log.consumed_datetime if meal_log else 'Not found'}")
        
        not_skipped = meal_log and meal_log.was_skipped is False
        print_result("was_skipped = False", not_skipped)
    finally:
        db2.close()
    
    # TEST 3: Test with portion multiplier
    print("\n[Test 3] Portion multiplier works")
    db3 = SessionLocal()
    
    try:
        # Create another meal log for portion test
        recipe_id = test_data["recipe_id"]
        meal_log_portion = MealLog(
            user_id=test_data["user_id"],
            recipe_id=recipe_id,
            meal_type="snack",
            planned_datetime=datetime.utcnow(),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        db3.add(meal_log_portion)
        db3.commit()
        db3.refresh(meal_log_portion)
        
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks for async calls
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db3, test_data["user_id"])
        
                result = asyncio.run(tracking_agent.log_meal_consumption(
                    meal_log_id=meal_log_portion.id,
                    portion_multiplier=2.0  # Double portion
                ))
        
                is_success = result.get("success", False)
                print_result("Accepts portion_multiplier=2.0", is_success)
        
                # Verify portion was applied
                db3.refresh(meal_log_portion)
                portion_saved = meal_log_portion.portion_multiplier == 2.0
                print_result("Portion multiplier saved", portion_saved,
                            f"Saved: {meal_log_portion.portion_multiplier}")
        
        db3.commit()
    finally:
        db3.close()
    
    # TEST 4: Invalid meal_log_id
    print("\n[Test 4] Handle invalid meal_log_id")
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
        
                result = asyncio.run(tracking_agent.log_meal_consumption(
                    meal_log_id=999999,
                    portion_multiplier=1.0
                ))
        
                is_error = not result.get("success", True)
                print_result("Returns success=False", is_error)
        
                has_error_msg = "error" in result
                print_result("Has error message", has_error_msg,
                            f"Error: {result.get('error', 'None')}")
    finally:
        db4.close()
    
    # TEST 5: Invalid portion multiplier
    print("\n[Test 5] Validate portion multiplier")
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
        
                # Test negative portion
                result_negative = asyncio.run(tracking_agent.log_meal_consumption(
                    meal_log_id=test_data["meal_to_log"],
                    portion_multiplier=-1.0
                ))
        
                is_error = not result_negative.get("success", True)
                print_result("Rejects negative portion", is_error,
                            f"Error: {result_negative.get('error', 'None')}")
        
                # Test too large portion
                result_large = asyncio.run(tracking_agent.log_meal_consumption(
                    meal_log_id=test_data["meal_to_log"],
                    portion_multiplier=10.0
                ))
        
                is_error = not result_large.get("success", True)
                print_result("Rejects portion > 5", is_error,
                            f"Error: {result_large.get('error', 'None')}")
    finally:
        db5.close()

def test_track_skipped_meals(test_data):
    """Test track_skipped_meals() delegates to service"""
    
    print("\n" + "="*60)
    print("Testing: track_skipped_meals()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1: Skip a valid meal
    print("\n[Test 1] Skip meal successfully")
    db1 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db1, test_data["user_id"])
        
                result = tracking_agent.track_skipped_meals(
                    meal_log_id=test_data["meal_to_skip"],
                    reason="Not feeling well"
                )
        
                is_success = result.get("success", False)
                print_result("Returns success=True", is_success,
                            f"Error: {result.get('error', 'None')}")
        
                if is_success:
                    has_meal_type = "meal_type" in result
                    print_result("Has meal_type", has_meal_type,
                                f"Type: {result.get('meal_type')}")
            
                    has_recipe = "recipe" in result
                    print_result("Has recipe name", has_recipe,
                                f"Recipe: {result.get('recipe')}")
            
                    has_reason = result.get("reason") == "Not feeling well"
                    print_result("Reason is correct", has_reason,
                                f"Reason: {result.get('reason')}")
            
                    has_pattern = "pattern_analysis" in result
                    print_result("Has pattern_analysis", has_pattern)
            
                    has_adherence = "adherence_impact" in result
                    print_result("Has adherence_impact", has_adherence)
        
        db1.commit()
    finally:
        db1.close()
    
    # TEST 2: Verify database updated
    print("\n[Test 2] Database updated correctly")
    db2 = SessionLocal()
    
    try:
        meal_log = db2.query(MealLog).filter(
            MealLog.id == test_data["meal_to_skip"]
        ).first()
        
        was_skipped_set = meal_log and meal_log.was_skipped is True
        print_result("was_skipped = True", was_skipped_set)
        
        reason_set = meal_log and meal_log.skip_reason == "Not feeling well"
        print_result("skip_reason saved", reason_set,
                    f"Reason: {meal_log.skip_reason if meal_log else 'Not found'}")
        
        consumed_is_none = meal_log and meal_log.consumed_datetime is None
        print_result("consumed_datetime is None", consumed_is_none)
    finally:
        db2.close()
    
    # TEST 3: Cannot skip already consumed meal
    print("\n[Test 3] Cannot skip consumed meal")
    db3 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db3, test_data["user_id"])
        
                result = tracking_agent.track_skipped_meals(
                    meal_log_id=test_data["already_consumed"],
                    reason="Test"
                )
        
                is_error = not result.get("success", True)
                print_result("Returns success=False", is_error)
        
                mentions_consumed = "error" in result and "consum" in result.get("error", "").lower()
                print_result("Error mentions consumed", mentions_consumed,
                            f"Error: {result.get('error', 'None')}")
    finally:
        db3.close()
    
    # TEST 4: Cannot skip already skipped meal
    print("\n[Test 4] Cannot skip already skipped meal")
    db4 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db4, test_data["user_id"])
        
                result = tracking_agent.track_skipped_meals(
                    meal_log_id=test_data["already_skipped"],
                    reason="Test"
                )
        
                is_error = not result.get("success", True)
                print_result("Returns success=False", is_error)
        
                mentions_skip = "error" in result and "skip" in result.get("error", "").lower()
                print_result("Error mentions skip", mentions_skip,
                            f"Error: {result.get('error', 'None')}")
    finally:
        db4.close()
    
    # TEST 5: Invalid meal_log_id
    print("\n[Test 5] Handle invalid meal_log_id")
    db5 = SessionLocal()
    
    try:
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db5, test_data["user_id"])
        
                result = tracking_agent.track_skipped_meals(
                    meal_log_id=999999,
                    reason="Test"
                )
        
                is_error = not result.get("success", True)
                print_result("Returns success=False", is_error)
        
                has_error = "error" in result
                print_result("Has error message", has_error,
                            f"Error: {result.get('error', 'None')}")
    finally:
        db5.close()
    
    # TEST 6: Reason too long
    print("\n[Test 6] Validate reason length")
    db6 = SessionLocal()
    
    try:
        # Create another meal to test with
        recipe_id = test_data["recipe_id"]
        meal_log_test = MealLog(
            user_id=test_data["user_id"],
            recipe_id=recipe_id,
            meal_type="snack",
            planned_datetime=datetime.utcnow(),
            consumed_datetime=None,
            was_skipped=False,
            portion_multiplier=1.0
        )
        db6.add(meal_log_test)
        db6.commit()
        db6.refresh(meal_log_test)
        
        # Mock WebSocket Manager and Notification Service
        with patch('app.agents.tracking_agent.websocket_manager') as mock_ws:
            with patch('app.agents.tracking_agent.NotificationService') as mock_notif:
                # Configure mocks
                mock_ws.broadcast_to_user = AsyncMock()
                mock_notif_instance = Mock()
                mock_notif.return_value = mock_notif_instance
                
                tracking_agent = TrackingAgent(db6, test_data["user_id"])
        
                long_reason = "x" * 300  # 300 characters (max is 255)
        
                result = tracking_agent.track_skipped_meals(
                    meal_log_id=meal_log_test.id,
                    reason=long_reason
                )
        
                is_error = not result.get("success", True)
                print_result("Rejects reason > 255 chars", is_error,
                            f"Error: {result.get('error', 'None')}")
    finally:
        db6.close()

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
    print("TRACKING AGENT: MEAL TOOLS TESTS")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_log_meal_consumption(test_data)
        test_track_skipped_meals(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")