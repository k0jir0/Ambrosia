"""Regression suite for the Index162-164 governed Ollama/report module.

The suite is intentionally runnable from the repository root. It exercises the
stateful Python contracts directly and verifies the browser/AWS release gates
that cannot be instantiated without a deployed staging environment.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.api_problems import normalize_error_code, problem_document  # noqa: E402
from app.artifact_store import ArtifactStore  # noqa: E402
from app.llm_catalog import (  # noqa: E402
    Catalog,
    LlmJobCreate,
    WorkerClaim,
    WorkerResult,
    canonical_hash,
)


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def correction_candidate() -> dict:
    return {
        "schemaVersion": "specialist-output.v2",
        "role": "correctionVerifier",
        "instructionReferences": ["I1", "I2", "I3", "I4"],
        "summary": "The reviewer-authored correction is evaluated without rewriting.",
        "roleConclusion": "The corrected inference is supported by the supplied evidence.",
        "confidence": {
            "direction": "supports",
            "evidenceStrength": 0.8,
            "modelUncertainty": 0.2,
            "coverage": 1.0,
            "materiality": "high",
        },
        "claimsTested": ["Corrected bounded inference."],
        "materialClaims": [
            {
                "claimId": "corrected-1",
                "text": "Exact reviewer-authored correction.",
                "claimType": "inference",
                "materiality": "high",
                "supportingEvidenceIds": ["source-1"],
                "contradictingEvidenceIds": [],
                "uncertainty": 0.2,
                "falsifier": "A subsequent filing contradicts the cited observation.",
                "admissionStatus": "human_review",
            }
        ],
        "verificationFindings": [
            {
                "claimId": "corrected-1",
                "status": "entailed",
                "evidenceIds": ["source-1"],
                "reasons": [],
                "deterministicChecksPassed": True,
                "verifier": "ollama-independent-verifier.v2",
            }
        ],
        "falsifiableConditions": ["A later filing reverses the observation."],
        "alternativeExplanations": [],
        "contradictions": [],
        "missingEvidence": [],
        "evidenceReferences": ["source-1"],
        "abstained": False,
    }


class GovernedWorkflowUnitTests(unittest.TestCase):
    def test_problem_contract_preserves_domain_failures_and_correlation(self) -> None:
        self.assertEqual(
            normalize_error_code(503, {"code": "worker_offline"}, "/providers/status"),
            "WORKER_OFFLINE",
        )
        self.assertEqual(
            normalize_error_code(503, "provider unavailable", "/market/AAPL/snapshot"),
            "MARKET_DATA_UNAVAILABLE",
        )
        problem = problem_document(
            status=503,
            detail={"code": "worker_offline", "operationId": "operation-1"},
            request_id="request-1",
            trace_id="trace-1",
            path="/providers/status",
        )
        self.assertEqual(problem["code"], "WORKER_OFFLINE")
        self.assertEqual(problem["requestId"], "request-1")
        self.assertEqual(problem["traceId"], "trace-1")
        self.assertEqual(problem["operationId"], "operation-1")
        self.assertTrue(problem["retryable"])

    def test_report_idempotency_replays_and_rejects_key_reuse(self) -> None:
        artifact_store = ArtifactStore()
        principal = SimpleNamespace(subject="reviewer-1")
        with (
            patch.dict(os.environ, {"DATABASE_URL": ""}),
            patch("app.artifact_store.current_organization_id", return_value="tenant-1"),
            patch("app.artifact_store.current_principal", return_value=principal),
        ):
            state, replay = artifact_store.begin_report_request(
                "stable-key", "a" * 64, "packet-1", 1
            )
            self.assertEqual((state, replay), ("new", None))
            state, _ = artifact_store.begin_report_request(
                "stable-key", "a" * 64, "packet-1", 1
            )
            self.assertEqual(state, "pending")
            artifact_store.finish_report_request(
                "stable-key", "a" * 64, {"artifactId": "artifact-1"}
            )
            state, replay = artifact_store.begin_report_request(
                "stable-key", "a" * 64, "packet-1", 1
            )
            self.assertEqual(state, "replay")
            self.assertEqual(replay, {"artifactId": "artifact-1"})
            state, _ = artifact_store.begin_report_request(
                "stable-key", "b" * 64, "packet-2", 1
            )
            self.assertEqual(state, "conflict")

    def test_corrected_claim_requires_bound_independent_worker_run(self) -> None:
        model_digest = "sha256:qwen-governed-test"
        binding_hash = canonical_hash({"proposal": "proposal-1", "correction": "exact"})
        candidate = correction_candidate()
        job_request = LlmJobCreate(
            packetId="packet-1",
            thesis="Independently verify exact corrected prose against supplied evidence.",
            claims=[candidate["materialClaims"][0]["text"]],
            evidence=[{"id": "source-1", "sourceName": "Test filing"}],
            observationCutoff=datetime.now(UTC),
            role="correctionVerifier",
            tickerIdentity={
                "ticker": "AAPL",
                "canonicalTicker": "AAPL",
                "instrumentId": "instrument-aapl",
                "resolutionStatus": "verified",
            },
            requestedModel="qwen3:8b-q4_K_M",
            requestedModelDigest=model_digest,
            verificationCandidate=candidate,
            verificationBindingHash=binding_hash,
        )

        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            catalog = Catalog()
            credential = catalog.create_worker("tenant-1", "owner-1", "Pinned Qwen worker")
            worker = catalog.authenticate_worker(credential["token"])
            self.assertIsNotNone(worker)
            queued = catalog.enqueue("tenant-1", job_request)
            lease = catalog.claim(
                worker,
                120,
                WorkerClaim(
                    models=[
                        {
                            "name": "qwen3:8b-q4_K_M",
                            "digest": model_digest,
                            "contextLength": 8192,
                            "readiness": "preflighted",
                            "preflightCompletedAt": datetime.now(UTC).isoformat(),
                        }
                    ]
                ),
            )
            self.assertIsNotNone(lease)
            started = datetime.now(UTC)
            result = WorkerResult(
                leaseId=lease["leaseId"],
                generation=lease["generation"],
                inputHash=lease["inputHash"],
                modelName="qwen3:8b-q4_K_M",
                modelDigest=model_digest,
                verifierModelName="qwen3:8b-q4_K_M",
                verifierModelDigest=model_digest,
                startedAt=started,
                completedAt=started + timedelta(seconds=1),
                output=candidate,
            )
            result = result.model_copy(
                update={
                    "resultHash": canonical_hash(
                        result.output.model_dump(mode="json", exclude_unset=True)
                    )
                }
            )
            completed = catalog.complete(worker, queued["id"], result)
            self.assertIsNotNone(completed)
            self.assertEqual(completed["verificationStatus"], "passed")
            trusted = catalog.correction_verification(
                "tenant-1", completed["runId"], binding_hash
            )
            self.assertIsNotNone(trusted)
            self.assertEqual(
                trusted["structured_output"]["materialClaims"][0]["text"],
                "Exact reviewer-authored correction.",
            )
            self.assertIsNone(
                catalog.correction_verification(
                    "tenant-1", completed["runId"], "0" * 64
                )
            )


class GovernedWorkflowRepositoryContractTests(unittest.TestCase):
    def test_v0015_migration_governs_retention_replay_and_tenant_isolation(self) -> None:
        migration = read_text(
            "infra/db/migrations/V0015__govern_proposal_retention_and_report_replay.sql"
        )
        schema = read_text("infra/db/schema-version.json")
        for required in (
            "retention_until",
            "legal_hold",
            "deletion_state",
            "report_generation_requests",
            "idempotency_key_hash",
            "ENABLE ROW LEVEL SECURITY",
            "CREATE POLICY tenant_isolation",
        ):
            self.assertIn(required, migration)
        self.assertIn('"dbSchemaVersion": "v0015"', schema)

    def test_frontend_governed_reports_fail_closed_and_reverify_corrections(self) -> None:
        api = read_text("apps/web/src/lib/api.ts")
        workbench = read_text("apps/web/src/components/workbench.tsx")
        self.assertIn("GOVERNED_REPORT_EXPORT_ENABLED", api)
        self.assertIn("ARTIFACT_STORAGE_UNAVAILABLE", api)
        self.assertIn("report.reportValidationStatus", api)
        self.assertIn("/correction-verification", api)
        self.assertIn("correctionVerificationRunId", api)
        self.assertIn("if (governedReportExportEnabled) throw error", workbench)
        self.assertNotIn(
            'provenanceLabel: "API unavailable',
            workbench,
        )

    def test_aws_release_requires_same_commit_and_writable_report_storage(self) -> None:
        workflow = read_text(".github/workflows/aws-release.yml")
        terraform = read_text("infra/aws/main.tf")
        for required in (
            "NEXT_PUBLIC_ENABLE_REVIEW_EXPORT=true",
            "NEXT_PUBLIC_BUILD_SHA=$GITHUB_SHA",
            'jq -r .buildSha "$RUNNER_TEMP/api-version.json"',
            'jq -r .buildSha "$RUNNER_TEMP/web-version.json"',
            'jq -r .reportExport.writable "$RUNNER_TEMP/capabilities.json"',
            'jq -r .dbSchemaVersion "$RUNNER_TEMP/api-version.json"',
        ):
            self.assertIn(required, workflow)
        self.assertIn('path     = "/live"', terraform)
        self.assertIn('metric_name         = "UnHealthyHostCount"', terraform)
        self.assertIn("ReportArtifactFailure", terraform)
        self.assertIn("KmsAccessDenied", terraform)
        self.assertIn("PersistenceUnavailable", terraform)


if __name__ == "__main__":
    unittest.main()
