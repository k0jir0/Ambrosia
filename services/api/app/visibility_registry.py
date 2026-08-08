from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException

from .project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
FUNCTION_REGISTRY_PATH = ROOT / "docs" / "visibility" / "function-registry.json"
FRONTEND_MATRIX_PATH = ROOT / "docs" / "visibility" / "frontend-visibility-matrix.md"
ADMIN_BOUNDARY_RULES_PATH = ROOT / "docs" / "visibility" / "admin-boundary-rules.md"


def load_function_registry() -> list[dict[str, str]]:
    if not FUNCTION_REGISTRY_PATH.exists():
        raise HTTPException(status_code=404, detail="Function registry artifact not found")

    with FUNCTION_REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_markdown(path: Path, *, missing_detail: str, surface: str) -> dict[str, str]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=missing_detail)

    content = path.read_text(encoding="utf-8")
    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return {
        "surface": surface,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "updatedAt": updated_at,
        "content": content,
    }


def load_frontend_visibility_matrix() -> dict[str, str]:
    return _load_markdown(
        FRONTEND_MATRIX_PATH,
        missing_detail="Frontend visibility matrix artifact not found",
        surface="advanced",
    )


def load_admin_boundary_rules() -> dict[str, str]:
    return _load_markdown(
        ADMIN_BOUNDARY_RULES_PATH,
        missing_detail="Admin boundary rules artifact not found",
        surface="admin",
    )
