from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EXPECTED_STATUSES = {
    "hypothesis": 2,
    "validation_passed": 2,
    "active_candidate": 2,
    "constrained": 1,
    "retired": 1,
}


def request_json(base_url: str, path: str, method: str = "GET") -> object:
    url = f"{base_url.rstrip('/')}{path}"
    request = Request(url, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc


def status_distribution(signals: list[dict]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for signal in signals:
        status = str(signal.get("status") or "unknown")
        distribution[status] = distribution.get(status, 0) + 1
    return distribution


def verify(base_url: str) -> dict:
    signals = request_json(base_url, "/signals")
    if not isinstance(signals, list):
        raise RuntimeError("GET /signals did not return a list")

    seeded = [signal for signal in signals if isinstance(signal, dict) and str(signal.get("signalId", "")).startswith("sig-index97-")]
    distribution = status_distribution(seeded)
    missing_statuses = {status: expected for status, expected in EXPECTED_STATUSES.items() if distribution.get(status) != expected}
    if missing_statuses:
        raise RuntimeError(f"Index97 status distribution mismatch: {distribution}")

    linked = sum(1 for signal in seeded if int(signal.get("linkedReviewCount", 0)) > 0)
    outcomes = sum(1 for signal in seeded if int(signal.get("outcomeCount", 0)) > 0)
    if linked < 4 or outcomes < 4:
        raise RuntimeError(f"Index97 review/outcome coverage too low: linked={linked}, outcomes={outcomes}")

    metrics = request_json(base_url, "/signals/program-metrics")
    scorecard = request_json(base_url, "/signals/quality-scorecard/weekly")
    gates = scorecard.get("gates", {}) if isinstance(scorecard, dict) else {}
    failing_gates = [name for name, gate in gates.items() if isinstance(gate, dict) and gate.get("status") != "pass"]
    if failing_gates:
        raise RuntimeError(f"Index97 quality gates failed: {', '.join(failing_gates)}")

    return {
        "status": "ok",
        "seededSignals": len(seeded),
        "statusDistribution": distribution,
        "linkedReviewSignals": linked,
        "outcomeWritebackSignals": outcomes,
        "programMetrics": metrics,
        "qualityGates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed and verify the Index97 /signals lifecycle inventory.")
    parser.add_argument("--base-url", default=os.getenv("AMBROSIA_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    try:
        seed_result = None if args.check_only else request_json(args.base_url, "/signals/seed-index97", method="POST")
        verification = verify(args.base_url)
    except RuntimeError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps({"seed": seed_result, "verification": verification}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
