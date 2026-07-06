# Ambrosia CLI

Ambrosia CLI for Index84/Index85 automation. Supports read and write operations
for relay evaluation, signals, backtests, paper trades, and enterprise controls.

Examples:

```bash
ambrosia --json health --detailed
ambrosia --json reviews list
ambrosia --json reviews create --thesis "Semiconductor breadth improving" --ticker SOXX
ambrosia --json packets get pkt-123
ambrosia --json market snapshot SPY
ambrosia --json relay evaluate --question "What evidence supports margin expansion?"
ambrosia --json relay runs --limit 25
ambrosia --json relay get relay-run-123
ambrosia --json signals create --name Momentum --formula "close/close_20d-1"
ambrosia --json signals get signal-123
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