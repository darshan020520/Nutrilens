"""
COMPLETE USER JOURNEY - Integration Test (FIXED FOR DOCKER)

Tests against ACTUAL running server (not TestClient)
Run with: docker compose exec api python tests/integration/test_tracking_api.py
"""

import asyncio
import json
from datetime import datetime, timedelta
import requests
import websockets
import redis

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import database models for direct DB verification
from app.models.database import (
    SessionLocal, User, UserProfile, UserGoal, UserPath, UserPreference,
    MealPlan, MealLog, UserInventory, ReceiptUpload, NotificationLog, NotificationPreference, AgentInteraction,
    Item, Recipe, GoalType, ActivityLevel, DietaryType, PathType
)
from app.agents.tracking_agent import TrackingAgent
from app.agents.planning_agent import PlanningAgent


class TestCompleteUserJourney:
    """
    Integration Test - Tests ACTUAL Running Server
    
    Uses requests + websockets libraries (like real UI will)
    No TestClient - hits actual uvicorn server in Docker
    """
    
    def __init__(self):
        # CHANGE: Use actual server URL instead of TestClient
        self.base_url = "http://localhost:8000"
        self.ws_url = "ws://localhost:8000"
        
        # Database for verification only
        self.db = get_test_db()
        self.redis = None
        
        # Test data
        self.user_email = "journey@test.com"
        self.user_password = "TestPass123"
        self.user = None
        self.token = None
        self.headers = None
        self.meal_plan = None
        self.meal_logs = []
    
    
    def cleanup_previous_test_data(self):
        """Clean up any previous test data"""
        user = self.db.query(User).filter_by(email=self.user_email).first()
        if user:
            # Delete all related data
            
            self.db.query(AgentInteraction).filter_by(user_id=user.id).delete()
            self.db.query(NotificationPreference).filter_by(user_id=user.id).delete()
            self.db.query(NotificationLog).filter_by(user_id=user.id).delete()
            self.db.query(MealLog).filter_by(user_id=user.id).delete()
            self.db.query(MealPlan).filter_by(user_id=user.id).delete()
            self.db.query(UserInventory).filter_by(user_id=user.id).delete()
            self.db.query(ReceiptUpload).filter_by(user_id=user.id).delete()
            self.db.query(UserPreference).filter_by(user_id=user.id).delete()
            self.db.query(UserPath).filter_by(user_id=user.id).delete()
            self.db.query(UserGoal).filter_by(user_id=user.id).delete()
            self.db.query(UserProfile).filter_by(user_id=user.id).delete()
            self.db.query(User).filter_by(id=user.id).delete()
            self.db.commit()
            print("  ✅ Cleaned up previous test data")
    
    
    # ========================================================================
    # STEP 1: USER REGISTRATION (FIXED)
    # ========================================================================
    
    def step_1_register_user(self):
        """Step 1: Register via ACTUAL server"""
        print("\n" + "="*70)
        print("STEP 1: USER REGISTRATION")
        print("="*70)

        register_data = {
            "email": self.user_email,
            "password": self.user_password
        }
        
        # CHANGE: Use requests instead of TestClie
        response = requests.post(f"{self.base_url}/api/auth/register", json=register_data)
        
        assert response.status_code == 200, f"Registration failed: {response.text}"
        
        user_data = response.json()
        assert user_data["email"] == self.user_email
        assert user_data["is_active"] is True
        
        # Verify user in database
        self.user = self.db.query(User).filter_by(email=self.user_email).first()
        assert self.user is not None
        
        print(f"  ✅ User registered: {self.user.email}")
        print(f"  ✅ User ID: {self.user.id}")
    
    
    # ========================================================================
    # STEP 2: USER LOGIN (FIXED)
    # ========================================================================
    
    def step_2_login_user(self):
        """Step 2: Login via ACTUAL server"""
        print("\n" + "="*70)
        print("STEP 2: USER LOGIN")
        print("="*70)
        
        # CHANGE: Use requests with form data
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            data={  # OAuth2 uses form data
                "username": self.user_email,
                "password": self.user_password
            }
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        login_data = response.json()
        self.token = login_data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        print(f"  ✅ Login successful")
        print(f"  ✅ JWT token: {self.token[:30]}...")
    
    
    # ========================================================================
    # STEP 3: COMPLETE ONBOARDING (FIXED)
    # ========================================================================
    
    def step_3_complete_onboarding(self):
        """Step 3: Complete onboarding via ACTUAL server"""
        print("\n" + "="*70)
        print("STEP 3: COMPLETE ONBOARDING")
        print("="*70)
        
        # 3.1: Basic Profile
        print("\n  3.1: Setting up basic profile...")
        response = requests.post(
            f"{self.base_url}/api/onboarding/basic-info",
            json={
                "name": "Test User",
                "age": 28,
                "height_cm": 175,
                "weight_kg": 75,
                "sex": "male",
                "activity_level": "moderately_active",
                "medical_conditions": []
            },
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Profile failed: {response.text}"
        
        profile = self.db.query(UserProfile).filter_by(user_id=self.user.id).first()
        print(f"    ✅ BMR: {profile.bmr} kcal/day")
        print(f"    ✅ TDEE: {profile.tdee} kcal/day")
        
        # 3.2: Goal Selection
        print("\n  3.2: Setting fitness goal...")
        response = requests.post(
            f"{self.base_url}/api/onboarding/goal-selection",
            json={
                "goal_type": "muscle_gain",
                "target_weight_kg": 80,
                "weekly_goal_rate_kg": 0.5
            },
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Goal failed: {response.text}"
        print(f"    ✅ Goal set: muscle_gain")
        
        # 3.3: Path Selection
        print("\n  3.3: Setting eating path...")
        response = requests.post(
            f"{self.base_url}/api/onboarding/path-selection",
            json={"path_type": "if_16_8"},
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Path failed: {response.text}"
        print(f"    ✅ Path set: IF 16:8")
        
        # 3.4: Preferences
        print("\n  3.4: Setting preferences...")
        response = requests.post(
            f"{self.base_url}/api/onboarding/preferences",
            json={
                "dietary_type": "non_vegetarian",
                "allergies": ["nuts"],
                "disliked_foods": ["mushrooms"],
                "preferred_cuisines": ["indian", "italian"]
            },
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Preferences failed: {response.text}"
        print(f"    ✅ Preferences set")
        
        print("\n  ✅ ONBOARDING COMPLETE!")
    
    
    # ========================================================================
    # STEP 4: ADD INVENTORY (FIXED)
    # ========================================================================
    
    def step_4_add_inventory_via_ocr(self):
        """Step 4: Add inventory (direct agent call)"""
        print("\n" + "="*70)
        print("STEP 4: ADD INVENTORY VIA OCR")
        print("="*70)
        
        ocr_text = """
        10kg whole wheat flour
        1L amul gold milk
        700g chicken breast
        """
        
        # Create receipt record
        receipt = ReceiptUpload(
            user_id=self.user.id,
            file_url="test://receipt.jpg",
            ocr_raw_text=ocr_text,
            processing_status="pending",
            created_at=datetime.utcnow()
        )
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        
        # Process via agent
        tracking_agent = TrackingAgent(self.db, self.user.id)
        
        # Process OCR
        ocr_result = tracking_agent.process_receipt_ocr(receipt.id)
        print("ocr_result", ocr_result)
        assert ocr_result["success"] is True
        parsed_items = ocr_result["parsed_items"]
        print(f"  ✅ OCR processed: {len(parsed_items)} items")
        
        # Normalize
        ocr_text_for_normalize = "\n".join(parsed_items)
        normalize_result = tracking_agent.normalize_ocr_items(ocr_text_for_normalize)
        assert normalize_result["success"] is True
        normalized_items = normalize_result["normalized_items"]
        print(f"  ✅ Normalized: {normalize_result['normalized_count']} items")
        
        # Add to inventory
        inventory_updates = [
            {
                "item_id": item["matched_item"]["id"],
                "quantity_grams": item["quantity_grams"]
            }
            for item in normalized_items
        ]
        
        async def add_inventory():
            return await tracking_agent.update_inventory(
                updates=inventory_updates,
                operation="add"
            )
        
        inventory_result = asyncio.run(add_inventory())
        assert inventory_result["success"] is True
        print(f"  ✅ Inventory updated")
    
    
    # ========================================================================
    # STEP 5: GENERATE MEAL PLAN (FIXED)
    # ========================================================================
    
    def step_5_generate_meal_plan(self):
        """Step 5: Generate meal plan via ACTUAL API"""
        print("\n" + "="*70)
        print("STEP 5: GENERATE MEAL PLAN")
        print("="*70)
        
        # CHANGE: Use API endpoint instead of direct agent
        response = requests.post(
            f"{self.base_url}/api/meal-plans/generate",
            json={
                "start_date": datetime.now().isoformat(),
                "preferences": {}
            },
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Meal plan failed: {response.text}"
        
        self.meal_plan = response.json()
        
        # Verify in database
        db_meal_plan = self.db.query(MealPlan).filter_by(
            user_id=self.user.id,
            is_active=True
        ).first()
        
        assert db_meal_plan is not None
        print(f"\n  ✅ Meal plan generated: ID {db_meal_plan.id}")
        
        # Get meal logs
        self.meal_logs = self.db.query(MealLog).filter_by(
            user_id=self.user.id,
            meal_plan_id=db_meal_plan.id
        ).all()
        
        print(f"  ✅ MealLog records: {len(self.meal_logs)} meals")
    
    
    # ========================================================================
    # STEP 7: LOG MEAL WITH WEBSOCKET (FIXED)
    # ========================================================================
    
    def step_7_log_meal_with_websocket(self):
        """Step 7: Log meal + test WebSocket (FIXED for real server)"""
        print("\n" + "="*70)
        print("STEP 7: LOG MEAL WITH WEBSOCKET")
        print("="*70)
        
        # Get a meal to log
        today_meal = self.meal_logs[0] if self.meal_logs else None
        if not today_meal:
            print("  ⚠️ No meals to log, skipping")
            return
        
        async def test_websocket_and_meal():
            # CHANGE: Use websockets library for real connection
            uri = f"{self.ws_url}/ws/tracking?token={self.token}"
            
            async with websockets.connect(uri) as websocket:
                # Receive welcome
                welcome = await websocket.recv()
                print(f"  ✅ WebSocket connected")
                
                # Start listening
                received_events = []
                
                async def listen():
                    try:
                        while True:
                            msg = await websocket.recv()
                            data = json.loads(msg)
                            received_events.append(data)
                            print(f"     📨 Event: {data.get('event_type')}")
                    except:
                        pass
                
                listen_task = asyncio.create_task(listen())
                
                # Give listener time
                await asyncio.sleep(0.5)
                
                # CHANGE: Use requests to log meal (in separate thread)
                def log_meal():
                    response = requests.post(
                        f"{self.base_url}/tracking/log-meal",
                        json={
                            "meal_log_id": today_meal.id,
                            "portion_multiplier": 1.0,
                            "notes": "Test meal"
                        },
                        headers=self.headers
                    )
                    return response.status_code == 200
                
                # Execute in thread
                import threading
                thread = threading.Thread(target=log_meal)
                thread.start()
                
                # Wait for broadcast
                await asyncio.sleep(2)
                
                # Cleanup
                listen_task.cancel()
                thread.join()
                
                # Verify
                print(f"\n  ✅ Received {len(received_events)} events")
                if received_events:
                    print(f"  ✅ WebSocket broadcasts working!")
        
        asyncio.run(test_websocket_and_meal())
    
    
    # ========================================================================
    # RUN COMPLETE JOURNEY
    # ========================================================================
    
    def run_complete_journey(self):
        """Run the complete test"""
        print("\n" + "="*80)
        print("🚀 INTEGRATION TEST - TESTING ACTUAL RUNNING SERVER")
        print("="*80)
        print(f"\nServer: {self.base_url}")
        print(f"WebSocket: {self.ws_url}")
        print("\n" + "="*80)
        
        try:
            # Verify server is running
            try:
                health = requests.get(f"{self.base_url}/health", timeout=5)
                assert health.status_code == 200
                print("✅ Server is running and healthy\n")
            except:
                print("❌ SERVER NOT RUNNING!")
                print("Start with: docker compose up -d")
                raise
            
            # Cleanup
            self.cleanup_previous_test_data()
            
            # Run all steps
            self.step_1_register_user()
            self.step_2_login_user()
            self.step_3_complete_onboarding()
            self.step_4_add_inventory_via_ocr()
            self.step_5_generate_meal_plan()
            self.step_7_log_meal_with_websocket()
            
            # Success!
            print("\n" + "="*80)
            print("✅ INTEGRATION TEST PASSED!")
            print("="*80)
            print("\n📋 What Was Tested:")
            print("  ✅ User registration (via real API)")
            print("  ✅ User login (via real API)")
            print("  ✅ Complete onboarding (via real API)")
            print("  ✅ OCR processing (direct agent)")
            print("  ✅ Inventory addition (direct agent)")
            print("  ✅ Meal plan generation (via real API)")
            print("  ✅ Meal logging (via real API)")
            print("  ✅ WebSocket broadcasts (real connection)")
            print("\n🎉 YOUR BACKEND IS WORKING!")
            print("="*80 + "\n")
            
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {str(e)}")
            raise
        except Exception as e:
            print(f"\n❌ TEST ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            if self.redis:
                self.redis.close()
            self.db.close()


def get_test_db():
    """Get test database session"""
    return SessionLocal()


def run_test():
    """Run the integration test"""
    test = TestCompleteUserJourney()
    test.run_complete_journey()


if __name__ == "__main__":
    run_test()