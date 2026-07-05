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
ambrosia --json signals create --name Momentum --formula "close/close_20d-1"
ambrosia --json backtests run --signal-id signal-123
ambrosia --json paper-trades create --decision-id dec-1 --ticker SOXX --quantity 1
ambrosia --json enterprise service-account --name ci-bot --scopes public:read,advanced:read
ambrosia --json enterprise service-account-rotate svc-123 --rotated-by ci
ambrosia --json enterprise service-account-revoke svc-123
ambrosia --json enterprise audit-export --requested-by admin --scope all
ambrosia --json enterprise sso-config --provider oidc --issuer-url https://idp.example.test --audience ambrosia-enterprise
ambrosia --json enterprise sso-get
ambrosia --json enterprise offline-bundle
ambrosia --json plans list
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