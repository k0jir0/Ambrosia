"""Organization-scoped persistence for the Alpha and Signals lifecycle."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from .tenant_context import apply_tenant_context


COLLECTIONS = (
    "signals",
    "signalVersions",
    "signalReviewLinks",
    "researchAttachmentEvents",
    "signalValidationRuns",
    "signalPolicyEvents",
    "scannerPromotions",
    "alphaHypotheses",
)


def empty_lifecycle_state() -> dict[str, dict]:
    return {name: {} for name in COLLECTIONS}


class LifecycleRepository(Protocol):
    def load(self, organization_id: str) -> dict[str, dict]: ...

    def save(self, organization_id: str, state: dict[str, dict]) -> None: ...


@dataclass
class MemoryLifecycleRepository:
    """Explicit development compatibility store, partitioned by organization."""

    _states: dict[str, dict[str, dict]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def load(self, organization_id: str) -> dict[str, dict]:
        with self._lock:
            return copy.deepcopy(self._states.get(organization_id, empty_lifecycle_state()))

    def save(self, organization_id: str, state: dict[str, dict]) -> None:
        with self._lock:
            self._states[organization_id] = copy.deepcopy(state)


class PostgresLifecycleRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        apply_tenant_context(connection)
        return connection

    @staticmethod
    def _canonical_hash(artifact: dict) -> str:
        payload = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def load(self, organization_id: str) -> dict[str, dict]:
        state = empty_lifecycle_state()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT hypothesis_id, artifact FROM alpha_hypothesis WHERE organization_id = %s",
                (organization_id,),
            ).fetchall()
            state["alphaHypotheses"] = {row["hypothesis_id"]: row["artifact"] for row in rows}

            rows = connection.execute(
                "SELECT signal_id, artifact FROM research_signal WHERE organization_id = %s",
                (organization_id,),
            ).fetchall()
            state["signals"] = {row["signal_id"]: row["artifact"] for row in rows}

            rows = connection.execute(
                "SELECT signal_id, artifact FROM research_signal_version WHERE organization_id = %s ORDER BY version",
                (organization_id,),
            ).fetchall()
            versions: defaultdict[str, list[dict]] = defaultdict(list)
            for row in rows:
                versions[row["signal_id"]].append(row["artifact"])
            state["signalVersions"] = dict(versions)

            rows = connection.execute(
                "SELECT validation_id, signal_id, artifact FROM signal_validation_record WHERE organization_id = %s ORDER BY completed_at",
                (organization_id,),
            ).fetchall()
            validations: defaultdict[str, list[dict]] = defaultdict(list)
            for row in rows:
                validations[row["signal_id"]].append(row["artifact"])
            state["signalValidationRuns"] = dict(validations)

            rows = connection.execute(
                "SELECT link_id, artifact FROM research_review_link WHERE organization_id = %s",
                (organization_id,),
            ).fetchall()
            state["signalReviewLinks"] = {row["link_id"]: row["artifact"] for row in rows}

            rows = connection.execute(
                "SELECT event_id, object_id, artifact FROM research_lifecycle_event WHERE organization_id = %s ORDER BY created_at",
                (organization_id,),
            ).fetchall()
            events: defaultdict[str, list[dict]] = defaultdict(list)
            for row in rows:
                if row["artifact"].get("eventType") == "research_object.attached":
                    state["researchAttachmentEvents"][row["event_id"]] = row["artifact"]
                else:
                    events[row["object_id"]].append(row["artifact"])
            state["signalPolicyEvents"] = dict(events)

            rows = connection.execute(
                "SELECT promotion_id, artifact FROM scanner_promotion WHERE organization_id = %s",
                (organization_id,),
            ).fetchall()
            state["scannerPromotions"] = {row["promotion_id"]: row["artifact"] for row in rows}
        return state

    def save(self, organization_id: str, state: dict[str, dict]) -> None:
        with self._connect() as connection:
            with connection.transaction():
                for table in (
                    "signal_validation_artifact",
                    "signal_decision_writeback",
                    "signal_outcome_writeback",
                    "scanner_promotion",
                    "research_review_link",
                    "research_object_snapshot",
                    "research_lifecycle_event",
                    "signal_validation_record",
                    "research_signal_version",
                    "research_signal",
                    "alpha_hypothesis",
                ):
                    connection.execute(
                        f"DELETE FROM {table} WHERE organization_id = %s",  # noqa: S608
                        (organization_id,),
                    )

                for hypothesis_id, artifact in state["alphaHypotheses"].items():
                    connection.execute(
                        """INSERT INTO alpha_hypothesis
                           (organization_id, hypothesis_id, title, status, artifact, updated_at)
                           VALUES (%s, %s, %s, %s, %s::jsonb, now())""",
                        (organization_id, hypothesis_id, artifact.get("title", hypothesis_id), artifact.get("status", "active"), json.dumps(artifact)),
                    )

                for signal_id, artifact in state["signals"].items():
                    connection.execute(
                        """INSERT INTO research_signal
                           (organization_id, signal_id, name, status, active_version, artifact, updated_at)
                           VALUES (%s, %s, %s, %s, %s, %s::jsonb, now())""",
                        (organization_id, signal_id, artifact.get("name", signal_id), artifact.get("status", "hypothesis"), int(artifact.get("activeVersion", artifact.get("version", 1))), json.dumps(artifact)),
                    )

                for signal_id, versions in state["signalVersions"].items():
                    for artifact in versions:
                        connection.execute(
                            """INSERT INTO research_signal_version
                               (organization_id, signal_id, version, artifact, content_hash)
                               VALUES (%s, %s, %s, %s::jsonb, %s)""",
                            (organization_id, signal_id, int(artifact["version"]), json.dumps(artifact), self._canonical_hash(artifact)),
                        )

                for signal_id, runs in state["signalValidationRuns"].items():
                    for artifact in runs:
                        validation_id = str(artifact["validationRunId"])
                        connection.execute(
                            """INSERT INTO signal_validation_record
                               (organization_id, validation_id, signal_id, signal_version, status, evidence_class, artifact, completed_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)""",
                            (organization_id, validation_id, signal_id, int(artifact["signalVersion"]), artifact.get("status", "unknown"), artifact.get("evidenceClass", "fixture"), json.dumps(artifact), artifact.get("completedAt")),
                        )
                        for artifact_ref in artifact.get("artifactRefs", []):
                            connection.execute(
                                """INSERT INTO signal_validation_artifact
                                   (organization_id, validation_id, artifact_ref)
                                   VALUES (%s, %s, %s)""",
                                (organization_id, validation_id, str(artifact_ref)),
                            )

                for link_id, artifact in state["signalReviewLinks"].items():
                    reference = artifact.get("researchObjectReference")
                    object_type = str(reference.get("objectType")) if reference else "signal"
                    object_id = str(reference.get("objectId")) if reference else str(artifact["signalId"])
                    object_version = int(reference.get("versionId")) if reference else int(artifact["signalVersion"])
                    snapshot = reference.get("snapshot") if reference else next(
                        item for item in state["signalVersions"].get(object_id, [])
                        if int(item.get("version", 0)) == object_version
                    )
                    content_hash = str(reference.get("contentHash")) if reference else self._canonical_hash(snapshot)
                    snapshot_id = str(reference.get("snapshotId")) if reference else f"signal:{object_id}:{object_version}:{content_hash[:16]}"
                    connection.execute(
                        """INSERT INTO research_object_snapshot
                           (organization_id, snapshot_id, object_type, object_id, object_version, content_hash, snapshot, source, data_mode, provider, as_of)
                           VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)""",
                        (organization_id, snapshot_id, object_type, object_id, object_version, content_hash, json.dumps(snapshot), reference.get("source") if reference else snapshot.get("source"), reference.get("mode") if reference else snapshot.get("dataMode"), reference.get("provider") if reference else snapshot.get("provider"), reference.get("asOf") if reference else snapshot.get("asOf")),
                    )
                    connection.execute(
                        """INSERT INTO research_review_link
                           (organization_id, link_id, review_id, object_type, object_id, object_version, snapshot_id, relationship_type, artifact, linked_at, updated_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, now()), now())""",
                        (organization_id, link_id, artifact["reviewId"], object_type, object_id, object_version, snapshot_id, artifact.get("relationshipType", "research_evidence"), json.dumps(artifact), artifact.get("linkedAt")),
                    )
                    if object_type == "signal" and artifact.get("reviewDecisionState"):
                        connection.execute(
                            """INSERT INTO signal_decision_writeback
                               (organization_id, writeback_id, signal_id, signal_version, review_id, decision_state, execution_readiness, artifact)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                            (organization_id, f"decision:{link_id}", object_id, object_version, artifact["reviewId"], artifact["reviewDecisionState"], artifact.get("executionReadiness", "not_executable"), json.dumps(artifact)),
                        )
                    if object_type == "signal" and artifact.get("outcomeQuality"):
                        connection.execute(
                            """INSERT INTO signal_outcome_writeback
                               (organization_id, writeback_id, signal_id, signal_version, review_id, outcome_quality, artifact, observed_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, now()))""",
                            (organization_id, f"outcome:{link_id}", object_id, object_version, artifact["reviewId"], artifact["outcomeQuality"], json.dumps(artifact), artifact.get("lastOutcomeAt")),
                        )

                for event_id, artifact in state["researchAttachmentEvents"].items():
                    connection.execute(
                        """INSERT INTO research_lifecycle_event
                           (organization_id, event_id, object_type, object_id, object_version, event_type, actor_subject, reason, artifact, created_at)
                           VALUES (%s, %s, %s, %s, %s, 'research_object.attached', %s, %s, %s::jsonb, COALESCE(%s::timestamptz, now()))""",
                        (organization_id, event_id, artifact["objectType"], artifact["objectId"], int(artifact["versionId"]), artifact.get("actor"), artifact.get("relationshipType"), json.dumps(artifact), artifact.get("attachedAt")),
                    )

                for signal_id, events in state["signalPolicyEvents"].items():
                    previous_status = None
                    for artifact in events:
                        connection.execute(
                            """INSERT INTO research_lifecycle_event
                               (organization_id, event_id, object_type, object_id, object_version, event_type, from_status, to_status, actor_subject, reason, artifact, created_at)
                               VALUES (%s, %s, 'signal', %s, %s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, now()))""",
                            (organization_id, artifact["eventId"], signal_id, artifact.get("signalVersion"), artifact.get("eventType", "unknown"), previous_status, artifact.get("toStatus"), artifact.get("actor"), artifact.get("reason"), json.dumps(artifact), artifact.get("createdAt")),
                        )
                        previous_status = artifact.get("toStatus")

                for promotion_id, artifact in state["scannerPromotions"].items():
                    connection.execute(
                        """INSERT INTO scanner_promotion
                           (organization_id, promotion_id, candidate_key, scanner_run_id, hypothesis_id, signal_id, signal_version, promoted_by_subject, artifact, promoted_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, now()))""",
                        (organization_id, promotion_id, artifact["candidateKey"], artifact["scannerRunId"], artifact["hypothesisId"], artifact["signalId"], int(artifact["signalVersion"]), artifact.get("promotedBy"), json.dumps(artifact), artifact.get("promotedAt")),
                    )