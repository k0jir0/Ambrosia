"""Privacy-minimized, tenant-scoped activation telemetry."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from .operations import current_principal
from .tenant_context import apply_tenant_context

router = APIRouter(prefix="/analytics", tags=["product-analytics"])

EVENT_TYPES = {
    "onboarding_viewed",
    "guided_started",
    "own_thesis_started",
    "packet_saved",
    "review_completed",
    "outcome_recorded",
    "return_session",
}
PROPERTY_KEYS = {"mode", "sourceLabel", "workflowVersion", "durationBucket", "errorCode"}


class ProductEventCreate(BaseModel):
    eventType: str = Field(min_length=3, max_length=80)
    surface: str = Field(min_length=1, max_length=80)
    objectReference: str | None = Field(default=None, max_length=500)
    eventKey: str | None = Field(default=None, min_length=8, max_length=120)
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ProductAnalytics:
    def __init__(self) -> None:
        self._lock = RLock()
        self._events: list[dict] = []

    @property
    def durable(self) -> bool:
        return bool(os.getenv("DATABASE_URL", "").strip())

    def _connect(self):
        connection = psycopg.connect(
            os.environ["DATABASE_URL"], connect_timeout=5, row_factory=dict_row
        )
        apply_tenant_context(connection)
        return connection

    def record(self, organization_id: str, user_id: str, event: ProductEventCreate) -> bool:
        if event.eventType not in EVENT_TYPES:
            raise ValueError("event type is not part of the minimized activation taxonomy")
        unexpected = set(event.properties) - PROPERTY_KEYS
        if unexpected:
            raise ValueError("event properties contain fields outside the minimized taxonomy")
        row = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "user_id": user_id,
            "event_type": event.eventType,
            "surface": event.surface,
            "object_reference_hash": (
                hashlib.sha256(event.objectReference.encode()).hexdigest()
                if event.objectReference else None
            ),
            "event_key": event.eventKey,
            "properties": dict(event.properties),
            "occurred_at": datetime.now(UTC),
        }
        if self.durable:
            with self._connect() as connection:
                result = connection.execute(
                    """
                    INSERT INTO product_events (
                      id, organization_id, user_id, event_type, surface,
                      object_reference_hash, event_key, properties, occurred_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (organization_id, event_key)
                      WHERE event_key IS NOT NULL DO NOTHING
                    """,
                    (
                        row["id"], organization_id, user_id, row["event_type"],
                        row["surface"], row["object_reference_hash"], row["event_key"],
                        json.dumps(row["properties"]), row["occurred_at"],
                    ),
                )
                return result.rowcount == 1
        with self._lock:
            if event.eventKey and any(
                item["organization_id"] == organization_id
                and item["event_key"] == event.eventKey
                for item in self._events
            ):
                return False
            self._events.append(row)
        return True

    def activation(self, organization_id: str, days: int) -> dict:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        if self.durable:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT event_type, COUNT(*) AS event_count,
                           COUNT(DISTINCT user_id) AS unique_users
                    FROM product_events
                    WHERE occurred_at >= %s
                    GROUP BY event_type ORDER BY event_type
                    """,
                    (cutoff,),
                ).fetchall()
            return {
                "windowDays": days,
                "events": {
                    row["event_type"]: {
                        "count": int(row["event_count"]),
                        "uniqueUsers": int(row["unique_users"]),
                    }
                    for row in rows
                },
            }
        with self._lock:
            rows = [
                event for event in self._events
                if event["organization_id"] == organization_id and event["occurred_at"] >= cutoff
            ]
        counts = Counter(event["event_type"] for event in rows)
        unique = {
            event_type: len({event["user_id"] for event in rows if event["event_type"] == event_type})
            for event_type in counts
        }
        return {
            "windowDays": days,
            "events": {
                event_type: {"count": count, "uniqueUsers": unique[event_type]}
                for event_type, count in sorted(counts.items())
            },
        }

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


analytics = ProductAnalytics()


def _principal():
    principal = current_principal()
    if principal is None or not principal.organization_id:
        raise HTTPException(status_code=401, detail="Tenant-bound identity required")
    return principal


@router.post("/events", status_code=202)
def record_event(event: ProductEventCreate) -> dict:
    principal = _principal()
    if principal.auth_method != "session":
        raise HTTPException(status_code=403, detail="User session required for product telemetry")
    try:
        inserted = analytics.record(principal.organization_id, principal.subject, event)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"accepted": True, "inserted": inserted}


@router.get("/activation")
def activation_report(days: int = 30) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin", "service"}:
        raise HTTPException(status_code=403, detail="Organization administrator required")
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")
    return analytics.activation(principal.organization_id, days)
