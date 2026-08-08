"""Canonical tenant-bound S3 object key construction."""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath
from uuid import UUID

from .tenant_context import current_organization_id

_KINDS = {"exports", "evidence", "llm", "reports"}
_SAFE_FILENAME = re.compile(r"[^a-zA-Z0-9._-]+")


def tenant_object_key(kind: str, object_reference: str, filename: str) -> str:
    """Create an opaque key under the authenticated tenant's prefix.

    Tenant identity is read only from request context; callers cannot supply or
    guess another organization. Object references are hashed and filenames are
    reduced to their final safe component to prevent path traversal.
    """

    organization_id = current_organization_id()
    if not organization_id:
        raise PermissionError("tenant context is required for object storage")
    normalized_org = str(UUID(organization_id))
    if kind not in _KINDS:
        raise ValueError("unsupported artifact kind")
    if not object_reference or len(object_reference) > 500:
        raise ValueError("object reference is required")
    basename = PurePosixPath(filename.replace("\\", "/")).name
    safe_name = _SAFE_FILENAME.sub("-", basename).strip(".-")[:120]
    if not safe_name:
        raise ValueError("safe filename is required")
    reference_hash = hashlib.sha256(object_reference.encode()).hexdigest()
    return f"tenants/{normalized_org}/{kind}/{reference_hash}/{safe_name}"
