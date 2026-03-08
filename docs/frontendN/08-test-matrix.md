# Test Matrix

## Tooling
- Unit/Integration: Vitest + React Testing Library.
- E2E Smoke: Playwright.

## Required Scenarios
- AUTH-01 to AUTH-05.
- ONB-01 to ONB-04.
- HOME-01 to HOME-03.
- MEAL-01 to MEAL-09.
- INV-01 to INV-06.
- NUT-01 to NUT-03.
- PRO-01.
- SET-01.
- A11Y-01 and A11Y-02.
- PERF-01.

## Execution Policy
- Gate-level checks must run before marking gate complete.
- Failures block gate completion.

## Evidence
Each scenario run should capture:
1. Route/screen.
2. Input action.
3. Expected result.
4. Actual result.
5. Pass/fail.

## Current Automated Smoke Coverage (2026-02-27)
- `SMOKE-01`: Landing page renders title, hero heading, and primary CTAs.
- `SMOKE-02`: Login page renders required controls and register navigation.
- `SMOKE-03`: Register page renders required controls and login navigation.
- `SMOKE-04`: Unauthenticated `/dashboard` access redirects to `/login?next=...`.
- `SMOKE-05`: `/verify-email` without token shows invalid-link error state.

## Current Automated Gate Coverage (2026-02-27)
- `AUTH-01`: Register success redirects to verify-pending login.
- `AUTH-02`: Duplicate register error is rendered inline.
- `AUTH-03`: Login success redirects according to onboarding status.
- `AUTH-04`: Unverified login exposes resend verification workflow.
- `AUTH-05`: Verify-email success and failure token states.
- `ONB-01`: Basic info submit navigates to goal selection.
- `ONB-02`: Goal selection submits optional target weight.
- `ONB-03`: Path selection submit navigates to preferences.
- `ONB-04`: Preferences completion redirects to dashboard.
- `HOME-01`: Dashboard summary and recent activity render with live contracts mocked.
- `HOME-02`: Dashboard error state recovers via retry action.
- `HOME-03`: Notification center receives websocket event and renders alert.
- `MEAL-01`: Week plan renders with status badges.
- `MEAL-02`: Regenerate plan handles failure and success branches.
- `MEAL-03`: Swap meal loads alternatives and commits successfully.
- `MEAL-04`: Log meal updates Today flow and reflected week status.
- `MEAL-05`: Skip meal captures reason and renders recommendations.
- `MEAL-06`: External meal estimate-adjust-confirm flow works.
- `MEAL-07`: Recipe search, filters, and pagination are functional.
- `MEAL-08`: Recipe detail dialog remains stable with missing optional fields.
- `MEAL-09`: History range changes update adherence analytics.
- `INV-01`: Inventory list search, category/quick filters, and grid/list switch are functional.
- `INV-02`: Add-items fuzzy parse handles success, confirmation branch, and failed parse rendering.
- `INV-03`: Receipt upload, OCR processing, pending-review, and confirm-and-seed flow complete successfully.
- `INV-04`: Expiring-items day filter updates data and item removal action executes correctly.
- `INV-05`: Restock list supports selection, quantity edits, and bulk add to inventory.
- `INV-06`: Makeable recipes render and AI recipe generation works for both goal-adherent and guilt-free modes.
- `NUT-01`: Nutrition analytics dashboard loads trend cards and KPI summaries from live contracts.
- `NUT-02`: Nutrition chat handles success and failure recovery states reliably.
- `NUT-03`: Nutrition chat context chips and session controls render and remain functional.
- `PRO-01`: Profile MVP renders account data and persists editable safe fields.
- `SET-01`: Settings MVP persists allowed local preferences across reloads.
- `A11Y-01`: Keyboard navigation works across top bar controls, dialogs, and form flows.
- `A11Y-02`: Critical controls expose aria labels and keyboard focus styles are visible.
- `PERF-01`: Dashboard warm navigation remains inside agreed baseline thresholds.

## Supplemental Mobile Smoke Coverage (2026-02-27)
- `MOB-01`: Mobile bottom navigation reaches Home/Meals/Inventory/Nutrition/Profile modules.
- `MOB-02`: Inventory dialogs (`Add Items`, `Scan Receipt`) are reachable and operable on mobile viewport.
- `MOB-03`: Nutrition chat composer and response rendering work on mobile viewport.

## Supplemental Cross-Browser Smoke Coverage (2026-02-27)
- `XBR-01`: Firefox smoke baseline passes for landing/auth/redirect/verify-email critical routes.
- `XBR-02`: WebKit smoke baseline passes for landing/auth/redirect/verify-email critical routes.

## Supplemental Mobile Cross-Browser Coverage (2026-02-27)
- `MXB-01`: Android Chrome emulation passes mobile bottom-nav module traversal.
- `MXB-02`: iOS WebKit emulation passes mobile bottom-nav module traversal.
- `MXB-03`: Android Chrome + iOS WebKit emulation pass mobile inventory dialog operability.
- `MXB-04`: Android Chrome + iOS WebKit emulation pass mobile nutrition chat composer flow.

