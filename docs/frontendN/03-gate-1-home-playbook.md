# Gate 1 Playbook - Command Center Home

## Frames
- G1-F01: daily hero + next action CTA.
- G1-F02: timeline context section.
- G1-F03: real quick actions.
- G1-F04: enhanced activity feed.
- G1-F05: notification center from websocket stream.

## Implementation Steps
1. Build hero card using dashboard summary values.
2. Add remaining calories and continue CTA.
3. Wire quick actions to real routes.
4. Keep summary cards and recent activity parity.
5. Add top bar notification drawer with unread counter.
6. Ensure websocket reconnect and fallback behavior.

## Acceptance
- Dashboard loads without placeholder text.
- Every quick action navigates to a real functional module.
- Notification drawer renders tracking events.
- Error states are recoverable with retry.
