from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
CLI_DIR = ROOT / "packages" / "cli"
SDK_DIR = ROOT / "packages" / "sdk-python"
ARTIFACT_JSON = ROOT / "artifacts" / "cli-live-function-matrix.json"
ARTIFACT_MD = ROOT / "artifacts" / "cli-live-function-matrix.md"
CLI_MAIN = "from ambrosia_cli.main import main; raise SystemExit(main())"


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


RUN_CLI_LIVE_E2E = _env_flag("RUN_CLI_LIVE_E2E")
STRICT_CLI_LIVE_E2E = _env_flag("STRICT_CLI_LIVE_E2E")
API_URL = os.getenv("CLI_LIVE_API_URL", "").rstrip("/")
COMMAND_TIMEOUT = float(os.getenv("CLI_LIVE_COMMAND_TIMEOUT_SECONDS", "30"))


pytestmark = [
    pytest.mark.integration,
    pytest.mark.smoke,
    pytest.mark.timeout(420),
]


@dataclass
class CommandResult:
    name: str
    command: list[str]
    status: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    reason: str | None = None
    durationSeconds: float = 0.0
    payload: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": ["ambrosia", *self.command],
            "status": self.status,
            "returncode": self.returncode,
            "durationSeconds": round(self.durationSeconds, 3),
            "reason": self.reason,
            "stdoutPreview": self.stdout[:2000],
            "stderrPreview": self.stderr[:2000],
            "payload": self.payload,
        }


@dataclass
class MatrixState:
    suffix: str = field(default_factory=lambda: str(int(time.time())))
    review_id: str | None = None
    packet_id: str | None = None
    job_id: str | None = None
    plan_id: str | None = None
    relay_run_id: str | None = None
    signal_id: str | None = None
    service_account_id: str | None = None


def _pythonpath() -> str:
    existing = os.environ.get("PYTHONPATH", "")
    paths = [str(CLI_DIR), str(SDK_DIR)]
    if existing:
        paths.append(existing)
    return os.pathsep.join(paths)


def _run_cli(name: str, args: list[str], *, api: bool = True) -> CommandResult:
    env = {**os.environ, "PYTHONPATH": _pythonpath()}
    command = [sys.executable, "-c", CLI_MAIN]
    if api:
        command.extend(["--api-url", API_URL])
    command.extend(["--json", *args])

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=name,
            command=args,
            status="failed",
            reason=f"timed out after {COMMAND_TIMEOUT:.1f}s",
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            durationSeconds=time.perf_counter() - started,
        )

    payload = _try_json(completed.stdout)
    status = "passed" if completed.returncode == 0 else "failed"
    reason = None if status == "passed" else _failure_reason(payload, completed.stderr)
    return CommandResult(
        name=name,
        command=args,
        status=status,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        reason=reason,
        durationSeconds=time.perf_counter() - started,
        payload=payload,
    )


