# Ambrosia Python SDK

Ambrosia Python SDK for Index84/Index85 workflows. It defaults to
`AMBROSIA_API_URL` or `http://localhost:8000`, supports `AMBROSIA_TOKEN`, and
exposes read/write methods for reviews, relay evaluation, signals, backtests,
paper trades, and enterprise governance surfaces.

Core methods include:

- `health`, `health_detailed`, `list_reviews`, `create_review`, `get_review`
- `list_packets`, `create_packet`, `get_packet`, `market_snapshot`
- `relay_evaluate`, `relay_scorecard`, `create_signal`, `run_backtest`
- `create_paper_trade`, `create_service_account`, `rotate_service_account`, `revoke_service_account`
- `create_audit_export`, `configure_sso`, `get_sso_config`, `get_offline_bundle_manifest`