from __future__ import annotations

import argparse
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from ambrosia_sdk import AmbrosiaApiError, AmbrosiaClient

DEFAULT_VERSION = "0.1.0"
DEFAULT_API_URL = "http://127.0.0.1:8001"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.resource is None:
        parser.print_help()
        try:
            print()
            print_context_hint(resolve_cli_context(args))
        except AmbrosiaApiError as exc:
            print()
            print(f"Configuration warning: {exc}")
        return 0

    context: dict[str, Any] | None = None
    try:
        context = resolve_cli_context(args)
        client = AmbrosiaClient(
            base_url=context["apiUrl"],
            token=context["token"],
            timeout=args.timeout,
        )
        result = dispatch(args, client, context)
    except AmbrosiaApiError as exc:
        payload = error_payload(exc, args=args, context=context)
        print_json(payload) if args.json else print_human(payload)
        return 1

    if args.json:
        print_json(result)
    else:
        print_human(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ambrosia",
        description="Ambrosia API/CLI decision platform",
        epilog="Examples: ambrosia commands list | ambrosia health --detailed | ambrosia --json signals list",
    )
    parser.add_argument("--api-url", default=None, help="Ambrosia API base URL; overrides AMBROSIA_API_URL and profile config")
    parser.add_argument("--token", default=None, help="Bearer token; overrides --token-file, AMBROSIA_TOKEN, and profile config")
    parser.add_argument("--token-file", default=None, help="Read bearer token from a local file instead of exposing it in shell history")
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
    parser.add_argument("--version", action="version", version=f"%(prog)s {cli_version()}")

    subcommands = parser.add_subparsers(dest="resource", required=False)

    subcommands.add_parser("status", help="Show CLI, profile, token, and API target status")

    quickstart = subcommands.add_parser("quickstart", help="Show or write first-run target configuration")
    quickstart.add_argument("--target", choices=["local", "staging", "production", "custom"], default="local")
    quickstart.add_argument("--api-url", dest="quickstart_api_url", default=None, help="API URL when --target custom is used")
    quickstart.add_argument("--write-profile", action="store_true", help="Write the selected API URL to ~/.ambrosia/config.json")
    quickstart.add_argument("--check", action="store_true", help="Check the selected API target health")

    commands = subcommands.add_parser("commands", help="Inspect numbered CLI command catalog")
    commands_sub = commands.add_subparsers(dest="action", required=True)
    commands_sub.add_parser("list", help="List all commands as numbered entries")
    commands_show = commands_sub.add_parser("show", help="Show one command by number")
    commands_show.add_argument("index", type=int)

    subcommands.add_parser("examples", help="Show common command examples")

    auth = subcommands.add_parser("auth", help="Manage local auth profile metadata")
    auth_sub = auth.add_subparsers(dest="action", required=True)
    auth_sub.add_parser("login", help="Validate configured token/profile")
    auth_sub.add_parser("token", help="Show whether a token is configured")
    auth_sub.add_parser("whoami", help="Show active profile and API URL")
    auth_sub.add_parser("logout", help="Return logout instructions for local profile")

    config = subcommands.add_parser("config", help="Read or describe CLI profile config")
    config_sub = config.add_subparsers(dest="action", required=True)
    config_sub.add_parser("show", help="Show resolved profile, API URL, and token source")
    config_sub.add_parser("profiles", help="List configured profile names")
    config_get = config_sub.add_parser("get", help="Get a config key")
    config_get.add_argument("key")
    config_set = config_sub.add_parser("set", help="Describe how a config key would be set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_set_api = config_sub.add_parser("set-api-url", help="Write an API URL for a profile")
    config_set_api.add_argument("profile_name")
    config_set_api.add_argument("api_url")

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
    relay_runs = relay_sub.add_parser("runs", help="List relay runs")
    relay_runs.add_argument("--limit", type=int, default=None)
    relay_runs.add_argument("--offset", type=int, default=0)
    relay_run_get = relay_sub.add_parser("get", help="Get one relay run")
    relay_run_get.add_argument("run_id")

    signals = subcommands.add_parser("signals", help="Create and inspect signal definitions")
    signals_sub = signals.add_subparsers(dest="action", required=True)
    signal_create = signals_sub.add_parser("create", help="Create a signal")
    signal_create.add_argument("--name", required=True)
    signal_create.add_argument("--formula", required=True)
    signal_create.add_argument("--universe", default="SPY")
    signal_create.add_argument("--horizon", default="20d")
    signals_sub.add_parser("list", help="List signals")
    signal_get = signals_sub.add_parser("get", help="Get one signal")
    signal_get.add_argument("signal_id")
    signal_link_review = signals_sub.add_parser("link-review", help="Link a review to a signal version")
    signal_link_review.add_argument("--signal-id", required=True)
    signal_link_review.add_argument("--review-id", required=True)
    signal_link_review.add_argument("--hypothesis-id", default=None)
    signal_link_review.add_argument("--signal-version", type=int, default=None)
    signal_wb_decision = signals_sub.add_parser("writeback-decision", help="Write back decision quality state")
    signal_wb_decision.add_argument("--signal-id", required=True)
    signal_wb_decision.add_argument("--review-id", required=True)
    signal_wb_decision.add_argument("--decision-state", required=True)
    signal_wb_decision.add_argument("--decision-action", choices=["BUY", "SELL", "HOLD", "HEDGE", "RISK_ADJUST", "BLOCK", "RETIRE"], default=None)
    signal_wb_decision.add_argument("--decision-quality", default="D2")
    signal_wb_decision.add_argument("--override-used", action="store_true")
    signal_wb_decision.add_argument("--rationale", default=None)
    signal_wb_decision.add_argument("--evidence-links", default="")
    signal_wb_decision.add_argument("--verifier-status", default=None)
    signal_wb_decision.add_argument("--review-date", default=None)
    signal_wb_outcome = signals_sub.add_parser("writeback-outcome", help="Write back signal outcome quality")
    signal_wb_outcome.add_argument("--signal-id", required=True)
    signal_wb_outcome.add_argument("--review-id", required=True)
    signal_wb_outcome.add_argument("--outcome-quality", required=True)
    signal_wb_outcome.add_argument("--last-reviewed-at", default=None)
    signals_sub.add_parser("quality-scorecard", help="Read weekly signal quality scorecard")

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
    paper_list = paper_sub.add_parser("list", help="List paper trades")
    paper_list.add_argument("--limit", type=int, default=None)
    paper_list.add_argument("--offset", type=int, default=0)

    warm = subcommands.add_parser("warm-path", help="Inspect warm-path execution intelligence events")
    warm_sub = warm.add_subparsers(dest="action", required=True)
    warm_ingest = warm_sub.add_parser("ingest", help="Ingest a warm-path event")
    warm_ingest.add_argument("--event-type", required=True)
    warm_ingest.add_argument("--ticker", required=True)
    warm_ingest.add_argument("--latency-ms", type=int, required=True)
    warm_ingest.add_argument("--notional-usd", type=float, required=True)
    warm_list = warm_sub.add_parser("list", help="List recent warm-path events")
    warm_list.add_argument("--limit", type=int, default=None)
    warm_list.add_argument("--offset", type=int, default=0)

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
    enterprise_sub.add_parser("service-accounts", help="List service accounts")
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


def dispatch(args: argparse.Namespace, client: AmbrosiaClient, context: dict[str, Any] | None = None) -> Any:
    if args.resource == "status":
        return get_status(context or client_context(args, client), client=client)

    if args.resource == "quickstart":
        return run_quickstart(args, client)

    if args.resource == "examples":
        return get_examples()

    if args.resource == "commands":
        catalog = get_command_catalog()
        if args.action == "show":
            if args.index < 1 or args.index > len(catalog):
                raise AmbrosiaApiError(f"Command index out of range: {args.index}")
            return catalog[args.index - 1]
        return catalog

    if args.resource == "auth":
        return dispatch_auth(args, client, context)
    if args.resource == "config":
        return dispatch_config(args, context)
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
        if args.action == "scorecard":
            return client.relay_scorecard()
        if args.action == "runs":
            return client.list_relay_runs(limit=args.limit, offset=args.offset)
        if args.action == "get":
            return client.get_relay_run(args.run_id)
        return client.relay_evaluate(args.question)
    if args.resource == "signals":
        if args.action == "list":
            return client.list_signals()
        if args.action == "get":
            return client.get_signal(args.signal_id)
        if args.action == "link-review":
            payload = {
                "reviewId": args.review_id,
                "hypothesisId": args.hypothesis_id,
                "signalVersion": args.signal_version,
            }
            return client.link_signal_review(args.signal_id, payload)
        if args.action == "writeback-decision":
            evidence_links = [link.strip() for link in args.evidence_links.split(",") if link.strip()]
            payload = {
                "reviewId": args.review_id,
                "decisionState": args.decision_state,
                "decisionAction": args.decision_action,
                "decisionQuality": args.decision_quality,
                "overrideUsed": args.override_used,
                "rationale": args.rationale,
                "evidenceLinks": evidence_links,
                "verifierStatus": args.verifier_status,
                "reviewDate": args.review_date,
            }
            return client.writeback_signal_decision(args.signal_id, payload)
        if args.action == "writeback-outcome":
            payload = {
                "reviewId": args.review_id,
                "outcomeQuality": args.outcome_quality,
            }
            if args.last_reviewed_at:
                payload["lastReviewedAt"] = args.last_reviewed_at
            return client.writeback_signal_outcome(args.signal_id, payload)
        if args.action == "quality-scorecard":
            return client.signal_quality_scorecard_weekly()
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
            return client.list_paper_trades(limit=args.limit, offset=args.offset)
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
            events = client.list_warm_path_events()
            if args.limit is None and args.offset == 0:
                return events
            if isinstance(events, dict):
                return events
            offset = max(0, args.offset)
            limit = args.limit or 100
            window = events[offset : offset + limit]
            return {
                "schemaVersion": "warm-path-events-list.v1",
                "items": window,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(events),
                    "hasMore": offset + limit < len(events),
                },
            }
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
        if args.action == "service-accounts":
            return client.list_service_accounts()
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


