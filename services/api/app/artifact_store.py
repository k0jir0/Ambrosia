"""Tenant-bound governed artifact persistence for S3/KMS."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import boto3
import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from .operations import current_principal
from .tenant_artifacts import tenant_object_key
from .tenant_context import apply_tenant_context, current_organization_id

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def _production() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() in {"staging", "production"}


class ArtifactStore:
    def __init__(self) -> None:
        self._report_probe: dict = {
            "enabled": False,
            "writable": False,
            "lastProbeAt": None,
            "reasonCode": "not_probed",
        }
        self._report_probe_monotonic = 0.0

    def _bucket(self) -> str:
        return os.getenv("ARTIFACT_BUCKET", "").strip()

    def _client(self):
        return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

    def healthcheck(self) -> None:
        bucket = self._bucket()
        if not bucket:
            if _production():
                raise RuntimeError("ARTIFACT_BUCKET is required")
            return
        self._client().head_bucket(Bucket=bucket)

    def report_export_healthcheck(self) -> None:
        """Prove the staging report path can perform an encrypted S3 write."""
        protected = _production()
        if protected and not os.getenv("DATABASE_URL", "").strip():
            self._record_report_probe(False, "database_unconfigured")
            raise RuntimeError("DATABASE_URL is required for governed report export")
        bucket = self._bucket()
        if not bucket:
            if protected:
                self._record_report_probe(False, "artifact_bucket_unconfigured")
                raise RuntimeError("ARTIFACT_BUCKET is required for governed report export")
            self._record_report_probe(True, "development_storage_not_configured")
            return
        kms_key = os.getenv("ARTIFACT_KMS_KEY_ARN", "").strip()
        if protected and not kms_key:
            self._record_report_probe(False, "kms_key_unconfigured")
            raise RuntimeError("ARTIFACT_KMS_KEY_ARN is required for governed report export")
        if self._report_probe["writable"] and time.monotonic() - self._report_probe_monotonic < 60:
            return
        client = self._client()
        key = f"_health/report-export/{uuid4()}.json"
        request = {
            "Bucket": bucket,
            "Key": key,
            "Body": b"{}",
            "ContentType": "application/json",
            "ServerSideEncryption": "aws:kms",
        }
        if kms_key:
            request["SSEKMSKeyId"] = kms_key
        try:
            client.put_object(**request)
            client.delete_object(Bucket=bucket, Key=key)
        except Exception:
            self._record_report_probe(False, "encrypted_write_probe_failed")
            raise
        self._record_report_probe(True, "ready")

    def _record_report_probe(self, writable: bool, reason: str) -> None:
        self._report_probe = {
            "enabled": True,
            "writable": writable,
            "lastProbeAt": datetime.now(UTC).isoformat(),
            "reasonCode": reason,
        }
        self._report_probe_monotonic = time.monotonic()

    def report_export_status(self) -> dict:
        return dict(self._report_probe)

    def persist_json(
        self,
        kind: str,
        object_reference: str,
        filename: str,
        payload: object,
        *,
        created_by_user_id: str | None = None,
    ) -> dict:
        organization_id = current_organization_id()
        if not organization_id:
            raise PermissionError("tenant context is required for artifact persistence")
        bucket = self._bucket()
        if not bucket:
            if _production():
                raise RuntimeError("ARTIFACT_BUCKET is required")
            return {"artifactId": None, "storageStatus": "development_not_persisted"}

        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        content_hash = hashlib.sha256(encoded).hexdigest()
        key = tenant_object_key(kind, object_reference, filename)
        artifact_id = str(uuid4())
        principal = current_principal()
        created_by = created_by_user_id or (principal.subject if principal else None)
        if created_by:
            try:
                created_by = str(UUID(created_by))
            except ValueError:
                created_by = None
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL is required for governed artifact persistence")

        with psycopg.connect(database_url) as connection:
            apply_tenant_context(connection)
            connection.execute(
                """
                INSERT INTO artifact_records (
                  id, organization_id, created_by_user_id, artifact_kind,
                  object_reference_hash, storage_key, content_hash, content_type,
                  size_bytes, storage_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'application/json', %s, 'pending')
                """,
                (
                    artifact_id, organization_id, created_by, kind,
                    hashlib.sha256(object_reference.encode()).hexdigest(), key,
                    content_hash, len(encoded),
                ),
            )
        try:
            request = {
                "Bucket": bucket,
                "Key": key,
                "Body": encoded,
                "ContentType": "application/json",
                "Metadata": {"content-sha256": content_hash, "artifact-id": artifact_id},
                "ServerSideEncryption": "aws:kms",
            }
            kms_key = os.getenv("ARTIFACT_KMS_KEY_ARN", "").strip()
            if kms_key:
                request["SSEKMSKeyId"] = kms_key
            self._client().put_object(**request)
        except Exception:
            self._set_status(database_url, artifact_id, "failed")
            raise
        self._set_status(database_url, artifact_id, "durable")
        return {"artifactId": artifact_id, "storageStatus": "durable"}

    @staticmethod
    def _set_status(database_url: str, artifact_id: str, status: str) -> None:
        with psycopg.connect(database_url) as connection:
            apply_tenant_context(connection)
            connection.execute(
                "UPDATE artifact_records SET storage_status = %s, updated_at = now() WHERE id = %s",
                (status, artifact_id),
            )

    def list_records(self, kind: str | None = None) -> list[dict]:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            return []
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            apply_tenant_context(connection)
            if kind:
                rows = connection.execute(
                    """
                    SELECT id, artifact_kind, content_hash, size_bytes, storage_status, created_at
                    FROM artifact_records WHERE artifact_kind = %s
                    ORDER BY created_at DESC LIMIT 100
                    """,
                    (kind,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, artifact_kind, content_hash, size_bytes, storage_status, created_at
                    FROM artifact_records ORDER BY created_at DESC LIMIT 100
                    """
                ).fetchall()
        return [dict(row) for row in rows]

    def download_url(self, artifact_id: str) -> str | None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            return None
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            apply_tenant_context(connection)
            row = connection.execute(
                "SELECT storage_key FROM artifact_records WHERE id = %s AND storage_status = 'durable'",
                (artifact_id,),
            ).fetchone()
        if not row:
            return None
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket(), "Key": row["storage_key"]},
            ExpiresIn=60,
        )

    def load_json(self, artifact_id: str) -> object:
        """Read and hash-verify one tenant-scoped durable JSON artifact server-side."""
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url or not self._bucket():
            raise RuntimeError("Durable artifact storage is unavailable")
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            apply_tenant_context(connection)
            row = connection.execute(
                """SELECT storage_key,content_hash FROM artifact_records
                WHERE id=%s AND storage_status='durable'""",
                (artifact_id,),
            ).fetchone()
        if not row:
            raise FileNotFoundError("Governed artifact not found")
        encoded = self._client().get_object(Bucket=self._bucket(), Key=row["storage_key"])[
            "Body"
        ].read()
        if hashlib.sha256(encoded).hexdigest() != row["content_hash"]:
            raise ValueError("Governed artifact content hash mismatch")
        return json.loads(encoded)

    def discard(self, artifact_id: str) -> None:
        """Compensate a failed parent transaction without leaving readable input data."""
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url or not self._bucket():
            return
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            apply_tenant_context(connection)
            row = connection.execute(
                "SELECT storage_key FROM artifact_records WHERE id=%s FOR UPDATE",
                (artifact_id,),
            ).fetchone()
            if not row:
                return
            self._client().delete_object(Bucket=self._bucket(), Key=row["storage_key"])
            connection.execute(
                "UPDATE artifact_records SET storage_status='deleted',updated_at=now() WHERE id=%s",
                (artifact_id,),
            )


artifact_store = ArtifactStore()


@router.get("")
def list_artifacts(kind: str | None = None) -> dict:
    if kind is not None and kind not in {"exports", "evidence", "llm", "reports"}:
        raise HTTPException(status_code=422, detail="Unsupported artifact kind")
    return {"artifacts": artifact_store.list_records(kind)}


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: str) -> dict:
    try:
        UUID(artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    url = artifact_store.download_url(artifact_id)
    if not url:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return {"url": url, "expiresInSeconds": 60}
