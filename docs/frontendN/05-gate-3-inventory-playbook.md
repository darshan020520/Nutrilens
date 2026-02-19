# Gate 3 Playbook - Inventory

## Frames
- G3-F01 to G3-F07.

## Focus Areas
- Inventory health and risk visibility.
- Item list actions and filters.
- Fuzzy add items with confirmation queue.
- Receipt processing and confirm-and-seed.
- Expiry, restock, makeable recipes, AI creative recipes.

## Implementation Checklist
1. Render status metrics and AI recommendations.
2. Keep item list both grid and list modes.
3. Support robust receipt pending review.
4. Keep restock bulk-add writeback behavior.
5. Ensure no destructive action lacks confirmation.

## Acceptance
- End-to-end receipt flow is stable.
- Restock to inventory loop works.
- Expiring items view supports day window filter.
