# Debug Logging Added for Achievement Flow Analysis

## Purpose
To understand the complete data flow and identify where achievement spam is occurring.

## Files Modified

### 1. `backend/app/agents/tracking_agent.py`

**Location 1: `log_meal_consumption()` method (Lines 482-509)**
- Added debug logging before calling `_check_meal_achievements()`
- Added debug logging for each achievement being sent
- Shows: User ID, achievement type, message, priority

**Location 2: `_check_meal_achievements()` method (Lines 1322-1416)**
- Added comprehensive debug logging for entire achievement check process
- Shows:
  - User ID and meal result keys
  - Streak calculation (recent logs, streak days)
  - Daily completion check (today's log count)
  - Nutrition target check (protein consumed vs target)
  - Final list of achievements found

### 2. `backend/app/services/notification_service.py`

**Location 1: `send_achievement()` method (Lines 267-296)**
- Added debug logging for achievement notification creation
- Shows: User ID, achievement type, message, priority
- Shows notification data preparation
- Shows result from `_queue_notification()`

**Location 2: `_queue_notification()` method (Lines 351-399)**
- Added comprehensive debug logging for queuing process
- Shows:
  - User preferences fetched
  - Notification type enabled/disabled check
  - Quiet hours check
  - Redis queue name
  - Final notification data being pushed
  - Redis lpush result

## Debug Output Structure

When a meal is logged, you will see debug output in this order:

```
[MEAL LOG] Calling _check_meal_achievements...

================================================================================
[ACHIEVEMENT CHECK] Starting achievement check
[ACHIEVEMENT CHECK] User ID: 221
[ACHIEVEMENT CHECK] Meal result keys: [...]
================================================================================

[ACHIEVEMENT CHECK - STREAK] Recent logs (last 7 days): X
[ACHIEVEMENT CHECK - STREAK] ✅/❌ [streak result]

[ACHIEVEMENT CHECK - DAILY] Today's logs count: X
[ACHIEVEMENT CHECK - DAILY] ✅/❌ [daily completion result]

[ACHIEVEMENT CHECK - NUTRITION] Daily totals: {...}
[ACHIEVEMENT CHECK - NUTRITION] Protein consumed: Xg
[ACHIEVEMENT CHECK - NUTRITION] Protein target: 50g
[ACHIEVEMENT CHECK - NUTRITION] ✅/❌ [protein goal result]

[ACHIEVEMENT CHECK] Total achievements found: X
[ACHIEVEMENT CHECK]   1. Type: ..., Message: ...
================================================================================

[MEAL LOG] Returned achievements: [...]
[MEAL LOG] Number of achievements to send: X

================================================================================
[NOTIFICATION SEND] Processing achievement 1/X
[NOTIFICATION SEND] Achievement type: nutrition_target
[NOTIFICATION SEND] Achievement message: Protein goal achieved!...
[NOTIFICATION SEND] User ID: 221
[NOTIFICATION SEND] Priority: NORMAL
================================================================================

[NOTIFICATION SEND] Calling notification_service.send_achievement()...

================================================================================
[NOTIFICATION SERVICE] send_achievement() called
[NOTIFICATION SERVICE] User ID: 221
[NOTIFICATION SERVICE] Achievement Type: nutrition_target
[NOTIFICATION SERVICE] Message: Protein goal achieved!...
[NOTIFICATION SERVICE] Priority: normal
================================================================================

[NOTIFICATION SERVICE] Notification data prepared: {...}
[NOTIFICATION SERVICE] Calling _queue_notification()...

================================================================================
[QUEUE NOTIFICATION] _queue_notification() called
[QUEUE NOTIFICATION] User ID: 221
[QUEUE NOTIFICATION] Notification Type: achievement
================================================================================

[QUEUE NOTIFICATION] Fetching user preferences...
[QUEUE NOTIFICATION] User preferences: {...}

[QUEUE NOTIFICATION] Checking if notification type 'achievement' is enabled...
[QUEUE NOTIFICATION] ✅ Notification type 'achievement' is ENABLED

[QUEUE NOTIFICATION] Checking quiet hours (priority: normal)...
[QUEUE NOTIFICATION] ✅ Current time is allowed (not in quiet hours)

[QUEUE NOTIFICATION] Target queue: notifications:normal

[QUEUE NOTIFICATION] Pushing to Redis queue 'notifications:normal'...
[QUEUE NOTIFICATION] Notification data: {...}
[QUEUE NOTIFICATION] ✅ Redis lpush result: 1
[QUEUE NOTIFICATION] ✅ Notification queued successfully!

[NOTIFICATION SERVICE] _queue_notification() returned: True

[NOTIFICATION SEND] ✅ Achievement notification sent successfully!
```

## Testing Instructions

1. **Start monitoring API container logs:**
   ```bash
   docker logs nutrilens-api-1 -f
   ```

2. **Log a meal via API or frontend**
   - Use user 221 (who has history of achievement spam)
   - Log a meal that would trigger protein goal achievement

3. **Observe the debug output**
   - Check what achievements are detected
   - Check if protein consumed >= 50g
   - Verify notification is queued

4. **Log ANOTHER meal (this is the critical test)**
   - Log a second meal for same user
   - Protein will still be >= 50g
   - **Question:** Does achievement trigger again?
   - **Expected behavior (current bug):** Yes, it triggers again
   - **Desired behavior:** No, should not trigger (already sent today)

## What to Look For

### Key Questions:
1. **How many times is `_check_meal_achievements()` called?**
   - Once per meal log

2. **What is the protein_consumed value?**
   - Does it keep increasing with each meal?

3. **What achievements are returned?**
   - Does `nutrition_target` appear in the list every time?

4. **Is the notification queued each time?**
   - Check `Redis lpush result`

5. **Does the notification actually get sent?**
   - Check notification-processor logs

## Next Steps After Testing

1. Analyze the debug logs
2. Identify exact point where duplicate detection should occur
3. Discuss Redis-based deduplication strategy
4. Implement the fix
5. Re-test with debug logging to verify fix works
6. Remove debug logging (keep minimal logging for production)

## Expected Findings

We expect to confirm:
- Achievement check runs on EVERY meal log
- Protein goal check uses current totals (not delta)
- No tracking of "already sent today"
- Notification queued every time condition is met
- Same notification sent multiple times per day

This will validate our analysis and inform the exact implementation of the fix.
