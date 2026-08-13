from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_worker_enrollment_create_and_status() -> None:
    created = client.post(
        "/llm/worker-enrollments",
        json={
            "name": "Enrollment API worker",
            "requestedModelDigest": "sha256:enrollment-test",
            "requiredContextLength": 8192,
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["workerId"]
    assert payload["token"]
    assert payload["readiness"]["reasonCode"] in {"worker_offline", "no_enrolled_worker", "preflight_incomplete", "digest_mismatch", "model_policy_ambiguous", "worker_revoked", "ready"}

    status = client.get(
        f"/llm/worker-enrollments/{payload['enrollmentId']}",
        params={"requestedModelDigest": "sha256:enrollment-test", "requiredContextLength": 8192},
    )
    assert status.status_code == 200
    body = status.json()
    assert body["enrollmentId"] == payload["enrollmentId"]
    assert body["worker"]["name"] == "Enrollment API worker"


def test_worker_enrollment_rotate_and_canary_blocked_without_ready_worker() -> None:
    created = client.post(
        "/llm/worker-enrollments",
        json={
            "name": "Enrollment rotate worker",
            "requestedModelDigest": "sha256:rotate-test",
            "requiredContextLength": 8192,
        },
    )
    assert created.status_code == 201
    enrollment_id = created.json()["enrollmentId"]

    rotated = client.post(f"/llm/worker-enrollments/{enrollment_id}/rotate")
    assert rotated.status_code == 200
    assert rotated.json()["enrollmentId"] == enrollment_id
    assert rotated.json()["token"]

    canary = client.post(
        f"/llm/worker-enrollments/{enrollment_id}/canary",
        json={"requestedModelDigest": "sha256:rotate-test", "requiredContextLength": 8192},
    )
    assert canary.status_code == 409
