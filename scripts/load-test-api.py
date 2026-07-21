#!/usr/bin/env python3
"""Small dependency-free API capacity probe; never targets write routes."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request


def request_once(url: str, token: str | None, timeout: float) -> tuple[int, float]:
    headers = {"User-Agent": "AmbrosiaCapacityProbe/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1024)
            status = response.status
    except Exception:
        status = 0
    return status, (time.perf_counter() - started) * 1000


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--token")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.concurrency > 200:
        parser.error("requests must be positive and concurrency must be 1..200")

    url = args.base_url.rstrip("/") + "/" + args.path.lstrip("/")
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(
            lambda _: request_once(url, args.token, args.timeout), range(args.requests)
        ))
    elapsed = time.perf_counter() - started
    latencies = [latency for _, latency in results]
    errors = sum(1 for status, _ in results if status < 200 or status >= 400)
    report = {
        "url": url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "requestsPerSecond": round(args.requests / elapsed, 2),
        "errorRate": round(errors / args.requests, 4),
        "latencyMs": {
            "mean": round(statistics.mean(latencies), 2),
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "max": round(max(latencies), 2),
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if report["errorRate"] <= args.max_error_rate and report["latencyMs"]["p95"] <= args.max_p95_ms else 1


if __name__ == "__main__":
    raise SystemExit(main())
