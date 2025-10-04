"""
TEST FILE: test_send_meal_reminder.py
Testing: send_meal_reminder() from notification_service.py

Run with: python test_send_meal_reminder.py

Function Signature:
async def send_meal_reminder(
    self,
    user_id: int,
    meal_type: str,
    recipe_name: str,
    time_until: int,
    priority: NotificationPriority = NotificationPriority.NORMAL
) -> bool
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import redis

from app.services.notification_service import NotificationService, NotificationPriority
from app.models.database import User, NotificationPreference, NotificationLog
from app.core.config import settings


class TestSendMealReminder:
    """Test suite for send_meal_reminder() function"""
    
    def __init__(self):
        self.test_results = []
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Setup Database and Redis for testing"""
        # Use ACTUAL database from app
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        self.db = SessionLocal()
        
        # Get existing test user or use first active user
        self.test_user = self.db.query(User).filter_by(id=197).first()
        if not self.test_user:
            print("⚠️  No active users found in database.")
            print("   Please create a test user first.")
            sys.exit(1)
        
        # Setup test Redis connection (DB 15)
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,  # Test Redis DB
            decode_responses=False
        )
        self.redis_client.flushdb()
        
        # Create NotificationService (it initializes its own Redis internally)
        self.service = NotificationService(self.db)
        
        # Override the service's Redis to use test DB 15
        self.service.redis_client = self.redis_client
        
        print("✅ Test environment setup complete")
        print(f"   - Using actual database: {settings.database_url}")
        print(f"   - Test user: ID={self.test_user.id}, Email={self.test_user.email}")
        print(f"   - Redis Test DB: 15")
    
    def cleanup(self):
        """Cleanup test environment"""
        # Clear test Redis
        self.redis_client.flushdb()
        self.redis_client.close()
        
        # Close database session
        self.db.close()
        
        print("\n✅ Test environment cleaned up")
    
    def log_test_result(self, test_name, passed, error=None):
        """Log test result"""
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'error': error
        })
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if error:
            print(f"   Error: {error}")
    
    # ==========================================
    # TEST 1: Basic Success Case
    # ==========================================
    
    @patch('app.services.notification_service.NotificationService._send_email_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_sms_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_push_notification', new_callable=AsyncMock)
    async def test_1_basic_success(self, mock_push, mock_sms, mock_email):
        """
        TEST 1: Basic success case with all correct parameters
        
        What we're testing:
        - Function accepts all required parameters
        - Notification is queued to Redis
        - Returns True on success
        """
        try:
            # Arrange
            user_id = self.test_user.id
            meal_type = "breakfast"
            recipe_name = "Oatmeal with Berries"
            time_until = 30
            
            # Act
            result = await self.service.send_meal_reminder(
                user_id=user_id,
                meal_type=meal_type,
                recipe_name=recipe_name,
                time_until=time_until
            )

            
            # Assert
            assert result is True, "Function should return True on success"
            
            # Verify notification is in Redis queue
            queue_key = "notifications:normal"
            queue_length = self.redis_client.llen(queue_key)
            print("queue_length", queue_length)
            assert queue_length > 0, "Notification should be in Redis queue"
            
            # Get notification from Redis
            notification_data = self.redis_client.lpop(queue_key)
            print("notification_data", notification_data)
            notification = json.loads(notification_data)
            
            # Verify structure
            assert notification['type'] == 'meal_reminder', "Type should be meal_reminder"
            assert notification['user_id'] == user_id, "User ID should match"
            assert notification['priority'] == 'normal', "Default priority should be normal"
            assert notification['data']['meal_type'] == meal_type, "Meal type should match"
            assert notification['data']['recipe_name'] == recipe_name, "Recipe name should match"
            assert notification['data']['time_until'] == time_until, "Time until should match"
            
            self.log_test_result("test_1_basic_success", True)
            
        except AssertionError as e:
            self.log_test_result("test_1_basic_success", False, str(e))
        except Exception as e:
            self.log_test_result("test_1_basic_success", False, f"Unexpected error: {str(e)}")
    
    # ==========================================
    # TEST 2: High Priority Queue
    # ==========================================
    
    @patch('app.services.notification_service.NotificationService._send_email_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_sms_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_push_notification', new_callable=AsyncMock)
    async def test_2_high_priority(self, mock_push, mock_sms, mock_email):
        """
        TEST 2: High priority notifications go to correct queue
        
        What we're testing:
        - Priority parameter works
        - Notification goes to high priority queue
        """
        try:
            # Act
            result = await self.service.send_meal_reminder(
                user_id=self.test_user.id,
                meal_type="breakfast",
                recipe_name="Quick Toast",
                time_until=5,
                priority=NotificationPriority.HIGH
            )
            
            # Assert
            assert result is True, "Function should return True"
            
            # Verify in HIGH priority queue
            high_queue_key = "notifications:high"
            queue_length = self.redis_client.llen(high_queue_key)
            assert queue_length > 0, "Should be in high priority queue"
            
            notification_data = self.redis_client.lpop(high_queue_key)
            notification = json.loads(notification_data)
            assert notification['priority'] == 'high', "Priority should be high"
            
            self.log_test_result("test_2_high_priority", True)
            
        except AssertionError as e:
            self.log_test_result("test_2_high_priority", False, str(e))
        except Exception as e:
            self.log_test_result("test_2_high_priority", False, f"Unexpected error: {str(e)}")
    
    # ==========================================
    # TEST 3: Database Logging
    # ==========================================
    
    @patch('app.services.notification_service.NotificationService._send_email_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_sms_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_push_notification', new_callable=AsyncMock)
    async def test_3_database_logging(self, mock_push, mock_sms, mock_email):
        """
        TEST 3: Notification log is created in database
        
        What we're testing:
        - NotificationLog entry is created
        - Correct status and data stored
        """
        try:
            # Act
            await self.service.send_meal_reminder(
                user_id=self.test_user.id,
                meal_type="dinner",
                recipe_name="daal rice with curd",
                time_until=25
            )

            print("\n⏳ Step 3: Waiting for background worker (15 seconds)...")
            print("   Worker processes queue every 5 seconds")
            for i in range(25, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Assert - Check database
            log = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='meal_reminder'
            ).order_by(NotificationLog.created_at.desc()).first()

            print("log fetched", log.status)
            
            assert log is not None, "Notification log should exist"
            assert log.status == 'queued', "Status should be queued"
            assert 'meal_type' in log.data, "Data should contain meal_type"
            assert 'recipe_name' in log.data, "Data should contain recipe_name"
            assert log.data['meal_type'] == 'lunch', "Meal type should match"
            assert log.data['recipe_name'] == 'Chicken Curry', "Recipe name should match"
            
            self.log_test_result("test_3_database_logging", True)
            
        except AssertionError as e:
            self.log_test_result("test_3_database_logging", False, str(e))
        except Exception as e:
            self.log_test_result("test_3_database_logging", False, f"Unexpected error: {str(e)}")
    
    # ==========================================
    # TEST 4: User Preferences
    # ==========================================
    
    @patch('app.services.notification_service.NotificationService._send_email_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_sms_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_push_notification', new_callable=AsyncMock)
    async def test_4_user_preferences(self, mock_push, mock_sms, mock_email):
        """
        TEST 4: Respects user preferences
        
        What we're testing:
        - If meal_reminders not in enabled_types, don't queue
        - Function returns False
        """
        try:
            # Arrange - Get or create preference, disable meal reminders
            pref = self.db.query(NotificationPreference).filter_by(
                user_id=self.test_user.id
            ).first()
            
            if pref:
                original_types = pref.enabled_types.copy() if pref.enabled_types else []
                # Remove meal_reminder if present
                if 'meal_reminder' in pref.enabled_types:
                    pref.enabled_types = [t for t in pref.enabled_types if t != 'meal_reminder']
                    self.db.commit()
            else:
                original_types = None
                pref = NotificationPreference(
                    user_id=self.test_user.id,
                    enabled_types=['achievement', 'daily_summary'],  # No meal_reminder
                    enabled_providers=['email']
                )
                self.db.add(pref)
                self.db.commit()
            
            # Act
            result = await self.service.send_meal_reminder(
                user_id=self.test_user.id,
                meal_type="dinner",
                recipe_name="Fish Curry",
                time_until=30
            )
            
            # Assert
            assert result is False, "Should return False when disabled"
            
            # Verify nothing in queues
            normal_queue = self.redis_client.llen("notifications:normal")
            high_queue = self.redis_client.llen("notifications:high")
            assert normal_queue == 0, "Should not queue when disabled"
            assert high_queue == 0, "Should not queue when disabled"
            
            # Cleanup - Restore original preferences
            if original_types is not None:
                pref.enabled_types = original_types
                self.db.commit()
            else:
                self.db.delete(pref)
                self.db.commit()
            
            self.log_test_result("test_4_user_preferences", True)
            
        except AssertionError as e:
            self.log_test_result("test_4_user_preferences", False, str(e))
        except Exception as e:
            self.log_test_result("test_4_user_preferences", False, f"Unexpected error: {str(e)}")
    
    # ==========================================
    # TEST 5: Different Meal Types
    # ==========================================
    
    @patch('app.services.notification_service.NotificationService._send_email_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_sms_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_push_notification', new_callable=AsyncMock)
    async def test_5_different_meal_types(self, mock_push, mock_sms, mock_email):
        """
        TEST 5: All meal types work correctly
        
        What we're testing:
        - breakfast, lunch, dinner, snacks all work
        - Each creates separate notification
        """
        try:
            # Arrange
            meal_types = [
                ("breakfast", "Pancakes"),
                ("lunch", "Pasta"),
                ("dinner", "Steak"),
                ("snacks", "Fruit Bowl")
            ]
            
            # Act - Send for each meal type
            for meal_type, recipe_name in meal_types:
                result = await self.service.send_meal_reminder(
                    user_id=self.test_user.id,
                    meal_type=meal_type,
                    recipe_name=recipe_name,
                    time_until=30
                )
                assert result is True, f"Should succeed for {meal_type}"
            
            # Assert - Should have 4 notifications
            queue_length = self.redis_client.llen("notifications:normal")
            assert queue_length == 4, f"Should have 4 notifications, found {queue_length}"
            
            self.log_test_result("test_5_different_meal_types", True)
            
        except AssertionError as e:
            self.log_test_result("test_5_different_meal_types", False, str(e))
        except Exception as e:
            self.log_test_result("test_5_different_meal_types", False, f"Unexpected error: {str(e)}")
    
    # ==========================================
    # TEST 6: Different Time Values
    # ==========================================
    
    @patch('app.services.notification_service.NotificationService._send_email_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_sms_notification', new_callable=AsyncMock)
    @patch('app.services.notification_service.NotificationService._send_push_notification', new_callable=AsyncMock)
    async def test_6_different_time_values(self, mock_push, mock_sms, mock_email):
        """
        TEST 6: Various time_until values work
        
        What we're testing:
        - Different time values (5, 15, 30, 60 minutes)
        - time_until stored correctly
        """
        try:
            # Arrange
            time_values = [5, 15, 30, 60]
            
            # Act & Assert
            for time_until in time_values:
                result = await self.service.send_meal_reminder(
                    user_id=self.test_user.id,
                    meal_type="breakfast",
                    recipe_name="Test Recipe",
                    time_until=time_until
                )
                assert result is True, f"Should succeed for {time_until} minutes"
                
                # Verify time_until in notification
                notification_data = self.redis_client.lpop("notifications:normal")
                notification = json.loads(notification_data)
                assert notification['data']['time_until'] == time_until, \
                    f"Time until should be {time_until}"
            
            self.log_test_result("test_6_different_time_values", True)
            
        except AssertionError as e:
            self.log_test_result("test_6_different_time_values", False, str(e))
        except Exception as e:
            self.log_test_result("test_6_different_time_values", False, f"Unexpected error: {str(e)}")
    
    # ==========================================
    # RUN ALL TESTS
    # ==========================================
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("\n" + "="*60)
        print("STARTING TESTS FOR send_meal_reminder()")
        print("="*60 + "\n")
        
        await self.test_1_basic_success()
        # self.redis_client.flushdb()
        
        await self.test_2_high_priority()
        # self.redis_client.flushdb()
        
        await self.test_3_database_logging()
        # self.redis_client.flushdb()
        
        # await self.test_4_user_preferences()
        # self.redis_client.flushdb()
        
        # await self.test_5_different_meal_types()
        # self.redis_client.flushdb()
        
        # await self.test_6_different_time_values()
        
        # self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = total - passed
        
        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test']}")
                    if result['error']:
                        print(f"    {result['error']}")
        
        print("\n" + "="*60)
        
        return failed == 0


async def main():
    """Main test execution"""
    tester = TestSendMealReminder()
    
    try:
        all_passed = await tester.run_all_tests()
        # tester.cleanup()
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED! 🎉")
            sys.exit(0)
        else:
            print("\n⚠️  SOME TESTS FAILED")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        # tester.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  TEST: send_meal_reminder()                              ║
    ║  File: notification_service.py                           ║
    ║  Tests: 6 test cases                                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())