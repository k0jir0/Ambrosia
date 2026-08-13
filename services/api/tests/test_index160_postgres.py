"""PostgreSQL-only Index160 tenant and transition gates."""

from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("INDEX160_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="INDEX160_TEST_DATABASE_URL is only set by the PostgreSQL gate"
)


def _operation_values(organization_id: str, packet_id: str) -> tuple:
    return (
        str(uuid4()),
        organization_id,
        packet_id,
        "a" * 64,
        "b" * 64,
        "00-" + "c" * 32 + "-" + "d" * 16 + "-01",
    )


def test_index160_rls_and_transition_trigger() -> None:
    first, second = str(uuid4()), str(uuid4())
    first_packet, second_packet = f"packet-{uuid4()}", f"packet-{uuid4()}"
    insert_operation = """
        INSERT INTO ollama_review_operations
        (id,organization_id,packet_id,expected_packet_version,semantic_key_hash,state,stage,
         input_hash,deadline_at,trace_id,created_by)
        VALUES (%s,%s,%s,1,%s,'queued','queued',%s,now()+interval '15 minutes',%s,'test')
    """
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "INSERT INTO organizations(id,name,slug) VALUES (%s,'First',%s),(%s,'Second',%s)",
            (first, f"first-{uuid4()}", second, f"second-{uuid4()}"),
        )
        connection.execute(
            """INSERT INTO review_packet(packet_id,organization_id,artifact)
            VALUES (%s,%s,'{}'::jsonb),(%s,%s,'{}'::jsonb)""",
            (first_packet, first, second_packet, second),
        )
        first_values = _operation_values(first, first_packet)
        second_values = _operation_values(second, second_packet)
        connection.execute(insert_operation, first_values)
        connection.execute(insert_operation, second_values)
        connection.commit()

        connection.execute("SET ROLE ambrosia_runtime")
        connection.execute("SELECT set_config('app.current_organization_id',%s,false)", (first,))
        visible = connection.execute(
            "SELECT organization_id FROM ollama_review_operations ORDER BY organization_id"
        ).fetchall()
        assert [str(row[0]) for row in visible] == [first]
        assert connection.execute(
            "UPDATE ollama_review_operations SET stage='forbidden' WHERE organization_id=%s",
            (second,),
        ).rowcount == 0

        operation_id = first_values[0]
        connection.execute(
            "UPDATE ollama_review_operations SET state='leased' WHERE id=%s", (operation_id,)
        )
        with pytest.raises(psycopg.errors.RaiseException):
            connection.execute(
                "UPDATE ollama_review_operations SET state='queued' WHERE id=%s",
                (operation_id,),
            )
        connection.rollback()
