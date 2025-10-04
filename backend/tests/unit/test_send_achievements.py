"""
TEST FILE: test_send_achievement.py
Testing: send_achievement() from notification_service.py

Run with: python test_send_achievement.py

Function Signature:
async def send_achievement(
    self,
    user_id: int,
    achievement_type: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.NORMAL
) -> bool
"""

import asyncio
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# ENABLE MOCK PROVIDERS
os.environ["MOCK_NOTIFICATION_PROVIDERS"] = "true"

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import redis

from app.services.notification_service import NotificationService, NotificationPriority
from app.models.database import User, NotificationPreference, NotificationLog
from app.core.config import settings


class TestSendAchievement:
    """Test suite for send_achievement() function"""
    
    def __init__(self):
        self.test_results = []
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Setup Database and Redis for testing"""
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        self.db = SessionLocal()
        
        self.test_user = self.db.query(User).filter_by(is_active=True).first()
        if not self.test_user:
            print("⚠️  No active users found. Please create a test user first.")
            sys.exit(1)
        
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,
            decode_responses=False
        )
        self.redis_client.flushdb()
        
        self.service = NotificationService(self.db)
        self.service.redis_client = self.redis_client
        
        # Ensure user has proper preferences
        pref = self.db.query(NotificationPreference).filter_by(
            user_id=self.test_user.id
        ).first()
        
        if not pref:
            pref = NotificationPreference(
                user_id=self.test_user.id,
                enabled_providers=['email', 'push'],
                enabled_types=['achievement', 'progress_update', 'daily_summary'],
                quiet_hours_start=22,
                quiet_hours_end=7
            )
            self.db.add(pref)
            self.db.commit()
        
        print("✅ Test environment setup complete")
        print(f"   - Database: {settings.database_url}")
        print(f"   - Test user: ID={self.test_user.id}, Email={self.test_user.email}")
        print(f"   - Redis Test DB: 15")
        print(f"   - Mock providers: ENABLED")
        print("\n⚠️  Make sure background worker is running!")
        print("   Run: python -m app.workers.notification_worker\n")
    
    def cleanup(self):
        """Cleanup test environment"""
        self.redis_client.flushdb()
        self.redis_client.close()
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
    # TEST 1: Achievement Queued Correctly
    # ==========================================
    
    async def test_1_achievement_queued(self):
        """
        TEST 1: Achievement notification is queued and processed correctly
        
        Flow:
        1. Send achievement with type and message
        2. Wait for background worker
        3. Verify database log entry
        """
        try:
            print("\n" + "="*60)
            print("TEST 1: Achievement Queued Correctly")
            print("="*60)
            
            # Arrange
            achievement_type = "7_day_streak"
            message = "Congratulations! You've logged meals for 7 days straight!"
            
            # Act
            print("\n📤 Queueing achievement notification...")
            result = await self.service.send_achievement(
                user_id=self.test_user.id,
                achievement_type=achievement_type,
                message=message
            )
            
            assert result is True, "Should queue successfully"
            print("✅ Notification queued")
            
            # Verify in Redis
            print("\n📋 Verifying Redis queue...")
            queue_length = self.redis_client.llen("notifications:normal")
            print(f"   Queue length: {queue_length}")
            assert queue_length == 1, "Should be in NORMAL priority queue"
            print("✅ Found in NORMAL priority queue")
            
            # Wait for worker
            print("\n⏳ Waiting for background worker (15 seconds)...")
            for i in range(15, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Verify queue processed
            print("\n📋 Checking if queue was processed...")
            queue_length = self.redis_client.llen("notifications:normal")
            assert queue_length == 0, "Queue should be empty"
            print("✅ Queue processed")
            
            # Verify database log
            print("\n💾 Checking database log...")
            log = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='achievement'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            print(f"✅ Log entry found (ID: {log.id})")
            
            assert log.status == 'sent', f"Status should be 'sent', got '{log.status}'"
            print(f"✅ Status: {log.status}")
            
            assert log.title == "Achievement Unlocked!", "Title should be 'Achievement Unlocked!'"
            print(f"✅ Title: {log.title}")
            
            assert log.body == message, "Body should be the achievement message"
            print(f"✅ Body: {log.body}")
            
            print("\n" + "="*60)
            print("✅ TEST 1 PASSED!")
            print("="*60)
            
            self.log_test_result("test_1_achievement_queued", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_1_achievement_queued", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_1_achievement_queued", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 2: Achievement Type and Message Included
    # ==========================================
    
    async def test_2_achievement_type_and_message(self):
        """
        TEST 2: Achievement type and message are included in data
        
        What we're testing:
        - achievement_type is in data
        - achievement_message is in data
        - Values are correct
        """
        try:
            print("\n" + "="*60)
            print("TEST 2: Achievement Type and Message Included")
            print("="*60)
            
            # Arrange
            achievement_type = "first_meal_logged"
            message = "Great start! You've logged your first meal!"
            
            # Act
            print(f"\n📤 Sending achievement: {achievement_type}...")
            result = await self.service.send_achievement(
                user_id=self.test_user.id,
                achievement_type=achievement_type,
                message=message
            )
            
            assert result is True, "Should queue successfully"
            print("✅ Notification queued")
            
            # Wait for worker
            print("\n⏳ Waiting for background worker (15 seconds)...")
            for i in range(15, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Verify database log
            print("\n💾 Checking database log...")
            log = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='achievement'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            
            assert 'achievement_type' in log.data, "Data should contain achievement_type"
            assert log.data['achievement_type'] == achievement_type
            print(f"✅ achievement_type: {log.data['achievement_type']}")
            
            assert 'achievement_message' in log.data, "Data should contain achievement_message"
            assert log.data['achievement_message'] == message
            print(f"✅ achievement_message: {log.data['achievement_message']}")
            
            print("\n" + "="*60)
            print("✅ TEST 2 PASSED!")
            print("="*60)
            
            self.log_test_result("test_2_achievement_type_and_message", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_2_achievement_type_and_message", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_2_achievement_type_and_message", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 3: Different Achievement Types
    # ==========================================
    
    async def test_3_different_achievement_types(self):
        """
        TEST 3: Different achievement types are handled correctly
        
        What we're testing:
        - Various achievement types work
        - Each creates separate notification
        """
        try:
            print("\n" + "="*60)
            print("TEST 3: Different Achievement Types")
            print("="*60)
            
            # Arrange - Different achievement types
            achievements = [
                ("streak_7", "7 day streak achieved!"),
                ("streak_30", "30 day streak - Amazing!"),
                ("goal_reached", "Weight goal reached!"),
                ("perfect_week", "Perfect compliance this week!")
            ]
            
            # Act
            print(f"\n📤 Sending {len(achievements)} different achievements...")
            for achievement_type, message in achievements:
                result = await self.service.send_achievement(
                    user_id=self.test_user.id,
                    achievement_type=achievement_type,
                    message=message
                )
                assert result is True, f"Should succeed for {achievement_type}"
                print(f"✅ Queued: {achievement_type}")
            
            # Wait for worker
            print("\n⏳ Waiting for background worker (15 seconds)...")
            for i in range(15, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Verify all logs created
            print("\n💾 Checking database logs...")
            logs = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='achievement'
            ).order_by(NotificationLog.created_at.desc()).limit(len(achievements)).all()
            
            assert len(logs) >= len(achievements), f"Should have {len(achievements)} logs"
            print(f"✅ Found {len(logs)} achievement logs")
            
            # Verify each achievement type is present
            logged_types = [log.data.get('achievement_type') for log in logs]
            for achievement_type, _ in achievements:
                assert achievement_type in logged_types, f"{achievement_type} should be logged"
            print("✅ All achievement types logged correctly")
            
            print("\n" + "="*60)
            print("✅ TEST 3 PASSED!")
            print("="*60)
            
            self.log_test_result("test_3_different_achievement_types", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_3_different_achievement_types", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_3_different_achievement_types", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 4: Returns True on Success
    # ==========================================
    
    async def test_4_returns_true_on_success(self):
        """
        TEST 4: Function returns True when queued successfully
        
        What we're testing:
        - Function returns boolean True
        - Queue operation succeeds
        """
        try:
            print("\n" + "="*60)
            print("TEST 4: Returns True on Success")
            print("="*60)
            
            # Act
            print("\n📤 Testing return value...")
            result = await self.service.send_achievement(
                user_id=self.test_user.id,
                achievement_type="test_achievement",
                message="Test achievement message"
            )
            
            # Assert
            assert result is True, "Function should return True"
            assert isinstance(result, bool), "Return value should be boolean"
            print("✅ Returns True")
            print("✅ Return type is boolean")
            
            # Verify actually queued
            print("\n📋 Verifying notification was actually queued...")
            queue_length = self.redis_client.llen("notifications:normal")
            assert queue_length == 1, "Should be in queue"
            print("✅ Notification queued successfully")
            
            print("\n" + "="*60)
            print("✅ TEST 4 PASSED!")
            print("="*60)
            
            self.log_test_result("test_4_returns_true_on_success", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_4_returns_true_on_success", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_4_returns_true_on_success", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # RUN ALL TESTS
    # ==========================================
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("\n" + "="*60)
        print("TESTING send_achievement() - ALL TESTS")
        print("="*60 + "\n")
        
        await self.test_1_achievement_queued()
        self.redis_client.flushdb()
        
        await self.test_2_achievement_type_and_message()
        self.redis_client.flushdb()
        
        await self.test_3_different_achievement_types()
        self.redis_client.flushdb()
        
        await self.test_4_returns_true_on_success()
        
        self.print_summary()
    
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
    tester = TestSendAchievement()
    
    try:
        all_passed = await tester.run_all_tests()
        tester.cleanup()
        
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
        tester.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  TEST: send_achievement()                                ║
    ║  Tests achievement notifications                         ║
    ║  Total: 4 test cases                                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())