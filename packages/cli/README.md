# Ambrosia CLI

Ambrosia CLI for Index84/Index85 automation. Supports read and write operations
for relay evaluation, signals, backtests, paper trades, and enterprise controls.

## Fastest hosted use

For immediate hosted operation, point the CLI at staging and verify status:

```powershell
setx AMBROSIA_API_URL https://ambrosia-api-staging.onrender.com
ambrosia status
ambrosia market snapshot GOOG
```

Open a new terminal after `setx`. For a one-command override, put the target on
the command itself:

```powershell
ambrosia --api-url https://ambrosia-api-staging.onrender.com market snapshot GOOG
```

The CLI also includes a first-run helper:

```powershell
ambrosia quickstart --target staging --write-profile
ambrosia status
```

## Install locally

From the repository root:

```bash
pnpm cli:install
pnpm cli:menu
```

To build local SDK/CLI wheels and install Ambrosia CLI into an isolated local
environment:

```powershell
pnpm cli:install:dist
```

To also add that isolated install to your user PATH:

```powershell
pnpm cli:install:path
```

This installs into `.local/ambrosia-cli` and uses local wheels from
`dist/ambrosia-cli`, so it does not require publishing to PyPI.

To build an optional single-file Windows executable:

```powershell
pnpm cli:build:exe
```

The executable is written to `dist/ambrosia-cli-exe/ambrosia.exe`.

Or directly from the CLI package:

```bash
cd packages/cli
uv sync
uv run ambrosia commands list
```

For Windows operators, double-click `launch-ambrosia-cli-menu.bat` at the repo
root. It opens a persistent command menu, shows the active API target, lets you
choose local/staging/production/custom targets, and remains usable until you
choose `Q`.

To make `ambrosia` available from new PowerShell sessions, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-ambrosia-cli.ps1 -AddToPath
```

For a distribution-style install from local wheels, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-ambrosia-cli.ps1 -Distribution -BuildDistribution -AddToPath
```

Open a new terminal after changing PATH.

## Discover commands

```bash
ambrosia --help
ambrosia --version
ambrosia status
ambrosia quickstart --target staging
ambrosia examples
ambrosia commands list
ambrosia commands show 12
ambrosia config show
ambrosia config profiles
```

Examples:

```bash
ambrosia --json health --detailed
ambrosia --json status
ambrosia --json quickstart --target staging
ambrosia --json reviews list
ambrosia --json reviews create --thesis "Semiconductor breadth improving" --ticker SOXX
ambrosia --json packets get pkt-123
ambrosia --json market snapshot SPY
ambrosia --json relay evaluate --question "What evidence supports margin expansion?"
ambrosia --json relay runs --limit 25
ambrosia --json relay get relay-run-123
ambrosia --json signals create --name Momentum --formula "close/close_20d-1"
ambrosia --json signals get signal-123
ambrosia --json signals link-review --signal-id signal-123 --review-id review-1
ambrosia --json signals writeback-decision --signal-id signal-123 --review-id review-1 --decision-state pursue --decision-quality D4 --evidence-links "docs/evidence-1,docs/evidence-2" --verifier-status passed --review-date 2026-07-06
ambrosia --json signals writeback-outcome --signal-id signal-123 --review-id review-1 --outcome-quality O3
ambrosia --json signals quality-scorecard
ambrosia --json backtests run --signal-id signal-123
ambrosia --json paper-trades create --decision-id dec-1 --ticker SOXX --quantity 1
ambrosia --json paper-trades list --limit 20 --offset 0
ambrosia --json warm-path list --limit 50
ambrosia --json enterprise service-account --name ci-bot --scopes public:read,advanced:read
ambrosia --json enterprise service-accounts
ambrosia --json enterprise service-account-rotate svc-123 --rotated-by ci
ambrosia --json enterprise service-account-revoke svc-123
ambrosia --json enterprise audit-export --requested-by admin --scope all
ambrosia --json enterprise sso-config --provider oidc --issuer-url https://idp.example.test --audience ambrosia-enterprise
ambrosia --json enterprise sso-get
ambrosia --json enterprise offline-bundle
ambrosia --json plans list
ambrosia --json commands list
ambrosia --json commands show 12
```

Core command forms:

```bash
ambrosia relay evaluate --question "What evidence supports margin expansion?"
ambrosia signals create --name Momentum --formula "close/close_20d-1"
ambrosia backtests run --signal-id signal-123
ambrosia paper-trades create --decision-id dec-1 --ticker SOXX --quantity 1
ambrosia enterprise service-account --name ci-bot
ambrosia enterprise audit-export --requested-by admin --scope all
```