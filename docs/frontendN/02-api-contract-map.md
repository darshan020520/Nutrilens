# API Contract Map

## Base URL
- `http://localhost:8000/api`

## Endpoint Mapping Strategy
- Frontend requests use legacy logical paths, converted by `getEndpoint` into `/v2` backend endpoints.

## Core Clients
- AuthClient: register, login, me, verify, resend.
- OnboardingClient: basic-info, goal-selection, path-selection, preferences, calculated-targets.
- DashboardClient: summary, recent-activity.
- MealPlanClient: current-with-status, generate, swap, alternatives, grocery-list.
- TrackingClient: today, history, log-meal, skip-meal, log-external-meal, estimate-external-meal, inventory-status, expiring-items, restock-list.
- InventoryClient: status, items, add-items, confirm-item, delete-item, makeable-recipes, ai-recipes, bulk-add-from-restock.
- ReceiptClient: initiate, process, pending, confirm-and-seed.
- NutritionClient: chat, context.

## Realtime
- WS endpoint: `/ws/tracking?token=<jwt>`
- Event contract: `TrackingEvent { event_type, message, timestamp?, payload? }`

## Error Envelope
- `UiError { code, message, recoverable, retryAction? }`

## Contract Mismatch Policy
- Adapter-first fixes for safe frontend normalization.
- Every mismatch recorded in `issues/contract-mismatch-log.md` with impact and resolution owner.
