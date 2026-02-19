# Cutover Checklist

## Pre-Cutover
- [ ] All gate playbooks marked complete.
- [ ] Feature parity matrix confirmed.
- [ ] Contract mismatch log reviewed and closed or accepted.
- [ ] Smoke suite green in CI.
- [ ] Manual UX pass on desktop and mobile complete.

## Release Readiness
- [ ] `frontendN` environment tested against backend.
- [ ] Rollback path validated (`frontend` remains intact).
- [ ] Stakeholder signoff complete.

## Launch
- [ ] Switch active frontend target to `frontendN`.
- [ ] Monitor critical routes and websocket notifications.
- [ ] Verify auth, onboarding, meals, inventory, nutrition in production-like env.

## Post-Launch
- [ ] 24h stability check.
- [ ] Record issues and prioritize hotfixes.
