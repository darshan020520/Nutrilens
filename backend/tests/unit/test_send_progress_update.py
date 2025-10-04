"""
TEST FILE: test_send_progress_update.py
Testing: send_progress_update() from notification_service.py

Run with: python test_send_progress_update.py

Function Signature:
async def send_progress_update(
    self,
    user_id: int,
    compliance_rate: float,
    calories_consumed: float,
    calories_remaining: float,
    priority: NotificationPriority = NotificationPriority.LOW
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


class TestSendProgressUpdate:
    """Test suite for send_progress_update() function"""
    
    def __init__(self):
        self.test_results = []
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Setup Database and Redis for testing"""
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        self.db = SessionLocal()
        
        self.test_user = self.db.query(User).filter_by(id=197).first()
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
                enabled_types=['progress_update', 'achievement', 'daily_summary'],
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
    # TEST 1: Progress Update Queued Correctly
    # ==========================================
    
    async def test_1_progress_update_queued(self):
        """
        TEST 1: Progress update is queued and processed correctly
        
        Flow:
        1. Send progress update with compliance data
        2. Wait for background worker
        3. Verify database log entry
        """
        try:
            print("\n" + "="*60)
            print("TEST 1: Progress Update Queued Correctly")
            print("="*60)
            
            # Arrange
            compliance_rate = 85.0
            calories_consumed = 1800.0
            calories_remaining = 200.0
            
            # Act
            print("\n📤 Queueing progress update...")
            result = await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=compliance_rate,
                calories_consumed=calories_consumed,
                calories_remaining=calories_remaining
            )
            
            assert result is True, "Should queue successfully"
            print("✅ Notification queued")
            
            # Verify in Redis
            print("\n📋 Verifying Redis queue...")
            queue_length = self.redis_client.llen("notifications:low")
            print(f"   Queue length: {queue_length}")
            assert queue_length == 1, "Should be in LOW priority queue"
            print("✅ Found in LOW priority queue")
            
            # Wait for worker
            print("\n⏳ Waiting for background worker (15 seconds)...")
            for i in range(15, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Verify queue processed
            print("\n📋 Checking if queue was processed...")
            queue_length = self.redis_client.llen("notifications:low")
            assert queue_length == 0, "Queue should be empty"
            print("✅ Queue processed")
            
            # Verify database log
            print("\n💾 Checking database log...")
            log = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='progress_update'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            print(f"✅ Log entry found (ID: {log.id})")
            
            assert log.status == 'sent', f"Status should be 'sent', got '{log.status}'"
            print(f"✅ Status: {log.status}")
            
            assert log.title == "Daily Progress Update", "Title should be correct"
            print(f"✅ Title: {log.title}")
            
            print("\n" + "="*60)
            print("✅ TEST 1 PASSED!")
            print("="*60)
            
            self.log_test_result("test_1_progress_update_queued", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_1_progress_update_queued", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_1_progress_update_queued", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 2: Compliance Rate Included
    # ==========================================
    
    async def test_2_compliance_rate_included(self):
        """
        TEST 2: Compliance rate is included in notification data
        
        What we're testing:
        - compliance_rate is in data
        - Value is correct
        """
        try:
            print("\n" + "="*60)
            print("TEST 2: Compliance Rate Included")
            print("="*60)
            
            # Arrange
            compliance_rate = 92.5
            
            # Act
            print(f"\n📤 Sending progress update with {compliance_rate}% compliance...")
            result = await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=compliance_rate,
                calories_consumed=1950.0,
                calories_remaining=50.0
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
                notification_type='progress_update'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            
            assert 'compliance_rate' in log.data, "Data should contain compliance_rate"
            print(f"✅ compliance_rate found in data")
            
            assert log.data['compliance_rate'] == compliance_rate, \
                f"compliance_rate should be {compliance_rate}"
            print(f"✅ compliance_rate value: {log.data['compliance_rate']}")
            
            print("\n" + "="*60)
            print("✅ TEST 2 PASSED!")
            print("="*60)
            
            self.log_test_result("test_2_compliance_rate_included", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_2_compliance_rate_included", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_2_compliance_rate_included", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 3: Calories Data Included
    # ==========================================
    
    async def test_3_calories_data_included(self):
        """
        TEST 3: Calories consumed and remaining are included
        
        What we're testing:
        - calories_consumed is in data
        - calories_remaining is in data
        - Body includes calorie information
        """
        try:
            print("\n" + "="*60)
            print("TEST 3: Calories Data Included")
            print("="*60)
            
            # Arrange
            calories_consumed = 1675.5
            calories_remaining = 324.5
            
            # Act
            print(f"\n📤 Sending progress with {calories_consumed} consumed, {calories_remaining} remaining...")
            result = await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=75.0,
                calories_consumed=calories_consumed,
                calories_remaining=calories_remaining
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
                notification_type='progress_update'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            
            assert 'calories_consumed' in log.data, "Data should contain calories_consumed"
            assert log.data['calories_consumed'] == calories_consumed
            print(f"✅ calories_consumed: {log.data['calories_consumed']}")
            
            assert 'calories_remaining' in log.data, "Data should contain calories_remaining"
            assert log.data['calories_remaining'] == calories_remaining
            print(f"✅ calories_remaining: {log.data['calories_remaining']}")
            
            assert "cal consumed" in log.body, "Body should mention calories consumed"
            assert "cal remaining" in log.body, "Body should mention calories remaining"
            print(f"✅ Body includes calorie info: {log.body}")
            
            print("\n" + "="*60)
            print("✅ TEST 3 PASSED!")
            print("="*60)
            
            self.log_test_result("test_3_calories_data_included", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_3_calories_data_included", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_3_calories_data_included", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 4: Message Varies by Compliance Rate
    # ==========================================
    
    async def test_4_message_varies_by_compliance(self):
        """
        TEST 4: Message varies based on compliance rate
        
        What we're testing:
        - >= 90%: "Amazing!" message
        - >= 70%: "Good progress!" message
        - < 70%: "Stay on track!" message
        """
        try:
            print("\n" + "="*60)
            print("TEST 4: Message Varies by Compliance Rate")
            print("="*60)
            
            # Test high compliance (>= 90%)
            print("\n📤 Testing HIGH compliance (95%)...")
            await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=95.0,
                calories_consumed=1900.0,
                calories_remaining=100.0
            )
            
            await asyncio.sleep(15)
            
            log_high = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='progress_update'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log_high is not None, "High compliance log should exist"
            assert "Amazing" in log_high.body, "Should contain 'Amazing' for >= 90%"
            print(f"✅ High compliance message: {log_high.body}")
            
            self.redis_client.flushdb()
            
            # Test medium compliance (>= 70%)
            print("\n📤 Testing MEDIUM compliance (75%)...")
            await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=75.0,
                calories_consumed=1700.0,
                calories_remaining=300.0
            )
            
            await asyncio.sleep(15)
            
            log_medium = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='progress_update'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log_medium is not None, "Medium compliance log should exist"
            assert "Good progress" in log_medium.body, "Should contain 'Good progress' for >= 70%"
            print(f"✅ Medium compliance message: {log_medium.body}")
            
            self.redis_client.flushdb()
            
            # Test low compliance (< 70%)
            print("\n📤 Testing LOW compliance (50%)...")
            await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=50.0,
                calories_consumed=1200.0,
                calories_remaining=800.0
            )
            
            await asyncio.sleep(15)
            
            log_low = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='progress_update'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log_low is not None, "Low compliance log should exist"
            assert "Stay on track" in log_low.body, "Should contain 'Stay on track' for < 70%"
            print(f"✅ Low compliance message: {log_low.body}")
            
            print("\n" + "="*60)
            print("✅ TEST 4 PASSED!")
            print("="*60)
            
            self.log_test_result("test_4_message_varies_by_compliance", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_4_message_varies_by_compliance", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_4_message_varies_by_compliance", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 5: Returns True on Success
    # ==========================================
    
    async def test_5_returns_true_on_success(self):
        """
        TEST 5: Function returns True when queued successfully
        
        What we're testing:
        - Function returns boolean True
        - Queue operation succeeds
        """
        try:
            print("\n" + "="*60)
            print("TEST 5: Returns True on Success")
            print("="*60)
            
            # Act
            print("\n📤 Testing return value...")
            result = await self.service.send_progress_update(
                user_id=self.test_user.id,
                compliance_rate=80.0,
                calories_consumed=1800.0,
                calories_remaining=200.0
            )
            
            # Assert
            assert result is True, "Function should return True"
            assert isinstance(result, bool), "Return value should be boolean"
            print("✅ Returns True")
            print("✅ Return type is boolean")
            
            # Verify actually queued
            print("\n📋 Verifying notification was actually queued...")
            queue_length = self.redis_client.llen("notifications:low")
            assert queue_length == 1, "Should be in queue"
            print("✅ Notification queued successfully")
            
            print("\n" + "="*60)
            print("✅ TEST 5 PASSED!")
            print("="*60)
            
            self.log_test_result("test_5_returns_true_on_success", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_5_returns_true_on_success", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_5_returns_true_on_success", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # RUN ALL TESTS
    # ==========================================
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("\n" + "="*60)
        print("TESTING send_progress_update() - ALL TESTS")
        print("="*60 + "\n")
        
        await self.test_1_progress_update_queued()
        self.redis_client.flushdb()
        
        await self.test_2_compliance_rate_included()
        self.redis_client.flushdb()
        
        await self.test_3_calories_data_included()
        self.redis_client.flushdb()
        
        await self.test_4_message_varies_by_compliance()
        self.redis_client.flushdb()
        
        await self.test_5_returns_true_on_success()
        
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
    tester = TestSendProgressUpdate()
    
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
    ║  TEST: send_progress_update()                            ║
    ║  Tests daily progress notifications                      ║
    ║  Total: 5 test cases                                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())