def dispatch_auth(args: argparse.Namespace, client: AmbrosiaClient, context: dict[str, Any] | None = None) -> dict[str, Any]:
    has_token = bool(client.token)
    if args.action == "login":
        return {"status": "ok" if has_token else "missing_token", "apiUrl": client.base_url}
    if args.action == "token":
        return {"configured": has_token, "source": (context or {}).get("tokenSource", "argument-or-profile-or-env")}
    if args.action == "whoami":
        return {"profile": args.profile, "apiUrl": client.base_url, "apiUrlSource": (context or {}).get("apiUrlSource"), "authenticated": has_token}
    if args.action == "logout":
        return {"status": "noop", "message": "Remove token from ~/.ambrosia/config.json or AMBROSIA_TOKEN."}
    raise AmbrosiaApiError(f"Unsupported auth action: {args.action}")


def dispatch_config(args: argparse.Namespace, context: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = load_profile(args.profile)
    if args.action == "show":
        return public_context(context or resolve_cli_context(args))
    if args.action == "profiles":
        config = read_config()
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        return {"profiles": sorted(profiles.keys()), "activeProfile": args.profile, "path": str(config_path())}
    if args.action == "get":
        return {"key": args.key, "value": profile.get(args.key)}
    if args.action == "set-api-url":
        write_profile_api_url(args.profile_name, args.api_url)
        return {"status": "written", "profile": args.profile_name, "apiUrl": args.api_url, "path": str(config_path())}
    return {"status": "dry_run", "key": args.key, "value": args.value, "path": str(Path.home() / ".ambrosia" / "config.json")}


def resolve_cli_context(args: argparse.Namespace) -> dict[str, Any]:
    profile = load_profile(args.profile)
    api_url, api_url_source = resolve_api_url(args, profile)
    token, token_source = resolve_token(args, profile)
    return {
        "profile": args.profile,
        "configPath": str(config_path()),
        "apiUrl": api_url,
        "apiUrlSource": api_url_source,
        "token": token,
        "tokenConfigured": bool(token),
        "tokenSource": token_source,
        "timeout": args.timeout,
    }


def client_context(args: argparse.Namespace, client: AmbrosiaClient) -> dict[str, Any]:
    return {
        "profile": args.profile,
        "configPath": str(config_path()),
        "apiUrl": client.base_url,
        "apiUrlSource": "client",
        "token": client.token,
        "tokenConfigured": bool(client.token),
        "tokenSource": "client" if client.token else "missing",
        "timeout": args.timeout,
    }


def resolve_api_url(args: argparse.Namespace, profile: dict[str, str | None]) -> tuple[str, str]:
    if args.api_url:
        return args.api_url, "flag"
    env_url = os.getenv("AMBROSIA_API_URL")
    if env_url:
        return env_url, "env"
    if profile.get("api_url"):
        return str(profile["api_url"]), "profile"
    return DEFAULT_API_URL, "default-local"


def resolve_token(args: argparse.Namespace, profile: dict[str, str | None]) -> tuple[str | None, str]:
    if args.token:
        return args.token, "flag"
    token_from_file = read_token_file(args.token_file)
    if token_from_file:
        return token_from_file, "token-file"
    env_token = os.getenv("AMBROSIA_TOKEN")
    if env_token:
        return env_token, "env"
    if profile.get("token"):
        return str(profile["token"]), "profile"
    return None, "missing"


def get_status(context: dict[str, Any], *, client: AmbrosiaClient | None = None) -> dict[str, Any]:
    payload = public_context(context)
    payload.update(
        {
            "status": "ok",
            "cliVersion": cli_version(),
            "sdkVersion": package_version("ambrosia-sdk"),
            "quickstart": "ambrosia quickstart",
        }
    )
    if client is not None:
        try:
            health = client.health()
            payload["apiReachable"] = True
            payload["apiHealth"] = health
        except AmbrosiaApiError as exc:
            payload["apiReachable"] = False
            payload["apiError"] = str(exc)
            payload["recovery"] = recovery_hints(context, target=exc.target)
    return payload


def run_quickstart(args: argparse.Namespace, client: AmbrosiaClient) -> dict[str, Any]:
    api_url = quickstart_api_url(args)
    result: dict[str, Any] = {
        "status": "ready",
        "target": args.target,
        "apiUrl": api_url,
        "writeProfile": bool(args.write_profile),
        "profile": args.profile,
        "nextCommands": [
            "ambrosia status",
            "ambrosia health --detailed",
            "ambrosia market snapshot GOOG",
            "ambrosia commands list",
        ],
    }
    if args.write_profile:
        write_profile_api_url(args.profile, api_url)
        result["configPath"] = str(config_path())
        result["message"] = f"Profile '{args.profile}' now uses {api_url}."
    else:
        result["message"] = "Dry run only. Add --write-profile to persist this API target."

    if args.check:
        check_client = AmbrosiaClient(base_url=api_url, token=client.token, timeout=client.timeout)
        try:
            result["apiReachable"] = True
            result["apiHealth"] = check_client.health()
        except AmbrosiaApiError as exc:
            result["apiReachable"] = False
            result["apiError"] = str(exc)
            result["recovery"] = recovery_hints({"apiUrl": api_url}, target=exc.target)
    return result


def quickstart_api_url(args: argparse.Namespace) -> str:
    if args.target == "local":
        return DEFAULT_API_URL
    if args.target == "staging":
        configured = os.getenv("AMBROSIA_STAGING_API_URL", "").strip()
        if configured:
            return configured.rstrip("/")
        raise AmbrosiaApiError(
            "AMBROSIA_STAGING_API_URL is required for the staging target"
        )
    if args.target == "production":
        configured = os.getenv("AMBROSIA_PRODUCTION_API_URL", "").strip()
        if configured:
            return configured.rstrip("/")
        raise AmbrosiaApiError(
            "AMBROSIA_PRODUCTION_API_URL is required for the production target"
        )
    if args.quickstart_api_url:
        return args.quickstart_api_url
    raise AmbrosiaApiError("--api-url is required when --target custom is used")


def public_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile": context.get("profile"),
        "configPath": context.get("configPath"),
        "apiUrl": context.get("apiUrl"),
        "apiUrlSource": context.get("apiUrlSource"),
        "tokenConfigured": bool(context.get("tokenConfigured")),
        "tokenSource": context.get("tokenSource"),
        "timeout": context.get("timeout"),
    }


