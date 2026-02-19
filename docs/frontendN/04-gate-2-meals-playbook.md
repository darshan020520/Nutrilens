# Gate 2 Playbook - Meals

## Frames
- G2-F01 to G2-F09.

## Focus Areas
- Today-first meal execution.
- Week plan generation and swap.
- External meal estimate->confirm flow.
- Semantic recipe browse and recipe details.
- History trend + adherence review.

## Implementation Checklist
1. Keep week and today query keys consistent.
2. Guarantee all mutations invalidate both tracking and meal-plan caches.
3. Surface recommendation text after log/skip/external actions.
4. Preserve grocery list dialog and alternatives flow.
5. Improve empty/no-plan/no-results states.

## Acceptance
- All current meal features work in `frontendN`.
- Swap and external flow complete with error recovery.
- History supports 7/14/30/90 day ranges.
