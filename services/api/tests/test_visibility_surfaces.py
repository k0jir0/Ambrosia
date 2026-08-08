from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ADVANCED_HEADERS = {"X-Ambrosia-Role": "analyst"}
ADMIN_HEADERS = {"X-Ambrosia-Role": "admin"}


def test_frontend_visibility_matrix_available_for_advanced_role() -> None:
    response = client.get("/visibility/frontend-matrix", headers=ADVANCED_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "advanced"
    assert payload["path"] == "docs/visibility/frontend-visibility-matrix.md"
    assert "# Frontend Visibility Matrix" in payload["content"]


def test_frontend_visibility_matrix_requires_role() -> None:
    response = client.get(
        "/visibility/frontend-matrix",
        headers={"X-Ambrosia-Role": "viewer"},
    )
    assert response.status_code == 403


def test_admin_boundary_rules_available_for_admin() -> None:
    response = client.get("/admin/boundary-rules", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "admin"
    assert payload["path"] == "docs/visibility/admin-boundary-rules.md"
    assert "# Admin Boundary Rules" in payload["content"]


def test_admin_boundary_rules_denied_for_analyst() -> None:
    response = client.get("/admin/boundary-rules", headers=ADVANCED_HEADERS)
    assert response.status_code == 403