def error_payload(exc: AmbrosiaApiError, *, args: argparse.Namespace, context: dict[str, Any] | None) -> dict[str, Any]:
    payload = {
        "status": "error",
        "message": str(exc),
        "statusCode": exc.status_code,
        "payload": exc.payload,
    }
    target = exc.target or (context or {}).get("apiUrl")
    if target:
        payload["target"] = target
    if "Ambrosia API unavailable" in str(exc):
        payload["recovery"] = recovery_hints(context or {"apiUrl": target}, target=target, command=args)
    return payload


def recovery_hints(context: dict[str, Any], *, target: str | None = None, command: argparse.Namespace | None = None) -> list[dict[str, str]]:
    command_text = command_example(command) if command is not None else "ambrosia health --detailed"
    tried = target or str(context.get("apiUrl") or DEFAULT_API_URL)
    hints = [
        {
            "label": "Start the local API",
            "command": f"uv run --project services/api uvicorn app.main:app --host 127.0.0.1 --port 8001  # attempted {tried}",
        },
    ]
    staging_url = os.getenv("AMBROSIA_STAGING_API_URL", "").strip().rstrip("/")
    if staging_url:
        hints.extend([
            {
                "label": "Use configured staging for this command",
                "command": command_text.replace(
                    "ambrosia ", f"ambrosia --api-url {staging_url} ", 1
                ),
            },
            {
                "label": "Make staging the default in new Windows terminals",
                "command": f"setx AMBROSIA_API_URL {staging_url}",
            },
        ])
    return hints


