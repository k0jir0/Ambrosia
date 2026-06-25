#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ProbeResult:
    name: str
    endpoint: str
    ok: bool
    latencyMs: float
    statusCode: int
    message: str


def fetch_json(base_url: str, endpoint: str) -> tuple[int, float, object]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    start = perf_counter()
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
        latency_ms = (perf_counter() - start) * 1000.0
        return int(response.status), latency_ms, json.loads(payload)


def run_probes(base_url: str) -> list[ProbeResult]:
    probes: list[ProbeResult] = []

    def append_result(name: str, endpoint: str, check) -> None:
        try:
            status_code, latency_ms, body = fetch_json(base_url, endpoint)
            ok, message = check(body, latency_ms)
            probes.append(
                ProbeResult(
                    name=name,
                    endpoint=endpoint,
                    ok=ok,
                    latencyMs=round(latency_ms, 2),
                    statusCode=status_code,
                    message=message,
                )
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            probes.append(
                ProbeResult(
                    name=name,
                    endpoint=endpoint,
                    ok=False,
                    latencyMs=0.0,
                    statusCode=getattr(exc, "code", 0) or 0,
                    message=f"request failed: {exc}",
                )
            )

    append_result(
        "health",
        "/health",
        lambda body, latency: (
            body.get("status") == "ok" and latency <= 5000,
            f"status={body.get('status')} latency={round(latency, 2)}ms",
        ),
    )

    append_result(
        "scorecard",
        "/scorecard",
        lambda body, latency: (
            bool(body.get("certification_status"))
            and bool(body.get("overall_status"))
            and latency <= 7000,
            "certification_status="
            f"{body.get('certification_status')} overall_status={body.get('overall_status')} "
            f"latency={round(latency, 2)}ms",
        ),
    )

    append_result(
        "providers",
        "/providers/status",
        lambda body, latency: (
            "hostedConfigured" in body and "ollamaConfigured" in body and latency <= 5000,
            f"hostedConfigured={body.get('hostedConfigured')} ollamaConfigured={body.get('ollamaConfigured')} latency={round(latency, 2)}ms",
        ),
    )

    append_result(
        "visibility_registry",
        "/visibility/function-registry",
        lambda body, latency: (
            isinstance(body, list) and len(body) > 0 and latency <= 7000,
            f"registry_count={len(body) if isinstance(body, list) else 'invalid'} latency={round(latency, 2)}ms",
        ),
    )

    return probes


def build_markdown(base_url: str, probes: list[ProbeResult]) -> str:
    lines: list[str] = []
    passed = sum(1 for probe in probes if probe.ok)
    lines.append("# Synthetic Monitoring Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append(f"Base URL: {base_url}")
    lines.append(f"Passed probes: {passed}/{len(probes)}")
    lines.append("")
    lines.append("| Probe | Endpoint | Status | HTTP | Latency (ms) | Details |")
    lines.append("| --- | --- | --- | ---: | ---: | --- |")
    for probe in probes:
        status = "PASS" if probe.ok else "FAIL"
        lines.append(
            f"| {probe.name} | {probe.endpoint} | {status} | {probe.statusCode} | {probe.latencyMs} | {probe.message} |"
        )
    lines.append("")
    lines.append("## Thresholds")
    lines.append("")
    lines.append("- /health <= 5000ms and status=ok")
    lines.append("- /scorecard <= 7000ms and required fields present")
    lines.append("- /providers/status <= 5000ms and provider flags present")
    lines.append("- /visibility/function-registry <= 7000ms and non-empty registry")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Ambrosia synthetic monitoring probes.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("AMBROSIA_API_BASE_URL", ""),
        help="Base API URL to probe, e.g. https://ambrosia-api.onrender.com",
    )
    parser.add_argument(
        "--output-json",
        default="artifacts/synthetic-monitor.json",
        help="Path to JSON report artifact",
    )
    parser.add_argument(
        "--output-md",
        default="artifacts/synthetic-monitor.md",
        help="Path to markdown report artifact",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.strip()
    if not base_url:
        print("Missing --base-url or AMBROSIA_API_BASE_URL", file=sys.stderr)
        return 2

    probes = run_probes(base_url)
    passed = sum(1 for probe in probes if probe.ok)
    failed = len(probes) - passed

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(UTC).isoformat(),
                "baseUrl": base_url,
                "summary": {"passed": passed, "failed": failed, "total": len(probes)},
                "probes": [asdict(probe) for probe in probes],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_md.write_text(build_markdown(base_url, probes), encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    for probe in probes:
        state = "PASS" if probe.ok else "FAIL"
        print(f"- {state} {probe.name} {probe.endpoint} {probe.latencyMs}ms {probe.message}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
