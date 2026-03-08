# Cutover Checklist

## Status Snapshot (2026-02-27)

| Item | Status | Evidence |
|---|---|---|
| Gate implementation complete (`G0` to `G5`) | Done | Route and feature coverage implemented in `frontendN` |
| Automated quality gates (lint, typecheck, unit, e2e) | Done | `npm -C frontendN run verify:cutover` green; Playwright `43/43` pass |
| Cross-browser smoke baseline | Done | Firefox + WebKit smoke `10/10` pass |
| Mobile cross-browser emulation baseline | Done | Android Chrome + iOS WebKit mobile smoke `6/6` pass |
| Feature parity matrix verification | Done (automated) / Pending (manual walkthrough signoff) | `docs/frontendN/08-test-matrix.md` |
| Contract mismatch review | Done | `docs/frontendN/issues/contract-mismatch-log.md` shows no open mismatches |
| Desktop + mobile manual UX pass | Pending | Manual QA execution required |
| Stakeholder product/design signoff | Pending | Final review session required |
| Cutover window approval | Pending | Release manager approval required |

## Go/No-Go Criteria

- `GO` only if all items in sections `Pre-Cutover Execution` and `Launch Gate` are checked.
- Any Sev-1 issue in auth, onboarding, meal logging, inventory write paths, or nutrition chat is `NO-GO`.
- Rollback path must be validated before cutover starts.

## Pre-Cutover Execution

### 1. Quality Gate Re-Run (same day as launch)
- [x] Run `npm -C frontendN run verify:cutover` for full automated gate bundle.
- [x] Run `npm -C frontendN run verify:release`.
- [x] Confirm `verify:release` includes `MOB-01..03` via default `test:e2e` run.
- [x] Run `npm -C frontendN run test:e2e:cross-browser` for Firefox/WebKit smoke baseline.
- [x] Run `npm -C frontendN run test:e2e:mobile-cross-browser` for Android/iOS emulation baseline.
- [ ] Optional focused rerun: `npm -C frontendN run test:e2e:mobile`.
- [ ] If composite command fails, run individually:
  - [ ] `npm -C frontendN run lint`.
  - [ ] `npm -C frontendN run typecheck`.
  - [ ] `npm -C frontendN run test`.
  - [ ] `npm -C frontendN run test:e2e`.
- [x] Save run artifacts/logs to release evidence (`docs/frontendN/11-release-evidence-2026-02-27.md`).

### 2. Manual Parity Walkthrough (Desktop + Mobile)
- [ ] Record outcomes in `docs/frontendN/10-parity-walkthrough-log.md`.
- [ ] `/login`: success path, invalid credentials, unverified + resend verification.
- [ ] `/register`: success path and duplicate email handling.
- [ ] `/verify-email`: valid and invalid token states.
- [ ] `/onboarding/basic-info`, `/onboarding/goal-selection`, `/onboarding/path-selection`, `/onboarding/preferences`: complete-step flow and redirects.
- [ ] `/dashboard`: summary cards, activity feed, notification center, quick actions.
- [ ] `/dashboard/meals`: week/today/recipes/history including swap, skip, external meal, and history ranges.
- [ ] `/dashboard/inventory`: status cards, list filters, add-items fuzzy flow, receipt flow, expiring tab, shopping tab, makeable + AI recipes.
- [ ] `/dashboard/nutrition`: analytics charts and values.
- [ ] `/dashboard/nutrition/chat`: success/error replies, new chat reset, context chips.
- [ ] `/dashboard/profile`: profile data render and saved personalization.
- [ ] `/dashboard/settings`: local preference toggles persist.

### 3. Environment and Config Verification
- [x] Local production build check: `npm -C frontendN run build` passes.
- [x] Frontend API and realtime clients resolve targets from `NEXT_PUBLIC_API_URL` with local fallback.
- [ ] Backend API target is correct for release environment.
- [ ] WebSocket endpoint `/ws/tracking` is reachable with valid token auth.
- [ ] `frontendN` build artifact is deployable in release environment.
- [ ] Existing `frontend` deployment remains runnable for rollback.

## Launch Gate

- [ ] Release manager confirms cutover window.
- [ ] Product owner signs functional parity.
- [ ] Engineering lead signs quality gate evidence.
- [ ] Support/on-call owner confirms incident response availability.

## Launch Sequence

1. [ ] Freeze non-release changes on frontend deployment target.
2. [ ] Deploy `frontendN` build to target environment.
3. [ ] Switch active frontend target to `frontendN` (routing/hosting pointer).
4. [ ] Validate critical paths within first 15 minutes:
   - [ ] Auth login/register/verify.
   - [ ] Onboarding redirect chain.
   - [ ] Meal log/skip/external action writes.
   - [ ] Inventory add/remove/receipt confirm-and-seed writes.
   - [ ] Nutrition chat response path.
   - [ ] Notification center websocket event feed.

## Rollback Plan

1. [ ] Re-point active frontend target from `frontendN` back to `frontend`.
2. [ ] Purge edge cache/CDN for UI assets.
3. [ ] Re-run smoke on `/login`, `/dashboard`, `/dashboard/meals`, `/dashboard/inventory`.
4. [ ] Record rollback trigger, timestamp, and incident owner.

## Post-Launch (0-24h Hypercare)

- [ ] Monitor error rate, auth failures, websocket disconnect rate, and API 5xx.
- [ ] Track user-reported issues and classify severity.
- [ ] Hold 24h stability checkpoint.
- [ ] Close cutover if no unresolved Sev-1/Sev-2 issues remain.

## Signoff Log

| Role | Owner | Status | Date | Notes |
|---|---|---|---|---|
| Engineering Lead | TBD | Pending | TBD |  |
| Product Owner | TBD | Pending | TBD |  |
| Design/UX | TBD | Pending | TBD |  |
| QA Lead | TBD | Pending | TBD |  |
| Release Manager | TBD | Pending | TBD |  |