def command_example(command: argparse.Namespace) -> str:
    resource = getattr(command, "resource", None)
    action = getattr(command, "action", None)
    if resource == "market" and action == "snapshot":
        return f"ambrosia market snapshot {command.ticker}"
    if resource == "health":
        return "ambrosia health --detailed" if getattr(command, "detailed", False) else "ambrosia health"
    if resource:
        return f"ambrosia {resource}"
    return "ambrosia health --detailed"


def write_profile_api_url(profile_name: str, api_url: str) -> None:
    path = config_path()
    data = read_config()
    profiles = data.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        raise AmbrosiaApiError(f"Invalid profiles object in config: {path}")
    profile = profiles.setdefault(profile_name, {})
    if not isinstance(profile, dict):
        raise AmbrosiaApiError(f"Invalid profile '{profile_name}' in config: {path}")
    profile["api_url"] = api_url
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def config_path() -> Path:
    return Path.home() / ".ambrosia" / "config.json"


def read_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AmbrosiaApiError(f"Invalid profile config: {path}") from exc
    return existing if isinstance(existing, dict) else {}


def load_profile(profile_name: str) -> dict[str, str | None]:
    data = read_config()
    profile = data.get("profiles", {}).get(profile_name, {})
    if not isinstance(profile, dict):
        return {}
    return {
        "api_url": profile.get("api_url") or profile.get("apiUrl"),
        "token": profile.get("token"),
    }


