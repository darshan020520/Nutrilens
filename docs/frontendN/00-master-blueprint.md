# FrontendN Master Blueprint

## Objective
Build `frontendN` as a parallel Next.js app with full feature parity and upgraded UX while preserving backend contracts.

## Principles
- Contract-safe frontend changes only.
- Gate-by-gate delivery with review checkpoints.
- No placeholder regressions for implemented backend features.
- Strong async/error states and accessibility coverage.

## Gate Plan
- G0: Foundation and shell.
- G1: Command center dashboard and notification center.
- G2: Meals full parity and improved execution UX.
- G3: Inventory intelligence and receipt workflows.
- G4: Nutrition analytics and context chat.
- G5: Auth/onboarding/profile/settings functional parity.
- G6: Hardening, QA, cutover readiness.

## Mandatory Constraints
- Strict use of existing backend APIs.
- Desktop-first with complete mobile support.
- English-only V1 with i18n-ready architecture.
- WCAG AA core compliance in all gates.
- Required checks before merge: lint, typecheck, unit/integration tests, E2E smoke.

## Architecture Summary
- `src/core`: API/auth/query/realtime/utilities.
- `src/design`: tokens, typography, motion.
- `src/shared`: shell and state primitives.
- `src/features`: module boundaries for future extraction.
- `src/app`: route-level composition.

## Gate Signoff Rule
A gate is done only when:
1. All mapped frames are implemented.
2. No route regressions against parity matrix.
3. Tests for that gate pass.
4. Known contract mismatches are logged in `issues/contract-mismatch-log.md`.

## Current Status (2026-02-27)
- Foundation architecture, route scaffold, design tokens, app shell, and realtime notification plumbing are implemented in `frontendN`.
- Core command center, meals, inventory, nutrition, auth, onboarding, profile, and settings routes are functional with backend contract continuity.
- Latest stabilization pass completed:
  - `typecheck` passes.
  - `lint` passes with zero warnings/errors under current config.
  - `vitest` suite passes.
  - `playwright` suite passes with smoke + gate coverage for `AUTH-01..05`, `ONB-01..04`, `HOME-01..03`, `MEAL-01..09`, `INV-01..06`, `NUT-01..03`, `PRO-01`, `SET-01`, `A11Y-01`, `A11Y-02`, `PERF-01`, and mobile smoke `MOB-01..03`.
  - Supplemental cross-browser smoke passes on Firefox/WebKit (`XBR-01..02`).
  - Supplemental mobile cross-browser emulation passes on Android Chrome and iOS WebKit (`MXB-01..04`).
  - Production build passes (`npm -C frontendN run build`; static generation `19/19`).
  - API + websocket targets are environment-driven via `NEXT_PUBLIC_API_URL` (with local fallback), not hardcoded.
  - Release evidence captured in `docs/frontendN/11-release-evidence-2026-02-27.md`.
- Remaining quality debt:
  - No open scenario-coverage debt remains in the current test matrix.
  - `G6` runbook is now detailed in `docs/frontendN/09-cutover-checklist.md`.
  - `npm -C frontendN run verify:cutover` passes and is the canonical pre-cutover automation command.
  - Remaining launch blockers are manual parity walkthrough signoff, stakeholder approvals, and release-window execution.

