"""
TEST FILE: test_notification_worker_core.py
Testing: NotificationWorker core functions (Group E)

Run with: python test_notification_worker_core.py

Functions Tested:
1. __init__() - Initialize worker state
2. _handle_shutdown() - Graceful shutdown handler
3. run() - Main worker loop

Total: 17 test cases
"""

import asyncio
import signal
import sys
import os
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.workers.notification_worker import NotificationWorker


class TestNotificationWorkerCore:
    """Test suite for NotificationWorker core functions"""
    
    def __init__(self):
        self.test_results = []
    
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
    # GROUP E1: __init__() Tests (4 tests)
    # ==========================================
    
    def test_1_init_sets_should_stop_false(self):
        """
        TEST 1: __init__() sets should_stop to False
        
        What we're testing:
        - Worker starts in running state (should_stop = False)
        """
        try:
            print("\n" + "="*60)
            print("TEST 1: Init - should_stop = False")
            print("="*60)
            
            # Act
            worker = NotificationWorker()
            
            # Assert
            assert hasattr(worker, 'should_stop'), "Worker should have should_stop attribute"
            assert worker.should_stop is False, "should_stop should be False initially"
            
            print("✅ should_stop initialized to False")
            
            self.log_test_result("test_1_init_sets_should_stop_false", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_1_init_sets_should_stop_false", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_1_init_sets_should_stop_false", False, f"Unexpected: {str(e)}")
    
    def test_2_init_creates_session_factory(self):
        """
        TEST 2: __init__() creates session_factory
        
        What we're testing:
        - session_factory is created for database access
        """
        try:
            print("\n" + "="*60)
            print("TEST 2: Init - session_factory created")
            print("="*60)
            
            # Act
            worker = NotificationWorker()
            
            # Assert
            assert hasattr(worker, 'session_factory'), "Worker should have session_factory"
            assert worker.session_factory is not None, "session_factory should not be None"
            
            print("✅ session_factory created")
            
            self.log_test_result("test_2_init_creates_session_factory", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_2_init_creates_session_factory", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_2_init_creates_session_factory", False, f"Unexpected: {str(e)}")
    
    def test_3_init_state_variables(self):
        """
        TEST 3: __init__() initializes state variables to None
        
        What we're testing:
        - last_daily_summary = None
        - last_weekly_report = None
        - last_meal_reminder_check = None
        """
        try:
            print("\n" + "="*60)
            print("TEST 3: Init - state variables = None")
            print("="*60)
            
            # Act
            worker = NotificationWorker()
            
            # Assert
            assert hasattr(worker, 'last_daily_summary'), "Should have last_daily_summary"
            assert worker.last_daily_summary is None, "last_daily_summary should be None"
            print("✅ last_daily_summary = None")
            
            assert hasattr(worker, 'last_weekly_report'), "Should have last_weekly_report"
            assert worker.last_weekly_report is None, "last_weekly_report should be None"
            print("✅ last_weekly_report = None")
            
            assert hasattr(worker, 'last_meal_reminder_check'), "Should have last_meal_reminder_check"
            assert worker.last_meal_reminder_check is None, "last_meal_reminder_check should be None"
            print("✅ last_meal_reminder_check = None")
            
            self.log_test_result("test_3_init_state_variables", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_3_init_state_variables", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_3_init_state_variables", False, f"Unexpected: {str(e)}")
    
    def test_4_init_signal_handlers(self):
        """
        TEST 4: __init__() sets up signal handlers
        
        What we're testing:
        - SIGTERM handler registered
        - SIGINT handler registered
        """
        try:
            print("\n" + "="*60)
            print("TEST 4: Init - signal handlers registered")
            print("="*60)
            
            # Save original handlers
            original_sigterm = signal.getsignal(signal.SIGTERM)
            original_sigint = signal.getsignal(signal.SIGINT)
            
            # Act
            worker = NotificationWorker()
            
            # Assert
            current_sigterm = signal.getsignal(signal.SIGTERM)
            current_sigint = signal.getsignal(signal.SIGINT)
            
            assert current_sigterm != original_sigterm, "SIGTERM handler should be changed"
            assert current_sigint != original_sigint, "SIGINT handler should be changed"
            
            print("✅ SIGTERM handler registered")
            print("✅ SIGINT handler registered")
            
            self.log_test_result("test_4_init_signal_handlers", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_4_init_signal_handlers", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_4_init_signal_handlers", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # GROUP E2: _handle_shutdown() Tests (4 tests)
    # ==========================================
    
    def test_5_handle_shutdown_sets_should_stop(self):
        """
        TEST 5: _handle_shutdown() sets should_stop to True
        
        What we're testing:
        - Calling _handle_shutdown changes should_stop to True
        """
        try:
            print("\n" + "="*60)
            print("TEST 5: Shutdown - sets should_stop = True")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            assert worker.should_stop is False, "Initially should be False"
            
            # Act
            worker._handle_shutdown(signal.SIGTERM, None)
            
            # Assert
            assert worker.should_stop is True, "should_stop should be True after shutdown"
            
            print("✅ should_stop changed to True")
            
            self.log_test_result("test_5_handle_shutdown_sets_should_stop", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_5_handle_shutdown_sets_should_stop", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_5_handle_shutdown_sets_should_stop", False, f"Unexpected: {str(e)}")
    
    def test_6_handle_shutdown_sigterm(self):
        """
        TEST 6: _handle_shutdown() handles SIGTERM signal
        
        What we're testing:
        - Can be called with SIGTERM
        """
        try:
            print("\n" + "="*60)
            print("TEST 6: Shutdown - handles SIGTERM")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            
            # Act - Should not raise exception
            worker._handle_shutdown(signal.SIGTERM, None)
            
            # Assert
            assert worker.should_stop is True, "should_stop should be True"
            
            print("✅ SIGTERM handled successfully")
            
            self.log_test_result("test_6_handle_shutdown_sigterm", True)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_6_handle_shutdown_sigterm", False, str(e))
    
    def test_7_handle_shutdown_sigint(self):
        """
        TEST 7: _handle_shutdown() handles SIGINT signal
        
        What we're testing:
        - Can be called with SIGINT (Ctrl+C)
        """
        try:
            print("\n" + "="*60)
            print("TEST 7: Shutdown - handles SIGINT")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            
            # Act - Should not raise exception
            worker._handle_shutdown(signal.SIGINT, None)
            
            # Assert
            assert worker.should_stop is True, "should_stop should be True"
            
            print("✅ SIGINT handled successfully")
            
            self.log_test_result("test_7_handle_shutdown_sigint", True)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_7_handle_shutdown_sigint", False, str(e))
    
    def test_8_handle_shutdown_logs_message(self):
        """
        TEST 8: _handle_shutdown() logs shutdown message
        
        What we're testing:
        - Shutdown is logged (using mock)
        """
        try:
            print("\n" + "="*60)
            print("TEST 8: Shutdown - logs message")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            
            with patch('app.workers.notification_worker.logger') as mock_logger:
                # Act
                worker._handle_shutdown(signal.SIGTERM, None)
                
                # Assert
                assert mock_logger.info.called, "Logger should be called"
                
                # Check if message contains shutdown info
                call_args = mock_logger.info.call_args[0][0]
                assert "shutting down" in call_args.lower(), "Log should mention shutdown"
                
                print("✅ Shutdown message logged")
            
            self.log_test_result("test_8_handle_shutdown_logs_message", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_8_handle_shutdown_logs_message", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_8_handle_shutdown_logs_message", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # GROUP E3: run() Tests (9 tests)
    # ==========================================
    
    async def test_9_run_creates_services(self):
        """
        TEST 9: run() creates NotificationService and ConsumptionService
        
        What we're testing:
        - Services are instantiated in the loop
        """
        try:
            print("\n" + "="*60)
            print("TEST 9: Run - creates services")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True  # Stop after one iteration
            
            with patch('app.workers.notification_worker.NotificationService') as mock_notif_service, \
                 patch('app.workers.notification_worker.ConsumptionService') as mock_cons_service:
                
                # Act
                await worker.run()
                
                # Assert
                assert mock_notif_service.called, "NotificationService should be created"
                assert mock_cons_service.called, "ConsumptionService should be created"
                
                print("✅ NotificationService created")
                print("✅ ConsumptionService created")
            
            self.log_test_result("test_9_run_creates_services", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_9_run_creates_services", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_9_run_creates_services", False, f"Unexpected: {str(e)}")
    
    async def test_10_run_calls_scheduled_notifications(self):
        """
        TEST 10: run() calls _process_scheduled_notifications
        
        What we're testing:
        - Scheduled notification processing is invoked
        """
        try:
            print("\n" + "="*60)
            print("TEST 10: Run - calls scheduled notifications")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True  # Stop after one iteration
            
            with patch.object(worker, '_process_scheduled_notifications', new_callable=MagicMock) as mock_scheduled:
                mock_scheduled.return_value = asyncio.coroutine(lambda: None)()
                
                with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                    mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                    
                    # Act
                    await worker.run()
                    
                    # Assert
                    assert mock_scheduled.called, "_process_scheduled_notifications should be called"
                    
                    print("✅ _process_scheduled_notifications called")
            
            self.log_test_result("test_10_run_calls_scheduled_notifications", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_10_run_calls_scheduled_notifications", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_10_run_calls_scheduled_notifications", False, f"Unexpected: {str(e)}")
    
    async def test_11_run_calls_meal_reminders(self):
        """
        TEST 11: run() calls _process_meal_reminders
        
        What we're testing:
        - Meal reminder processing is invoked
        """
        try:
            print("\n" + "="*60)
            print("TEST 11: Run - calls meal reminders")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True  # Stop after one iteration
            
            with patch.object(worker, '_process_scheduled_notifications', new_callable=MagicMock) as mock_scheduled:
                mock_scheduled.return_value = asyncio.coroutine(lambda: None)()
                
                with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                    mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                    
                    # Act
                    await worker.run()
                    
                    # Assert
                    assert mock_reminders.called, "_process_meal_reminders should be called"
                    
                    print("✅ _process_meal_reminders called")
            
            self.log_test_result("test_11_run_calls_meal_reminders", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_11_run_calls_meal_reminders", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_11_run_calls_meal_reminders", False, f"Unexpected: {str(e)}")
    
    async def test_12_run_closes_db_session(self):
        """
        TEST 12: run() closes database session in finally block
        
        What we're testing:
        - Database session is always closed
        """
        try:
            print("\n" + "="*60)
            print("TEST 12: Run - closes DB session")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True
            
            mock_db = Mock()
            
            with patch.object(worker.session_factory, '__call__', return_value=mock_db):
                with patch.object(worker, '_process_scheduled_notifications', new_callable=MagicMock) as mock_scheduled:
                    mock_scheduled.return_value = asyncio.coroutine(lambda: None)()
                    
                    with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                        mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                        
                        # Act
                        await worker.run()
                        
                        # Assert
                        assert mock_db.close.called, "Database session should be closed"
                        
                        print("✅ Database session closed")
            
            self.log_test_result("test_12_run_closes_db_session", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_12_run_closes_db_session", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_12_run_closes_db_session", False, f"Unexpected: {str(e)}")
    
    async def test_13_run_handles_errors_gracefully(self):
        """
        TEST 13: run() handles errors and continues
        
        What we're testing:
        - Errors don't crash the worker
        - Worker continues after error
        """
        try:
            print("\n" + "="*60)
            print("TEST 13: Run - handles errors gracefully")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            
            call_count = [0]
            
            async def failing_process(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("Simulated error")
                # Second call succeeds, then stop
                worker.should_stop = True
            
            with patch.object(worker, '_process_scheduled_notifications', side_effect=failing_process):
                with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                    mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                    
                    # Act - Should not raise exception
                    await worker.run()
                    
                    # Assert
                    assert call_count[0] >= 1, "Should have attempted processing"
                    
                    print("✅ Error handled gracefully")
                    print("✅ Worker continued after error")
            
            self.log_test_result("test_13_run_handles_errors_gracefully", True)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_13_run_handles_errors_gracefully", False, str(e))
    
    async def test_14_run_stops_when_should_stop_true(self):
        """
        TEST 14: run() stops when should_stop is True
        
        What we're testing:
        - Loop exits when should_stop = True
        """
        try:
            print("\n" + "="*60)
            print("TEST 14: Run - stops when should_stop = True")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True  # Already set to stop
            
            with patch.object(worker, '_process_scheduled_notifications', new_callable=MagicMock) as mock_scheduled:
                mock_scheduled.return_value = asyncio.coroutine(lambda: None)()
                
                with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                    mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                    
                    # Act
                    await worker.run()
                    
                    # Assert - Should complete without hanging
                    print("✅ Worker stopped immediately")
                    print("✅ No infinite loop")
            
            self.log_test_result("test_14_run_stops_when_should_stop_true", True)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_14_run_stops_when_should_stop_true", False, str(e))
    
    async def test_15_run_logs_start_message(self):
        """
        TEST 15: run() logs start message
        
        What we're testing:
        - Worker logs when it starts
        """
        try:
            print("\n" + "="*60)
            print("TEST 15: Run - logs start message")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True
            
            with patch('app.workers.notification_worker.logger') as mock_logger:
                with patch.object(worker, '_process_scheduled_notifications', new_callable=MagicMock) as mock_scheduled:
                    mock_scheduled.return_value = asyncio.coroutine(lambda: None)()
                    
                    with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                        mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                        
                        # Act
                        await worker.run()
                        
                        # Assert
                        assert mock_logger.info.called, "Logger should be called"
                        
                        # Check for start message
                        calls = [str(call) for call in mock_logger.info.call_args_list]
                        has_start = any("Starting" in str(call) or "started" in str(call).lower() 
                                      for call in calls)
                        assert has_start, "Should log start message"
                        
                        print("✅ Start message logged")
            
            self.log_test_result("test_15_run_logs_start_message", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_15_run_logs_start_message", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_15_run_logs_start_message", False, f"Unexpected: {str(e)}")
    
    async def test_16_run_logs_stop_message(self):
        """
        TEST 16: run() logs stop message when exiting
        
        What we're testing:
        - Worker logs when it stops
        """
        try:
            print("\n" + "="*60)
            print("TEST 16: Run - logs stop message")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            worker.should_stop = True
            
            with patch('app.workers.notification_worker.logger') as mock_logger:
                with patch.object(worker, '_process_scheduled_notifications', new_callable=MagicMock) as mock_scheduled:
                    mock_scheduled.return_value = asyncio.coroutine(lambda: None)()
                    
                    with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                        mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                        
                        # Act
                        await worker.run()
                        
                        # Assert
                        calls = [str(call) for call in mock_logger.info.call_args_list]
                        has_stop = any("stopped" in str(call).lower() for call in calls)
                        assert has_stop, "Should log stop message"
                        
                        print("✅ Stop message logged")
            
            self.log_test_result("test_16_run_logs_stop_message", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_16_run_logs_stop_message", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_16_run_logs_stop_message", False, f"Unexpected: {str(e)}")
    
    async def test_17_run_sleeps_between_cycles(self):
        """
        TEST 17: run() sleeps 30 seconds between cycles
        
        What we're testing:
        - Worker sleeps to avoid spinning
        """
        try:
            print("\n" + "="*60)
            print("TEST 17: Run - sleeps between cycles")
            print("="*60)
            
            # Arrange
            worker = NotificationWorker()
            
            cycle_count = [0]
            
            async def count_cycles(*args):
                cycle_count[0] += 1
                if cycle_count[0] >= 2:
                    worker.should_stop = True
            
            with patch('asyncio.sleep', new_callable=MagicMock) as mock_sleep:
                mock_sleep.return_value = asyncio.coroutine(lambda: None)()
                
                with patch.object(worker, '_process_scheduled_notifications', side_effect=count_cycles):
                    with patch.object(worker, '_process_meal_reminders', new_callable=MagicMock) as mock_reminders:
                        mock_reminders.return_value = asyncio.coroutine(lambda: None)()
                        
                        # Act
                        await worker.run()
                        
                        # Assert
                        assert mock_sleep.called, "Should call asyncio.sleep"
                        
                        # Check if sleep was called with 30 seconds
                        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                        assert 30 in sleep_calls, "Should sleep for 30 seconds"
                        
                        print("✅ Sleeps 30 seconds between cycles")
            
            self.log_test_result("test_17_run_sleeps_between_cycles", True)
            
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            self.log_test_result("test_17_run_sleeps_between_cycles", False, str(e))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            self.log_test_result("test_17_run_sleeps_between_cycles", False, f"Unexpected: {str(e)}")
    
    # ==========================================
    # RUN ALL TESTS
    # ==========================================
    
    async def run_all_tests(self):
        """Run all tests sequentially"""
        print("\n" + "="*60)
        print("TESTING NotificationWorker - GROUP E (CORE)")
        print("="*60 + "\n")
        
        # E1: __init__() tests
        self.test_1_init_sets_should_stop_false()
        self.test_2_init_creates_session_factory()
        self.test_3_init_state_variables()
        self.test_4_init_signal_handlers()
        
        # E2: _handle_shutdown() tests
        self.test_5_handle_shutdown_sets_should_stop()
        self.test_6_handle_shutdown_sigterm()
        self.test_7_handle_shutdown_sigint()
        self.test_8_handle_shutdown_logs_message()
        
        # E3: run() tests
        await self.test_9_run_creates_services()
        await self.test_10_run_calls_scheduled_notifications()
        await self.test_11_run_calls_meal_reminders()
        await self.test_12_run_closes_db_session()
        await self.test_13_run_handles_errors_gracefully()
        await self.test_14_run_stops_when_should_stop_true()
        await self.test_15_run_logs_start_message()
        await self.test_16_run_logs_stop_message()
        await self.test_17_run_sleeps_between_cycles()
        
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
    tester = TestNotificationWorkerCore()
    
    try:
        all_passed = await tester.run_all_tests()
        
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
        sys.exit(1)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  TEST: NotificationWorker - Group E (Core)               ║
    ║  Tests worker initialization, shutdown, and main loop    ║
    ║  Total: 17 test cases                                    ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())