def read_token_file(token_file: str | None) -> str | None:
    if not token_file:
        return None
    path = Path(token_file).expanduser()
    if not path.exists():
        raise AmbrosiaApiError(f"Token file not found: {path}")
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise AmbrosiaApiError(f"Token file is empty: {path}")
    return token


def cli_version() -> str:
    return package_version("ambrosia-cli")


def package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return DEFAULT_VERSION


def get_examples() -> list[dict[str, str]]:
    return [
        {"description": "Show current target/profile status", "command": "ambrosia status"},
        {"description": "Configure a hosted target", "command": "ambrosia quickstart --target custom --api-url https://api.example.com --write-profile"},
        {"description": "Show the command catalog", "command": "ambrosia commands list"},
        {"description": "Read API health", "command": "ambrosia health --detailed"},
        {"description": "Read market data from the active profile", "command": "ambrosia market snapshot GOOG"},
        {"description": "List signals as JSON", "command": "ambrosia --json signals list"},
        {"description": "Run the scanner", "command": "ambrosia scanner run --universe AAPL,MSFT,SPY --max-candidates 5"},
        {"description": "Create a signal", "command": "ambrosia signals create --name Momentum --formula \"close/close_20d-1\""},
        {"description": "Use a token file", "command": "ambrosia --token-file %USERPROFILE%\\.ambrosia\\token health"},
    ]


