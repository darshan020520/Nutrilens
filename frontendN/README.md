# FrontendN

FrontendN is the parallel rebuild of NutriLens frontend using the Performance OS design direction.

## Run

```bash
npm install
npm run dev
```

The app runs on `http://localhost:3001`.

## Quality Commands

```bash
npm run lint
npm run typecheck
npm run test
npm run test:e2e
```

## Architecture

- `src/core`: API, auth, query, realtime, utilities
- `src/design`: token and motion primitives
- `src/shared`: shell and reusable state UI
- `src/features`: module boundaries
- `src/app`: route composition

## Planning Artifacts

See `../docs/frontendN` for gate playbooks and cutover checklist.
