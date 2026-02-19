# Notification Types and Triggers - Simple Breakdown

**Date:** 2026-01-02

---

## CATEGORY 1: User-Triggered (Immediate - during API request)

These happen **immediately** when user performs an action.

### 1. Achievement Unlocked
- **Trigger:** User logs a meal
- **When:** If achievement conditions met (streak/daily completion/protein goal)
- **Who checks:** API/Service layer
- **Delivery:**
  - WebSocket (real-time popup)
  - Push notification (queued to Redis)
- **Dedup:** Redis key with 24hr TTL (sent once per day max)

### 2. Progress Update (Macro Update)
- **Trigger:** User logs a meal
- **When:** After every meal logging
- **Who checks:** API/Service layer
- **Delivery:**
  - WebSocket (real-time dashboard update)
  - Push notification (optional - currently sent)
- **Dedup:** None (sent every time)

---

## CATEGORY 2: Worker-Triggered (Scheduled - background job)

These happen at **scheduled times** regardless of user actions.

### 3. Meal Reminder
- **Trigger:** Worker every 5 minutes
- **When:** 30 minutes before meal planned_datetime
- **Who checks:** Worker queries upcoming meals
- **Delivery:** Push notification only
- **Dedup:** Natural (only upcoming meals in time window)

### 4. Inventory Alert - Expiring Items
- **Trigger:** Worker at 8 AM daily
- **When:** Items expiring within 3 days
- **Who checks:** Worker via inventory service
- **Delivery:** Push notification only
- **Dedup:** Redis key with 24hr TTL (once per day)

### 5. Inventory Alert - Low Stock
- **Trigger:** Worker at 8 AM daily
- **When:** Restock list has urgent items
- **Who checks:** Worker via inventory service
- **Delivery:** Push notification only
- **Dedup:** Redis key with 24hr TTL (once per day)

### 6. Daily Summary
- **Trigger:** Worker at 9 PM daily
- **When:** End of day
- **Who checks:** Worker for all active users
- **Delivery:** Push notification only
- **Dedup:** Natural (once per day per user)

### 7. Weekly Report
- **Trigger:** Worker at 8 PM every Sunday
- **When:** End of week
- **Who checks:** Worker for all active users
- **Delivery:** Push notification only
- **Dedup:** Natural (once per week per user)

---

## CATEGORY 3: Real-Time Events (WebSocket ONLY - no push notification)

These are for **live UI updates** only, no persistent notifications.

### 8. Meal Logged Event
- **Trigger:** User logs a meal
- **When:** After meal logging completes
- **Delivery:** WebSocket only (update meal list in UI)
- **Purpose:** Refresh UI without page reload

### 9. Inventory Updated Event
- **Trigger:** User logs a meal (ingredients deducted)
- **When:** After inventory deduction
- **Delivery:** WebSocket only (update inventory counts)
- **Purpose:** Show updated inventory levels

---

## Summary Table

| # | Notification Type | Trigger | WebSocket | Push | Dedup |
|---|------------------|---------|-----------|------|-------|
| 1 | Achievement | User logs meal | ✅ | ✅ | Redis 24h |
| 2 | Progress Update | User logs meal | ✅ | ✅ | None |
| 3 | Meal Reminder | Worker 5min | ❌ | ✅ | Natural |
| 4 | Expiring Items | Worker 8 AM | ❌ | ✅ | Redis 24h |
| 5 | Low Stock | Worker 8 AM | ❌ | ✅ | Redis 24h |
| 6 | Daily Summary | Worker 9 PM | ❌ | ✅ | Natural |
| 7 | Weekly Report | Worker Sun 8 PM | ❌ | ✅ | Natural |
| 8 | Meal Logged | User logs meal | ✅ | ❌ | None |
| 9 | Inventory Updated | User logs meal | ✅ | ❌ | None |

---

## Key Points

**User-Triggered (2):**
- Achievement (WebSocket + Push)
- Progress Update (WebSocket + Push)

**Worker-Triggered (5):**
- Meal Reminder (Push only)
- Expiring Items (Push only)
- Low Stock (Push only)
- Daily Summary (Push only)
- Weekly Report (Push only)

**WebSocket Events (2):**
- Meal Logged (WebSocket only)
- Inventory Updated (WebSocket only)

**Total:** 9 notification types

---

## Current Issues in v2

1. **Achievement system missing** - User-triggered
2. **Progress update missing** - User-triggered
3. **Worker integration missing** - All worker-triggered notifications
4. **Notifications block API** - await in orchestrator (lines 137, 145)
5. **Inventory alert in wrong place** - Should be worker-only, not after meal logging

---

## Questions to Clarify

1. **Progress Update:** Do we need push notification after EVERY meal, or just WebSocket update?
2. **Inventory Alert:** Should orchestrator check critical items after meal logging? Or ONLY worker at 8 AM?
3. **Event Bus:** Event publisher has event_bus parameter but it's never used. Remove it?

