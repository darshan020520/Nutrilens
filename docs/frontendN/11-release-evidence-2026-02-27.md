# Release Evidence - 2026-02-27

## Scope

Automated pre-cutover verification runs for `frontendN` in local rehearsal environment.

## Command Results

| Command | Result | Key Evidence |
|---|---|---|
| `npm -C frontendN run verify:cutover` | Pass | Composite run green (`verify:release` + desktop cross-browser + mobile cross-browser) |
| `npm -C frontendN run verify:release` | Pass | `lint` pass, `typecheck` pass, `vitest` `1/1` files and `2/2` tests pass, Playwright `43/43` pass (includes `MOB-01..03`) |
| `npm -C frontendN run test:e2e:cross-browser` | Pass | Firefox/WebKit smoke `10/10` pass |
| `npm -C frontendN run test:e2e:mobile-cross-browser` | Pass | Android Chrome + iOS WebKit mobile smoke `6/6` pass |
| `npm -C frontendN run build` | Pass | Next.js production build completes; static page generation `19/19` |

## Notes

- All automated gates required by `docs/frontendN/09-cutover-checklist.md` section `Quality Gate Re-Run` are green.
- Build-time blocker (`useSearchParams` without Suspense on `/login`) was fixed by wrapping search-param pages in Suspense-safe page shells.
- API base URL and websocket tracking endpoint were hardened to use `NEXT_PUBLIC_API_URL` (with safe local fallback), removing hardcoded `localhost` dependency for release deployment.
- Remaining cutover blockers are manual parity walkthrough signoff, stakeholder approvals, and release-window authorization.
