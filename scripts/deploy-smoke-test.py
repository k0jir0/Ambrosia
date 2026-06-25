#!/usr/bin/env python3
"""
Deploy smoke test — validates health and contract gates after release.

Runs immediately after deployment to catch issues before rollback is needed.
Exits with code 0 on pass, 1 on fail. Suitable for deploy hook integration.

Usage:
    python scripts/deploy-smoke-test.py https://api.onrender.com
    python scripts/deploy-smoke-test.py http://localhost:8000
"""
from __future__ import annotations

import sys
import time
import json
import argparse
import requests
from typing import Optional


class SmokeTestResult:
    def __init__(self, name: str, passed: bool, duration_ms: float, detail: str = ""):
        self.name = name
        self.passed = passed
        self.duration_ms = duration_ms
        self.detail = detail

    def __str__(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status:8} {self.name:40} {self.duration_ms:6.1f}ms  {self.detail}"


def run_smoke_tests(base_url: str, timeout_secs: float = 10.0) -> list[SmokeTestResult]:
    """
    Run critical health and contract gates against deployed API.
    
    Args:
        base_url: Base URL of the deployed API (e.g., https://api.onrender.com)
        timeout_secs: Request timeout for each test
    
    Returns:
        List of test results
    """
    base_url = base_url.rstrip("/")
    results: list[SmokeTestResult] = []

    # -----------------------------------------------------------------------
    # Health Check — basic liveness
    # -----------------------------------------------------------------------
    start = time.time()
    try:
        resp = requests.get(f"{base_url}/health", timeout=timeout_secs)
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            data = resp.json()
            passed = data.get("status") == "ok"
            detail = f"status={data.get('status')}, service={data.get('service')}"
            results.append(SmokeTestResult("GET /health", passed, elapsed, detail))
        else:
            results.append(SmokeTestResult("GET /health", False, elapsed, f"HTTP {resp.status_code}"))
    except requests.RequestException as e:
        elapsed = (time.time() - start) * 1000
        results.append(SmokeTestResult("GET /health", False, elapsed, str(e)))

    # -----------------------------------------------------------------------
    # Detailed Health — SLO and alert checks
    # -----------------------------------------------------------------------
    start = time.time()
    try:
        resp = requests.get(f"{base_url}/health/detailed", timeout=timeout_secs)
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            data = resp.json()
            # Check for critical alerts (not just degraded state)
            alerts = data.get("alerts", [])
            has_critical = any("failed" in str(a).lower() for a in alerts)
            passed = data.get("status") in {"ok", "degraded"} and not has_critical
            
            alert_summary = f"alerts={len(alerts)}"
            if alerts:
                alert_summary += f" ({alerts[0][:50]}...)" if len(str(alerts[0])) > 50 else f" ({alerts[0]})"
            
            results.append(SmokeTestResult("GET /health/detailed", passed, elapsed, alert_summary))
        else:
            results.append(SmokeTestResult("GET /health/detailed", False, elapsed, f"HTTP {resp.status_code}"))
    except requests.RequestException as e:
        elapsed = (time.time() - start) * 1000
        results.append(SmokeTestResult("GET /health/detailed", False, elapsed, str(e)))

    # -----------------------------------------------------------------------
    # Contract Gate 1: Review Creation
    # -----------------------------------------------------------------------
    start = time.time()
    try:
        resp = requests.post(
            f"{base_url}/reviews",
            json={"thesis": "SPY breadth improving versus broad market", "ticker": "SPY"},
            timeout=timeout_secs
        )
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            review = resp.json()
            required_fields = {
                "id", "schemaVersion", "title", "thesis", "ticker",
                "validation", "claims", "tradeability", "sources", "audit"
            }
            passed = required_fields <= set(review.keys())
            detail = f"fields={len(required_fields & set(review.keys()))}/{len(required_fields)}"
            results.append(SmokeTestResult("POST /reviews (Contract 1)", passed, elapsed, detail))
        else:
            results.append(SmokeTestResult("POST /reviews (Contract 1)", False, elapsed, f"HTTP {resp.status_code}"))
    except requests.RequestException as e:
        elapsed = (time.time() - start) * 1000
        results.append(SmokeTestResult("POST /reviews (Contract 1)", False, elapsed, str(e)))

    # -----------------------------------------------------------------------
    # Contract Gate 3: Packet Lifecycle
    # -----------------------------------------------------------------------
    pkt_id = f"smoke-test-{int(time.time())}"
    packet_payload = {
        "id": pkt_id,
        "title": "Smoke test packet",
        "thesis": "SPY relative strength improving",
        "ticker": "SPY",
        "assetClass": "ETF",
        "timeHorizon": "2-6 weeks",
        "intendedExpression": "Long",
        "status": "synthesis",
        "decisionState": "watch",
        "confidence": 65,
        "trialCountImpact": 1,
        "followUpDate": "2026-07-15",
        "createdAt": "2026-06-25T10:00:00Z",
        "claims": [{"id": "c1", "kind": "sourced", "text": "Test", "evidence": "test", "confidence": 70}],
        "strongestCritique": "Test",
        "disconfirmingTest": "Test",
        "historicalAnalogue": {"title": "Test", "similarity": "Test", "differences": "Test", "resolution": "Test"},
        "validation": {"status": "specified", "hypothesis": "Test", "nullHypothesis": "Test", "dataRequirements": [], "protocol": "Test", "refusalReason": None},
        "tradeability": [],
        "sources": [{"id": "s1", "title": "Test", "sourceType": "internal", "timestamp": "2026-06-25T09:00:00Z", "permission": "user_owned", "relevance": 0.8}],
        "audit": [{"id": "a1", "timestamp": "10:00:00", "eventType": "packet.created", "detail": "Smoke test"}],
    }
    
    start = time.time()
    try:
        resp = requests.post(f"{base_url}/packets", json=packet_payload, timeout=timeout_secs)
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code in {200, 201}:
            created = resp.json()
            passed = created.get("id") == pkt_id
            results.append(SmokeTestResult("POST /packets (Contract 3a)", passed, elapsed, f"id={created.get('id')}"))
        else:
            results.append(SmokeTestResult("POST /packets (Contract 3a)", False, elapsed, f"HTTP {resp.status_code}"))
    except requests.RequestException as e:
        elapsed = (time.time() - start) * 1000
        results.append(SmokeTestResult("POST /packets (Contract 3a)", False, elapsed, str(e)))

    # Verify we can retrieve the packet
    start = time.time()
    try:
        resp = requests.get(f"{base_url}/packets/{pkt_id}", timeout=timeout_secs)
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            retrieved = resp.json()
            passed = retrieved.get("ticker") == "SPY"
            results.append(SmokeTestResult("GET /packets/{id} (Contract 3b)", passed, elapsed, f"ticker={retrieved.get('ticker')}"))
        else:
            results.append(SmokeTestResult("GET /packets/{id} (Contract 3b)", False, elapsed, f"HTTP {resp.status_code}"))
    except requests.RequestException as e:
        elapsed = (time.time() - start) * 1000
        results.append(SmokeTestResult("GET /packets/{id} (Contract 3b)", False, elapsed, str(e)))

    # -----------------------------------------------------------------------
    # Contract Gate 4: Market Data Refresh
    # -----------------------------------------------------------------------
    start = time.time()
    try:
        resp = requests.get(f"{base_url}/market/SPY/snapshot", timeout=timeout_secs)
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            snapshot = resp.json()
            has_provenance = "dataSource" in snapshot and "dataSourceConfidence" in snapshot
            passed = has_provenance and snapshot.get("dataSourceConfidence") in {"live", "fallback", "demo"}
            detail = f"mode={snapshot.get('dataSourceConfidence')}"
            results.append(SmokeTestResult("GET /market/SPY/snapshot (Contract 4)", passed, elapsed, detail))
        else:
            results.append(SmokeTestResult("GET /market/SPY/snapshot (Contract 4)", False, elapsed, f"HTTP {resp.status_code}"))
    except requests.RequestException as e:
        elapsed = (time.time() - start) * 1000
        results.append(SmokeTestResult("GET /market/SPY/snapshot (Contract 4)", False, elapsed, str(e)))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy smoke test — validates health and contract gates after release."
    )
    parser.add_argument("base_url", help="Base URL of the deployed API")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds")
    parser.add_argument("--fail-fast", action="store_true", help="Exit on first failure")
    args = parser.parse_args()

    print(f"\n{'='*90}")
    print(f"Deploy Smoke Test")
    print(f"Target: {args.base_url}")
    print(f"{'='*90}\n")

    try:
        results = run_smoke_tests(args.base_url, args.timeout)
    except Exception as e:
        print(f"✗ FATAL: {e}")
        return 1

    # Print results
    for result in results:
        print(result)
        if args.fail_fast and not result.passed:
            break

    # Summary
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    print(f"\n{'='*90}")
    print(f"Result: {passed_count}/{total_count} checks passed")
    print(f"{'='*90}\n")

    # Exit code
    if passed_count == total_count:
        print("✓ Deploy smoke test PASSED — service is healthy")
        return 0
    else:
        print("✗ Deploy smoke test FAILED — issues detected")
        return 1


if __name__ == "__main__":
    sys.exit(main())
