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

## CLI Design E2E

The Ambrosia CLI design suite lives at [tests/test_cli_design_e2e.py](tests/test_cli_design_e2e.py).

It validates:

- `ambrosia` no-argument help/discovery behavior.
- Target/profile status and quickstart behavior.
- API-unavailable recovery output with actionable staging/local commands.
- Version, examples, numbered command catalog, and command-detail output.
- JSON output and `--token-file` behavior without leaking token contents.
- Clean error handling without tracebacks for expected user mistakes.
- CLI package metadata for the local SDK dependency and entrypoint.
- Root package scripts for local install, wheel distribution, PATH install, and executable build.
- Windows launcher target-awareness for status, target choice, and quick checks.
- The optional standalone executable catalog when `dist/ambrosia-cli-exe/ambrosia.exe` exists.

Run it from the repository root:

```powershell
pnpm test:cli:e2e
```

## CLI Live Function Matrix

The live Ambrosia CLI function matrix lives at [tests/test_cli_live_function_matrix.py](tests/test_cli_live_function_matrix.py).

It invokes every cataloged CLI command with representative arguments against a live Ambrosia API target and writes:

- `artifacts/cli-live-function-matrix.json`
- `artifacts/cli-live-function-matrix.md`

Run it explicitly:

```powershell
$env:RUN_CLI_LIVE_E2E="true"
$env:CLI_LIVE_API_URL="https://ambrosia-api-staging.onrender.com"
pnpm test:cli:live
```

By default it records failures and blocked dependency cases without failing the pytest run. Set `STRICT_CLI_LIVE_E2E=true` when you want any broken CLI command to fail the suite.

## Deploy-Targeted E2E (Staging + Production)

An opt-in deploy-targeted suite lives at [tests/test_deploy_targets_e2e.py](tests/test_deploy_targets_e2e.py).

It validates:

- Staging and production web root reachability.
- Staging and production API `/health` reachability.
- Staging Index96 surfaces (`/market-scanner`, `/alpha`, `/signals`).
- Staging API scanner and signals contracts.

Run it with environment flags so normal local runs remain fast and isolated:

```powershell
$env:RUN_DEPLOY_E2E="true"
pnpm test:deploy:e2e
```

Optional overrides:

- `STAGING_WEB_URL`
- `STAGING_API_URL`
- `PRODUCTION_WEB_URL`
- `PRODUCTION_API_URL`
- `DEPLOY_TARGETS` (comma-separated: `staging,production`)