def get_command_catalog() -> list[dict[str, Any]]:
    parser = build_parser()
    catalog: list[dict[str, Any]] = []
    root_subparsers = None
    for action in parser._actions:  # type: ignore[attr-defined]
        if isinstance(action, argparse._SubParsersAction):  # type: ignore[attr-defined]
            root_subparsers = action
            break

    if root_subparsers is None:
        return catalog

    for resource_name, resource_parser in root_subparsers.choices.items():
        nested = None
        for action in resource_parser._actions:  # type: ignore[attr-defined]
            if isinstance(action, argparse._SubParsersAction):  # type: ignore[attr-defined]
                nested = action
                break

        if nested is None:
            catalog.append(
                {
                    "index": len(catalog) + 1,
                    "command": f"ambrosia {resource_name}",
                    "resource": resource_name,
                    "workflow": command_workflow(resource_name),
                    "summary": (getattr(resource_parser, "description", None) or "").strip(),
                }
            )
            continue

        for action_name, action_parser in nested.choices.items():
            usage = (action_parser.format_usage() or "").strip().replace("usage: ", "")
            catalog.append(
                {
                    "index": len(catalog) + 1,
                    "command": f"ambrosia {resource_name} {action_name}",
                    "resource": resource_name,
                    "action": action_name,
                    "workflow": command_workflow(resource_name),
                    "summary": (getattr(action_parser, "description", None) or "").strip(),
                    "usage": usage,
                }
            )

    return catalog


