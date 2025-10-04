"""
TEST FILE: test_send_inventory_alert.py
Testing: send_inventory_alert() from notification_service.py

Run with: python test_send_inventory_alert.py

Function Signature:
async def send_inventory_alert(
    self,
    user_id: int,
    alert_type: str,           # "low_stock" or "expiring"
    items: List[str],          # List of item names
    priority: NotificationPriority = NotificationPriority.HIGH
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


class TestSendInventoryAlert:
    """Test suite for send_inventory_alert() function"""
    
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
                enabled_types=['inventory_alert', 'achievement', 'daily_summary'],
                quiet_hours_start=21,
                quiet_hours_end=22
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
    # TEST 1: Low Stock Alert
    # ==========================================
    
    async def test_1_low_stock_alert(self):
        """
        TEST 1: Low stock alert queued and processed correctly
        
        Flow:
        1. Send low_stock alert with items
        2. Wait for background worker
        3. Verify database log entry
        """
        try:
            print("\n" + "="*60)
            print("TEST 1: Low Stock Alert")
            print("="*60)
            
            # Arrange
            items = ["Rice", "Dal", "Oil"]
            
            # Act - Queue notification
            print("\n📤 Queueing low stock alert...")
            result = await self.service.send_inventory_alert(
                user_id=self.test_user.id,
                alert_type="low_stock",
                items=items
            )
            
            assert result is True, "Should queue successfully"
            print("✅ Notification queued")
            
            # Verify in Redis
            print("\n📋 Verifying Redis queue...")
            queue_length = self.redis_client.llen("notifications:high")
            print(f"   Queue length: {queue_length}")
            assert queue_length == 1, "Should be in HIGH priority queue"
            print("✅ Found in HIGH priority queue")
            
            # Wait for background worker
            print("\n⏳ Waiting for background worker (15 seconds)...")
            for i in range(15, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Verify queue processed
            print("\n📋 Checking if queue was processed...")
            queue_length = self.redis_client.llen("notifications:high")
            assert queue_length == 0, "Queue should be empty"
            print("✅ Queue processed")
            
            # Verify database log
            print("\n💾 Checking database log...")
            log = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='inventory_alert'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            print(f"✅ Log entry found (ID: {log.id})")
            
            assert log.status == 'sent', f"Status should be 'sent', got '{log.status}'"
            print(f"✅ Status: {log.status}")
            
            assert 'alert_type' in log.data, "Data should contain alert_type"
            assert log.data['alert_type'] == 'low_stock', "Alert type should be low_stock"
            print(f"✅ Alert type: {log.data['alert_type']}")
            
            assert 'items' in log.data, "Data should contain items"
            assert log.data['items'] == items, "Items should match"
            print(f"✅ Items: {log.data['items']}")
            
            assert log.title == "Low Stock Alert", "Title should be correct"
            print(f"✅ Title: {log.title}")
            
            print("\n" + "="*60)
            print("✅ TEST 1 PASSED!")
            print("="*60)
            
            self.log_test_result("test_1_low_stock_alert", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_1_low_stock_alert", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_1_low_stock_alert", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 2: Expiring Items Alert
    # ==========================================
    
    async def test_2_expiring_items_alert(self):
        """
        TEST 2: Expiring items alert queued and processed correctly
        
        What we're testing:
        - Alert type "expiring" works
        - Title and body are correct for expiring items
        - Items are included in data
        """
        try:
            print("\n" + "="*60)
            print("TEST 2: Expiring Items Alert")
            print("="*60)
            
            # Arrange
            items = ["Milk", "Yogurt", "Cheese"]
            
            # Act
            print("\n📤 Queueing expiring items alert...")
            result = await self.service.send_inventory_alert(
                user_id=self.test_user.id,
                alert_type="expiring",
                items=items
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
                notification_type='inventory_alert'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            assert log.data['alert_type'] == 'expiring', "Alert type should be expiring"
            print(f"✅ Alert type: {log.data['alert_type']}")
            
            assert log.data['items'] == items, "Items should match"
            print(f"✅ Items: {log.data['items']}")
            
            assert log.title == "Expiry Alert", "Title should be 'Expiry Alert'"
            print(f"✅ Title: {log.title}")
            
            assert "expiring soon" in log.body.lower(), "Body should mention expiring"
            print(f"✅ Body: {log.body}")
            
            print("\n" + "="*60)
            print("✅ TEST 2 PASSED!")
            print("="*60)
            
            self.log_test_result("test_2_expiring_items_alert", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_2_expiring_items_alert", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_2_expiring_items_alert", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 3: Items Array Validation
    # ==========================================
    
    async def test_3_items_array_included(self):
        """
        TEST 3: Items array is properly included in notification data
        
        What we're testing:
        - Items list is included in data
        - item_count is calculated correctly
        - Multiple items are handled
        """
        try:
            print("\n" + "="*60)
            print("TEST 3: Items Array Validation")
            print("="*60)
            
            # Arrange - Many items
            items = ["Tomatoes", "Onions", "Potatoes", "Garlic", "Ginger"]
            
            # Act
            print(f"\n📤 Queueing alert with {len(items)} items...")
            result = await self.service.send_inventory_alert(
                user_id=self.test_user.id,
                alert_type="low_stock",
                items=items
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
                notification_type='inventory_alert'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            
            assert 'items' in log.data, "Data should contain items array"
            assert isinstance(log.data['items'], list), "Items should be a list"
            print(f"✅ Items is a list")
            
            assert len(log.data['items']) == len(items), f"Should have {len(items)} items"
            print(f"✅ Item count: {len(log.data['items'])}")
            
            assert 'item_count' in log.data, "Data should contain item_count"
            assert log.data['item_count'] == len(items), "item_count should match"
            print(f"✅ item_count: {log.data['item_count']}")
            
            # Check body shows "and X more items" for >3 items
            assert "more items" in log.body, "Body should mention 'more items'"
            print(f"✅ Body handles multiple items: {log.body}")
            
            print("\n" + "="*60)
            print("✅ TEST 3 PASSED!")
            print("="*60)
            
            self.log_test_result("test_3_items_array_included", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_3_items_array_included", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_3_items_array_included", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 4: Default HIGH Priority
    # ==========================================
    
    async def test_4_default_high_priority(self):
        """
        TEST 4: Inventory alerts use HIGH priority by default
        
        What we're testing:
        - Default priority is HIGH
        - Goes to high priority queue
        """
        try:
            print("\n" + "="*60)
            print("TEST 4: Default HIGH Priority")
            print("="*60)
            
            # Act - Don't specify priority (use default)
            print("\n📤 Queueing alert with default priority...")
            result = await self.service.send_inventory_alert(
                user_id=self.test_user.id,
                alert_type="low_stock",
                items=["Bread"]
            )
            
            assert result is True, "Should queue successfully"
            print("✅ Notification queued")
            
            # Verify in HIGH priority queue
            print("\n📋 Verifying queue priority...")
            high_queue = self.redis_client.llen("notifications:high")
            normal_queue = self.redis_client.llen("notifications:normal")
            
            assert high_queue == 1, "Should be in HIGH priority queue"
            assert normal_queue == 0, "Should NOT be in normal queue"
            print("✅ Confirmed in HIGH priority queue")
            
            # Wait for worker
            print("\n⏳ Waiting for background worker (15 seconds)...")
            for i in range(15, 0, -1):
                print(f"   Waiting... {i}s", end='\r')
                await asyncio.sleep(1)
            print("\n✅ Wait complete")
            
            # Verify log has high priority
            print("\n💾 Checking database log...")
            log = self.db.query(NotificationLog).filter_by(
                user_id=self.test_user.id,
                notification_type='inventory_alert'
            ).order_by(NotificationLog.created_at.desc()).first()
            
            assert log is not None, "Log should exist"
            # Note: priority might not be stored in log, but we verified queue
            print(f"✅ Log created successfully")
            
            print("\n" + "="*60)
            print("✅ TEST 4 PASSED!")
            print("="*60)
            
            self.log_test_result("test_4_default_high_priority", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_4_default_high_priority", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_4_default_high_priority", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # TEST 5: Returns True on Success
    # ==========================================
    
    async def test_5_returns_true_on_success(self):
        """
        TEST 5: Function returns True when alert is queued successfully
        
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
            result = await self.service.send_inventory_alert(
                user_id=self.test_user.id,
                alert_type="expiring",
                items=["Eggs", "Butter"]
            )
            
            # Assert
            assert result is True, "Function should return True"
            assert isinstance(result, bool), "Return value should be boolean"
            print("✅ Returns True")
            print("✅ Return type is boolean")
            
            # Verify actually queued
            print("\n📋 Verifying notification was actually queued...")
            queue_length = self.redis_client.llen("notifications:high")
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
        print("TESTING send_inventory_alert() - ALL TESTS")
        print("="*60 + "\n")
        
        await self.test_1_low_stock_alert()
        self.redis_client.flushdb()
        
        await self.test_2_expiring_items_alert()
        self.redis_client.flushdb()
        
        await self.test_3_items_array_included()
        self.redis_client.flushdb()
        
        await self.test_4_default_high_priority()
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
    tester = TestSendInventoryAlert()
    
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
    ║  TEST: send_inventory_alert()                            ║
    ║  Tests inventory alerts (low_stock & expiring)           ║
    ║  Total: 5 test cases                                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())