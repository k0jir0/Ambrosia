from __future__ import annotations

from typing import Any


WRITE_COMMANDS = {
    "ambrosia config set-api-url",
    "ambrosia reviews create",
    "ambrosia packets create",
    "ambrosia scanner run",
    "ambrosia relay evaluate",
    "ambrosia signals create",
    "ambrosia signals link-review",
    "ambrosia signals writeback-decision",
    "ambrosia signals writeback-outcome",
    "ambrosia alpha create",
    "ambrosia backtests run",
    "ambrosia paper-trades create",
    "ambrosia warm-path ingest",
    "ambrosia enterprise service-account",
    "ambrosia enterprise service-account-rotate",
    "ambrosia enterprise service-account-revoke",
    "ambrosia enterprise audit-export",
    "ambrosia enterprise sso-config",
}

TESTED_COMMANDS = {
    "ambrosia commands list",
    "ambrosia examples",
    "ambrosia status",
    "ambrosia quickstart",
    "ambrosia health",
    "ambrosia market snapshot",
    "ambrosia relay runs",
    "ambrosia signals link-review",
    "ambrosia signals writeback-decision",
    "ambrosia signals quality-scorecard",
}

QUALIFIED_READ_CONTRACTS = {
    "ambrosia health": "/health",
    "ambrosia reviews list": "/reviews",
    "ambrosia reviews get": "/reviews/{review_id}",
    "ambrosia packets list": "/packets",
    "ambrosia packets get": "/packets/{packet_id}",
    "ambrosia packets audit": "/packets/{packet_id}/audit",
    "ambrosia market snapshot": "/market/{ticker}/snapshot",
    "ambrosia jobs list": "/jobs",
    "ambrosia jobs get": "/jobs/{job_id}",
    "ambrosia plans list": "/roadmap/plans",
    "ambrosia plans get": "/roadmap/plans/{plan_id}",
    "ambrosia signals list": "/signals",
    "ambrosia signals get": "/signals/{signal_id}",
    "ambrosia signals quality-scorecard": "/signals/quality-scorecard/weekly",
    "ambrosia alpha list": "/alpha/hypotheses",
    "ambrosia alpha decay": "/signals/{signal_id}/alpha-decay",
    "ambrosia enterprise service-accounts": "/enterprise/service-accounts",
    "ambrosia enterprise sso-get": "/enterprise/sso/config",
    "ambrosia enterprise offline-bundle": "/enterprise/deployment-bundles/offline",
    "ambrosia enterprise security-packet": "/enterprise/support/security-packet",
    "ambrosia enterprise readiness": "/enterprise/readiness",
}


def add_guide_evidence(entry: dict[str, Any]) -> dict[str, Any]:
    command = str(entry["command"])
    endpoint = QUALIFIED_READ_CONTRACTS.get(command)
    return {
        **entry,
        "authority": "write" if command in WRITE_COMMANDS else "read",
        "implementationStatus": "implemented",
        "testStatus": "tested" if command in TESTED_COMMANDS else "not-tested",
        "qualificationStatus": "qualified" if endpoint else "not-qualified",
        "endpoint": endpoint,
    }