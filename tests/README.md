# Stack Contract Tests

These tests verify that the repository still matches the MVP architecture described in the papers and README.

They are intentionally dependency-free Python `unittest` tests so they can run before the frontend or backend virtual environments are active.

Run from the repository root:

```powershell
pnpm test:stack
```

The tests check:

- Root monorepo scripts and package manager contract.
- Next.js/React frontend stack and pinned versions.
- Workbench feature surfaces: generated thesis, API creation/fallback, decision memory, calibration, source library, live metrics, validation.
- FastAPI backend dependency and endpoint surface.
- PostgreSQL/pgvector target schema.
- Evaluation fixture categories.
- README current-state and verification claims.