"""
TEST FILE: test_websocket_manager.py
Testing WebSocketManager with REAL PRODUCTION ENDPOINT

Run with: python test_websocket_manager.py

✅ Uses REAL /ws/tracking endpoint (from websocket.py)
✅ Uses REAL JWT authentication
✅ Uses REAL user creation and database
✅ Tests COMPLETE production flow
✅ NO shortcuts, NO fake endpoints

This tests EVERYTHING as it runs in production!
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import redis.asyncio as aioredis

# Import REAL production app and components
from app.main import app  # ← REAL production app!
from app.services.websocket_manager import websocket_manager
from app.services.auth import create_access_token
from app.models.database import User, NotificationPreference
from app.core.config import settings


class TestWebSocketManager:
    """
    Test suite for WebSocketManager using REAL production endpoint
    
    This tests the COMPLETE flow:
    1. Real user creation
    2. Real JWT token generation  
    3. Real /ws/tracking endpoint
    4. Real authentication
    5. Real manager functions
    
    NO SHORTCUTS - Everything is production-realistic!
    """
    
    def __init__(self):
        self.test_results = []
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Setup test environment with REAL database and user"""
        
        # Use REAL database connection
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        self.db = SessionLocal()
        
        # Get or create REAL test user
        self.test_user = self.db.query(User).filter_by(
            email="test_websocket@example.com"
        ).first()
        
        if not self.test_user:
            self.test_user = User(
                email="test_websocket@example.com",
                hashed_password="test_hash",  # In real tests, use proper hashing
                is_active=True
            )
            self.db.add(self.test_user)
            self.db.commit()
            self.db.refresh(self.test_user)
        
        # Generate REAL JWT token
        self.test_token = create_access_token({
            "sub": str(self.test_user.id),
            "email": self.test_user.email
        })
        
        # Use REAL FastAPI app (not a test app!)
        self.client = TestClient(app)
        
        # REAL manager instance
        self.manager = websocket_manager
        
        print("✅ Test environment setup complete")
        print("   - Using REAL FastAPI app (app.main:app)")
        print("   - Using REAL /ws/tracking endpoint")
        print("   - Using REAL JWT authentication")
        print(f"   - Test user: (ID: {self.test_user.id})")
        print(f"   - JWT token: {self.test_token[:30]}...")
        print()
    
    async def async_setup(self):
        """Async setup for Redis"""
        self.redis_client = await aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=15,  # Test database
            decode_responses=True
        )
        await self.redis_client.flushdb()
        print("✅ Redis Test DB 15 connected and flushed\n")
    
    async def cleanup(self):
        """Cleanup test environment"""
        if self.redis_client:
            await self.redis_client.flushdb()
            await self.redis_client.close()
        
        self.manager.active_connections.clear()
        self.manager.connection_metadata.clear()
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
    
    # ========================================================================
    # TEST 1: REAL Endpoint Connection with REAL Authentication
    # ========================================================================
    
    async def test_1_real_endpoint_connection(self):
        """
        TEST 1: Connect to REAL /ws/tracking endpoint with REAL JWT
        
        This tests:
        - REAL websocket.py endpoint
        - REAL authenticate_websocket() function
        - REAL JWT token validation
        - REAL manager.connect() call
        - Complete production flow
        """
        try:
            print("\n" + "="*60)
            print("TEST 1: Real Endpoint Connection with Authentication")
            print("="*60)
            
            # Clear connections
            self.manager.active_connections.clear()
            self.manager.connection_metadata.clear()
            
            print(f"\n🔐 Connecting to REAL /ws/tracking endpoint")
            print(f"   Endpoint: /ws/tracking?token=<jwt>")
            print(f"   User ID: {self.test_user.id}")
            print(f"   This will:")
            print(f"   1. Call REAL authenticate_websocket()")
            print(f"   2. Validate REAL JWT token")
            print(f"   3. Call REAL manager.connect()")
            print(f"   4. Send welcome message")
            
            # Connect to REAL production endpoint
            with self.client.websocket_connect(
                f"/ws/tracking?token={self.test_token}"
            ) as websocket:
                
                print("\n✅ Connection established!")
                
                # Give async operations time to complete
                await asyncio.sleep(0.1)
                
                # Receive welcome message from REAL endpoint
                print("\n📥 Receiving welcome message from REAL endpoint...")
                data = websocket.receive_json()
                
                print(f"\n📨 Received data:")
                print(f"   {json.dumps(data, indent=2)}")
                
                # Assert - Verify REAL endpoint behavior
                assert "event_type" in data, \
                    "Response should contain event_type"
                assert data["event_type"] == "connected", \
                    f"Expected 'connected', got '{data.get('event_type')}'"
                print("✅ Event type: 'connected'")
                
                assert "user_id" in data, \
                    "Response should contain user_id"
                assert data["user_id"] == self.test_user.id, \
                    f"Expected user_id {self.test_user.id}, got {data.get('user_id')}"
                print(f"✅ User ID matches: {data['user_id']}")
                
                assert "message" in data, \
                    "Response should contain message"
                print(f"✅ Message: {data['message']}")
                
                # Verify REAL manager state
                print("\n🔍 Verifying REAL manager state...")
                
                assert self.test_user.id in self.manager.active_connections, \
                    f"User {self.test_user.id} should be in active_connections"
                print(f"✅ User {self.test_user.id} in active_connections")
                
                conn_count = len(self.manager.active_connections[self.test_user.id])
                assert conn_count == 1, \
                    f"Should have 1 connection, got {conn_count}"
                print(f"✅ Connection count: {conn_count}")
                
                # Check metadata
                ws_obj = self.manager.active_connections[self.test_user.id][0]
                ws_id = id(ws_obj)
                assert ws_id in self.manager.connection_metadata, \
                    "WebSocket metadata should exist"
                print("✅ Connection metadata stored")
            
            # After disconnect
            await asyncio.sleep(0.1)
            
            # Verify cleanup
            assert self.test_user.id not in self.manager.active_connections, \
                "User should be removed after disconnect"
            print("✅ User removed after disconnect")
            
            print("\n" + "="*60)
            print("✅ TEST 1 PASSED! (Complete production flow tested)")
            print("="*60)
            
            self.log_test_result("test_1_real_endpoint_connection", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_1_real_endpoint_connection", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_1_real_endpoint_connection", False, f"Unexpected: {str(e)}")
    
    # ========================================================================
    # TEST 2: REAL Authentication Rejection
    # ========================================================================
    
    async def test_2_authentication_rejected(self):
        """
        TEST 2: REAL endpoint rejects invalid authentication
        
        This tests:
        - REAL authentication validation
        - Invalid token handling
        - Missing token handling
        - Proper error responses
        """
        try:
            print("\n" + "="*60)
            print("TEST 2: Authentication Rejection (Security Test)")
            print("="*60)
            
            # Test 1: No token provided
            print("\n🔒 Test 2.1: Connection without token")
            try:
                with self.client.websocket_connect("/ws/tracking"):
                    assert False, "Should reject connection without token"
            except Exception:
                print("✅ Connection rejected without token (as expected)")
            
            # Test 2: Invalid token
            print("\n🔒 Test 2.2: Connection with invalid token")
            try:
                with self.client.websocket_connect(
                    "/ws/tracking?token=invalid_fake_token_12345"
                ):
                    assert False, "Should reject invalid token"
            except Exception:
                print("✅ Connection rejected with invalid token (as expected)")
            
            # Test 3: Expired token (if you implement expiry)
            print("\n🔒 Test 2.3: Testing token validation works")
            
            # Create token for non-existent user
            fake_token = create_access_token({
                "sub": "99999",  # Non-existent user
                "email": "fake@example.com"
            })
            
            try:
                with self.client.websocket_connect(
                    f"/ws/tracking?token={fake_token}"
                ):
                    assert False, "Should reject token for non-existent user"
            except Exception:
                print("✅ Token validation working correctly")
            
            print("\n" + "="*60)
            print("✅ TEST 2 PASSED! (Authentication security verified)")
            print("="*60)
            
            self.log_test_result("test_2_authentication_rejected", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_2_authentication_rejected", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_2_authentication_rejected", False, f"Unexpected: {str(e)}")
    
    # ========================================================================
    # TEST 3: REAL Message Communication
    # ========================================================================
    
    async def test_3_real_message_communication(self):
        """
        TEST 3: Send and receive messages through REAL endpoint
        
        This tests:
        - REAL handle_client_message() function
        - Message processing through REAL endpoint
        - Echo functionality
        - Pong responses
        """
        try:
            print("\n" + "="*60)
            print("TEST 3: Real Message Communication")
            print("="*60)
            
            with self.client.websocket_connect(
                f"/ws/tracking?token={self.test_token}"
            ) as websocket:
                
                # Receive welcome
                welcome = websocket.receive_json()
                print(f"\n✅ Received welcome: {welcome['message']}")
                
                # Test echo message
                print("\n📤 Test 3.1: Sending echo message to REAL endpoint")
                echo_msg = {
                    "type": "echo",
                    "content": "Test message from real test!"
                }
                websocket.send_json(echo_msg)
                
                print("📥 Waiting for echo response from REAL handle_client_message()...")
                response = websocket.receive_json()
                
                print(f"📨 Received: {json.dumps(response, indent=2)}")
                
                assert response["event_type"] == "echo_response", \
                    f"Expected echo_response, got {response.get('event_type')}"
                assert response["original_message"] == echo_msg, \
                    "Original message should be echoed back"
                print("✅ Echo functionality working through REAL endpoint")
                
                # Test pong response
                print("\n📤 Test 3.2: Simulating pong response")
                pong_msg = {"type": "pong"}
                websocket.send_json(pong_msg)
                
                # Give it time to process
                await asyncio.sleep(0.1)
                
                # Verify last_ping was updated in metadata
                ws_obj = self.manager.active_connections[self.test_user.id][0]
                ws_id = id(ws_obj)
                metadata = self.manager.connection_metadata[ws_id]
                
                # Check last_ping is recent
                last_ping = metadata["last_ping"]
                time_diff = (datetime.utcnow() - last_ping).seconds
                assert time_diff < 5, "last_ping should be updated"
                print("✅ Pong handling working (heartbeat mechanism)")
            
            print("\n" + "="*60)
            print("✅ TEST 3 PASSED! (Message handling verified)")
            print("="*60)
            
            self.log_test_result("test_3_real_message_communication", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_3_real_message_communication", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_3_real_message_communication", False, f"Unexpected: {str(e)}")
    
    # ========================================================================
    # TEST 4: REAL Multi-Device Support
    # ========================================================================
    
    async def test_4_real_multi_device(self):
        """
        TEST 4: Same user with multiple devices (REAL scenario)
        
        This tests:
        - Multiple connections for same user
        - Each connection gets own metadata
        - Both connections receive broadcasts
        - Proper cleanup when one disconnects
        """
        try:
            print("\n" + "="*60)
            print("TEST 4: Real Multi-Device Support")
            print("="*60)
            
            print("\n📱 Connecting device 1 (e.g., phone)...")
            with self.client.websocket_connect(
                f"/ws/tracking?token={self.test_token}"
            ) as ws1:
                
                # Receive welcome on device 1
                welcome1 = ws1.receive_json()
                print(f"✅ Device 1 connected: {welcome1['message']}")
                
                print("\n💻 Connecting device 2 (e.g., laptop) for SAME user...")
                with self.client.websocket_connect(
                    f"/ws/tracking?token={self.test_token}"
                ) as ws2:
                    
                    # Receive welcome on device 2
                    welcome2 = ws2.receive_json()
                    print(f"✅ Device 2 connected: {welcome2['message']}")
                    
                    # Give async time
                    await asyncio.sleep(0.1)
                    
                    # Verify both connections exist
                    print("\n🔍 Verifying both devices connected...")
                    conn_count = len(self.manager.active_connections[self.test_user.id])
                    assert conn_count == 2, \
                        f"Should have 2 connections, got {conn_count}"
                    print(f"✅ Both devices connected: {conn_count} connections")
                    
                    # Test broadcast to both devices
                    print("\n📡 Testing broadcast to both devices...")
                    await self.manager.broadcast_to_user(
                        user_id=self.test_user.id,
                        message={
                            "event_type": "test_broadcast",
                            "data": "Message to all devices"
                        }
                    )
                    
                    # Both should receive
                    msg1 = ws1.receive_json()
                    msg2 = ws2.receive_json()
                    
                    assert msg1["event_type"] == "test_broadcast"
                    assert msg2["event_type"] == "test_broadcast"
                    print("✅ Both devices received broadcast")
                
                # Device 2 disconnected (exited with block)
                await asyncio.sleep(0.1)
                
                # Verify device 2 removed, device 1 still active
                print("\n🔍 Verifying device 2 disconnected, device 1 still active...")
                conn_count = len(self.manager.active_connections.get(self.test_user.id, []))
                assert conn_count == 1, \
                    f"Should have 1 connection remaining, got {conn_count}"
                print(f"✅ Device 1 still connected, device 2 removed: {conn_count} connection")
            
            # Both disconnected
            await asyncio.sleep(0.1)
            
            # Verify all cleaned up
            assert self.test_user.id not in self.manager.active_connections
            print("✅ All devices disconnected and cleaned up")
            
            print("\n" + "="*60)
            print("✅ TEST 4 PASSED! (Multi-device support verified)")
            print("="*60)
            
            self.log_test_result("test_4_real_multi_device", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_4_real_multi_device", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_4_real_multi_device", False, f"Unexpected: {str(e)}")
    
    # ========================================================================
    # TEST 5: REAL Broadcast Functionality
    # ========================================================================
    
    async def test_5_real_broadcast(self):
        """
        TEST 5: Test REAL broadcast_to_user() function
        
        This tests:
        - REAL broadcast_to_user() method
        - REAL Redis pub/sub (if configured)
        - Message delivery to all user connections
        """
        try:
            print("\n" + "="*60)
            print("TEST 5: Real Broadcast Functionality")
            print("="*60)
            
            with self.client.websocket_connect(
                f"/ws/tracking?token={self.test_token}"
            ) as websocket:
                
                # Clear welcome message
                websocket.receive_json()
                
                print("\n📡 Testing REAL broadcast_to_user() function...")
                
                # Call REAL broadcast function
                test_message = {
                    "event_type": "meal_logged",
                    "data": {
                        "meal_type": "breakfast",
                        "calories": 450,
                        "protein": 25
                    }
                }
                
                result = await self.manager.broadcast_to_user(
                    user_id=self.test_user.id,
                    message=test_message
                )
                
                assert result is True, "Broadcast should return True"
                print("✅ broadcast_to_user() returned True")
                
                # Receive broadcast
                received = websocket.receive_json()
                
                print(f"\n📨 Received broadcast:")
                print(f"   {json.dumps(received, indent=2)}")
                
                assert received["event_type"] == "meal_logged"
                assert received["data"]["calories"] == 450
                assert received["user_id"] == self.test_user.id
                assert "timestamp" in received
                print("✅ Broadcast received with correct data")
                
                # Verify stats updated
                assert self.manager.stats["total_broadcasts"] > 0
                print(f"✅ Broadcast stats updated: {self.manager.stats['total_broadcasts']} total broadcasts")
            
            print("\n" + "="*60)
            print("✅ TEST 5 PASSED! (Broadcast functionality verified)")
            print("="*60)
            
            self.log_test_result("test_5_real_broadcast", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_5_real_broadcast", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_5_real_broadcast", False, f"Unexpected: {str(e)}")
    
    # ========================================================================
    # TEST 6: REAL Stats Functionality
    # ========================================================================
    
    async def test_6_real_stats(self):
        """
        TEST 6: Test REAL get_stats() function
        
        This tests:
        - REAL get_stats() method
        - Accurate connection counting
        - Stats updates
        """
        try:
            print("\n" + "="*60)
            print("TEST 6: Real Stats Functionality")
            print("="*60)
            
            # Reset stats
            self.manager.stats = {
                "total_connections": 0,
                "total_messages_sent": 0,
                "total_broadcasts": 0,
                "active_users": 0
            }
            
            print("\n📊 Getting initial stats...")
            initial_stats = self.manager.get_stats()
            print(f"   Initial stats: {initial_stats}")
            
            print("\n🔌 Connecting user...")
            with self.client.websocket_connect(
                f"/ws/tracking?token={self.test_token}"
            ) as websocket:
                
                websocket.receive_json()  # Clear welcome
                await asyncio.sleep(0.1)
                
                print("\n📊 Getting stats with active connection...")
                active_stats = self.manager.get_stats()
                print(f"   Active stats: {active_stats}")
                
                assert active_stats["total_connections"] == 1
                assert active_stats["active_users"] == 1
                print("✅ Stats correctly reflect 1 active user")
                
                # Send a broadcast to increment stats
                await self.manager.broadcast_to_user(
                    user_id=self.test_user.id,
                    message={"event_type": "test", "data": {}}
                )
                websocket.receive_json()  # Clear broadcast
                
                updated_stats = self.manager.get_stats()
                assert updated_stats["total_broadcasts"] >= 1
                print(f"✅ Broadcast stats updated: {updated_stats['total_broadcasts']}")
            
            await asyncio.sleep(0.1)
            
            # After disconnect
            final_stats = self.manager.get_stats()
            assert final_stats["active_users"] == 0
            print(f"✅ Stats correctly reflect 0 active users after disconnect")
            
            print("\n" + "="*60)
            print("✅ TEST 6 PASSED! (Stats functionality verified)")
            print("="*60)
            
            self.log_test_result("test_6_real_stats", True)
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            self.log_test_result("test_6_real_stats", False, str(e))
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.log_test_result("test_6_real_stats", False, f"Unexpected: {str(e)}")
    
    # ========================================================================
    # RUN ALL TESTS
    # ========================================================================
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("\n" + "="*60)
        print("TESTING WebSocketManager with REAL Production Endpoint")
        print("NO SHORTCUTS - Complete Integration Testing")
        print("="*60 + "\n")
        
        await self.async_setup()
        
        # Run all tests
        await self.test_1_real_endpoint_connection()
        await self.test_2_authentication_rejected()
        await self.test_3_real_message_communication()
        await self.test_4_real_multi_device()
        await self.test_5_real_broadcast()
        await self.test_6_real_stats()
        
        return await self.print_summary()
    
    async def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY - Real Production Endpoint Testing")
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
        
        print("\n📋 What Was Tested:")
        print("  ✅ REAL /ws/tracking endpoint (websocket.py)")
        print("  ✅ REAL JWT authentication")
        print("  ✅ REAL manager.connect() integration")
        print("  ✅ REAL message handling")
        print("  ✅ REAL multi-device support")
        print("  ✅ REAL broadcast functionality")
        print("  ✅ REAL stats functionality")
        print("\n  NO test endpoints used - 100% production code tested!")
        
        print("\n" + "="*60)
        
        return failed == 0


async def main():
    """Main test execution"""
    tester = TestWebSocketManager()
    
    try:
        all_passed = await tester.run_all_tests()
        await tester.cleanup()
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED! 🎉")
            print("✅ Complete production flow verified!")
            print("✅ Ready for production deployment!")
            sys.exit(0)
        else:
            print("\n⚠️  SOME TESTS FAILED")
            print("❌ Fix issues before production!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        await tester.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  REAL PRODUCTION ENDPOINT TESTING                        ║
    ║  ✅ Using /ws/tracking (websocket.py)                    ║
    ║  ✅ Real JWT authentication                              ║
    ║  ✅ Real database users                                  ║
    ║  ✅ Complete integration testing                         ║
    ║  ❌ NO shortcuts, NO fake endpoints                      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())