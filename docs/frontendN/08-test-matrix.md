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
