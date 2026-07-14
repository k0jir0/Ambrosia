from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.api.app import calibration_metrics, tool_boundaries, visibility_registry
from services.api.app.feedback import FeedbackRecord, OutcomeResult
from services.api.app.models import AuditEvent, DecisionState
from services.api.app.store import ReviewStore


class _FakeJsonPath:
    def __init__(self, content: str, exists: bool = True) -> None:
        self.content = content
        self._exists = exists

    def exists(self) -> bool:
        return self._exists

    def open(self, *args, **kwargs):
        return StringIO(self.content)


class _FakeMarkdownPath:
    def __init__(self, content: str = "", exists: bool = True) -> None:
        self.content = content
        self._exists = exists

    def exists(self) -> bool:
        return self._exists

    def read_text(self, encoding: str = "utf-8") -> str:
        return self.content

    def stat(self):
        return SimpleNamespace(st_mtime=0)

    def relative_to(self, root):
        return "frontend.md"


def _memory_store(monkeypatch) -> ReviewStore:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REQUIRE_DATABASE", raising=False)
    return ReviewStore()


def test_metrics_cover_review_validity_and_decision_consistency(monkeypatch, review_factory, packet_factory) -> None:
    store = _memory_store(monkeypatch)
    review = review_factory()
    packet = packet_factory().model_copy(
        update={
            "decisionState": DecisionState.watch,
            "audit": [
                *packet_factory().audit,
                AuditEvent(
                    id="audit-convert",
                    timestamp="12:00:00",
                    eventType="review.converted_to_packet",
                    detail="Converted in unit test",
                ),
            ],
        }
    )
    store.save_review(review)
    store.save_packet(packet)

    validity = calibration_metrics.compute_review_validity(store)
    consistency = calibration_metrics.compute_decision_consistency(store)

    assert validity.total_reviews == 1
    assert validity.reviews_converted == 1
    assert validity.conversion_rate == 1.0
    assert validity.status == "ok"
    assert consistency == 1.0


def test_metrics_detect_packet_integrity_and_feedback_calibration(monkeypatch, packet_factory) -> None:
    store = _memory_store(monkeypatch)
    incomplete = packet_factory().model_copy(update={"decisionState": None})
    complete = packet_factory(ticker="QQQ").model_copy(
        update={"id": "pkt-qqq-complete", "decisionState": DecisionState.pursue}
    )
    store.save_packet(incomplete)
    store.save_packet(complete)
    store.save_feedback_record(
        FeedbackRecord(
            packet_id=complete.id,
            decision_state="pursue",
            confidence=60,
            ticker="QQQ",
            asset_class="US equities",
            time_horizon="1-4 weeks",
            outcome_date="2026-07-20",
            outcome=OutcomeResult.won,
        )
    )
    store.recompute_cohort_calibration("QQQ", "US equities", "1-4 weeks")

    integrity = calibration_metrics.compute_packet_integrity(store)
    confidence = calibration_metrics.compute_confidence_calibration(store)

    assert integrity.total_packets == 2
    assert integrity.complete_packets == 1
    assert integrity.missing_fields == {"decisionState": 1}
    assert integrity.status == "warning"
    assert confidence.total_bands >= 1


def test_metrics_board_returns_overall_status(monkeypatch, packet_factory) -> None:
    store = _memory_store(monkeypatch)
    store.save_packet(packet_factory().model_copy(update={"decisionState": DecisionState.watch}))

    board = calibration_metrics.compute_all_metrics(store)

    assert board.packet_integrity.total_packets == 1
    assert board.data_quality.total_packets == 1
    assert board.overall_status in {"ok", "warning", "critical"}


def test_tool_boundaries_are_named_and_have_valid_modes() -> None:
    boundaries = tool_boundaries.list_tool_boundaries()

    assert {boundary.name for boundary in boundaries} >= {
        "Market_data_tools",
        "Retrieval_tools",
        "Backtest_tools",
        "Report_tools",
    }
    assert all(boundary.mode in {"internal", "mcp-compatible"} for boundary in boundaries)


def test_visibility_registry_loads_json_and_markdown_artifacts(monkeypatch) -> None:
    registry_path = _FakeJsonPath(json.dumps([{"name": "unit", "surface": "test"}]))
    markdown_path = _FakeMarkdownPath("# Visibility\nUnit content")

    monkeypatch.setattr(visibility_registry, "ROOT", object())
    monkeypatch.setattr(visibility_registry, "FUNCTION_REGISTRY_PATH", registry_path)

    assert visibility_registry.load_function_registry() == [{"name": "unit", "surface": "test"}]

    loaded = visibility_registry._load_markdown(
        markdown_path,
        missing_detail="missing",
        surface="advanced",
    )
    assert loaded["surface"] == "advanced"
    assert loaded["path"] == "frontend.md"
    assert "Unit content" in loaded["content"]


def test_visibility_registry_missing_artifacts_raise_http_404(monkeypatch) -> None:
    missing_json = _FakeJsonPath("[]", exists=False)
    missing_markdown = _FakeMarkdownPath(exists=False)
    monkeypatch.setattr(visibility_registry, "FUNCTION_REGISTRY_PATH", missing_json)

    with pytest.raises(HTTPException) as registry_error:
        visibility_registry.load_function_registry()
    with pytest.raises(HTTPException) as markdown_error:
        visibility_registry._load_markdown(missing_markdown, missing_detail="missing markdown", surface="advanced")

    assert registry_error.value.status_code == 404
    assert markdown_error.value.status_code == 404
