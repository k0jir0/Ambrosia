from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ambrosia_sdk import AmbrosiaApiError, AmbrosiaClient


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    profile = load_profile(args.profile)
    client = AmbrosiaClient(
        base_url=args.api_url or profile.get("api_url"),
        token=args.token or profile.get("token"),
        timeout=args.timeout,
    )

    try:
        result = dispatch(args, client)
    except AmbrosiaApiError as exc:
        payload = {
            "status": "error",
            "message": str(exc),
            "statusCode": exc.status_code,
            "payload": exc.payload,
        }
        print_json(payload)
        return 1

    if args.json:
        print_json(result)
    else:
        print_human(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ambrosia", description="Ambrosia API/CLI decision platform")
    parser.add_argument("--api-url", default=os.getenv("AMBROSIA_API_URL"), help="Ambrosia API base URL")
    parser.add_argument("--token", default=os.getenv("AMBROSIA_TOKEN"), help="Bearer token or env-provided token")
    parser.add_argument("--profile", default="default", help="Profile name from ~/.ambrosia/config.json")
    parser.add_argument("--timeout", type=float, default=65.0, help="Request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--yaml", action="store_true", help="Accepted for automation; JSON is emitted until YAML output is packaged")
    parser.add_argument("--table", action="store_true", help="Print compact human table summaries")
    parser.add_argument("--output", default=None, help="Optional output path reserved for generated artifacts")
    parser.add_argument("--org", default=None, help="Organization scope")
    parser.add_argument("--workspace", default=None, help="Workspace scope")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential human output")
    parser.add_argument("--verbose", action="store_true", help="Include verbose diagnostics when available")
    parser.add_argument("--no-color", action="store_true", help="Accepted for automation; output never relies on color")

    subcommands = parser.add_subparsers(dest="resource", required=True)

    auth = subcommands.add_parser("auth", help="Manage local auth profile metadata")
    auth_sub = auth.add_subparsers(dest="action", required=True)
    auth_sub.add_parser("login", help="Validate configured token/profile")
    auth_sub.add_parser("token", help="Show whether a token is configured")
    auth_sub.add_parser("whoami", help="Show active profile and API URL")
    auth_sub.add_parser("logout", help="Return logout instructions for local profile")

    config = subcommands.add_parser("config", help="Read or describe CLI profile config")
    config_sub = config.add_subparsers(dest="action", required=True)
    config_get = config_sub.add_parser("get", help="Get a config key")
    config_get.add_argument("key")
    config_set = config_sub.add_parser("set", help="Describe how a config key would be set")
    config_set.add_argument("key")
    config_set.add_argument("value")

    health = subcommands.add_parser("health", help="Read API health")
    health.add_argument("--detailed", action="store_true", help="Read /health/detailed")

    reviews = subcommands.add_parser("reviews", help="Read reviews")
    reviews_sub = reviews.add_subparsers(dest="action", required=True)
    reviews_sub.add_parser("list", help="List reviews")
    review_get = reviews_sub.add_parser("get", help="Get one review")
    review_get.add_argument("review_id")
    review_create = reviews_sub.add_parser("create", help="Create a review")
    review_create.add_argument("--thesis", required=True)
    review_create.add_argument("--ticker", default="Unspecified")
    review_create.add_argument("--asset-class", default="Unspecified")
    review_create.add_argument("--time-horizon", default="Unspecified")

    packets = subcommands.add_parser("packets", help="Read packets")
    packets_sub = packets.add_subparsers(dest="action", required=True)
    packets_sub.add_parser("list", help="List packets")
    packet_get = packets_sub.add_parser("get", help="Get one packet")
    packet_get.add_argument("packet_id")
    packet_create = packets_sub.add_parser("create", help="Create a packet from a JSON payload")
    packet_create.add_argument("--payload", required=True, help="Inline JSON object")
    packet_audit = packets_sub.add_parser("audit", help="Read packet audit")
    packet_audit.add_argument("packet_id")

    market = subcommands.add_parser("market", help="Read market data")
    market_sub = market.add_subparsers(dest="action", required=True)
    market_snapshot = market_sub.add_parser("snapshot", help="Read market snapshot")
    market_snapshot.add_argument("ticker")

    scanner = subcommands.add_parser("scanner", help="Run scanner jobs")
    scanner_sub = scanner.add_subparsers(dest="action", required=True)
    scanner_run = scanner_sub.add_parser("run", help="Run a deterministic scanner")
    scanner_run.add_argument("--universe", default="", help="Comma-separated tickers")
    scanner_run.add_argument("--max-candidates", type=int, default=10)

    jobs = subcommands.add_parser("jobs", help="Read async jobs")
    jobs_sub = jobs.add_subparsers(dest="action", required=True)
    jobs_sub.add_parser("list", help="List jobs")
    job_get = jobs_sub.add_parser("get", help="Get one job")
    job_get.add_argument("job_id")
    job_wait = jobs_sub.add_parser("wait", help="Read a job as a wait-compatible operation")
    job_wait.add_argument("job_id")

    plans = subcommands.add_parser("plans", help="Read roadmap plans")
    plans_sub = plans.add_subparsers(dest="action", required=True)
    plans_sub.add_parser("list", help="List roadmap plans")
    plan_get = plans_sub.add_parser("get", help="Get one roadmap plan")
    plan_get.add_argument("plan_id")

    relay = subcommands.add_parser("relay", help="Run and inspect benchmark relay traces")
    relay_sub = relay.add_subparsers(dest="action", required=True)
    relay_eval = relay_sub.add_parser("evaluate", help="Evaluate a benchmark question")
    relay_eval.add_argument("--question", required=True)
    relay_sub.add_parser("scorecard", help="Read relay scorecard")

    signals = subcommands.add_parser("signals", help="Create and inspect signal definitions")
    signals_sub = signals.add_subparsers(dest="action", required=True)
    signal_create = signals_sub.add_parser("create", help="Create a signal")
    signal_create.add_argument("--name", required=True)
    signal_create.add_argument("--formula", required=True)
    signal_create.add_argument("--universe", default="SPY")
    signal_create.add_argument("--horizon", default="20d")
    signals_sub.add_parser("list", help="List signals")

    alpha = subcommands.add_parser("alpha", help="Manage alpha hypotheses and decay analytics")
    alpha_sub = alpha.add_subparsers(dest="action", required=True)
    alpha_create = alpha_sub.add_parser("create", help="Create an alpha hypothesis")
    alpha_create.add_argument("--title", required=True)
    alpha_create.add_argument("--signal-family", required=True)
    alpha_create.add_argument("--thesis", required=True)
    alpha_create.add_argument("--universe", default="SPY")
    alpha_create.add_argument("--horizon", default="20d")
    alpha_sub.add_parser("list", help="List alpha hypotheses")
    alpha_decay = alpha_sub.add_parser("decay", help="Read alpha decay analytics for a signal")
    alpha_decay.add_argument("--signal-id", required=True)

    backtests = subcommands.add_parser("backtests", help="Run backtests")
    backtests_sub = backtests.add_subparsers(dest="action", required=True)
    backtest_run = backtests_sub.add_parser("run", help="Run a signal backtest")
    backtest_run.add_argument("--signal-id", required=True)

    paper = subcommands.add_parser("paper-trades", help="Create and inspect paper trades")
    paper_sub = paper.add_subparsers(dest="action", required=True)
    paper_create = paper_sub.add_parser("create", help="Create a paper trade")
    paper_create.add_argument("--decision-id", required=True)
    paper_create.add_argument("--ticker", required=True)
    paper_create.add_argument("--quantity", type=float, required=True)
    paper_create.add_argument("--side", default="buy")
    paper_create.add_argument("--intended-price", type=float, default=100.0)
    paper_sub.add_parser("list", help="List paper trades")

    warm = subcommands.add_parser("warm-path", help="Inspect warm-path execution intelligence events")
    warm_sub = warm.add_subparsers(dest="action", required=True)
    warm_ingest = warm_sub.add_parser("ingest", help="Ingest a warm-path event")
    warm_ingest.add_argument("--event-type", required=True)
    warm_ingest.add_argument("--ticker", required=True)
    warm_ingest.add_argument("--latency-ms", type=int, required=True)
    warm_ingest.add_argument("--notional-usd", type=float, required=True)
    warm_sub.add_parser("list", help="List recent warm-path events")

    enterprise = subcommands.add_parser("enterprise", help="Enterprise governance operations")
    enterprise_sub = enterprise.add_subparsers(dest="action", required=True)
    svc_create = enterprise_sub.add_parser("service-account", help="Create service account")
    svc_create.add_argument("--name", required=True)
    svc_create.add_argument("--scopes", default="public:read")
    svc_rotate = enterprise_sub.add_parser("service-account-rotate", help="Rotate a service account token")
    svc_rotate.add_argument("service_account_id")
    svc_rotate.add_argument("--rotated-by", default="system")
    svc_revoke = enterprise_sub.add_parser("service-account-revoke", help="Revoke a service account")
    svc_revoke.add_argument("service_account_id")
    audit_export = enterprise_sub.add_parser("audit-export", help="Create audit export")
    audit_export.add_argument("--requested-by", default="admin")
    audit_export.add_argument("--scope", default="all")
    sso_config = enterprise_sub.add_parser("sso-config", help="Configure enterprise SSO")
    sso_config.add_argument("--provider", choices=["oidc", "saml"], required=True)
    sso_config.add_argument("--issuer-url", required=True)
    sso_config.add_argument("--audience", required=True)
    sso_config.add_argument("--default-role", default="viewer")
    sso_config.add_argument("--role-mappings", default="{}", help="JSON object mapping identity groups to Ambrosia roles")
    enterprise_sub.add_parser("sso-get", help="Read enterprise SSO config")
    enterprise_sub.add_parser("offline-bundle", help="Read offline/private deployment bundle manifest")
    enterprise_sub.add_parser("security-packet", help="Read enterprise support/security packet")
    enterprise_sub.add_parser("readiness", help="Read enterprise readiness")

    return parser


def dispatch(args: argparse.Namespace, client: AmbrosiaClient) -> Any:
    if args.resource == "auth":
        return dispatch_auth(args, client)
    if args.resource == "config":
        return dispatch_config(args)
    if args.resource == "health":
        return client.health_detailed() if args.detailed else client.health()
    if args.resource == "reviews":
        if args.action == "list":
            return client.list_reviews()
        if args.action == "create":
            return client.create_review(
                args.thesis,
                ticker=args.ticker,
                asset_class=args.asset_class,
                time_horizon=args.time_horizon,
            )
        return client.get_review(args.review_id)
    if args.resource == "packets":
        if args.action == "list":
            return client.list_packets()
        if args.action == "create":
            return client.create_packet(json.loads(args.payload))
        if args.action == "audit":
            return client._get(f"/packets/{args.packet_id}/audit")
        return client.get_packet(args.packet_id)
    if args.resource == "market":
        return client.market_snapshot(args.ticker)
    if args.resource == "scanner":
        universe = [ticker.strip() for ticker in args.universe.split(",") if ticker.strip()] or None
        return client.scanner_run(universe=universe, max_candidates=args.max_candidates)
    if args.resource == "jobs":
        if args.action == "list":
            return client.list_jobs()
        return client.wait_job(args.job_id) if args.action == "wait" else client.get_job(args.job_id)
    if args.resource == "plans":
        return client.list_plans() if args.action == "list" else client.get_plan(args.plan_id)
    if args.resource == "relay":
        return client.relay_scorecard() if args.action == "scorecard" else client.relay_evaluate(args.question)
    if args.resource == "signals":
        if args.action == "list":
            return client._get("/signals")
        return client.create_signal(
            {
                "name": args.name,
                "formula": args.formula,
                "universe": [ticker.strip() for ticker in args.universe.split(",") if ticker.strip()],
                "horizon": args.horizon,
            }
        )
    if args.resource == "alpha":
        if args.action == "list":
            return client.list_alpha_hypotheses()
        if args.action == "decay":
            return client.get_alpha_decay(args.signal_id)
        return client.create_alpha_hypothesis(
            {
                "title": args.title,
                "signalFamily": args.signal_family,
                "thesis": args.thesis,
                "universe": [ticker.strip() for ticker in args.universe.split(",") if ticker.strip()],
                "horizon": args.horizon,
                "disconfirmingTests": ["degrade if IC drops below 0.03"],
            }
        )
    if args.resource == "backtests":
        return client.run_backtest(args.signal_id)
    if args.resource == "paper-trades":
        if args.action == "list":
            return client._get("/paper-trades")
        return client.create_paper_trade(
            {
                "decisionId": args.decision_id,
                "ticker": args.ticker,
                "quantity": args.quantity,
                "side": args.side,
                "intendedPrice": args.intended_price,
            }
        )
    if args.resource == "warm-path":
        if args.action == "list":
            return client.list_warm_path_events()
        return client.ingest_warm_path_event(
            {
                "eventType": args.event_type,
                "ticker": args.ticker,
                "latencyMs": args.latency_ms,
                "notionalUsd": args.notional_usd,
                "source": "cli",
            }
        )
    if args.resource == "enterprise":
        if args.action == "service-account":
            return client.create_service_account(args.name, [scope.strip() for scope in args.scopes.split(",") if scope.strip()])
        if args.action == "service-account-rotate":
            return client.rotate_service_account(args.service_account_id, rotated_by=args.rotated_by)
        if args.action == "service-account-revoke":
            return client.revoke_service_account(args.service_account_id)
        if args.action == "audit-export":
            return client.create_audit_export(requested_by=args.requested_by, scope=args.scope)
        if args.action == "sso-config":
            return client.configure_sso(
                provider=args.provider,
                issuer_url=args.issuer_url,
                audience=args.audience,
                default_role=args.default_role,
                role_mappings=json.loads(args.role_mappings),
            )
        if args.action == "sso-get":
            return client.get_sso_config()
        if args.action == "offline-bundle":
            return client.get_offline_bundle_manifest()
        if args.action == "security-packet":
            return client.get_enterprise_security_packet()
        return client._get("/enterprise/readiness")
    raise AmbrosiaApiError(f"Unsupported command: {args.resource}")


def dispatch_auth(args: argparse.Namespace, client: AmbrosiaClient) -> dict[str, Any]:
    has_token = bool(client.token)
    if args.action == "login":
        return {"status": "ok" if has_token else "missing_token", "apiUrl": client.base_url}
    if args.action == "token":
        return {"configured": has_token, "source": "argument-or-profile-or-env"}
    if args.action == "whoami":
        return {"profile": args.profile, "apiUrl": client.base_url, "authenticated": has_token}
    if args.action == "logout":
        return {"status": "noop", "message": "Remove token from ~/.ambrosia/config.json or AMBROSIA_TOKEN."}
    raise AmbrosiaApiError(f"Unsupported auth action: {args.action}")


def dispatch_config(args: argparse.Namespace) -> dict[str, Any]:
    profile = load_profile(args.profile)
    if args.action == "get":
        return {"key": args.key, "value": profile.get(args.key)}
    return {"status": "dry_run", "key": args.key, "value": args.value, "path": str(Path.home() / ".ambrosia" / "config.json")}


def load_profile(profile_name: str) -> dict[str, str | None]:
    config_path = Path.home() / ".ambrosia" / "config.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AmbrosiaApiError(f"Invalid profile config: {config_path}") from exc
    profile = data.get("profiles", {}).get(profile_name, {})
    if not isinstance(profile, dict):
        return {}
    return {
        "api_url": profile.get("api_url") or profile.get("apiUrl"),
        "token": profile.get("token"),
    }


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def print_human(payload: Any) -> None:
    if isinstance(payload, list):
        print(f"{len(payload)} item(s)")
        for item in payload[:20]:
            print(summary_line(item))
        return
    if isinstance(payload, dict):
        print(summary_line(payload))
        return
    print(payload)


def summary_line(item: dict[str, Any]) -> str:
    for key in ("id", "plan_id", "jobType", "service", "ticker", "title"):
        if key in item and item[key] is not None:
            return f"{key}: {item[key]}"
    return json.dumps(item, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())