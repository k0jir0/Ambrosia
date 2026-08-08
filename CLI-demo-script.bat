@where python >nul 2>nul && python -x "%~f0" %* || py -3 -x "%~f0" %* & goto :eof
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CLI_DIR = ROOT / "packages" / "cli"
SDK_DIR = ROOT / "packages" / "sdk-python"
CLI_MAIN = "from ambrosia_cli.main import main; raise SystemExit(main())"
DEFAULT_API_URL = "http://127.0.0.1:8001"
PRODUCTION_HINTS = ("production", "prod")


@dataclass
class DemoResult:
    name: str
    command: list[str]
    status: str
    returncode: int | None = None
    duration_seconds: float = 0.0
    stdout_path: str | None = None
    stderr_path: str | None = None
    reason: str | None = None
    payload: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": ["ambrosia", *self.command],
            "status": self.status,
            "returncode": self.returncode,
            "durationSeconds": round(self.duration_seconds, 3),
            "stdoutPath": self.stdout_path,
            "stderrPath": self.stderr_path,
            "reason": self.reason,
            "payloadPreview": _redact(self.payload),
        }


@dataclass
class DemoState:
    suffix: str
    review_id: str | None = None
    packet_id: str | None = None
    job_id: str | None = None
    plan_id: str | None = None
    relay_run_id: str | None = None
    signal_id: str | None = None
    service_account_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a positive-functioning demo across the Ambrosia CLI command surface.",
    )
    parser.add_argument("--api-url", default=os.getenv("DEMO_API_URL") or os.getenv("AMBROSIA_API_URL") or DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("CLI_DEMO_TIMEOUT_SECONDS", "45")))
    parser.add_argument("--allow-production", action="store_true", help="Allow demo writes against a production-looking API URL")
    parser.add_argument("--list-only", action="store_true", help="List the demo command sequence without running it")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    if _looks_like_production(api_url) and not args.allow_production:
        print(f"[STOP] Refusing to run mutating demo commands against production-looking target: {api_url}")
        print("       Re-run with --allow-production only if you intentionally want production demo writes.")
        return 2

    suffix = str(int(time.time()))
    output_dir = ROOT / ".local" / "cli-demo" / suffix
    output_dir.mkdir(parents=True, exist_ok=True)
    state = DemoState(suffix=suffix)
    runner = CliRunner(api_url=api_url, timeout=args.timeout, output_dir=output_dir)

    print("Ambrosia CLI positive-functioning demo")
    print(f"Project: {ROOT}")
    print(f"API URL: {api_url}")
    print(f"Output: {output_dir}")
    print("Note: this demo creates temporary review, packet, signal, trade, warm-path, and enterprise objects on the target API.")

    command_names = demo_command_names()
    if args.list_only:
        print("\nCommand sequence:")
        for index, name in enumerate(command_names, start=1):
            print(f"{index:02d}. {name}")
        return 0

    results: list[DemoResult] = []
    run = lambda name, command, api=True: _record(results, runner.run(name, command, api=api))

    run("commands list", ["commands", "list"], api=False)
    run("commands show", ["commands", "show", "1"], api=False)
    run("examples", ["examples"], api=False)
    run("status", ["status"])
    run("quickstart staging check", ["quickstart", "--target", "staging", "--check"], api=False)
    run("auth login", ["auth", "login"], api=False)
    run("auth token", ["auth", "token"], api=False)
    run("auth whoami", ["auth", "whoami"], api=False)
    run("auth logout", ["auth", "logout"], api=False)
    run("config show", ["config", "show"], api=False)
    run("config profiles", ["config", "profiles"], api=False)
    run("config get api_url", ["config", "get", "api_url"], api=False)
    run("config set dry run", ["config", "set", "api_url", api_url], api=False)
    run("config set-api-url cli-demo", ["config", "set-api-url", "cli-demo", api_url], api=False)

    run("health", ["health"])
    run("health detailed", ["health", "--detailed"])

    reviews_list = run("reviews list", ["reviews", "list"])
    state.review_id = _first_id(reviews_list, "id", "reviewId")
    review_create = run(
        "reviews create",
        [
            "reviews",
            "create",
            "--thesis",
            f"CLI demo review {suffix}: staged accessibility walkthrough",
            "--ticker",
            "AAPL",
            "--asset-class",
            "Equity",
            "--time-horizon",
            "2-6 weeks",
        ],
    )
    state.review_id = _first_id(review_create, "id", "reviewId") or state.review_id
    if state.review_id:
        run("reviews get", ["reviews", "get", state.review_id])
    else:
        _blocked(results, "reviews get", ["reviews", "get", "<review_id>"], "no review id available")

    packet_list = run("packets list", ["packets", "list"])
    state.packet_id = _first_id(packet_list, "id", "packetId")
    packet_payload = _packet_payload(suffix)
    packet_create = run("packets create", ["packets", "create", "--payload", json.dumps(packet_payload, separators=(",", ":"))])
    state.packet_id = _first_id(packet_create, "id", "packetId") or state.packet_id or packet_payload["id"]
    if state.packet_id:
        run("packets get", ["packets", "get", state.packet_id])
        run("packets audit", ["packets", "audit", state.packet_id])
        try:
            job_seed = api_post(api_url, f"/packets/{state.packet_id}/backtest/run/async", {"forceRun": True}, args.timeout)
            state.job_id = _first_id(job_seed, "id", "jobId")
        except Exception as exc:  # Keep the CLI demo moving if optional setup fails.
            print(f"[WARN] Could not seed async packet job: {exc}")
    else:
        _blocked(results, "packets get", ["packets", "get", "<packet_id>"], "no packet id available")
        _blocked(results, "packets audit", ["packets", "audit", "<packet_id>"], "no packet id available")

    run("market snapshot", ["market", "snapshot", "GOOG"])
    run("scanner run", ["scanner", "run", "--universe", "AAPL,MSFT,SPY", "--max-candidates", "3"])

    jobs_list = run("jobs list", ["jobs", "list"])
    state.job_id = state.job_id or _first_id(jobs_list, "id", "jobId")
    if state.job_id:
        run("jobs get", ["jobs", "get", state.job_id])
        run("jobs wait", ["jobs", "wait", state.job_id])
    else:
        _blocked(results, "jobs get", ["jobs", "get", "<job_id>"], "no job id available")
        _blocked(results, "jobs wait", ["jobs", "wait", "<job_id>"], "no job id available")

    try:
        api_post(api_url, "/roadmap/sync-plans", {}, args.timeout)
    except Exception as exc:
        print(f"[WARN] Could not sync roadmap plans before plan demo: {exc}")
    plans_list = run("plans list", ["plans", "list"])
    state.plan_id = _first_id(plans_list, "plan_id", "planId", "id")
    if state.plan_id:
        run("plans get", ["plans", "get", state.plan_id])
    else:
        _blocked(results, "plans get", ["plans", "get", "<plan_id>"], "no plan id available")

    relay_eval = run("relay evaluate", ["relay", "evaluate", "--question", "What evidence supports AAPL margin expansion?"])
    relay_runs = run("relay runs", ["relay", "runs", "--limit", "5", "--offset", "0"])
    state.relay_run_id = _first_id(relay_runs, "runId", "run_id", "id") or _first_id(relay_eval, "runId", "run_id", "id")
    run("relay scorecard", ["relay", "scorecard"])
    if state.relay_run_id:
        run("relay get", ["relay", "get", state.relay_run_id])
    else:
        _blocked(results, "relay get", ["relay", "get", "<run_id>"], "no relay run id available")

    signals_list = run("signals list", ["signals", "list"])
    state.signal_id = _first_id(signals_list, "signalId", "signal_id", "id")
    signal_create = run(
        "signals create",
        [
            "signals",
            "create",
            "--name",
            f"CLI Demo Signal {suffix}",
            "--formula",
            "close/close_20d-1",
            "--universe",
            "AAPL,MSFT",
            "--horizon",
            "20d",
        ],
    )
    state.signal_id = _first_id(signal_create, "signalId", "signal_id", "id") or state.signal_id
    if state.signal_id:
        run("signals get", ["signals", "get", state.signal_id])
        if state.review_id:
            run("signals link-review", ["signals", "link-review", "--signal-id", state.signal_id, "--review-id", state.review_id])
            run(
                "signals writeback-decision",
                [
                    "signals",
                    "writeback-decision",
                    "--signal-id",
                    state.signal_id,
                    "--review-id",
                    state.review_id,
                    "--decision-state",
                    "pursue",
                    "--decision-quality",
                    "D3",
                    "--evidence-links",
                    "artifacts/cli-demo",
                    "--verifier-status",
                    "passed",
                    "--review-date",
                    "2026-07-06",
                ],
            )
            run(
                "signals writeback-outcome",
                [
                    "signals",
                    "writeback-outcome",
                    "--signal-id",
                    state.signal_id,
                    "--review-id",
                    state.review_id,
                    "--outcome-quality",
                    "validated",
                ],
            )
        else:
            _blocked(results, "signals link-review", ["signals", "link-review"], "no review id available")
            _blocked(results, "signals writeback-decision", ["signals", "writeback-decision"], "no review id available")
            _blocked(results, "signals writeback-outcome", ["signals", "writeback-outcome"], "no review id available")
    else:
        _blocked(results, "signals get", ["signals", "get", "<signal_id>"], "no signal id available")
        _blocked(results, "signals link-review", ["signals", "link-review"], "no signal id available")
        _blocked(results, "signals writeback-decision", ["signals", "writeback-decision"], "no signal id available")
        _blocked(results, "signals writeback-outcome", ["signals", "writeback-outcome"], "no signal id available")
    run("signals quality-scorecard", ["signals", "quality-scorecard"])

    run("alpha list", ["alpha", "list"])
    run(
        "alpha create",
        [
            "alpha",
            "create",
            "--title",
            f"CLI demo alpha {suffix}",
            "--signal-family",
            "momentum",
            "--thesis",
            "CLI demo alpha smoke test",
            "--universe",
            "AAPL,MSFT",
            "--horizon",
            "20d",
        ],
    )
    if state.signal_id:
        run("alpha decay", ["alpha", "decay", "--signal-id", state.signal_id])
        run("backtests run", ["backtests", "run", "--signal-id", state.signal_id])
    else:
        _blocked(results, "alpha decay", ["alpha", "decay", "--signal-id", "<signal_id>"], "no signal id available")
        _blocked(results, "backtests run", ["backtests", "run", "--signal-id", "<signal_id>"], "no signal id available")

    run(
        "paper-trades create",
        [
            "paper-trades",
            "create",
            "--decision-id",
            f"cli-demo-{suffix}",
            "--ticker",
            "AAPL",
            "--quantity",
            "1",
            "--side",
            "buy",
            "--intended-price",
            "100",
        ],
    )
    run("paper-trades list", ["paper-trades", "list", "--limit", "5", "--offset", "0"])

    run(
        "warm-path ingest",
        [
            "warm-path",
            "ingest",
            "--event-type",
            "cli_demo",
            "--ticker",
            "AAPL",
            "--latency-ms",
            "12",
            "--notional-usd",
            "1000",
        ],
    )
    run("warm-path list", ["warm-path", "list", "--limit", "5", "--offset", "0"])

    service_create = run(
        "enterprise service-account",
        ["enterprise", "service-account", "--name", f"cli-demo-{suffix}", "--scopes", "public:read"],
    )
    state.service_account_id = _first_id(service_create, "serviceAccountId", "service_account_id", "id")
    run("enterprise service-accounts", ["enterprise", "service-accounts"])
    if state.service_account_id:
        run("enterprise service-account-rotate", ["enterprise", "service-account-rotate", state.service_account_id, "--rotated-by", "cli-demo"])
        run("enterprise service-account-revoke", ["enterprise", "service-account-revoke", state.service_account_id])
    else:
        _blocked(results, "enterprise service-account-rotate", ["enterprise", "service-account-rotate", "<service_account_id>"], "no service account id available")
        _blocked(results, "enterprise service-account-revoke", ["enterprise", "service-account-revoke", "<service_account_id>"], "no service account id available")

    run("enterprise audit-export", ["enterprise", "audit-export", "--requested-by", "cli-demo", "--scope", "all"])
    run(
        "enterprise sso-config",
        [
            "enterprise",
            "sso-config",
            "--provider",
            "oidc",
            "--issuer-url",
            "https://idp.example.test",
            "--audience",
            "ambrosia-cli-demo",
            "--default-role",
            "viewer",
            "--role-mappings",
            "{}",
        ],
    )
    run("enterprise sso-get", ["enterprise", "sso-get"])
    run("enterprise offline-bundle", ["enterprise", "offline-bundle"])
    run("enterprise security-packet", ["enterprise", "security-packet"])
    run("enterprise readiness", ["enterprise", "readiness"])

    report = build_report(api_url, output_dir, state, results)
    report_json = output_dir / "CLI-demo-report.json"
    report_md = output_dir / "CLI-demo-report.md"
    report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    print("\nDemo summary")
    print(f"Total: {summary['total']}  Passed: {summary['passed']}  Failed: {summary['failed']}  Blocked: {summary['blocked']}  Pass rate: {summary['passRate']}%")
    print(f"Report JSON: {report_json}")
    print(f"Report MD:   {report_md}")
    return 0 if summary["failed"] == 0 and summary["blocked"] == 0 else 1


