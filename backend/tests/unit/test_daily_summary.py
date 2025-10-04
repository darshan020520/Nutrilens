"""
TEST FILE: test_send_daily_summary.py
Testing: send_daily_summary() from notification_service.py

Run with: python test_send_daily_summary.py

Function Signature:
async def send_daily_summary(
    self,
    user_id: int,
    summary_data: Dict[str, Any],
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


class TestSendDailySummary:
    """Test suite for send_daily_summary() function"""
    
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
                enabled_types=['daily_summary', 'progress_update', 'achievement'],
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
    # TEST 1: Daily Summary Queued Correctly
    # ==========================================
    
    async def test_1_daily_summary_queued(self):
        """
        TEST 1: Daily summary is queued and processed correctly
        
        Flow:
        1. Send daily summary with summary data
        2. Wait for background worker
        3. Verify database log entry
        """
        try:
            print("\n" + "="*60)
            print("TEST 1: Daily Summary Queued Correctly")
            print("="*60)
            
            # Arrange
            summary_data = {
                "meals_consumed": 3,
                "compliance_rate": 100.0,
                "total_calories": 2000,
                "meals_planned": 3
            }
            
            # Act
            print("\n📤 Queueing daily summary...")
            result = await self.service.send_daily_summary(
                user_id=self.test_user.id,
                summary_data=summary_data
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
                notification_type='daily_summary'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            print(f"✅ Log entry found (ID: {log.id})")
            
            assert log.status == 'sent', f"Status should be 'sent', got '{log.status}'"
            print(f"✅ Status: {log.status}")
            
            assert log.title == "Daily Summary", "Title should be 'Daily Summary'"
            print(f"✅ Title: {log.title}")
            
            print("\n" + "="*60)
            print("✅ TEST 1 PASSED!")
            print("="*60)
            
            self.log_test_result("test_1_daily_summary_queued", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_1_daily_summary_queued", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_1_daily_summary_queued", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 2: Summary Data Included
    # ==========================================
    
    async def test_2_summary_data_included(self):
        """
        TEST 2: Summary data (meals_consumed, compliance_rate) is included
        
        What we're testing:
        - meals_consumed is in data
        - compliance_rate is in data
        - Body includes both values
        """
        try:
            print("\n" + "="*60)
            print("TEST 2: Summary Data Included")
            print("="*60)
            
            # Arrange
            summary_data = {
                "meals_consumed": 2,
                "compliance_rate": 66.7,
                "total_calories": 1500,
                "meals_planned": 3,
                "meals_skipped": 1
            }
            
            # Act
            print(f"\n📤 Sending summary: {summary_data['meals_consumed']} meals, {summary_data['compliance_rate']}% compliance...")
            result = await self.service.send_daily_summary(
                user_id=self.test_user.id,
                summary_data=summary_data
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
                notification_type='daily_summary'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            
            # Verify complete summary_data is stored
            assert 'meals_consumed' in log.data, "Data should contain meals_consumed"
            assert log.data['meals_consumed'] == summary_data['meals_consumed']
            print(f"✅ meals_consumed: {log.data['meals_consumed']}")
            
            assert 'compliance_rate' in log.data, "Data should contain compliance_rate"
            assert log.data['compliance_rate'] == summary_data['compliance_rate']
            print(f"✅ compliance_rate: {log.data['compliance_rate']}")
            
            # Verify additional fields are preserved
            assert 'total_calories' in log.data, "Data should contain total_calories"
            assert 'meals_planned' in log.data, "Data should contain meals_planned"
            print(f"✅ All summary data preserved")
            
            # Verify body format
            expected_body = f"Today: {summary_data['meals_consumed']} meals logged, {summary_data['compliance_rate']:.0f}% compliance"
            assert log.body == expected_body, f"Body should be '{expected_body}'"
            print(f"✅ Body format: {log.body}")
            
            print("\n" + "="*60)
            print("✅ TEST 2 PASSED!")
            print("="*60)
            
            self.log_test_result("test_2_summary_data_included", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_2_summary_data_included", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_2_summary_data_included", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 3: Default LOW Priority
    # ==========================================
    
    async def test_3_default_low_priority(self):
        """
        TEST 3: Daily summaries use LOW priority by default
        
        What we're testing:
        - Default priority is LOW
        - Goes to low priority queue
        """
        try:
            print("\n" + "="*60)
            print("TEST 3: Default LOW Priority")
            print("="*60)
            
            # Arrange
            summary_data = {
                "meals_consumed": 3,
                "compliance_rate": 100.0
            }
            
            # Act - Don't specify priority (use default)
            print("\n📤 Queueing summary with default priority...")
            result = await self.service.send_daily_summary(
                user_id=self.test_user.id,
                summary_data=summary_data
            )
            
            assert result is True, "Should queue successfully"
            print("✅ Notification queued")
            
            # Verify in LOW priority queue
            print("\n📋 Verifying queue priority...")
            low_queue = self.redis_client.llen("notifications:low")
            normal_queue = self.redis_client.llen("notifications:normal")
            high_queue = self.redis_client.llen("notifications:high")
            
            assert low_queue == 1, "Should be in LOW priority queue"
            assert normal_queue == 0, "Should NOT be in normal queue"
            assert high_queue == 0, "Should NOT be in high queue"
            print("✅ Confirmed in LOW priority queue")
            
            print("\n" + "="*60)
            print("✅ TEST 3 PASSED!")
            print("="*60)
            
            self.log_test_result("test_3_default_low_priority", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_3_default_low_priority", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_3_default_low_priority", False, f"Unexpected: {str(e)}")
    
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
            
            # Arrange
            summary_data = {
                "meals_consumed": 2,
                "compliance_rate": 75.0,
                "total_calories": 1800
            }
            
            # Act
            print("\n📤 Testing return value...")
            result = await self.service.send_daily_summary(
                user_id=self.test_user.id,
                summary_data=summary_data
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
        print("TESTING send_daily_summary() - ALL TESTS")
        print("="*60 + "\n")
        
        await self.test_1_daily_summary_queued()
        self.redis_client.flushdb()
        
        await self.test_2_summary_data_included()
        self.redis_client.flushdb()
        
        await self.test_3_default_low_priority()
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
    tester = TestSendDailySummary()
    
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
    ║  TEST: send_daily_summary()                              ║
    ║  Tests daily summary notifications                       ║
    ║  Total: 4 test cases                                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())