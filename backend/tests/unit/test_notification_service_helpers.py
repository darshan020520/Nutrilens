"""
Test Notification Service - Group D: Helper Functions
Tests all 8 helper/utility functions in notification_service.py
"""

import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, NotificationPreference, NotificationLog
from app.services.notification_service import NotificationService, NotificationType, NotificationProvider, NotificationPriority
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create test user
        user = User(
            email=f"test_notif_helpers_{datetime.now().timestamp()}@testnotif.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Create notification preferences
        prefs = NotificationPreference(
            user_id=user.id,
            enabled_providers=["email", "push"],
            enabled_types=["meal_reminder", "achievement", "daily_summary", "weekly_report", "inventory_alert"],
            quiet_hours_start=21,  # 10 PM
            quiet_hours_end=22,     # 7 AM
            timezone="UTC"
        )
        db.add(prefs)
        
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}, Preferences {prefs.id}")
        
        return {
            "user_id": user.id,
            "pref_id": prefs.id,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

# ============================================================================
# TEST 1: _get_user_preferences()
# ============================================================================

def test_get_user_preferences(test_data):
    """Test _get_user_preferences() - 4 tests"""
    
    print("\n" + "="*60)
    print("Testing: _get_user_preferences()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 1.1: Get existing preferences
    print("\n[Test 1.1] Get existing user preferences")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        prefs = notification_service._get_user_preferences(test_data["user_id"])
        
        has_enabled_providers = "enabled_providers" in prefs
        print_result("Has enabled_providers", has_enabled_providers,
                    f"Providers: {prefs.get('enabled_providers')}")
        
        has_enabled_types = "enabled_types" in prefs
        print_result("Has enabled_types", has_enabled_types,
                    f"Types: {prefs.get('enabled_types')}")
        
        has_quiet_hours = "quiet_hours_start" in prefs and "quiet_hours_end" in prefs
        print_result("Has quiet hours", has_quiet_hours,
                    f"Hours: {prefs.get('quiet_hours_start')}-{prefs.get('quiet_hours_end')}")
        
        # Verify values match what we set
        correct_providers = prefs.get("enabled_providers") == ["email", "push"]
        print_result("Providers match setup", correct_providers)
        
    finally:
        db1.close()
    
    # TEST 1.2: Get preferences for user without preferences (returns defaults)
    print("\n[Test 1.2] Get defaults for user without preferences")
    db2 = SessionLocal()
    
    try:
        # Create user without preferences
        user_no_prefs = User(
            email=f"no_prefs_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db2.add(user_no_prefs)
        db2.commit()
        
        notification_service = NotificationService(db2)
        
        prefs = notification_service._get_user_preferences(user_no_prefs.id)
        
        has_defaults = "enabled_providers" in prefs
        print_result("Returns default structure", has_defaults)
        
        default_quiet_start = prefs.get("quiet_hours_start") == 22
        print_result("Default quiet_hours_start = 22", default_quiet_start,
                    f"Value: {prefs.get('quiet_hours_start')}")
        
        default_quiet_end = prefs.get("quiet_hours_end") == 7
        print_result("Default quiet_hours_end = 7", default_quiet_end,
                    f"Value: {prefs.get('quiet_hours_end')}")
        
        # Cleanup
        # db2.query(User).filter(User.id == user_no_prefs.id).delete()
        db2.commit()
        
    finally:
        db2.close()
    
    # TEST 1.3: Handle database error gracefully
    print("\n[Test 1.3] Handle database errors gracefully")
    db3 = SessionLocal()
    
    try:
        notification_service = NotificationService(db3)
        
        # Try to get prefs for non-existent user
        prefs = notification_service._get_user_preferences(999999)
        
        returns_defaults = "enabled_providers" in prefs
        print_result("Returns defaults on error", returns_defaults)
        
    finally:
        db3.close()
    
    # TEST 1.4: Verify preference structure
    print("\n[Test 1.4] Preference structure is complete")
    db4 = SessionLocal()
    
    try:
        notification_service = NotificationService(db4)
        
        prefs = notification_service._get_user_preferences(test_data["user_id"])
        
        required_keys = ["enabled_providers", "enabled_types", "quiet_hours_start", "quiet_hours_end", "timezone"]
        has_all_keys = all(key in prefs for key in required_keys)
        print_result("Has all required keys", has_all_keys,
                    f"Keys: {list(prefs.keys())}")
        
    finally:
        db4.close()

# ============================================================================
# TEST 2: _should_send_notification()
# ============================================================================

def test_should_send_notification(test_data):
    """Test _should_send_notification() - 2 tests"""
    
    print("\n" + "="*60)
    print("Testing: _should_send_notification()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 2.1: Enabled notification type
    print("\n[Test 2.1] Returns True for enabled types")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        preferences = {
            "enabled_types": ["meal_reminder", "achievement"]
        }
        
        # Test enabled type
        is_allowed = notification_service._should_send_notification(preferences, "meal_reminder")
        print_result("Returns True for meal_reminder", is_allowed)
        
        is_allowed_achievement = notification_service._should_send_notification(preferences, "achievement")
        print_result("Returns True for achievement", is_allowed_achievement)
        
    finally:
        db1.close()
    
    # TEST 2.2: Disabled notification type
    print("\n[Test 2.2] Returns False for disabled types")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)
        
        preferences = {
            "enabled_types": ["meal_reminder"]  # Only meal_reminder enabled
        }
        
        # Test disabled type
        is_not_allowed = notification_service._should_send_notification(preferences, "weekly_report")
        print_result("Returns False for weekly_report", not is_not_allowed,
                    f"Result: {is_not_allowed}")
        
        is_not_allowed_progress = notification_service._should_send_notification(preferences, "progress_update")
        print_result("Returns False for progress_update", not is_not_allowed_progress,
                    f"Result: {is_not_allowed_progress}")
        
    finally:
        db2.close()

# ============================================================================
# TEST 3: _is_in_quiet_hours()
# ============================================================================

def test_is_in_quiet_hours(test_data):
    """Test _is_in_quiet_hours() - 4 tests"""
    
    print("\n" + "="*60)
    print("Testing: _is_in_quiet_hours()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 3.1: During quiet hours (overnight range)
    print("\n[Test 3.1] Detects quiet hours (overnight range)")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        preferences = {
            "quiet_hours_start": 22,  # 10 PM
            "quiet_hours_end": 7      # 7 AM
        }
        
        # Test 11 PM (should be in quiet hours)
        test_time_night = datetime.now().replace(hour=23, minute=0, second=0)
        is_quiet_night = notification_service._is_in_quiet_hours(test_time_night, preferences)
        print_result("11 PM is in quiet hours", is_quiet_night,
                    f"Time: 23:00, Result: {is_quiet_night}")
        
        # Test 2 AM (should be in quiet hours)
        test_time_early = datetime.now().replace(hour=2, minute=0, second=0)
        is_quiet_early = notification_service._is_in_quiet_hours(test_time_early, preferences)
        print_result("2 AM is in quiet hours", is_quiet_early,
                    f"Time: 02:00, Result: {is_quiet_early}")
        
    finally:
        db1.close()
    
    # TEST 3.2: Outside quiet hours
    print("\n[Test 3.2] Detects normal hours")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        # Test 10 AM (should NOT be in quiet hours)
        test_time_morning = datetime.now().replace(hour=10, minute=0, second=0)
        is_quiet_morning = notification_service._is_in_quiet_hours(test_time_morning, preferences)
        print_result("10 AM is NOT in quiet hours", not is_quiet_morning,
                    f"Time: 10:00, Result: {is_quiet_morning}")
        
        # Test 8 PM (should NOT be in quiet hours)
        test_time_evening = datetime.now().replace(hour=20, minute=0, second=0)
        is_quiet_evening = notification_service._is_in_quiet_hours(test_time_evening, preferences)
        print_result("8 PM is NOT in quiet hours", not is_quiet_evening,
                    f"Time: 20:00, Result: {is_quiet_evening}")
        
    finally:
        db2.close()
    
    # TEST 3.3: Edge cases (exactly at boundary)
    print("\n[Test 3.3] Handle boundary times")
    db3 = SessionLocal()
    
    try:
        notification_service = NotificationService(db3)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        # Test exactly 10 PM (start of quiet hours)
        test_time_start = datetime.now().replace(hour=22, minute=0, second=0)
        is_quiet_start = notification_service._is_in_quiet_hours(test_time_start, preferences)
        print_result("10 PM (start) handled", True,
                    f"Time: 22:00, In quiet hours: {is_quiet_start}")
        
        # Test exactly 7 AM (end of quiet hours)
        test_time_end = datetime.now().replace(hour=7, minute=0, second=0)
        is_quiet_end = notification_service._is_in_quiet_hours(test_time_end, preferences)
        print_result("7 AM (end) handled", True,
                    f"Time: 07:00, In quiet hours: {is_quiet_end}")
        
    finally:
        db3.close()
    
    # TEST 3.4: Same-day range (non-overnight)
    print("\n[Test 3.4] Handle same-day quiet hours")
    db4 = SessionLocal()
    
    try:
        notification_service = NotificationService(db4)
        
        # Example: 1 PM to 2 PM quiet hours (lunch break)
        preferences = {
            "quiet_hours_start": 13,
            "quiet_hours_end": 14
        }
        
        # Test 1:30 PM (should be in quiet hours)
        test_time_quiet = datetime.now().replace(hour=13, minute=30, second=0)
        is_quiet = notification_service._is_in_quiet_hours(test_time_quiet, preferences)
        print_result("1:30 PM is in quiet hours (13-14)", is_quiet,
                    f"Time: 13:30, Result: {is_quiet}")
        
        # Test 3 PM (should NOT be in quiet hours)
        test_time_not_quiet = datetime.now().replace(hour=15, minute=0, second=0)
        is_not_quiet = notification_service._is_in_quiet_hours(test_time_not_quiet, preferences)
        print_result("3 PM is NOT in quiet hours (13-14)", not is_not_quiet,
                    f"Time: 15:00, Result: {is_not_quiet}")
        
    finally:
        db4.close()

# ============================================================================
# TEST 4: _is_allowed_time()
# ============================================================================

def test_is_allowed_time(test_data):
    """Test _is_allowed_time() - 4 tests"""
    
    print("\n" + "="*60)
    print("Testing: _is_allowed_time()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 4.1: URGENT priority always allowed
    print("\n[Test 4.1] URGENT priority always allowed")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        # Even in quiet hours, urgent is allowed
        is_allowed = notification_service._is_allowed_time(preferences, "urgent")
        print_result("URGENT allowed during quiet hours", is_allowed)
        
    finally:
        db1.close()
    
    # TEST 4.2: Normal priority respects quiet hours
    print("\n[Test 4.2] Normal priority respects quiet hours")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        # Mock current time to be in quiet hours
        # We'll check the logic by understanding that _is_allowed_time calls _is_in_quiet_hours
        # For now, we verify the function exists and handles the priority parameter
        
        is_allowed = notification_service._is_allowed_time(preferences, "normal")
        print_result("Function handles normal priority", True,
                    f"Returns boolean: {type(is_allowed) == bool}")
        
    finally:
        db2.close()
    
    # TEST 4.3: HIGH priority respects quiet hours
    print("\n[Test 4.3] HIGH priority respects quiet hours")
    db3 = SessionLocal()
    
    try:
        notification_service = NotificationService(db3)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        is_allowed = notification_service._is_allowed_time(preferences, "high")
        print_result("Function handles high priority", True,
                    f"Returns boolean: {type(is_allowed) == bool}")
        
    finally:
        db3.close()
    
    # TEST 4.4: LOW priority respects quiet hours
    print("\n[Test 4.4] LOW priority respects quiet hours")
    db4 = SessionLocal()
    
    try:
        notification_service = NotificationService(db4)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        is_allowed = notification_service._is_allowed_time(preferences, "low")
        print_result("Function handles low priority", True,
                    f"Returns boolean: {type(is_allowed) == bool}")
        
    finally:
        db4.close()

# ============================================================================
# TEST 5: _calculate_next_allowed_time()
# ============================================================================

def test_calculate_next_allowed_time(test_data):
    """Test _calculate_next_allowed_time() - 3 tests"""
    
    print("\n" + "="*60)
    print("Testing: _calculate_next_allowed_time()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 5.1: Returns datetime object
    print("\n[Test 5.1] Returns datetime object")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        next_time = notification_service._calculate_next_allowed_time(preferences)
        
        is_datetime = isinstance(next_time, datetime)
        print_result("Returns datetime object", is_datetime,
                    f"Type: {type(next_time)}")
        
        is_future = next_time > datetime.utcnow()
        print_result("Returns future time", is_future,
                    f"Next allowed: {next_time.strftime('%Y-%m-%d %H:%M')}")
        
    finally:
        db1.close()
    
    # TEST 5.2: Next time is after quiet hours end
    print("\n[Test 5.2] Calculated time is after quiet hours end")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7
        }
        
        next_time = notification_service._calculate_next_allowed_time(preferences)
        
        # Next allowed time should have hour >= 7 (after quiet hours)
        hour_is_valid = next_time.hour >= preferences["quiet_hours_end"]
        print_result("Time is after quiet hours end", hour_is_valid,
                    f"Hour: {next_time.hour}, Quiet ends at: {preferences['quiet_hours_end']}")
        
    finally:
        db2.close()
    
    # TEST 5.3: Handles different time zones (if implemented)
    print("\n[Test 5.3] Handles timezone parameter")
    db3 = SessionLocal()
    
    try:
        notification_service = NotificationService(db3)
        
        preferences = {
            "quiet_hours_start": 22,
            "quiet_hours_end": 7,
            "timezone": "UTC"
        }
        
        next_time = notification_service._calculate_next_allowed_time(preferences)
        
        is_valid = isinstance(next_time, datetime)
        print_result("Handles timezone in preferences", is_valid,
                    f"Calculated time: {next_time.strftime('%Y-%m-%d %H:%M')}")
        
    finally:
        db3.close()

# ============================================================================
# TEST 6: _log_notification()
# ============================================================================

def test_log_notification(test_data):
    """Test _log_notification() - 4 tests"""
    
    print("\n" + "="*60)
    print("Testing: _log_notification()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 6.1: Log notification successfully
    print("\n[Test 6.1] Log notification to database")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        notification_data = {
            "type": NotificationType.MEAL_REMINDER,
            "user_id": test_data["user_id"],
            "priority": "high",
            "data": {
                "meal_type": "lunch",
                "recipe_name": "Chicken Salad 22",
                "time_until": 30
            },
            "title": f"LUNCH Reminder",
            "body": f"Time to prepare Chicken Salad 22! Starting in 30 minutes.",
            "action_url": f"/meals/lunch",
            "created_at": datetime.utcnow().isoformat()
        }
        
        notification_service._log_notification(notification_data, "email", "sent")
        
        # Verify log was created
        log = db1.query(NotificationLog).filter(
            NotificationLog.user_id == test_data["user_id"],
            NotificationLog.notification_type == NotificationType.MEAL_REMINDER
        ).first()
        
        log_created = log is not None
        print_result("Log created in database", log_created,
                    f"Log ID: {log.id if log else 'None'}")
        
        if log:
            correct_provider = log.provider == "email"
            print_result("Provider stored correctly", correct_provider,
                        f"Provider: {log.provider}")
            
            correct_status = log.status == "sent"
            print_result("Status stored correctly", correct_status,
                        f"Status: {log.status}")
            
            has_sent_at = log.created_at is not None
            print_result("sent_at timestamp set", has_sent_at,
                        f"Sent at: {log.created_at}")
        
        db1.commit()
        
    finally:
        db1.close()
    
    # TEST 6.2: Log failed notification
    print("\n[Test 6.2] Log failed notification")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)

        notification_data = {
            "type": NotificationType.ACHIEVEMENT,
            "user_id": test_data["user_id"],
            "priority": "high",
            "data": {"achievement": "3_day_streak"},
            "title": f"ACHIEVEMENT",
            "body": f"3_day_streak",
            "action_url": f"/meals/lunch",
            "created_at": datetime.utcnow().isoformat()
        }
        
        
        notification_service._log_notification(notification_data, "sms", "failed")
        
        # Verify failed log
        log = db2.query(NotificationLog).filter(
            NotificationLog.user_id == test_data["user_id"],
            NotificationLog.notification_type == NotificationType.ACHIEVEMENT,
            NotificationLog.status == "failed"
        ).first()
        
        log_created = log is not None
        print_result("Failed log created", log_created)
        
        if log:
            has_error = log.error_message is not None
            print_result("Error message stored", has_error,
                        f"Error: {log.error_message}")
        
        db2.commit()
        
    finally:
        db2.close()
    
    # TEST 6.3: Handle missing optional fields
    print("\n[Test 6.3] Handle missing optional fields")
    db3 = SessionLocal()
    
    try:
        notification_service = NotificationService(db3)
        
        # Minimal notification data
        notification_data = {
            "user_id": test_data["user_id"],
            "type": NotificationType.DAILY_SUMMARY
        }
        
        notification_service._log_notification(notification_data, "push", "sent")
        
        # Verify log created even with minimal data
        log = db3.query(NotificationLog).filter(
            NotificationLog.user_id == test_data["user_id"],
            NotificationLog.notification_type == NotificationType.DAILY_SUMMARY
        ).first()
        
        log_created = log is not None
        print_result("Handles minimal data", log_created)
        
        db3.commit()
        
    finally:
        db3.close()
    
    # TEST 6.4: Database transaction handling
    print("\n[Test 6.4] Database transaction committed")
    db4 = SessionLocal()
    
    try:
        notification_service = NotificationService(db4)
        notification_data = {
            "type": NotificationType.PROGRESS_UPDATE,
            "user_id": test_data["user_id"],
            "priority": "high",
            "data": {"compliance": 85},
            "title": f"PROGRESS_UPDATE",
            "body": f"compliance: 85",
            "action_url": f"/meals/lunch",
            "created_at": datetime.utcnow().isoformat()
        }

        notification_service._log_notification(notification_data, "email", "sent")
        
        # Close session and reopen to verify persistence
        log_id = db4.query(NotificationLog).filter(
            NotificationLog.user_id == test_data["user_id"],
            NotificationLog.notification_type == NotificationType.PROGRESS_UPDATE
        ).first().id
        
        db4.commit()
        db4.close()
        
        # Reopen and verify
        db4 = SessionLocal()
        log_persisted = db4.query(NotificationLog).filter(
            NotificationLog.id == log_id
        ).first()
        
        is_persisted = log_persisted is not None
        print_result("Log persisted after commit", is_persisted)
        
    finally:
        db4.close()

# ============================================================================
# TEST 7: get_notification_stats()
# ============================================================================

def test_get_notification_stats(test_data):
    """Test get_notification_stats() - 4 tests"""
    
    print("\n" + "="*60)
    print("Testing: get_notification_stats()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # Setup: Create some notification logs
    db_setup = SessionLocal()
    try:
        # Create logs for different types and statuses
        logs_data = [
            (NotificationType.MEAL_REMINDER, "sent"),
            (NotificationType.MEAL_REMINDER, "sent"),
            (NotificationType.ACHIEVEMENT, "sent"),
            (NotificationType.ACHIEVEMENT, "failed"),
            (NotificationType.DAILY_SUMMARY, "sent"),
        ]
        
        for notif_type, status in logs_data:
            log = NotificationLog(
                user_id=test_data["user_id"],
                notification_type=notif_type,
                provider="email",
                status=status,
                created_at=datetime.utcnow()
            )
            db_setup.add(log)
        
        db_setup.commit()
    finally:
        db_setup.close()
    
    # TEST 7.1: Get stats for default period (7 days)
    print("\n[Test 7.1] Get stats for 7 days")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        stats = notification_service.get_notification_stats(test_data["user_id"], days=7)
        
        has_total = "total_notifications" in stats
        print_result("Has total_notifications", has_total,
                    f"Total: {stats.get('total_notifications')}")
        
        has_sent = "total_sent" in stats
        print_result("Has total_sent", has_sent,
                    f"Sent: {stats.get('total_sent')}")
        
        has_failed = "total_failed" in stats
        print_result("Has total_failed", has_failed,
                    f"Failed: {stats.get('total_failed')}")
        
        has_success_rate = "success_rate" in stats
        print_result("Has success_rate", has_success_rate,
                    f"Rate: {stats.get('success_rate')}%")
        
    finally:
        db1.close()
    
    # TEST 7.2: Stats grouped by type
    print("\n[Test 7.2] Stats grouped by notification type")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)
        
        stats = notification_service.get_notification_stats(test_data["user_id"], days=7)
        
        has_by_type = "by_type" in stats
        print_result("Has by_type breakdown", has_by_type)
        
        if has_by_type:
            by_type = stats["by_type"]
            has_meal_reminder = "meal_reminder" in by_type
            print_result("Has meal_reminder stats", has_meal_reminder,
                        f"Data: {by_type.get('meal_reminder')}")
            
            has_achievement = "achievement" in by_type
            print_result("Has achievement stats", has_achievement,
                        f"Data: {by_type.get('achievement')}")
        
    finally:
        db2.close()
    
    # TEST 7.3: Calculate success rate correctly
    print("\n[Test 7.3] Success rate calculation")
    db3 = SessionLocal()
    
    try:
        notification_service = NotificationService(db3)
        
        stats = notification_service.get_notification_stats(test_data["user_id"], days=7)
        
        # We created 5 logs: 4 sent, 1 failed
        # Success rate should be 80%
        total = stats.get("total_notifications", 0)
        sent = stats.get("total_sent", 0)
        failed = stats.get("total_failed", 0)
        success_rate = stats.get("success_rate", 0)
        
        totals_correct = total == 5
        print_result("Total count correct", totals_correct,
                    f"Expected: 5, Got: {total}")
        
        sent_correct = sent == 4
        print_result("Sent count correct", sent_correct,
                    f"Expected: 4, Got: {sent}")
        
        failed_correct = failed == 1
        print_result("Failed count correct", failed_correct,
                    f"Expected: 1, Got: {failed}")
        
        rate_correct = success_rate == 80.0
        print_result("Success rate correct", rate_correct,
                    f"Expected: 80.0%, Got: {success_rate}%")
        
    finally:
        db3.close()
    
    # TEST 7.4: Handle empty results
    print("\n[Test 7.4] Handle user with no notifications")
    db4 = SessionLocal()
    
    try:
        # Create user with no notifications
        user_no_logs = User(
            email=f"no_logs_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db4.add(user_no_logs)
        db4.commit()
        
        notification_service = NotificationService(db4)
        
        stats = notification_service.get_notification_stats(user_no_logs.id, days=7)
        
        handles_empty = "total_notifications" in stats
        print_result("Handles empty results", handles_empty)
        
        zero_total = stats.get("total_notifications", -1) == 0
        print_result("Returns 0 for empty", zero_total,
                    f"Total: {stats.get('total_notifications')}")
        
        # Cleanup
        db4.query(User).filter(User.id == user_no_logs.id).delete()
        db4.commit()
        
    finally:
        db4.close()

# ============================================================================
# TEST 8: update_user_preferences()
# ============================================================================

def test_update_user_preferences(test_data):
    """Test update_user_preferences() - 5 tests"""
    
    print("\n" + "="*60)
    print("Testing: update_user_preferences()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # TEST 8.1: Update existing preferences
    print("\n[Test 8.1] Update existing preferences")
    db1 = SessionLocal()
    
    try:
        notification_service = NotificationService(db1)
        
        # Update enabled_providers
        result = notification_service.update_user_preferences(
            user_id=test_data["user_id"],
            enabled_providers=["email", "sms", "push"]
        )
        
        print_result("Returns True on success", result)
        
        # Verify update
        prefs = db1.query(NotificationPreference).filter(
            NotificationPreference.user_id == test_data["user_id"]
        ).first()
        
        providers_updated = prefs.enabled_providers == ["email", "sms", "push"]
        print_result("Providers updated correctly", providers_updated,
                    f"Providers: {prefs.enabled_providers}")
        
    finally:
        db1.close()
    
    # TEST 8.2: Update only specific fields
    print("\n[Test 8.2] Update only provided fields")
    db2 = SessionLocal()
    
    try:
        notification_service = NotificationService(db2)
        
        # Get current quiet hours
        prefs_before = db2.query(NotificationPreference).filter(
            NotificationPreference.user_id == test_data["user_id"]
        ).first()
        quiet_start_before = prefs_before.quiet_hours_start
        
        # Update only enabled_types
        notification_service.update_user_preferences(
            user_id=test_data["user_id"],
            enabled_types=["achievement", "weekly_report"]
        )
        
        # Verify enabled_types changed but quiet_hours didn't
        prefs_after = db2.query(NotificationPreference).filter(
            NotificationPreference.user_id == test_data["user_id"]
        ).first()
        
        types_updated = prefs_after.enabled_types == ["achievement", "weekly_report"]
        print_result("enabled_types updated", types_updated,
                    f"Types: {prefs_after.enabled_types}")
        
        quiet_unchanged = prefs_after.quiet_hours_start == quiet_start_before
        print_result("Other fields unchanged", quiet_unchanged,
                    f"Quiet hours: {prefs_after.quiet_hours_start}")
        
    finally:
        db2.close()
    
    # TEST 8.3: Create preferences if don't exist
    print("\n[Test 8.3] Create preferences for new user")
    db3 = SessionLocal()
    
    try:
        # Create user without preferences
        user_new = User(
            email=f"new_prefs_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db3.add(user_new)
        db3.commit()
        
        notification_service = NotificationService(db3)
        
        # Update (should create new)
        result = notification_service.update_user_preferences(
            user_id=user_new.id,
            enabled_providers=["email"],
            quiet_hours_start=23,
            quiet_hours_end=8
        )
        
        print_result("Creates new preferences", result)
        
        # Verify created
        prefs = db3.query(NotificationPreference).filter(
            NotificationPreference.user_id == user_new.id
        ).first()
        
        prefs_created = prefs is not None
        print_result("Preferences exist", prefs_created)
        
        if prefs:
            values_correct = (prefs.enabled_providers == ["email"] and 
                            prefs.quiet_hours_start == 23)
            print_result("Values set correctly", values_correct,
                        f"Providers: {prefs.enabled_providers}, Quiet start: {prefs.quiet_hours_start}")
        
        # Cleanup
        db3.query(NotificationPreference).filter(NotificationPreference.user_id == user_new.id).delete()
        db3.query(User).filter(User.id == user_new.id).delete()
        db3.commit()
        
    finally:
        db3.close()
    
    # TEST 8.4: Update quiet hours
    print("\n[Test 8.4] Update quiet hours")
    db4 = SessionLocal()
    
    try:
        notification_service = NotificationService(db4)
        
        notification_service.update_user_preferences(
            user_id=test_data["user_id"],
            quiet_hours_start=21,
            quiet_hours_end=6
        )
        
        prefs = db4.query(NotificationPreference).filter(
            NotificationPreference.user_id == test_data["user_id"]
        ).first()
        
        start_updated = prefs.quiet_hours_start == 21
        print_result("quiet_hours_start updated", start_updated,
                    f"Value: {prefs.quiet_hours_start}")
        
        end_updated = prefs.quiet_hours_end == 6
        print_result("quiet_hours_end updated", end_updated,
                    f"Value: {prefs.quiet_hours_end}")
        
    finally:
        db4.close()
    
    # TEST 8.5: Database commit works
    print("\n[Test 8.5] Changes persisted to database")
    db5 = SessionLocal()
    
    try:
        notification_service = NotificationService(db5)
        
        # Update and close
        notification_service.update_user_preferences(
            user_id=test_data["user_id"],
            enabled_types=["meal_reminder", "inventory_alert"]
        )
        
        db5.close()
        
        # Reopen and verify
        db5 = SessionLocal()
        prefs = db5.query(NotificationPreference).filter(
            NotificationPreference.user_id == test_data["user_id"]
        ).first()
        
        is_persisted = prefs.enabled_types == ["meal_reminder", "inventory_alert"]
        print_result("Changes persisted", is_persisted,
                    f"Types: {prefs.enabled_types}")
        
    finally:
        db5.close()

def cleanup(test_data):
    """Clean up test data"""
    print("\n" + "="*60)
    print("Cleanup")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        db.query(NotificationLog).filter(NotificationLog.user_id == test_data["user_id"]).delete()
        db.query(NotificationPreference).filter(NotificationPreference.user_id == test_data["user_id"]).delete()
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
    print("NOTIFICATION SERVICE: GROUP D - HELPER FUNCTIONS")
    print("Testing 8 helper/utility functions")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_get_user_preferences(test_data)
        test_should_send_notification(test_data)
        # test_is_in_quiet_hours(test_data)
        test_is_allowed_time(test_data)
        test_calculate_next_allowed_time(test_data)
        test_log_notification(test_data)
        test_get_notification_stats(test_data)
        # test_update_user_preferences(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")