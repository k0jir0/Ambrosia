from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_offline_bundle_manifest_includes_local_worker_release_block() -> None:
    response = client.get("/enterprise/deployment-bundles/offline")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == "enterprise-offline-bundle.v1"
    assert "ambrosia-local-worker" in payload["components"]
    assert payload["localWorkerRelease"]["availability"] in {"published", "unpublished"}


def test_offline_bundle_manifest_uses_worker_distribution_env(monkeypatch) -> None:
    monkeypatch.setenv("AMBROSIA_LOCAL_WORKER_BUNDLE_URL", "https://example.invalid/worker/ambrosia-local-worker.zip")
    monkeypatch.setenv("AMBROSIA_LOCAL_WORKER_BUNDLE_SHA256", "abc123")
    monkeypatch.setenv("AMBROSIA_LOCAL_WORKER_SBOM_URL", "https://example.invalid/worker/ambrosia-local-worker.spdx.json")
    monkeypatch.setenv("AMBROSIA_LOCAL_WORKER_PROVENANCE_URL", "https://example.invalid/worker/ambrosia-local-worker.intoto.jsonl")
    monkeypatch.setenv("AMBROSIA_LOCAL_WORKER_SIGNATURE_URL", "https://example.invalid/worker/ambrosia-local-worker.sig")

    response = client.get("/enterprise/deployment-bundles/offline")
    assert response.status_code == 200
    payload = response.json()
    assert payload["localWorkerRelease"]["availability"] == "published"
    assert payload["localWorkerRelease"]["bundleUrl"] == "https://example.invalid/worker/ambrosia-local-worker.zip"
    assert payload["localWorkerRelease"]["checksumSha256"] == "abc123"
    assert payload["localWorkerRelease"]["sbomUrl"] == "https://example.invalid/worker/ambrosia-local-worker.spdx.json"
    assert payload["localWorkerRelease"]["provenanceUrl"] == "https://example.invalid/worker/ambrosia-local-worker.intoto.jsonl"
    assert payload["localWorkerRelease"]["signatureUrl"] == "https://example.invalid/worker/ambrosia-local-worker.sig"
    assert payload["localWorkerRelease"]["signatureType"] == "sigstore-cosign"