class CliRunner:
    def __init__(self, *, api_url: str, timeout: float, output_dir: Path) -> None:
        self.api_url = api_url
        self.timeout = timeout
        self.output_dir = output_dir
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = os.pathsep.join(
            [str(CLI_DIR), str(SDK_DIR), self.env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

    def run(self, name: str, command: list[str], *, api: bool = True) -> DemoResult:
        display = "ambrosia " + " ".join(command)
        print(f"[RUN] {name}: {display}")
        global_flags = ["--timeout", str(self.timeout)]
        if api:
            global_flags.extend(["--api-url", self.api_url])
        full_command = [sys.executable, "-c", CLI_MAIN, *global_flags, "--json", *command]
        started = time.perf_counter()
        completed = subprocess.run(
            full_command,
            cwd=ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=self.timeout + 10,
            check=False,
        )
        duration = time.perf_counter() - started
        safe_name = _safe_name(name)
        stdout_path = self.output_dir / f"{safe_name}.stdout.json"
        stderr_path = self.output_dir / f"{safe_name}.stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        payload = _try_json(completed.stdout)
        status = "passed" if completed.returncode == 0 else "failed"
        reason = None if status == "passed" else _failure_reason(payload, completed.stderr)
        print(f"[{status.upper()}] {name} ({duration:.2f}s)")
        if reason:
            print(f"       {reason}")
        return DemoResult(
            name=name,
            command=command,
            status=status,
            returncode=completed.returncode,
            duration_seconds=duration,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            reason=reason,
            payload=payload,
        )


def demo_command_names() -> list[str]:
    return [
        "commands list/show",
        "examples",
        "status",
        "quickstart",
        "auth login/token/whoami/logout",
        "config show/profiles/get/set/set-api-url",
        "health and health --detailed",
        "reviews list/create/get",
        "packets list/create/get/audit",
        "market snapshot",
        "scanner run",
        "jobs list/get/wait",
        "plans list/get",
        "relay evaluate/runs/scorecard/get",
        "signals list/create/get/link-review/writeback-decision/writeback-outcome/quality-scorecard",
        "alpha list/create/decay",
        "backtests run",
        "paper-trades create/list",
        "warm-path ingest/list",
        "enterprise service-account/service-accounts/rotate/revoke/audit-export/sso-config/sso-get/offline-bundle/security-packet/readiness",
    ]


def _packet_payload(suffix: str) -> dict[str, Any]:
    return {
        "id": f"pkt-cli-demo-{suffix}",
        "schemaVersion": "packet.v1",
        "workflowVersion": "quant-agent.v1",
        "ticker": "AAPL",
        "title": f"CLI demo packet {suffix}",
        "thesis": "CLI demo packet smoke test",
        "assetClass": "Equity",
        "timeHorizon": "2-6 weeks",
        "intendedExpression": "AAPL long equity expression",
        "status": "intake",
        "decisionState": "watch",
        "confidence": 62,
        "trialCountImpact": 1,
        "followUpDate": "2026-07-13",
        "createdAt": "20:00:00",
        "claims": [
            {"id": "claim-1", "kind": "assumption", "text": "CLI demo packet payload is accepted", "confidence": 62}
        ],
        "strongestCritique": "Synthetic payload for CLI demo validation only.",
        "disconfirmingTest": "Reject if packet create schema validation fails.",
        "historicalAnalogue": {
            "title": "CLI schema smoke test",
            "similarity": "Representative packet shape",
            "differences": "No live investment thesis intended",
            "resolution": "Used only for endpoint coverage",
        },
        "validation": {
            "status": "specified",
            "hypothesis": "A valid CLI packet can be created",
            "nullHypothesis": "The CLI packet schema is rejected",
            "dataRequirements": ["packet schema"],
            "protocol": "submit packet payload through CLI",
        },
        "tradeability": [
            {"topic": "schema", "question": "Does the packet satisfy required fields?", "severity": "low"}
        ],
        "sources": [
            {
                "id": "source-1",
                "title": "CLI demo script",
                "sourceType": "test",
                "timestamp": "2026-07-06T20:00:00Z",
                "permission": "public",
                "relevance": 1.0,
            }
        ],
        "audit": [
            {"id": "audit-1", "timestamp": "20:00:00", "eventType": "cli.demo", "detail": "Created by CLI demo script"}
        ],
    }


def api_post(api_url: str, path: str, payload: dict[str, Any], timeout: float) -> Any:
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "ambrosia-cli-demo-script/1.0"}
    token = os.getenv("AMBROSIA_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{api_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator controls target URL.
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def _record(results: list[DemoResult], result: DemoResult) -> Any:
    results.append(result)
    return result.payload


def _blocked(results: list[DemoResult], name: str, command: list[str], reason: str) -> None:
    print(f"[BLOCKED] {name}: {reason}")
    results.append(DemoResult(name=name, command=command, status="blocked", reason=reason))


def _first_id(payload: Any, *keys: str) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value is not None:
                return str(value)
        for collection_key in ("items", "results", "runs", "data", "candidates"):
            found = _first_id(payload.get(collection_key), *keys)
            if found:
                return found
        for value in payload.values():
            found = _first_id(value, *keys)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _first_id(item, *keys)
            if found:
                return found
    return None


def _try_json(output: str) -> Any:
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _failure_reason(payload: Any, stderr: str) -> str:
    if isinstance(payload, dict):
        for key in ("message", "detail", "reason"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    return stderr.strip() or "command exited non-zero"


def build_report(api_url: str, output_dir: Path, state: DemoState, results: list[DemoResult]) -> dict[str, Any]:
    counts = {"passed": 0, "failed": 0, "blocked": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    total = len(results)
    return {
        "schemaVersion": "ambrosia-cli-demo.v1",
        "apiUrl": api_url,
        "outputDir": str(output_dir),
        "generatedAtEpoch": int(time.time()),
        "summary": {"total": total, **counts, "passRate": round((counts["passed"] / total) * 100, 1) if total else 0},
        "state": state.as_dict(),
        "results": [result.as_dict() for result in results],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Ambrosia CLI Demo Report",
        "",
        f"- API URL: {report['apiUrl']}",
        f"- Total commands: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Blocked: {summary['blocked']}",
        f"- Pass rate: {summary['passRate']}%",
        "",
        "| Status | Command | Reason |",
        "| --- | --- | --- |",
    ]
    for result in report["results"]:
        command = " ".join(result["command"])
        reason = (result.get("reason") or "").replace("|", "\\|")
        lines.append(f"| {result['status']} | `{command}` | {reason} |")
    lines.append("")
    return "\n".join(lines)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(secret in key.lower() for secret in ("token", "secret", "password", "credential")):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value[:5]]
    return value


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in name.lower()).strip("-")


def _looks_like_production(api_url: str) -> bool:
    lowered = api_url.lower()
    if DEFAULT_API_URL in api_url:
        return False
    return any(hint in lowered for hint in PRODUCTION_HINTS)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(f"[FAIL] CLI demo timed out: {exc}")
        raise SystemExit(1)
    except urllib.error.URLError as exc:
        print(f"[FAIL] API setup request failed: {exc}")
        raise SystemExit(1)
