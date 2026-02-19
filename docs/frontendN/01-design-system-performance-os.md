# Design System - Performance OS

## Brand Direction
- Display font: Sora.
- UI font: Manrope.
- Tone: high-signal, coach-like, action-forward.

## Token Groups
- `--bg-*` canvas and backdrop layers.
- `--surface-*` elevation surfaces.
- `--text-*` hierarchy levels.
- `--brand-*` primary teal states.
- `--risk-*` amber/red alert states.
- `--success-*` positive states.
- `--info-*` neutral informational accents.

## Spatial Scale
- 4, 8, 12, 16, 24, 32, 40, 56.

## Radius Scale
- 8, 12, 16.

## Motion Rules
- Durations: 120ms, 180ms, 240ms.
- Easing: `cubic-bezier(0.2, 0, 0, 1)`.
- Motion allowed: state transitions, progressive reveals, dialogs, timeline updates.
- Motion not allowed: decorative infinite animations.

## Accessibility Rules
- Keyboard access for all actions.
- Focus-visible style mandatory.
- Color contrast must meet AA for text and controls.
- Landmark and semantic headings required per page.
- Screen reader labels for icon-only controls.
