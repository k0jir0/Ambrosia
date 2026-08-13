#!/usr/bin/env python3
"""Authenticated staging canary for the outbound Ollama worker path."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL_STATES = {"completed", "failed", "dead_letter", "expired", "canceled", "superseded"}
SUCCESS_ADMISSION_STATES = {"auto_admitted", "awaiting_human_review", "human_admitted", "corrected_and_admitted"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one authenticated staging canary through the Ollama operation path."
    )
    parser.add_argument("--base-url", required=True, help="API base URL, for example https://api.example.com")
    parser.add_argument("--token", required=True, help="Bearer token for the canary tenant")
    parser.add_argument(
        "--requested-model-digest",
        default="",
        help="Exact approved model digest expected for the canary run",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=int,
        default=300,
        help="Maximum time to wait for the canary operation to reach a terminal state",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Polling interval for the operation status endpoint",
    )
    parser.add_argument(
        "--allow-awaiting-human-review",
        action="store_true",
        help="Treat a completed proposal awaiting human review as a successful worker-path canary",
    )
    return parser.parse_args()


def request_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    encoded = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=encoded, method=method, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}, dict(response.headers)
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        data = json.loads(body) if body else {}
        return exc.code, data, dict(exc.headers)
    except URLError as exc:
        raise SystemExit(f"Canary request failed for {url}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def build_packet_payload() -> dict[str, Any]:
    packet_id = f"staging-canary-{int(time.time())}"
    return {
        "id": packet_id,
        "title": "Staging Ollama canary packet",
        "thesis": "Semiconductor breadth and leadership may be stabilizing relative to the broad market.",
        "ticker": "SOXX",
        "assetClass": "ETF",
        "timeHorizon": "2-6 weeks",
        "intendedExpression": "Long ETF",
        "status": "synthesis",
        "decisionState": "watch",
        "confidence": 68,
        "trialCountImpact": 1,
        "followUpDate": "2026-08-20",
        "createdAt": "2026-08-13T10:00:00Z",
        "claims": [
            {
                "id": "claim-1",
                "kind": "sourced",
                "text": "Breadth has improved relative to the prior month.",
                "evidence": "canary-source-1",
                "confidence": 70,
            }
        ],
        "strongestCritique": "Improvement may be transient and driven by short covering.",
        "disconfirmingTest": "Relative breadth deteriorates over the next two weeks.",
        "historicalAnalogue": {
            "title": "Semiconductor recovery test",
            "similarity": "Sector leadership recovered after a breadth contraction.",
            "differences": "Macro backdrop differs from prior periods.",
            "resolution": "Requires ongoing validation.",
        },
        "validation": {
            "status": "specified",
            "hypothesis": "Breadth improvement supports a governed long thesis.",
            "nullHypothesis": "Breadth remains weak and the thesis should not advance.",
            "dataRequirements": ["Breadth", "Relative strength"],
            "protocol": "Run one governed adversarial review.",
            "refusalReason": None,
        },
        "tradeability": [],
        "sources": [
            {
                "id": "canary-source-1",
                "title": "Synthetic canary evidence",
                "sourceType": "internal",
                "timestamp": "2026-08-13T09:00:00Z",
                "permission": "user_owned",
                "relevance": 0.8,
            }
        ],
        "audit": [
            {
                "id": "canary-audit-1",
                "timestamp": "10:00:00",
                "eventType": "packet.created",
                "detail": "Staging canary packet created",
            }
        ],
    }


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    params = []
    if args.requested_model_digest:
        params.append(f"requestedModelDigest={args.requested_model_digest}")
    provider_url = f"{base_url}/providers/status"
    if params:
        provider_url = f"{provider_url}?{'&'.join(params)}"
    status_code, provider_status, _ = request_json("GET", provider_url, args.token)
    require(status_code == 200, f"Provider status failed: HTTP {status_code} {provider_status}")
    readiness = provider_status.get("ollamaWorkerReadiness") or {}
    require(readiness.get("ready") is True, f"Worker readiness is blocked: {readiness}")

    packet_payload = build_packet_payload()
    packet_id = packet_payload["id"]
    status_code, created_packet, _ = request_json(
        "POST", f"{base_url}/packets", args.token, packet_payload
    )
    require(status_code in {200, 201}, f"Packet creation failed: HTTP {status_code} {created_packet}")
    require(created_packet.get("id") == packet_id, f"Packet creation returned unexpected id: {created_packet}")

    operation_payload: dict[str, Any] = {"providerMode": "ollama"}
    if args.requested_model_digest:
        operation_payload["requestedModelDigest"] = args.requested_model_digest
    status_code, operation, _ = request_json(
        "POST",
        f"{base_url}/packets/{packet_id}/agent-operations",
        args.token,
        operation_payload,
    )
    require(status_code == 202, f"Operation creation failed: HTTP {status_code} {operation}")
    operation_id = operation.get("id")
    require(isinstance(operation_id, str) and operation_id, f"Operation id missing: {operation}")

    deadline = time.time() + args.max_wait_seconds
    latest = operation
    while time.time() < deadline:
        status_code, latest, _ = request_json(
            "GET", f"{base_url}/operations/{operation_id}", args.token
        )
        require(status_code == 200, f"Operation polling failed: HTTP {status_code} {latest}")
        state = latest.get("state")
        if state in TERMINAL_STATES:
            break
        time.sleep(args.poll_seconds)
    else:
        raise SystemExit(f"Canary operation did not complete before timeout: {latest}")

    require(latest.get("state") == "completed", f"Canary operation ended unsuccessfully: {latest}")
    require(latest.get("actualProvider") == "ollama-local-worker", f"Unexpected provider path: {latest}")
    require(not latest.get("fallbackOperationId"), f"Canary should not use fallback: {latest}")

    admission_state = latest.get("admissionState")
    if admission_state == "awaiting_human_review":
        require(
            args.allow_awaiting_human_review,
            f"Canary requires automatic admission but proposal awaits human review: {latest}",
        )
    else:
        require(
            admission_state in SUCCESS_ADMISSION_STATES,
            f"Canary operation completed without a valid admission state: {latest}",
        )

    proposal_status, proposal, _ = request_json(
        "GET", f"{base_url}/operations/{operation_id}/proposal", args.token
    )
    require(proposal_status == 200, f"Proposal lookup failed: HTTP {proposal_status} {proposal}")
    require(proposal.get("proposalEvents"), f"Proposal has no event lineage: {proposal}")

    summary = {
        "packetId": packet_id,
        "operationId": operation_id,
        "state": latest.get("state"),
        "admissionState": admission_state,
        "verificationStatus": latest.get("verificationStatus"),
        "proposalId": proposal.get("id"),
        "proposalEvent": proposal.get("proposalEvents", [])[-1].get("eventType"),
        "resultPacketVersion": latest.get("resultPacketVersion"),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
