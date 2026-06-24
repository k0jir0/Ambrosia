from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from .models import AuditEvent, AuditEventCreate, DecisionPacket, DecisionState


@dataclass
class PacketQuery:
    search: str | None = None
    ticker: str | None = None
    decision_state: DecisionState | None = None


class PostgresPacketStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def healthcheck(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

    def save_packet(self, packet: DecisionPacket) -> DecisionPacket:
        payload = packet.model_dump(mode="json")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO review_packet (
                        packet_id,
                        schema_version,
                        workflow_version,
                        ticker,
                        decision_state,
                        confidence,
                        created_at,
                        artifact
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (packet_id)
                    DO UPDATE SET
                        schema_version = EXCLUDED.schema_version,
                        workflow_version = EXCLUDED.workflow_version,
                        ticker = EXCLUDED.ticker,
                        decision_state = EXCLUDED.decision_state,
                        confidence = EXCLUDED.confidence,
                        artifact = EXCLUDED.artifact,
                        updated_at = now()
                    """,
                    (
                        packet.id,
                        packet.schemaVersion,
                        packet.workflowVersion,
                        packet.ticker,
                        packet.decisionState.value if packet.decisionState else None,
                        packet.confidence,
                        packet.createdAt,
                        json.dumps(payload),
                    ),
                )
        return packet

    def get_packet(self, packet_id: str) -> DecisionPacket | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM review_packet WHERE packet_id = %s",
                    (packet_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return DecisionPacket.model_validate(row["artifact"])

    def list_packets(self, query: PacketQuery) -> list[DecisionPacket]:
        where_clauses: list[str] = []
        params: list[object] = []

        if query.search:
            where_clauses.append("(artifact->>'title' ILIKE %s OR artifact->>'thesis' ILIKE %s)")
            search_like = f"%{query.search}%"
            params.extend([search_like, search_like])
        if query.ticker:
            where_clauses.append("LOWER(ticker) = LOWER(%s)")
            params.append(query.ticker)
        if query.decision_state is not None:
            where_clauses.append("decision_state = %s")
            params.append(query.decision_state.value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
            SELECT artifact
            FROM review_packet
            {where_sql}
            ORDER BY created_at DESC
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

        return [DecisionPacket.model_validate(row["artifact"]) for row in rows]

    def add_packet_audit_event(self, packet_id: str, event: AuditEventCreate) -> DecisionPacket | None:
        packet = self.get_packet(packet_id)
        if packet is None:
            return None

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO decision_audit (packet_id, event_type, detail, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        packet_id,
                        event.eventType,
                        event.detail,
                        json.dumps({"source": "api"}),
                    ),
                )

        packet.audit.append(
            AuditEvent(
                id=f"packet-audit-{len(packet.audit) + 1}",
                timestamp="db_event",
                eventType=event.eventType,
                detail=event.detail,
            )
        )
        return self.save_packet(packet)

    def get_packet_audit(self, packet_id: str) -> list[AuditEvent] | None:
        packet = self.get_packet(packet_id)
        if packet is None:
            return None
        return packet.audit

    def add_metric_snapshot(self, packet_id: str, metric_type: str, metric_payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO metric_snapshot (packet_id, metric_type, metric_payload)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (packet_id, metric_type, json.dumps(metric_payload)),
                )

    def add_outcome_record(self, packet_id: str, outcome: str, outcome_date: str, payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO outcome_record (packet_id, outcome, outcome_date, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (packet_id, outcome, outcome_date, json.dumps(payload)),
                )

    def add_retrieval_event(self, packet_id: str, query_text: str, result_count: int, payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO retrieval_event (packet_id, query_text, result_count, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (packet_id, query_text, result_count, json.dumps(payload)),
                )