def command_workflow(resource_name: str) -> str:
    workflows = {
        "status": "Setup and diagnostics",
        "quickstart": "Setup and diagnostics",
        "commands": "Setup and diagnostics",
        "examples": "Setup and diagnostics",
        "auth": "Setup and diagnostics",
        "config": "Setup and diagnostics",
        "health": "Setup and diagnostics",
        "market": "Discovery",
        "scanner": "Discovery",
        "relay": "Discovery",
        "reviews": "Review and packets",
        "packets": "Review and packets",
        "signals": "Signals lifecycle",
        "alpha": "Alpha and execution",
        "backtests": "Alpha and execution",
        "paper-trades": "Alpha and execution",
        "warm-path": "Alpha and execution",
        "enterprise": "Enterprise controls",
        "jobs": "Automation",
        "plans": "Automation",
    }
    return workflows.get(resource_name, "Automation")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def print_human(payload: Any) -> None:
    if isinstance(payload, dict) and payload.get("status") == "error":
        print("Status: error")
        print(f"Reason: {payload.get('message')}")
        if payload.get("target"):
            print(f"Tried: {payload['target']}")
        recovery = payload.get("recovery")
        if isinstance(recovery, list) and recovery:
            print("Try one of these:")
            for index, item in enumerate(recovery, start=1):
                if isinstance(item, dict):
                    print(f"{index}. {item.get('label')}")
                    print(f"   {item.get('command')}")
        return

    if isinstance(payload, dict) and {"cliVersion", "apiUrl", "apiReachable"}.issubset(payload.keys()):
        print("Ambrosia CLI status")
        print(f"CLI version: {payload.get('cliVersion')}")
        print(f"SDK version: {payload.get('sdkVersion')}")
        print(f"Profile: {payload.get('profile')}")
        print(f"API URL: {payload.get('apiUrl')} ({payload.get('apiUrlSource')})")
        print(f"API reachable: {payload.get('apiReachable')}")
        print(f"Token: {payload.get('tokenSource')} ({'configured' if payload.get('tokenConfigured') else 'not configured'})")
        if payload.get("quickstart"):
            print(f"Quickstart: {payload['quickstart']}")
        recovery = payload.get("recovery")
        if isinstance(recovery, list) and recovery:
            print("Recovery:")
            for item in recovery:
                if isinstance(item, dict):
                    print(f"- {item.get('label')}: {item.get('command')}")
        return

    if isinstance(payload, dict) and {"target", "apiUrl", "nextCommands"}.issubset(payload.keys()):
        print(f"Quickstart target: {payload.get('target')}")
        print(f"API URL: {payload.get('apiUrl')}")
        print(str(payload.get("message", "")))
        print("Next commands:")
        for command in payload.get("nextCommands", []):
            print(f"- {command}")
        return

    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "index" in payload[0] and "command" in payload[0]:
        print(f"{len(payload)} command(s)")
        current_workflow = None
        for item in payload:
            workflow = item.get("workflow")
            if workflow and workflow != current_workflow:
                current_workflow = workflow
                print(f"\n{workflow}")
            print(f"{item['index']:>3}. {item['command']}")
        return

    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "description" in payload[0] and "command" in payload[0]:
        print(f"{len(payload)} example(s)")
        for item in payload:
            print(f"- {item['description']}: {item['command']}")
        return

    if isinstance(payload, dict) and "command" in payload:
        print(payload["command"])
        if payload.get("usage"):
            print(f"usage: {payload['usage']}")
        if payload.get("summary"):
            print(payload["summary"])
        return

    if isinstance(payload, dict) and {"items", "pagination"}.issubset(payload.keys()):
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
        print(f"{len(items)} item(s) [offset={pagination.get('offset', 0)} limit={pagination.get('limit', len(items))} total={pagination.get('total', len(items))}]")
        for item in items[:20]:
            if isinstance(item, dict):
                print(summary_line(item))
            else:
                print(item)
        return

    if isinstance(payload, list):
        print(f"{len(payload)} item(s)")
        for item in payload[:20]:
            if isinstance(item, dict):
                print(summary_line(item))
            else:
                print(item)
        return
    if isinstance(payload, dict):
        print(summary_line(payload))
        return
    print(payload)


def print_context_hint(context: dict[str, Any]) -> None:
    print("Current target")
    print(f"  Profile: {context.get('profile')}")
    print(f"  API URL: {context.get('apiUrl')} ({context.get('apiUrlSource')})")
    print(f"  Token: {context.get('tokenSource')} ({'configured' if context.get('tokenConfigured') else 'not configured'})")
    print("  Suggested next step: ambrosia quickstart")


def summary_line(item: dict[str, Any]) -> str:
    for key in ("id", "plan_id", "jobType", "service", "ticker", "title"):
        if key in item and item[key] is not None:
            return f"{key}: {item[key]}"
    return json.dumps(item, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