def _api_post(path: str, payload: dict[str, Any] | None = None) -> Any:
    response = requests.post(
        f"{API_URL}{path}",
        json=payload or {},
        headers={"User-Agent": "ambrosia-cli-live-function-matrix/1.0"},
        timeout=COMMAND_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _blocked(name: str, args: list[str], reason: str) -> CommandResult:
    return CommandResult(name=name, command=args, status="blocked", reason=reason)


def _try_json(output: str) -> Any:
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _failure_reason(payload: Any, stderr: str) -> str:
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("detail")
        if isinstance(message, str):
            return message
    return stderr.strip() or "command exited non-zero"


def _first_id(payload: Any, *keys: str) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value is not None:
                return str(value)
        for collection_key in ("items", "results", "runs", "data", "candidates"):
            nested = payload.get(collection_key)
            found = _first_id(nested, *keys)
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


def _record(results: list[CommandResult], result: CommandResult) -> Any:
    results.append(result)
    return result.payload


def test_ambrosia_cli_live_function_matrix() -> None:
    if not RUN_CLI_LIVE_E2E:
        pytest.skip("Set RUN_CLI_LIVE_E2E=true to run live Ambrosia CLI function matrix.")
    if not API_URL:
        pytest.fail("CLI_LIVE_API_URL is required when RUN_CLI_LIVE_E2E=true")

    state = MatrixState()
    results: list[CommandResult] = []

    _record(results, _run_cli("commands list", ["commands", "list"], api=False))
    _record(results, _run_cli("commands show", ["commands", "show", "1"], api=False))
    _record(results, _run_cli("examples", ["examples"], api=False))
    _record(results, _run_cli("auth login", ["auth", "login"], api=False))
    _record(results, _run_cli("auth token", ["auth", "token"], api=False))
    _record(results, _run_cli("auth whoami", ["auth", "whoami"], api=False))
    _record(results, _run_cli("auth logout", ["auth", "logout"], api=False))
    _record(results, _run_cli("config get", ["config", "get", "api_url"], api=False))
    _record(results, _run_cli("config set", ["config", "set", "api_url", API_URL], api=False))

    _record(results, _run_cli("health", ["health"]))

    review_list = _record(results, _run_cli("reviews list", ["reviews", "list"]))
    state.review_id = _first_id(review_list, "id", "reviewId")
    review_create = _record(
        results,
        _run_cli(
            "reviews create",
            [
                "reviews",
                "create",
                "--thesis",
                f"CLI live matrix review {state.suffix}",
                "--ticker",
                "AAPL",
                "--asset-class",
                "Equity",
                "--time-horizon",
                "2-6 weeks",
            ],
        ),
    )
    state.review_id = _first_id(review_create, "id", "reviewId") or state.review_id
    if state.review_id:
        _record(results, _run_cli("reviews get", ["reviews", "get", state.review_id]))
    else:
        results.append(_blocked("reviews get", ["reviews", "get", "<review_id>"], "no review id from list/create"))

    packet_list = _record(results, _run_cli("packets list", ["packets", "list"]))
    state.packet_id = _first_id(packet_list, "id", "packetId")
    packet_payload = json.dumps(
        {
            "id": f"pkt-cli-live-{state.suffix}",
            "schemaVersion": "packet.v1",
            "workflowVersion": "quant-agent.v1",
            "ticker": "AAPL",
            "title": f"CLI live packet {state.suffix}",
            "thesis": "CLI matrix packet smoke test",
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
                {"id": "claim-1", "kind": "assumption", "text": "CLI matrix packet payload is accepted", "confidence": 62}
            ],
            "strongestCritique": "Synthetic payload for CLI matrix validation only.",
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
                    "title": "CLI live function matrix",
                    "sourceType": "test",
                    "timestamp": "2026-07-06T20:00:00Z",
                    "permission": "public",
                    "relevance": 1.0,
                }
            ],
            "audit": [
                {"id": "audit-1", "timestamp": "20:00:00", "eventType": "cli.matrix", "detail": "Created by CLI live matrix"}
            ],
        }
    )
    packet_create = _record(results, _run_cli("packets create", ["packets", "create", "--payload", packet_payload]))
    state.packet_id = _first_id(packet_create, "id", "packetId") or state.packet_id
    if state.packet_id:
        _record(results, _run_cli("packets get", ["packets", "get", state.packet_id]))
        _record(results, _run_cli("packets audit", ["packets", "audit", state.packet_id]))
        job_seed = _api_post(f"/packets/{state.packet_id}/backtest/run/async", {"forceRun": True})
        state.job_id = _first_id(job_seed, "id", "jobId")
    else:
        results.append(_blocked("packets get", ["packets", "get", "<packet_id>"], "no packet id from list/create"))
        results.append(_blocked("packets audit", ["packets", "audit", "<packet_id>"], "no packet id from list/create"))

    _record(results, _run_cli("market snapshot", ["market", "snapshot", "SPY"]))
    _record(results, _run_cli("scanner run", ["scanner", "run", "--universe", "AAPL,MSFT,SPY", "--max-candidates", "3"]))

    jobs_list = _record(results, _run_cli("jobs list", ["jobs", "list"]))
    state.job_id = state.job_id or _first_id(jobs_list, "id", "jobId")
    if state.job_id:
        _record(results, _run_cli("jobs get", ["jobs", "get", state.job_id]))
        _record(results, _run_cli("jobs wait", ["jobs", "wait", state.job_id]))
    else:
        results.append(_blocked("jobs get", ["jobs", "get", "<job_id>"], "no jobs available"))
        results.append(_blocked("jobs wait", ["jobs", "wait", "<job_id>"], "no jobs available"))

    _api_post("/roadmap/sync-plans")
    plans_list = _record(results, _run_cli("plans list", ["plans", "list"]))
    state.plan_id = _first_id(plans_list, "plan_id", "planId", "id")
    if state.plan_id:
        _record(results, _run_cli("plans get", ["plans", "get", state.plan_id]))
    else:
        results.append(_blocked("plans get", ["plans", "get", "<plan_id>"], "no plan id from list"))

    relay_eval = _record(results, _run_cli("relay evaluate", ["relay", "evaluate", "--question", "What supports AAPL margin expansion?"]))
    relay_runs = _record(results, _run_cli("relay runs", ["relay", "runs", "--limit", "5", "--offset", "0"]))
    state.relay_run_id = _first_id(relay_runs, "runId", "run_id", "id") or _first_id(relay_eval, "runId", "run_id", "id")
    _record(results, _run_cli("relay scorecard", ["relay", "scorecard"]))
    if state.relay_run_id:
        _record(results, _run_cli("relay get", ["relay", "get", state.relay_run_id]))
    else:
        results.append(_blocked("relay get", ["relay", "get", "<run_id>"], "no relay run id from evaluate/runs"))

    signals_list = _record(results, _run_cli("signals list", ["signals", "list"]))
    state.signal_id = _first_id(signals_list, "signalId", "signal_id", "id")
    signal_create = _record(
        results,
        _run_cli(
            "signals create",
            [
                "signals",
                "create",
                "--name",
                f"CLI Live Signal {state.suffix}",
                "--formula",
                "close/close_20d-1",
                "--universe",
                "AAPL,MSFT",
                "--horizon",
                "20d",
            ],
        ),
    )
    state.signal_id = _first_id(signal_create, "signalId", "signal_id", "id") or state.signal_id
    if state.signal_id:
        _record(results, _run_cli("signals get", ["signals", "get", state.signal_id]))
        if state.review_id:
            _record(results, _run_cli("signals link-review", ["signals", "link-review", "--signal-id", state.signal_id, "--review-id", state.review_id]))
            _record(
                results,
                _run_cli(
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
                        "artifacts/cli-live-matrix",
                        "--verifier-status",
                        "passed",
                        "--review-date",
                        "2026-07-06",
                    ],
                ),
            )
            _record(
                results,
                _run_cli(
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
                ),
            )
        else:
            results.append(_blocked("signals writeback-decision", ["signals", "writeback-decision"], "no review id available"))
            results.append(_blocked("signals writeback-outcome", ["signals", "writeback-outcome"], "no review id available"))
    else:
        results.append(_blocked("signals get", ["signals", "get", "<signal_id>"], "no signal id from list/create"))
        results.append(_blocked("signals writeback-decision", ["signals", "writeback-decision"], "no signal id available"))
        results.append(_blocked("signals writeback-outcome", ["signals", "writeback-outcome"], "no signal id available"))
    _record(results, _run_cli("signals quality-scorecard", ["signals", "quality-scorecard"]))

    _record(results, _run_cli("alpha list", ["alpha", "list"]))
    _record(
        results,
        _run_cli(
            "alpha create",
            [
                "alpha",
                "create",
                "--title",
                f"CLI live alpha {state.suffix}",
                "--signal-family",
                "momentum",
                "--thesis",
                "CLI live matrix alpha smoke test",
                "--universe",
                "AAPL,MSFT",
                "--horizon",
                "20d",
            ],
        ),
    )
    if state.signal_id:
        _record(results, _run_cli("alpha decay", ["alpha", "decay", "--signal-id", state.signal_id]))
        _record(results, _run_cli("backtests run", ["backtests", "run", "--signal-id", state.signal_id]))
    else:
        results.append(_blocked("alpha decay", ["alpha", "decay", "--signal-id", "<signal_id>"], "no signal id available"))
        results.append(_blocked("backtests run", ["backtests", "run", "--signal-id", "<signal_id>"], "no signal id available"))

    _record(
        results,
        _run_cli(
            "paper-trades create",
            [
                "paper-trades",
                "create",
                "--decision-id",
                f"cli-live-{state.suffix}",
                "--ticker",
                "AAPL",
                "--quantity",
                "1",
                "--side",
                "buy",
                "--intended-price",
                "100",
            ],
        ),
    )
    _record(results, _run_cli("paper-trades list", ["paper-trades", "list", "--limit", "5", "--offset", "0"]))

    _record(
        results,
        _run_cli(
            "warm-path ingest",
            [
                "warm-path",
                "ingest",
                "--event-type",
                "cli_live_matrix",
                "--ticker",
                "AAPL",
                "--latency-ms",
                "12",
                "--notional-usd",
                "1000",
            ],
        ),
    )
    _record(results, _run_cli("warm-path list", ["warm-path", "list", "--limit", "5", "--offset", "0"]))

    service_create = _record(
        results,
        _run_cli("enterprise service-account", ["enterprise", "service-account", "--name", f"cli-live-{state.suffix}", "--scopes", "public:read"]),
    )
    state.service_account_id = _first_id(service_create, "serviceAccountId", "service_account_id", "id")
    _record(results, _run_cli("enterprise service-accounts", ["enterprise", "service-accounts"]))
    if state.service_account_id:
        _record(results, _run_cli("enterprise service-account-rotate", ["enterprise", "service-account-rotate", state.service_account_id, "--rotated-by", "cli-live"]))
        _record(results, _run_cli("enterprise service-account-revoke", ["enterprise", "service-account-revoke", state.service_account_id]))
    else:
        results.append(_blocked("enterprise service-account-rotate", ["enterprise", "service-account-rotate", "<service_account_id>"], "no service account id from create"))
        results.append(_blocked("enterprise service-account-revoke", ["enterprise", "service-account-revoke", "<service_account_id>"], "no service account id from create"))

    _record(results, _run_cli("enterprise audit-export", ["enterprise", "audit-export", "--requested-by", "cli-live", "--scope", "all"]))
    _record(
        results,
        _run_cli(
            "enterprise sso-config",
            [
                "enterprise",
                "sso-config",
                "--provider",
                "oidc",
                "--issuer-url",
                "https://idp.example.test",
                "--audience",
                "ambrosia-cli-live",
                "--default-role",
                "viewer",
                "--role-mappings",
                "{}",
            ],
        ),
    )
    _record(results, _run_cli("enterprise sso-get", ["enterprise", "sso-get"]))
    _record(results, _run_cli("enterprise offline-bundle", ["enterprise", "offline-bundle"]))
    _record(results, _run_cli("enterprise security-packet", ["enterprise", "security-packet"]))
    _record(results, _run_cli("enterprise readiness", ["enterprise", "readiness"]))

    report = _build_report(results, state)
    ARTIFACT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    ARTIFACT_MD.write_text(_render_markdown(report), encoding="utf-8")

    if STRICT_CLI_LIVE_E2E and report["summary"]["failed"]:
        failed = ", ".join(item["name"] for item in report["results"] if item["status"] == "failed")
        pytest.fail(f"Ambrosia CLI live matrix failures: {failed}")


def _build_report(results: list[CommandResult], state: MatrixState) -> dict[str, Any]:
    counts = {"passed": 0, "failed": 0, "blocked": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "schemaVersion": "ambrosia-cli-live-function-matrix.v1",
        "apiUrl": API_URL,
        "generatedAtEpoch": int(time.time()),
        "summary": {
            "total": len(results),
            **counts,
            "passRate": round((counts["passed"] / len(results)) * 100, 1) if results else 0,
        },
        "state": state.__dict__,
        "results": [result.as_dict() for result in results],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Ambrosia CLI Live Function Matrix",
        "",
        f"- API URL: {report['apiUrl']}",
        f"- Total commands exercised: {summary['total']}",
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
