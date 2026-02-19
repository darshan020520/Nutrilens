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
